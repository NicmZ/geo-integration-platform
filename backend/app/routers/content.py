# -*- coding: utf-8 -*-
"""内容中心与全渠道发布：/api/content/（协议 §6.4）"""
import base64
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.billing import charge, get_price
from app.database import get_db
from app.envelope import ok
from app.models import (
    Brand, Content, Keyword, MediaPlatform, PublishTask, User,
)
from app.routers.deps import get_current_user, submit_task
from app.engines.publisher import MEDIA_PLATFORMS

router = APIRouter(prefix="/api/content", tags=["content"])


def _content_dict(c: Content) -> dict:
    return {
        "id": c.id, "title": c.title, "keywords": json.loads(c.keywords or "[]"),
        "brand_id": c.brand_id, "category": c.category, "length": c.length,
        "summary": c.summary, "body": c.body, "engine_key": c.engine_key,
        "status": c.status, "cover_url": c.cover_url, "cost": c.cost,
        "created_at": c.created_at.isoformat() if c.created_at else "",
        "updated_at": c.updated_at.isoformat() if c.updated_at else "",
    }


@router.get("/content/")
def list_content(request: Request, page: int = 1, page_size: int = 20, search: str = "",
                 status: str = "", u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Content).filter_by(user_id=u.id)
    if search:
        q = q.filter(Content.title.like("%" + search + "%"))
    if status:
        q = q.filter(Content.status == status)
    items = q.order_by(Content.id.desc()).all()
    data = {
        "count": len(items), "next": None, "previous": None,
        "results": [_content_dict(c) for c in items[(page - 1) * page_size: page * page_size]],
    }
    return ok(data)


@router.post("/content/")
def create_content(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    c = Content(
        user_id=u.id, title=body.get("title", ""), keywords=json.dumps(body.get("keywords") or [], ensure_ascii=False),
        brand_id=body.get("brand_id"), category=body.get("category", ""), length=body.get("length", 1200),
        summary=body.get("summary", ""), body=body.get("body", ""), engine_key=body.get("engine_key", "deepseek"),
        special_requirements=body.get("special_requirements", ""),
        status="draft" if body.get("body") else "generating",
    )
    db.add(c)
    db.commit()
    return ok(_content_dict(c))


@router.get("/content/{cid}/")
def get_content(cid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.query(Content).filter_by(id=cid, user_id=u.id).first()
    if not c:
        return {"code": 1, "msg": "内容不存在", "data": None}
    return ok(_content_dict(c))


@router.put("/content/{cid}/")
@router.patch("/content/{cid}/")
def update_content(cid: int, body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.query(Content).filter_by(id=cid, user_id=u.id).first()
    if not c:
        return {"code": 1, "msg": "内容不存在", "data": None}
    body = body or {}
    body.pop("created_by", None)   # 协议：PUT/PATCH 剥离 created_by
    for f in ("title", "category", "summary", "body", "engine_key", "special_requirements", "status", "cover_url"):
        if f in body:
            setattr(c, f, body[f])
    if "keywords" in body:
        c.keywords = json.dumps(body["keywords"] or [], ensure_ascii=False)
    if "brand" in body:
        c.brand_id = body["brand"]
    c.updated_at = datetime.utcnow()
    db.commit()
    return ok(_content_dict(c))


@router.delete("/content/{cid}/")
def delete_content(cid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Content).filter_by(id=cid, user_id=u.id).delete()
    db.commit()
    return ok({"deleted": True})


@router.post("/content/generate-content/")
def generate_content(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """AI 内容生成（计费 CONTENT_GENERATE，任务异步执行）
    body: {title, keywords:[], brand:[local_id], cost, length, summary, category, engine_platform_key, special_requirements}"""
    body = body or {}
    if not body.get("title"):
        return {"code": 1, "msg": "标题不能为空", "data": None}
    brand_ids = body.get("brand") or []
    brand_id = None
    if isinstance(brand_ids, int):
        brand_id = brand_ids
    elif brand_ids:
        brand_id = brand_ids[0]
    if brand_id:
        b = db.query(Brand).filter_by(id=brand_id, user_id=u.id).first()
        if not b:
            return {"code": 1, "msg": "品牌不存在", "data": None}

    standard = float(body.get("cost") or 0)
    price = get_price(db, "CONTENT_GENERATE", standard_cost=standard)
    balance_after = charge(db, u.id, "CONTENT_GENERATE", price, description="AI 内容生成：%s" % body.get("title", ""))
    if balance_after is None:
        return {"__status__": 402, "body": {"code": 402, "msg": "余额不足，请先充值", "data": None}}

    c = Content(
        user_id=u.id, brand_id=brand_id, title=body.get("title", ""),
        keywords=json.dumps(body.get("keywords") or [], ensure_ascii=False),
        category=body.get("category", ""), length=int(body.get("length") or 1200),
        summary=body.get("summary", ""), engine_key=body.get("engine_platform_key") or body.get("engine_key") or "deepseek",
        special_requirements=body.get("special_requirements", ""), status="generating", cost=price,
    )
    db.add(c)
    db.flush()
    task_id = submit_task(db, "content_generate", {"content_id": c.id}, tenant=str(u.id))
    db.commit()
    data = {"content_id": c.id, "task_id": task_id, "cost": price, "balance_after": balance_after, "status": "generating"}
    return ok(data)


@router.post("/content/upload-image/")
async def upload_image(file: UploadFile = File(None), u: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """图片上传（本地实现：dataURL 引用；生产可替换为对象存储）"""
    if file is None:
        return {"code": 1, "msg": "缺少文件字段 file", "data": None}
    data = await file.read()
    if len(data) > 2 * 1024 * 1024:
        return {"code": 1, "msg": "图片不能超过 2MB", "data": None}
    b64 = base64.b64encode(data).decode()
    url = "data:%s;base64,%s" % (file.content_type or "image/png", b64)
    return ok({"url": url, "filename": file.filename})


@router.get("/media-platforms/")
def media_platforms(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for i, (key, name, imgs, api_type) in enumerate(MEDIA_PLATFORMS):
        if not db.query(MediaPlatform).filter_by(key=key).first():
            db.add(MediaPlatform(key=key, name=name, enabled=True, supports_images=imgs,
                                 api_type=api_type, order=i))
    db.commit()
    rows = db.query(MediaPlatform).order_by(MediaPlatform.order).all()
    return ok([{"key": p.key, "name": p.name, "enabled": p.enabled,
                "supports_images": p.supports_images, "api_type": p.api_type} for p in rows])


# ---------------- 发布任务 ----------------

def _pt_dict(p: PublishTask) -> dict:
    return {
        "id": p.id, "content_id": p.content_id, "platform_key": p.platform_key,
        "status": p.status, "cost": p.cost, "publish_url": p.publish_url, "error": p.error,
        "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else "",
        "finished_at": p.finished_at.isoformat() if p.finished_at else None,
    }


def _create_publish_tasks(u, content_id, platforms, db, scheduled_at=None):
    content = db.query(Content).filter_by(id=content_id, user_id=u.id).first()
    if not content:
        return None
    price = get_price(db, "CONTENT_PUBLISH", standard_cost=5.0)
    tasks = []
    for key in platforms:
        balance_after = charge(db, u.id, "CONTENT_PUBLISH", price,
                               description="发布到 %s：%s" % (key, content.title), ref_id=content_id)
        if balance_after is None:
            break
        pt = PublishTask(user_id=u.id, content_id=content_id, platform_key=key,
                         cost=price, scheduled_at=scheduled_at)
        db.add(pt)
        db.flush()
        task_id = submit_task(db, "publish_dispatch", {"publish_task_ids": [pt.id]}, tenant=str(u.id))
        pt.scheduler_task_id = task_id
        tasks.append(pt)
    db.commit()
    return tasks


@router.post("/publish-tasks/")
def create_publish_task(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """{content_id, platforms:[key...], scheduled_at?}"""
    body = body or {}
    content_id = body.get("content_id")
    platforms = body.get("platforms") or []
    if not content_id or not platforms:
        return {"code": 1, "msg": "content_id 与 platforms 必填", "data": None}
    sa = None
    if body.get("scheduled_at"):
        try:
            sa = datetime.fromisoformat(body["scheduled_at"].replace("Z", ""))
        except Exception:
            sa = None
    tasks = _create_publish_tasks(u, content_id, platforms, db, sa)
    if tasks is None:
        return {"code": 1, "msg": "内容不存在", "data": None}
    return ok({"count": len(tasks), "tasks": [_pt_dict(p) for p in tasks]})


@router.get("/publish-tasks/")
def list_publish_tasks(request: Request, page: int = 1, page_size: int = 20, status: str = "",
                       content_id: int = None, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(PublishTask).filter_by(user_id=u.id)
    if status:
        q = q.filter(PublishTask.status == status)
    if content_id:
        q = q.filter(PublishTask.content_id == content_id)
    items = q.order_by(PublishTask.created_at.desc()).limit(500).all()
    results = [_pt_dict(p) for p in items[(page - 1) * page_size: page * page_size]]
    return ok({"count": len(items), "next": None, "previous": None, "results": results})


@router.get("/publish-tasks/{pid}/")
def publish_task_detail(pid: str, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(PublishTask).filter_by(id=pid, user_id=u.id).first()
    if not p:
        return {"code": 1, "msg": "任务不存在", "data": None}
    return ok(_pt_dict(p))


@router.delete("/publish-tasks/{pid}/")
def delete_publish_task(pid: str, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(PublishTask).filter_by(id=pid, user_id=u.id).delete()
    db.commit()
    return ok({"deleted": True})


@router.post("/publish-tasks/{pid}/cancel/")
def cancel_publish_task(pid: str, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(PublishTask).filter_by(id=pid, user_id=u.id).first()
    if not p:
        return {"code": 1, "msg": "任务不存在", "data": None}
    if p.status in ("success",):
        return {"code": 1, "msg": "已发布任务不可取消", "data": None}
    p.status = "cancelled"
    p.finished_at = datetime.utcnow()
    db.commit()
    return ok(_pt_dict(p))


@router.post("/publish-tasks/{pid}/retry/")
def retry_publish_task(pid: str, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(PublishTask).filter_by(id=pid, user_id=u.id).first()
    if not p:
        return {"code": 1, "msg": "任务不存在", "data": None}
    p.status = "pending"
    p.error = ""
    task_id = submit_task(db, "publish_dispatch", {"publish_task_ids": [p.id]}, tenant=str(u.id))
    p.scheduler_task_id = task_id
    db.commit()
    return ok(_pt_dict(p))


@router.post("/publish-tasks/bulk-publish/")
def bulk_publish(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """批量发布（计费 CONTENT_PUBLISH）：{content_ids:[], platforms:[]}"""
    body = body or {}
    content_ids = body.get("content_ids") or []
    platforms = body.get("platforms") or []
    if not content_ids or not platforms:
        return {"code": 1, "msg": "content_ids 与 platforms 必填", "data": None}
    all_tasks = []
    for cid in content_ids[:20]:
        tasks = _create_publish_tasks(u, cid, platforms, db)
        if tasks:
            all_tasks.extend(tasks)
    return ok({"count": len(all_tasks),
               "total_cost": round(sum(t.cost for t in all_tasks), 2),
               "tasks": [_pt_dict(p) for p in all_tasks]})


@router.post("/publish-tasks/export/")
def export_publish_tasks(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import csv as _csv
    import io as _io
    rows = db.query(PublishTask).filter_by(user_id=u.id).order_by(PublishTask.created_at.desc()).limit(1000).all()
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["task_id", "content_id", "platform", "status", "cost", "publish_url", "created_at"])
    for p in rows:
        w.writerow([p.id, p.content_id, p.platform_key, p.status, p.cost, p.publish_url,
                    p.created_at.isoformat() if p.created_at else ""])
    buf.seek(0)
    return StreamingResponse(iter(["\ufeff" + buf.read()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=publish_tasks.csv"})
