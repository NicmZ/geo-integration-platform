# -*- coding: utf-8 -*-
"""Slurm 计算节点 worker：sbatch 作业内运行，直连数据库执行任务并回写状态。

超算用法：登录节点运行 API（EXECUTOR=slurm），本模块由 sbatch 脚本在每个任务作业中执行：
    python -m app.scheduler.slurm_worker <task_id>
"""
import json
import sys
import time


def main(task_id: str):
    from app.database import SessionLocal
    from app.models import SchedulerTask
    from app.scheduler import core

    db = SessionLocal()
    try:
        t = db.query(SchedulerTask).filter_by(id=task_id).first()
        if not t:
            print("task not found:", task_id)
            return
        payload = json.loads(t.payload or "{}")
    finally:
        db.close()

    handler = core._handlers.get(t.task_type)

    def progress_cb(pct, message=""):
        s = SessionLocal()
        try:
            row = s.query(SchedulerTask).filter_by(id=task_id).first()
            if row:
                row.status = core.PROGRESS
                row.progress = max(0, min(100, int(pct)))
                s.commit()
        finally:
            s.close()

    t0 = time.time()
    try:
        result = handler(payload, progress_cb, {"task_id": task_id, "tenant": t.tenant}) if handler else {}
        s = SessionLocal()
        try:
            core._finish(s, task_id, core.SUCCESS, result, progress=100,
                         cpu_seconds=time.time() - t0, cores=t.cpu_cores)
        finally:
            s.close()
    except Exception as e:
        s = SessionLocal()
        try:
            core._retry_or_fail(s, task_id, str(e))
        finally:
            s.close()
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m app.scheduler.slurm_worker <task_id>")
        sys.exit(1)
    main(sys.argv[1])
