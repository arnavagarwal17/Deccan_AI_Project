"""
tests/test_reward.py
Unit tests verifying reward function properties:
- NOP submission (empty file) fails gates and scores 0.
- Stub submission (copy only, no WebGL) fails gates and scores 0.
- Phase 1 solution passes all gates and scores above 0.6.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from reward.score import score


class TestRewardFunction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec_path = Path("tasks/calm-wave-fintech/environment/brief.json")
        cls.spec = json.loads(spec_path.read_text(encoding="utf-8"))

    def test_nop_submission_scores_zero(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            empty_file = Path(tmp_dir) / "index.html"
            empty_file.write_text("", encoding="utf-8")

            res = score(self.spec, tmp_dir)
            self.assertFalse(res["gate_pass"], "NOP submission must fail gate_pass")
            self.assertEqual(res["reward_binary"], 0, "NOP submission reward must be 0")
            self.assertEqual(res["quality"], 0.0, "NOP submission quality must be 0.0")

            # Verify every critical gate fails on empty file
            self.assertFalse(res["gates"]["compiles"], "Empty HTML must fail compiles gate")
            self.assertFalse(res["gates"]["webgl_context"], "Empty file must fail webgl_context")
            self.assertFalse(res["gates"]["first_frame_under_budget"], "Empty file must fail first_frame")
            self.assertFalse(res["gates"]["required_copy_present"], "Empty file must fail required_copy")

    def test_stub_submission_without_webgl_fails_gates(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            stub_file = Path(tmp_dir) / "index.html"
            stub_file.write_text(
                "<html><body><h1>NextGen Wealth</h1><p>Calm Investing</p><button>Get Started</button></body></html>",
                encoding="utf-8"
            )

            res = score(self.spec, tmp_dir)
            self.assertFalse(res["gate_pass"], "Stub submission without WebGL must fail gate_pass")
            self.assertFalse(res["gates"]["webgl_context"], "Stub without canvas must fail webgl_context")
            self.assertEqual(res["reward_binary"], 0, "Stub submission reward must be 0")
            self.assertEqual(res["quality"], 0.0, "Stub submission quality must be 0.0")

    def test_phase1_solution_passes_gates_and_scores_high(self):
        solution_dir = "tasks/calm-wave-fintech/solution"
        capture_dir = "out/test_cap"

        res = score(self.spec, solution_dir, capture_dir=capture_dir)
        for gate_name, passed in res["gates"].items():
            self.assertTrue(passed, f"Gate '{gate_name}' should pass for reference solution")

        self.assertTrue(res["gate_pass"], "Reference solution must pass gate_pass")
        self.assertEqual(res["reward_binary"], 1, "Reference solution reward must be 1")
        self.assertGreaterEqual(res["quality"], 0.6, f"Quality {res['quality']} must be >= 0.6")
        self.assertIsNone(res["families"]["judge"], "Judge slot must be null")


if __name__ == "__main__":
    unittest.main()

