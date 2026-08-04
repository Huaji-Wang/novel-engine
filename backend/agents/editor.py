"""Editor Agent：章节正文润色（对话/感官/节奏，不改剧情事实）。"""

from __future__ import annotations

from backend.llm.client import LLMClient
from backend.prompts import definitions as P
from backend.prompts.anti_ai import prompt_kwargs


class EditorAgent:
    def __init__(self):
        self.llm = LLMClient("editor")

    def polish(self, *, chapter_text: str, writing_style: str,
               narrative_pov: str, instruction: str = "",
               style_guide: str = "") -> str:
        return self.llm.invoke(P.POLISH_PROMPT.format(
            chapter_text=chapter_text,
            writing_style=writing_style or "（不限）",
            narrative_pov=narrative_pov or "（保持原文视角）",
            instruction=instruction or "（无）",
            style_guide=style_guide or "（无）",
            **prompt_kwargs(include_writer_extra=False),
        ))

    def humanize(self, *, chapter_text: str, writing_style: str,
                 narrative_pov: str, instruction: str = "",
                 style_guide: str = "") -> str:
        """ainovel-cli 去 AI 味专用改写（HUMANIZE_PROMPT）。"""
        return self.llm.invoke(P.HUMANIZE_PROMPT.format(
            chapter_text=chapter_text,
            writing_style=writing_style or "（不限）",
            narrative_pov=narrative_pov or "（保持原文视角）",
            instruction=instruction or "（无）",
            style_guide=style_guide or "（无）",
            **prompt_kwargs(),
        ))

    def polish_segment(self, *, selected_text: str, instruction: str,
                       context: str, context_before: str, context_after: str,
                       writing_style: str, narrative_pov: str,
                       style_guide: str = "") -> str:
        return self.llm.invoke(P.POLISH_SEGMENT_PROMPT.format(
            selected_text=selected_text,
            instruction=instruction or "（无）",
            context=context or "（无）",
            context_before=context_before or "（无）",
            context_after=context_after or "（无）",
            writing_style=writing_style or "（不限）",
            narrative_pov=narrative_pov or "（不限）",
            style_guide=style_guide or "（无）",
            **prompt_kwargs(include_writer_extra=False),
        ))

    def humanize_segment(self, *, selected_text: str, instruction: str,
                         context: str, context_before: str, context_after: str,
                         writing_style: str, narrative_pov: str,
                         style_guide: str = "") -> str:
        return self.llm.invoke(P.HUMANIZE_SEGMENT_PROMPT.format(
            selected_text=selected_text,
            instruction=instruction or "（无）",
            context=context or "（无）",
            context_before=context_before or "（无）",
            context_after=context_after or "（无）",
            writing_style=writing_style or "（不限）",
            narrative_pov=narrative_pov or "（不限）",
            style_guide=style_guide or "（无）",
            **prompt_kwargs(),
        ))

    def extract_style_rules_arc(
        self,
        *,
        volume_no: int,
        arc_no: int,
        arc_title: str,
        arc_goal: str,
        chapter_excerpts: str,
        existing_rules: dict | None = None,
    ) -> dict:
        import json
        result = self.llm.invoke_json(P.STYLE_RULES_ARC_PROMPT.format(
            volume_no=volume_no,
            arc_no=arc_no,
            arc_title=arc_title or "（无）",
            arc_goal=arc_goal or "（无）",
            existing_rules=json.dumps(existing_rules or {}, ensure_ascii=False, indent=2),
            chapter_excerpts=(chapter_excerpts or "（无）")[:16000],
        ))
        return result if isinstance(result, dict) else {}

    def review_arc(
        self,
        *,
        volume_no: int,
        volume_title: str,
        arc_no: int,
        arc_title: str,
        arc_goal: str,
        start_chapter: int,
        end_chapter: int,
        global_summary: str,
        character_state: str,
        chapter_excerpts: str,
    ) -> dict:
        result = self.llm.invoke_json(P.ARC_REVIEW_PROMPT.format(
            volume_no=volume_no,
            volume_title=volume_title or "（无）",
            arc_no=arc_no,
            arc_title=arc_title or "（无）",
            arc_goal=arc_goal or "（无）",
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            global_summary=global_summary or "（无）",
            character_state=(character_state or "（无）")[:4000],
            chapter_excerpts=(chapter_excerpts or "（无）")[:16000],
        ))
        return result if isinstance(result, dict) else {}

    def save_arc_boundary(
        self,
        *,
        volume_no: int,
        volume_title: str,
        arc_no: int,
        arc_title: str,
        arc_goal: str,
        start_chapter: int,
        end_chapter: int,
        global_summary: str,
        character_state: str,
        arc_review_summary: str,
        chapter_excerpts: str,
        existing_rules: dict | None = None,
    ) -> dict:
        import json
        result = self.llm.invoke_json(P.ARC_BOUNDARY_PROMPT.format(
            volume_no=volume_no,
            volume_title=volume_title or "（无）",
            arc_no=arc_no,
            arc_title=arc_title or "（无）",
            arc_goal=arc_goal or "（无）",
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            global_summary=global_summary or "（无）",
            character_state=(character_state or "（无）")[:4000],
            arc_review_summary=arc_review_summary or "（无）",
            existing_rules=json.dumps(existing_rules or {}, ensure_ascii=False, indent=2),
            chapter_excerpts=(chapter_excerpts or "（无）")[:16000],
        ))
        return result if isinstance(result, dict) else {}

    def summarize_volume(
        self,
        *,
        volume_no: int,
        volume_title: str,
        volume_theme: str,
        start_chapter: int,
        end_chapter: int,
        global_summary: str,
        arc_summaries: str,
        chapter_excerpts: str,
    ) -> dict:
        result = self.llm.invoke_json(P.VOLUME_SUMMARY_PROMPT.format(
            volume_no=volume_no,
            volume_title=volume_title or "（无）",
            volume_theme=volume_theme or "（无）",
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            global_summary=global_summary or "（无）",
            arc_summaries=arc_summaries or "（无）",
            chapter_excerpts=(chapter_excerpts or "（无）")[:16000],
        ))
        return result if isinstance(result, dict) else {}
