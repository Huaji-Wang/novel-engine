"""按需组装 references/ 参考资料（不修改 tasks 模板正文）。"""

from __future__ import annotations

from backend.prompts.load import format_reference_pack, load_reference


def writer_references(*, chapter_no: int) -> str:
    refs: dict[str, str] = {}
    wq = load_reference("writing-quality")
    if wq:
        refs["writing_quality"] = wq
    for key, name in (
        ("hook_techniques", "hook-techniques"),
        ("consistency", "consistency"),
    ):
        text = load_reference(name)
        if text:
            refs[key] = text
    if chapter_no <= 3:
        for key, name in (
            ("chapter_guide", "chapter-guide"),
            ("dialogue_writing", "dialogue-writing"),
        ):
            text = load_reference(name)
            if text:
                refs[key] = text
    return format_reference_pack(refs)


def reviewer_references() -> str:
    refs: dict[str, str] = {}
    for key, name in (
        ("quality_checklist", "quality-checklist"),
        ("consistency_rubric", "consistency"),
    ):
        text = load_reference(name)
        if text:
            refs[key] = text
    return format_reference_pack(refs)


def planner_references() -> str:
    refs: dict[str, str] = {}
    for key, name in (
        ("longform_planning", "longform-planning"),
        ("arc_planning", "arc-planning"),
        ("outline_template", "outline-template"),
        ("character_template", "character-template"),
        ("character_building", "character-building"),
    ):
        text = load_reference(name)
        if text:
            refs[key] = text
    return format_reference_pack(refs)


def arc_planner_references() -> str:
    """卷/弧规划任务专用：长篇 + 叙事弧参考。"""
    refs: dict[str, str] = {}
    for key, name in (
        ("arc_planning", "arc-planning"),
        ("outline_template", "outline-template"),
    ):
        text = load_reference(name)
        if text:
            refs[key] = text
    return format_reference_pack(refs)


def append_reference_block(prompt: str, pack: str) -> str:
    if not pack or pack == "（无额外参考资料）":
        return prompt
    return prompt + "\n\n【补充参考资料（供对照，勿逐字复述）】\n" + pack
