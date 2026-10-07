# -*- coding: utf-8 -*-
"""csg/v1 任务处理器注册：keyword_check / compliance_check / content_generate / kb_build / publish_dispatch"""
import json
import logging

from app.database import SessionLocal
from app.models import (
    Brand, CheckTask, CheckResult, Keyword, AiSearchResult, ComplianceReport,
    ComplianceFinding, Content, KnowledgeBase, KbVersion, KbTask, PublishTask, User,
)
from app.engines.geo_eval import check_keyword_once
from app.engines.compliance import check_compliance
from app.engines.content_gen import generate_article, keyword_density
from app.engines.publisher import publish_one

log = logging.getLogger("handlers")


def _handle_keyword_check(payload, progress_cb, ctx):
    """payload: {check_id} — 逐引擎检测并写结果"""
    db = SessionLocal()
    try:
        check = db.query(CheckTask).filter_by(id=payload["check_id"]).first()
        if not check:
            raise RuntimeError("check task not found")
        kw = db.query(Keyword).filter_by(id=check.keyword_id).first()
        brand = db.query(Brand).filter_by(id=kw.brand_id).first() if kw and kw.brand_id else None
        brand_name = brand.name if brand else ""
        engines = json.loads(check.engines or "[]")
        kw.status = "checking"
        db.commit()

        scores = []
        for i, eng in enumerate(engines):
            r = check_keyword_once(eng, kw.keyword, brand_name)
            db.add(CheckResult(
                task_id=check.id, keyword_id=kw.id, engine=eng, cited=r["cited"], rank=r["rank"],
                mention_rate=r["mention_rate"], sentiment=r["sentiment"], geo_score=r["geo_score"],
                answer=r["answer"], sources=json.dumps(r["sources"], ensure_ascii=False),
            ))
            db.add(AiSearchResult(
                user_id=check.user_id, keyword_id=kw.id, engine=eng, question=r["question"],
                answer=r["answer"], sources=json.dumps(r["sources"], ensure_ascii=False),
                rank=r["rank"], cited=r["cited"],
            ))
            scores.append(r["geo_score"])
            kw.geo_score = round(sum(scores) / len(scores), 1)
            db.commit()
            progress_cb(int((i + 1) / len(engines) * 100))

        kw.status = "checked"
        kw.last_check_id = check.id
        check.status = "SUCCESS"
        check.progress = 100
        check.finished_at = __import__("datetime").datetime.utcnow()
        db.commit()
        return {
            "keyword": kw.keyword, "engines": engines, "geo_score": kw.geo_score,
            "engine_scores": dict(zip(engines, scores)),
        }
    finally:
        db.close()


def _handle_compliance_check(payload, progress_cb, ctx):
    """payload: {report_id} — 对内容或检测结果做合规分析"""
    db = SessionLocal()
    try:
        report = db.query(ComplianceReport).filter_by(id=payload["report_id"]).first()
        if not report:
            raise RuntimeError("compliance report not found")
        text = ""
        if report.content_id:
            c = db.query(Content).filter_by(id=report.content_id).first()
            text = (c.title or "") + "\n" + (c.body or "") if c else ""
        if not text and report.keyword_id:
            rows = db.query(CheckResult).filter_by(keyword_id=report.keyword_id).order_by(CheckResult.id.desc()).limit(5).all()
            text = "\n".join(r.answer for r in rows)
        if not text:
            text = payload.get("text", "")
        progress_cb(50)
        result = check_compliance(text)
        report.score = result["score"]
        report.risk_level = result["risk_level"]
        report.summary = result["summary"]
        for f in result["findings"]:
            db.add(ComplianceFinding(report_id=report.id, **f))
        db.commit()
        progress_cb(100)
        return {"report_id": report.id, "score": result["score"],
                "risk_level": result["risk_level"], "findings_count": len(result["findings"])}
    finally:
        db.close()


def _handle_content_generate(payload, progress_cb, ctx):
    """payload: {content_id} — 生成文章并回写"""
    db = SessionLocal()
    try:
        c = db.query(Content).filter_by(id=payload["content_id"]).first()
        if not c:
            raise RuntimeError("content not found")
        brand = db.query(Brand).filter_by(id=c.brand_id).first() if c.brand_id else None
        kb = None
        if brand:
            kb = db.query(KnowledgeBase).filter_by(brand_id=brand.id, status="published").first()
        progress_cb(20)
        keywords = json.loads(c.keywords or "[]")
        result = generate_article(
            engine_key=c.engine_key, title=c.title, keywords=keywords, summary=c.summary,
            requirements=c.special_requirements, brand=brand.name if brand else "",
            kb_content=kb.content if kb else "", length=c.length,
        )
        progress_cb(80)
        c.body = result["body"]
        c.status = "ready"
        c.updated_at = __import__("datetime").datetime.utcnow()
        db.commit()
        return {"content_id": c.id, "length": len(result["body"]),
                "keyword_density": keyword_density(result["body"], keywords), "mock": result.get("mock", False)}
    finally:
        db.close()


def _handle_kb_build(payload, progress_cb, ctx):
    """payload: {kb_task_id} — 汇总品牌资料/文档/默认知识生成知识库"""
    import datetime as dt
    db = SessionLocal()
    try:
        task = db.query(KbTask).filter_by(id=payload["kb_task_id"]).first()
        if not task:
            raise RuntimeError("kb task not found")
        brand = db.query(Brand).filter_by(id=task.brand_id).first()
        progress_cb(30)
        parts = []
        if brand:
            parts.append("品牌名称：%s\n品牌类型：%s\n品牌介绍：%s" % (brand.name, brand.brand_type, brand.description or "（待补充）"))
        if brand and brand.documents:
            for doc in brand.documents:
                parts.append("【资料：%s】%s" % (doc.filename, (doc.content or "")[:600]))
        progress_cb(60)
        from app.routers.account_info import DEFAULT_KNOWLEDGE_TEMPLATE
        parts.append(DEFAULT_KNOWLEDGE_TEMPLATE.format(brand_name=brand.name if brand else "品牌"))
        content = "\n\n".join(parts)
        kb = db.query(KnowledgeBase).filter_by(brand_id=task.brand_id, user_id=task.user_id).first()
        if kb:
            kb.version += 1
            kb.content = content
            kb.status = "published"
            kb.published_at = dt.datetime.utcnow()
        else:
            kb = KnowledgeBase(user_id=task.user_id, brand_id=task.brand_id, title="%s 品牌知识库" % (brand.name if brand else ""),
                               content=content, status="published", published_at=dt.datetime.utcnow())
            db.add(kb)
            db.flush()
        db.add(KbVersion(kb_id=kb.id, version_no=kb.version, content=content))
        task.status = "SUCCESS"
        task.progress = 100
        task.finished_at = dt.datetime.utcnow()
        db.commit()
        return {"kb_id": kb.id, "version": kb.version, "content_length": len(content)}
    finally:
        db.close()


def _handle_publish_dispatch(payload, progress_cb, ctx):
    """payload: {publish_task_ids: [...]} — 逐平台发布"""
    db = SessionLocal()
    try:
        ids = payload.get("publish_task_ids", [])
        done = 0
        outcomes = {}
        for pid in ids:
            pt = db.query(PublishTask).filter_by(id=pid).first()
            if not pt or pt.status == "cancelled":
                done += 1
                continue
            pt.status = "publishing"
            db.commit()
            c = db.query(Content).filter_by(id=pt.content_id).first()
            acc_name = ""
            pt2 = publish_one(pt.platform_key, c.title if c else "", c.body if c else "", c.cover_url if c else "")
            if pt2["success"]:
                pt.status = "success"
                pt.publish_url = pt2.get("url", "")
                outcomes[pid] = {"status": "success", "url": pt.publish_url}
            else:
                pt.status = "failed"
                pt.error = pt2.get("error", "publish failed")
                outcomes[pid] = {"status": "failed", "error": pt.error}
            pt.finished_at = __import__("datetime").datetime.utcnow()
            db.commit()
            done += 1
            progress_cb(int(done / max(1, len(ids)) * 100))
        return {"outcomes": outcomes}
    finally:
        db.close()


def register_all():
    from app.scheduler import core
    core.register_handler("keyword_check", _handle_keyword_check)
    core.register_handler("compliance_check", _handle_compliance_check)
    core.register_handler("content_generate", _handle_content_generate)
    core.register_handler("kb_build", _handle_kb_build)
    core.register_handler("publish_dispatch", _handle_publish_dispatch)
