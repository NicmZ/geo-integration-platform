# -*- coding: utf-8 -*-
"""路由公共依赖：JWT 鉴权、信封响应、调度任务提交助手"""
import json

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else (auth[6:] if auth.startswith("Token ") else auth)
    user_id = decode_token(token.strip())
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    user = db.query(User).filter_by(id=user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def submit_task(db: Session, task_type: str, payload: dict, tenant: str, priority: int = 5, cores: int = 1):
    from app.scheduler import core
    return core.enqueue(db, task_type, payload, tenant=tenant, priority=priority, cpu_cores=cores)


def user_brief(u: User) -> dict:
    return {"id": u.id, "username": u.username, "email": u.email, "is_vip": bool(u.is_vip)}
