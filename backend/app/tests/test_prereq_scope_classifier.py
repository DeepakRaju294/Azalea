"""app/services/prereq_scope_classifier.py — the §3.1/§6.1 real classifier + §3 deterministic target_goal
builder. All offline: every test injects a fake model_fn, never a live LLM call.
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_prereq_scope_classifier
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core.prereq_links import ScopeRule
from app.services.prereq_scope_classifier import (
    SCOPE_CLASSIFICATION_SYSTEM_PROMPT, build_prerequisite_goal, classify_recommended_scope_rule,
)


def _fn(result):
    calls = []

    def fn(payload):
        calls.append(payload)
        if callable(result):
            return result(payload)
        return result
    fn.calls = calls
    return fn


class ClassifyRecommendedScopeRule(unittest.TestCase):
    def test_valid_round_trip(self):
        fn = _fn({"scope_rule": "beginner_minimum_sequence", "scope_rationale": "part of the minimum sequence"})
        rule, rationale = classify_recommended_scope_rule(
            canonical_name="Voltage", goal="Learn basic DC circuits from scratch", domain="physics",
            candidate_kind="taught_foundation", model_fn=fn)
        self.assertEqual(rule, ScopeRule.beginner_minimum_sequence)
        self.assertEqual(rationale, "part of the minimum sequence")
        self.assertEqual(len(fn.calls), 1)

    def test_missing_scope_rule_falls_back(self):
        fn = _fn({"scope_rationale": "no rule given"})
        rule, rationale = classify_recommended_scope_rule(
            canonical_name="Voltage", goal="g", domain="physics", candidate_kind="assumed_prerequisite",
            model_fn=fn)
        self.assertEqual(rule, ScopeRule.recognition_only_fallback)

    def test_invalid_scope_rule_string_falls_back(self):
        fn = _fn({"scope_rule": "not_a_real_rule", "scope_rationale": "x"})
        rule, _ = classify_recommended_scope_rule(
            canonical_name="Voltage", goal="g", domain="physics", candidate_kind="assumed_prerequisite",
            model_fn=fn)
        self.assertEqual(rule, ScopeRule.recognition_only_fallback)

    def test_model_fn_raising_falls_back_never_propagates(self):
        def fn(payload):
            raise RuntimeError("simulated LLM failure")
        rule, rationale = classify_recommended_scope_rule(
            canonical_name="Voltage", goal="g", domain="physics", candidate_kind="assumed_prerequisite",
            model_fn=fn)
        self.assertEqual(rule, ScopeRule.recognition_only_fallback)
        self.assertEqual(rationale, "")

    def test_non_dict_response_falls_back(self):
        for bad in (None, ["a", "list"], "a bare string", 42):
            with self.subTest(bad=bad):
                fn = _fn(bad)
                rule, rationale = classify_recommended_scope_rule(
                    canonical_name="Voltage", goal="g", domain="physics", candidate_kind="assumed_prerequisite",
                    model_fn=fn)
                self.assertEqual(rule, ScopeRule.recognition_only_fallback)
                self.assertEqual(rationale, "")

    def test_non_string_rationale_is_coerced_to_empty(self):
        fn = _fn({"scope_rule": "recognition_only_fallback", "scope_rationale": None})
        _, rationale = classify_recommended_scope_rule(
            canonical_name="Voltage", goal="g", domain="physics", candidate_kind="assumed_prerequisite",
            model_fn=fn)
        self.assertEqual(rationale, "")

    def test_empty_goal_short_circuits_with_zero_calls(self):
        fn = _fn({"scope_rule": "explicit_objective", "scope_rationale": "x"})
        rule, rationale = classify_recommended_scope_rule(
            canonical_name="Voltage", goal="   ", domain="physics", candidate_kind="assumed_prerequisite",
            model_fn=fn)
        self.assertEqual(rule, ScopeRule.recognition_only_fallback)
        self.assertEqual(rationale, "")
        self.assertEqual(len(fn.calls), 0)   # never called at all

    def test_candidate_kind_frames_the_prompt_differently(self):
        fn = _fn({"scope_rule": "recognition_only_fallback", "scope_rationale": "x"})
        classify_recommended_scope_rule(canonical_name="Voltage", goal="g", domain="physics",
                                        candidate_kind="taught_foundation", model_fn=fn)
        classify_recommended_scope_rule(canonical_name="Voltage", goal="g", domain="physics",
                                        candidate_kind="assumed_prerequisite", model_fn=fn)
        self.assertNotEqual(fn.calls[0]["user"], fn.calls[1]["user"])


class PromptDriftGuard(unittest.TestCase):
    def test_prompt_names_every_rule_and_the_fallback(self):
        # A drift tripwire, not a byte-identity check: catches an edit that silently drops a rule.
        for phrase in ("explicit_objective", "beginner_minimum_sequence", "competency_required",
                       "source_or_user_objective", "recognition_only_fallback"):
            self.assertIn(phrase, SCOPE_CLASSIFICATION_SYSTEM_PROMPT)


class BuildPrerequisiteGoal(unittest.TestCase):
    def test_non_empty_and_contains_name_and_context(self):
        goal = build_prerequisite_goal("Voltage", "physics", "Ohm's law")
        self.assertTrue(goal)
        self.assertIn("voltage", goal.lower())
        self.assertIn("Ohm's law", goal)
        self.assertIn("physics", goal)

    def test_degrades_gracefully_with_empty_context_and_domain(self):
        goal = build_prerequisite_goal("Voltage", "", "")
        self.assertTrue(goal)
        self.assertIn("voltage", goal.lower())

    def test_empty_name_still_produces_non_empty_goal(self):
        goal = build_prerequisite_goal("", "physics", "Ohm's law")
        self.assertTrue(goal)

    def test_acronym_casing_preserved(self):
        goal = build_prerequisite_goal("DNS", "networking", "web basics")
        self.assertIn("DNS", goal)
        self.assertNotIn("dNS", goal)


if __name__ == "__main__":
    unittest.main()
