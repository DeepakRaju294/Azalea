"""app/services/prereq_relevance_classifier.py — is a claimed assumed_prerequisite actually true/necessary,
as opposed to §3.1's SCOPE question (which assumes the claim is true). All offline: every test injects a
fake model_fn, never a live LLM call.
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_prereq_relevance_classifier
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.prereq_relevance_classifier import (
    RELEVANCE_CLASSIFICATION_SYSTEM_PROMPT, classify_prereq_relevance,
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


class ClassifyPrereqRelevance(unittest.TestCase):
    def test_valid_round_trip_accepted(self):
        fn = _fn({"relevant": True, "rationale": "a genuine, specific sub-skill"})
        relevant, rationale = classify_prereq_relevance(
            canonical_name="line integrals", goal="learn Stokes' theorem", gloss="integrating along a curve",
            model_fn=fn)
        self.assertTrue(relevant)
        self.assertEqual(rationale, "a genuine, specific sub-skill")
        self.assertEqual(len(fn.calls), 1)

    def test_valid_round_trip_rejected(self):
        # The live bug this was built for: "vector calculus" as a prerequisite of a vector-calculus theorem.
        fn = _fn({"relevant": False, "rationale": "circular — restates the goal's own subject"})
        relevant, rationale = classify_prereq_relevance(
            canonical_name="vector calculus", goal="learn Stokes' theorem", model_fn=fn)
        self.assertFalse(relevant)
        self.assertEqual(rationale, "circular — restates the goal's own subject")

    def test_missing_relevant_field_fails_open(self):
        fn = _fn({"rationale": "no verdict given"})
        relevant, _ = classify_prereq_relevance(canonical_name="x", goal="g", model_fn=fn)
        self.assertTrue(relevant)

    def test_non_bool_relevant_field_fails_open(self):
        fn = _fn({"relevant": "yes", "rationale": "x"})   # a string, not a bool
        relevant, _ = classify_prereq_relevance(canonical_name="x", goal="g", model_fn=fn)
        self.assertTrue(relevant)

    def test_model_fn_raising_fails_open_never_propagates(self):
        def fn(payload):
            raise RuntimeError("simulated LLM failure")
        relevant, rationale = classify_prereq_relevance(canonical_name="x", goal="g", model_fn=fn)
        self.assertTrue(relevant)
        self.assertEqual(rationale, "")

    def test_non_dict_response_fails_open(self):
        for bad in (None, ["a", "list"], "a bare string", 42):
            with self.subTest(bad=bad):
                fn = _fn(bad)
                relevant, rationale = classify_prereq_relevance(canonical_name="x", goal="g", model_fn=fn)
                self.assertTrue(relevant)
                self.assertEqual(rationale, "")

    def test_non_string_rationale_is_coerced_to_empty(self):
        fn = _fn({"relevant": True, "rationale": None})
        _, rationale = classify_prereq_relevance(canonical_name="x", goal="g", model_fn=fn)
        self.assertEqual(rationale, "")

    def test_empty_goal_fails_open_with_zero_calls(self):
        fn = _fn({"relevant": False, "rationale": "x"})
        relevant, rationale = classify_prereq_relevance(canonical_name="x", goal="   ", model_fn=fn)
        self.assertTrue(relevant)
        self.assertEqual(rationale, "")
        self.assertEqual(len(fn.calls), 0)

    def test_empty_canonical_name_fails_open_with_zero_calls(self):
        fn = _fn({"relevant": False, "rationale": "x"})
        relevant, _ = classify_prereq_relevance(canonical_name="   ", goal="g", model_fn=fn)
        self.assertTrue(relevant)
        self.assertEqual(len(fn.calls), 0)

    def test_gloss_is_threaded_into_the_prompt(self):
        fn = _fn({"relevant": True, "rationale": "x"})
        classify_prereq_relevance(canonical_name="x", goal="g", gloss="a distinguishing gloss", model_fn=fn)
        self.assertIn("a distinguishing gloss", fn.calls[0]["user"])


class PromptDriftGuard(unittest.TestCase):
    def test_prompt_names_both_rejection_classes(self):
        for phrase in ("CIRCULAR", "UNRELATED"):
            self.assertIn(phrase, RELEVANCE_CLASSIFICATION_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
