# -*- coding: utf-8 -*-
"""用户与账号路由：/api/users/（协议 §6.1）"""
import random

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.billing import credit
from app.config import settings
from app.database import get_db
from app.envelope import ok
from app.models import CompanyProfile, User, Brand
from app.routers.deps import get_current_user, user_brief
from app.security import (
    check_captcha, create_token, gen_captcha, hash_password, new_geo_token, verify_password,
)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/captcha/")
def captcha():
    token, image = gen_captcha()
    return ok({"captcha_image": image, "captcha_token": token, "require_case_sensitive": False})


@router.post("/check_phone/")
def check_phone(body: dict, db: Session = Depends(get_db)):
    phone = (body or {}).get("phone", "")
    exists = db.query(User).filter_by(phone=phone).first() is not None
    return ok({"exists": exists})


@router.post("/sms_code/")
def sms_code(body: dict):
    """短信验证码（本地实现为 mock：日志输出，返回 sent=true）"""
    code = "%06d" % random.randint(0, 999999)
    print("[sms_code] phone=%s code=%s (mock)" % ((body or {}).get("phone", ""), code))
    return ok({"sent": True})


@router.post("/register/")
def register(body: dict, db: Session = Depends(get_db)):
    body = body or {}
    if settings.CAPTCHA_ENABLED and not check_captcha(body.get("captcha_token", ""), body.get("captcha_code", body.get("captcha", ""))):
        return {"code": 1, "msg": "验证码错误或已过期", "data": None}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if len(username) < 3 or len(password) < 6:
        return {"code": 1, "msg": "用户名至少 3 位，密码至少 6 位", "data": None}
    if db.query(User).filter_by(username=username).first():
        return {"code": 1, "msg": "用户名已存在", "data": None}
    u = User(
        username=username, email=body.get("email", ""), phone=body.get("phone", ""),
        password_hash=hash_password(password), geo_token=new_geo_token(),
    )
    db.add(u)
    db.flush()
    db.add(CompanyProfile(user_id=u.id))
    if settings.REGISTER_GIFT_BALANCE > 0:
        db.commit()
        credit(db, u.id, settings.REGISTER_GIFT_BALANCE, record_type="gift",
               description="注册赠送体验金", action_type="REGISTER_GIFT")
    else:
        db.commit()
    return ok({"token": create_token(u.id), "user": user_brief(u)})


@router.post("/login/")
def login(body: dict, db: Session = Depends(get_db)):
    body = body or {}
    u = db.query(User).filter_by(username=body.get("username", "")).first()
    if not u or not verify_password(body.get("password", ""), u.password_hash):
        return {"code": 1, "msg": "用户名或密码错误", "data": None}
    if not u.is_active:
        return {"code": 1, "msg": "账号已禁用", "data": None}
    return ok({"token": create_token(u.id), "user": user_brief(u)})


@router.post("/logout/")
def logout():
    return ok({"success": True})


def _profile_data(u: User, db: Session) -> dict:
    cp = db.query(CompanyProfile).filter_by(user_id=u.id).first()
    brands = db.query(Brand).filter_by(user_id=u.id).all()
    return {
        "id": u.id, "username": u.username, "email": u.email, "phone": u.phone,
        "is_vip": bool(u.is_vip), "vip_expires_at": u.vip_expires_at.isoformat() if u.vip_expires_at else None,
        "balance": round(float(u.balance), 2), "local_balance": round(float(u.local_balance), 2),
        "company": cp.company_name if cp else "",
        "company_profile": {
            "company_name": cp.company_name if cp else "", "industry": cp.industry if cp else "",
            "website": cp.website if cp else "", "contact": cp.contact if cp else "",
            "logo": cp.logo if cp else "", "description": cp.description if cp else "",
        } if cp else {},
        "brands": [{"id": b.id, "name": b.name, "brand_type": b.brand_type} for b in brands],
    }


@router.get("/profile/")
def profile(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(_profile_data(u, db))


@router.get("/my-token/")
def my_token_get(u: User = Depends(get_current_user)):
    return ok({"token": u.geo_token, "created_at": u.created_at.isoformat() if u.created_at else ""})


@router.post("/my-token/")
def my_token_reset(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """强制重置接入码，旧码失效"""
    u.geo_token = new_geo_token()
    db.commit()
    return ok({"token": u.geo_token, "created_at": u.created_at.isoformat() if u.created_at else ""})
