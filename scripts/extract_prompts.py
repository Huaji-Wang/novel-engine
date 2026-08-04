"""One-time: extract definitions.py prompt constants into tasks/**/*.md verbatim."""
from __future__ import annotations

import ast
from pathlib import Path

MAPPING = {
    "EXPAND_STORY_PROMPT": "tasks/planner/expand-story.md",
    "CORE_SEED_PROMPT": "tasks/planner/core-seed.md",
    "WORLD_BUILDING_PROMPT": "tasks/planner/world-building.md",
    "PLOT_ARCHITECTURE_PROMPT": "tasks/planner/plot-architecture.md",
    "NOVEL_META_PROMPT": "tasks/planner/novel-meta.md",
    "VOLUME_PLAN_PROMPT": "tasks/planner/volume-plan.md",
    "ARC_SUMMARY_PROMPT": "tasks/planner/arc-summary.md",
    "COMPASS_INIT_PROMPT": "tasks/planner/compass-init.md",
    "COMPASS_UPDATE_PROMPT": "tasks/planner/compass-update.md",
    "CHARACTER_DYNAMICS_PROMPT": "tasks/character/character-dynamics.md",
    "EXTRACT_CHARACTERS_PROMPT": "tasks/character/extract-characters.md",
    "CHARACTER_EXTRACT_CHAPTER_PROMPT": "tasks/character/extract-chapter.md",
    "DEEPEN_NEW_CHARACTER_PROMPT": "tasks/character/deepen-new.md",
    "UPDATE_VOICE_RULES_PROMPT": "tasks/character/update-voice-rules.md",
    "CAST_EXTRACT_CHAPTER_PROMPT": "tasks/character/cast-extract-chapter.md",
    "STYLE_RULES_ARC_PROMPT": "tasks/editor/style-rules-arc.md",
    "CREATE_CHARACTER_STATE_PROMPT": "tasks/character/create-state.md",
    "UPDATE_CHARACTER_STATE_PROMPT": "tasks/character/update-state.md",
    "CREATE_FACTIONS_PROMPT": "tasks/worldkeeper/create-factions.md",
    "FACTION_SEED_OPENING_PROMPT": "tasks/worldkeeper/faction-seed-opening.md",
    "FACTION_EXTRACT_CHAPTER_PROMPT": "tasks/worldkeeper/faction-extract-chapter.md",
    "CHAPTER_OUTLINES_PROMPT": "tasks/chapter_planner/chapter-outlines.md",
    "FIRST_CHAPTER_DRAFT_PROMPT": "tasks/writer/first-chapter.md",
    "NEXT_CHAPTER_DRAFT_PROMPT": "tasks/writer/next-chapter.md",
    "SUMMARY_UPDATE_PROMPT": "tasks/writer/update-summary.md",
    "ENRICH_PROMPT": "tasks/writer/enrich.md",
    "CONSISTENCY_CHECK_PROMPT": "tasks/reviewer/consistency-check.md",
    "CRITIQUE_PROMPT": "tasks/reviewer/critique.md",
    "LORE_EXTRACT_INITIAL_PROMPT": "tasks/worldkeeper/lore-extract-initial.md",
    "LORE_UPDATE_PROMPT": "tasks/worldkeeper/lore-update.md",
    "FORESHADOW_EXTRACT_PROMPT": "tasks/narrative_ledger/foreshadow-extract.md",
    "TOXIN_SCAN_PROMPT": "tasks/narrative_ledger/toxin-scan.md",
    "PAYOFF_EXTRACT_PROMPT": "tasks/narrative_ledger/payoff-extract.md",
    "REVISE_TEXT_PROMPT": "tasks/revision/revise-text.md",
    "REVISE_SEGMENT_PROMPT": "tasks/revision/revise-segment.md",
    "REVISE_BY_ISSUES_PROMPT": "tasks/writer/rewrite-by-issues.md",
    "POLISH_PROMPT": "tasks/editor/polish.md",
    "HUMANIZE_PROMPT": "tasks/editor/humanize.md",
    "POLISH_SEGMENT_PROMPT": "tasks/editor/polish-segment.md",
    "HUMANIZE_SEGMENT_PROMPT": "tasks/editor/humanize-segment.md",
    "IMPACT_ANALYSIS_PROMPT": "tasks/oneshot/impact-analysis.md",
    "STYLE_LEARN_PROMPT": "tasks/oneshot/style-learn.md",
}


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "backend" / "prompts"
    src = root / "definitions.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id not in MAPPING:
                continue
            val = node.value
            if not isinstance(val, ast.Constant) or not isinstance(val.value, str):
                raise SystemExit(f"unsupported value for {target.id}")
            out = root / MAPPING[target.id]
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(val.value, encoding="utf-8")
            print("wrote", out.relative_to(root))
    print("done")


if __name__ == "__main__":
    main()
