# -*- coding: utf-8 -*-
"""提示词库 — 任务模板从 tasks/**/*.md 加载（正文与 novel-engine 原版一致）。"""

from backend.prompts.anti_ai import (
    load_anti_ai_tone,
    load_mechanical_rules,
    prompt_kwargs,
)
from backend.prompts.load import load_task

ANTI_AI_TONE = load_anti_ai_tone()
MECHANICAL_ANTI_AI_RULES = load_mechanical_rules()

# Planner
EXPAND_STORY_PROMPT = load_task("planner/expand-story")
CORE_SEED_PROMPT = load_task("planner/core-seed")
WORLD_BUILDING_PROMPT = load_task("planner/world-building")
PLOT_ARCHITECTURE_PROMPT = load_task("planner/plot-architecture")
NOVEL_META_PROMPT = load_task("planner/novel-meta")
VOLUME_PLAN_PROMPT = load_task("planner/volume-plan")
INITIAL_VOLUME_PLAN_PROMPT = load_task("planner/initial-volume-plan")
VOLUME_PROPOSE_NEXT_PROMPT = load_task("planner/volume-propose-next")
REPLAN_SKELETON_ARCS_PROMPT = load_task("planner/replan-skeleton-arcs")
COMPASS_REFRESH_PROMPT = load_task("planner/compass-refresh")
ARC_SUMMARY_PROMPT = load_task("planner/arc-summary")
COMPASS_INIT_PROMPT = load_task("planner/compass-init")
COMPASS_UPDATE_PROMPT = load_task("planner/compass-update")

# Character
CHARACTER_DYNAMICS_PROMPT = load_task("character/character-dynamics")
EXTRACT_CHARACTERS_PROMPT = load_task("character/extract-characters")
CHARACTER_EXTRACT_CHAPTER_PROMPT = load_task("character/extract-chapter")
CREATE_CHARACTER_STATE_PROMPT = load_task("character/create-state")
UPDATE_CHARACTER_STATE_PROMPT = load_task("character/update-state")
DEEPEN_NEW_CHARACTER_PROMPT = load_task("character/deepen-new")
UPDATE_VOICE_RULES_PROMPT = load_task("character/update-voice-rules")
CAST_EXTRACT_CHAPTER_PROMPT = load_task("character/cast-extract-chapter")

# WorldKeeper (faction + lore)
CREATE_FACTIONS_PROMPT = load_task("worldkeeper/create-factions")
FACTION_SEED_OPENING_PROMPT = load_task("worldkeeper/faction-seed-opening")
FACTION_EXTRACT_CHAPTER_PROMPT = load_task("worldkeeper/faction-extract-chapter")
LORE_EXTRACT_INITIAL_PROMPT = load_task("worldkeeper/lore-extract-initial")
LORE_UPDATE_PROMPT = load_task("worldkeeper/lore-update")

# ChapterPlanner
CHAPTER_OUTLINES_PROMPT = load_task("chapter_planner/chapter-outlines")
EXPAND_ARC_OUTLINES_PROMPT = load_task("chapter_planner/expand-arc-outlines")

# Writer
FIRST_CHAPTER_DRAFT_PROMPT = load_task("writer/first-chapter")
NEXT_CHAPTER_DRAFT_PROMPT = load_task("writer/next-chapter")
SUMMARY_UPDATE_PROMPT = load_task("writer/update-summary")
ENRICH_PROMPT = load_task("writer/enrich")
REVISE_BY_ISSUES_PROMPT = load_task("writer/rewrite-by-issues")

# Reviewer (consistency + critic)
CONSISTENCY_CHECK_PROMPT = load_task("reviewer/consistency-check")
CRITIQUE_PROMPT = load_task("reviewer/critique")

# NarrativeLedger (foreshadow + payoff + toxin)
FORESHADOW_EXTRACT_PROMPT = load_task("narrative_ledger/foreshadow-extract")
TOXIN_SCAN_PROMPT = load_task("narrative_ledger/toxin-scan")
PAYOFF_EXTRACT_PROMPT = load_task("narrative_ledger/payoff-extract")

# Revision
REVISE_TEXT_PROMPT = load_task("revision/revise-text")
REVISE_SEGMENT_PROMPT = load_task("revision/revise-segment")

# Editor
POLISH_PROMPT = load_task("editor/polish")
HUMANIZE_PROMPT = load_task("editor/humanize")
POLISH_SEGMENT_PROMPT = load_task("editor/polish-segment")
HUMANIZE_SEGMENT_PROMPT = load_task("editor/humanize-segment")
STYLE_RULES_ARC_PROMPT = load_task("editor/style-rules-arc")
ARC_REVIEW_PROMPT = load_task("editor/arc-review")
ARC_BOUNDARY_PROMPT = load_task("editor/arc-boundary")
VOLUME_SUMMARY_PROMPT = load_task("editor/volume-summary")

# Oneshot
IMPACT_ANALYSIS_PROMPT = load_task("oneshot/impact-analysis")
STYLE_LEARN_PROMPT = load_task("oneshot/style-learn")

__all__ = [
    "ANTI_AI_TONE",
    "MECHANICAL_ANTI_AI_RULES",
    "prompt_kwargs",
    "EXPAND_STORY_PROMPT",
    "CORE_SEED_PROMPT",
    "WORLD_BUILDING_PROMPT",
    "PLOT_ARCHITECTURE_PROMPT",
    "NOVEL_META_PROMPT",
    "VOLUME_PLAN_PROMPT",
    "CHARACTER_DYNAMICS_PROMPT",
    "EXTRACT_CHARACTERS_PROMPT",
    "CHARACTER_EXTRACT_CHAPTER_PROMPT",
    "CREATE_CHARACTER_STATE_PROMPT",
    "UPDATE_CHARACTER_STATE_PROMPT",
    "DEEPEN_NEW_CHARACTER_PROMPT",
    "CREATE_FACTIONS_PROMPT",
    "FACTION_SEED_OPENING_PROMPT",
    "FACTION_EXTRACT_CHAPTER_PROMPT",
    "LORE_EXTRACT_INITIAL_PROMPT",
    "LORE_UPDATE_PROMPT",
    "CHAPTER_OUTLINES_PROMPT",
    "FIRST_CHAPTER_DRAFT_PROMPT",
    "NEXT_CHAPTER_DRAFT_PROMPT",
    "SUMMARY_UPDATE_PROMPT",
    "ENRICH_PROMPT",
    "REVISE_BY_ISSUES_PROMPT",
    "CONSISTENCY_CHECK_PROMPT",
    "CRITIQUE_PROMPT",
    "FORESHADOW_EXTRACT_PROMPT",
    "TOXIN_SCAN_PROMPT",
    "PAYOFF_EXTRACT_PROMPT",
    "REVISE_TEXT_PROMPT",
    "REVISE_SEGMENT_PROMPT",
    "POLISH_PROMPT",
    "HUMANIZE_PROMPT",
    "POLISH_SEGMENT_PROMPT",
    "HUMANIZE_SEGMENT_PROMPT",
    "IMPACT_ANALYSIS_PROMPT",
    "STYLE_LEARN_PROMPT",
]
