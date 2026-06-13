"""Example System — Phase 2: every hand-verified fixture passes validators 1-3 by
running through the REAL visual_v2 pipeline (spec §5.3, §7.1 hand_verified).

This is the golden test the spec mandates: a fixture that doesn't trace + validate +
meet its min_steps is a broken fixture, caught at author time.

Run: python -m unittest app.tests.test_example_fixtures
"""
from __future__ import annotations

import unittest

from app.core.example_fixtures import FIXTURES, CanonicalFixture
from app.core.visual_ontology_v2 import MODES_BY_BASE_TYPE
from app.services.examples.handoff import fixture_to_canonical_example, resolve_visual
from app.services.visual_v2.pipeline import run_for_registered

ALL_FIXTURES: list[CanonicalFixture] = [fx for fxs in FIXTURES.values() for fx in fxs]


class TestFixturesValidate(unittest.TestCase):
    def test_there_are_fixtures(self):
        self.assertGreaterEqual(len(ALL_FIXTURES), 4)

    def test_resolve_visual_is_a_real_ontology_pair(self):
        # VisualValidator (spec §5.3 #3): the resolved (base_type, mode) must exist.
        for fx in ALL_FIXTURES:
            base_type, mode = resolve_visual(fx)
            self.assertIn(base_type, MODES_BY_BASE_TYPE, f"{fx.fixture_id}: base {base_type}")
            self.assertIn(mode, MODES_BY_BASE_TYPE[base_type], f"{fx.fixture_id}: mode {mode}")

    def test_every_fixture_validates_through_the_pipeline(self):
        # InputValidator + TraceValidator + VisualModelValidator run inside the pipeline.
        for fx in ALL_FIXTURES:
            example = fixture_to_canonical_example(fx)
            result = run_for_registered(example, model_id=f"test_{fx.fixture_id}")
            self.assertEqual(
                result["status"], "validated",
                f"{fx.fixture_id} failed at {result.get('stage')}: {result.get('errors')}",
            )

    def test_every_fixture_meets_min_steps(self):
        for fx in ALL_FIXTURES:
            example = fixture_to_canonical_example(fx)
            result = run_for_registered(example, model_id=f"test_{fx.fixture_id}")
            min_steps = int(fx.sizing.get("min_steps", 0))
            self.assertGreaterEqual(
                len(result["frames"]), min_steps,
                f"{fx.fixture_id}: {len(result['frames'])} frames < min_steps {min_steps}",
            )

    def test_code_fixtures_carry_runnable_code(self):
        for fx in ALL_FIXTURES:
            if fx.example_type == "code_execution_trace":
                self.assertTrue(fx.code and fx.entry_function, f"{fx.fixture_id} missing code/entry")


if __name__ == "__main__":
    unittest.main()
