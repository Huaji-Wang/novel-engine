"""FastAPI 入口：API 路由 + 静态前端托管。"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api import generation, jobs, novels, pending_proposals, style_profiles
from backend.db.session import init_db
from backend.jobs.worker import start_worker, stop_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="多智能体小说生成引擎 (novel-engine-next)", version="0.2.0")
app.include_router(novels.router)
app.include_router(generation.router)
app.include_router(style_profiles.router)
app.include_router(pending_proposals.router)
app.include_router(jobs.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    # 恢复上次中断的任务并拉起后台 worker（写章/定稿走 jobs 队列）
    start_worker()


@app.on_event("shutdown")
def _shutdown() -> None:
    stop_worker()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
