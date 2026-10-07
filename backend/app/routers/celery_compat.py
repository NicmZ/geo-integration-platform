# -*- coding: utf-8 -*-
"""任务状态兼容层：/api/celery_tasks/task-status/{task_id}/（协议 §6.6）"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.envelope import ok
from app.routers.deps import get_current_user
from app.scheduler import core

router = APIRouter(prefix="/api/celery_tasks", tags=["celery-compat"])


@router.get("/task-status/{task_id}/")
def task_status(task_id: str, u=Depends(get_current_user), db: Session = Depends(get_db)):
    data = core.get_status(db, task_id)
    if data is None:
        return {"code": 1, "msg": "任务不存在", "data": None}
    return ok(data)
