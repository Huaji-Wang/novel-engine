"""蓝图流水线：

共创(+指南针) → 核心种子 → 角色动力学 → 世界观
  → 第1弧架构 → 指南针精炼 → 初始角色状态 → 首批细纲

取消开书「全书散文压缩故事」；硬锁共创；结局/总章数不写死。
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.chapter_planner import ChapterPlannerAgent
from backend.agents.character import CharacterAgent
from backend.agents.planner import PlannerAgent
from backend.planning.compass import format_compass_context
from backend.planning.guidance import chapter_cap


class BlueprintState(TypedDict, total=False):
    # 输入
    premise: str
    genre: str
    num_chapters: int
    words_per_chapter: int
    cocreate_context: str
    guide_style: str
    guide_pov: str
    guide_taboos: str
    is_fanfic: bool
    outline_window: int
    story_compass: dict
    # 产出
    full_story: str
    core_seed: str
    character_dynamics: str
    world_building: str
    plot_architecture: str
    character_state: str
    chapter_outlines: list[dict]


def _guide_kwargs(state: BlueprintState) -> dict:
    return {
        "cocreate_context": state.get("cocreate_context", ""),
        "guide_style": state.get("guide_style", ""),
        "guide_pov": state.get("guide_pov", ""),
        "guide_taboos": state.get("guide_taboos", ""),
    }


def _core_seed(state: BlueprintState) -> dict:
    seed = PlannerAgent().core_seed(
        premise=state["premise"], genre=state["genre"],
        num_chapters=state["num_chapters"],
        words_per_chapter=state["words_per_chapter"],
        compass_context=format_compass_context(state.get("story_compass")),
        **_guide_kwargs(state),
    )
    return {"core_seed": seed}


def _character_dynamics(state: BlueprintState) -> dict:
    dynamics = CharacterAgent().design_dynamics(
        core_seed=state["core_seed"], **_guide_kwargs(state),
    )
    return {"character_dynamics": dynamics}


def _world_building(state: BlueprintState) -> dict:
    world = PlannerAgent().world_building(
        core_seed=state["core_seed"], **_guide_kwargs(state),
    )
    return {"world_building": world}


def _plot_architecture(state: BlueprintState) -> dict:
    plot = PlannerAgent().plot_architecture(
        core_seed=state["core_seed"],
        character_dynamics=state["character_dynamics"],
        world_building=state["world_building"],
        compass_context=format_compass_context(state.get("story_compass")),
        num_chapters=state.get("num_chapters", 0),
        words_per_chapter=state.get("words_per_chapter", 3000),
        **_guide_kwargs(state),
    )
    return {"plot_architecture": plot}


def _init_compass(state: BlueprintState) -> dict:
    """在共创抽取基础上精炼弱指南针；无共创稿时也能生成倾向指引。"""
    existing = state.get("story_compass") or {}
    compass = PlannerAgent().init_compass(
        core_seed=state.get("core_seed", ""),
        full_story="",
        plot_architecture=state.get("plot_architecture", ""),
        num_chapters=state.get("num_chapters", 0),
        existing_compass=existing if existing.get("ending_direction") or existing.get("open_threads") else None,
        **_guide_kwargs(state),
    )
    if not compass:
        compass = existing
    summary_parts = []
    if compass.get("ending_direction"):
        summary_parts.append(f"【终局倾向】{compass['ending_direction']}")
    threads = compass.get("open_threads") or []
    if threads:
        summary_parts.append("【开放长线】\n" + "\n".join(f"- {t}" for t in threads[:8]))
    if compass.get("estimated_scale"):
        summary_parts.append(f"【规模参考】{compass['estimated_scale']}")
    if compass.get("tone_notes"):
        summary_parts.append(f"【调性/禁区】{compass['tone_notes']}")
    summary_parts.append("（弱指南针：可随时修改；收束前须作者同意。非全书散文故事。）")
    return {
        "story_compass": compass,
        "full_story": "\n\n".join(summary_parts),
    }


def _init_character_state(state: BlueprintState) -> dict:
    char_state = CharacterAgent().create_state(state["character_dynamics"])
    return {"character_state": char_state}


def _initial_outlines(state: BlueprintState) -> dict:
    window = state.get("outline_window", 3)
    cap = chapter_cap(state.get("num_chapters", 0))
    outlines = ChapterPlannerAgent().plan_next(
        core_seed=state["core_seed"],
        world_building=state["world_building"],
        plot_architecture=state["plot_architecture"],
        character_state=state.get("character_state", ""),
        global_summary="",
        existing_outlines="",
        num_chapters=state.get("num_chapters", 0),
        start_no=1,
        end_no=min(window, cap),
        is_fanfic=bool(state.get("is_fanfic")),
        compass_context=format_compass_context(state.get("story_compass")),
        **_guide_kwargs(state),
    )
    return {"chapter_outlines": outlines}


BLUEPRINT_STEPS = {
    "core_seed": "Planner：提炼核心种子（锁共创）",
    "character_dynamics": "Character：角色动力学（锁共创）",
    "world_building": "Planner：世界观（锁共创）",
    "plot_architecture": "Planner：第1弧架构（近处节拍）",
    "init_compass": "Planner：精炼全书弱指南针",
    "init_character_state": "Character：建立初始角色状态表",
    "initial_outlines": "ChapterPlanner：生成首批章节细纲",
}

BLUEPRINT_NODE_ORDER = [
    ("core_seed", _core_seed),
    ("character_dynamics", _character_dynamics),
    ("world_building", _world_building),
    ("plot_architecture", _plot_architecture),
    ("init_compass", _init_compass),
    ("init_character_state", _init_character_state),
    ("initial_outlines", _initial_outlines),
]


def iter_blueprint_steps(state: BlueprintState):
    """逐步执行蓝图：每步开始前 yield ('start', id)，完成后 yield ('done', id, updates)。"""
    current: dict = dict(state)
    for node_id, fn in BLUEPRINT_NODE_ORDER:
        yield ("start", node_id, None)
        updates = fn(current) or {}
        current.update(updates)
        yield ("done", node_id, updates)


def build_blueprint_graph():
    g = StateGraph(BlueprintState)
    for node_id, fn in BLUEPRINT_NODE_ORDER:
        g.add_node(node_id, fn)
    g.add_edge(START, "core_seed")
    g.add_edge("core_seed", "character_dynamics")
    g.add_edge("character_dynamics", "world_building")
    g.add_edge("world_building", "plot_architecture")
    g.add_edge("plot_architecture", "init_compass")
    g.add_edge("init_compass", "init_character_state")
    g.add_edge("init_character_state", "initial_outlines")
    g.add_edge("initial_outlines", END)
    return g.compile()
