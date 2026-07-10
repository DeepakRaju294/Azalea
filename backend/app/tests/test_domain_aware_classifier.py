"""Domain-aware topic-type constraint at the SOURCE (DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC).

The wording-based classifier could emit a coding type on a math path ("Algorithm for Completing the Square" ->
algorithm_walkthrough). constrain_type_to_domain remaps it to the domain's own teaching type before any
downstream logic, so the list-level gate is only a backstop. Offline.
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_domain_aware_classifier
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.domain_gate import constrain_type_to_domain as C
from app.services.course_type_classifier import enrich_topic_with_course_type


class ConstrainTypeToDomain(unittest.TestCase):
    def test_coding_types_remapped_on_math_path(self):
        self.assertEqual(C("algorithm_walkthrough", "math"), ("math_formula_method", True))
        self.assertEqual(C("process_walkthrough", "math"), ("math_formula_method", True))
        self.assertEqual(C("science_mechanism", "math"), ("math_formula_method", True))

    def test_coding_implementation_left_for_list_gate_to_drop(self):
        # a DROP case: relabelling a single topic here would just make a duplicate; the list gate drops it
        self.assertEqual(C("coding_implementation", "math"), ("coding_implementation", False))

    def test_allowed_and_universal_types_untouched(self):
        self.assertEqual(C("math_formula_method", "math"), ("math_formula_method", False))
        self.assertEqual(C("concept_intuition", "math"), ("concept_intuition", False))    # universal
        self.assertEqual(C("study_path_introduction", "math"), ("study_path_introduction", False))

    def test_other_domains(self):
        self.assertEqual(C("math_formula_method", "coding"), ("algorithm_walkthrough", True))
        self.assertEqual(C("process_walkthrough", "science"), ("science_mechanism", True))

    def test_unknown_or_mixed_domain_is_noop(self):
        self.assertEqual(C("algorithm_walkthrough", "mixed"), ("algorithm_walkthrough", False))
        self.assertEqual(C("algorithm_walkthrough", None), ("algorithm_walkthrough", False))

    def test_enrich_applies_the_constraint_and_fixes_the_reason(self):
        t = enrich_topic_with_course_type(
            {"title": "Algorithm for Completing the Square", "topic_type": "algorithm_walkthrough"}, domain="math")
        self.assertEqual(t["course_type"], "math_formula_method")
        self.assertEqual(t["topic_type"], "math_formula_method")
        self.assertIn("math_formula_method", t["course_type_reason"])
        self.assertIn("remapped", t["course_type_reason"])

    def test_enrich_without_domain_unchanged(self):
        t = enrich_topic_with_course_type(
            {"title": "Algorithm for Completing the Square", "topic_type": "algorithm_walkthrough"})
        self.assertEqual(t["course_type"], "algorithm_walkthrough")   # no domain -> classifier's raw output


if __name__ == "__main__":
    unittest.main()
