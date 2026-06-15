"""Smoke test for the lean->legacy conversion path.

This path (_convert_lean_to_legacy) had no test coverage, so a removed-variable orphan
(topic_type_key) only surfaced at runtime. This exercises it for coding + non-coding topics
so structural edits to the converter are caught in CI, not in a live generation.

Run: python -m unittest app.tests.test_lean_to_legacy_smoke
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

from types import SimpleNamespace

from app.services.lean_lesson_generator import _convert_lean_to_legacy


def _topic(course_type: str):
    return SimpleNamespace(
        id="t1", title="Merge Sort", description="", course_type=course_type,
        topic_type=course_type, order_index=1, study_path_id="s1",
    )


def _lean():
    return {"cards": [
        {"blueprint_key": "background", "title": "Background", "points": ["Merge sort sorts by splitting."]},
        {"blueprint_key": "code_walkthrough", "title": "Code",
         "code_snippet": "def merge_sort(arr):\n    return sorted(arr)", "points": ["It returns a sorted copy."]},
        {"blueprint_key": "worked_example", "title": "Example", "points": ["Sort [3, 1, 2]."]},
        {"blueprint_key": "practice", "title": "Practice", "points": ["Try it."]},
    ]}


class TestLeanToLegacySmoke(unittest.TestCase):
    def test_converts_without_error_for_each_topic_type(self):
        for course_type in ("coding_implementation", "concept_intuition", "algorithm_walkthrough",
                            "math_formula_method", "process_walkthrough"):
            with self.subTest(course_type=course_type):
                out = _convert_lean_to_legacy(_lean(), _topic(course_type), [])
                self.assertIsInstance(out, dict)
                self.assertTrue(out.get("lesson_cards"))  # produced cards, no exception


if __name__ == "__main__":
    unittest.main()
