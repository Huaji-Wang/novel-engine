"""配角名册：MergeAppearances + recent_cast（对齐 ainovel-cli）。"""

from __future__ import annotations

from backend.db.models import CastEntry, Character
from backend.db.session import db_session


def load_cast(novel_id: int) -> list[dict]:
    with db_session() as session:
        rows = session.query(CastEntry).filter_by(
            novel_id=novel_id).order_by(CastEntry.last_seen_chapter.desc()).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "brief_role": r.brief_role,
                "first_seen_chapter": r.first_seen_chapter,
                "last_seen_chapter": r.last_seen_chapter,
                "appearance_count": r.appearance_count,
                "appearance_chapters": r.appearance_chapters or [],
                "promoted": bool(r.promoted),
            }
            for r in rows
        ]


def core_character_names(novel_id: int) -> set[str]:
    with db_session() as session:
        return {
            c.name for c in session.query(Character).filter_by(novel_id=novel_id).all()
        }


def merge_cast_appearances(
    novel_id: int,
    chapter_no: int,
    appeared: list[str],
    cast_intros: list[dict],
) -> int:
    """合并本章配角出场记录。返回新增条目数。"""
    if chapter_no <= 0 or not appeared:
        return 0
    known_core = core_character_names(novel_id)
    intro_map = {
        str(x.get("name", "")).strip(): str(x.get("brief_role", "")).strip()
        for x in cast_intros if isinstance(x, dict)
    }
    added = 0
    with db_session() as session:
        by_name = {
            r.name: r for r in session.query(CastEntry).filter_by(novel_id=novel_id).all()
        }
        seen: set[str] = set()
        for name in appeared:
            name = name.strip()
            if not name or name in seen or name in known_core:
                continue
            seen.add(name)
            row = by_name.get(name)
            if row:
                chapters = list(row.appearance_chapters or [])
                if chapter_no not in chapters:
                    chapters.append(chapter_no)
                    chapters.sort()
                    row.appearance_chapters = chapters
                    row.appearance_count = len(chapters)
                    row.last_seen_chapter = max(row.last_seen_chapter, chapter_no)
                    if not row.first_seen_chapter:
                        row.first_seen_chapter = chapter_no
                if not row.brief_role and intro_map.get(name):
                    row.brief_role = intro_map[name]
                continue
            session.add(CastEntry(
                novel_id=novel_id,
                name=name,
                brief_role=intro_map.get(name, ""),
                first_seen_chapter=chapter_no,
                last_seen_chapter=chapter_no,
                appearance_count=1,
                appearance_chapters=[chapter_no],
            ))
            added += 1
    return added


def recent_active_cast(novel_id: int, limit: int = 12) -> list[dict]:
    rows = [r for r in load_cast(novel_id) if not r.get("promoted")]
    rows.sort(key=lambda r: (r.get("last_seen_chapter") or 0, r.get("appearance_count") or 0),
              reverse=True)
    return rows[:limit]


def format_recent_cast(novel_id: int, *, outline_text: str = "") -> str:
    """Writer 上下文：近期活跃配角 + 细纲命中提示。"""
    rows = recent_active_cast(novel_id)
    if not rows:
        return "（无近期配角记录）"
    lines = [
        "以下次要角色曾出场，写到的名字须保持口吻/定位一致；"
        "可回读其 last_seen 章原文（勿写死，仅作 continuity 参考）：",
    ]
    hit_names = [r["name"] for r in rows if r["name"] in (outline_text or "")]
    for r in rows[:10]:
        mark = " ★本章可能涉及" if r["name"] in hit_names else ""
        role = f"，{r['brief_role']}" if r.get("brief_role") else ""
        lines.append(
            f"- {r['name']}{role}（第{r['first_seen_chapter']}-{r['last_seen_chapter']}章，"
            f"共{r['appearance_count']}次）{mark}"
        )
    return "\n".join(lines)
