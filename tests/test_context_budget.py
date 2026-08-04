from __future__ import annotations

import unittest

from backend.context.budget import (
    apply_writer_budget,
    clip_to_tokens,
    context_strategy,
    estimate_tokens,
    strategy_profile,
)


class EstimateTokensTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(0, estimate_tokens(""))
        self.assertEqual(0, estimate_tokens(None))

    def test_cjk_costs_more_than_ascii(self):
        cjk = "他推开门走进了昏暗的仓库深处" * 10
        ascii_text = "a" * len(cjk)
        self.assertGreater(estimate_tokens(cjk), estimate_tokens(ascii_text))


class ClipToTokensTests(unittest.TestCase):
    def test_within_budget_unchanged(self):
        text = "短文本。"
        self.assertEqual(text, clip_to_tokens(text, 1000))

    def test_keep_head(self):
        text = "开头标记。" + "中间内容。" * 500
        clipped = clip_to_tokens(text, 100, keep="head")
        self.assertTrue(clipped.startswith("开头标记。"))
        self.assertLessEqual(estimate_tokens(clipped), 160)  # 含截断标记

    def test_keep_tail(self):
        text = "中间内容。" * 500 + "结尾标记。"
        clipped = clip_to_tokens(text, 100, keep="tail")
        self.assertTrue(clipped.endswith("结尾标记。"))

    def test_keep_lines(self):
        text = "\n".join(f"第{i}行设定" for i in range(200))
        clipped = clip_to_tokens(text, 100, keep="lines")
        self.assertIn("第0行设定", clipped)
        self.assertNotIn("第199行设定", clipped)

    def test_zero_budget(self):
        self.assertEqual("", clip_to_tokens("内容", 0))


class StrategyTests(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual("full", context_strategy(30))
        self.assertEqual("sliding", context_strategy(100))
        self.assertEqual("layered", context_strategy(300))

    def test_profile_has_budget(self):
        profile = strategy_profile(300)
        self.assertEqual("layered", profile["strategy"])
        self.assertGreater(profile["budget_tokens"], 0)
        self.assertGreater(profile["prev_excerpt_chars"], 0)


class ApplyWriterBudgetTests(unittest.TestCase):
    def _fat_state(self) -> dict:
        para = "这里是很长的一段中文上下文内容，反复出现以撑大体积。"
        return {
            "chapter_outline": para * 20,
            "retrieved_context": "\n".join([para] * 120),
            "recent_cast_context": "\n".join([para] * 60),
            "style_rules_context": para * 60,
            "voice_context": "\n".join([para] * 60),
            "compiled_style": para * 120,
            "style_guide": para * 120,
            "next_chapter_outline": para * 40,
            "plot_architecture": para * 160,
            "compass_context": para * 60,
            "foreshadowing_ledger": "\n".join([para] * 60),
            "lore_context": "\n".join([para] * 80),
            "world_building": para * 160,
            "previous_chapter_excerpt": para * 60,
            "global_summary": para * 200,
            "character_state": para * 120,
        }

    def test_over_budget_gets_trimmed_l3_first(self):
        state = self._fat_state()
        report = apply_writer_budget(state, num_chapters=300)
        self.assertLess(report["after"], report["before"])
        # L3 外部参考必然先被裁
        self.assertIn("retrieved_context", report["trimmed"])
        # 本章细纲永不裁剪
        self.assertNotIn("chapter_outline", report["trimmed"])

    def test_facts_keep_floor(self):
        state = self._fat_state()
        apply_writer_budget(state, num_chapters=300)
        # L0 事实层最后裁且有高地板：摘要与角色状态不会被清空
        self.assertGreaterEqual(estimate_tokens(state["global_summary"]), 700)
        self.assertGreaterEqual(estimate_tokens(state["character_state"]), 500)

    def test_summary_keeps_recent_tail(self):
        state = self._fat_state()
        state["global_summary"] = "很旧的开头。" + "中段。" * 3000 + "最近发生的事。"
        apply_writer_budget(state, num_chapters=300)
        self.assertTrue(state["global_summary"].endswith("最近发生的事。"))

    def test_small_state_untouched(self):
        state = {
            "chapter_outline": "第10章：对峙。",
            "global_summary": "前情概要。",
            "character_state": "主角：健康。",
        }
        report = apply_writer_budget(state, num_chapters=20)
        self.assertEqual({}, report["trimmed"])
        self.assertEqual("前情概要。", state["global_summary"])


if __name__ == "__main__":
    unittest.main()
