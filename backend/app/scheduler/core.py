# -*- coding: utf-8 -*-
"""CPU 算力调度器核心（csg/v1 协议，见 GEO_PROTOCOL §7）

- 队列：Redis ZSET（分数 = priority*1e10 + ts，小者先出）；无 Redis 时降级 DB 轮询
- 状态机：PENDING → STARTED → PROGRESS → SUCCESS | FAILURE（与 Celery 查询协议兼容）
- 执行器：local（进程内线程池）/ slurm（sbatch 提交计算节点）
- 公平调度：单租户并发上限 TENANT_MAX_CONCURRENT（DRF 防饿死）
- 计量：任务结束写 task_usage（cpu_seconds）
"""
import json
import logging
import socket
import threading
import time
import uuid
from datetime import datetime

from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.models import SchedulerTask, TaskUsage, ComputeNode

log = logging.getLogger("scheduler")

# 状态常量（Celery 兼容）
PENDING, STARTED, PROGRESS, SUCCESS, FAILURE = "PENDING", "STARTED", "PROGRESS", "SUCCESS", "FAILURE"

_handlers = {}          # task_type -> callable(payload, progress_cb, ctx) -> dict
_worker_started = False
_pool = None            # ThreadPoolExecutor
_redis = None


def register_handler(task_type: str, fn):
    _handlers[task_type] = fn


# ---------------- 队列后端 ----------------

def _get_redis():
    global _redis
    if _redis is None and settings.REDIS_URL:
        import redis
        _redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


_QUEUE_KEY = "csg:v1:queue"


def _zscore(priority: int, ts: float) -> float:
    return priority * 1e10 + ts


def enqueue(db, task_type: str, payload: dict, tenant: str = "", priority: int = 5,
            cpu_cores: int = 1, timeout_s: int = 600, max_retry: int = 2) -> str:
    """产出 csg/v1 任务信封并持久化；返回 task_id"""
    task_id = str(uuid.uuid4())
    task = SchedulerTask(
        id=task_id, task_type=task_type, status=PENDING, priority=priority,
        cpu_cores=cpu_cores, timeout_s=timeout_s, max_retry=max_retry,
        payload=json.dumps(payload or {}), tenant=str(tenant),
        executor="slurm" if settings.EXECUTOR == "slurm" else "local",
    )
    db.add(task)
    db.commit()
    r = _get_redis()
    if r:
        try:
            r.zadd(_QUEUE_KEY, {task_id: _zscore(priority, time.time())})
        except Exception as e:  # Redis 不可用自动降级 DB
            log.warning("redis zadd failed, fallback to db queue: %s", e)
    return task_id


def _pick_from_redis() -> str:
    r = _get_redis()
    if not r:
        return ""
    try:
        items = r.zrange(_QUEUE_KEY, 0, 0)
        if not items:
            return ""
        task_id = items[0]
        if r.zrem(_QUEUE_KEY, task_id):
            return task_id
    except Exception as e:
        log.warning("redis pick failed: %s", e)
    return ""


def _pick_from_db(db) -> str:
    row = db.execute(text(
        "SELECT id FROM scheduler_tasks WHERE status = 'PENDING' "
        "ORDER BY priority ASC, created_at ASC LIMIT 20"
    )).fetchall()
    if not row:
        return ""
    # 公平调度：按租户在途并发数升序 + 优先级排序选取
    candidates = [r[0] for r in row]
    best_id, best_key = "", None
    for tid in candidates:
        t = db.query(SchedulerTask).filter_by(id=tid).first()
        if not t:
            continue
        running = db.query(SchedulerTask).filter(
            SchedulerTask.tenant == t.tenant,
            SchedulerTask.status.in_([STARTED, PROGRESS]),
        ).count()
        key = (running, t.priority, t.created_at)
        if best_key is None or key < best_key:
            best_key, best_id = key, tid
    return best_id


def _claim(db, task_id: str):
    """原子抢占：PENDING → STARTED"""
    res = db.execute(text(
        "UPDATE scheduler_tasks SET status='STARTED', started_at=:now, attempts=attempts+1 "
        "WHERE id=:id AND status='PENDING'"),
        {"now": datetime.utcnow(), "id": task_id},
    )
    db.commit()
    return res.rowcount == 1


def _finish(db, task_id: str, status: str, result: dict = None, error: str = "",
            progress: int = 100, cpu_seconds: float = 0.0, queued_s: float = 0.0, cores: int = 1):
    t = db.query(SchedulerTask).filter_by(id=task_id).first()
    if not t:
        return
    t.status = status
    t.result = json.dumps(result or {}, ensure_ascii=False)
    t.error = error
    t.progress = progress
    t.finished_at = datetime.utcnow()
    db.add(TaskUsage(
        task_id=task_id, tenant=t.tenant, task_type=t.task_type, cores=cores,
        cpu_seconds=round(cpu_seconds, 3), queued_s=round(queued_s, 3),
        run_s=round(cpu_seconds, 3), finished_at=datetime.utcnow(),
    ))
    db.commit()


def _retry_or_fail(db, task_id: str, error: str):
    t = db.query(SchedulerTask).filter_by(id=task_id).first()
    if not t:
        return
    if t.attempts < t.max_retry:
        t.status = PENDING
        t.error = error
        t.progress = 0
        db.commit()
        r = _get_redis()
        if r:
            try:
                r.zadd(_QUEUE_KEY, {task_id: _zscore(t.priority, time.time())})
            except Exception:
                pass
        log.warning("task %s retry %d/%d: %s", task_id, t.attempts, t.max_retry, error)
    else:
        _finish(db, task_id, FAILURE, {}, error, progress=100)


# ---------------- 执行器 ----------------

def _run_local(task_id: str):
    """local 执行器：线程池内直接运行 handler"""
    db = SessionLocal()
    t = db.query(SchedulerTask).filter_by(id=task_id).first()
    if not t:
        return
    queued_s = (datetime.utcnow() - t.created_at).total_seconds() if t.created_at else 0.0
    handler = _handlers.get(t.task_type)
    payload = json.loads(t.payload or "{}")
    cores = t.cpu_cores or 1

    def progress_cb(pct: int, message: str = ""):
        s = SessionLocal()
        try:
            row = s.query(SchedulerTask).filter_by(id=task_id).first()
            if row:
                row.status = PROGRESS
                row.progress = max(0, min(100, int(pct)))
                s.commit()
        finally:
            s.close()

    t0 = time.time()
    try:
        result = handler(payload, progress_cb, {"task_id": task_id, "tenant": t.tenant}) if handler else {}
        cpu_seconds = time.time() - t0
        s = SessionLocal()
        try:
            _finish(s, task_id, SUCCESS, result, progress=100,
                    cpu_seconds=cpu_seconds, queued_s=queued_s, cores=cores)
        finally:
            s.close()
    except Exception as e:
        log.exception("task %s failed", task_id)
        s = SessionLocal()
        try:
            s2 = s.query(SchedulerTask).filter_by(id=task_id).first()
            if s2 and s2.attempts < s2.max_retry:
                _retry_or_fail(s, task_id, str(e))
            else:
                _finish(s, task_id, FAILURE, {}, error=str(e), progress=100,
                        cpu_seconds=time.time() - t0, queued_s=queued_s, cores=cores)
        finally:
            s.close()
    finally:
        db.close()


def _submit_slurm(task_id: str):
    """slurm 执行器：sbatch 提交单 CPU 作业，计算节点运行 slurm_worker 回写状态"""
    import os
    import subprocess
    db = SessionLocal()
    t = db.query(SchedulerTask).filter_by(id=task_id).first()
    db.close()
    if not t:
        return
    os.makedirs(settings.SLURM_WORKDIR, exist_ok=True)
    py = settings.SLURM_PYTHON
    script = f"""#!/bin/bash
#SBATCH --job-name=geo_{t.task_type}
#SBATCH --partition={settings.SLURM_PARTITION}
#SBATCH --cpus-per-task={t.cpu_cores}
#SBATCH --time={max(1, t.timeout_s // 60)}
{("#SBATCH --account=" + settings.SLURM_ACCOUNT) if settings.SLURM_ACCOUNT else ""}
cd {os.getcwd()}
{py} -m app.scheduler.slurm_worker {task_id}
"""
    path = os.path.join(settings.SLURM_WORKDIR, f"{task_id}.sbatch")
    with open(path, "w", encoding="utf-8") as f:
        f.write(script)
    try:
        out = subprocess.check_output(["sbatch", path], stderr=subprocess.STDOUT).decode()
        job_id = out.strip().split()[-1]
        s = SessionLocal()
        try:
            t2 = s.query(SchedulerTask).filter_by(id=task_id).first()
            t2.slurm_job_id = job_id
            s.commit()
        finally:
            s.close()
    except Exception as e:
        s = SessionLocal()
        try:
            _retry_or_fail(s, task_id, "sbatch submit failed: %s" % e)
        finally:
            s.close()


def _worker_loop():
    while True:
        try:
            db = SessionLocal()
            try:
                task_id = _pick_from_redis()
                if not task_id:
                    task_id = _pick_from_db(db)
                if not task_id:
                    continue
                t = db.query(SchedulerTask).filter_by(id=task_id).first()
                if not t or t.status != PENDING:
                    continue
                # 公平调度：租户并发上限
                running = db.query(SchedulerTask).filter(
                    SchedulerTask.tenant == t.tenant,
                    SchedulerTask.status.in_([STARTED, PROGRESS]),
                ).count()
                if running >= settings.TENANT_MAX_CONCURRENT:
                    time.sleep(0.5)
                    continue
                if not _claim(db, task_id):
                    continue
                if t.executor == "slurm":
                    _submit_slurm(task_id)   # 异步：由 slurm_worker 回写
                else:
                    _pool.submit(_run_local, task_id)
            finally:
                db.close()
        except Exception:
            log.exception("worker loop error")
        time.sleep(0.3)


def start_worker(app=None):
    """应用启动时调用：启动本地线程池 worker + 注册本机节点"""
    global _worker_started, _pool
    if _worker_started:
        return
    _worker_started = True
    import concurrent.futures
    _pool = concurrent.futures.ThreadPoolExecutor(max_workers=settings.CPU_CONCURRENCY)

    db = SessionLocal()
    try:
        if not db.query(ComputeNode).filter_by(hostname=socket.gethostname()).first():
            db.add(ComputeNode(hostname=socket.gethostname(), partition="local", state="running",
                               cores_total=settings.CPU_CONCURRENCY, cores_used=0, mem_gb=8))
        db.commit()
    finally:
        db.close()

    threading.Thread(target=_worker_loop, daemon=True, name="csg-scheduler").start()
    log.info("csg/v1 scheduler started (executor=%s, concurrency=%d)", settings.EXECUTOR, settings.CPU_CONCURRENCY)


def get_status(db, task_id: str):
    """Celery 兼容任务状态查询"""
    t = db.query(SchedulerTask).filter_by(id=task_id).first()
    if not t:
        return None
    try:
        result = json.loads(t.result or "{}")
    except Exception:
        result = {}
    return {"task_id": t.id, "status": t.status, "progress": t.progress, "result": result}
