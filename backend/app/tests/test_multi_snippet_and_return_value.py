"""Combine separate code_snippets + use the real return value for "Final result".

An algorithm whose helper lives in a SEPARATE card (merge sort's `merge`) must still
trace end-to-end; and the terminal card's "Final result" must be the function's ACTUAL
return value, not a hardcoded-name accumulator guess (which missed `sorted_array` and
shipped "Final result: []"). Asserted by behavior, not topic.

Run: python -m unittest app.tests.test_multi_snippet_and_return_value
"""
from __future__ import annotations

import os
import sys
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")
os.environ["AZALEA_VISUAL_V2_MODES"] = "all"
for _name in ("dotenv", "openai"):
    if _name not in sys.modules:
        try:
            __import__(_name)
        except ImportError:
            _m = types.ModuleType(_name)
            if _name == "dotenv":
                _m.load_dotenv = lambda *a, **k: None
            else:
                _m.OpenAI = lambda *a, **k: object()
                for _e in ("APIError", "RateLimitError", "APITimeoutError", "APIConnectionError"):
                    setattr(_m, _e, type(_e, (Exception,), {}))
            sys.modules[_name] = _m

from app.services.visual_v2.code_lesson_integration import (
    _extract_code_and_entry,
    apply_code_execution_to_lesson,
)
from app.services.visual_v2.simulators.code_tracer import _returned_vars

# merge_sort recursion and its `merge` helper in SEPARATE cards. The helper uses an
# accumulator named `sorted_array` (not in the conventional-name list) and pop(0).
MERGE_SORT = '''def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return merge(left, right)'''

MERGE_HELPER = '''def merge(left, right):
    sorted_array = []
    while left and right:
        if left[0] < right[0]:
            sorted_array.append(left.pop(0))
        else:
            sorted_array.append(right.pop(0))
    sorted_array.extend(left)
    sorted_array.extend(right)
    return sorted_array'''


def _two_card_lesson():
    return {
        "lesson_cards": [
            {"blueprint_key": "worked_example", "code_snippet": MERGE_SORT,
             "points": ["Sort the array [38, 27, 43, 3, 9, 82, 10] using merge sort."]},
            {"blueprint_key": "code_walkthrough", "code_snippet": MERGE_HELPER},
        ],
        "visual_models": [],
    }


class TestCombineSnippets(unittest.TestCase):
    def setUp(self):
        # Pin the flag — another suite's tearDown can pop it, gating apply_code_execution.
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"

    def test_entry_is_call_graph_root(self):
        code, entry = _extract_code_and_entry(_two_card_lesson())
        self.assertEqual(entry, "merge_sort")              # the root, not the `merge` helper
        self.assertIn("def merge_sort", code)
        self.assertIn("def merge(", code)                  # helper combined in

    def test_complete_example_reaches_real_sorted_result(self):
        lesson = _two_card_lesson()
        applied = apply_code_execution_to_lesson(
            lesson, {"id": "ms", "title": "Merge Sort", "topic_type": "coding_implementation"},
            sandboxed=False,
        )
        self.assertTrue(applied)
        we = [c for c in lesson["lesson_cards"] if c.get("blueprint_key") == "worked_example"]
        last = we[-1]
        self.assertTrue(last.get("metadata", {}).get("reaches_final_answer"))
        joined = " ".join(str(p) for p in last.get("points") or [])
        self.assertIn("[3, 9, 10, 27, 38, 43, 82]", joined)  # the REAL sorted output
        self.assertNotIn("Final result: []", joined)         # not the empty-accumulator bug


class TestReturnedVars(unittest.TestCase):
    def test_returned_variable_derived_from_code(self):
        m = _returned_vars(MERGE_HELPER)
        self.assertEqual(m.get("merge"), "sorted_array")    # the function's own result var

    def test_return_of_call_is_skipped(self):
        # merge_sort `return merge(...)` is a call (no single var); its base case returns `arr`.
        m = _returned_vars(MERGE_SORT)
        self.assertEqual(m.get("merge_sort"), "arr")


if __name__ == "__main__":
    unittest.main()
