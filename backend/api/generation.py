"""AI 生成与修订接口：全部以 SSE 流式返回逐步进度。

事件协议：
  event: steps      data: {"steps": [{"id", "label"}]}        # 流程开始，公布步骤清单
  event: step_done  data: {"id", "label", "payload"?}         # 某步骤完成
  event: done       data: {...}                               # 全部完成
  event: error      data: {"message"}
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import queue
import threading
from collections.abc import AsyncIterator, Callable, Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.agents.chapter_planner import ChapterPlannerAgent
from backend.agents.character import CharacterAgent, merge_card_data
from backend.agents.cocreate import format_cocreate_context
from backend.agents.editor import EditorAgent
from backend.agents.impact import ImpactAgent
from backend.agents.narrative_ledger import (
    format_ledger,
    format_payoff_ledger,
)
from backend.agents.planner import PlannerAgent, format_volume_context
from backend.agents.revision import TARGET_LABELS, RevisionAgent
from backend.agents.reviewer import ReviewerAgent
from backend.agents.style_learner import StyleLearnerAgent
from backend.agents.worldkeeper import (
    WorldKeeperAgent,
    format_factions_brief,
)
from backend.planning.guidance import chapter_cap, guides_from_novel, is_scale_open
from backend.api.schemas import (
    AppendVolumeRequest,
    DeepenCharactersRequest,
    ExpandArcRequest,
    ProposeNextVolumeRequest,
    ReplanSkeletonArcsRequest,
    UserHintRequest,
    PolishRequest, ReviseRequest, SegmentEditRequest, SegmentReviseRequest,
    StyleLearnRequest, WriteChapterRequest,
)
from backend.characters.deepen import apply_deepen_result
from backend.config import app_config, quality_gate_config
from backend.pending.service import load_confirmed_lore_entries
from backend.style.compiler import compile_style_context
from backend.planning.compass import format_compass_context
from backend.planning.skeleton import (
    allocate_skeleton_arc,
    find_skeleton_arc,
    next_skeleton_to_expand,
)
from backend.planning.structure import (
    find_arc_for_chapter,
    format_arc_context,
    format_prev_arcs_context,
    is_volume_end,
)
from backend.planning.volumes import (
    chapter_beyond_planned,
    format_arc_summaries_for_propose,
    format_volume_summaries,
    is_book_complete,
    last_volume,
    locked_arcs_text,
    option_to_volume_dict,
    prepare_volume_for_persist,
    skeleton_arcs_text,
)
from backend.db.models import (
    Arc,
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
    WritingStyleProfile,
)
from backend.db.session import db_session
from backend.graph.blueprint_graph import BLUEPRINT_STEPS, iter_blueprint_steps
from backend.graph.chapter_graph import CHAPTER_STEPS, build_chapter_graph
from backend.utils.chapter_health import check_chapter_health

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/novels", tags=["generation"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sse_response(gen: Iterator[str] | AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(gen, media_type="text/event-stream", headers=SSE_HEADERS)


async def _sse_from_worker(
    *,
    preamble: list[tuple[str, dict]],
    worker: Callable[[Callable[[str, dict], None]], None],
    heartbeat_seconds: float = 15.0,
    heartbeat_message: str = "仍在生成中，请稍候…",
) -> AsyncIterator[str]:
    """在线程里跑阻塞流水线，主协程立即推 SSE，并定期心跳，避免长时间无输出像卡死。"""
    for event, data in preamble:
        yield _sse(event, data)
    q: queue.Queue[tuple[str, dict] | None] = queue.Queue()
    status = {"heartbeat": heartbeat_message}

    def emit(event: str, data: dict | None = None) -> None:
        payload = data or {}
        if event == "step_start" and payload.get("label"):
            status["heartbeat"] = f"正在执行：{payload['label']}（模型调用中，请稍候）…"
        elif event == "log" and payload.get("message"):
            # 保留最近日志作心跳文案
            status["heartbeat"] = str(payload["message"])
        q.put((event, payload))

    def run() -> None:
        try:
            worker(emit)
        except Exception as e:  # noqa: BLE001
            logger.exception("SSE worker 失败")
            q.put(("error", {"message": str(e)}))
        finally:
            q.put(None)

    threading.Thread(target=run, daemon=True).start()
    while True:
        try:
            item = await asyncio.to_thread(q.get, True, heartbeat_seconds)
        except queue.Empty:
            yield _sse("log", {"message": status["heartbeat"]})
            continue
        if item is None:
            break
        event, data = item
        yield _sse(event, data)


def _load_novel(novel_id: int) -> dict:
    with db_session() as session:
        novel = session.get(Novel, novel_id)
        if not novel:
            raise HTTPException(404, "小说不存在")
        return {
            "id": novel.id, "title": novel.title,
            "premise": novel.premise, "genre": novel.genre,
            "writing_style": novel.writing_style,
            "narrative_pov": novel.narrative_pov,
            "num_chapters": novel.num_chapters,
            "words_per_chapter": novel.words_per_chapter,
            "guide_style": getattr(novel, "guide_style", "") or "",
            "guide_pov": getattr(novel, "guide_pov", "") or "",
            "guide_taboos": getattr(novel, "guide_taboos", "") or "",
            "is_fanfic": bool(getattr(novel, "is_fanfic", 0)),
            "cocreate_draft": getattr(novel, "cocreate_draft", "") or "",
            "cocreate_ready": bool(getattr(novel, "cocreate_ready", 0)),
            "cocreate_locks": dict(getattr(novel, "cocreate_locks", None) or {}),
            "full_story": novel.full_story,
            "core_seed": novel.core_seed,
            "character_dynamics": novel.character_dynamics,
            "world_building": novel.world_building,
            "plot_architecture": novel.plot_architecture,
            "global_summary": novel.global_summary,
            "character_state": novel.character_state,
            "style_guide": novel.style_guide or "",
            "style_profile_id": novel.style_profile_id,
            "quality_gate": novel.quality_gate or {},
            "story_compass": novel.story_compass or {},
            "writing_style_rules": novel.writing_style_rules or {},
        }


def _novel_guide_kwargs(novel: dict) -> dict:
    g = guides_from_novel(novel)
    return {
        **g,
        "cocreate_context": format_cocreate_context(
            draft=novel.get("cocreate_draft") or "",
            locks=novel.get("cocreate_locks") or {},
            is_fanfic=bool(novel.get("is_fanfic")),
        ),
    }


def _effective_quality_gate(novel: dict) -> dict:
    return quality_gate_config(novel.get("quality_gate") or None)


def _load_style_profile_dict(style_profile_id: int | None) -> dict | None:
    if not style_profile_id:
        return None
    with db_session() as session:
        row = session.get(WritingStyleProfile, style_profile_id)
        if not row:
            return None
        return {
            "features": row.features or [],
            "compiled_summary": row.compiled_summary or "",
        }


def _compiled_style_for_novel(novel: dict) -> str:
    profile = _load_style_profile_dict(novel.get("style_profile_id"))
    return compile_style_context(
        profile=profile,
        style_guide=novel.get("style_guide", ""),
        style_rules=novel.get("writing_style_rules"),
        writing_style=novel.get("writing_style", ""),
    )


# ---------------------------------------------------------------- 蓝图生成

def _load_payoffs(novel_id: int) -> list[dict]:
    with db_session() as session:
        rows = session.query(Payoff).filter_by(
            novel_id=novel_id).order_by(Payoff.chapter_no).all()
        return [
            {"id": p.id, "chapter_no": p.chapter_no, "payoff_type": p.payoff_type,
             "name": p.name, "description": p.description, "intensity": p.intensity}
            for p in rows
        ]


def _load_ledger(novel_id: int) -> list[dict]:
    with db_session() as session:
        rows = session.query(Foreshadowing).filter_by(
            novel_id=novel_id).order_by(Foreshadowing.planted_chapter).all()
        return [
            {"id": f.id, "name": f.name, "description": f.description,
             "status": f.status, "planted_chapter": f.planted_chapter,
             "last_touched_chapter": f.last_touched_chapter,
             "resolve_by_chapter": f.resolve_by_chapter, "notes": f.notes}
            for f in rows
        ]


def _load_volumes(novel_id: int) -> list[dict]:
    with db_session() as session:
        vol_rows = session.query(Volume).filter_by(
            novel_id=novel_id).order_by(Volume.volume_no).all()
        result = []
        for v in vol_rows:
            arc_rows = session.query(Arc).filter_by(
                volume_id=v.id).order_by(Arc.arc_no).all()
            result.append({
                "id": v.id,
                "volume_no": v.volume_no,
                "title": v.title,
                "start_chapter": v.start_chapter,
                "end_chapter": v.end_chapter,
                "theme": v.theme,
                "summary": v.summary,
                "key_events": v.key_events or [],
                "arcs": [
                    {
                        "id": a.id,
                        "arc_no": a.arc_no,
                        "title": a.title,
                        "goal": a.goal,
                        "start_chapter": a.start_chapter,
                        "end_chapter": a.end_chapter,
                        "estimated_chapters": a.estimated_chapters,
                        "summary": a.summary,
                        "key_events": a.key_events or [],
                        "arc_review": a.arc_review or "",
                        "status": a.status,
                    }
                    for a in arc_rows
                ],
            })
        return result


def _persist_volume_rows(session, novel_id: int, vol: dict) -> tuple[int, int]:
    """写入一卷及其弧；vol 含 arcs 与 status 字段。"""
    vol = copy.deepcopy(vol)
    arcs = vol.pop("arcs", [])
    vol_row = Volume(
        novel_id=novel_id,
        volume_no=int(vol["volume_no"]),
        title=str(vol.get("title", "")),
        start_chapter=int(vol["start_chapter"]),
        end_chapter=int(vol["end_chapter"]),
        theme=str(vol.get("theme", "")),
        summary=str(vol.get("summary", "")),
        status=str(vol.get("status", "draft")),
    )
    session.add(vol_row)
    session.flush()
    arc_count = 0
    sk_count = 0
    for a in arcs:
        arc_data = dict(a)
        st = arc_data.pop("status", "skeleton")
        if st == "skeleton":
            sk_count += 1
        session.add(Arc(
            novel_id=novel_id,
            volume_id=vol_row.id,
            status=st,
            arc_no=int(arc_data["arc_no"]),
            title=str(arc_data.get("title", "")),
            goal=str(arc_data.get("goal", "")),
            start_chapter=int(arc_data.get("start_chapter") or 0),
            end_chapter=int(arc_data.get("end_chapter") or 0),
            estimated_chapters=int(arc_data.get("estimated_chapters") or 0),
            summary=str(arc_data.get("summary") or ""),
        ))
        arc_count += 1
    return arc_count, sk_count


def _store_volume_proposals(session, novel_id: int, proposal: dict) -> None:
    n = session.get(Novel, novel_id)
    if not n:
        return
    compass = dict(n.story_compass or {})
    compass["pending_volume_options"] = proposal.get("options") or []
    compass["can_complete_book"] = bool(proposal.get("can_complete_book"))
    compass["complete_book_hint"] = str(proposal.get("complete_book_hint") or "")
    compass["proposed_at_volume"] = proposal.get("volume_no")
    n.story_compass = compass


def _clear_volume_proposals(session, novel_id: int) -> None:
    n = session.get(Novel, novel_id)
    if not n:
        return
    compass = dict(n.story_compass or {})
    for key in (
        "pending_volume_options", "can_complete_book",
        "complete_book_hint", "proposed_at_volume",
    ):
        compass.pop(key, None)
    n.story_compass = compass


def _run_propose_next_volume(
    novel_id: int,
    novel: dict,
    volumes: list[dict],
    *,
    volume_no: int | None = None,
    user_hint: str = "",
) -> dict:
    vol = next((v for v in volumes if v["volume_no"] == volume_no), None) if volume_no else last_volume(volumes)
    if not vol:
        raise ValueError("无可用卷用于生成下一卷方向")
    planner = PlannerAgent()
    proposal = planner.propose_next_volume(
        story_compass=novel.get("story_compass") or {},
        global_summary=novel["global_summary"],
        volume_no=vol["volume_no"],
        volume_title=vol["title"],
        volume_theme=vol["theme"],
        volume_summary=vol.get("summary", ""),
        arc_summaries=format_arc_summaries_for_propose(volumes),
        num_chapters=novel["num_chapters"],
        user_hint=user_hint,
    )
    proposal["volume_no"] = vol["volume_no"]
    with db_session() as session:
        _store_volume_proposals(session, novel_id, proposal)
    return proposal


def _guard_chapter_planning(novel_id: int, novel: dict, chapter_no: int) -> None:
    if is_book_complete(novel.get("story_compass")):
        raise HTTPException(400, "全书已标记完结，无法继续写作或生成细纲")
    volumes = _load_volumes(novel_id)
    blocked = chapter_beyond_planned(volumes, chapter_no)
    if blocked:
        raise HTTPException(400, blocked["message"])
    need = next_skeleton_to_expand(volumes, chapter_no)
    if need:
        raise HTTPException(
            400,
            f"第{need['volume_no']}卷第{need['arc_no']}弧《{need['title']}》尚未展开，"
            f"请先调用「展开弧」再生成细纲",
        )


def _arc_chapter_excerpts(
    novel_id: int, start_ch: int, end_ch: int, *, max_chars: int = 12000,
) -> str:
    parts: list[str] = []
    total = 0
    with db_session() as session:
        rows = session.query(Chapter).filter_by(
            novel_id=novel_id, status="finalized",
        ).filter(
            Chapter.chapter_no >= start_ch,
            Chapter.chapter_no <= end_ch,
        ).order_by(Chapter.chapter_no).all()
    for row in rows:
        if not row.content:
            continue
        chunk = f"【第{row.chapter_no}章】\n{row.content[:2500]}"
        if total + len(chunk) > max_chars:
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n\n".join(parts)


def _format_arc_hook_note(volumes: list[dict], chapter_no: int) -> str:
    """写章时注入钩子节奏提示：弧末必钩；其余章遵循约 2–3 章一次强钩子。"""
    arc = find_arc_for_chapter(volumes, chapter_no)
    if arc and chapter_no == arc["end_chapter"]:
        return (
            "【钩子节奏】本章为第"
            f"{arc['volume_no']}卷第{arc['arc_no']}弧最后一章：章末**必须**留强钩子，承接下一弧。"
        )
    return (
        "【钩子节奏】强钩子约每 2–3 章一次即可；若本章细纲 hook 为「无强钩子」或未要求悬念，"
        "可自然收束，勿硬凑 cliffhanger。"
    )


def _sync_dialogue_voice_rules(novel_id: int, dialogue: list) -> list[str]:
    """将 style_rules.dialogue 同步到 Character.data.voice_rules（兼容 build_voice_context）。"""
    by_name = {
        v.get("name"): [str(r) for r in (v.get("rules") or []) if str(r).strip()]
        for v in dialogue
        if isinstance(v, dict) and v.get("name")
    }
    if not by_name:
        return []
    updated: list[str] = []
    with db_session() as session:
        for row in session.query(Character).filter_by(novel_id=novel_id).all():
            rules = by_name.get(row.name)
            if not rules:
                continue
            row.data = merge_card_data(row.data or {}, {"voice_rules": rules})
            updated.append(row.name)
    return updated


def _persist_character_snapshots(
    novel_id: int, volume_no: int, arc_no: int, snapshots: list,
) -> int:
    count = 0
    with db_session() as session:
        for snap in snapshots:
            if not isinstance(snap, dict):
                continue
            name = str(snap.get("name") or "").strip()
            if not name:
                continue
            row = session.query(CharacterSnapshot).filter_by(
                novel_id=novel_id, volume_no=volume_no, arc_no=arc_no, name=name,
            ).first()
            if row:
                row.status = str(snap.get("status") or "")
                row.power = str(snap.get("power") or "")
                row.motivation = str(snap.get("motivation") or "")
                row.relations = str(snap.get("relations") or "")
            else:
                session.add(CharacterSnapshot(
                    novel_id=novel_id,
                    volume_no=volume_no,
                    arc_no=arc_no,
                    name=name,
                    status=str(snap.get("status") or ""),
                    power=str(snap.get("power") or ""),
                    motivation=str(snap.get("motivation") or ""),
                    relations=str(snap.get("relations") or ""),
                ))
            count += 1
    return count


def _format_arc_summaries_for_volume(vol: dict) -> str:
    lines = []
    for arc in vol.get("arcs") or []:
        summary = str(arc.get("summary") or "").strip()
        if summary:
            lines.append(f"第{arc['arc_no']}弧《{arc.get('title', '')}》：{summary}")
    return "\n".join(lines) if lines else "（无）"


def _run_arc_boundary(
    novel_id: int,
    novel: dict,
    chapter_no: int,
    volumes: list[dict],
) -> dict | None:
    """弧末：弧级评审 → 弧摘要/快照/style_rules（对齐 ainovel-cli Router 顺序）。"""
    arc = find_arc_for_chapter(volumes, chapter_no)
    if not arc or chapter_no != arc["end_chapter"] or arc.get("status") == "finished":
        return None

    excerpts = _arc_chapter_excerpts(
        novel_id, arc["start_chapter"], arc["end_chapter"],
    )
    editor = EditorAgent()
    review_payload = editor.review_arc(
        volume_no=arc["volume_no"],
        volume_title=arc.get("volume_title", ""),
        arc_no=arc["arc_no"],
        arc_title=arc["title"],
        arc_goal=arc["goal"],
        start_chapter=arc["start_chapter"],
        end_chapter=arc["end_chapter"],
        global_summary=novel["global_summary"],
        character_state=novel["character_state"],
        chapter_excerpts=excerpts,
    )
    review_summary = str(review_payload.get("summary") or "").strip()
    arc_review_json = json.dumps(review_payload, ensure_ascii=False)

    boundary_payload = editor.save_arc_boundary(
        volume_no=arc["volume_no"],
        volume_title=arc.get("volume_title", ""),
        arc_no=arc["arc_no"],
        arc_title=arc["title"],
        arc_goal=arc["goal"],
        start_chapter=arc["start_chapter"],
        end_chapter=arc["end_chapter"],
        global_summary=novel["global_summary"],
        character_state=novel["character_state"],
        arc_review_summary=review_summary,
        chapter_excerpts=excerpts,
        existing_rules=novel.get("writing_style_rules"),
    )

    arc_summary = str(boundary_payload.get("summary") or "").strip()
    key_events = [
        str(x) for x in (boundary_payload.get("key_events") or []) if str(x).strip()
    ]
    snapshots = boundary_payload.get("character_snapshots") or []
    style_rules = boundary_payload.get("style_rules") or {}
    prose = [str(x) for x in (style_rules.get("prose") or []) if str(x).strip()][:5]
    taboos = [str(x) for x in (style_rules.get("taboos") or []) if str(x).strip()][:8]
    dialogue = [
        {"name": str(v.get("name")), "rules": [str(r) for r in (v.get("rules") or []) if str(r).strip()][:3]}
        for v in (style_rules.get("dialogue") or [])
        if isinstance(v, dict) and v.get("name")
    ]

    snapshot_count = _persist_character_snapshots(
        novel_id, arc["volume_no"], arc["arc_no"], snapshots,
    )
    voice_updated = _sync_dialogue_voice_rules(novel_id, dialogue)

    with db_session() as session:
        row = session.get(Arc, arc["id"])
        if row:
            row.summary = arc_summary or row.summary
            row.key_events = key_events
            row.arc_review = arc_review_json
            row.status = "finished"
        n = session.get(Novel, novel_id)
        if n and (prose or dialogue or taboos):
            merged = dict(n.writing_style_rules or {})
            if prose:
                merged["prose"] = prose
            if dialogue:
                merged["dialogue"] = dialogue
            if taboos:
                merged["taboos"] = taboos
            merged["updated_at_arc"] = {
                "volume_no": arc["volume_no"],
                "arc_no": arc["arc_no"],
                "end_chapter": chapter_no,
            }
            n.writing_style_rules = merged

    return {
        "arc_no": arc["arc_no"],
        "title": arc["title"],
        "summary": arc_summary,
        "review_verdict": review_payload.get("verdict"),
        "snapshot_count": snapshot_count,
        "voice_updated": voice_updated,
        "style_rules_updated": bool(prose or dialogue or taboos),
    }


def _run_volume_summary(
    novel_id: int,
    novel: dict,
    chapter_no: int,
    volumes: list[dict],
) -> dict | None:
    """卷末：生成卷摘要（在指南针更新之前）。"""
    if not is_volume_end(volumes, chapter_no):
        return None
    vol = next(v for v in volumes if v["end_chapter"] == chapter_no)
    excerpts = _arc_chapter_excerpts(
        novel_id, vol["start_chapter"], vol["end_chapter"], max_chars=16000,
    )
    payload = EditorAgent().summarize_volume(
        volume_no=vol["volume_no"],
        volume_title=vol["title"],
        volume_theme=vol["theme"],
        start_chapter=vol["start_chapter"],
        end_chapter=vol["end_chapter"],
        global_summary=novel["global_summary"],
        arc_summaries=_format_arc_summaries_for_volume(vol),
        chapter_excerpts=excerpts,
    )
    summary = str(payload.get("summary") or "").strip()
    key_events = [
        str(x) for x in (payload.get("key_events") or []) if str(x).strip()
    ]
    with db_session() as session:
        row = session.query(Volume).filter_by(
            novel_id=novel_id, volume_no=vol["volume_no"],
        ).first()
        if row:
            row.summary = summary or row.summary
            row.key_events = key_events
    return {
        "volume_no": vol["volume_no"],
        "title": vol["title"],
        "summary": summary,
        "key_events": key_events,
    }


def _outline_plan_blocks(
    novel_id: int,
    novel: dict,
    start_no: int,
    end_no: int,
    existing_text: str,
    *,
    expand_arc: dict | None = None,
) -> list[dict]:
    volumes = _load_volumes(novel_id)
    planner = ChapterPlannerAgent()
    common = dict(
        core_seed=novel["core_seed"],
        world_building=novel["world_building"],
        plot_architecture=novel["plot_architecture"],
        character_state=novel["character_state"],
        global_summary=novel["global_summary"],
        existing_outlines=existing_text,
        start_no=start_no,
        end_no=end_no,
        foreshadowing_ledger=format_ledger(_load_ledger(novel_id)),
        volume_context=format_volume_context(volumes, start_no, end_no),
        arc_context=format_arc_context(volumes, start_no, end_no),
        compass_context=format_compass_context(novel.get("story_compass")),
        factions_brief=format_factions_brief(*_load_factions(novel_id)),
        payoff_ledger=format_payoff_ledger(
            _load_payoffs(novel_id), up_to_chapter=start_no - 1),
        **_novel_guide_kwargs(novel),
    )
    if expand_arc:
        return planner.plan_arc_expand(
            **common,
            volume_no=int(expand_arc["volume_no"]),
            arc_no=int(expand_arc["arc_no"]),
            arc_title=str(expand_arc.get("title", "")),
            arc_goal=str(expand_arc.get("goal", "")),
            estimated_chapters=int(expand_arc.get("estimated_chapters") or (end_no - start_no + 1)),
            prev_arcs_context=format_prev_arcs_context(
                volumes,
                volume_no=int(expand_arc["volume_no"]),
                before_arc_no=int(expand_arc["arc_no"]),
            ),
        )
    return planner.plan_next(
        **common,
        num_chapters=novel["num_chapters"],
        is_fanfic=bool(novel.get("is_fanfic")),
    )


def _load_characters(novel_id: int) -> list[dict]:
    with db_session() as session:
        return [
            {"id": c.id, "name": c.name, "data": c.data or {},
             "first_chapter": c.first_chapter, "last_chapter": c.last_chapter,
             "status": c.status}
            for c in session.query(Character).filter_by(novel_id=novel_id).all()
        ]


def _load_chapter_text(novel_id: int, chapter_no: int) -> str:
    with db_session() as session:
        ch = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        return ch.content if ch and ch.content else ""


def _load_outline_text(novel_id: int, chapter_no: int) -> str:
    with db_session() as session:
        ol = session.query(ChapterOutline).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if not ol:
            return ""
        title = ol.title or ""
        return f"第{chapter_no}章 {title}\n{ol.content or ''}".strip()


def _build_deepen_context(
    novel_id: int,
    *,
    mode: str,
    name: str,
    debut_chapter_no: int | None,
    target_chapter_no: int | None,
    role_hint: str = "",
) -> str:
    parts: list[str] = []
    if mode == "planned":
        ch_no = target_chapter_no
        if ch_no:
            outline = _load_outline_text(novel_id, ch_no)
            if outline:
                parts.append(f"【预计第{ch_no}章细纲】\n{outline}")
            else:
                parts.append(f"（第{ch_no}章细纲尚未生成，请依据前情与情节架构推断出场方式）")
        if role_hint:
            parts.append(f"【规划功能】{role_hint}")
    else:
        ch_no = debut_chapter_no
        if ch_no:
            text = _load_chapter_text(novel_id, ch_no)
            if text:
                parts.append(f"【第{ch_no}章正文（该角色首次登场或主要出场）】\n{text[:12000]}")
        if target_chapter_no and target_chapter_no != ch_no:
            outline = _load_outline_text(novel_id, target_chapter_no)
            if outline:
                parts.append(f"【第{target_chapter_no}章细纲（ upcoming ）】\n{outline}")
    return "\n\n".join(parts) if parts else "（无额外上下文）"


def _run_character_deepen(
    novel_id: int,
    novel: dict,
    *,
    name: str,
    mode: str,
    char_id: int | None = None,
    current_card: dict | None = None,
    debut_chapter_no: int | None = None,
    target_chapter_no: int | None = None,
    role_hint: str = "",
    user_hint: str = "",
    create_if_missing: bool = False,
) -> dict:
    agent = CharacterAgent()
    context = _build_deepen_context(
        novel_id, mode=mode, name=name,
        debut_chapter_no=debut_chapter_no,
        target_chapter_no=target_chapter_no,
        role_hint=role_hint,
    )
    raw = agent.deepen_character(
        name=name,
        mode=mode,
        core_seed=novel["core_seed"],
        character_dynamics=novel["character_dynamics"],
        world_building=novel["world_building"],
        global_summary=novel["global_summary"],
        character_state=novel["character_state"],
        current_card=current_card,
        context_block=context,
        user_hint=user_hint,
    )
    if not raw:
        raise ValueError(f"角色「{name}」深化失败：模型未返回有效 JSON")
    cid = apply_deepen_result(
        novel_id,
        char_id=char_id,
        name=name,
        raw=raw,
        first_chapter=debut_chapter_no or target_chapter_no or 0,
        last_chapter=debut_chapter_no or target_chapter_no or 0,
        create_if_missing=create_if_missing,
    )
    return {"id": cid, "name": name, "deepened": True}


def _deepen_new_from_finalize(
    novel_id: int,
    novel: dict,
    char_changes: dict,
    chapter_no: int,
) -> list[str]:
    """定稿后自动深化本章 new 角色。返回已深化名字列表。"""
    done: list[str] = []
    novel = _load_novel(novel_id)
    by_name = {c["name"]: c for c in _load_characters(novel_id)}
    for item in char_changes.get("new") or []:
        name = item["name"]
        char_row = by_name.get(name)
        _run_character_deepen(
            novel_id, novel,
            name=name,
            mode="existing",
            char_id=char_row["id"] if char_row else None,
            current_card=item.get("data") or (char_row or {}).get("data"),
            debut_chapter_no=chapter_no,
            target_chapter_no=chapter_no + 1,
            user_hint="该角色本章首次建档，请补全人设并给出下章互动建议。",
            create_if_missing=char_row is None,
        )
        novel = _load_novel(novel_id)
        done.append(name)
    return done


def _load_factions(novel_id: int) -> tuple[list[dict], list[dict]]:
    with db_session() as session:
        factions = [
            {"id": f.id, "name": f.name, "data": f.data or {},
             "first_chapter": f.first_chapter, "last_chapter": f.last_chapter,
             "status": f.status}
            for f in session.query(Faction).filter_by(novel_id=novel_id).all()
        ]
        relations = [
            {"source": r.source, "target": r.target,
             "relation_type": r.relation_type, "data": r.data or {}}
            for r in session.query(FactionRelation).filter_by(novel_id=novel_id).all()
        ]
        return factions, relations


def _load_lore(novel_id: int) -> list[dict]:
    """仅已确认（入账）设定条目。"""
    return load_confirmed_lore_entries(novel_id)


def _persist_blueprint_node(novel_id: int, node: str, updates: dict) -> None:
    field_map = {
        "expand_story": "full_story",
        "init_compass": "full_story",  # 弱指南针摘要写入 full_story 供旧 UI 展示
        "core_seed": "core_seed",
        "character_dynamics": "character_dynamics",
        "world_building": "world_building",
        "plot_architecture": "plot_architecture",
        "init_character_state": "character_state",
    }
    with db_session() as session:
        novel = session.get(Novel, novel_id)
        if node == "init_compass":
            if updates.get("story_compass"):
                novel.story_compass = updates["story_compass"]
            if "full_story" in updates:
                novel.full_story = updates["full_story"]
        elif node in field_map:
            setattr(novel, field_map[node], updates[field_map[node]
                    if node != "init_character_state" else "character_state"])
        elif node == "initial_outlines":
            for block in updates.get("chapter_outlines", []):
                existing = session.query(ChapterOutline).filter_by(
                    novel_id=novel_id, chapter_no=block["chapter_no"]).first()
                if existing:
                    existing.title = block["title"]
                    existing.content = block["content"]
                    existing.status = "draft"
                else:
                    session.add(ChapterOutline(
                        novel_id=novel_id, chapter_no=block["chapter_no"],
                        title=block["title"], content=block["content"],
                    ))


@router.post("/{novel_id}/blueprint")
async def generate_blueprint(novel_id: int):
    """运行蓝图：种子→角色→世界→第1弧→指南针→状态表→首批细纲。"""
    novel = _load_novel(novel_id)
    if not novel["premise"]:
        raise HTTPException(400, "请先填写故事方向（premise）")

    steps = [{"id": k, "label": v} for k, v in BLUEPRINT_STEPS.items()]
    state = {
        "premise": novel["premise"], "genre": novel["genre"],
        "num_chapters": novel["num_chapters"],
        "words_per_chapter": novel["words_per_chapter"],
        "is_fanfic": bool(novel.get("is_fanfic")),
        "story_compass": novel.get("story_compass") or {},
        "outline_window": int(app_config().get("outline_window", 3)),
        **_novel_guide_kwargs(novel),
    }

    def worker(emit: Callable[[str, dict], None]) -> None:
        try:
            total = len(steps)
            step_i = 0
            for kind, node, updates in iter_blueprint_steps(state):
                label = BLUEPRINT_STEPS.get(node, node)
                if kind == "start":
                    step_i += 1
                    emit("step_start", {
                        "id": node,
                        "label": label,
                        "index": step_i,
                        "total": total,
                    })
                    emit("log", {"message": f"[{step_i}/{total}] 开始：{label}"})
                elif kind == "done":
                    _persist_blueprint_node(novel_id, node, updates or {})
                    emit("step_done", {
                        "id": node,
                        "label": label,
                        "index": step_i,
                        "total": total,
                    })
                    emit("log", {"message": f"[{step_i}/{total}] 完成：{label}"})
            emit("done", {"novel_id": novel_id})
        except Exception as e:  # noqa: BLE001
            logger.exception("蓝图生成失败")
            emit("error", {"message": str(e)})

    return _sse_response(_sse_from_worker(
        preamble=[
            ("steps", {"steps": steps}),
            ("log", {"message": "蓝图流水线已启动，右侧/下方会逐步显示进度；首步扩写故事通常最久"}),
        ],
        worker=worker,
        heartbeat_seconds=8.0,
        heartbeat_message="正在生成蓝图，模型调用中…",
    ))


# ---------------------------------------------------------------- 书籍包装

@router.post("/{novel_id}/meta/generate")
def generate_meta(novel_id: int):
    """PlannerAgent.generate_meta：书籍包装（标题/副标题/引言/简介/风格/视角/标签）。"""
    novel = _load_novel(novel_id)
    if not novel["core_seed"]:
        raise HTTPException(400, "请先生成蓝图（需要核心种子）")

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "meta", "label": "Planner：生成书籍包装信息"}]})
        try:
            meta = PlannerAgent().generate_meta(
                premise=novel["premise"], genre=novel["genre"],
                num_chapters=novel["num_chapters"],
                words_per_chapter=novel["words_per_chapter"],
                core_seed=novel["core_seed"], full_story=novel["full_story"],
            )
            if not meta:
                raise ValueError("Planner（书籍包装）未返回有效 JSON")
            with db_session() as session:
                n = session.get(Novel, novel_id)
                # 用户已自定义标题时不覆盖
                if n.title in ("", "未命名小说") and meta.get("title"):
                    n.title = str(meta["title"])[:200]
                n.subtitle = str(meta.get("subtitle", ""))[:200]
                n.introduction = str(meta.get("introduction", ""))
                n.book_summary = str(meta.get("summary", ""))
                n.writing_style = str(meta.get("writing_style", ""))[:200]
                n.narrative_pov = str(meta.get("narrative_pov", ""))[:50]
                n.era_background = str(meta.get("era_background", ""))[:200]
                n.tags = [str(t) for t in meta.get("tags", [])][:8]
            yield _sse("step_done", {"id": "meta", "label": "书籍包装已生成"})
            yield _sse("done", {"novel_id": novel_id})
        except Exception as e:  # noqa: BLE001
            logger.exception("书籍包装生成失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


# ---------------------------------------------------------------- 分卷规划

@router.post("/{novel_id}/volumes/generate")
def generate_volumes(novel_id: int):
    """滚动分卷：仅规划第 1 卷 + 初始化 Compass（不写死全书各卷）。"""
    novel = _load_novel(novel_id)
    if not novel["plot_architecture"]:
        raise HTTPException(400, "请先生成蓝图")

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "volumes", "label": "Planner：规划首卷与弧结构"},
            {"id": "compass", "label": "Planner：初始化终局指南针"},
        ]})
        try:
            planner = PlannerAgent()
            vol = planner.plan_initial_volume(
                core_seed=novel["core_seed"], full_story=novel["full_story"],
                plot_architecture=novel["plot_architecture"],
                num_chapters=novel["num_chapters"],
                **_novel_guide_kwargs(novel),
            )
            if not vol:
                raise ValueError("Planner（首卷）未返回有效卷结构")
            vol = prepare_volume_for_persist(vol, expand_volume_no=1)
            compass = planner.init_compass(
                core_seed=novel["core_seed"],
                full_story=novel["full_story"],
                plot_architecture=novel["plot_architecture"],
                num_chapters=novel["num_chapters"],
                **_novel_guide_kwargs(novel),
            )
            with db_session() as session:
                session.query(Arc).filter_by(novel_id=novel_id).delete()
                session.query(Volume).filter_by(novel_id=novel_id).delete()
                n = session.get(Novel, novel_id)
                merged_compass = dict(compass or {})
                merged_compass["planning_mode"] = "rolling"
                merged_compass["last_updated_chapter"] = 0
                merged_compass.pop("book_complete", None)
                for key in (
                    "pending_volume_options", "can_complete_book",
                    "complete_book_hint", "proposed_at_volume",
                ):
                    merged_compass.pop(key, None)
                n.story_compass = merged_compass
                arc_count, sk_count = _persist_volume_rows(
                    session, novel_id, dict(vol),
                )
            yield _sse("step_done", {
                "id": "volumes",
                "label": f"已规划首卷（{arc_count} 弧，{sk_count} 骨架待展开）",
                "payload": {"count": 1, "arcs": arc_count, "skeleton": sk_count},
            })
            yield _sse("step_done", {
                "id": "compass",
                "label": "终局指南针已建立" if compass else "指南针跳过",
            })
            yield _sse("done", {"novel_id": novel_id, "volume_no": 1})
        except Exception as e:  # noqa: BLE001
            logger.exception("首卷规划失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


@router.post("/{novel_id}/arcs/expand")
def expand_arc(novel_id: int, payload: ExpandArcRequest):
    """展开骨架弧：分配章范围并生成该弧全部细纲（对齐 ainovel expand_arc）。"""
    novel = _load_novel(novel_id)
    if not novel["plot_architecture"]:
        raise HTTPException(400, "请先生成蓝图并分卷")

    volumes = _load_volumes(novel_id)
    found = find_skeleton_arc(volumes, payload.volume_no, payload.arc_no)
    if not found:
        raise HTTPException(400, f"第{payload.volume_no}卷第{payload.arc_no}弧不是可展开的 skeleton 弧")
    vol, arc = found
    start_no, end_no = allocate_skeleton_arc(vol, arc)

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "expand", "label": f"Planner：展开第{payload.volume_no}卷第{payload.arc_no}弧"},
            {"id": "plan", "label": f"ChapterPlanner：生成第{start_no}-{end_no}章细纲"},
        ]})
        try:
            with db_session() as session:
                row = session.get(Arc, arc["id"])
                row.start_chapter = start_no
                row.end_chapter = end_no
                row.estimated_chapters = end_no - start_no + 1
                row.status = "expanded"
            with db_session() as session:
                outlines = session.query(ChapterOutline).filter_by(
                    novel_id=novel_id).order_by(ChapterOutline.chapter_no).all()
                existing_text = "\n\n".join(o.content for o in outlines[-6:])
            yield _sse("step_done", {
                "id": "expand",
                "label": f"已展开：第{start_no}-{end_no}章",
                "payload": {"start_no": start_no, "end_no": end_no},
            })
            blocks = _outline_plan_blocks(
                novel_id, novel, start_no, end_no, existing_text,
                expand_arc={
                    "volume_no": payload.volume_no,
                    "arc_no": payload.arc_no,
                    "title": arc["title"],
                    "goal": arc["goal"],
                    "estimated_chapters": arc.get("estimated_chapters") or (end_no - start_no + 1),
                },
            )
            with db_session() as session:
                for block in blocks:
                    existing = session.query(ChapterOutline).filter_by(
                        novel_id=novel_id, chapter_no=block["chapter_no"]).first()
                    if existing:
                        existing.title = block["title"]
                        existing.content = block["content"]
                    else:
                        session.add(ChapterOutline(
                            novel_id=novel_id, chapter_no=block["chapter_no"],
                            title=block["title"], content=block["content"],
                        ))
            yield _sse("step_done", {
                "id": "plan",
                "label": f"已生成 {len(blocks)} 章细纲",
                "payload": {"count": len(blocks)},
            })
            yield _sse("done", {
                "volume_no": payload.volume_no,
                "arc_no": payload.arc_no,
                "start_no": start_no,
                "end_no": end_no,
            })
        except Exception as e:  # noqa: BLE001
            logger.exception("展开弧失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


@router.post("/{novel_id}/volumes/propose-next")
def propose_next_volume(novel_id: int, payload: ProposeNextVolumeRequest):
    """卷末（或手动）：生成 2–4 个下一卷方向，写入 story_compass.pending_volume_options。"""
    novel = _load_novel(novel_id)
    if is_book_complete(novel.get("story_compass")):
        raise HTTPException(400, "全书已完结")
    volumes = _load_volumes(novel_id)
    if not volumes:
        raise HTTPException(400, "请先生成首卷规划")
    try:
        return _run_propose_next_volume(
            novel_id, novel, volumes,
            volume_no=payload.volume_no,
            user_hint=payload.user_hint,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/{novel_id}/volumes/append")
def append_volume(novel_id: int, payload: AppendVolumeRequest):
    """选定方向追加新卷，并展开该卷第 1 弧细纲。"""
    novel = _load_novel(novel_id)
    if is_book_complete(novel.get("story_compass")):
        raise HTTPException(400, "全书已完结，无法追加卷")
    if not novel["plot_architecture"]:
        raise HTTPException(400, "请先生成蓝图")

    compass = novel.get("story_compass") or {}
    options = compass.get("pending_volume_options") or []
    option = next((o for o in options if str(o.get("id")) == payload.option_id), None)
    if not option:
        raise HTTPException(400, f"未找到方向选项 id={payload.option_id}，请先「生成下一卷方向」")

    volumes = _load_volumes(novel_id)
    last = last_volume(volumes)
    if not last:
        raise HTTPException(400, "请先生成首卷规划")
    vol_no = int(last["volume_no"]) + 1
    start_ch = int(last["end_chapter"]) + 1
    vol_dict = option_to_volume_dict(option, volume_no=vol_no, start_chapter=start_ch)
    vol_dict = prepare_volume_for_persist(vol_dict, expand_volume_no=vol_no)

    first_arc = next((a for a in vol_dict.get("arcs") or [] if a.get("status") == "expanded"), None)
    start_no = int(first_arc["start_chapter"]) if first_arc else start_ch
    end_no = int(first_arc["end_chapter"]) if first_arc else start_ch

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "append", "label": f"Planner：追加第{vol_no}卷《{vol_dict.get('title', '')}》"},
            {"id": "compass", "label": "Planner：校准终局指南针"},
            {"id": "plan", "label": f"ChapterPlanner：生成第{start_no}-{end_no}章细纲"},
        ]})
        try:
            with db_session() as session:
                _persist_volume_rows(session, novel_id, vol_dict)
                if (not is_scale_open(novel["num_chapters"])
                        and vol_dict["end_chapter"] > novel["num_chapters"]):
                    n = session.get(Novel, novel_id)
                    n.num_chapters = int(vol_dict["end_chapter"])
                _clear_volume_proposals(session, novel_id)
            yield _sse("step_done", {
                "id": "append",
                "label": f"已追加第{vol_no}卷（第{start_ch}-{vol_dict['end_chapter']}章）",
                "payload": {"volume_no": vol_no, "start_chapter": start_ch, "end_chapter": vol_dict["end_chapter"]},
            })
            if payload.user_hint.strip():
                novel_fresh = _load_novel(novel_id)
                volumes_fresh = _load_volumes(novel_id)
                refreshed = PlannerAgent().refresh_compass(
                    current_compass=novel_fresh.get("story_compass") or {},
                    global_summary=novel_fresh["global_summary"],
                    volume_summaries=format_volume_summaries(volumes_fresh),
                    user_hint=payload.user_hint,
                )
                if refreshed:
                    with db_session() as session:
                        n = session.get(Novel, novel_id)
                        merged = dict(n.story_compass or {})
                        merged.update(refreshed)
                        merged["planning_mode"] = "rolling"
                        n.story_compass = merged
            yield _sse("step_done", {"id": "compass", "label": "指南针已校准"})
            with db_session() as session:
                outlines = session.query(ChapterOutline).filter_by(
                    novel_id=novel_id).order_by(ChapterOutline.chapter_no).all()
                existing_text = "\n\n".join(o.content for o in outlines[-6:])
            novel_now = _load_novel(novel_id)
            blocks = _outline_plan_blocks(
                novel_id, novel_now, start_no, end_no, existing_text,
                expand_arc={
                    "volume_no": vol_no,
                    "arc_no": int(first_arc["arc_no"]) if first_arc else 1,
                    "title": str(first_arc.get("title", "") if first_arc else vol_dict.get("title", "")),
                    "goal": str(first_arc.get("goal", "") if first_arc else vol_dict.get("theme", "")),
                    "estimated_chapters": int(first_arc.get("estimated_chapters") or (end_no - start_no + 1)) if first_arc else (end_no - start_no + 1),
                },
            )
            with db_session() as session:
                for block in blocks:
                    existing = session.query(ChapterOutline).filter_by(
                        novel_id=novel_id, chapter_no=block["chapter_no"]).first()
                    if existing:
                        existing.title = block["title"]
                        existing.content = block["content"]
                    else:
                        session.add(ChapterOutline(
                            novel_id=novel_id, chapter_no=block["chapter_no"],
                            title=block["title"], content=block["content"],
                        ))
            yield _sse("step_done", {
                "id": "plan",
                "label": f"已生成第 1 弧 {len(blocks)} 章细纲",
                "payload": {"count": len(blocks)},
            })
            yield _sse("done", {"volume_no": vol_no, "start_no": start_no, "end_no": end_no})
        except Exception as e:  # noqa: BLE001
            logger.exception("追加卷失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


@router.post("/{novel_id}/volumes/{volume_no}/replan-skeleton")
def replan_skeleton_arcs(novel_id: int, volume_no: int, payload: ReplanSkeletonArcsRequest):
    """重规划卷内尚未展开的 skeleton 弧（不动已 expanded/finished 弧）。"""
    novel = _load_novel(novel_id)
    volumes = _load_volumes(novel_id)
    vol = next((v for v in volumes if v["volume_no"] == volume_no), None)
    if not vol:
        raise HTTPException(404, "卷不存在")
    if not any(a.get("status") == "skeleton" for a in vol.get("arcs") or []):
        raise HTTPException(400, "本卷没有可重规划的 skeleton 弧")

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "replan", "label": f"Planner：重规划第{volume_no}卷 skeleton 弧"},
        ]})
        try:
            new_arcs = PlannerAgent().replan_skeleton_arcs(
                story_compass=novel.get("story_compass") or {},
                global_summary=novel["global_summary"],
                volume=vol,
                locked_arcs=locked_arcs_text(vol),
                current_skeleton_arcs=skeleton_arcs_text(vol),
                user_hint=payload.user_hint,
            )
            if not new_arcs:
                raise ValueError("Planner 未返回有效 skeleton 弧")
            with db_session() as session:
                vol_row = session.query(Volume).filter_by(
                    novel_id=novel_id, volume_no=volume_no).first()
                session.query(Arc).filter(
                    Arc.volume_id == vol_row.id,
                    Arc.status == "skeleton",
                ).delete(synchronize_session=False)
                for a in new_arcs:
                    session.add(Arc(
                        novel_id=novel_id,
                        volume_id=vol_row.id,
                        status="skeleton",
                        arc_no=int(a["arc_no"]),
                        title=str(a.get("title", "")),
                        goal=str(a.get("goal", "")),
                        start_chapter=0,
                        end_chapter=0,
                        estimated_chapters=int(a.get("estimated_chapters") or 5),
                    ))
            yield _sse("step_done", {
                "id": "replan",
                "label": f"已替换为 {len(new_arcs)} 条 skeleton 弧",
                "payload": {"count": len(new_arcs)},
            })
            yield _sse("done", {"volume_no": volume_no})
        except Exception as e:  # noqa: BLE001
            logger.exception("重规划 skeleton 弧失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


@router.post("/{novel_id}/compass/refresh")
def refresh_compass(novel_id: int, payload: UserHintRequest):
    """手动刷新终局指南针（作者改主意时）。"""
    novel = _load_novel(novel_id)
    volumes = _load_volumes(novel_id)

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "compass", "label": "Planner：刷新终局指南针"},
        ]})
        try:
            refreshed = PlannerAgent().refresh_compass(
                current_compass=novel.get("story_compass") or {},
                global_summary=novel["global_summary"],
                volume_summaries=format_volume_summaries(volumes),
                user_hint=payload.user_hint,
            )
            if not refreshed:
                raise ValueError("Planner 未返回有效指南针")
            with db_session() as session:
                n = session.get(Novel, novel_id)
                merged = dict(n.story_compass or {})
                merged.update(refreshed)
                merged["planning_mode"] = merged.get("planning_mode") or "rolling"
                n.story_compass = merged
            yield _sse("step_done", {"id": "compass", "label": "终局指南针已刷新"})
            yield _sse("done", {"novel_id": novel_id})
        except Exception as e:  # noqa: BLE001
            logger.exception("刷新指南针失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


@router.post("/{novel_id}/book/complete")
def complete_book(novel_id: int, payload: UserHintRequest):
    """标记全书完结（对齐 ainovel complete_book）。"""
    _load_novel(novel_id)  # 404 守卫
    volumes = _load_volumes(novel_id)
    last = last_volume(volumes)
    with db_session() as session:
        finalized = session.query(Chapter).filter_by(
            novel_id=novel_id, status="finalized",
        ).count()
    if last and finalized < last["end_chapter"]:
        raise HTTPException(
            400,
            f"尚有章节未定稿（已写定稿 {finalized} 章，当前规划到第 {last['end_chapter']} 章）",
        )

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "complete", "label": "标记全书完结"},
        ]})
        try:
            with db_session() as session:
                n = session.get(Novel, novel_id)
                compass = dict(n.story_compass or {})
                compass["book_complete"] = True
                compass["completed_at_chapter"] = finalized
                if payload.user_hint.strip():
                    compass["complete_note"] = payload.user_hint.strip()
                for key in (
                    "pending_volume_options", "can_complete_book",
                    "complete_book_hint", "proposed_at_volume",
                ):
                    compass.pop(key, None)
                n.story_compass = compass
            yield _sse("step_done", {"id": "complete", "label": "全书已标记完结"})
            yield _sse("done", {"novel_id": novel_id, "finalized_chapters": finalized})
        except Exception as e:  # noqa: BLE001
            logger.exception("标记完结失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


# ---------------------------------------------------------------- 阵营设计

@router.post("/{novel_id}/factions/generate")
def generate_factions(novel_id: int):
    """WorldKeeperAgent.seed_factions：从蓝图识别 0-2 个开篇核心阵营。"""
    novel = _load_novel(novel_id)
    if not novel["core_seed"]:
        raise HTTPException(400, "请先生成蓝图")

    existing_factions, _ = _load_factions(novel_id)
    existing_names = [f["name"] for f in existing_factions]

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "factions", "label": "WorldKeeper：识别开篇核心阵营"}]})
        try:
            result = WorldKeeperAgent().seed_factions(
                world_building=novel["world_building"],
                core_seed=novel["core_seed"],
                existing_names=existing_names,
            )
            factions = result["core_factions"]
            relations = result["faction_relations"]
            added_f, added_r = 0, 0
            known = set(existing_names)
            with db_session() as session:
                for f in factions:
                    if not isinstance(f, dict):
                        continue
                    name = str(f.pop("name", "")).strip()
                    if not name or name in known:
                        continue
                    session.add(Faction(
                        novel_id=novel_id, name=name, data=f,
                        first_chapter=0, last_chapter=0, status="active"))
                    known.add(name)
                    added_f += 1
                for r in relations:
                    if not isinstance(r, dict):
                        continue
                    source = str(r.pop("source_faction_name", "")).strip()
                    target = str(r.pop("target_faction_name", "")).strip()
                    rel_type = str(r.pop("relation_type", "")).strip()
                    if not (source and target):
                        continue
                    session.add(FactionRelation(
                        novel_id=novel_id, source=source, target=target,
                        relation_type=rel_type, data=r,
                    ))
                    added_r += 1
            label = (f"新增 {added_f} 个开篇阵营、{added_r} 组关系"
                     if added_f or added_r else "未识别到需建档的开篇阵营")
            yield _sse("step_done", {"id": "factions", "label": label})
            yield _sse("done", {"novel_id": novel_id})
        except Exception as e:  # noqa: BLE001
            logger.exception("开篇阵营识别失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


# ---------------------------------------------------------------- 设定库

@router.post("/{novel_id}/lore/generate")
def generate_lore(novel_id: int):
    """WorldKeeperAgent.extract_initial_lore：把蓝图整理为条目化世界书。"""
    novel = _load_novel(novel_id)
    if not novel["world_building"]:
        raise HTTPException(400, "请先生成蓝图")

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "lore", "label": "WorldKeeper：整理世界书条目"}]})
        try:
            entries = WorldKeeperAgent().extract_initial_lore(
                world_building=novel["world_building"],
                full_story=novel["full_story"],
                plot_architecture=novel["plot_architecture"],
            )
            if not entries:
                raise ValueError("WorldKeeper（世界书）未返回有效条目")
            with db_session() as session:
                session.query(LoreEntry).filter_by(novel_id=novel_id).delete()
                for e in entries:
                    session.add(LoreEntry(novel_id=novel_id, **e))
            yield _sse("step_done", {
                "id": "lore", "label": f"已整理 {len(entries)} 个设定条目"})
            yield _sse("done", {"novel_id": novel_id, "count": len(entries)})
        except Exception as e:  # noqa: BLE001
            logger.exception("设定库生成失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


# ---------------------------------------------------------------- 滚动细纲

@router.post("/{novel_id}/outlines/next")
def generate_next_outlines(novel_id: int):
    """生成接下来 N 章细纲（N 由 config.app.outline_window 决定）。"""
    novel = _load_novel(novel_id)
    if not novel["plot_architecture"]:
        raise HTTPException(400, "请先生成蓝图")

    window = int(app_config().get("outline_window", 3))
    with db_session() as session:
        outlines = session.query(ChapterOutline).filter_by(
            novel_id=novel_id).order_by(ChapterOutline.chapter_no).all()
        existing_text = "\n\n".join(o.content for o in outlines[-6:])
        start_no = (outlines[-1].chapter_no + 1) if outlines else 1

    volumes = _load_volumes(novel_id)
    _guard_chapter_planning(novel_id, novel, start_no)
    last = last_volume(volumes)
    plan_cap = int(last["end_chapter"]) if last else chapter_cap(novel["num_chapters"])
    end_no = min(start_no + window - 1, plan_cap, chapter_cap(novel["num_chapters"]))
    if start_no > plan_cap:
        raise HTTPException(
            400,
            chapter_beyond_planned(volumes, start_no)["message"]
            if chapter_beyond_planned(volumes, start_no)
            else "已超过当前规划范围",
        )

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "plan", "label": f"ChapterPlanner：生成第{start_no}-{end_no}章细纲"}]})
        try:
            blocks = _outline_plan_blocks(
                novel_id, novel, start_no, end_no, existing_text,
            )
            with db_session() as session:
                for block in blocks:
                    session.add(ChapterOutline(
                        novel_id=novel_id, chapter_no=block["chapter_no"],
                        title=block["title"], content=block["content"],
                    ))
            yield _sse("step_done", {"id": "plan", "label": "细纲生成完成",
                                     "payload": {"count": len(blocks)}})
            yield _sse("done", {"start_no": start_no, "end_no": end_no})
        except Exception as e:  # noqa: BLE001
            logger.exception("细纲生成失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


# ---------------------------------------------------------------- 章节写作

@router.post("/{novel_id}/chapters/{chapter_no}/write")
def write_chapter(novel_id: int, chapter_no: int, payload: WriteChapterRequest):
    """运行章节流水线（同步 SSE 版）：Writer 写稿 → Reviewer 审校 → 质量门。

    上下文组装/裁剪与落库逻辑复用 services.write_chapter；
    后台任务版见 POST .../write_job（支持断点恢复）。
    """
    from backend.services.write_chapter import (
        _persist_chapter,
        _step_payload,
        prepare_write_state,
    )
    from backend.context.budget import budget_log_message

    state = prepare_write_state(novel_id, chapter_no, payload.user_guidance)

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": k, "label": v} for k, v in CHAPTER_STEPS.items()]})
        try:
            report = state.pop("_context_budget", None)
            if report:
                yield _sse("log", {"message": budget_log_message(report)})
            graph = build_chapter_graph()
            merged = dict(state)
            for event in graph.stream(state, stream_mode="updates"):
                for node, updates in event.items():
                    merged.update(updates or {})
                    yield _sse("step_done", {
                        "id": node,
                        "label": CHAPTER_STEPS.get(node, node),
                        "payload": _step_payload(node, merged),
                    })
            _persist_chapter(merged)
            yield _sse("done", {
                "chapter_no": chapter_no,
                "review": merged.get("review") or {},
                "health": merged.get("health_report") or {},
                "readiness": merged.get("readiness_report") or {},
                "quality_decision": merged.get("quality_decision") or {},
            })
        except Exception as e:  # noqa: BLE001
            logger.exception("章节生成失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


# ---------------------------------------------------------------- 定稿

@router.post("/{novel_id}/chapters/{chapter_no}/finalize")
def finalize_chapter(novel_id: int, chapter_no: int):
    """定稿（同步 SSE 版）：更新摘要/角色状态/各台账，章节标记为 finalized。

    步骤实现复用 services.finalize_chapter（与后台任务版同一套函数）；
    后台任务版见 POST .../finalize_job（支持断点恢复）。
    """
    from backend.services.finalize_chapter import (
        FINALIZE_STEPS,
        FinalizeBlocked,
        _Ctx,
        _STEP_FUNCS,
    )

    _load_novel(novel_id)
    with db_session() as session:
        chapter = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if not chapter or not chapter.content:
            raise HTTPException(400, "章节不存在或内容为空")
        chapter_text = chapter.content
        ol = session.query(ChapterOutline).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        outline_text = ol.content if ol else ""

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": FINALIZE_STEPS})
        buffer: list[tuple[str, dict]] = []
        fctx = _Ctx(
            novel_id=novel_id, chapter_no=chapter_no,
            chapter_text=chapter_text, outline_text=outline_text,
            emit=lambda event, data=None: buffer.append((event, data or {})),
        )

        def flush():
            while buffer:
                event, data = buffer.pop(0)
                yield _sse(event, data)

        try:
            for _step_id, fn in _STEP_FUNCS:
                fn(fctx)
                yield from flush()
            yield _sse("done", {"chapter_no": chapter_no})
        except FinalizeBlocked as e:
            yield from flush()
            yield _sse("error", {"message": str(e)})
        except Exception as e:  # noqa: BLE001
            logger.exception("定稿失败")
            yield from flush()
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


# ---------------------------------------------------------------- 风格学习

@router.post("/{novel_id}/style/learn")
def learn_style(novel_id: int, payload: StyleLearnRequest):
    """StyleLearner：从参考书节选提炼风格指南，写入 novel.style_guide。"""
    with db_session() as session:
        if not session.get(Novel, novel_id):
            raise HTTPException(404, "小说不存在")

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "style_learn", "label": "StyleLearner：分析参考书风格"}]})
        try:
            guide = StyleLearnerAgent().learn(payload.reference_text)
            with db_session() as session:
                session.get(Novel, novel_id).style_guide = guide
            yield _sse("step_done", {
                "id": "style_learn",
                "label": f"风格指南已生成（{len(guide)} 字）",
                "payload": {"style_guide": guide},
            })
            yield _sse("done", {"style_guide": guide})
        except Exception as e:  # noqa: BLE001
            logger.exception("风格学习失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


# ---------------------------------------------------------------- 章节健康检查

@router.post("/{novel_id}/chapters/{chapter_no}/health_check")
def chapter_health_check(novel_id: int, chapter_no: int):
    """规则化健康检查（零 LLM）：模板词、引号、Humanizer 模式等。"""
    novel = _load_novel(novel_id)
    with db_session() as session:
        chapter = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if not chapter or not chapter.content:
            raise HTTPException(400, "章节不存在或内容为空")
        report = check_chapter_health(
            chapter.content, chapter_no=chapter_no,
            target_words=novel["words_per_chapter"],
        )
        chapter.health_report = json.dumps(report, ensure_ascii=False)
    return report


# ---------------------------------------------------------------- 润色

@router.post("/{novel_id}/chapters/{chapter_no}/polish")
def polish_chapter(novel_id: int, chapter_no: int, payload: PolishRequest):
    """Editor Agent：润色章节正文（对话/感官/节奏，不改剧情事实）。"""
    novel = _load_novel(novel_id)
    with db_session() as session:
        chapter = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if not chapter or not chapter.content:
            raise HTTPException(400, "章节不存在或内容为空")
        original = chapter.content

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "polish", "label": f"Editor：润色第{chapter_no}章正文"}]})
        try:
            polished = EditorAgent().polish(
                chapter_text=original,
                writing_style=novel["writing_style"],
                narrative_pov=novel["narrative_pov"],
                instruction=payload.instruction,
                style_guide=novel["style_guide"],
            )
            with db_session() as session:
                session.add(RevisionLog(
                    novel_id=novel_id, target_type="chapter",
                    target_key=str(chapter_no),
                    instruction=f"（润色）{payload.instruction}".strip(),
                    old_content=original,
                ))
                c = session.query(Chapter).filter_by(
                    novel_id=novel_id, chapter_no=chapter_no).first()
                c.content = polished
                c.status = "edited"
            yield _sse("step_done", {"id": "polish", "label": "润色完成"})
            yield _sse("done", {"chapter_no": chapter_no})
        except Exception as e:  # noqa: BLE001
            logger.exception("润色失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


# ---------------------------------------------------------------- 去 AI 味

@router.post("/{novel_id}/chapters/{chapter_no}/humanize")
def humanize_chapter(novel_id: int, chapter_no: int, payload: PolishRequest):
    """Editor Agent：按 ainovel-cli 去 AI 味判据改写正文。"""
    novel = _load_novel(novel_id)
    with db_session() as session:
        chapter = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if not chapter or not chapter.content:
            raise HTTPException(400, "章节不存在或内容为空")
        original = chapter.content

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "humanize", "label": f"Editor：去 AI 味改写第{chapter_no}章"}]})
        try:
            revised = EditorAgent().humanize(
                chapter_text=original,
                writing_style=novel["writing_style"],
                narrative_pov=novel["narrative_pov"],
                instruction=payload.instruction,
                style_guide=novel["style_guide"],
            )
            with db_session() as session:
                session.add(RevisionLog(
                    novel_id=novel_id, target_type="chapter",
                    target_key=str(chapter_no),
                    instruction=f"（去AI味）{payload.instruction}".strip(),
                    old_content=original,
                ))
                c = session.query(Chapter).filter_by(
                    novel_id=novel_id, chapter_no=chapter_no).first()
                c.content = revised
                c.status = "edited"
            yield _sse("step_done", {"id": "humanize", "label": "去 AI 味改写完成"})
            yield _sse("done", {"chapter_no": chapter_no})
        except Exception as e:  # noqa: BLE001
            logger.exception("去 AI 味改写失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


def _find_segment(chapter_text: str, selected: str) -> tuple[int, str]:
    """在正文中定位选中片段，返回 (起始索引, 实际匹配文本)。"""
    needle = selected.strip()
    if len(needle) < 8:
        raise HTTPException(400, "选中片段过短，请至少选择 8 个字符")
    idx = chapter_text.find(needle)
    if idx >= 0:
        return idx, needle
    raise HTTPException(
        400, "选中的片段在正文中未找到（正文可能已变更），请重新展开章节并拖选")


def _load_segment_job(novel_id: int, chapter_no: int, selected_text: str) -> dict:
    """加载片段编辑所需的章节上下文与定位信息。"""
    novel = _load_novel(novel_id)
    with db_session() as session:
        chapter = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if not chapter or not chapter.content:
            raise HTTPException(400, "章节不存在或内容为空")
        chapter_text = chapter.content
        idx, matched = _find_segment(chapter_text, selected_text)
        if chapter_text.count(matched) > 1:
            logger.warning("选中片段在正文中出现多次，将替换首次出现位置")
        outline = session.query(ChapterOutline).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        outline_text = outline.content if outline else "（无）"

    context_before = chapter_text[max(0, idx - 400):idx]
    context_after = chapter_text[idx + len(matched):idx + len(matched) + 400]
    context = (
        f"本章细纲：\n{outline_text}\n"
        f"前文摘要：\n{novel['global_summary'] or '（无）'}\n"
        f"角色状态：\n{novel['character_state'] or '（无）'}\n"
        f"世界观要点：\n{novel['world_building'][:800] or '（无）'}"
    )
    target_key = f"{chapter_no}:segment"
    with db_session() as session:
        logs = (session.query(RevisionLog)
                .filter_by(novel_id=novel_id, target_type="chapter_segment",
                           target_key=target_key)
                .filter(RevisionLog.instruction != "")
                .order_by(RevisionLog.id.desc()).limit(5).all())
        history = "\n".join(
            f"{i}. {log.instruction}"
            for i, log in enumerate(reversed(logs), start=1)
        ) or "（首次修改）"

    return {
        "novel": novel,
        "chapter_text": chapter_text,
        "idx": idx,
        "matched": matched,
        "context": context,
        "context_before": context_before,
        "context_after": context_after,
        "history": history,
        "target_key": target_key,
    }


def _apply_segment_replace(
    *, novel_id: int, chapter_no: int, chapter_text: str,
    idx: int, matched: str, new_segment: str,
    target_key: str, instruction: str,
) -> str:
    if not new_segment.strip():
        raise ValueError("模型未返回有效片段")
    new_content = (
        chapter_text[:idx] + new_segment.strip() + chapter_text[idx + len(matched):]
    )
    with db_session() as session:
        session.add(RevisionLog(
            novel_id=novel_id, target_type="chapter_segment",
            target_key=target_key,
            instruction=instruction,
            old_content=matched,
        ))
        c = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        c.content = new_content
        c.status = "edited"
    return new_content


# ---------------------------------------------------------------- 片段重写 / 润色 / 去 AI 味

@router.post("/{novel_id}/chapters/{chapter_no}/revise_segment")
def revise_segment(novel_id: int, chapter_no: int, payload: SegmentReviseRequest):
    """Revision Agent：只重写用户选中的正文片段，自动拼回章节。"""
    job = _load_segment_job(novel_id, chapter_no, payload.selected_text)
    novel, matched = job["novel"], job["matched"]

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "revise_segment",
             "label": f"Revision：重写第{chapter_no}章选中片段（{len(matched)}字）"}]})
        try:
            new_segment = RevisionAgent().revise_segment(
                selected_text=matched,
                instruction=payload.instruction,
                context=job["context"],
                context_before=job["context_before"],
                context_after=job["context_after"],
                writing_style=novel["writing_style"],
                narrative_pov=novel["narrative_pov"],
                history=job["history"],
                style_guide=novel["style_guide"],
            )
            _apply_segment_replace(
                novel_id=novel_id, chapter_no=chapter_no,
                chapter_text=job["chapter_text"], idx=job["idx"],
                matched=matched, new_segment=new_segment,
                target_key=job["target_key"],
                instruction=payload.instruction,
            )
            yield _sse("step_done", {
                "id": "revise_segment",
                "label": f"片段已重写并拼回（{len(new_segment.strip())}字）",
            })
            yield _sse("done", {"chapter_no": chapter_no})
        except Exception as e:  # noqa: BLE001
            logger.exception("片段重写失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


@router.post("/{novel_id}/chapters/{chapter_no}/polish_segment")
def polish_segment(novel_id: int, chapter_no: int, payload: SegmentEditRequest):
    """Editor Agent：只润色用户选中的正文片段。"""
    job = _load_segment_job(novel_id, chapter_no, payload.selected_text)
    novel, matched = job["novel"], job["matched"]
    log_instruction = f"（片段润色）{payload.instruction}".strip()

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "polish_segment",
             "label": f"Editor：润色第{chapter_no}章选中片段（{len(matched)}字）"}]})
        try:
            new_segment = EditorAgent().polish_segment(
                selected_text=matched,
                instruction=payload.instruction,
                context=job["context"],
                context_before=job["context_before"],
                context_after=job["context_after"],
                writing_style=novel["writing_style"],
                narrative_pov=novel["narrative_pov"],
                style_guide=novel["style_guide"],
            )
            _apply_segment_replace(
                novel_id=novel_id, chapter_no=chapter_no,
                chapter_text=job["chapter_text"], idx=job["idx"],
                matched=matched, new_segment=new_segment,
                target_key=job["target_key"],
                instruction=log_instruction or "（片段润色）",
            )
            yield _sse("step_done", {
                "id": "polish_segment",
                "label": f"片段已润色并拼回（{len(new_segment.strip())}字）",
            })
            yield _sse("done", {"chapter_no": chapter_no})
        except Exception as e:  # noqa: BLE001
            logger.exception("片段润色失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


@router.post("/{novel_id}/chapters/{chapter_no}/humanize_segment")
def humanize_segment(novel_id: int, chapter_no: int, payload: SegmentEditRequest):
    """Editor Agent：只对选中片段做去 AI 味改写（针对 AIGC 检测标红段落）。"""
    job = _load_segment_job(novel_id, chapter_no, payload.selected_text)
    novel, matched = job["novel"], job["matched"]
    log_instruction = f"（片段去AI味）{payload.instruction}".strip()

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "humanize_segment",
             "label": f"Editor：去 AI 味改写第{chapter_no}章选中片段（{len(matched)}字）"}]})
        try:
            new_segment = EditorAgent().humanize_segment(
                selected_text=matched,
                instruction=payload.instruction,
                context=job["context"],
                context_before=job["context_before"],
                context_after=job["context_after"],
                writing_style=novel["writing_style"],
                narrative_pov=novel["narrative_pov"],
                style_guide=novel["style_guide"],
            )
            _apply_segment_replace(
                novel_id=novel_id, chapter_no=chapter_no,
                chapter_text=job["chapter_text"], idx=job["idx"],
                matched=matched, new_segment=new_segment,
                target_key=job["target_key"],
                instruction=log_instruction or "（片段去AI味）",
            )
            yield _sse("step_done", {
                "id": "humanize_segment",
                "label": f"片段已去 AI 味并拼回（{len(new_segment.strip())}字）",
            })
            yield _sse("done", {"chapter_no": chapter_no})
        except Exception as e:  # noqa: BLE001
            logger.exception("片段去 AI 味失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


# ---------------------------------------------------------------- 质量评审

@router.post("/{novel_id}/chapters/{chapter_no}/critique")
def critique_chapter(novel_id: int, chapter_no: int):
    """ReviewerAgent.review_chapter：整章质量评审（一致性 + 文学质量）。"""
    novel = _load_novel(novel_id)
    with db_session() as session:
        chapter = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if not chapter or not chapter.content:
            raise HTTPException(400, "章节不存在或内容为空")
        chapter_text = chapter.content
        outline = session.query(ChapterOutline).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        outline_text = outline.content if outline else ""

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "critique", "label": f"Reviewer：评审第{chapter_no}章成稿"}]})
        try:
            report = ReviewerAgent().review_chapter(
                chapter_no=chapter_no, chapter_text=chapter_text,
                chapter_outline=outline_text,
                character_state=novel["character_state"],
                world_building=novel["world_building"],
                genre=novel["genre"],
                writing_style=novel["writing_style"],
                narrative_pov=novel["narrative_pov"],
                words_per_chapter=novel["words_per_chapter"],
                user_guidance="",
                **_novel_guide_kwargs(novel),
            )
            if not report:
                raise ValueError("Reviewer 未返回有效评审报告")
            with db_session() as session:
                c = session.query(Chapter).filter_by(
                    novel_id=novel_id, chapter_no=chapter_no).first()
                c.critique = json.dumps(report, ensure_ascii=False)
            verdict_label = ("达到出稿标准" if report["verdict"] == "pass"
                             else f"需要修改（{len(report['issues'])}个问题）")
            yield _sse("step_done", {
                "id": "critique",
                "label": f"评审完成：{report['overall']}分，{verdict_label}",
                "payload": {"critique": report},
            })
            yield _sse("done", {"chapter_no": chapter_no, "critique": report})
        except Exception as e:  # noqa: BLE001
            logger.exception("评审失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


@router.post("/{novel_id}/chapters/{chapter_no}/revise_by_critique")
def revise_by_critique(novel_id: int, chapter_no: int):
    """按最近一次评审报告中的问题清单修订章节正文。"""
    novel = _load_novel(novel_id)
    with db_session() as session:
        chapter = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if not chapter or not chapter.content:
            raise HTTPException(400, "章节不存在或内容为空")
        try:
            report = json.loads(chapter.critique or "{}")
        except json.JSONDecodeError:
            report = {}
        issues = report.get("issues") or []
        if not issues:
            raise HTTPException(400, "评审报告中没有待解决的问题，请先运行评审")
        original = chapter.content
        outline = session.query(ChapterOutline).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        outline_text = outline.content if outline else "（无）"

    def gen() -> Iterator[str]:
        yield _sse("steps", {"steps": [
            {"id": "revise", "label": f"Revision：按{len(issues)}条评审意见修订第{chapter_no}章"}]})
        try:
            revised = RevisionAgent().revise_by_issues(
                issues=issues,
                character_state=novel["character_state"],
                global_summary=novel["global_summary"],
                chapter_outline=outline_text,
                chapter_text=original,
            )
            with db_session() as session:
                session.add(RevisionLog(
                    novel_id=novel_id, target_type="chapter",
                    target_key=str(chapter_no),
                    instruction=f"（按评审意见修订，共{len(issues)}条）",
                    old_content=original,
                ))
                c = session.query(Chapter).filter_by(
                    novel_id=novel_id, chapter_no=chapter_no).first()
                c.content = revised
                c.status = "edited"
                report["applied"] = True  # 标记本报告的问题已处理
                c.critique = json.dumps(report, ensure_ascii=False)
            yield _sse("step_done", {"id": "revise", "label": "修订完成（建议再次评审确认）"})
            yield _sse("done", {"chapter_no": chapter_no})
        except Exception as e:  # noqa: BLE001
            logger.exception("按评审意见修订失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


# ---------------------------------------------------------------- AI 修订

BLUEPRINT_REVISE_FIELDS = {
    "full_story", "core_seed", "world_building", "plot_architecture",
    "character_dynamics",
}


@router.post("/{novel_id}/revise")
def revise(novel_id: int, payload: ReviseRequest):
    """按用户指令修订：蓝图字段 / 章节细纲 / 章节正文。"""
    novel = _load_novel(novel_id)
    target = payload.target_type

    if target in BLUEPRINT_REVISE_FIELDS:
        original = novel[target]
        context = (
            f"故事方向：{novel['premise']}\n核心种子：{novel['core_seed']}\n"
            f"类型：{novel['genre']}"
        )
        target_key = target
    elif target == "chapter_outline":
        if payload.chapter_no is None:
            raise HTTPException(400, "缺少 chapter_no")
        with db_session() as session:
            outline = session.query(ChapterOutline).filter_by(
                novel_id=novel_id, chapter_no=payload.chapter_no).first()
            if not outline:
                raise HTTPException(404, "细纲不存在")
            original = outline.content
        context = (
            f"核心种子：{novel['core_seed']}\n"
            f"情节架构：\n{novel['plot_architecture']}\n"
            f"前文摘要：\n{novel['global_summary'] or '（无）'}\n"
            f"角色状态：\n{novel['character_state'] or '（无）'}"
        )
        target_key = str(payload.chapter_no)
    elif target == "chapter":
        if payload.chapter_no is None:
            raise HTTPException(400, "缺少 chapter_no")
        with db_session() as session:
            chapter = session.query(Chapter).filter_by(
                novel_id=novel_id, chapter_no=payload.chapter_no).first()
            if not chapter:
                raise HTTPException(404, "章节不存在")
            original = chapter.content
            outline = session.query(ChapterOutline).filter_by(
                novel_id=novel_id, chapter_no=payload.chapter_no).first()
            outline_text = outline.content if outline else "（无）"
        context = (
            f"本章细纲：\n{outline_text}\n"
            f"前文摘要：\n{novel['global_summary'] or '（无）'}\n"
            f"角色状态：\n{novel['character_state'] or '（无）'}"
        )
        target_key = str(payload.chapter_no)
    else:
        raise HTTPException(400, f"不支持的修订目标: {target}")

    if not original:
        raise HTTPException(400, "目标内容为空，无法修订")

    # 对话式改写：注入同一目标此前的修改指令历史（参考 dev 分支 rewrite_novel_field）
    with db_session() as session:
        logs = (session.query(RevisionLog)
                .filter_by(novel_id=novel_id, target_type=target, target_key=target_key)
                .filter(RevisionLog.instruction != "")
                .order_by(RevisionLog.id.desc()).limit(5).all())
        history = "\n".join(
            f"{i}. {log.instruction}"
            for i, log in enumerate(reversed(logs), start=1)
        )

    # 影响分析的下游资产：仅看被改目标之后的内容
    after_no = payload.chapter_no or 0
    with db_session() as session:
        later_outlines = (session.query(ChapterOutline)
                          .filter(ChapterOutline.novel_id == novel_id,
                                  ChapterOutline.chapter_no > after_no)
                          .order_by(ChapterOutline.chapter_no).all())
        downstream_outlines = "\n".join(
            f"第{o.chapter_no}章《{o.title}》：{o.content[:80]}" for o in later_outlines)
        later_chapters = (session.query(Chapter)
                          .filter(Chapter.novel_id == novel_id,
                                  Chapter.chapter_no > after_no)
                          .order_by(Chapter.chapter_no).all())
        downstream_chapters = "\n".join(
            f"第{c.chapter_no}章《{c.title}》（{c.status}）" for c in later_chapters)
    has_downstream = bool(downstream_outlines or downstream_chapters
                          or novel["global_summary"])
    do_impact = payload.analyze_impact and has_downstream

    def gen() -> Iterator[str]:
        steps = [{"id": "revise", "label": "Revision：按指令修订中"}]
        if do_impact:
            steps.append({"id": "impact", "label": "Impact：分析对下游内容的影响"})
        yield _sse("steps", {"steps": steps})
        try:
            revised = RevisionAgent().revise(
                target_type=target, original=original,
                instruction=payload.instruction, context=context,
                history=history,
            )
            with db_session() as session:
                log = RevisionLog(
                    novel_id=novel_id, target_type=target, target_key=target_key,
                    instruction=payload.instruction, old_content=original,
                )
                session.add(log)
                if target in BLUEPRINT_REVISE_FIELDS:
                    setattr(session.get(Novel, novel_id), target, revised)
                elif target == "chapter_outline":
                    o = session.query(ChapterOutline).filter_by(
                        novel_id=novel_id, chapter_no=payload.chapter_no).first()
                    o.content = revised
                    o.status = "edited"
                else:
                    c = session.query(Chapter).filter_by(
                        novel_id=novel_id, chapter_no=payload.chapter_no).first()
                    c.content = revised
                    c.status = "edited"
                session.flush()
                log_id = log.id
            yield _sse("step_done", {"id": "revise", "label": "修订完成"})

            impacted: list[dict] = []
            if do_impact:
                label = TARGET_LABELS.get(target, target)
                if payload.chapter_no:
                    label = f"第{payload.chapter_no}章的{label}"
                impacted = ImpactAgent().analyze(
                    target_label=label,
                    instruction=payload.instruction,
                    old_content=original, new_content=revised,
                    downstream_outlines=downstream_outlines,
                    downstream_chapters=downstream_chapters,
                    global_summary=novel["global_summary"],
                    character_state=novel["character_state"],
                )
                with db_session() as session:
                    session.get(RevisionLog, log_id).impact_report = json.dumps(
                        impacted, ensure_ascii=False)
                yield _sse("step_done", {
                    "id": "impact",
                    "label": (f"发现 {len(impacted)} 处受影响内容"
                              if impacted else "未发现下游冲突"),
                    "payload": {"impacted": impacted},
                })
            yield _sse("done", {
                "target_type": target, "target_key": target_key,
                "impacted": impacted,
            })
        except Exception as e:  # noqa: BLE001
            logger.exception("修订失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())


# ---------------------------------------------------------------- 新角色深化

@router.post("/{novel_id}/characters/deepen")
def deepen_characters(novel_id: int, payload: DeepenCharactersRequest):
    """深化新角色：定稿后补全初稿卡，或为 upcoming 章节预建重要角色。"""
    novel = _load_novel(novel_id)
    if not novel.get("character_dynamics") and not novel.get("core_seed"):
        raise HTTPException(400, "请先生成蓝图（需要核心种子或角色动力学）")
    if not payload.names and not payload.planned:
        raise HTTPException(400, "请提供 names（已有角色）或 planned（规划登场）")

    def gen() -> Iterator[str]:
        tasks: list[dict] = []
        by_name = {c["name"]: c for c in _load_characters(novel_id)}
        for name in payload.names:
            tasks.append({"kind": "existing", "name": name.strip()})
        for p in payload.planned:
            tasks.append({
                "kind": "planned",
                "name": p.name.strip(),
                "role_hint": p.role_hint,
            })
        yield _sse("steps", {"steps": [
            {"id": f"deepen_{i}", "label": f"Character：深化「{t['name']}」"}
            for i, t in enumerate(tasks)
        ]})
        results: list[dict] = []
        try:
            ctx_novel = novel
            for i, task in enumerate(tasks):
                name = task["name"]
                if not name:
                    continue
                if task["kind"] == "existing":
                    row = by_name.get(name)
                    if not row:
                        raise ValueError(f"角色「{name}」不在角色库中，请使用 planned 模式预建")
                    _run_character_deepen(
                        novel_id, ctx_novel,
                        name=name,
                        mode="existing",
                        char_id=row["id"],
                        current_card=row.get("data"),
                        debut_chapter_no=payload.debut_chapter_no or row.get("first_chapter"),
                        target_chapter_no=payload.target_chapter_no,
                        user_hint=payload.user_hint,
                    )
                else:
                    _run_character_deepen(
                        novel_id, ctx_novel,
                        name=name,
                        mode="planned",
                        current_card=by_name.get(name, {}).get("data"),
                        char_id=by_name.get(name, {}).get("id"),
                        target_chapter_no=payload.target_chapter_no,
                        role_hint=task.get("role_hint", ""),
                        user_hint=payload.user_hint,
                        create_if_missing=True,
                    )
                ctx_novel = _load_novel(novel_id)
                by_name = {c["name"]: c for c in _load_characters(novel_id)}
                results.append({"name": name, "kind": task["kind"]})
                yield _sse("step_done", {
                    "id": f"deepen_{i}",
                    "label": f"已深化：{name}",
                })
            yield _sse("done", {"deepened": results})
        except Exception as e:  # noqa: BLE001
            logger.exception("角色深化失败")
            yield _sse("error", {"message": str(e)})

    return _sse_response(gen())
