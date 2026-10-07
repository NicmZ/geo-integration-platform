# -*- coding: utf-8 -*-
"""关键词 / GEO 评估路由：/api/keywords/（协议 §6.2）"""
import csv
import io
import json
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.billing import charge, get_price
from app.database import get_db
from app.envelope import ok, paginate
from app.models import (
    Brand, CheckResult, CheckTask, Keyword, KeywordTag, KeywordTagMap, ComplianceReport,
    ComplianceFinding, User,
)
from app.routers.deps import get_current_user, submit_task
from app.engines.ai_platforms import PLATFORMS

router = APIRouter(prefix="/api/keywords", tags=["keywords"])

DEFAULT_ENGINES = ["deepseek", "doubao", "ernie", "kimi", "qwen", "hunyuan", "metaso"]


def _kw_dict(k: Keyword) -> dict:
    return {
        "id": k.id, "keyword": k.keyword, "brand_id": k.brand_id, "category": k.category,
        "priority": k.priority, "status": k.status, "geo_score": k.geo_score,
        "last_check_id": k.last_check_id, "created_at": k.created_at.isoformat() if k.created_at else "",
    }


@router.get("/keyword-library/")
def keyword_library(request: Request, page: int = 1, page_size: int = 20, brand_id: int = None,
                    search: str = "", status: str = "", tag_id: int = None,
                    u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Keyword).filter_by(user_id=u.id)
    if brand_id:
        q = q.filter(Keyword.brand_id == brand_id)
    if search:
        q = q.filter(Keyword.keyword.like("%" + search + "%"))
    if status:
        q = q.filter(Keyword.status == status)
    if tag_id:
        ids = [m.keyword_id for m in db.query(KeywordTagMap).filter_by(tag_id=tag_id).all()]
        q = q.filter(Keyword.id.in_(ids or [0]))
    items = q.order_by(Keyword.id.desc()).all()
    data = paginate([_kw_dict(k) for k in items], page, page_size, request, "/api/keywords/keyword-library/")
    return ok(data)


@router.get("/tags/")
def list_tags(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tags = db.query(KeywordTag).filter_by(user_id=u.id).all()
    return ok([{"id": t.id, "name": t.name, "color": t.color, "keyword_count":
                db.query(KeywordTagMap).filter_by(tag_id=t.id).count()} for t in tags])


@router.post("/tags/")
def create_tag(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = body or {}
    name = (body.get("name") or "").strip()
    if not name:
        return {"code": 1, "msg": "标签名不能为空", "data": None}
    if db.query(KeywordTag).filter_by(user_id=u.id, name=name).first():
        return {"code": 1, "msg": "标签已存在", "data": None}
    t = KeywordTag(user_id=u.id, name=name, color=body.get("color", "#409EFF"))
    db.add(t)
    db.commit()
    return ok({"id": t.id, "name": t.name, "color": t.color})


@router.delete("/tags/{tag_id}/")
def delete_tag(tag_id: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(KeywordTagMap).filter_by(tag_id=tag_id).delete()
    db.query(KeywordTag).filter_by(id=tag_id, user_id=u.id).delete()
    db.commit()
    return ok({"deleted": True})


@router.post("/bulk-import/")
def bulk_import(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """批量导入：{keywords: ["词1", ...] 或 "词1\n词2", brand_id?, category?, tags?[]}"""
    body = body or {}
    raw = body.get("keywords") or []
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.replace("，", "\n").replace(",", "\n").splitlines() if x.strip()]
    brand_id = body.get("brand_id")
    if brand_id:
        brand = db.query(Brand).filter_by(id=brand_id, user_id=u.id).first()
        if not brand:
            return {"code": 1, "msg": "品牌不存在", "data": None}
    created, skipped = [], 0
    for word in raw[:500]:
        word = str(word).strip()
        if not word or db.query(Keyword).filter_by(user_id=u.id, keyword=word).first():
            skipped += 1
            continue
        k = Keyword(user_id=u.id, keyword=word, brand_id=brand_id or None,
                    category=body.get("category", ""))
        db.add(k)
        db.flush()
        for tag_id in body.get("tags") or []:
            db.add(KeywordTagMap(keyword_id=k.id, tag_id=tag_id))
        created.append(_kw_dict(k))
    db.commit()
    return ok({"created": len(created), "skipped": skipped, "keywords": created})


@router.patch("/keywords/{kid}/")
def update_keyword(kid: int, body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    k = db.query(Keyword).filter_by(id=kid, user_id=u.id).first()
    if not k:
        return {"code": 1, "msg": "关键词不存在", "data": None}
    body = body or {}
    for f in ("keyword", "category", "priority", "brand_id"):
        if f in body:
            setattr(k, f, body[f])
    if "tags" in body:
        db.query(KeywordTagMap).filter_by(keyword_id=k.id).delete()
        for tag_id in body["tags"] or []:
            db.add(KeywordTagMap(keyword_id=k.id, tag_id=tag_id))
    db.commit()
    return ok(_kw_dict(k))


@router.delete("/keywords/{kid}/")
def delete_keyword(kid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Keyword).filter_by(id=kid, user_id=u.id).delete()
    db.commit()
    return ok({"deleted": True})


def _new_check(kw: Keyword, u: User, engines: list, db: Session, batch_no: str = "") -> CheckTask:
    check = CheckTask(user_id=u.id, keyword_id=kw.id, batch_no=batch_no,
                      engines=json.dumps(engines), status="PENDING")
    db.add(check)
    db.flush()
    task_id = submit_task(db, "keyword_check", {"check_id": check.id}, tenant=str(u.id), cores=1)
    check.scheduler_task_id = task_id
    kw.status = "checking"
    db.commit()
    return check


def _gate_balance(u: User, db: Session, action_type: str) -> str:
    """余额不足以支付单价时拦截（任务完成时扣费）"""
    price = get_price(db, action_type)
    if price > 0 and u.balance < price:
        return "余额不足（单次 %g 元），请先充值" % price
    return ""


@router.post("/keywords/{kid}/check/")
def check_keyword(kid: int, body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    k = db.query(Keyword).filter_by(id=kid, user_id=u.id).first()
    if not k:
        return {"code": 1, "msg": "关键词不存在", "data": None}
    err = _gate_balance(u, db, "KEYWORD_CHECK")
    if err:
        return {"__status__": 402, "body": {"code": 402, "msg": err, "data": None}}
    engines = (body or {}).get("engines") or DEFAULT_ENGINES
    check = _new_check(k, u, engines, db)
    return ok({"check_id": check.id, "task_id": check.scheduler_task_id, "status": "PENDING"})


@router.post("/keywords/{kid}/recheck/")
def recheck_keyword(kid: int, body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return check_keyword(kid, body, u, db)


@router.get("/keywords/{kid}/checks/")
def keyword_checks(kid: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(CheckTask).filter_by(keyword_id=kid, user_id=u.id).order_by(CheckTask.id.desc()).limit(50).all()
    return ok([{"check_id": r.id, "status": r.status, "progress": r.progress,
                "created_at": r.created_at.isoformat(), "engines": json.loads(r.engines or "[]")} for r in rows])


@router.post("/checks/")
def batch_checks(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """批量提交：{keywords: [id...], engines: []}"""
    body = body or {}
    ids = body.get("keywords") or []
    engines = body.get("engines") or DEFAULT_ENGINES
    err = _gate_balance(u, db, "KEYWORD_CHECK")
    if err:
        return {"__status__": 402, "body": {"code": 402, "msg": err, "data": None}}
    batch_no = uuid.uuid4().hex[:12]
    tasks = []
    for kid in ids[:100]:
        k = db.query(Keyword).filter_by(id=kid, user_id=u.id).first()
        if not k:
            continue
        check = _new_check(k, u, engines, db, batch_no)
        tasks.append({"check_id": check.id, "task_id": check.scheduler_task_id, "keyword": k.keyword})
    return ok({"batch_no": batch_no, "count": len(tasks), "tasks": tasks})


@router.get("/checks/{check_id}/status/")
def check_status(check_id: str, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.query(CheckTask).filter_by(id=check_id, user_id=u.id).first()
    if not r:
        return {"code": 1, "msg": "任务不存在", "data": None}
    return ok({"check_id": r.id, "status": r.status, "progress": r.progress})


@router.get("/checks/{check_id}/")
def check_detail(check_id: str, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.query(CheckTask).filter_by(id=check_id, user_id=u.id).first()
    if not r:
        return {"code": 1, "msg": "任务不存在", "data": None}
    kw = db.query(Keyword).filter_by(id=r.keyword_id).first()
    results = db.query(CheckResult).filter_by(task_id=r.id).all()
    return ok({
        "check_id": r.id, "status": r.status, "progress": r.progress,
        "keyword": kw.keyword if kw else "", "geo_score": kw.geo_score if kw else 0,
        "results": [{
            "engine": x.engine, "cited": x.cited, "rank": x.rank, "mention_rate": x.mention_rate,
            "sentiment": x.sentiment, "geo_score": x.geo_score, "answer": x.answer,
            "sources": json.loads(x.sources or "[]"), "checked_at": x.checked_at.isoformat(),
        } for x in results],
    })


def _dash_stats(u, db):
    total_kw = db.query(Keyword).filter_by(user_id=u.id).count()
    checked_kw = db.query(Keyword).filter_by(user_id=u.id, status="checked").count()
    avg = db.query(func.avg(Keyword.geo_score)).filter_by(user_id=u.id).scalar() or 0
    rows = db.query(CheckResult.engine, CheckResult.cited).join(CheckTask).filter(
        CheckTask.user_id == u.id).all()
    total_results = len(rows)
    cited = sum(1 for _, c in rows if c)
    agg = {}
    for e, c in rows:
        n, k = agg.get(e, (0, 0))
        agg[e] = (n + 1, k + (1 if c else 0))
    engines = [{"engine": e, "name": PLATFORMS.get(e, (e,))[0], "checks": n,
                "cite_rate": round(k / n * 100, 1) if n else 0} for e, (n, k) in agg.items()]
    return {
        "total_keywords": total_kw, "checked_keywords": checked_kw,
        "avg_geo_score": round(float(avg), 1),
        "cite_rate": round(cited / total_results * 100, 1) if total_results else 0,
        "engines": engines,
    }


@router.get("/dashboard/")
def dashboard(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(_dash_stats(u, db))


@router.get("/dashboard/trend/")
def dashboard_trend(request: Request, days_range: str = Query("7days", alias="range"),
                    u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    days = 30 if days_range == "30days" else 7
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.query(CheckResult).join(CheckTask).filter(
        CheckTask.user_id == u.id, CheckResult.checked_at >= since).all()
    buckets = {}
    for r in rows:
        d = r.checked_at.date().isoformat()
        b = buckets.setdefault(d, {"date": d, "checks": 0, "cited": 0, "score_sum": 0.0})
        b["checks"] += 1
        b["cited"] += 1 if r.cited else 0
        b["score_sum"] += r.geo_score
    trend = []
    for i in range(days, -1, -1):
        d = (datetime.utcnow() - timedelta(days=i)).date().isoformat()
        b = buckets.get(d, {"date": d, "checks": 0, "cited": 0, "score_sum": 0.0})
        trend.append({"date": d, "checks": b["checks"], "cited": b["cited"],
                      "avg_score": round(b["score_sum"] / b["checks"], 1) if b["checks"] else 0})
    return ok(trend)


@router.get("/dashboard/recent/")
def dashboard_recent(request: Request, limit: int = 10,
                     u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(CheckTask).filter_by(user_id=u.id).order_by(CheckTask.id.desc()).limit(limit).all()
    out = []
    for r in rows:
        kw = db.query(Keyword).filter_by(id=r.keyword_id).first()
        out.append({"check_id": r.id, "keyword": kw.keyword if kw else "", "status": r.status,
                    "geo_score": kw.geo_score if kw else 0, "created_at": r.created_at.isoformat()})
    return ok(out)


@router.get("/dashboard/best-practices/")
def best_practices(limit: int = 10):
    """GEO 优化最佳实践（静态知识库）"""
    tips = [
        {"title": "结论先行", "detail": "将核心结论放在正文首段，AI 引擎优先引用开头内容。"},
        {"title": "补充权威来源", "detail": "引用 2-3 条带 URL 的权威来源可显著提升引用率。"},
        {"title": "使用结构化表述", "detail": "分点、编号、表格化内容更容易被生成式引擎摘录。"},
        {"title": "避免绝对化用语", "detail": "《广告法》禁用词会同时影响合规与平台分发。"},
        {"title": "品牌词+品类词组合", "detail": "同时覆盖「品牌名+品类」与「品类+场景」两类搜索意图。"},
        {"title": "保持内容更新频率", "detail": "近 3 个月有更新的内容在多数 AI 搜索中排序更靠前。"},
        {"title": "数据可验证", "detail": "「据统计」类断言必须给出处，否则降低 AI 信任度。"},
        {"title": "多平台一致性", "detail": "各发布平台的品牌描述保持一致，强化实体识别。"},
    ]
    return ok(tips[:limit])


@router.get("/keyword-center/")
def keyword_center(request: Request, page: int = 1, page_size: int = 20,
                   u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stats = _dash_stats(u, db)
    kws = db.query(Keyword).filter_by(user_id=u.id).order_by(Keyword.id.desc()).all()
    data = paginate([_kw_dict(k) for k in kws], page, page_size, request, "/api/keywords/keyword-center/")
    data["summary"] = stats
    return ok(data)


@router.post("/batch-operations/")
def batch_operations(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """批量操作：{action: check|delete|tag, keyword_ids:[], engines?, tag_id?}"""
    body = body or {}
    action = body.get("action", "")
    ids = body.get("keyword_ids") or []
    if action == "check":
        return batch_checks({"keywords": ids, "engines": body.get("engines")}, u, db)
    if action == "delete":
        n = db.query(Keyword).filter(Keyword.user_id == u.id, Keyword.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        return ok({"deleted": n})
    if action == "tag":
        for kid in ids:
            db.add(KeywordTagMap(keyword_id=kid, tag_id=body.get("tag_id")))
        db.commit()
        return ok({"tagged": len(ids)})
    return {"code": 1, "msg": "未知操作", "data": None}


@router.get("/export/")
def export(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Keyword).filter_by(user_id=u.id).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "keyword", "category", "status", "geo_score", "created_at"])
    for k in rows:
        w.writerow([k.id, k.keyword, k.category, k.status, k.geo_score,
                    k.created_at.isoformat() if k.created_at else ""])
    buf.seek(0)
    return StreamingResponse(iter(["\ufeff" + buf.read()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=keywords.csv"})


@router.post("/compliance/")
def compliance_check(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """发起合规检测：{keyword_id?, content_id?} → 报告（详情需解锁）"""
    body = body or {}
    report = ComplianceReport(user_id=u.id, keyword_id=body.get("keyword_id"),
                              content_id=body.get("content_id"))
    db.add(report)
    db.flush()
    task_id = submit_task(db, "compliance_check", {"report_id": report.id}, tenant=str(u.id))
    report.scheduler_task_id = task_id
    db.commit()
    return ok({"report_id": report.id, "task_id": task_id, "status": "PENDING"})


@router.get("/compliance/")
def compliance_list(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(ComplianceReport).filter_by(user_id=u.id).order_by(ComplianceReport.id.desc()).limit(100).all()
    return ok([{
        "id": r.id, "keyword_id": r.keyword_id, "content_id": r.content_id, "score": r.score,
        "risk_level": r.risk_level, "summary": r.summary, "locked": r.locked,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    } for r in rows])


@router.get("/compliance/{report_id}/")
def compliance_detail(report_id: int, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.query(ComplianceReport).filter_by(id=report_id, user_id=u.id).first()
    if not r:
        return {"code": 1, "msg": "报告不存在", "data": None}
    status = "SUCCESS" if (r.score or r.summary) else "PROGRESS"
    findings = db.query(ComplianceFinding).filter_by(report_id=r.id).all() if not r.locked else []
    return ok({
        "report_id": r.id, "score": r.score, "risk_level": r.risk_level, "summary": r.summary,
        "locked": r.locked, "status": status,
        "findings": [{"rule_code": f.rule_code, "category": f.category, "severity": f.severity,
                      "fragment": f.fragment, "suggestion": f.suggestion} for f in findings],
    })


@router.post("/unlock/")
def unlock(body: dict, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """解锁合规报告详情（计费 COMPLIANCE_UNLOCK）"""
    body = body or {}
    r = db.query(ComplianceReport).filter_by(id=body.get("report_id"), user_id=u.id).first()
    if not r:
        return {"code": 1, "msg": "报告不存在", "data": None}
    if not r.locked:
        return ok({"unlocked": True, "already": True})
    price = get_price(db, "COMPLIANCE_UNLOCK")
    balance_after = charge(db, u.id, "COMPLIANCE_UNLOCK", price,
                           description="合规报告解锁 #%d" % r.id, ref_id=str(r.id))
    if balance_after is None:
        return {"__status__": 402, "body": {"code": 402, "msg": "余额不足，请先充值", "data": None}}
    r.locked = False
    db.commit()
    findings = db.query(ComplianceFinding).filter_by(report_id=r.id).all()
    ok_data = {"unlocked": True, "cost": price, "balance_after": balance_after,
               "findings": [{"rule_code": f.rule_code, "category": f.category, "severity": f.severity,
                             "fragment": f.fragment, "suggestion": f.suggestion} for f in findings]}
    return ok(ok_data)
