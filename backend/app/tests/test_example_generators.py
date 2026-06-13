"""Tier-2 fixture generators (spec §7.1). Generated scenarios are verified through
the real pipeline (never asserted), vary by seed, and are flag-gated.

Run: python -m unittest app.tests.test_example_generators
"""
from __future__ import annotations

import os
import unittest

from app.services.examples.generators import (
    GENERATORS,
    generate_binary_search,
    generated_fixtures,
)
from app.services.examples.handoff import fixture_to_canonical_example
from app.services.visual_v2.pipeline import run_for_registered


class TestFlagGate(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AZALEA_FIXTURE_GENERATORS", None)

    def test_returns_empty_when_flag_off(self):
        os.environ.pop("AZALEA_FIXTURE_GENERATORS", None)
        self.assertEqual(generated_fixtures("binary_search", "seed"), [])

    def test_returns_fixtures_when_flag_on(self):
        os.environ["AZALEA_FIXTURE_GENERATORS"] = "1"
        self.assertTrue(generated_fixtures("binary_search", "seed"))

    def test_unknown_application_is_empty(self):
        os.environ["AZALEA_FIXTURE_GENERATORS"] = "1"
        self.assertEqual(generated_fixtures("not_an_app", "seed"), [])


class TestGeneratedScenariosValidate(unittest.TestCase):
    def test_every_generated_fixture_validates_over_many_seeds(self):
        # The golden gate: a generator may only emit scenarios that trace + validate.
        for seed in range(25):
            for fx in generate_binary_search(seed):
                result = run_for_registered(fixture_to_canonical_example(fx), model_id=f"g{seed}")
                self.assertEqual(
                    result["status"], "validated",
                    f"seed {seed} fixture {fx.fixture_id} failed at {result.get('stage')}: {result.get('errors')}",
                )
                self.assertGreaterEqual(len(result["frames"]), int(fx.sizing.get("min_steps", 0)))

    def test_expected_output_is_correct(self):
        for seed in range(10):
            for fx in generate_binary_search(seed):
                arr = list(fx.base_structure.get("array") or fx.input.get("array") or [])
                target = fx.input.get("target")
                want = arr.index(target) if target in arr else -1
                self.assertEqual(fx.expected_output, want, fx.fixture_id)

    def test_roles_present(self):
        tags = {t for fx in generate_binary_search(1) for t in fx.tags}
        self.assertIn("medium_nontrivial", tags)
        self.assertIn("edge_case", tags)
        self.assertIn("isomorphic_variant", tags)

    def test_variety_across_seeds(self):
        scenarios = set()
        for seed in range(8):
            we = next(f for f in generate_binary_search(seed)
                      if f.example_type == "sequence_state_trace" and "medium_nontrivial" in f.tags)
            scenarios.add((tuple(we.base_structure["array"]), we.input["target"]))
        self.assertGreaterEqual(len(scenarios), 5)  # genuinely varied


class TestPickFixtureSeeded(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AZALEA_FIXTURE_GENERATORS", None)

    def test_no_seed_uses_hand_verified(self):
        from app.services.examples.declaration import declare_example, pick_fixture
        d = declare_example({"id": "t", "title": "Binary Search", "topic_type": "algorithm_walkthrough"})
        fx = pick_fixture(d, "worked_example")  # no seed → stable hand-verified
        self.assertEqual(fx.fixture_id, "binary_search_concept_found_late_01")

    def test_seed_with_flag_can_pick_generated(self):
        os.environ["AZALEA_FIXTURE_GENERATORS"] = "1"
        from app.services.examples.declaration import declare_example, pick_fixture
        d = declare_example({"id": "t", "title": "Binary Search", "topic_type": "algorithm_walkthrough"})
        ids = {pick_fixture(d, "worked_example", seed=f"topic-{n}").fixture_id for n in range(12)}
        self.assertTrue(any(i.startswith("binary_search_gen_") for i in ids), ids)


if __name__ == "__main__":
    unittest.main()
