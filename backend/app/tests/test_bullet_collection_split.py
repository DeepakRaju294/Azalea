"""A collection literal is never shredded across sub-bullets.

`[38, 27, 43]` must stay one sub-bullet — its internal commas are not item separators —
while a genuine plain list ("apples, oranges, bananas") still splits.

Run: python -m unittest app.tests.test_bullet_collection_split
"""
from __future__ import annotations

import os
import sys
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")
for _name in ("dotenv", "openai"):
    if _name not in sys.modules:
        _m = types.ModuleType(_name)
        if _name == "dotenv":
            _m.load_dotenv = lambda *a, **k: None
        else:
            _m.OpenAI = lambda *a, **k: object()
            for _e in ("APIError", "RateLimitError", "APITimeoutError", "APIConnectionError"):
                setattr(_m, _e, type(_e, (Exception,), {}))
        sys.modules[_name] = _m

from app.services.lean_lesson_generator import (
    _expand_colon_point,
    _has_bracketed_commas,
    _split_detail_units,
)


class TestCollectionSplit(unittest.TestCase):
    def test_array_stays_one_unit(self):
        self.assertEqual(_split_detail_units("[38, 27, 43]"), ["[38, 27, 43]"])

    def test_assignments_with_arrays_stay_intact(self):
        self.assertEqual(
            _split_detail_units("left=[38, 27, 43], sorted_left=[27, 38, 43]"),
            ["left=[38, 27, 43], sorted_left=[27, 38, 43]"],
        )

    def test_dict_stays_one_unit(self):
        self.assertEqual(_split_detail_units("{a: 1, b: 2, c: 3}"), ["{a: 1, b: 2, c: 3}"])

    def test_plain_list_still_splits(self):
        self.assertEqual(
            _split_detail_units("apples, oranges, bananas"), ["apples", "oranges", "bananas"]
        )

    def test_bracketed_comma_detection(self):
        self.assertTrue(_has_bracketed_commas("[1, 2]"))
        self.assertFalse(_has_bracketed_commas("a, b, c"))

    def test_colon_point_keeps_array_in_one_subpoint(self):
        out = _expand_colon_point("Next, we apply merge sort to the left part: [38, 27, 43]")
        self.assertEqual(out, ["Next, we apply merge sort to the left part", "  - [38, 27, 43]"])


if __name__ == "__main__":
    unittest.main()
