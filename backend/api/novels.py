"""小说 CRUD 与手动编辑接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.schemas import (
    ChapterEdit,
    CompassEdit,
    FieldEdit,
    LoreEntryCreate,
    LoreEntryEdit,
    NovelCreate,
    OutlineEdit,
    VolumeEdit,
)
from backend.db.models import (
    Arc,
    CastEntry,
    Chapter,
    ChapterOutline,
    Character,
    CharacterSnapshot,
    Faction,
    FactionRelation,
    Foreshadowing,
    LoreEntry,
    Novel,
    Payoff,
    RevisionLog,
    Volume,
)
from backend.pending.service import count_pending

router = APIRouter(prefix="/api/novels", tags=["novels"])

EDITABLE_FIELDS = {
    "title", "premise", "genre", "user_guidance",
    "subtitle", "introduction", "book_summary",
    "writing_style", "narrative_pov", "era_background",
    "full_story", "core_seed", "character_dynamics", "world_building",
    "plot_architecture", "global_summary", "character_state",
    "style_guide",
}


def _novel_or_404(session, novel_id: int) -> Novel:
    novel = session.get(Novel, novel_id)
    if not novel:
        raise HTTPException(404, "小说不存在")
    return novel


def novel_detail(novel: Novel) -> dict:
    return {
        "id": novel.id,
        "title": novel.title,
        "premise": novel.premise,
        "genre": novel.genre,
        "num_chapters": novel.num_chapters,
        "words_per_chapter": novel.words_per_chapter,
        "user_guidance": novel.user_guidance,
        "subtitle": novel.subtitle,
        "introduction": novel.introduction,
        "book_summary": novel.book_summary,
        "writing_style": novel.writing_style,
        "narrative_pov": novel.narrative_pov,
        "era_background": novel.era_background,
        "tags": novel.tags or [],
        "full_story": novel.full_story,
        "core_seed": novel.core_seed,
        "character_dynamics": novel.character_dynamics,
        "world_building": novel.world_building,
        "plot_architecture": novel.plot_architecture,
        "global_summary": novel.global_summary,
        "character_state": novel.character_state,
        "style_guide": novel.style_guide,
        "style_profile_id": novel.style_profile_id,
        "quality_gate": novel.quality_gate or {},
        "pending_count": count_pending(novel.id),
        "story_compass": novel.story_compass or {},
        "writing_style_rules": novel.writing_style_rules or {},
        "characters": [
            {
                "id": c.id, "name": c.name,
                "first_chapter": c.first_chapter, "last_chapter": c.last_chapter,
                "status": c.status, **(c.data or {}),
            }
            for c in novel.characters
        ],
        "chapter_outlines": sorted(
            (
                {
                    "chapter_no": o.chapter_no,
                    "title": o.title,
                    "content": o.content,
                    "status": o.status,
                }
                for o in novel.chapter_outlines
            ),
            key=lambda x: x["chapter_no"],
        ),
        "chapters": sorted(
            (
                {
                    "chapter_no": ch.chapter_no,
                    "title": ch.title,
                    "content": ch.content,
                    "summary": ch.summary,
                    "review": ch.review,
                    "critique": ch.critique,
                    "health_report": ch.health_report,
                    "toxin_report": ch.toxin_report,
                    "status": ch.status,
                }
                for ch in novel.chapters
            ),
            key=lambda x: x["chapter_no"],
        ),
    }


@router.post("")
def create_novel(payload: NovelCreate):
    with db_session() as session:
        novel = Novel(**payload.model_dump())
        session.add(novel)
        session.flush()
        return {"id": novel.id}


@router.get("")
def list_novels():
    with db_session() as session:
        novels = session.query(Novel).order_by(Novel.id.desc()).all()
        return [
            {
                "id": n.id, "title": n.title, "genre": n.genre,
                "num_chapters": n.num_chapters,
                "has_blueprint": bool(n.plot_architecture),
                "chapters_done": len(n.chapters),
            }
            for n in novels
        ]


@router.get("/{novel_id}")
def get_novel(novel_id: int):
    with db_session() as session:
        detail = novel_detail(_novel_or_404(session, novel_id))
        detail["foreshadowings"] = [
            {
                "id": f.id, "name": f.name, "description": f.description,
                "status": f.status, "planted_chapter": f.planted_chapter,
                "last_touched_chapter": f.last_touched_chapter,
                "resolve_by_chapter": f.resolve_by_chapter, "notes": f.notes,
            }
            for f in session.query(Foreshadowing).filter_by(novel_id=novel_id)
            .order_by(Foreshadowing.planted_chapter).all()
        ]
        detail["volumes"] = []
        for v in session.query(Volume).filter_by(novel_id=novel_id).order_by(Volume.volume_no).all():
            arcs = session.query(Arc).filter_by(volume_id=v.id).order_by(Arc.arc_no).all()
            detail["volumes"].append({
                "volume_no": v.volume_no, "title": v.title,
                "start_chapter": v.start_chapter, "end_chapter": v.end_chapter,
                "theme": v.theme, "summary": v.summary,
                "key_events": v.key_events or [],
                "arcs": [
                    {
                        "arc_no": a.arc_no, "title": a.title, "goal": a.goal,
                        "start_chapter": a.start_chapter, "end_chapter": a.end_chapter,
                        "estimated_chapters": a.estimated_chapters,
                        "summary": a.summary, "key_events": a.key_events or [],
                        "arc_review": a.arc_review or "",
                        "status": a.status,
                    }
                    for a in arcs
                ],
            })
        detail["character_snapshots"] = [
            {
                "volume_no": s.volume_no, "arc_no": s.arc_no, "name": s.name,
                "status": s.status, "power": s.power,
                "motivation": s.motivation, "relations": s.relations,
            }
            for s in session.query(CharacterSnapshot).filter_by(novel_id=novel_id)
            .order_by(CharacterSnapshot.volume_no, CharacterSnapshot.arc_no, CharacterSnapshot.name)
            .all()
        ]
        detail["factions"] = [
            {
                "id": f.id, "name": f.name,
                "first_chapter": f.first_chapter, "last_chapter": f.last_chapter,
                "status": f.status, **(f.data or {}),
            }
            for f in session.query(Faction).filter_by(novel_id=novel_id).all()
        ]
        detail["faction_relations"] = [
            {"source": r.source, "target": r.target,
             "relation_type": r.relation_type, **(r.data or {})}
            for r in session.query(FactionRelation).filter_by(novel_id=novel_id).all()
        ]
        detail["lore_entries"] = [
            {"id": e.id, "name": e.name, "category": e.category,
             "keywords": e.keywords or [], "content": e.content,
             "source_chapter": e.source_chapter, "enabled": bool(e.enabled)}
            for e in session.query(LoreEntry).filter_by(novel_id=novel_id)
            .order_by(LoreEntry.category, LoreEntry.id).all()
        ]
        detail["payoffs"] = [
            {
                "id": p.id, "chapter_no": p.chapter_no,
                "payoff_type": p.payoff_type, "name": p.name,
                "description": p.description, "intensity": p.intensity,
            }
            for p in session.query(Payoff).filter_by(novel_id=novel_id)
            .order_by(Payoff.chapter_no).all()
        ]
        detail["cast_entries"] = [
            {
                "id": c.id, "name": c.name, "brief_role": c.brief_role,
                "first_seen_chapter": c.first_seen_chapter,
                "last_seen_chapter": c.last_seen_chapter,
                "appearance_count": c.appearance_count,
                "promoted": bool(c.promoted),
            }
            for c in session.query(CastEntry).filter_by(novel_id=novel_id)
            .order_by(CastEntry.last_seen_chapter.desc()).all()
        ]
        return detail


@router.delete("/{novel_id}")
def delete_novel(novel_id: int):
    with db_session() as session:
        session.delete(_novel_or_404(session, novel_id))
        return {"ok": True}


@router.put("/{novel_id}/field")
def edit_field(novel_id: int, payload: FieldEdit):
    if payload.field not in EDITABLE_FIELDS:
        raise HTTPException(400, f"字段不可编辑: {payload.field}")
    with db_session() as session:
        novel = _novel_or_404(session, novel_id)
        old = getattr(novel, payload.field)
        setattr(novel, payload.field, payload.content)
        session.add(RevisionLog(
            novel_id=novel_id, target_type=payload.field,
            target_key=payload.field, instruction="", old_content=old or "",
        ))
        return {"ok": True}


@router.put("/{novel_id}/outlines/{chapter_no}")
def edit_outline(novel_id: int, chapter_no: int, payload: OutlineEdit):
    with db_session() as session:
        _novel_or_404(session, novel_id)
        outline = session.query(ChapterOutline).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if not outline:
            raise HTTPException(404, "细纲不存在")
        session.add(RevisionLog(
            novel_id=novel_id, target_type="chapter_outline",
            target_key=str(chapter_no), instruction="", old_content=outline.content,
        ))
        outline.content = payload.content
        if payload.title is not None:
            outline.title = payload.title
        outline.status = "edited"
        return {"ok": True}


@router.put("/{novel_id}/volumes/{volume_no}")
def edit_volume(novel_id: int, volume_no: int, payload: VolumeEdit):
    with db_session() as session:
        _novel_or_404(session, novel_id)
        volume = session.query(Volume).filter_by(
            novel_id=novel_id, volume_no=volume_no).first()
        if not volume:
            raise HTTPException(404, "卷不存在")
        for field in ("title", "theme", "summary"):
            value = getattr(payload, field)
            if value is not None:
                setattr(volume, field, value)
        volume.status = "edited"
        return {"ok": True}


@router.put("/{novel_id}/compass")
def edit_compass(novel_id: int, payload: CompassEdit):
    """手动编辑终局指南针（软锚，可随时调整）。"""
    with db_session() as session:
        n = _novel_or_404(session, novel_id)
        compass = dict(n.story_compass or {})
        if payload.ending_direction is not None:
            compass["ending_direction"] = payload.ending_direction
        if payload.open_threads is not None:
            compass["open_threads"] = payload.open_threads
        if payload.estimated_scale is not None:
            compass["estimated_scale"] = payload.estimated_scale
        compass["planning_mode"] = compass.get("planning_mode") or "rolling"
        n.story_compass = compass
        return {"ok": True, "story_compass": compass}


@router.put("/{novel_id}/characters/{char_id}/status")
def set_character_status(novel_id: int, char_id: int, status: str):
    if status not in ("active", "inactive"):
        raise HTTPException(400, "status 须为 active 或 inactive")
    with db_session() as session:
        char = session.get(Character, char_id)
        if not char or char.novel_id != novel_id:
            raise HTTPException(404, "角色不存在")
        char.status = status
        return {"ok": True}


@router.put("/{novel_id}/factions/{faction_id}/status")
def set_faction_status(novel_id: int, faction_id: int, status: str):
    if status not in ("active", "inactive"):
        raise HTTPException(400, "status 须为 active 或 inactive")
    with db_session() as session:
        fac = session.get(Faction, faction_id)
        if not fac or fac.novel_id != novel_id:
            raise HTTPException(404, "阵营不存在")
        fac.status = status
        return {"ok": True}


@router.post("/{novel_id}/lore")
def add_lore_entry(novel_id: int, payload: LoreEntryCreate):
    with db_session() as session:
        _novel_or_404(session, novel_id)
        entry = LoreEntry(novel_id=novel_id, **payload.model_dump())
        session.add(entry)
        session.flush()
        return {"id": entry.id}


@router.put("/{novel_id}/lore/{entry_id}")
def edit_lore_entry(novel_id: int, entry_id: int, payload: LoreEntryEdit):
    with db_session() as session:
        entry = session.get(LoreEntry, entry_id)
        if not entry or entry.novel_id != novel_id:
            raise HTTPException(404, "设定条目不存在")
        for field in ("name", "category", "keywords", "content"):
            value = getattr(payload, field)
            if value is not None:
                setattr(entry, field, value)
        if payload.enabled is not None:
            entry.enabled = int(payload.enabled)
        return {"ok": True}


@router.delete("/{novel_id}/lore/{entry_id}")
def delete_lore_entry(novel_id: int, entry_id: int):
    with db_session() as session:
        entry = session.get(LoreEntry, entry_id)
        if not entry or entry.novel_id != novel_id:
            raise HTTPException(404, "设定条目不存在")
        session.delete(entry)
        return {"ok": True}


@router.put("/{novel_id}/chapters/{chapter_no}")
def edit_chapter(novel_id: int, chapter_no: int, payload: ChapterEdit):
    with db_session() as session:
        _novel_or_404(session, novel_id)
        chapter = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if not chapter:
            raise HTTPException(404, "章节不存在")
        session.add(RevisionLog(
            novel_id=novel_id, target_type="chapter",
            target_key=str(chapter_no), instruction="", old_content=chapter.content,
        ))
        chapter.content = payload.content
        chapter.status = "edited"
        return {"ok": True}
