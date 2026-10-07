# -*- coding: utf-8 -*-
"""AI 引擎注册与报告路由：/api/result/ /api/report_info/（协议 §6.3）"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.billing import charge, get_price
from app.database import get_db
from app.envelope import ok
from app.models import AiSearchResult, Engine, Keyword, User
from app.routers.deps import get_current_user
from app.engines.ai_platforms import PLATFORMS

router = APIRouter(tags=["results"])


def _seed_engines(db: Session):
    for i, (key, (name, vendor, _p, model)) in enumerate(sorted(PLATFORMS.items())):
        if not db.query(Engine).filter_by(key=key).first():
            db.add(Engine(key=key, name=name, vendor=vendor, order=i, enabled=True,
                          config='{"model": "%s"}' % model))
    db.commit()


@router.get("/api/result/engines/")
def engines(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _seed_engines(db)
    rows = db.query(Engine).order_by(Engine.order).all()
    return ok([{"key": e.key, "name": e.name, "vendor": e.vendor, "enabled": e.enabled,
                "weight": e.weight} for e in rows])


@router.get("/api/result/engines/configs/")
def engine_configs(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _seed_engines(db)
    rows = db.query(Engine).order_by(Engine.order).all()
    return ok({e.key: {"model": e.config, "enabled": e.enabled} for e in rows})


@router.get("/api/result/engines/choices/")
def engine_choices():
    choices = [{"key": k, "name": v[0], "vendor": v[1]} for k, v in
               sorted(PLATFORMS.items(), key=lambda x: list(PLATFORMS).index(x[0]))]
    return ok(choices)


@router.get("/api/report_info/ai-search-results/")
def ai_search_results(keyword_id: int = None, engine: str = "", page: int = 1, page_size: int = 20,
                      u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(AiSearchResult).filter_by(user_id=u.id)
    if keyword_id:
        q = q.filter(AiSearchResult.keyword_id == keyword_id)
    if engine:
        q = q.filter(AiSearchResult.engine == engine)
    rows = q.order_by(AiSearchResult.id.desc()).limit(200).all()
    start = (page - 1) * page_size
    data = {
        "count": len(rows),
        "next": None, "previous": None,
        "results": [{
            "id": r.id, "keyword_id": r.keyword_id, "engine": r.engine, "question": r.question,
            "answer": r.answer, "sources": r.sources, "rank": r.rank, "cited": r.cited,
            "created_at": r.created_at.isoformat(),
        } for r in rows[start:start + page_size]],
    }
    return ok(data)


@router.post("/api/report_info/publish")
def report_publish(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """将报告/内容发布到 AI 报告中心（计费 CONTENT_PUBLISH）"""
    price = get_price(db, "CONTENT_PUBLISH", standard_cost=5.0)
    balance_after = charge(db, u.id, "CONTENT_PUBLISH", price,
                           description="报告发布", ref_id=str((body or {}).get("report_id", "")))
    if balance_after is None:
        return {"__status__": 402, "body": {"code": 402, "msg": "余额不足，请先充值", "data": None}}
    data = {"published": True, "cost": price, "balance_after": balance_after}
    return ok(data)
