# -*- coding: utf-8 -*-
"""计费与支付路由：/api/payment/（协议 §6.7）"""
import json
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.billing import credit
from app.config import settings
from app.database import get_db
from app.envelope import ok
from app.models import Order, User
from app.routers.deps import get_current_user

router = APIRouter(prefix="/api/payment", tags=["payment"])

PLANS = {
    "monthly":    {"name": "月度会员", "amount": 99.0,  "credits": 100.0,  "vip_days": 30},
    "quarterly":  {"name": "季度会员", "amount": 269.0, "credits": 300.0,  "vip_days": 90},
    "yearly":     {"name": "年度会员", "amount": 899.0, "credits": 1200.0, "vip_days": 365},
    "credits_50":  {"name": "充值 50 元",  "amount": 50.0,  "credits": 50.0,  "vip_days": 0},
    "credits_200": {"name": "充值 200 元", "amount": 200.0, "credits": 210.0, "vip_days": 0},
}


@router.post("/create/")
def create_order(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    plan_type = body.get("plan_type", "monthly")
    if plan_type not in PLANS:
        return {"code": 1, "msg": "套餐不存在", "data": None}
    plan = PLANS[plan_type]
    order = Order(
        order_no="GP" + time.strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6].upper(),
        user_id=u.id, plan_type=plan_type, payment_method=body.get("payment_method", "alipay"),
        amount=plan["amount"], credits=plan["credits"],
    )
    db.add(order)
    db.commit()
    data = {"order_no": order.order_no, "plan_type": plan_type, "amount": order.amount,
            "payment_method": order.payment_method, "status": order.status}
    if order.payment_method == "alipay":
        data["pay_url"] = "/mock-pay?order_no=" + order.order_no
    else:
        data["qr_code"] = "weixin://wxpay/" + order.order_no
    # 沙箱模式：直接确认到账
    if settings.PAYMENT_SANDBOX:
        _confirm_paid(db, order)
        data["status"] = "paid"
        data["sandbox"] = True
        data["balance_after"] = round(float(_fresh_balance(db, u.id)), 2)
    return ok(data)


def _fresh_balance(db, user_id):
    from sqlalchemy import text
    v = db.execute(text("SELECT balance FROM users WHERE id = :id"), {"id": user_id}).scalar()
    return float(v or 0)


def _confirm_paid(db: Session, order: Order):
    if order.status == "paid":
        return
    order.status = "paid"
    order.paid_at = datetime.utcnow()
    plan = PLANS.get(order.plan_type, {})
    credit(db, order.user_id, order.credits, record_type="recharge",
           description="充值到账（%s）" % plan.get("name", order.plan_type), ref_id=order.order_no)
    if plan.get("vip_days"):
        u = db.query(User).filter_by(id=order.user_id).first()
        if u:
            from datetime import timedelta
            base = u.vip_expires_at if (u.is_vip and u.vip_expires_at and u.vip_expires_at > datetime.utcnow()) else datetime.utcnow()
            u.is_vip = True
            u.vip_expires_at = base + timedelta(days=plan["vip_days"])


@router.get("/status/{order_no}/")
def order_status(order_no: str, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.query(Order).filter_by(order_no=order_no, user_id=u.id).first()
    if not o:
        return {"code": 1, "msg": "订单不存在", "data": None}
    return ok({"order_no": o.order_no, "status": o.status, "amount": o.amount,
               "credits": o.credits, "paid_at": o.paid_at.isoformat() if o.paid_at else None,
               "balance": round(float(_fresh_balance(db, u.id)), 2)})


@router.get("/plans/")
def plans():
    return ok([{"plan_type": k, **v} for k, v in PLANS.items()])


@router.post("/alipay/notify/")
@router.post("/wechat/notify/")
async def pay_notify(request: Request, db: Session = Depends(get_db)):
    """支付回调（沙箱/联调：body 携带 order_no 即确认到账；生产环境需验签）"""
    body = {}
    try:
        import json as _json
        raw = await request.body()
        body = _json.loads(raw.decode()) if raw else {}
    except Exception:
        body = {}
    order_no = body.get("order_no") or request.query_params.get("order_no", "")
    o = db.query(Order).filter_by(order_no=order_no).first() if order_no else None
    if not o:
        return {"code": 1, "msg": "订单不存在", "data": None}
    _confirm_paid(db, o)
    return {"code": 0, "msg": "success", "data": {"order_no": o.order_no, "status": o.status}}
