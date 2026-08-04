"""Impact Analyzer Agent：修订后的下游影响分析。"""

from __future__ import annotations

from backend.llm.client import LLMClient
from backend.prompts import definitions as P

_EXCERPT = 1200


class ImpactAgent:
    def __init__(self):
        self.llm = LLMClient("impact")

    def analyze(self, *, target_label: str, instruction: str,
                old_content: str, new_content: str,
                downstream_outlines: str, downstream_chapters: str,
                global_summary: str, character_state: str) -> list[dict]:
        result = self.llm.invoke_json(P.IMPACT_ANALYSIS_PROMPT.format(
            target_label=target_label,
            instruction=instruction,
            old_excerpt=old_content[:_EXCERPT] or "（空）",
            new_excerpt=new_content[:_EXCERPT] or "（空）",
            downstream_outlines=downstream_outlines or "（无）",
            downstream_chapters=downstream_chapters or "（无）",
            global_summary=(global_summary or "（无）")[:1000],
            character_state=(character_state or "（无）")[:1500],
        ))
        if isinstance(result, dict) and isinstance(result.get("impacted"), list):
            return result["impacted"]
        return []
