"""蓝图流水线（LangGraph）：

创意 → 核心种子 → 角色动力学 → 结构化角色卡 → 世界观
     → 情节架构 → 初始角色状态 → 首批章节细纲

每个节点是一个 Agent 调用；API 层通过 graph.stream() 获取逐节点进度并持久化。
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.chapter_planner import ChapterPlannerAgent
from backend.agents.character import CharacterAgent
from backend.agents.planner import PlannerAgent


class BlueprintState(TypedDict, total=False):
    # 输入
    premise: str
    genre: str
    num_chapters: int
    words_per_chapter: int
    user_guidance: str
    outline_window: int
    # 产出
    full_story: str
    core_seed: str
    character_dynamics: str
    world_building: str
    plot_architecture: str
    character_state: str
    chapter_outlines: list[dict]


def _expand_story(state: BlueprintState) -> dict:
    story = PlannerAgent().expand_story(
        premise=state["premise"], genre=state["genre"],
        num_chapters=state["num_chapters"],
        words_per_chapter=state["words_per_chapter"],
        user_guidance=state.get("user_guidance", ""),
    )
    return {"full_story": story}


def _core_seed(state: BlueprintState) -> dict:
    seed = PlannerAgent().core_seed(
        premise=state["premise"], genre=state["genre"],
        num_chapters=state["num_chapters"],
        words_per_chapter=state["words_per_chapter"],
        user_guidance=state.get("user_guidance", ""),
        full_story=state.get("full_story", ""),
    )
    return {"core_seed": seed}


def _character_dynamics(state: BlueprintState) -> dict:
    dynamics = CharacterAgent().design_dynamics(
        core_seed=state["core_seed"], user_guidance=state.get("user_guidance", ""),
    )
    return {"character_dynamics": dynamics}


def _world_building(state: BlueprintState) -> dict:
    world = PlannerAgent().world_building(
        core_seed=state["core_seed"], user_guidance=state.get("user_guidance", ""),
    )
    return {"world_building": world}


def _plot_architecture(state: BlueprintState) -> dict:
    plot = PlannerAgent().plot_architecture(
        core_seed=state["core_seed"],
        character_dynamics=state["character_dynamics"],
        world_building=state["world_building"],
        user_guidance=state.get("user_guidance", ""),
        full_story=state.get("full_story", ""),
    )
    return {"plot_architecture": plot}


def _init_character_state(state: BlueprintState) -> dict:
    char_state = CharacterAgent().create_state(state["character_dynamics"])
    return {"character_state": char_state}


def _initial_outlines(state: BlueprintState) -> dict:
    window = state.get("outline_window", 3)
    outlines = ChapterPlannerAgent().plan_next(
        core_seed=state["core_seed"],
        world_building=state["world_building"],
        plot_architecture=state["plot_architecture"],
        character_state=state.get("character_state", ""),
        global_summary="",
        existing_outlines="",
        num_chapters=state["num_chapters"],
        start_no=1,
        end_no=min(window, state["num_chapters"]),
        user_guidance=state.get("user_guidance", ""),
    )
    return {"chapter_outlines": outlines}


# 节点名 → 前端展示用的步骤说明
BLUEPRINT_STEPS = {
    "expand_story": "Planner：扩写整本书压缩故事",
    "core_seed": "Planner：提炼核心种子",
    "character_dynamics": "Character：设计角色动力学",
    "world_building": "Planner：构建世界观",
    "plot_architecture": "Planner：设计三幕式情节架构",
    "init_character_state": "Character：建立初始角色状态表",
    "initial_outlines": "ChapterPlanner：生成首批章节细纲",
}


def build_blueprint_graph():
    g = StateGraph(BlueprintState)
    g.add_node("expand_story", _expand_story)
    g.add_node("core_seed", _core_seed)
    g.add_node("character_dynamics", _character_dynamics)
    g.add_node("world_building", _world_building)
    g.add_node("plot_architecture", _plot_architecture)
    g.add_node("init_character_state", _init_character_state)
    g.add_node("initial_outlines", _initial_outlines)

    g.add_edge(START, "expand_story")
    g.add_edge("expand_story", "core_seed")
    g.add_edge("core_seed", "character_dynamics")
    g.add_edge("character_dynamics", "world_building")
    g.add_edge("world_building", "plot_architecture")
    g.add_edge("plot_architecture", "init_character_state")
    g.add_edge("init_character_state", "initial_outlines")
    g.add_edge("initial_outlines", END)
    return g.compile()
