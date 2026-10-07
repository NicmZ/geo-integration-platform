# -*- coding: utf-8 -*-
"""启动入口：python run.py  或  uvicorn app.main:app --host 0.0.0.0 --port 8001"""
import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
