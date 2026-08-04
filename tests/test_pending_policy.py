from __future__ import annotations

import unittest

from backend.pending.policy import proposal_key, select_proposals


def item(kind: str, name: str, score: float, evidence: str, **extra):
    return {
        "kind": kind,
        "payload": {
            "name": name,
            "importance": score,
            "future_relevance": "high",
            "evidence": evidence,
            "reason": "后续主线会继续使用",
            **extra,
        },
    }


class PendingPolicyTests(unittest.TestCase):
    def test_requires_exact_chapter_evidence(self):
        kept, stats = select_proposals(
            [item("character", "顾沉", 0.9, "并不存在的原文")],
            chapter_text="顾沉推门走进仓库。",
        )
        self.assertEqual([], kept)
        self.assertEqual(1, stats["low_value"])

    def test_keeps_high_value_and_rejects_low_value(self):
        kept, stats = select_proposals(
            [
                item("character", "顾沉", 0.9, "顾沉推门走进仓库"),
                item("character", "路人甲", 0.4, "路人甲挥了挥手"),
            ],
            chapter_text="顾沉推门走进仓库。路人甲挥了挥手。",
        )
        self.assertEqual(["顾沉"], [x["payload"]["name"] for x in kept])
        self.assertEqual(1, stats["low_value"])

    def test_quota_prefers_higher_importance(self):
        kept, stats = select_proposals(
            [
                item("lore", "旧钥匙", 0.75, "旧钥匙只能开启北门"),
                item("lore", "北门禁令", 0.95, "午夜后北门禁止通行"),
            ],
            chapter_text="旧钥匙只能开启北门。午夜后北门禁止通行。",
            limits={"lore": 1},
        )
        self.assertEqual("北门禁令", kept[0]["payload"]["name"])
        self.assertEqual(1, stats["over_limit"])

    def test_existing_pending_or_canon_is_deduplicated(self):
        candidate = item("faction", "巡夜司", 0.9, "巡夜司封锁了整条街")
        key = proposal_key("faction", candidate["payload"])
        kept, stats = select_proposals(
            [candidate],
            chapter_text="巡夜司封锁了整条街。",
            existing_keys={key},
        )
        self.assertEqual([], kept)
        self.assertEqual(1, stats["duplicate"])


if __name__ == "__main__":
    unittest.main()
