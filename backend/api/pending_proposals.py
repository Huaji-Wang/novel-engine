"""待确认提案 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db.session import db_session
from backend.db.models import Novel
from backend.pending.service import (
    confirm_all_for_chapter,
    confirm_proposals,
    list_pending,
    reject_proposals,
)

router = APIRouter(prefix="/api/novels", tags=["pending"])


class PendingConfirmRequest(BaseModel):
    proposal_ids: list[int]


@router.get("/{novel_id}/pending")
def get_pending(novel_id: int, chapter_no: int | None = None):
    with db_session() as session:
        if not session.get(Novel, novel_id):
            raise HTTPException(404, "小说不存在")
    return {"items": list_pending(novel_id, chapter_no=chapter_no)}


@router.post("/{novel_id}/pending/confirm")
def confirm_pending(novel_id: int, payload: PendingConfirmRequest):
    with db_session() as session:
        if not session.get(Novel, novel_id):
            raise HTTPException(404, "小说不存在")
    return confirm_proposals(novel_id, payload.proposal_ids)


@router.post("/{novel_id}/pending/confirm-all/{chapter_no}")
def confirm_all_pending(novel_id: int, chapter_no: int):
    with db_session() as session:
        if not session.get(Novel, novel_id):
            raise HTTPException(404, "小说不存在")
    return confirm_all_for_chapter(novel_id, chapter_no)


@router.post("/{novel_id}/pending/reject")
def reject_pending(novel_id: int, payload: PendingConfirmRequest):
    with db_session() as session:
        if not session.get(Novel, novel_id):
            raise HTTPException(404, "小说不存在")
    n = reject_proposals(novel_id, payload.proposal_ids)
    return {"rejected": n}
