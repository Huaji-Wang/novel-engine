"""Smoke test without LLM: health check + prompt load.

Run from the repository root: python -m scripts.smoke_test
"""
from __future__ import annotations

from backend.prompts import definitions as P
from backend.utils.chapter_health import check_chapter_health

sample = "他说：" + "你好。" * 40 + "\n" + "故事继续。" * 20
report = check_chapter_health(sample, chapter_no=1, target_words=800)
print("prompt expand_story chars:", len(P.EXPAND_STORY_PROMPT))
print("health status:", report["status"])
print("health summary:", report["summary"])
