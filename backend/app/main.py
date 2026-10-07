# -*- coding: utf-8 -*-
"""GEO Integration Platform 后端入口（FastAPI, 端口 8001）"""
import json
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.envelope import ok

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(title=settings.APP_NAME, version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    # 建表 + 种子数据
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from app.billing import ensure_default_prices
        ensure_default_prices(db)

        from app.engines.publisher import MEDIA_PLATFORMS
        from app.models import MediaPlatform, MediaChannel
        for i, (key, name, imgs, api_type) in enumerate(MEDIA_PLATFORMS):
            if not db.query(MediaPlatform).filter_by(key=key).first():
                db.add(MediaPlatform(key=key, name=name, supports_images=imgs, api_type=api_type, order=i))
        # 媒体库样例渠道（生产环境可批量导入 2 万+ 渠道）
        if db.query(MediaChannel).count() == 0:
            import random
            random.seed(42)
            cats = {"C": "综合门户", "V": "垂直媒体", "X": "新媒体", "W": "微信生态"}
            for n in range(200):
                plat = MEDIA_PLATFORMS[n % len(MEDIA_PLATFORMS)]
                cat = list(cats.keys())[n % 4]
                db.add(MediaChannel(
                    platform_key=plat[0], channel_name="%s-%s号渠道%03d" % (plat[1], cats[cat], n + 1),
                    category=cat, account="acc_%04d" % (n + 1),
                    followers=random.randint(1000, 500000), price=round(random.uniform(50, 5000), 1),
                    channel_url="https://%s.example-media.cn/%04d" % (plat[0], n + 1)))
        db.commit()

        from app.scheduler.handlers import register_all
        register_all()

        from app.scheduler.core import start_worker
        start_worker(app)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}


@app.get("/api/health")
def api_health():
    return {"status": "ok"}


@app.middleware("http")
async def status_envelope_middleware(request, call_next):
    """将路由返回的 {"__status__": 402, "body": {...}} 结构转换为真正的 HTTP 状态码响应"""
    response = await call_next(request)
    ctype = response.headers.get("content-type", "")
    if response.status_code == 200 and ctype.startswith("application/json"):
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        try:
            data = json.loads(body)
        except Exception:
            data = None
        if isinstance(data, dict) and "__status__" in data:
            return JSONResponse(status_code=int(data["__status__"]), content=data["body"])
        from starlette.responses import Response as _Resp
        return _Resp(content=body, status_code=200, media_type="application/json")
    return response


# ---------------- 路由挂载 ----------------

from app.routers import (  # noqa: E402
    users, keywords, results, content, account_info, payment, feedback, celery_compat, extensions,
)

for r in (users.router, keywords.router, results.router, content.router,
          account_info.router, payment.router, feedback.router, celery_compat.router, extensions.router):
    app.include_router(r)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logging.getLogger("app").exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"code": 1, "msg": "服务器内部错误", "data": None})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
