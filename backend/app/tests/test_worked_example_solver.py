"""Problem-first LLM worked-example solver (Slice 1: full text breakdown + completion).

A non-code topic's worked example is replaced by a single focused solve rendered as a
setup card + one card per step, with the last card carrying the final answer and stamped
reaches_final_answer. Asserted by behavior; the LLM is a stub (no network).

Run: python -m unittest app.tests.test_worked_example_solver
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.solver import (
    _build_solution_cards,
    apply_llm_solved_worked_example,
    solve_worked_example,
)
from app.services.examples.worked_example_audit import audit_worked_examples


def _stub(payload):
    # A complete, concrete solution in the `cards` contract — what a focused solve returns.
    return {
        "problem": "Solve 2x^2 - 4x - 6 = 0 for x.",
        "problem_visual": "The equation 2x^2 - 4x - 6 = 0 centered, with a, b, c labeled below.",
        "cards": [
            {"title": "Identify coefficients", "points": ["Read off a, b, c:", "  - a = 2, b = -4, c = -6."],
             "visual": "The three coefficients a=2, b=-4, c=-6 boxed under the equation."},
            {"title": "Compute the discriminant",
             "points": ["Discriminant:", "  - b^2 - 4ac = 16 + 48 = 64.", "  - sqrt(64) = 8."],
             "visual": "b^2 - 4ac written out as 16 + 48 = 64, with sqrt(64)=8 highlighted."},
            {"title": "Apply the formula", "points": ["Two roots:", "  - x = (4 ± 8) / 4."],
             "visual": "x = (4 ± 8)/4 splitting into two branches for + and -."},
        ],
        "final_answer": "x = 3 or x = -1",
    }


def _steps_stub(payload):
    # Robustness: the model used the legacy steps/detail shape instead of cards.
    return {
        "problem": "Compute the mean of 2, 4, 9.",
        "steps": [{"title": "Sum", "detail": ["2 + 4 + 9 = 15."]},
                  {"title": "Divide", "detail": ["15 / 3 = 5."]}],
        "final_answer": "5",
    }


def _bad_stub(payload):
    return {"problem": "x", "cards": [], "final_answer": ""}  # nothing to render


def _lesson():
    return {
        "lesson_cards": [
            {"blueprint_key": "background", "title": "Intro"},
            {"blueprint_key": "worked_example", "title": "Example", "points": ["A rushed half-example."]},
            {"blueprint_key": "practice", "title": "Practice"},
        ],
        "metadata": {},
    }


class TestSolve(unittest.TestCase):
    def test_solve_normalizes_shape(self):
        sol = solve_worked_example({"title": "Quadratics"}, solver=_stub)
        self.assertEqual(sol["final_answer"], "x = 3 or x = -1")
        self.assertEqual(len(sol["cards"]), 3)

    def test_steps_fallback_shape(self):
        sol = solve_worked_example({"title": "Mean"}, solver=_steps_stub)
        self.assertEqual(len(sol["cards"]), 2)
        self.assertEqual(sol["cards"][0]["points"], ["2 + 4 + 9 = 15."])

    def test_empty_solution_is_none(self):
        self.assertIsNone(solve_worked_example({"title": "X"}, solver=_bad_stub))

    def test_cards_have_setup_and_final(self):
        sol = solve_worked_example({"title": "Quadratics"}, solver=_stub)
        cards = _build_solution_cards(sol, {"id": "t1"})
        self.assertGreaterEqual(len(cards), 4)                 # setup + 3 steps
        self.assertTrue(cards[0]["metadata"].get("worked_example_setup"))
        self.assertIn("2x^2 - 4x - 6", cards[0]["points"][0])
        # subpoint formatting preserved
        self.assertTrue(any(p.startswith("  - ") for c in cards for p in c["points"]))
        # rich per-card visual description carried (Phase-2 foundation)
        self.assertIn("a, b, c", cards[0]["visual_description"])      # setup uses problem_visual
        self.assertTrue(all(c.get("visual_description") for c in cards))
        last = cards[-1]
        self.assertTrue(last["metadata"].get("reaches_final_answer"))
        self.assertTrue(any("Final answer: x = 3 or x = -1" in p for p in last["points"]))


class TestCoding(unittest.TestCase):
    def test_coding_uses_code_system_and_attaches_ide_code(self):
        seen = {}

        def capture(payload):
            seen["system"] = payload.get("system")
            seen["user"] = payload.get("user")
            return {
                "problem": "Sort [5, 2, 8].",
                "cards": [
                    {"title": "Split", "points": ["We split the array into halves."], "visual": "two halves"},
                    {"title": "Merge", "points": ["We merge them in order."], "visual": "merged"},
                ],
                "final_answer": "[2, 5, 8]",
            }

        code = "def merge_sort(arr):\n    return sorted(arr)"
        lesson = {
            "lesson_cards": [
                {"blueprint_key": "worked_example", "code_snippet": code, "points": ["old"]},
                {"blueprint_key": "practice"},
            ],
            "metadata": {},
        }
        applied = apply_llm_solved_worked_example(
            lesson, {"id": "c1", "title": "Merge Sort", "topic_type": "coding_implementation"}, solver=capture,
        )
        self.assertTrue(applied)
        self.assertIn("never", seen["system"].lower())        # coding system prompt used
        self.assertIn("line number", seen["system"].lower())  # forbids line numbers
        self.assertIn(code, seen["user"])                     # the code was handed to the solve
        we = [c for c in lesson["lesson_cards"] if c.get("blueprint_key") == "worked_example"]
        self.assertTrue(all(c.get("code_snippet") == code for c in we))  # IDE code on every card
        joined = " ".join(p for c in we for p in c.get("points", [])).lower()
        self.assertNotIn("line ", joined)                     # no "line N executes" in the text


class TestApply(unittest.TestCase):
    def test_replaces_worked_example_and_completes(self):
        lesson = _lesson()
        applied = apply_llm_solved_worked_example(lesson, {"id": "t1", "title": "Quadratics"}, solver=_stub)
        self.assertTrue(applied)
        keys = [c.get("blueprint_key") for c in lesson["lesson_cards"]]
        self.assertEqual(keys[0], "background")               # other cards preserved, in place
        self.assertEqual(keys[-1], "practice")
        we = [c for c in lesson["lesson_cards"] if c.get("blueprint_key") == "worked_example"]
        self.assertGreaterEqual(len(we), 4)
        self.assertNotIn("A rushed half-example.", [p for c in we for p in c.get("points", [])])
        # Completion is now guaranteed upstream — the audit sees nothing incomplete.
        report = audit_worked_examples(lesson, {"id": "t1"}, regenerate=None)
        self.assertEqual(report["status"], "complete")

    def test_failed_solve_leaves_lesson_untouched(self):
        lesson = _lesson()
        before = [dict(c) for c in lesson["lesson_cards"]]
        applied = apply_llm_solved_worked_example(lesson, {"id": "t1", "title": "X"}, solver=lambda p: None)
        self.assertFalse(applied)
        self.assertEqual(lesson["lesson_cards"], before)

    def test_topic_without_worked_example_is_skipped(self):
        lesson = {"lesson_cards": [{"blueprint_key": "background"}], "metadata": {}}
        self.assertFalse(apply_llm_solved_worked_example(lesson, {"id": "t1"}, solver=_stub))


if __name__ == "__main__":
    unittest.main()
