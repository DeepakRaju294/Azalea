"""Phase-0 domain topic-type gate (DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §4–§5).

Deterministic gate over topic dicts: forbidden types are remapped (with a full-contract rewrite), coding
implementations drop when covered, native-domain coverage is guaranteed, and science `math_formula_method`
is allowed only when quantitatively centered. No DB, no LLM.

Run: python -m unittest app.tests.test_domain_gate
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.domain_gate import (
    gate_topic_types_by_domain, quantitative_center, rewrite_topic_contract, teaching_types_for,
)


def _types(topics):
    return [t.get("course_type") for t in topics]


class QuantitativeCenter(unittest.TestCase):
    def test_reviewer_table(self):
        cases = {
            "Calculate acceleration from force and mass": True,
            "Apply Ohm's Law to determine current": True,
            "Understand Ohm's Law": False,
            "Explain why acceleration increases with force": False,
            "Solve a quadratic equation": True,
            "Interpret the quadratic formula": False,
        }
        for title, expected in cases.items():
            self.assertEqual(quantitative_center({"title": title})["decision"], expected, title)

    def test_reason_codes_present(self):
        r = quantitative_center({"title": "Calculate force using F = ma"})
        for k in ("formula_detected", "quantitative_verb_detected", "numeric_or_unit_signal_detected",
                  "adapter_compatible", "decision"):
            self.assertIn(k, r)


class RewriteTopicContract(unittest.TestCase):
    def test_deterministic_title_normalization(self):
        for original, target, expected in [
            ("Implementing BFS", "algorithm_walkthrough", "Implementing BFS"),  # coding target: kept
            ("Implementing Completing the Square", "math_formula_method", "Completing the Square"),
            ("Solving Systems of Linear Equations", "math_formula_method", "Systems of Linear Equations"),
            ("Calculating Electric Field Strength", "science_mechanism", "Electric Field Strength"),
            ("Finding the Shortest Path", "math_formula_method", "Finding the Shortest Path"),  # NOT stripped
        ]:
            t = rewrite_topic_contract({"title": original}, target, "math", reason="t")
            self.assertEqual(t["title"], expected, original)

    def test_contract_fields_and_audit(self):
        t = rewrite_topic_contract(
            {"title": "Implementing Completing the Square", "course_type": "coding_implementation",
             "content_role": "implementation", "practice_format": "coding"},
            "math_formula_method", "math", reason="gate_remap")
        self.assertEqual(t["course_type"], "math_formula_method")
        self.assertEqual(t["content_role"], "calculation")
        self.assertEqual(t["practice_format"], "math_input")
        self.assertFalse(t["coding_follow_up"])
        self.assertEqual(t["_original_title"], "Implementing Completing the Square")
        self.assertEqual(t["_original_course_type"], "coding_implementation")
        self.assertEqual(t["rewrite_version"], "v1")


class Gate(unittest.TestCase):
    def _completing_square_path(self):
        return [
            {"title": "Introduction to Completing the Square", "course_type": "study_path_introduction"},
            {"title": "Understanding the Process of Completing the Square", "course_type": "process_walkthrough"},
            {"title": "Implementing Completing Square Worked Examples", "course_type": "coding_implementation"},
        ]

    def test_math_path_gets_no_coding_or_process(self):
        gated, tel = gate_topic_types_by_domain(self._completing_square_path(), "math")
        types = _types(gated)
        self.assertNotIn("coding_implementation", types)
        self.assertNotIn("process_walkthrough", types)          # loop scaffold forbidden for math
        self.assertIn("math_formula_method", types)             # process_walkthrough remapped to it
        self.assertIsNone(tel["routing_validation"])

    def test_coding_implementation_drops_when_covered(self):
        # the coding twin drops because process_walkthrough (remapped to math_formula_method) covers the subject
        gated, tel = gate_topic_types_by_domain(self._completing_square_path(), "math")
        self.assertEqual(tel["topics_dropped"], 1)
        self.assertEqual(len(gated), 2)

    def test_coding_path_is_noop(self):
        path = [{"title": "DFS Walkthrough", "course_type": "algorithm_walkthrough"},
                {"title": "Implementing DFS", "course_type": "coding_implementation"}]
        gated, tel = gate_topic_types_by_domain([dict(t) for t in path], "coding")
        self.assertEqual(_types(gated), ["algorithm_walkthrough", "coding_implementation"])

    def test_science_math_formula_method_gated_by_quantitative_center(self):
        # a science-FAMILY domain (physics): quantitative topic keeps math_formula_method
        quant = [{"title": "Calculate force using F = ma", "course_type": "math_formula_method"}]
        g1, _ = gate_topic_types_by_domain([dict(t) for t in quant], "physics")
        self.assertEqual(_types(g1), ["math_formula_method"])
        # a science-family domain (biology): qualitative topic is remapped to science_mechanism
        qual = [{"title": "Understand photosynthesis", "course_type": "math_formula_method"}]
        g2, _ = gate_topic_types_by_domain([dict(t) for t in qual], "biology")
        self.assertEqual(_types(g2), ["science_mechanism"])

    def test_expository_domain_forbids_stem_types(self):
        # economics (expository family): a stray math_formula_method topic remaps to concept_intuition
        path = [{"title": "Supply and Demand", "course_type": "math_formula_method"}]
        gated, _ = gate_topic_types_by_domain([dict(t) for t in path], "economics")
        self.assertEqual(_types(gated), ["concept_intuition"])

    def test_coarse_override_domains_route_like_their_family(self):
        # a user override may name a family directly ("science") or the wizard alias ("concept") — the gate must
        # route it exactly like an inferred fine domain of that family.
        quant = [{"title": "Calculate force using F = ma", "course_type": "math_formula_method"}]
        g_science, _ = gate_topic_types_by_domain([dict(t) for t in quant], "science")
        self.assertEqual(_types(g_science), ["math_formula_method"])   # science family keeps quantitative formula
        stem = [{"title": "Supply and Demand", "course_type": "math_formula_method"}]
        g_concept, tel = gate_topic_types_by_domain([dict(t) for t in stem], "concept")
        self.assertEqual(tel["gate_family"], "expository")
        self.assertEqual(_types(g_concept), ["concept_intuition"])     # concept alias == expository family

    def test_mixed_and_unknown_are_noops(self):
        path = [{"title": "X", "course_type": "coding_implementation"}]
        for d in ("mixed", "unknown"):
            gated, tel = gate_topic_types_by_domain([dict(t) for t in path], d)
            self.assertEqual(_types(gated), ["coding_implementation"], d)
            self.assertEqual(tel["gate_family"], "")

    def test_native_coverage_recovery(self):
        # a math path left with only universal types recovers by relabeling the first non-intro topic
        path = [{"title": "Intro", "course_type": "study_path_introduction"},
                {"title": "Key Terms", "course_type": "terminology_components"}]
        gated, tel = gate_topic_types_by_domain([dict(t) for t in path], "math")
        self.assertTrue(any(t.get("course_type") in teaching_types_for("math") for t in gated))
        self.assertTrue(tel["coverage_recovered"])

    def test_no_native_teaching_type_fails_validation(self):
        # only an intro, nothing to recover -> routing_validation
        path = [{"title": "Intro", "course_type": "study_path_introduction"}]
        _, tel = gate_topic_types_by_domain([dict(t) for t in path], "math")
        self.assertEqual(tel["routing_validation"], "no_native_teaching_type")


if __name__ == "__main__":
    unittest.main()
