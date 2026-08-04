"""章节写作流水线（LangGraph）：

记忆检索 → 写正文 → 一致性审校 → [自动修订] → 质量门(health+readiness) → [rewrite/humanize] → 结束
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.editor import EditorAgent
from backend.agents.memory import MemoryService, format_retrieved
from backend.agents.revision import RevisionAgent
from backend.agents.reviewer import ReviewerAgent
from backend.agents.writer import WriterAgent
from backend.config import quality_gate_config
from backend.context.budget import clip_to_tokens
from backend.context.priority import build_retrieval_query, build_writer_context_package
from backend.utils.chapter_health import check_chapter_health
from backend.utils.publish_readiness import check_publish_readiness
from backend.utils.rewrite_decider import (
    QualityDecision,
    decide_quality_action,
    quality_issues_for_revision,
)


class ChapterState(TypedDict, total=False):
    novel_id: int
    chapter_no: int
    chapter_title: str
    chapter_outline: str
    next_chapter_outline: str
    core_seed: str
    world_building: str
    plot_architecture: str
    character_state: str
    global_summary: str
    previous_chapter_excerpt: str
    words_per_chapter: int
    user_guidance: str
    max_revise_rounds: int
    max_quality_rounds: int
    foreshadowing_ledger: str
    writing_style: str
    narrative_pov: str
    lore_context: str
    style_guide: str
    compiled_style: str
    context_preamble: str
    voice_context: str
    compass_context: str
    style_rules_context: str
    recent_cast_context: str
    arc_hook_note: str
    retrieved_context: str
    known_character_names: list[str]
    pending_count: int
    draft: str
    review: dict
    health_report: dict
    readiness_report: dict
    quality_decision: dict
    revise_rounds: int
    quality_rounds: int


def _write_kwargs(state: ChapterState) -> dict:
    style = state.get("compiled_style") or state.get("style_guide", "")
    preamble = state.get("context_preamble", "")
    guide = f"{preamble}\n\n{style}".strip() if preamble else style
    base = {
        "writing_style": state.get("writing_style", ""),
        "narrative_pov": state.get("narrative_pov", ""),
        "style_guide": guide,
        "voice_context": state.get("voice_context", ""),
        "compass_context": state.get("compass_context", ""),
        "style_rules_context": state.get("style_rules_context", ""),
        "recent_cast_context": state.get("recent_cast_context", ""),
        "arc_hook_note": state.get("arc_hook_note", ""),
    }
    return base


def _retrieve_memory(state: ChapterState) -> dict:
    preamble = build_writer_context_package(
        state, pending_count=state.get("pending_count", 0),
    )
    chapter_no = state["chapter_no"]
    if chapter_no <= 2:
        return {"retrieved_context": "", "context_preamble": preamble}
    memory = MemoryService()
    if not memory.enabled:
        return {"retrieved_context": ""}
    query = build_retrieval_query(
        chapter_title=state.get("chapter_title", ""),
        chapter_outline=state["chapter_outline"],
        character_state=state.get("character_state", ""),
        compass_context=state.get("compass_context", ""),
        character_names=state.get("known_character_names"),
    )
    snippets = memory.retrieve(
        novel_id=state["novel_id"],
        query=query,
        exclude_chapters={chapter_no, chapter_no - 1},
    )
    # 检索结果属 L3 外部参考：裁到预算器的预留量内，避免挤占事实/规划层
    return {
        "retrieved_context": clip_to_tokens(
            format_retrieved(snippets), 2000, keep="lines"),
        "context_preamble": preamble,
    }


def _write(state: ChapterState) -> dict:
    writer = WriterAgent()
    kw = _write_kwargs(state)
    if state["chapter_no"] <= 1:
        draft = writer.write_first_chapter(
            chapter_no=state["chapter_no"],
            chapter_title=state.get("chapter_title", ""),
            chapter_outline=state["chapter_outline"],
            core_seed=state["core_seed"],
            world_building=state["world_building"],
            plot_architecture=state["plot_architecture"],
            character_state=state.get("character_state", ""),
            words_per_chapter=state["words_per_chapter"],
            user_guidance=state.get("user_guidance", ""),
            **kw,
        )
    else:
        draft = writer.write_next_chapter(
            chapter_no=state["chapter_no"],
            chapter_title=state.get("chapter_title", ""),
            chapter_outline=state["chapter_outline"],
            next_chapter_outline=state.get("next_chapter_outline", ""),
            global_summary=state.get("global_summary", ""),
            previous_chapter_excerpt=state.get("previous_chapter_excerpt", ""),
            character_state=state.get("character_state", ""),
            world_building=state["world_building"],
            words_per_chapter=state["words_per_chapter"],
            user_guidance=state.get("user_guidance", ""),
            retrieved_context=state.get("retrieved_context", ""),
            lore_context=state.get("lore_context", ""),
            **kw,
        )
    return {"draft": draft}


def _consistency_check(state: ChapterState) -> dict:
    review = ReviewerAgent().check_chapter(
        core_seed=state["core_seed"],
        world_building=state["world_building"],
        character_state=state.get("character_state", ""),
        global_summary=state.get("global_summary", ""),
        chapter_outline=state["chapter_outline"],
        chapter_text=state["draft"],
        foreshadowing_ledger=state.get("foreshadowing_ledger", ""),
    )
    return {"review": review}


def _auto_revise(state: ChapterState) -> dict:
    revised = RevisionAgent().revise_by_issues(
        issues=state["review"].get("issues", []),
        character_state=state.get("character_state", ""),
        global_summary=state.get("global_summary", ""),
        chapter_outline=state["chapter_outline"],
        chapter_text=state["draft"],
    )
    return {"draft": revised, "revise_rounds": state.get("revise_rounds", 0) + 1}


def _route_after_review(state: ChapterState) -> str:
    review = state.get("review", {})
    has_blocking = any(
        i.get("severity") in ("high", "medium") for i in review.get("issues", [])
    )
    if not review.get("ok", True) and has_blocking and \
            state.get("revise_rounds", 0) < state.get("max_revise_rounds", 1):
        return "auto_revise"
    return "quality_gate"


def _quality_gate(state: ChapterState) -> dict:
    gate = quality_gate_config()
    draft = state.get("draft", "")
    health = check_chapter_health(
        draft, chapter_no=state["chapter_no"],
        target_words=state["words_per_chapter"],
    )
    readiness = check_publish_readiness(
        draft, strict=bool(gate.get("strict_publish_audit", True)),
    )
    decision = decide_quality_action(health=health, readiness=readiness)
    return {
        "health_report": health,
        "readiness_report": readiness,
        "quality_decision": decision,
    }


def _quality_fix(state: ChapterState) -> dict:
    gate = quality_gate_config()
    decision = state.get("quality_decision") or {}
    draft = state["draft"]
    rounds = state.get("quality_rounds", 0) + 1

    if decision.get("decision") == QualityDecision.REWRITE.value and gate.get("auto_rewrite_on_critical", True):
        issues = quality_issues_for_revision(
            state.get("health_report") or {},
            state.get("readiness_report") or {},
            decision,
        )
        draft = RevisionAgent().revise_by_issues(
            issues=issues,
            character_state=state.get("character_state", ""),
            global_summary=state.get("global_summary", ""),
            chapter_outline=state["chapter_outline"],
            chapter_text=draft,
        )
    elif decision.get("decision") == QualityDecision.HUMANIZE.value and gate.get("auto_humanize_on_fix", True):
        kw = _write_kwargs(state)
        draft = EditorAgent().humanize(
            chapter_text=draft,
            writing_style=state.get("writing_style", ""),
            narrative_pov=state.get("narrative_pov", ""),
            style_guide=kw["style_guide"],
        )

    health = check_chapter_health(
        draft, chapter_no=state["chapter_no"],
        target_words=state["words_per_chapter"],
    )
    readiness = check_publish_readiness(
        draft, strict=bool(gate.get("strict_publish_audit", True)),
    )
    new_decision = decide_quality_action(health=health, readiness=readiness)
    return {
        "draft": draft,
        "quality_rounds": rounds,
        "health_report": health,
        "readiness_report": readiness,
        "quality_decision": new_decision,
    }


def _route_after_quality(state: ChapterState) -> str:
    gate = quality_gate_config()
    decision = state.get("quality_decision") or {}
    d = decision.get("decision")
    rounds = state.get("quality_rounds", 0)
    max_rounds = state.get("max_quality_rounds", int(gate.get("max_quality_rewrite_rounds", 1)))

    if d in (QualityDecision.REWRITE.value, QualityDecision.HUMANIZE.value) and rounds < max_rounds:
        if gate.get("auto_rewrite_on_critical", True) or gate.get("auto_humanize_on_fix", True):
            return "quality_fix"
    return END


CHAPTER_STEPS = {
    "retrieve_memory": "Memory：任务驱动检索 + 分层上下文",
    "write": "Writer：撰写章节正文",
    "consistency_check": "Reviewer：一致性审校",
    "auto_revise": "Revision：按审校问题自动修订",
    "quality_gate": "QualityGate：健康检查 + 发布结构审稿",
    "quality_fix": "QualityFix：整章修订 / 去 AI 味",
}

# 供后台任务 runner 复用：与 LangGraph 图完全相同的节点与路由，
# 但可在每个节点之间落 checkpoint 实现断点恢复。
NODE_FUNCS = {
    "retrieve_memory": _retrieve_memory,
    "write": _write,
    "consistency_check": _consistency_check,
    "auto_revise": _auto_revise,
    "quality_gate": _quality_gate,
    "quality_fix": _quality_fix,
}
route_after_review = _route_after_review
route_after_quality = _route_after_quality


def build_chapter_graph():
    g = StateGraph(ChapterState)
    g.add_node("retrieve_memory", _retrieve_memory)
    g.add_node("write", _write)
    g.add_node("consistency_check", _consistency_check)
    g.add_node("auto_revise", _auto_revise)
    g.add_node("quality_gate", _quality_gate)
    g.add_node("quality_fix", _quality_fix)

    g.add_edge(START, "retrieve_memory")
    g.add_edge("retrieve_memory", "write")
    g.add_edge("write", "consistency_check")
    g.add_conditional_edges("consistency_check", _route_after_review,
                            {"auto_revise": "auto_revise", "quality_gate": "quality_gate"})
    g.add_edge("auto_revise", "consistency_check")
    g.add_conditional_edges("quality_gate", _route_after_quality,
                            {"quality_fix": "quality_fix", END: END})
    g.add_edge("quality_fix", "quality_gate")
    return g.compile()
