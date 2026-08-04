"""弧结束时生成弧摘要（engine 任务，结构对齐 ainovel save_arc_summary 的 summary 部分）。"""

from __future__ import annotations

from backend.llm.client import LLMClient
from backend.prompts import definitions as P


class ArcPlannerAgent:
    def __init__(self):
        self.llm = LLMClient("planner")

    def summarize_arc(
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
        chapter_excerpts: str,
    ) -> dict:
        result = self.llm.invoke_json(P.ARC_SUMMARY_PROMPT.format(
            volume_no=volume_no,
            volume_title=volume_title or "（无）",
            arc_no=arc_no,
            arc_title=arc_title or "（无）",
            arc_goal=arc_goal or "（无）",
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            global_summary=global_summary or "（无）",
            chapter_excerpts=chapter_excerpts or "（无正文）",
        ))
        return result if isinstance(result, dict) else {}
