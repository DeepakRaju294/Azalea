"""Phase-1A structural depth resolver (ONBOARDING_AND_PREFERENCE_CAPTURE_SPEC §4.2).

Locks the "deep never silently equals working" contract: deep is honored only when a topic can materially expand,
and is disclosed as working_limited otherwise.

Run: python -m unittest app.tests.test_depth_profile
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.depth_profile import (
    DEPTH_PROFILE_V1, capabilities_for, compute_effective_depth,
)


class ComputeEffectiveDepth(unittest.TestCase):
    def test_working_and_intuition_always_honored(self):
        for d in ("working", "intuition"):
            r = compute_effective_depth(d, ["concept_intuition", "study_path_introduction"])
            self.assertEqual(r["effective_depth"], d)
            self.assertEqual(r["effective_depth_reason"], "honored")

    def test_deep_honored_when_a_teaching_topic_can_expand(self):
        r = compute_effective_depth("deep", ["study_path_introduction", "math_formula_method"])
        self.assertEqual(r["effective_depth"], "deep")
        self.assertEqual(r["effective_depth_reason"], "honored")
        self.assertTrue(r["deep_where_supported"])            # intro can't expand → partial
        self.assertEqual(r["expandable_topic_count"], 1)

    def test_deep_fully_supported_is_not_partial(self):
        r = compute_effective_depth("deep", ["math_formula_method", "algorithm_walkthrough"])
        self.assertEqual(r["effective_depth"], "deep")
        self.assertFalse(r["deep_where_supported"])

    def test_deep_downgrades_when_nothing_can_expand(self):
        # a path of only intro/terminology/plain-concept can't materially deepen
        r = compute_effective_depth("deep", ["study_path_introduction", "terminology_components", "concept_intuition"])
        self.assertEqual(r["effective_depth"], "working_limited")
        self.assertEqual(r["effective_depth_reason"], "no_material_expansion_available")

    def test_unknown_depth_defaults_to_working(self):
        r = compute_effective_depth(None, ["math_formula_method"])
        self.assertEqual(r["selected_depth"], "working")
        self.assertEqual(r["effective_depth"], "working")

    def test_capabilities_default_is_conservative(self):
        cap = capabilities_for("some_未知_type")
        self.assertFalse(cap["edge_cases"])
        self.assertFalse(cap["optional_cards"])
        self.assertEqual(cap["max_adapter_instances"], 1)

    def test_profile_has_all_levels(self):
        self.assertEqual(set(DEPTH_PROFILE_V1), {"intuition", "working", "deep"})


if __name__ == "__main__":
    unittest.main()
