"""StyleLearner Agent：从参考书节选提炼风格指南。"""

from __future__ import annotations

from backend.llm.client import LLMClient
from backend.prompts import definitions as P


class StyleLearnerAgent:
    def __init__(self):
        self.llm = LLMClient("meta")

    def learn(self, reference_text: str) -> str:
        text = reference_text.strip()
        if len(text) < 200:
            raise ValueError("参考书节选至少 200 字")
        return self.llm.invoke(P.STYLE_LEARN_PROMPT.format(reference_text=text[:12000])).strip()
