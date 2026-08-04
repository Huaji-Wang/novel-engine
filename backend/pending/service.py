"""待确认提案：定稿提取 → 确认入账。"""

from __future__ import annotations

from typing import Any

from backend.config import pending_policy_config
from backend.db.models import (
    CastEntry,
    Character,
    Faction,
    FactionRelation,
    LoreEntry,
    PendingProposal,
)
from backend.db.session import db_session
from backend.pending.policy import (
    proposal_key,
    select_proposals,
    strip_proposal_meta,
)


def count_pending(novel_id: int) -> int:
    with db_session() as session:
        return session.query(PendingProposal).filter_by(
            novel_id=novel_id, status="pending",
        ).count()


def list_pending(novel_id: int, *, chapter_no: int | None = None) -> list[dict]:
    with db_session() as session:
        q = session.query(PendingProposal).filter_by(
            novel_id=novel_id, status="pending",
        )
        if chapter_no is not None:
            q = q.filter(PendingProposal.chapter_no == chapter_no)
        rows = q.order_by(PendingProposal.id).all()
        return [
            {
                "id": r.id,
                "novel_id": r.novel_id,
                "chapter_no": r.chapter_no,
                "kind": r.kind,
                "payload": r.payload or {},
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]


def add_proposals(
    novel_id: int,
    chapter_no: int,
    items: list[dict],
    *,
    chapter_text: str,
) -> dict[str, int]:
    """按证据、重要性、配额和去重策略写入 Pending。

    该函数只由定稿流程调用；它不会把候选直接写入正式事实表。
    """
    if not items:
        return {
            "input": 0, "added": 0, "invalid": 0, "duplicate": 0,
            "low_value": 0, "over_limit": 0,
        }
    policy = pending_policy_config()
    with db_session() as session:
        selected, stats = select_proposals(
            items,
            chapter_text=chapter_text,
            existing_keys=_existing_proposal_keys(session, novel_id),
            limits=policy["per_chapter"],
            min_importance=policy["min_importance"],
            require_evidence=bool(policy["require_evidence"]),
        )
        for item in selected:
            session.add(PendingProposal(
                novel_id=novel_id,
                chapter_no=chapter_no,
                kind=str(item.get("kind", "")),
                payload=item.get("payload") or {},
                status="pending",
            ))
        return stats


def confirm_proposals(novel_id: int, proposal_ids: list[int]) -> dict[str, int]:
    stats = {"confirmed": 0, "rejected": 0, "skipped": 0}
    with db_session() as session:
        for pid in proposal_ids:
            row = session.query(PendingProposal).filter_by(
                id=pid, novel_id=novel_id,
            ).first()
            if not row or row.status != "pending":
                stats["skipped"] += 1
                continue
            if _apply_proposal(session, row):
                row.status = "confirmed"
                stats["confirmed"] += 1
            else:
                row.status = "rejected"
                stats["rejected"] += 1
    return stats


def confirm_all_for_chapter(novel_id: int, chapter_no: int) -> dict[str, int]:
    pending = list_pending(novel_id, chapter_no=chapter_no)
    return confirm_proposals(novel_id, [p["id"] for p in pending])


def reject_proposals(novel_id: int, proposal_ids: list[int]) -> int:
    n = 0
    with db_session() as session:
        for pid in proposal_ids:
            row = session.query(PendingProposal).filter_by(
                id=pid, novel_id=novel_id, status="pending",
            ).first()
            if row:
                row.status = "rejected"
                n += 1
    return n


def _apply_proposal(session, row: PendingProposal) -> bool:
    kind = row.kind
    payload = row.payload or {}
    novel_id = row.novel_id
    chapter_no = row.chapter_no

    if kind == "character":
        name = str(payload.get("name", "")).strip()
        if not name:
            return False
        exists = session.query(Character).filter_by(
            novel_id=novel_id, name=name,
        ).first()
        if exists:
            return False
        data = strip_proposal_meta(payload.get("data") or {})
        session.add(Character(
            novel_id=novel_id, name=name,
            data=data,
            first_chapter=chapter_no, last_chapter=chapter_no,
            status="active",
        ))
        # 同名 cast 是角色的轻量阶段；升格核心角色后移除，避免两套上下文重复。
        session.query(CastEntry).filter_by(
            novel_id=novel_id, name=name,
        ).delete()
        return True

    if kind == "cast":
        name = str(payload.get("name", "")).strip()
        if not name:
            return False
        exists = session.query(CastEntry).filter_by(
            novel_id=novel_id, name=name,
        ).first()
        if exists:
            return False
        session.add(CastEntry(
            novel_id=novel_id, name=name,
            brief_role=str(payload.get("brief_role", ""))[:300],
            first_seen_chapter=chapter_no,
            last_seen_chapter=chapter_no,
            appearance_count=1,
            appearance_chapters=[chapter_no],
        ))
        return True

    if kind == "lore":
        name = str(payload.get("name", "")).strip()
        if not name:
            return False
        exists = session.query(LoreEntry).filter_by(
            novel_id=novel_id, name=name,
        ).first()
        if exists:
            return False
        session.add(LoreEntry(
            novel_id=novel_id, name=name,
            category=str(payload.get("category", "其他")),
            keywords=payload.get("keywords") or [],
            content=str(payload.get("content", "")),
            source_chapter=chapter_no,
            enabled=1,
        ))
        return True

    if kind == "faction":
        name = str(payload.get("name", "")).strip()
        if not name:
            return False
        exists = session.query(Faction).filter_by(
            novel_id=novel_id, name=name,
        ).first()
        if exists:
            return False
        data = strip_proposal_meta(payload)
        data.pop("name", None)
        session.add(Faction(
            novel_id=novel_id, name=name, data=data,
            first_chapter=chapter_no, last_chapter=chapter_no,
            status="active",
        ))
        return True

    if kind == "faction_relation":
        source = str(payload.get("source", "")).strip()
        target = str(payload.get("target", "")).strip()
        if not (source and target):
            return False
        data = strip_proposal_meta(payload)
        rel_type = str(data.pop("relation_type", ""))
        session.add(FactionRelation(
            novel_id=novel_id, source=source, target=target,
            relation_type=rel_type, data=data,
        ))
        return True

    return False


def _existing_proposal_keys(session, novel_id: int) -> set[str]:
    """正式库 + 尚未处理的提案共同参与去重。"""
    keys: set[str] = set()
    character_names = [
        r.name for r in session.query(Character).filter_by(novel_id=novel_id)
    ]
    cast_names = [
        r.name for r in session.query(CastEntry).filter_by(novel_id=novel_id)
    ]
    lore_names = [
        r.name for r in session.query(LoreEntry).filter_by(novel_id=novel_id)
    ]
    faction_names = [
        r.name for r in session.query(Faction).filter_by(novel_id=novel_id)
    ]
    keys.update(proposal_key("character", {"name": n}) for n in character_names)
    # 核心角色也阻止同名配角提案；同名 cast 仍允许后续升格为 character。
    keys.update(proposal_key("cast", {"name": n}) for n in character_names + cast_names)
    keys.update(proposal_key("lore", {"name": n}) for n in lore_names)
    keys.update(proposal_key("faction", {"name": n}) for n in faction_names)
    for row in session.query(FactionRelation).filter_by(novel_id=novel_id):
        keys.add(proposal_key("faction_relation", {
            "source": row.source,
            "target": row.target,
            "relation_type": row.relation_type,
        }))
    for row in session.query(PendingProposal).filter_by(
        novel_id=novel_id, status="pending",
    ):
        keys.add(proposal_key(row.kind, row.payload or {}))
    return keys


def load_confirmed_lore_entries(novel_id: int) -> list[dict]:
    """仅返回已确认设定（LoreEntry 表 = 已入账）。"""
    with db_session() as session:
        rows = session.query(LoreEntry).filter_by(
            novel_id=novel_id, enabled=1,
        ).all()
        return [
            {
                "id": r.id, "name": r.name, "category": r.category,
                "keywords": r.keywords or [], "content": r.content,
                "source_chapter": r.source_chapter,
            }
            for r in rows
        ]
