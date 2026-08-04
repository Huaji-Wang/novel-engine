"""Reviewer Agent：一致性审校(Consistency) + 质量评审(Critic)。"""

from __future__ import annotations

from backend.context.assembler import append_reference_block, reviewer_references
from backend.llm.client import LLMClient
from backend.prompts import definitions as P
from backend.prompts.anti_ai import prompt_kwargs

SCORE_KEYS = ("plot", "character", "dialogue", "setting_fit", "requirement_fit", "prose")


class ReviewerAgent:
    def __init__(self):
        self._consistency_llm = LLMClient("consistency")
        self._critic_llm = LLMClient("critic")

    def check_chapter(self, *, core_seed: str, world_building: str,
                      character_state: str, global_summary: str,
                      chapter_outline: str, chapter_text: str,
                      foreshadowing_ledger: str = "") -> dict:
        """原 ConsistencyAgent.check_chapter"""
        prompt = append_reference_block(
            P.CONSISTENCY_CHECK_PROMPT.format(
                core_seed=core_seed,
                world_building=world_building,
                character_state=character_state or "（无）",
                global_summary=global_summary or "（无）",
                chapter_outline=chapter_outline,
                chapter_text=chapter_text,
                foreshadowing_ledger=foreshadowing_ledger or "（暂无伏笔记录）",
            ),
            reviewer_references(),
        )
        result = self._consistency_llm.invoke_json(prompt)
        if not isinstance(result, dict):
            return {"ok": True, "issues": []}
        result.setdefault("ok", True)
        result.setdefault("issues", [])
        return result

    def review_chapter(self, *, chapter_no: int, chapter_text: str,
                       chapter_outline: str, character_state: str,
                       world_building: str, genre: str,
                       writing_style: str, narrative_pov: str,
                       words_per_chapter: int, user_guidance: str) -> dict:
        """原 CriticAgent.review_chapter"""
        prompt = append_reference_block(
            P.CRITIQUE_PROMPT.format(
                chapter_no=chapter_no,
                chapter_text=chapter_text,
                chapter_outline=chapter_outline or "（无）",
                character_state=(character_state or "（无）")[:2000],
                world_building=(world_building or "（无）")[:1500],
                genre=genre or "（未定）",
                writing_style=writing_style or "（不限）",
                narrative_pov=narrative_pov or "（不限）",
                words_per_chapter=words_per_chapter,
                actual_words=len(chapter_text),
                user_guidance=user_guidance or "无",
                **prompt_kwargs(include_writer_extra=False),
            ),
            reviewer_references(),
        )
        result = self._critic_llm.invoke_json(prompt)
        if not isinstance(result, dict):
            return {}
        scores = result.get("scores")
        result["scores"] = scores if isinstance(scores, dict) else {}
        result["issues"] = result.get("issues") if isinstance(result.get("issues"), list) else []
        result["strengths"] = result.get("strengths") if isinstance(result.get("strengths"), list) else []
        has_high = any(i.get("severity") == "high" for i in result["issues"]
                       if isinstance(i, dict))
        try:
            overall = float(result.get("overall") or 0)
        except (TypeError, ValueError):
            overall = 0.0
        result["overall"] = overall
        result["verdict"] = "needs_work" if (has_high or overall < 7) else "pass"
        return result
