"""Broken coding-implementation code is detected and replaced by a clean regeneration.

The merge-sort code shipped by the incremental walkthrough used `left`/`right` without ever
assigning them — that must be caught and repaired with a validated LLM regeneration. Valid
code is left alone. Asserted by behavior; the generator is a stub (no network).

Run: python -m unittest app.tests.test_code_repair
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.code_repair import (
    apply_clean_code_to_lesson,
    code_has_undefined_names,
    generate_clean_code,
)

BROKEN = '''def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left_sorted = merge_sort(left)
    right_sorted = merge_sort(right)'''

GOOD = '''def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = arr[:mid]
    right = arr[mid:]
    return merge(merge_sort(left), merge_sort(right))


def merge(left, right):
    return sorted(left + right)'''


def _good_gen(payload):
    return {"code": GOOD}


def _bad_gen(payload):
    return {"code": BROKEN}  # still broken — must be rejected


class TestUndefinedNames(unittest.TestCase):
    def test_broken_code_flagged(self):
        self.assertTrue(code_has_undefined_names(BROKEN))   # left/right never assigned

    def test_good_code_not_flagged(self):
        self.assertFalse(code_has_undefined_names(GOOD))

    def test_syntax_error_flagged(self):
        self.assertTrue(code_has_undefined_names("def f(:\n  pass"))

    def test_no_function_flagged(self):
        self.assertTrue(code_has_undefined_names("x = 1"))


class TestRegenerate(unittest.TestCase):
    def test_generate_validates_output(self):
        self.assertEqual(generate_clean_code({"title": "Merge Sort"}, generator=_good_gen), GOOD)

    def test_generate_rejects_still_broken(self):
        self.assertIsNone(generate_clean_code({"title": "Merge Sort"}, generator=_bad_gen))


class TestApply(unittest.TestCase):
    def _lesson(self, code):
        return {
            "lesson_cards": [
                {"blueprint_key": "code_walkthrough", "code_snippet": code, "highlight_lines_per_step": [[1, 1]]},
                {"blueprint_key": "worked_example", "code_snippet": code},
                {"blueprint_key": "practice"},
            ],
            "metadata": {},
        }

    def test_broken_code_repaired_on_all_cards(self):
        lesson = self._lesson(BROKEN)
        applied = apply_clean_code_to_lesson(
            lesson, {"id": "c1", "title": "Merge Sort", "topic_type": "coding_implementation"}, generator=_good_gen,
        )
        self.assertTrue(applied)
        code_cards = [c for c in lesson["lesson_cards"] if c.get("code_snippet")]
        self.assertTrue(all(c["code_snippet"] == GOOD for c in code_cards))
        self.assertEqual(code_cards[0]["highlight_lines_per_step"], [])  # stale highlights cleared

    def test_valid_code_left_alone(self):
        lesson = self._lesson(GOOD)
        applied = apply_clean_code_to_lesson(
            lesson, {"id": "c1", "title": "Merge Sort", "topic_type": "coding_implementation"}, generator=_good_gen,
        )
        self.assertFalse(applied)

    def test_walkthrough_broken_worked_example_good_unifies_to_good(self):
        # The real bug: walkthrough has broken code, worked example has the correct full code.
        # No regeneration needed — the broken card must adopt the valid longest snippet.
        lesson = {
            "lesson_cards": [
                {"blueprint_key": "code_walkthrough", "code_snippet": BROKEN},
                {"blueprint_key": "worked_example", "code_snippet": GOOD},
            ],
            "metadata": {},
        }

        def _no_gen(payload):
            raise AssertionError("should not regenerate when a valid snippet exists")

        applied = apply_clean_code_to_lesson(
            lesson, {"id": "c1", "title": "Merge Sort", "topic_type": "coding_implementation"}, generator=_no_gen,
        )
        self.assertTrue(applied)
        self.assertTrue(all(c.get("code_snippet") == GOOD for c in lesson["lesson_cards"] if c.get("code_snippet")))

    def test_non_coding_topic_skipped(self):
        lesson = self._lesson(BROKEN)
        self.assertFalse(apply_clean_code_to_lesson(
            lesson, {"id": "c1", "title": "X", "topic_type": "concept_intuition"}, generator=_good_gen,
        ))


if __name__ == "__main__":
    unittest.main()
