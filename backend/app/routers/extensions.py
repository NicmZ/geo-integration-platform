# -*- coding: utf-8 -*-
"""插件通道与扩展：extension_monitor / social_publisher / content_center / media_db（协议 §6.8）
以及 Partner 协议兼容层（本平台可被当作上游：POST /partners/issue-user-token/）"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.envelope import ok
from app.models import (
    Content, MediaChannel, MediaPlatform, PublishTask, SocialAccount,
    SocialPublishTask, User,
)
from app.routers.deps import get_current_user
from app.security import new_geo_token
from app.engines.publisher import MEDIA_PLATFORMS

router = APIRouter(tags=["extensions"])


# ---------------- 浏览器插件监控 ----------------

@router.get("/api/extension_monitor/publisher-status/")
def publisher_status(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    accs = db.query(SocialAccount).filter_by(user_id=u.id).all()
    online = any(a.cookie_status == "valid" and a.last_heartbeat and
                 (datetime.utcnow() - a.last_heartbeat).total_seconds() < 300 for a in accs)
    auto = any(a.is_auto_mode for a in accs)
    last_hb = max((a.last_heartbeat for a in accs if a.last_heartbeat), default=None)
    return ok({"online": online, "is_auto_mode": auto,
               "last_heartbeat": last_hb.isoformat() if last_hb else None})


@router.post("/api/extension_monitor/heartbeat/")
def heartbeat(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    key = body.get("platform_key", "")
    acc = db.query(SocialAccount).filter_by(user_id=u.id, platform_key=key).first() if key else None
    if acc:
        acc.last_heartbeat = datetime.utcnow()
        acc.cookie_status = body.get("cookie_status", acc.cookie_status)
        db.commit()
    return ok({"received": True})


# ---------------- 社交发布（插件通道） ----------------

@router.get("/api/social_publisher/accounts/")
def social_accounts(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(SocialAccount).filter_by(user_id=u.id).all()
    return ok([{"id": a.id, "platform_key": a.platform_key, "account_name": a.account_name,
                "avatar": a.avatar, "cookie_status": a.cookie_status, "is_auto_mode": a.is_auto_mode,
                "last_heartbeat": a.last_heartbeat.isoformat() if a.last_heartbeat else None,
                "enabled": a.enabled} for a in rows])


@router.post("/api/social_publisher/accounts/")
def add_social_account(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    a = SocialAccount(user_id=u.id, platform_key=body.get("platform_key", ""),
                      account_name=body.get("account_name", ""), avatar=body.get("avatar", ""),
                      cookie_status=body.get("cookie_status", "valid"))
    db.add(a)
    db.commit()
    return ok({"id": a.id, "platform_key": a.platform_key, "account_name": a.account_name})


@router.delete("/api/social_publisher/accounts/{aid}/")
def del_social_account(aid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(SocialAccount).filter_by(id=aid, user_id=u.id).delete()
    db.commit()
    return ok({"deleted": True})


@router.post("/api/social_publisher/publish/create/")
def social_publish_create(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """插件发布通道：{content_ids, target_accounts:[platform_key 或 account_id]}"""
    body = body or {}
    content_ids = body.get("content_ids") or []
    targets = body.get("target_accounts") or []
    created = []
    for cid in content_ids:
        c = db.query(Content).filter_by(id=cid, user_id=u.id).first()
        if not c:
            continue
        for t in targets:
            platform = t if isinstance(t, str) else (db.query(SocialAccount).filter_by(id=t).first().platform_key
                                                     if db.query(SocialAccount).filter_by(id=t).first() else "")
            if not platform:
                continue
            spt = SocialPublishTask(user_id=u.id, content_id=cid, platform_key=platform)
            db.add(spt)
            db.flush()
            pt = PublishTask(user_id=u.id, content_id=cid, platform_key=platform)
            db.add(pt)
            db.flush()
            from app.routers.deps import submit_task
            submit_task(db, "publish_dispatch", {"publish_task_ids": [pt.id]}, tenant=str(u.id))
            spt.status = "dispatched"
            created.append({"social_task_id": spt.id, "publish_task_id": pt.id, "platform": platform})
    db.commit()
    return ok({"count": len(created), "tasks": created})


@router.get("/api/social_publisher/tasks/")
def social_tasks(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(SocialPublishTask).filter_by(user_id=u.id).limit(100).all()
    out = []
    for s in rows:
        pt = db.query(PublishTask).filter_by(id=s.id).first()
        out.append({"id": s.id, "content_id": s.content_id, "platform_key": s.platform_key,
                    "status": s.status, "result_url": s.result_url,
                    "publish_status": pt.status if pt else None,
                    "created_at": s.created_at.isoformat()})
    return ok(out)


@router.post("/api/social_publisher/tasks/{tid}/retry/")
def social_retry(tid: str, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.query(SocialPublishTask).filter_by(id=tid, user_id=u.id).first()
    if not s:
        return {"code": 1, "msg": "任务不存在", "data": None}
    pt = db.query(PublishTask).filter_by(id=s.id).first()
    if pt:
        pt.status = "pending"
        from app.routers.deps import submit_task
        submit_task(db, "publish_dispatch", {"publish_task_ids": [pt.id]}, tenant=str(u.id))
        s.status = "dispatched"
        db.commit()
    return ok({"retried": True})


@router.post("/api/content_center/save-temp/")
def save_temp(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    c = Content(user_id=u.id, title=body.get("title", ""), body=body.get("body", ""), status="draft")
    db.add(c)
    db.commit()
    return ok({"content_id": c.id, "status": "draft"})


# ---------------- 媒体库 ----------------

@router.get("/api/media_db/media/")
def media_db(request: Request, channel: str = "", platform: str = "", search: str = "",
             page: int = 1, page_size: int = 20, u: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    q = db.query(MediaChannel)
    if channel:
        q = q.filter(MediaChannel.category == channel.upper())
    if platform:
        q = q.filter(MediaChannel.platform_key == platform)
    if search:
        q = q.filter(MediaChannel.channel_name.like("%" + search + "%"))
    total = q.count()
    rows = q.order_by(MediaChannel.followers.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ok({
        "items": [{"id": m.id, "platform_key": m.platform_key, "channel_name": m.channel_name,
                   "category": m.category, "account": m.account, "followers": m.followers,
                   "price": m.price, "status": m.status, "channel_url": m.channel_url} for m in rows],
        "total": total, "page": page, "page_size": page_size,
    })


# ---------------- Partner 协议兼容层（本平台可被当作上游） ----------------

@router.post("/partners/issue-user-token/")
def issue_user_token(body: dict, request: Request, db: Session = Depends(get_db)):
    """Partner 协议：X-Partner-Key 换取第三方用户接入码（协议 §3）"""
    partner_key = request.headers.get("X-Partner-Key", "")
    if partner_key != settings.PARTNER_KEY:
        return {"__status__": 403, "body": {"code": 1, "msg": "invalid partner key", "data": None}}
    third_party_user_id = (body or {}).get("third_party_user_id", "")
    if not third_party_user_id:
        return {"code": 1, "msg": "third_party_user_id required", "data": None}
    u = db.query(User).filter_by(username="partner:" + third_party_user_id).first()
    if not u:
        from app.security import hash_password
        import secrets
        u = User(username="partner:" + third_party_user_id, password_hash=hash_password(secrets.token_hex(16)))
        db.add(u)
        db.flush()
        from app.models import CompanyProfile
        db.add(CompanyProfile(user_id=u.id))
    u.geo_token = new_geo_token()
    db.commit()
    return {"data": {"token": u.geo_token}, "token": u.geo_token}   # 兼容两种解析方式
