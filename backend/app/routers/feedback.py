# -*- coding: utf-8 -*-
"""工单/反馈路由：/api/feedback/（协议 §6.8）"""
import json
import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.envelope import ok
from app.models import Ticket, TicketResponse, User
from app.routers.deps import get_current_user

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

CATEGORIES = ["功能异常", "计费问题", "产品建议", "数据问题", "其他"]


def _t_dict(t: Ticket) -> dict:
    return {"id": t.id, "ticket_no": t.ticket_no, "title": t.title, "content": t.content,
            "category": t.category, "priority": t.priority, "status": t.status,
            "ai_analysis": json.loads(t.ai_analysis or "{}"),
            "created_at": t.created_at.isoformat() if t.created_at else "",
            "updated_at": t.updated_at.isoformat() if t.updated_at else ""}


@router.get("/feedbacks/")
def list_feedbacks(page: int = 1, page_size: int = 20, status: str = "",
                   u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Ticket).filter_by(user_id=u.id)
    if status:
        q = q.filter(Ticket.status == status)
    rows = q.order_by(Ticket.id.desc()).all()
    return ok({"count": len(rows), "next": None, "previous": None,
               "results": [_t_dict(t) for t in rows[(page - 1) * page_size: page * page_size]]})


@router.post("/feedbacks/")
def create_feedback(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    t = Ticket(user_id=u.id, ticket_no="TK" + time.strftime("%Y%m%d") + "%04d" % (db.query(Ticket).count() + 1),
               title=body.get("title", ""), content=body.get("content", ""),
               category=body.get("category", "其他"), priority=body.get("priority", "normal"))
    db.add(t)
    db.commit()
    return ok(_t_dict(t))


@router.get("/my-feedbacks/")
def my_feedbacks(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Ticket).filter_by(user_id=u.id).order_by(Ticket.id.desc()).limit(100).all()
    return ok([_t_dict(t) for t in rows])


@router.get("/feedbacks/{tid}/")
def feedback_detail(tid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(Ticket).filter_by(id=tid, user_id=u.id).first()
    if not t:
        return {"code": 1, "msg": "工单不存在", "data": None}
    d = _t_dict(t)
    d["responses"] = [{
        "id": r.id, "responder_type": r.responder_type, "content": r.content,
        "created_at": r.created_at.isoformat(),
    } for r in db.query(TicketResponse).filter_by(ticket_id=tid).order_by(TicketResponse.id).all()]
    return ok(d)


@router.put("/feedbacks/{tid}/")
def feedback_update(tid: int, body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(Ticket).filter_by(id=tid, user_id=u.id).first()
    if not t:
        return {"code": 1, "msg": "工单不存在", "data": None}
    body = body or {}
    for f in ("title", "content", "category", "priority", "status"):
        if f in body:
            setattr(t, f, body[f])
    db.commit()
    return ok(_t_dict(t))


@router.delete("/feedbacks/{tid}/")
def feedback_delete(tid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(TicketResponse).filter_by(ticket_id=tid).delete()
    db.query(Ticket).filter_by(id=tid, user_id=u.id).delete()
    db.commit()
    return ok({"deleted": True})


@router.post("/feedbacks/analyze/")
def analyze_feedback(body: dict, u: User = Depends(get_current_user)):
    """AI 工单分析（确定性规则 mock）"""
    text = (body or {}).get("content", "")
    low = text.lower()
    category = "其他"
    if any(k in low for k in ("余额", "扣费", "计费", "充值")):
        category = "计费问题"
    elif any(k in low for k in ("报错", "失败", "异常", "bug")):
        category = "功能异常"
    elif any(k in low for k in ("建议", "希望", "优化")):
        category = "产品建议"
    analysis = {
        "category_guess": category,
        "priority_guess": "high" if any(k in low for k in ("无法", "不能", "丢失")) else "normal",
        "keywords": [w for w in ("余额", "失败", "检测", "生成", "发布") if w in low],
        "summary": "工单已受理：识别为「%s」，客服将在 1 个工作日内回复。" % category,
    }
    return ok(analysis)


@router.post("/feedbacks/{tid}/respond/")
def respond(tid: int, body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(Ticket).filter_by(id=tid, user_id=u.id).first()
    if not t:
        return {"code": 1, "msg": "工单不存在", "data": None}
    body = body or {}
    r = TicketResponse(ticket_id=tid, responder_id=u.id, responder_type=body.get("responder_type", "user"),
                       content=body.get("content", ""))
    db.add(r)
    t.status = "responded" if body.get("responder_type", "user") != "user" else t.status
    db.commit()
    return ok({"id": r.id, "content": r.content})


@router.post("/feedbacks/{tid}/close/")
def close(tid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(Ticket).filter_by(id=tid, user_id=u.id).first()
    if not t:
        return {"code": 1, "msg": "工单不存在", "data": None}
    t.status = "closed"
    db.commit()
    return ok({"status": "closed"})


@router.get("/feedbacks/{tid}/responses/")
def responses(tid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(TicketResponse).filter_by(ticket_id=tid).order_by(TicketResponse.id).all()
    return ok([{"id": r.id, "responder_type": r.responder_type, "content": r.content,
                "created_at": r.created_at.isoformat()} for r in rows])
