"""将 deepen_character 结果写入 Novel / Character。"""

from __future__ import annotations

from typing import Any

from backend.agents.character import merge_card_data, normalize_card_payload
from backend.db.models import Character, Novel
from backend.db.session import db_session


def append_dynamics_section(dynamics: str, appendix: str, name: str) -> str:
    appendix = (appendix or "").strip()
    if not appendix:
        return dynamics or ""
    marker = f"### {name}"
    base = dynamics or ""
    if marker in base:
        return base
    section_title = "## 深化角色档案"
    if section_title in base:
        return base.rstrip() + "\n\n" + appendix
    return base.rstrip() + f"\n\n{section_title}\n\n" + appendix


def append_state_block(state: str, block: str, name: str) -> str:
    block = (block or "").strip()
    if not block:
        return state or ""
    header = f"{name}："
    if header in (state or ""):
        return (state or "").rstrip() + f"\n\n<!-- deepened:{name} -->\n{block}\n"
    return (state or "").rstrip() + f"\n\n{block}\n"


def apply_deepen_result(
    novel_id: int,
    *,
    char_id: int | None,
    name: str,
    raw: dict[str, Any],
    first_chapter: int = 0,
    last_chapter: int = 0,
    create_if_missing: bool = False,
) -> int:
    """更新或创建 Character，并回写 character_dynamics / character_state。返回 character id。"""
    card = normalize_card_payload(raw)
    card = merge_card_data({}, card)
    dynamics_appendix = str(raw.get("dynamics_appendix") or "").strip()
    state_block = str(raw.get("state_block") or "").strip()

    with db_session() as session:
        novel = session.get(Novel, novel_id)
        if not novel:
            raise ValueError("小说不存在")

        row: Character | None = None
        if char_id:
            row = session.get(Character, char_id)
        if row is None:
            row = session.query(Character).filter_by(
                novel_id=novel_id, name=name).first()
        if row is None:
            if not create_if_missing:
                raise ValueError(f"角色「{name}」不存在")
            row = Character(
                novel_id=novel_id,
                name=name,
                data=card,
                first_chapter=first_chapter or 0,
                last_chapter=last_chapter or first_chapter or 0,
                status="active",
            )
            session.add(row)
        else:
            row.data = merge_card_data(row.data or {}, card)
            if first_chapter and not row.first_chapter:
                row.first_chapter = first_chapter
            if last_chapter:
                row.last_chapter = last_chapter
            row.status = "active"

        novel.character_dynamics = append_dynamics_section(
            novel.character_dynamics or "", dynamics_appendix, name)
        novel.character_state = append_state_block(
            novel.character_state or "", state_block, name)

        session.flush()
        return row.id
