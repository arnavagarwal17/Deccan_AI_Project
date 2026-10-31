"""
tests/test_phase3.py
Validates Phase 3 brief synthesis components:
- Sampling determinism and incoherence rule enforcement
- Brief synthesis with constraint echo verification
- Persistent disk caching behavior in pipeline/cache/
- Embedding deduplication and 20% held-out partition
"""

import json
import unittest
from pathlib import Path

from pipeline.sample import sample_specs
from pipeline.synthesize_brief import synthesize_brief, validate_spec_echo
from pipeline.dedup import deduplicate_briefs


class TestPhase3BriefSynthesis(unittest.TestCase):
    def test_sampling_determinism_and_rules(self):
        specs1 = sample_specs(count=10, seed=42)
        specs2 = sample_specs(count=10, seed=42)
        self.assertEqual(len(specs1), 10)
        self.assertEqual([s.task_id for s in specs1], [s.task_id for s in specs2])

        # Verify incoherence rules hold
        for s in specs1:
            if s.mood == "calm":
                self.assertFalse(s.interaction == "drag-rotate")
                self.assertGreater(s.motion_budget_ms[1], 1600)
            if s.mood == "energetic":
                self.assertNotEqual(s.interaction, "none")
                self.assertLess(s.motion_budget_ms[0], 1800)

    def test_brief_synthesis_and_spec_echo_validation(self):
        specs = sample_specs(count=2, seed=123)
        target = specs[0]
        res = synthesize_brief(target, seed=123)

        self.assertIn("prose", res)
        self.assertIn(target.required_copy[0], res["prose"])
        self.assertEqual(res["spec_echo"]["product_category"], target.product_category)
        self.assertEqual(res["spec_echo"]["palette"], target.palette)

        # Mutate echo to assert validator catches alteration
        tampered = dict(res["spec_echo"])
        tampered["mood"] = "tampered_mood"
        with self.assertRaises(ValueError):
            validate_spec_echo(target, tampered)

    def test_caching_behavior(self):
        specs = sample_specs(count=1, seed=999)
        s = specs[0]

        # First call: populates cache
        res1 = synthesize_brief(s, seed=999)
        cache_key = res1["cache_key"]
        cache_file = Path("pipeline/cache") / f"{cache_key}.json"
        self.assertTrue(cache_file.exists(), "Cache file must exist on disk")

        # Second call: must read from cache
        res2 = synthesize_brief(s, seed=999)
        self.assertEqual(res2["path"], "cache", "Second call must return cached path")
        self.assertEqual(res1["prose"], res2["prose"])

    def test_embedding_deduplication_and_heldout_split(self):
        specs = sample_specs(count=10, seed=777)
        records = []
        for s in specs:
            b = synthesize_brief(s, seed=777)
            b["spec"] = s.model_dump()
            records.append(b)

        training, heldout, rejected = deduplicate_briefs(records, threshold=0.92)
        total_accepted = len(training) + len(heldout)

        self.assertEqual(len(records), total_accepted + len(rejected))
        self.assertGreater(len(training), 0)
        self.assertGreater(len(heldout), 0)

        # Check held-out files were written to disk
        heldout_files = list(Path("quality/heldout").glob("*.json"))
        self.assertGreaterEqual(len(heldout_files), len(heldout))


if __name__ == "__main__":
    unittest.main()

