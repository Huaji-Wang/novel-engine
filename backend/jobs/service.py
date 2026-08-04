"""jobs 表的读写：入队、领取、进度、checkpoint、恢复、取消。

所有函数都开短事务立刻提交，保证 worker 崩溃/进程重启后状态可从库中恢复。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.db.models import Job
from backend.db.session import db_session

ACTIVE_STATUSES = ("queued", "running", "cancelling")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dict(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "novel_id": job.novel_id,
        "kind": job.kind,
        "params": job.params or {},
        "status": job.status,
        "progress": job.progress or [],
        "checkpoint": job.checkpoint or {},
        "result": job.result or {},
        "error": job.error or "",
        "attempts": job.attempts or 0,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def enqueue_job(
    novel_id: int,
    kind: str,
    params: dict | None = None,
    checkpoint: dict | None = None,
) -> dict:
    """入队。同一本小说同时只允许一个活跃任务，避免状态互相踩踏。

    checkpoint 可携带入队时预组装的上下文（如写章 state），worker 直接续用。
    """
    with db_session() as session:
        active = session.query(Job).filter(
            Job.novel_id == novel_id,
            Job.status.in_(ACTIVE_STATUSES),
        ).first()
        if active:
            raise ValueError(
                f"该小说已有进行中的任务（#{active.id} {active.kind}），请等待完成或取消")
        job = Job(novel_id=novel_id, kind=kind, params=params or {},
                  checkpoint=checkpoint or {})
        session.add(job)
        session.flush()
        return _to_dict(job)


def get_job(job_id: int) -> dict | None:
    with db_session() as session:
        job = session.get(Job, job_id)
        return _to_dict(job) if job else None


def active_job_for_novel(novel_id: int) -> dict | None:
    with db_session() as session:
        job = session.query(Job).filter(
            Job.novel_id == novel_id,
            Job.status.in_(ACTIVE_STATUSES),
        ).order_by(Job.id.desc()).first()
        return _to_dict(job) if job else None


def list_jobs(novel_id: int, limit: int = 20) -> list[dict]:
    with db_session() as session:
        rows = session.query(Job).filter_by(novel_id=novel_id).order_by(
            Job.id.desc()).limit(limit).all()
        return [_to_dict(j) for j in rows]


def claim_next_job() -> dict | None:
    """领取最早的 queued 任务并标记 running（单 worker，无并发竞争）。"""
    with db_session() as session:
        job = session.query(Job).filter_by(status="queued").order_by(
            Job.id).first()
        if not job:
            return None
        job.status = "running"
        job.attempts = (job.attempts or 0) + 1
        job.started_at = job.started_at or _now()
        return _to_dict(job)


def append_progress(job_id: int, event: str, data: dict | None = None) -> None:
    with db_session() as session:
        job = session.get(Job, job_id)
        if not job:
            return
        entries = list(job.progress or [])
        entries.append({
            "event": event,
            "data": data or {},
            "ts": _now().isoformat(),
        })
        job.progress = entries


def save_checkpoint(job_id: int, checkpoint: dict) -> None:
    with db_session() as session:
        job = session.get(Job, job_id)
        if job:
            job.checkpoint = checkpoint


def job_status(job_id: int) -> str:
    with db_session() as session:
        job = session.get(Job, job_id)
        return job.status if job else "unknown"


def finish_job(job_id: int, result: dict | None = None) -> None:
    with db_session() as session:
        job = session.get(Job, job_id)
        if job:
            job.status = "succeeded"
            job.result = result or {}
            job.checkpoint = {}
            job.finished_at = _now()


def fail_job(job_id: int, error: str) -> None:
    """失败但保留 checkpoint：重试时从断点继续，不重复消耗 token。"""
    with db_session() as session:
        job = session.get(Job, job_id)
        if job:
            job.status = "failed"
            job.error = str(error)[:2000]
            job.finished_at = _now()


def mark_cancelled(job_id: int) -> None:
    with db_session() as session:
        job = session.get(Job, job_id)
        if job:
            job.status = "cancelled"
            job.finished_at = _now()


def request_cancel(job_id: int) -> bool:
    """协作式取消：queued 直接取消；running 置 cancelling，worker 在下个断点停。"""
    with db_session() as session:
        job = session.get(Job, job_id)
        if not job:
            return False
        if job.status == "queued":
            job.status = "cancelled"
            job.finished_at = _now()
            return True
        if job.status in ("running", "cancelling"):
            job.status = "cancelling"
            return True
        return False


def retry_job(job_id: int) -> dict | None:
    """failed/cancelled 任务重新入队；保留 checkpoint 从断点续跑。"""
    with db_session() as session:
        job = session.get(Job, job_id)
        if not job or job.status not in ("failed", "cancelled"):
            return None
        active = session.query(Job).filter(
            Job.novel_id == job.novel_id,
            Job.status.in_(ACTIVE_STATUSES),
        ).first()
        if active:
            raise ValueError(f"该小说已有进行中的任务（#{active.id}），请先等待完成")
        job.status = "queued"
        job.error = ""
        job.finished_at = None
        return _to_dict(job)


def recover_interrupted() -> int:
    """启动时把上次进程崩溃/重启遗留的 running 任务重新排队（checkpoint 不丢）。"""
    with db_session() as session:
        rows = session.query(Job).filter(
            Job.status.in_(("running", "cancelling"))).all()
        for job in rows:
            job.status = "queued"
            entries = list(job.progress or [])
            entries.append({
                "event": "log",
                "data": {"message": "服务重启，任务已从断点重新排队"},
                "ts": _now().isoformat(),
            })
            job.progress = entries
        return len(rows)
