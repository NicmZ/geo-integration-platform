# -*- coding: utf-8 -*-
"""账户信息路由：/api/account_info/（协议 §6.5）"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.billing import charge, get_price
from app.config import settings
from app.database import get_db
from app.envelope import ok
from app.models import (
    Brand, BrandDocument, CompanyProfile, KnowledgeBase, KbTask, KbVersion,
    KeywordSetting, LocalConsumptionRecord, User,
)
from app.routers.deps import get_current_user, submit_task

router = APIRouter(prefix="/api/account_info", tags=["account_info"])

INDUSTRIES = [
    {"id": 1, "name": "IT/互联网/电子"}, {"id": 2, "name": "制造业"},
    {"id": 3, "name": "医疗健康"}, {"id": 4, "name": "教育培训"},
    {"id": 5, "name": "金融保险"}, {"id": 6, "name": "电商零售"},
    {"id": 7, "name": "汽车出行"}, {"id": 8, "name": "房产建筑"},
    {"id": 9, "name": "文化传媒"}, {"id": 10, "name": "生活服务"},
    {"id": 11, "name": "能源化工"}, {"id": 12, "name": "政府/非营利"},
]

DEFAULT_KNOWLEDGE_TEMPLATE = (
    "GEO 优化要点：\n"
    "1. 品牌介绍保持客观、可验证，包含成立时间、主营业务、资质认证。\n"
    "2. 输出内容结论先行、分点论述，关键词密度控制在 2%-3%。\n"
    "3. 所有数据断言附来源，避免《广告法》绝对化用语。\n"
    "4. 定期（月度）更新知识库，保持 AI 引擎抓取到最新信息。"
)


@router.get("/industries/")
def industries():
    return ok(INDUSTRIES)


@router.get("/company-profile/")
def get_company_profile(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cp = db.query(CompanyProfile).filter_by(user_id=u.id).first()
    if not cp:
        cp = CompanyProfile(user_id=u.id)
        db.add(cp)
        db.commit()
    return ok({"company_name": cp.company_name, "industry": cp.industry, "website": cp.website,
               "contact": cp.contact, "logo": cp.logo, "description": cp.description})


@router.put("/company-profile/")
@router.patch("/company-profile/")
def update_company_profile(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    cp = db.query(CompanyProfile).filter_by(user_id=u.id).first()
    if not cp:
        cp = CompanyProfile(user_id=u.id)
        db.add(cp)
    for f in ("company_name", "industry", "website", "contact", "logo", "description"):
        if f in body:
            setattr(cp, f, body[f])
    db.commit()
    return ok({"company_name": cp.company_name, "industry": cp.industry, "website": cp.website,
               "contact": cp.contact, "logo": cp.logo, "description": cp.description})


def _brand_dict(b: Brand) -> dict:
    return {"id": b.id, "name": b.name, "brand_type": b.brand_type, "description": b.description,
            "documents_count": len(b.documents or []),
            "created_at": b.created_at.isoformat() if b.created_at else ""}


@router.get("/brands/")
def list_brands(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Brand).filter_by(user_id=u.id).all()
    return ok({"count": len(rows), "next": None, "previous": None,
               "results": [_brand_dict(b) for b in rows]})


@router.post("/brands/")
def create_brand(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    name = (body.get("name") or "").strip()
    if not name:
        return {"code": 1, "msg": "品牌名不能为空", "data": None}
    if db.query(Brand).filter_by(user_id=u.id, name=name).first():
        return {"code": 1, "msg": "同名品牌已存在", "data": None}
    b = Brand(user_id=u.id, name=name, brand_type=body.get("brand_type", "main"),
              description=body.get("description", ""))
    db.add(b)
    db.commit()
    return ok(_brand_dict(b))


@router.get("/brands/{bid}/")
def get_brand(bid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.query(Brand).filter_by(id=bid, user_id=u.id).first()
    if not b:
        return {"code": 1, "msg": "品牌不存在", "data": None}
    return ok(_brand_dict(b))


@router.put("/brands/{bid}/")
@router.patch("/brands/{bid}/")
def update_brand(bid: int, body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.query(Brand).filter_by(id=bid, user_id=u.id).first()
    if not b:
        return {"code": 1, "msg": "品牌不存在", "data": None}
    body = body or {}
    for f in ("name", "brand_type", "description"):
        if f in body:
            setattr(b, f, body[f])
    db.commit()
    return ok(_brand_dict(b))


@router.delete("/brands/{bid}/")
def delete_brand(bid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Brand).filter_by(id=bid, user_id=u.id).delete()
    db.commit()
    return ok({"deleted": True})


@router.get("/brands/{bid}/documents/")
def list_documents(bid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(BrandDocument).filter_by(brand_id=bid).all()
    return ok({"count": len(rows), "results": [{
        "id": d.id, "brand_id": d.brand_id, "filename": d.filename, "doc_type": d.doc_type,
        "status": d.status, "content": (d.content or "")[:200],
        "created_at": d.created_at.isoformat()} for d in rows]})


@router.post("/brands/{bid}/documents/")
def create_document(bid: int, body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    b = db.query(Brand).filter_by(id=bid, user_id=u.id).first()
    if not b:
        return {"code": 1, "msg": "品牌不存在", "data": None}
    d = BrandDocument(brand_id=bid, filename=body.get("filename", "未命名"),
                      doc_type=body.get("doc_type", "text"), content=body.get("content", ""))
    db.add(d)
    db.commit()
    return ok({"id": d.id, "filename": d.filename, "status": d.status})


@router.delete("/brands/{bid}/documents/{doc_id}/")
def delete_document(bid: int, doc_id: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(BrandDocument).filter_by(id=doc_id, brand_id=bid).delete()
    db.commit()
    return ok({"deleted": True})


@router.get("/brands/{bid}/keyword-settings/")
def get_keyword_settings(bid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.query(KeywordSetting).filter_by(user_id=u.id, brand_id=bid).first()
    if not s:
        return ok({"brand_id": bid, "settings": {}})
    return ok({"brand_id": bid, "settings": json.loads(s.settings or "{}"), "updated_at": s.updated_at.isoformat()})


@router.put("/brands/{bid}/keyword-settings/")
def put_keyword_settings(bid: int, body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.query(KeywordSetting).filter_by(user_id=u.id, brand_id=bid).first()
    if not s:
        s = KeywordSetting(user_id=u.id, brand_id=bid)
        db.add(s)
    s.settings = json.dumps(body or {}, ensure_ascii=False)
    db.commit()
    return ok({"brand_id": bid, "settings": json.loads(s.settings), "updated_at": s.updated_at.isoformat()})


# ---------------- 知识库 ----------------

def _kb_dict(k: KnowledgeBase) -> dict:
    return {"id": k.id, "brand_id": k.brand_id, "title": k.title,
            "content": (k.content or "")[:500], "status": k.status, "version": k.version,
            "published_at": k.published_at.isoformat() if k.published_at else None,
            "updated_at": k.updated_at.isoformat() if k.updated_at else ""}


@router.get("/knowledge-base/")
def list_kb(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(KnowledgeBase).filter_by(user_id=u.id).all()
    return ok({"count": len(rows), "next": None, "previous": None, "results": [_kb_dict(k) for k in rows]})


@router.post("/knowledge-base/")
def create_kb(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    if not body.get("brand_id"):
        return {"code": 1, "msg": "brand_id 必填", "data": None}
    k = KnowledgeBase(user_id=u.id, brand_id=body["brand_id"], title=body.get("title", ""),
                      content=body.get("content", ""), status=body.get("status", "draft"))
    db.add(k)
    db.flush()
    db.add(KbVersion(kb_id=k.id, version_no=1, content=k.content))
    db.commit()
    return ok(_kb_dict(k))


@router.get("/knowledge-base/brand/{bid}/")
def kb_of_brand(bid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(KnowledgeBase).filter_by(user_id=u.id, brand_id=bid).all()
    return ok({"count": len(rows), "results": [_kb_dict(k) for k in rows]})


@router.get("/knowledge-base/{kid}/")
def kb_detail(kid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    k = db.query(KnowledgeBase).filter_by(id=kid, user_id=u.id).first()
    if not k:
        return {"code": 1, "msg": "知识库不存在", "data": None}
    d = _kb_dict(k)
    d["content"] = k.content
    return ok(d)


@router.put("/knowledge-base/{kid}/")
def kb_update(kid: int, body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    k = db.query(KnowledgeBase).filter_by(id=kid, user_id=u.id).first()
    if not k:
        return {"code": 1, "msg": "知识库不存在", "data": None}
    body = body or {}
    if "title" in body:
        k.title = body["title"]
    if "content" in body:
        k.content = body["content"]
        k.version += 1
        db.add(KbVersion(kb_id=k.id, version_no=k.version, content=k.content))
    db.commit()
    return ok(_kb_dict(k))


@router.delete("/knowledge-base/{kid}/")
def kb_delete(kid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(KnowledgeBase).filter_by(id=kid, user_id=u.id).delete()
    db.commit()
    return ok({"deleted": True})


@router.post("/knowledge-base/create-task/")
def kb_create_task(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """构建品牌知识库（计费 BRAND_KNOWLEDGE fixed ¥10）
    body: {brand: local_id}"""
    body = body or {}
    brand_id = body.get("brand") or body.get("brand_id")
    b = db.query(Brand).filter_by(id=brand_id, user_id=u.id).first() if brand_id else None
    if not b:
        return {"code": 1, "msg": "品牌不存在", "data": None}
    price = get_price(db, "BRAND_KNOWLEDGE")
    balance_after = charge(db, u.id, "BRAND_KNOWLEDGE", price,
                           description="品牌知识库构建：%s" % b.name, ref_id=str(b.id))
    if balance_after is None:
        return {"__status__": 402, "body": {"code": 402, "msg": "余额不足，请先充值", "data": None}}
    task = KbTask(user_id=u.id, brand_id=b.id, task_type="build")
    db.add(task)
    db.flush()
    task_id = submit_task(db, "kb_build", {"kb_task_id": task.id}, tenant=str(u.id))
    task.scheduler_task_id = task_id
    db.commit()
    return ok({"task_id": task_id, "kb_task_id": task.id, "brand_id": b.id,
               "cost": price, "balance_after": balance_after, "status": "PENDING"})


@router.put("/knowledge-base/{kid}/publish/")
def kb_publish(kid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    k = db.query(KnowledgeBase).filter_by(id=kid, user_id=u.id).first()
    if not k:
        return {"code": 1, "msg": "知识库不存在", "data": None}
    k.status = "published"
    k.published_at = datetime.utcnow()
    db.commit()
    return ok(_kb_dict(k))


@router.get("/knowledge-base/{kid}/history/")
def kb_history(kid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    k = db.query(KnowledgeBase).filter_by(id=kid, user_id=u.id).first()
    if not k:
        return {"code": 1, "msg": "知识库不存在", "data": None}
    rows = db.query(KbVersion).filter_by(kb_id=kid).order_by(KbVersion.version_no.desc()).all()
    return ok([{"version_no": v.version_no, "content_length": len(v.content or ""),
                "created_at": v.created_at.isoformat()} for v in rows])


@router.post("/knowledge-base/{kid}/restore/")
def kb_restore(kid: int, body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    k = db.query(KnowledgeBase).filter_by(id=kid, user_id=u.id).first()
    if not k:
        return {"code": 1, "msg": "知识库不存在", "data": None}
    v = db.query(KbVersion).filter_by(kb_id=kid, version_no=body.get("version_no")).first()
    if not v:
        return {"code": 1, "msg": "版本不存在", "data": None}
    k.content = v.content
    k.version += 1
    db.add(KbVersion(kb_id=k.id, version_no=k.version, content=k.content))
    db.commit()
    return ok(_kb_dict(k))


@router.get("/knowledge-base/check/{bid}/")
def kb_check(bid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """知识库体检：完整性检查"""
    b = db.query(Brand).filter_by(id=bid, user_id=u.id).first()
    if not b:
        return {"code": 1, "msg": "品牌不存在", "data": None}
    kb = db.query(KnowledgeBase).filter_by(brand_id=bid).first()
    docs = db.query(BrandDocument).filter_by(brand_id=bid).count()
    items = [
        {"item": "品牌介绍", "ok": bool(b.description)},
        {"item": "资料文档", "ok": docs > 0, "detail": "%d 份" % docs},
        {"item": "知识库已构建", "ok": kb is not None},
        {"item": "知识库已发布", "ok": bool(kb and kb.status == "published")},
    ]
    return ok({"brand_id": bid, "items": items,
               "healthy": all(i["ok"] for i in items)})


@router.get("/knowledge-base/brand/{bid}/tasks/")
def kb_brand_tasks(bid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(KbTask).filter_by(user_id=u.id, brand_id=bid).order_by(KbTask.created_at.desc()).limit(50).all()
    return ok([{"task_id": t.id, "status": t.status, "progress": t.progress,
                "created_at": t.created_at.isoformat()} for t in rows])


@router.get("/knowledge-base/user-tasks/")
def kb_user_tasks(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(KbTask).filter_by(user_id=u.id).order_by(KbTask.created_at.desc()).limit(50).all()
    return ok([{"task_id": t.id, "brand_id": t.brand_id, "status": t.status, "progress": t.progress,
                "created_at": t.created_at.isoformat()} for t in rows])


@router.get("/default-knowledge-content/")
def default_kb(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok({"content": DEFAULT_KNOWLEDGE_TEMPLATE})


# ---------------- 余额与流水 ----------------

@router.get("/balance")
@router.get("/balance/")
def balance(u: User = Depends(get_current_user)):
    return ok({"balance": round(float(u.balance), 2), "local_balance": round(float(u.local_balance), 2)})


def _rec_dict(r: LocalConsumptionRecord) -> dict:
    return {"record_id": r.record_id, "record_type": r.record_type, "action_type": r.action_type,
            "amount": r.amount, "balance_after": r.balance_after, "status": r.status,
            "description": r.description, "ref_id": r.ref_id,
            "created_at": r.created_at.isoformat() if r.created_at else ""}


def _records_payload(u, db, page, page_size, request):
    rows = db.query(LocalConsumptionRecord).filter_by(user_id=u.id).order_by(LocalConsumptionRecord.id.desc()).all()
    from app.envelope import paginate
    return ok(paginate([_rec_dict(r) for r in rows], page, page_size,
                       request, "/api/account_info/consumption-records/"))


@router.get("/consumption-records/")
def consumption_records(request: Request, page: int = 1, page_size: int = 20,
                        u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _records_payload(u, db, page, page_size, request)


@router.get("/records")
@router.get("/records/")
def records_alias(request: Request, page: int = 1, page_size: int = 20,
                  u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _records_payload(u, db, page, page_size, request)
