"""Example blueprint validation: Goal/Reasoning/Work/Result structure + completeness + coverage.

Each step carries concrete `work` (a list of lines) and a `result`, plus optional goal/reasoning
and cases_covered. The blueprint validates structure (every step has concrete work + a result and
advances — no no-op), completeness (enough steps, reaches the expected final answer), and coverage
(required_cases exercised), stamping a nested example_status. Deterministic, no LLM.

Run: python -m unittest app.tests.test_example_blueprint
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.example_blueprint import DEFAULT_MIN_STEPS, stamp_example_metadata


def _setup():
    return {"blueprint_key": "worked_example", "points": ["Problem:", "  - Sort [5, 2, 8]."],
            "metadata": {"worked_example_setup": True}}


def _step(work, result, *, cases=None, final=False):
    meta = {}
    if final:
        meta["final_answer"] = result
    if cases:
        meta["cases_covered"] = cases
    return {"blueprint_key": "worked_example",
            "work": work if isinstance(work, list) else [work],
            "result": result, "metadata": meta}


def _cards(n_steps, *, setup=True, no_op_last=False, missing_last=False, cases_on_last=None):
    cards = []
    if setup:
        cards.append(_setup())
    for i in range(n_steps):
        last = i == n_steps - 1
        if last and missing_last:
            cards.append({"blueprint_key": "worked_example", "work": [], "result": "", "metadata": {}})
        elif last and no_op_last:
            prev = i - 1  # identical work + result to the previous step -> no-op
            cards.append(_step([f"act {prev}"], f"state {prev + 1}"))
        else:
            cards.append(_step([f"act {i}"], "[2, 5, 8]" if last else f"state {i + 1}",
                               final=last, cases=cases_on_last if last else None))
    return cards


class TestBlueprintValidation(unittest.TestCase):
    def test_complete_example(self):
        status = stamp_example_metadata(_cards(DEFAULT_MIN_STEPS), expected_final_answer="[2, 5, 8]")
        self.assertTrue(status["complete"], status)
        self.assertTrue(status["completeness"]["finished"])
        self.assertFalse(status["completeness"]["skipped"])
        self.assertEqual(status["structure"]["field_issues"], [])

    def test_too_few_steps_flags_skipped(self):
        status = stamp_example_metadata(_cards(2), expected_final_answer="[2, 5, 8]")
        self.assertTrue(status["completeness"]["skipped"])
        self.assertEqual(status["reason"], "steps_skipped")

    def test_expected_min_steps_overrides_default(self):
        status = stamp_example_metadata(_cards(6), expected_final_answer="[2, 5, 8]", expected_min_steps=10)
        self.assertTrue(status["completeness"]["skipped"])

    def test_missing_step_field_flagged(self):
        status = stamp_example_metadata(_cards(DEFAULT_MIN_STEPS, missing_last=True), expected_final_answer="[2, 5, 8]")
        self.assertTrue(status["structure"]["field_issues"])
        self.assertIn(status["reason"], {"missing_work", "missing_result"})

    def test_no_op_step_flagged(self):
        status = stamp_example_metadata(_cards(DEFAULT_MIN_STEPS, no_op_last=True), expected_final_answer="[2, 5, 8]")
        self.assertTrue(status["progression"]["no_op_steps"])
        self.assertEqual(status["reason"], "no_op_step")

    def test_missing_work_flagged(self):
        cards = _cards(DEFAULT_MIN_STEPS)
        cards[2]["work"] = []  # drop the concrete work on one step
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]")
        self.assertEqual(status["reason"], "missing_work")

    def test_non_concrete_work_flagged(self):
        cards = _cards(DEFAULT_MIN_STEPS)
        cards[2]["work"] = ["Apply the formula."]
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]")
        self.assertEqual(status["reason"], "non_concrete_work")

    def test_coding_algorithmic_step_flagged(self):
        cards = [_setup()]
        for i in range(DEFAULT_MIN_STEPS):
            last = i == DEFAULT_MIN_STEPS - 1
            work = ["The array is split into two halves"] if i == 2 else [f"arr[:{i}] = [{i}]"]
            cards.append(_step(work, "[2, 5, 8]" if last else f"left = [{i}]", final=last))
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]", coding=True)
        self.assertEqual(status["progression"]["algorithmic_steps"], [3])  # step 3 = prose, no code
        self.assertEqual(status["reason"], "algorithmic_not_implementation")

    def test_coding_code_anchored_not_flagged(self):
        cards = [_setup()]
        for i in range(DEFAULT_MIN_STEPS):
            last = i == DEFAULT_MIN_STEPS - 1
            cards.append(_step([f"left = arr[:{i}]", f"left = [{i}]"],
                               "[2, 5, 8]" if last else f"left = [{i}]", final=last))
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]", coding=True)
        self.assertEqual(status["progression"]["algorithmic_steps"], [])

    def test_inconsistent_merge_flagged(self):
        cards = _cards(DEFAULT_MIN_STEPS)
        cards[2]["work"] = ["[5, 32] + [32, 62] => [5, 7, 23, 32, 32, 34, 62]"]  # inputs != output
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]")
        self.assertTrue(status["progression"]["inconsistent_steps"])
        self.assertEqual(status["reason"], "inconsistent_step")

    def test_correct_merge_not_flagged(self):
        cards = _cards(DEFAULT_MIN_STEPS)
        cards[2]["work"] = ["compare 5 and 3 -> 3 < 5 -> append 3", "[5] + [3] => [3, 5]"]
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]")
        self.assertEqual(status["progression"]["inconsistent_steps"], [])

    def test_does_not_finish(self):
        cards = _cards(DEFAULT_MIN_STEPS)
        cards[-1]["result"] = "still working"
        cards[-1]["metadata"]["final_answer"] = "still working"
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]")
        self.assertFalse(status["completeness"]["finished"])
        self.assertEqual(status["reason"], "did_not_finish")

    def test_missing_required_case_flagged(self):
        status = stamp_example_metadata(_cards(DEFAULT_MIN_STEPS), expected_final_answer="[2, 5, 8]",
                                        required_cases=("leftover tail", "base case"))
        self.assertEqual(status["coverage"]["missing"], ["leftover tail", "base case"])
        self.assertEqual(status["reason"], "missing_required_case")

    def test_required_cases_covered(self):
        cards = _cards(DEFAULT_MIN_STEPS, cases_on_last=["leftover tail"])
        cards[1]["metadata"]["cases_covered"] = ["base case"]
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]",
                                        required_cases=("leftover tail", "base case"))
        self.assertEqual(status["coverage"]["missing"], [])
        self.assertTrue(status["complete"])

    def test_repeated_non_adjacent_step_flagged(self):
        cards = _cards(DEFAULT_MIN_STEPS)
        # make step 4 a copy of step 1 (non-adjacent) -> repeated_step, not no_op
        cards[4]["work"] = list(cards[1]["work"])
        cards[4]["result"] = cards[1]["result"]
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]")
        self.assertTrue(status["progression"]["repeated_steps"])
        self.assertEqual(status["reason"], "repeated_step")

    def test_missing_visible_conclusion_flagged(self):
        cards = _cards(DEFAULT_MIN_STEPS)
        # hidden answer reached, but the visible result does not state it
        cards[-1]["result"] = "the algorithm terminates"
        cards[-1]["metadata"]["final_answer"] = "[2, 5, 8]"
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]")
        self.assertTrue(status["completeness"]["finished"])
        self.assertFalse(status["completeness"]["visible_conclusion"])
        self.assertEqual(status["reason"], "missing_visible_conclusion")

    def test_issues_list_collects_all(self):
        cards = _cards(DEFAULT_MIN_STEPS)
        cards[2]["work"] = []  # a field issue
        status = stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]",
                                        required_cases=("uncovered case",))
        codes = {i["code"] for i in status["issues"]}
        self.assertIn("missing_work", codes)
        self.assertIn("missing_required_case", codes)

    def test_allow_short_example(self):
        status = stamp_example_metadata(_cards(2), expected_final_answer="[2, 5, 8]", allow_short_example=True)
        self.assertFalse(status["completeness"]["skipped"])
        self.assertTrue(status["complete"])

    def test_setup_metadata_stamped(self):
        cards = _cards(DEFAULT_MIN_STEPS)
        stamp_example_metadata(cards, expected_final_answer="[2, 5, 8]", expected_min_steps=6,
                               required_cases=("c1",))
        setup = cards[0]["metadata"]
        self.assertEqual(setup["expected_final_answer"], "[2, 5, 8]")
        self.assertEqual(setup["expected_min_steps"], 6)
        self.assertEqual(setup["required_cases"], ["c1"])


if __name__ == "__main__":
    unittest.main()
