"""Example System — telemetry (spec §9.1): every apply/fallback is recorded with
the closed fallback enum, per-application counts, and timing.

Run: python -m unittest app.tests.test_example_metrics
"""
from __future__ import annotations

import os
import unittest

from app.services.examples.handoff import apply_fixture_to_lesson
from app.services.examples.metrics import GLOBAL, normalize_reason


def _lesson():
    return {
        "lesson_cards": [
            {"id": "1", "blueprint_key": "worked_example"},
            {"id": "2", "blueprint_key": "practice"},
        ],
        "visual_models": [],
    }


class TestNormalizeReason(unittest.TestCase):
    def test_known_reasons_pass_through(self):
        self.assertEqual(normalize_reason("no_application_match"), "no_application_match")
        self.assertEqual(normalize_reason("feature_flag_disabled"), "feature_flag_disabled")

    def test_suffixed_and_unknown_reasons_bucket(self):
        self.assertEqual(normalize_reason("visual_pipeline_failed:TraceValidator"), "visual_pipeline_failed")
        self.assertEqual(normalize_reason("something_weird"), "visual_pipeline_failed")


class TestRecording(unittest.TestCase):
    def setUp(self):
        GLOBAL.reset()
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"

    def tearDown(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)
        GLOBAL.reset()

    def test_applied_is_recorded_with_fields(self):
        apply_fixture_to_lesson(_lesson(), {"id": "t", "title": "Binary Search", "topic_type": "algorithm_walkthrough"})
        snap = GLOBAL.snapshot()
        self.assertEqual(snap["applied"], 1)
        self.assertEqual(snap["by_application"].get("binary_search"), 1)
        self.assertEqual(snap["by_fixture"].get("binary_search_concept_found_late_01"), 1)
        self.assertEqual(snap["by_lens"].get("sequence_state_trace"), 1)
        self.assertGreater(snap["avg_time_to_apply_ms"], 0)

    def test_fallbacks_bucket_by_reason(self):
        apply_fixture_to_lesson(_lesson(), {"id": "t", "title": "The Fall of Rome", "topic_type": "concept_intuition"})
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)
        apply_fixture_to_lesson(_lesson(), {"id": "t", "title": "Binary Search", "topic_type": "algorithm_walkthrough"})
        snap = GLOBAL.snapshot()
        self.assertEqual(snap["applied"], 0)
        self.assertEqual(snap["fallbacks"].get("no_application_match"), 1)
        self.assertEqual(snap["fallbacks"].get("feature_flag_disabled"), 1)
        self.assertEqual(snap["apply_rate"], 0.0)

    def test_lesson_metadata_carries_telemetry_fields(self):
        lesson = _lesson()
        apply_fixture_to_lesson(lesson, {"id": "t", "title": "Implementing Binary Search", "topic_type": "coding_implementation"})
        meta = lesson["metadata"]["visual_v2_example_ontology"]
        for key in ("pattern", "fixture_source", "variant", "time_to_apply_ms"):
            self.assertIn(key, meta)
        self.assertEqual(meta["fixture_source"], "hand_verified")
        self.assertEqual(meta["pattern"], "loop_execution")


if __name__ == "__main__":
    unittest.main()
