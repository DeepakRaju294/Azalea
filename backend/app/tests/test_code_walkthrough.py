"""The line-explainer rebuilds coding code_walkthrough cards as one bullet + one single-line
highlight per code line, one card per logical block, complete code on every card.

Asserted by behavior; the explainer is a stub (no network).

Run: python -m unittest app.tests.test_code_walkthrough
"""
from __future__ import annotations

import os
import re
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.code_walkthrough import (
    _walkthrough_blocks,
    apply_line_explained_walkthrough,
    explain_lines,
)

CODE = (
    "def merge_sort(arr):\n"
    "    if len(arr) <= 1:\n"
    "        return arr\n"
    "    mid = len(arr) // 2\n"
    "    left = merge_sort(arr[:mid])\n"
    "    right = merge_sort(arr[mid:])\n"
    "    return merge(left, right)\n"
    "\n"
    "def merge(left, right):\n"
    "    merged = []\n"
    "    return merged\n"
)


def _explainer(payload):
    # One sentence per non-blank line, keyed by the line numbers we were given.
    numbered = [ln for ln in str(payload.get("code")).split("\n")]
    items = []
    for i, ln in enumerate(numbered, start=1):
        if ln.strip():
            items.append({"line": i, "text": f"Plain-English explanation of line {i}."})
    return {"explanations": items}


def _short_explainer(payload):
    return {"explanations": [{"line": 1, "text": "only the first line"}]}  # incomplete coverage


def _skip_one_explainer(payload):
    # Covers every non-blank line EXCEPT line 6 (the near-identical-line case the model fumbles).
    numbered = str(payload.get("code")).split("\n")
    items = [
        {"line": i, "text": f"Plain-English explanation of line {i}."}
        for i, ln in enumerate(numbered, start=1)
        if ln.strip() and i != 6
    ]
    return {"explanations": items}


class TestBlocks(unittest.TestCase):
    def test_blocks_break_on_blank_and_new_def(self):
        blocks = _walkthrough_blocks(CODE)
        # merge_sort body (7 lines, capped at 6 -> 6 + 1), then merge (2 lines).
        all_lines = [ln for b in blocks for ln in b]
        self.assertEqual(all_lines, sorted(all_lines))          # ascending, no reordering
        self.assertNotIn(8, all_lines)                          # the blank line is excluded
        self.assertEqual(all_lines, [1, 2, 3, 4, 5, 6, 7, 9, 10, 11])
        # the new `def merge` starts its own block
        merge_block = next(b for b in blocks if 9 in b)
        self.assertEqual(merge_block, [9, 10, 11])

    def test_long_block_split_to_max(self):
        blocks = _walkthrough_blocks(CODE)
        self.assertTrue(all(len(b) <= 6 for b in blocks))


class TestExplainLines(unittest.TestCase):
    def test_full_coverage(self):
        out = explain_lines(CODE, explainer=_explainer)
        self.assertIsNotNone(out)
        # every non-blank line covered; the blank line (8) absent
        self.assertEqual(set(out), {1, 2, 3, 4, 5, 6, 7, 9, 10, 11})

    def test_incomplete_coverage_is_none(self):
        self.assertIsNone(explain_lines(CODE, explainer=_short_explainer))

    def test_single_gap_is_filled_not_discarded(self):
        # One missing line must NOT discard every good explanation (that bail left the broken
        # lean single-card walkthrough behind). The gap is filled deterministically instead.
        out = explain_lines(CODE, explainer=_skip_one_explainer)
        self.assertIsNotNone(out)
        self.assertEqual(set(out), {1, 2, 3, 4, 5, 6, 7, 9, 10, 11})  # full per-line coverage
        self.assertTrue(out[6])                                       # line 6 filled, not empty
        self.assertEqual(out[1], "Plain-English explanation of line 1.")  # model wording kept


class TestApply(unittest.TestCase):
    def _lesson(self):
        return {
            "lesson_cards": [
                {"blueprint_key": "components_terms", "title": "Key terms"},
                {"blueprint_key": "code_walkthrough", "title": "old summary",
                 "code_snippet": CODE, "points": ["Vague summary 1", "Vague summary 2"]},
                {"blueprint_key": "worked_example", "code_snippet": CODE},
            ],
            "metadata": {},
        }

    def test_rebuilds_one_bullet_and_one_line_highlight_per_line(self):
        lesson = self._lesson()
        applied = apply_line_explained_walkthrough(
            lesson, {"id": "c1", "title": "Merge Sort", "topic_type": "coding_implementation"},
            explainer=_explainer,
        )
        self.assertTrue(applied)
        wt = [c for c in lesson["lesson_cards"] if c.get("blueprint_key") == "code_walkthrough"]
        self.assertGreaterEqual(len(wt), 2)  # split into blocks, not one collapsed card
        for c in wt:
            pts = c["points"]
            hl = c["highlight_lines_per_step"]
            self.assertEqual(len(pts), len(hl))            # one bullet per highlight
            self.assertTrue(all(r[0] == r[1] for r in hl))  # every highlight is a SINGLE line
            self.assertEqual(c["code_snippet"], CODE)       # complete code on every card
            # no raw-code main bullets (all are plain sentences from the explainer)
            self.assertTrue(all(not re.search(r"def |return |==|\[\]", p) for p in pts))
        # other cards preserved and order intact (terms before walkthrough before example)
        keys = [c.get("blueprint_key") for c in lesson["lesson_cards"]]
        self.assertEqual(keys[0], "components_terms")
        self.assertEqual(keys[-1], "worked_example")

    def test_inserts_when_no_walkthrough_exists(self):
        lesson = {
            "lesson_cards": [
                {"blueprint_key": "components_terms", "title": "Key terms"},
                {"blueprint_key": "worked_example", "code_snippet": CODE},
            ],
            "metadata": {},
        }
        applied = apply_line_explained_walkthrough(
            lesson, {"id": "c1", "title": "Merge Sort", "topic_type": "coding_implementation"},
            explainer=_explainer,
        )
        self.assertTrue(applied)
        keys = [c.get("blueprint_key") for c in lesson["lesson_cards"]]
        self.assertIn("code_walkthrough", keys)
        # inserted BEFORE the worked_example
        self.assertLess(keys.index("code_walkthrough"), keys.index("worked_example"))

    def test_bails_on_incomplete_explanations(self):
        lesson = self._lesson()
        before = [dict(c) for c in lesson["lesson_cards"]]
        applied = apply_line_explained_walkthrough(
            lesson, {"id": "c1", "title": "Merge Sort", "topic_type": "coding_implementation"},
            explainer=_short_explainer,
        )
        self.assertFalse(applied)
        self.assertEqual(lesson["lesson_cards"], before)  # untouched

    def test_non_coding_skipped(self):
        lesson = self._lesson()
        self.assertFalse(apply_line_explained_walkthrough(
            lesson, {"id": "c1", "title": "X", "topic_type": "concept_intuition"}, explainer=_explainer,
        ))


if __name__ == "__main__":
    unittest.main()
