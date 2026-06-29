"""Tests for the worked-example verification ladder (WORKED_EXAMPLE_ACCURACY_SPEC §3, Phase A1/A2).
Offline (no LLM): the determinate paths defer offline, so a computational topic yields guided_fallback —
proving the Phase-A1 invariant (a computational topic NEVER returns None → never the self-graded path)."""
import os
import unittest

from app.services.examples.accuracy_ladder import _enabled, solve_via_accuracy_ladder
from app.services.examples.guided_explanation import (_template_card, build_guided_explanation,
                                                      validate_guided_explanation)
from app.services.examples.task_classifier import classify_worked_example_task


class ClassifierTests(unittest.TestCase):
    def test_topic_with_adapter_is_determinate_resolved(self):
        # a walkthrough resolves to an adapter (the coding guard only blocks coding_implementation)
        task = classify_worked_example_task(
            {"title": "Understanding Kruskal's Algorithm", "topic_type": "algorithm_walkthrough"})
        self.assertEqual(task.task_kind, "deterministic_execution")
        self.assertEqual(task.classification_status, "resolved")
        self.assertTrue(task.is_determinate)
        self.assertEqual(task.classification_source, "deterministic_rule")
        self.assertEqual(task.evidence.get("adapter"), "kruskal")

    def test_computational_without_adapter_is_ambiguous(self):
        # Bellman-Ford has no adapter → computational but unsupported → ambiguous.
        task = classify_worked_example_task(
            {"title": "Implementing Bellman-Ford's Algorithm", "topic_type": "coding_implementation"})
        self.assertEqual(task.classification_status, "ambiguous")
        self.assertFalse(task.can_construct_valid_instance)        # no adapter to generate/verify
        self.assertTrue(task.has_executable_terminal_condition)    # still a computation

    def test_intro_is_conceptual_resolved(self):
        task = classify_worked_example_task(
            {"title": "Introduction to MST", "topic_type": "study_path_introduction"})
        self.assertEqual(task.task_kind, "conceptual_illustration")
        self.assertEqual(task.classification_status, "resolved")
        self.assertFalse(task.is_determinate)

    def test_unknown_is_unsupported(self):
        task = classify_worked_example_task({"title": "Mystery", "topic_type": "weird_type"})
        self.assertEqual(task.classification_status, "unsupported")


class GuidedContractTests(unittest.TestCase):
    def test_template_card_is_compliant(self):
        self.assertEqual(validate_guided_explanation(_template_card({"concept": "binary search"})), [])

    def test_specific_value_is_rejected(self):
        bad = {"goal": "", "reasoning": "next choose edge B-D with weight 4", "work": [], "result": ""}
        self.assertIn("contains_specific_value", validate_guided_explanation(bad))

    def test_step_n_is_rejected(self):
        bad = {"goal": "after step four... ", "reasoning": "see step 4", "work": [], "result": ""}
        self.assertIn("step_n_claim", validate_guided_explanation(bad))

    def test_build_guided_ships_a_compliant_card(self):
        r = build_guided_explanation({"title": "Prim's", "concept": "MST"}, reason="x")
        self.assertEqual(r["metadata"]["treatment"], "guided_fallback")
        self.assertEqual(r["metadata"]["verification_level"], "none")
        self.assertEqual(validate_guided_explanation(r["cards"][0]), [])   # whatever ships is compliant


class LadderRoutingTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("AZALEA_WORKED_EXAMPLE_REASON_EXTRACT", None)   # Tier 2 off → offline determinate → guided

    def test_flag_default_off(self):
        os.environ.pop("AZALEA_WORKED_EXAMPLE_ACCURACY_LADDER", None)
        self.assertFalse(_enabled())

    def test_conceptual_topic_defers(self):
        r = solve_via_accuracy_ladder({"title": "Intro to MST", "topic_type": "study_path_introduction"})
        self.assertIsNone(r)   # defer to the existing non-verified card path

    def test_unsupported_topic_gets_guided(self):
        r = solve_via_accuracy_ladder({"title": "Mystery", "topic_type": "weird"})
        self.assertIsNotNone(r)
        self.assertEqual(r["metadata"]["treatment"], "guided_fallback")
        self.assertEqual(r["metadata"]["withhold_reason"], "unsupported")

    def test_determinate_coding_topic_never_returns_none(self):
        # THE Phase-A1 FIX: Prim coding is computational → must not fall to the self-graded path.
        # ADAPTER_AND_GENERATION_SYSTEM_SPEC §1.2: the verified-trace tier now ships a trace-preserving
        # narration even offline (no LLM needed), so this determinate adapter-supported topic gets Tier 1
        # (hard) — STRONGER than the old offline guided_fallback, and still never None / never self-graded.
        r = solve_via_accuracy_ladder(
            {"title": "Implementing Prim's Algorithm", "topic_type": "coding_implementation"})
        self.assertIsNotNone(r)
        self.assertEqual(r["metadata"]["treatment"], "hard")
        self.assertEqual(r["metadata"]["verification_level"], "hard_trace")


if __name__ == "__main__":
    unittest.main()
