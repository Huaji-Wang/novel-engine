"""Revision Agent：按用户指令或审校问题列表修改目标内容。"""

from __future__ import annotations

import json

from backend.llm.client import LLMClient
from backend.prompts import definitions as P

TARGET_LABELS = {
    "full_story": "整本书压缩版完整故事",
    "core_seed": "核心种子（故事核心一句话）",
    "world_building": "世界观设定",
    "plot_architecture": "三幕式情节架构",
    "character_dynamics": "角色动力学设定",
    "chapter_outline": "章节细纲",
    "chapter": "章节正文",
    "chapter_segment": "章节正文片段",
}


class RevisionAgent:
    def __init__(self):
        self.llm = LLMClient("revision")

    def revise(self, *, target_type: str, original: str,
               instruction: str, context: str, history: str = "") -> str:
        return self.llm.invoke(P.REVISE_TEXT_PROMPT.format(
            target_label=TARGET_LABELS.get(target_type, target_type),
            context=context or "（无）",
            history=history or "（首次修改）",
            original=original,
            instruction=instruction,
        ))

    def revise_segment(self, *, selected_text: str, instruction: str,
                       context: str, context_before: str, context_after: str,
                       writing_style: str, narrative_pov: str,
                       history: str = "", style_guide: str = "") -> str:
        return self.llm.invoke(P.REVISE_SEGMENT_PROMPT.format(
            selected_text=selected_text,
            instruction=instruction,
            context=context or "（无）",
            context_before=context_before or "（无）",
            context_after=context_after or "（无）",
            writing_style=writing_style or "（不限）",
            narrative_pov=narrative_pov or "（不限）",
            history=history or "（首次修改）",
            style_guide=style_guide or "（无）",
        ))

    def revise_by_issues(self, *, issues: list[dict], character_state: str,
                         global_summary: str, chapter_outline: str,
                         chapter_text: str) -> str:
        return self.llm.invoke(P.REVISE_BY_ISSUES_PROMPT.format(
            issues=json.dumps(issues, ensure_ascii=False, indent=2),
            character_state=character_state or "（无）",
            global_summary=global_summary or "（无）",
            chapter_outline=chapter_outline,
            chapter_text=chapter_text,
        ))
