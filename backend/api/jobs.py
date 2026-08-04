"""后台任务 API：写章/定稿入队、进度轮询、取消与断点重试。

进度轮询协议（GET /api/jobs/{id}）返回 progress 列表，
每项 {event, data, ts}，event 与 SSE 版一致：steps / step_done / log / done / error。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.schemas import WriteChapterRequest
from backend.db.models import Chapter, Novel
from backend.db.session import db_session
from backend.jobs import service

router = APIRouter(prefix="/api", tags=["jobs"])


def _require_novel(novel_id: int) -> None:
    with db_session() as session:
        if not session.get(Novel, novel_id):
            raise HTTPException(404, "小说不存在")


@router.post("/novels/{novel_id}/chapters/{chapter_no}/write_job")
def enqueue_write_chapter(novel_id: int, chapter_no: int, payload: WriteChapterRequest):
    """写章任务入队：入队时即校验前置条件并冻结写作上下文。"""
    _require_novel(novel_id)
    from backend.services.write_chapter import prepare_write_state
    state = prepare_write_state(novel_id, chapter_no, payload.user_guidance)
    try:
        job = service.enqueue_job(
            novel_id, "write_chapter",
            params={
                "novel_id": novel_id,
                "chapter_no": chapter_no,
                "user_guidance": payload.user_guidance,
            },
            checkpoint={"phase": "retrieve_memory", "state": state},
        )
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"job_id": job["id"], "status": job["status"]}


@router.post("/novels/{novel_id}/chapters/{chapter_no}/finalize_job")
def enqueue_finalize_chapter(novel_id: int, chapter_no: int):
    """定稿任务入队。"""
    _require_novel(novel_id)
    with db_session() as session:
        chapter = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if not chapter or not chapter.content:
            raise HTTPException(400, "章节不存在或内容为空")
    try:
        job = service.enqueue_job(
            novel_id, "finalize_chapter",
            params={"novel_id": novel_id, "chapter_no": chapter_no},
        )
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"job_id": job["id"], "status": job["status"]}


@router.get("/jobs/{job_id}")
def get_job(job_id: int):
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    job.pop("checkpoint", None)  # 中间状态可能很大，轮询无需返回
    return job


@router.get("/novels/{novel_id}/jobs")
def list_novel_jobs(novel_id: int, limit: int = 20):
    _require_novel(novel_id)
    jobs = service.list_jobs(novel_id, limit=limit)
    for job in jobs:
        job.pop("checkpoint", None)
        job.pop("progress", None)
    return {"jobs": jobs}


@router.get("/novels/{novel_id}/jobs/active")
def active_novel_job(novel_id: int):
    _require_novel(novel_id)
    job = service.active_job_for_novel(novel_id)
    if job:
        job.pop("checkpoint", None)
    return {"job": job}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: int):
    if not service.request_cancel(job_id):
        raise HTTPException(400, "任务不存在或已结束")
    return {"ok": True}


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: int):
    """失败/取消的任务重新排队，从 checkpoint 断点继续。"""
    try:
        job = service.retry_job(job_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    if not job:
        raise HTTPException(400, "仅 failed/cancelled 任务可重试")
    return {"job_id": job["id"], "status": job["status"]}
