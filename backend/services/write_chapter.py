"""写章流水线（后台任务版）：与 LangGraph 图同一套节点，
但每个节点之间把状态落入 job.checkpoint，进程崩溃/重启后从断点继续，
不重复消耗已完成节点的 LLM token。
"""

from __future__ import annotations

import json
import logging

from langgraph.graph import END

from backend.api.generation import (
    _compiled_style_for_novel,
    _effective_quality_gate,
    _format_arc_hook_note,
    _guard_chapter_planning,
    _load_characters,
    _load_ledger,
    _load_lore,
    _load_novel,
    _load_volumes,
)
from backend.agents.cocreate import format_chapter_contract, format_cocreate_context
from backend.agents.narrative_ledger import format_ledger
from backend.agents.worldkeeper import format_lore, match_lore
from backend.characters.cast import format_recent_cast
from backend.characters.voice import build_voice_context
from backend.config import app_config
from backend.context.budget import (
    apply_writer_budget,
    budget_log_message,
    strategy_profile,
)
from backend.db.models import Chapter, ChapterOutline, RevisionLog
from backend.db.session import db_session
from backend.graph.chapter_graph import (
    CHAPTER_STEPS,
    NODE_FUNCS,
    route_after_quality,
    route_after_review,
)
from backend.jobs.context import JobContext
from backend.pending.service import count_pending
from backend.planning.compass import (
    format_character_snapshots_context,
    format_compass_context,
    format_style_rules_context,
    load_latest_character_snapshots,
)
from backend.planning.guidance import budget_scale, format_guides_block

logger = logging.getLogger(__name__)

CANCELLED = object()


def prepare_write_state(novel_id: int, chapter_no: int, user_guidance: str = "") -> dict:
    """组装写章全部上下文（零 LLM），并按自适应策略裁剪到预算内。

    前置条件不满足时抛 HTTPException；裁剪报告放在 state["_context_budget"]。
    """
    novel = _load_novel(novel_id)
    _guard_chapter_planning(novel_id, novel, chapter_no)
    profile = strategy_profile(budget_scale(novel["num_chapters"], chapter_no))
    with db_session() as session:
        outline = session.query(ChapterOutline).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if not outline:
            from fastapi import HTTPException
            raise HTTPException(400, f"第{chapter_no}章细纲不存在，请先生成细纲")
        outline_title, outline_content = outline.title, outline.content
        next_outline = session.query(ChapterOutline).filter_by(
            novel_id=novel_id, chapter_no=chapter_no + 1).first()
        next_outline_content = next_outline.content if next_outline else ""
        prev_chapter = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no - 1).first()
        prev_excerpt = (
            prev_chapter.content[-int(profile["prev_excerpt_chars"]):]
            if prev_chapter else "")

    guidance_kw = {
        "guide_style": novel.get("guide_style") or "",
        "guide_pov": novel.get("guide_pov") or "",
        "guide_taboos": novel.get("guide_taboos") or "",
        "cocreate_context": format_cocreate_context(
            draft=novel.get("cocreate_draft") or "",
            locks=novel.get("cocreate_locks") or {},
            is_fanfic=bool(novel.get("is_fanfic")),
        ),
        "chapter_extra": (user_guidance or "").strip(),
    }
    guidance_block = format_guides_block(**guidance_kw)

    match_text = "\n".join([outline_title, outline_content, next_outline_content])
    lore_context = format_lore(match_lore(_load_lore(novel_id), match_text))

    characters = _load_characters(novel_id)
    known_names = [c["name"] for c in characters]
    compiled_style = _compiled_style_for_novel(novel)
    gate = _effective_quality_gate(novel)
    outline_blob = "\n".join([outline_title, outline_content, next_outline_content])
    style_rules = novel.get("writing_style_rules") or {}
    voice_context = build_voice_context(
        novel_id, outline_text=outline_blob, characters=characters,
        style_dialogue=style_rules.get("dialogue"),
    )
    snapshots_context = format_character_snapshots_context(
        load_latest_character_snapshots(novel_id))
    character_state = novel["character_state"]
    if snapshots_context != "（无）":
        character_state = (
            f"{character_state or ''}\n\n【弧末角色快照】\n{snapshots_context}".strip()
        )
    volumes = _load_volumes(novel_id)

    state = {
        "novel_id": novel_id,
        "chapter_no": chapter_no,
        "chapter_title": outline_title,
        "chapter_outline": outline_content,
        "chapter_contract": format_chapter_contract(outline_content),
        "next_chapter_outline": next_outline_content,
        "core_seed": novel["core_seed"],
        "world_building": novel["world_building"],
        "plot_architecture": novel["plot_architecture"],
        "character_state": character_state,
        "global_summary": novel["global_summary"],
        "previous_chapter_excerpt": prev_excerpt,
        "words_per_chapter": novel["words_per_chapter"],
        "user_guidance": guidance_block,
        **guidance_kw,
        "max_revise_rounds": int(app_config().get("max_auto_revise_rounds", 1)),
        "max_quality_rounds": int(gate.get("max_quality_rewrite_rounds", 1)),
        "foreshadowing_ledger": format_ledger(_load_ledger(novel_id)),
        "writing_style": novel["writing_style"],
        "narrative_pov": novel["narrative_pov"],
        "compiled_style": compiled_style,
        "style_guide": compiled_style,
        "lore_context": lore_context,
        "voice_context": voice_context,
        "compass_context": format_compass_context(novel.get("story_compass")),
        "style_rules_context": format_style_rules_context(style_rules),
        "recent_cast_context": format_recent_cast(novel_id, outline_text=outline_blob),
        "arc_hook_note": _format_arc_hook_note(volumes, chapter_no),
        "known_character_names": known_names,
        "pending_count": count_pending(novel_id),
    }
    state["_context_budget"] = apply_writer_budget(
        state, num_chapters=budget_scale(novel["num_chapters"], chapter_no))
    return state


def _next_phase(phase: str, state: dict) -> str:
    if phase == "retrieve_memory":
        return "write"
    if phase == "write":
        return "consistency_check"
    if phase == "consistency_check":
        return route_after_review(state)
    if phase == "auto_revise":
        return "consistency_check"
    if phase in ("quality_gate", "quality_fix"):
        nxt = route_after_quality(state)
        return "__end__" if nxt == END else nxt
    return "__end__"


def _step_payload(phase: str, state: dict) -> dict:
    if phase == "consistency_check":
        return {"review": state.get("review") or {}}
    if phase == "quality_gate":
        return {
            "health": state.get("health_report") or {},
            "readiness": state.get("readiness_report") or {},
            "decision": state.get("quality_decision") or {},
        }
    return {}


def _persist_chapter(state: dict) -> None:
    novel_id, chapter_no = state["novel_id"], state["chapter_no"]
    review = state.get("review") or {}
    health = state.get("health_report") or {}
    readiness = state.get("readiness_report") or {}
    qdecision = state.get("quality_decision") or {}
    with db_session() as session:
        chapter = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if chapter:
            session.add(RevisionLog(
                novel_id=novel_id, target_type="chapter",
                target_key=str(chapter_no), instruction="（重新生成）",
                old_content=chapter.content,
            ))
            chapter.content = state.get("draft", "")
            chapter.title = state.get("chapter_title", "")
            chapter.review = json.dumps(review, ensure_ascii=False)
            chapter.health_report = json.dumps(health, ensure_ascii=False)
            chapter.readiness_report = json.dumps(readiness, ensure_ascii=False)
            chapter.quality_decision = json.dumps(qdecision, ensure_ascii=False)
            chapter.status = "draft"
        else:
            session.add(Chapter(
                novel_id=novel_id, chapter_no=chapter_no,
                title=state.get("chapter_title", ""), content=state.get("draft", ""),
                review=json.dumps(review, ensure_ascii=False),
                health_report=json.dumps(health, ensure_ascii=False),
                readiness_report=json.dumps(readiness, ensure_ascii=False),
                quality_decision=json.dumps(qdecision, ensure_ascii=False),
            ))


def run_write_job(job: dict, ctx: JobContext) -> dict | object:
    """按节点推进写章流水线；每个节点完成即落 checkpoint。"""
    params = job.get("params") or {}
    checkpoint = dict(job.get("checkpoint") or {})
    state = checkpoint.get("state")
    if not state:
        state = prepare_write_state(
            int(params["novel_id"]), int(params["chapter_no"]),
            str(params.get("user_guidance", "")),
        )
    phase = checkpoint.get("phase") or "retrieve_memory"

    already_has_steps = any(
        entry.get("event") == "steps" for entry in (job.get("progress") or []))
    if not already_has_steps:
        ctx.emit("steps", {"steps": [
            {"id": k, "label": v} for k, v in CHAPTER_STEPS.items()]})
        report = state.get("_context_budget")
        if report:
            ctx.emit("log", {"message": budget_log_message(report)})

    while phase != "__end__":
        if ctx.cancelled():
            return CANCELLED
        updates = NODE_FUNCS[phase](state) or {}
        state.update(updates)
        nxt = _next_phase(phase, state)
        ctx.save_checkpoint({"phase": nxt, "state": state})
        ctx.emit("step_done", {
            "id": phase,
            "label": CHAPTER_STEPS.get(phase, phase),
            "payload": _step_payload(phase, state),
        })
        phase = nxt

    _persist_chapter(state)
    result = {
        "chapter_no": state["chapter_no"],
        "review": state.get("review") or {},
        "health": state.get("health_report") or {},
        "readiness": state.get("readiness_report") or {},
        "quality_decision": state.get("quality_decision") or {},
    }
    ctx.emit("done", result)
    return result
