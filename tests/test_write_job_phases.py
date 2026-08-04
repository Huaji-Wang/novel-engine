"""写章后台任务的相位推进逻辑（纯函数，不触库不调 LLM）。"""

from __future__ import annotations

import unittest

from backend.services.write_chapter import _next_phase


class NextPhaseTests(unittest.TestCase):
    def test_linear_happy_path(self):
        self.assertEqual("write", _next_phase("retrieve_memory", {}))
        self.assertEqual("consistency_check", _next_phase("write", {}))

    def test_review_ok_goes_to_quality_gate(self):
        state = {"review": {"ok": True, "issues": []}}
        self.assertEqual("quality_gate", _next_phase("consistency_check", state))

    def test_blocking_review_triggers_auto_revise(self):
        state = {
            "review": {"ok": False, "issues": [{"severity": "high"}]},
            "revise_rounds": 0,
            "max_revise_rounds": 1,
        }
        self.assertEqual("auto_revise", _next_phase("consistency_check", state))

    def test_revise_rounds_exhausted(self):
        state = {
            "review": {"ok": False, "issues": [{"severity": "high"}]},
            "revise_rounds": 1,
            "max_revise_rounds": 1,
        }
        self.assertEqual("quality_gate", _next_phase("consistency_check", state))

    def test_auto_revise_loops_back(self):
        self.assertEqual("consistency_check", _next_phase("auto_revise", {}))

    def test_quality_pass_ends(self):
        state = {"quality_decision": {"decision": "pass"}, "quality_rounds": 0}
        self.assertEqual("__end__", _next_phase("quality_gate", state))

    def test_unknown_phase_ends(self):
        self.assertEqual("__end__", _next_phase("nonsense", {}))


if __name__ == "__main__":
    unittest.main()
