"""单 worker 线程：轮询 jobs 表，逐个执行长流程任务。

- 崩溃/重启后由 recover_interrupted() 把 running 任务重新排队，
  handler 依据 checkpoint 跳过已完成步骤（token 不重复消耗）。
- 取消是协作式的：handler 在步骤边界检查 cancelling 状态。
"""

from __future__ import annotations

import logging
import threading

from backend.jobs import service
from backend.jobs.context import JobContext

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 1.5
_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _handlers():
    # 延迟导入：services 依赖 agents/LLM 客户端，避免启动时序问题。
    from backend.services import finalize_chapter, write_chapter
    return {
        "write_chapter": (write_chapter.run_write_job, write_chapter.CANCELLED),
        "finalize_chapter": (finalize_chapter.run_finalize_job,
                             finalize_chapter.CANCELLED),
    }


def _run_one(job: dict) -> None:
    handlers = _handlers()
    entry = handlers.get(job["kind"])
    ctx = JobContext(job["id"])
    if not entry:
        service.fail_job(job["id"], f"未知任务类型：{job['kind']}")
        return
    handler, cancelled_marker = entry
    try:
        result = handler(job, ctx)
        if result is cancelled_marker:
            service.mark_cancelled(job["id"])
            ctx.emit("log", {"message": "任务已按请求取消"})
        else:
            service.finish_job(job["id"], result if isinstance(result, dict) else {})
    except Exception as e:  # noqa: BLE001
        logger.exception("任务 #%s (%s) 执行失败", job["id"], job["kind"])
        ctx.emit("error", {"message": str(e)})
        service.fail_job(job["id"], str(e))


def _loop() -> None:
    logger.info("后台任务 worker 已启动")
    while not _stop_event.is_set():
        try:
            job = service.claim_next_job()
        except Exception:  # noqa: BLE001
            logger.exception("领取任务失败")
            job = None
        if job:
            logger.info("开始执行任务 #%s (%s)", job["id"], job["kind"])
            _run_one(job)
        else:
            _stop_event.wait(_POLL_INTERVAL)


def start_worker() -> None:
    """应用启动时调用：先恢复中断任务，再拉起 worker 线程（幂等）。"""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    recovered = service.recover_interrupted()
    if recovered:
        logger.info("已恢复 %s 个中断任务到队列", recovered)
    _stop_event.clear()
    _worker_thread = threading.Thread(
        target=_loop, name="job-worker", daemon=True)
    _worker_thread.start()


def stop_worker() -> None:
    _stop_event.set()
