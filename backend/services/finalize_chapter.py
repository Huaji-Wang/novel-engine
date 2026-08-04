"""定稿流水线（后台任务版）：与 SSE 版完全相同的步骤序列，
每步完成即记入 job.checkpoint["done"]，崩溃/重启/失败重试时跳过已完成步骤，
不重复消耗 LLM token，也不重复写库。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from backend.agents.character import CharacterAgent
from backend.agents.memory import MemoryService
from backend.agents.narrative_ledger import NarrativeLedgerAgent
from backend.agents.planner import PlannerAgent
from backend.agents.worldkeeper import WorldKeeperAgent
from backend.agents.writer import WriterAgent
from backend.api.generation import (
    _effective_quality_gate,
    _load_characters,
    _load_factions,
    _load_ledger,
    _load_lore,
    _load_novel,
    _load_volumes,
    _run_arc_boundary,
    _run_propose_next_volume,
    _run_volume_summary,
)
from backend.characters.cast import merge_cast_appearances
from backend.db.models import (
    Chapter,
    ChapterOutline,
    Character,
    Faction,
    Foreshadowing,
    LoreEntry,
    Novel,
    Payoff,
)
from backend.db.session import db_session
from backend.jobs.context import JobContext
from backend.pending.service import add_proposals
from backend.planning.structure import find_arc_for_chapter, is_volume_end
from backend.planning.volumes import has_next_volume, is_book_complete
from backend.utils.chapter_health import check_chapter_health
from backend.utils.publish_readiness import check_publish_readiness
from backend.utils.rewrite_decider import decide_quality_action

logger = logging.getLogger(__name__)

CANCELLED = object()

FINALIZE_STEPS = [
    {"id": "health", "label": "HealthCheck：规则化章节健康检查"},
    {"id": "readiness", "label": "PublishAudit：发布结构审稿"},
    {"id": "summary", "label": "StateKeeper：更新前文摘要"},
    {"id": "char_state", "label": "StateKeeper：更新角色状态表"},
    {"id": "characters", "label": "Character：提取新角色提案"},
    {"id": "cast", "label": "Cast：提取配角提案"},
    {"id": "factions", "label": "WorldKeeper：提取阵营提案"},
    {"id": "toxin", "label": "NarrativeLedger：毒点扫描"},
    {"id": "payoff", "label": "NarrativeLedger：爽点台账抽取"},
    {"id": "foreshadow", "label": "NarrativeLedger：更新伏笔台账"},
    {"id": "lore", "label": "WorldKeeper：提取设定提案"},
    {"id": "pending", "label": "Pending：待确认提案入库"},
    {"id": "memory", "label": "MemoryService：章节向量化入库"},
]


class FinalizeBlocked(Exception):
    """质量门阻断定稿（critical 健康/结构问题）。"""


@dataclass
class _Ctx:
    novel_id: int
    chapter_no: int
    chapter_text: str
    outline_text: str
    emit: object
    pending_items: list = field(default_factory=list)


def _step_gate(f: _Ctx) -> None:
    novel = _load_novel(f.novel_id)
    gate = _effective_quality_gate(novel)
    health = check_chapter_health(
        f.chapter_text, chapter_no=f.chapter_no,
        target_words=novel["words_per_chapter"],
    )
    readiness = check_publish_readiness(
        f.chapter_text,
        strict=bool(gate.get("strict_publish_audit", True)),
    )
    qdecision = decide_quality_action(health=health, readiness=readiness)
    with db_session() as session:
        ch = session.query(Chapter).filter_by(
            novel_id=f.novel_id, chapter_no=f.chapter_no).first()
        ch.health_report = json.dumps(health, ensure_ascii=False)
        ch.readiness_report = json.dumps(readiness, ensure_ascii=False)
        ch.quality_decision = json.dumps(qdecision, ensure_ascii=False)
    f.emit("step_done", {"id": "health", "label": f"HealthCheck：{health['summary']}",
                         "payload": health})
    f.emit("step_done", {"id": "readiness", "label": f"PublishAudit：{readiness['summary']}",
                         "payload": readiness})
    if gate.get("block_finalize", True) and (
        health["status"] == "critical" or readiness["status"] == "critical"
    ):
        raise FinalizeBlocked(
            f"定稿已阻断：{health['summary']}；{readiness['summary']}。"
            "请先修订章节或关闭 block_finalize。"
        )


def _step_summary(f: _Ctx) -> None:
    novel = _load_novel(f.novel_id)
    new_summary = WriterAgent().update_summary(
        f.chapter_text, novel["global_summary"])
    with db_session() as session:
        session.get(Novel, f.novel_id).global_summary = new_summary
    f.emit("step_done", {"id": "summary", "label": "前文摘要已更新"})


def _step_char_state(f: _Ctx) -> None:
    novel = _load_novel(f.novel_id)
    new_state = CharacterAgent().update_state(
        f.chapter_text, novel["character_state"])
    with db_session() as session:
        session.get(Novel, f.novel_id).character_state = new_state
        ch = session.query(Chapter).filter_by(
            novel_id=f.novel_id, chapter_no=f.chapter_no).first()
        ch.status = "finalized"
        ch.summary = (novel["global_summary"] or "")[:500]
    f.emit("step_done", {"id": "char_state", "label": "角色状态已更新"})


def _step_characters(f: _Ctx) -> None:
    novel = _load_novel(f.novel_id)
    chars = _load_characters(f.novel_id)
    char_changes = CharacterAgent().extract_from_chapter(
        chapter_no=f.chapter_no, chapter_text=f.chapter_text,
        character_dynamics=novel["character_dynamics"],
        existing=chars,
    )
    by_char = {c["name"]: c for c in chars}
    for item in char_changes.get("new") or []:
        name = item.get("name")
        if name and name not in by_char:
            f.pending_items.append({
                "kind": "character",
                "payload": {
                    "name": name,
                    "data": item.get("data") or {},
                    "importance": item.get("importance"),
                    "future_relevance": item.get("future_relevance"),
                    "evidence": item.get("evidence"),
                    "reason": item.get("reason"),
                },
            })
    with db_session() as session:
        for name in char_changes.get("appeared") or []:
            match = by_char.get(name)
            if not match:
                continue
            row = session.get(Character, match["id"])
            row.last_chapter = f.chapter_no
            row.status = "active"
        for name in char_changes.get("inactive") or []:
            match = by_char.get(name)
            if not match:
                continue
            session.get(Character, match["id"]).status = "inactive"
    f.emit("step_done", {
        "id": "characters",
        "label": (f"新角色提案 {len(char_changes.get('new') or [])} 条"
                  f"（出场{len(char_changes.get('appeared') or [])}"
                  f"/离场{len(char_changes.get('inactive') or [])}）"),
    })


def _step_cast(f: _Ctx) -> None:
    core_names = [c["name"] for c in _load_characters(f.novel_id)]
    cast_raw = CharacterAgent().extract_cast_from_chapter(
        chapter_no=f.chapter_no,
        chapter_text=f.chapter_text,
        core_names=core_names,
    )
    for intro in cast_raw.get("cast_intros") or []:
        if isinstance(intro, dict) and intro.get("name"):
            f.pending_items.append({"kind": "cast", "payload": intro})
    cast_added = merge_cast_appearances(
        f.novel_id, f.chapter_no,
        cast_raw.get("appeared") or [],
        [],
    )
    f.emit("step_done", {
        "id": "cast",
        "label": (f"配角提案 {len(cast_raw.get('cast_intros') or [])} 条"
                  f"（本章出场 {len(cast_raw.get('appeared') or [])} 人"
                  f"{f'，已跟踪 {cast_added}' if cast_added else ''}）"),
    })


def _step_factions(f: _Ctx) -> None:
    novel = _load_novel(f.novel_id)
    factions, relations = _load_factions(f.novel_id)
    f_changes = WorldKeeperAgent().extract_factions_from_chapter(
        chapter_no=f.chapter_no, chapter_text=f.chapter_text,
        world_building=novel["world_building"],
        factions=factions, relations=relations,
    )
    by_faction = {x["name"]: x for x in factions}
    for raw in f_changes.get("new_factions") or []:
        if not isinstance(raw, dict):
            continue
        data = dict(raw)
        name = str(data.pop("name", "")).strip()
        if name and name not in by_faction:
            f.pending_items.append({
                "kind": "faction",
                "payload": {"name": name, **data},
            })
    for raw in f_changes.get("new_relations") or []:
        if not isinstance(raw, dict):
            continue
        data = dict(raw)
        source = str(data.pop("source_faction_name", "")).strip()
        target = str(data.pop("target_faction_name", "")).strip()
        rel_type = str(data.pop("relation_type", "")).strip()
        if source and target:
            f.pending_items.append({
                "kind": "faction_relation",
                "payload": {
                    "source": source, "target": target,
                    "relation_type": rel_type, **data,
                },
            })
    with db_session() as session:
        for upd in f_changes.get("updated_factions") or []:
            if not isinstance(upd, dict):
                continue
            name = str(upd.get("name", "")).strip()
            row = session.query(Faction).filter_by(
                novel_id=f.novel_id, name=name).first()
            if not row:
                continue
            data = dict(row.data or {})
            for key in ("public_stance", "core_goal", "positioning",
                        "hidden_goal", "conflict_with_mainline"):
                if upd.get(key):
                    data[key] = upd[key]
            row.data = data
            row.last_chapter = f.chapter_no
        for name in f_changes.get("appeared") or []:
            row = session.query(Faction).filter_by(
                novel_id=f.novel_id, name=name).first()
            if row:
                row.last_chapter = f.chapter_no
                row.status = "active"
        for name in f_changes.get("inactive") or []:
            row = session.query(Faction).filter_by(
                novel_id=f.novel_id, name=name).first()
            if row:
                row.status = "inactive"
    fstats = {k: len(v) for k, v in f_changes.items()}
    n_props = len([p for p in f.pending_items
                   if p["kind"] in ("faction", "faction_relation")])
    f.emit("step_done", {
        "id": "factions",
        "label": (f"阵营提案 {n_props} 条"
                  f"（出场{fstats.get('appeared', 0)}/离场{fstats.get('inactive', 0)}）"),
    })


def _step_toxin(f: _Ctx) -> None:
    toxin = NarrativeLedgerAgent().scan_toxin(
        chapter_text=f.chapter_text, chapter_outline=f.outline_text)
    with db_session() as session:
        ch = session.query(Chapter).filter_by(
            novel_id=f.novel_id, chapter_no=f.chapter_no).first()
        ch.toxin_report = json.dumps(toxin, ensure_ascii=False)
    tcount = len(toxin.get("issues", []))
    f.emit("step_done", {
        "id": "toxin",
        "label": f"毒点扫描完成（发现 {tcount} 项）" if tcount
        else "毒点扫描：未发现明显毒点",
        "payload": toxin,
    })


def _step_payoff(f: _Ctx) -> None:
    payoff_items = NarrativeLedgerAgent().extract_payoff(
        chapter_text=f.chapter_text, chapter_outline=f.outline_text)
    with db_session() as session:
        session.query(Payoff).filter_by(
            novel_id=f.novel_id, chapter_no=f.chapter_no).delete()
        for item in payoff_items:
            session.add(Payoff(
                novel_id=f.novel_id, chapter_no=f.chapter_no, **item))
    f.emit("step_done", {
        "id": "payoff",
        "label": f"爽点台账已更新（本章 {len(payoff_items)} 个）",
    })


def _step_foreshadow(f: _Ctx) -> None:
    novel = _load_novel(f.novel_id)
    ledger = _load_ledger(f.novel_id)
    changes = NarrativeLedgerAgent().analyze_foreshadow(
        chapter_no=f.chapter_no, chapter_text=f.chapter_text,
        ledger=ledger, num_chapters=novel["num_chapters"],
    )
    by_name = {it["name"]: it for it in ledger}
    with db_session() as session:
        for item in changes["new"]:
            name = str(item.get("name", "")).strip()
            if not name or name in by_name:
                continue
            session.add(Foreshadowing(
                novel_id=f.novel_id, name=name,
                description=str(item.get("description", "")),
                planted_chapter=f.chapter_no,
                last_touched_chapter=f.chapter_no,
                resolve_by_chapter=int(item.get("resolve_by_chapter") or 0),
            ))
        for key, new_status in (("reinforced", "reinforced"), ("resolved", "resolved")):
            for item in changes[key]:
                match = by_name.get(str(item.get("name", "")).strip())
                if not match:
                    continue
                row = session.get(Foreshadowing, match["id"])
                row.status = new_status
                row.last_touched_chapter = f.chapter_no
                note = str(item.get("note", ""))
                if note:
                    row.notes = (row.notes + "\n" if row.notes else "") + \
                        f"第{f.chapter_no}章：{note}"
    stats = {k: len(v) for k, v in changes.items()}
    f.emit("step_done", {
        "id": "foreshadow",
        "label": f"伏笔台账已更新（新增{stats['new']}/强化{stats['reinforced']}/回收{stats['resolved']}）",
    })


def _step_lore(f: _Ctx) -> None:
    lore_entries = _load_lore(f.novel_id)
    existing_by_name = {e["name"]: e for e in lore_entries}
    lore_changes = WorldKeeperAgent().extract_lore_from_chapter(
        chapter_no=f.chapter_no, chapter_text=f.chapter_text,
        existing_names=list(existing_by_name.keys()),
    )
    for item in lore_changes.get("new") or []:
        if item.get("name") and item["name"] not in existing_by_name:
            f.pending_items.append({"kind": "lore", "payload": item})
    with db_session() as session:
        for item in lore_changes.get("updated") or []:
            match = existing_by_name.get(item.get("name"))
            if match and item.get("content"):
                row = session.get(LoreEntry, match["id"])
                row.content = item["content"]
                row.source_chapter = f.chapter_no
    f.emit("step_done", {
        "id": "lore",
        "label": (f"设定提案 {len(lore_changes.get('new') or [])} 条"
                  f"（已确认设定修订 {len(lore_changes.get('updated') or [])}）"),
    })


def _step_pending(f: _Ctx) -> None:
    pending_stats = add_proposals(
        f.novel_id,
        f.chapter_no,
        f.pending_items,
        chapter_text=f.chapter_text,
    )
    pending_n = pending_stats["added"]
    filtered_n = pending_stats["input"] - pending_n
    f.emit("step_done", {
        "id": "pending",
        "label": (
            f"待确认提案 {pending_n} 条"
            f"（过滤低价值/重复/超额 {filtered_n} 条，请人工确认后入账）"
        ),
        "payload": {"count": pending_n, "stats": pending_stats},
    })


def _step_memory(f: _Ctx) -> None:
    chunk_count = MemoryService().index_chapter(
        f.novel_id, f.chapter_no, f.chapter_text)
    label = (f"已入库 {chunk_count} 个切片" if chunk_count >= 0
             else "未配置 embedding，已跳过")
    f.emit("step_done", {"id": "memory", "label": f"Memory：{label}"})


def _step_arc_boundary(f: _Ctx) -> None:
    volumes = _load_volumes(f.novel_id)
    arc_hit = find_arc_for_chapter(volumes, f.chapter_no)
    if not (arc_hit and f.chapter_no == arc_hit["end_chapter"]):
        return
    f.emit("steps", {"steps": [
        {"id": "arc_review", "label": "Editor：弧级评审"},
        {"id": "arc_boundary", "label": "Editor：弧摘要与快照"},
    ]})
    try:
        novel = _load_novel(f.novel_id)
        arc_result = _run_arc_boundary(f.novel_id, novel, f.chapter_no, volumes)
        if arc_result:
            verdict = arc_result.get("review_verdict") or "accept"
            f.emit("step_done", {
                "id": "arc_review",
                "label": f"第{arc_result['arc_no']}弧评审：{verdict}",
            })
            snap_n = arc_result.get("snapshot_count") or 0
            f.emit("step_done", {
                "id": "arc_boundary",
                "label": (
                    f"第{arc_result['arc_no']}弧《{arc_result['title']}》"
                    f"摘要已生成，{snap_n} 个角色快照"
                ),
            })
            vu = arc_result.get("voice_updated") or []
            if vu:
                f.emit("step_done", {
                    "id": "arc_boundary",
                    "label": f"对话规则已同步：{'、'.join(vu)}",
                })
    except Exception as e:  # noqa: BLE001
        logger.exception("弧边界处理失败")
        f.emit("step_done", {
            "id": "arc_boundary",
            "label": f"弧边界处理跳过（{e}）",
        })


def _step_volume_end(f: _Ctx) -> None:
    volumes = _load_volumes(f.novel_id)
    if not is_volume_end(volumes, f.chapter_no):
        return
    vol = next(v for v in volumes if v["end_chapter"] == f.chapter_no)
    f.emit("steps", {"steps": [
        {"id": "volume_summary", "label": "Editor：卷级摘要"},
    ]})
    try:
        novel = _load_novel(f.novel_id)
        volumes_fresh = _load_volumes(f.novel_id)
        vol_result = _run_volume_summary(
            f.novel_id, novel, f.chapter_no, volumes_fresh,
        )
        if vol_result:
            f.emit("step_done", {
                "id": "volume_summary",
                "label": (
                    f"第{vol_result['volume_no']}卷《{vol_result['title']}》"
                    "卷摘要已生成"
                ),
            })
    except Exception as e:  # noqa: BLE001
        logger.exception("卷摘要生成失败")
        f.emit("step_done", {
            "id": "volume_summary",
            "label": f"卷摘要跳过（{e}）",
        })
    try:
        novel = _load_novel(f.novel_id)
        updated = PlannerAgent().update_compass(
            current_compass=novel.get("story_compass") or {},
            global_summary=novel["global_summary"],
            volume_no=vol["volume_no"],
            volume_title=vol["title"],
            volume_theme=vol["theme"],
        )
        if updated:
            with db_session() as session:
                n = session.get(Novel, f.novel_id)
                merged = dict(n.story_compass or {})
                merged.update(updated)
                merged["last_updated_chapter"] = f.chapter_no
                merged["planning_mode"] = merged.get("planning_mode") or "rolling"
                n.story_compass = merged
            f.emit("step_done", {
                "id": "compass_update",
                "label": f"第{vol['volume_no']}卷结束：终局指南针已更新",
            })
    except Exception as e:  # noqa: BLE001
        logger.exception("指南针更新失败")
        f.emit("step_done", {
            "id": "compass_update",
            "label": f"指南针更新跳过（{e}）",
        })

    if not has_next_volume(volumes, vol["volume_no"]) and not is_book_complete(
        (_load_novel(f.novel_id).get("story_compass") or {})
    ):
        f.emit("steps", {"steps": [
            {"id": "propose_next", "label": "Planner：生成下一卷方向选项"},
        ]})
        try:
            novel = _load_novel(f.novel_id)
            volumes_now = _load_volumes(f.novel_id)
            proposal = _run_propose_next_volume(
                f.novel_id, novel, volumes_now,
                volume_no=vol["volume_no"],
            )
            opts = proposal.get("options") or []
            f.emit("step_done", {
                "id": "propose_next",
                "label": f"已生成 {len(opts)} 个下一卷方向，请在蓝图页选择并追加",
                "payload": {"count": len(opts),
                            "can_complete_book": proposal.get("can_complete_book")},
            })
        except Exception as e:  # noqa: BLE001
            logger.exception("生成下一卷方向失败")
            f.emit("step_done", {
                "id": "propose_next",
                "label": f"下一卷方向生成跳过（{e}）",
            })


# 顺序与 SSE 版定稿完全一致；id 用于 checkpoint 跳过判断。
_STEP_FUNCS = [
    ("gate", _step_gate),
    ("summary", _step_summary),
    ("char_state", _step_char_state),
    ("characters", _step_characters),
    ("cast", _step_cast),
    ("factions", _step_factions),
    ("toxin", _step_toxin),
    ("payoff", _step_payoff),
    ("foreshadow", _step_foreshadow),
    ("lore", _step_lore),
    ("pending", _step_pending),
    ("memory", _step_memory),
    ("arc_boundary", _step_arc_boundary),
    ("volume_end", _step_volume_end),
]


def run_finalize_job(job: dict, ctx: JobContext) -> dict | object:
    """按步骤推进定稿流水线；每步完成即落 checkpoint。"""
    params = job.get("params") or {}
    novel_id = int(params["novel_id"])
    chapter_no = int(params["chapter_no"])

    with db_session() as session:
        chapter = session.query(Chapter).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        if not chapter or not chapter.content:
            raise ValueError("章节不存在或内容为空")
        chapter_text = chapter.content
        ol = session.query(ChapterOutline).filter_by(
            novel_id=novel_id, chapter_no=chapter_no).first()
        outline_text = ol.content if ol else ""

    checkpoint = dict(job.get("checkpoint") or {})
    done = set(checkpoint.get("done") or [])
    f = _Ctx(
        novel_id=novel_id,
        chapter_no=chapter_no,
        chapter_text=chapter_text,
        outline_text=outline_text,
        emit=ctx.emit,
        pending_items=list(checkpoint.get("pending_items") or []),
    )

    already_has_steps = any(
        entry.get("event") == "steps" for entry in (job.get("progress") or []))
    if not already_has_steps:
        ctx.emit("steps", {"steps": FINALIZE_STEPS})

    for step_id, fn in _STEP_FUNCS:
        if step_id in done:
            continue
        if ctx.cancelled():
            return CANCELLED
        fn(f)
        done.add(step_id)
        ctx.save_checkpoint({
            "done": sorted(done),
            "pending_items": f.pending_items,
        })

    result = {"chapter_no": chapter_no}
    ctx.emit("done", result)
    return result
