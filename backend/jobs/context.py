"""任务执行上下文：handler 通过它上报进度、落 checkpoint、响应取消。"""

from __future__ import annotations

from dataclasses import dataclass

from backend.jobs import service


@dataclass
class JobContext:
    job_id: int

    def emit(self, event: str, data: dict | None = None) -> None:
        service.append_progress(self.job_id, event, data)

    def save_checkpoint(self, checkpoint: dict) -> None:
        service.save_checkpoint(self.job_id, checkpoint)

    def cancelled(self) -> bool:
        return service.job_status(self.job_id) == "cancelling"
