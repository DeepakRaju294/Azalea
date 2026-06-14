"""Hardened input extraction + drop telemetry + legacy array_state suppression.

The example array is found even when stated in a non-`points` field; a coding worked
example that can't trace records WHY; and the misleading legacy `array_state` guess on a
worked example is dropped (code-only) while a fixture/projector array model is kept.

Run: python -m unittest app.tests.test_code_drop_and_array_state
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

from app.services.legacy_v2_visual_bridge import gate_legacy_visuals
from app.services.visual_v2.code_lesson_integration import _extract_example_input
from app.services.visual_v2.invariant_metrics import GLOBAL as INV

BS = ("def binary_search(arr, target):\n    low = 0\n    high = len(arr) - 1\n"
      "    while low <= high:\n        mid = (low + high) // 2\n"
      "        if arr[mid] == target:\n            return mid\n"
      "        elif arr[mid] < target:\n            low = mid + 1\n"
      "        else:\n            high = mid - 1\n    return -1")


class TestExtractionFields(unittest.TestCase):
    def test_array_found_in_attention_note(self):
        lesson = {"lesson_cards": [{"blueprint_key": "worked_example",
                                    "visual_focus": {"attention_note": "input=[5, 3, 8, 1, 9], find 9"}}]}
        spec = _extract_example_input(lesson, BS, "binary_search")
        self.assertEqual(spec["array"], [5, 3, 8, 1, 9])
        self.assertEqual(spec["target"], 9)

    def test_array_found_in_bullets(self):
        lesson = {"lesson_cards": [{"blueprint_key": "worked_example",
                                    "bullets": ["Sort the array [4, 2, 7, 1]."]}]}
        spec = _extract_example_input(lesson, "def f(arr):\n    return arr", "f")
        self.assertEqual(spec["array"], [4, 2, 7, 1])

    def test_array_from_visual_model_fallback(self):
        lesson = {"lesson_cards": [{"blueprint_key": "worked_example"}],
                  "visual_models": [{"id": "m", "base_type": "indexed_sequence_diagram",
                                     "base": {"values": ["3", "1", "2", "9"]}}]}
        spec = _extract_example_input(lesson, "def f(arr):\n    return arr", "f")
        self.assertEqual(spec["array"], [3, 1, 2, 9])


class TestArrayStateSuppression(unittest.TestCase):
    def _lesson(self, model_id):
        return {
            "lesson_cards": [{"id": "we", "blueprint_key": "worked_example",
                              "visual_v2_ref": {"visual_model_id": model_id}}],
            "visual_models": [{"id": model_id, "base_type": "indexed_sequence_diagram",
                               "mode": "array_state", "base": {"values": ["1", "2", "3", "4"]},
                               "frames": [{"state": {}}]}],
        }

    def test_legacy_array_state_worked_example_dropped(self):
        lesson = self._lesson("indexed_sequence_diagram_t_card_25")  # legacy static guess
        gate_legacy_visuals(lesson)
        self.assertNotIn("visual_v2_ref", lesson["lesson_cards"][0])
        self.assertEqual(lesson["visual_models"], [])

    def test_fixture_array_state_kept(self):
        lesson = self._lesson("v2_linear_search_t")  # projector/fixture model — keep
        gate_legacy_visuals(lesson)
        self.assertIn("visual_v2_ref", lesson["lesson_cards"][0])
        self.assertEqual(len(lesson["visual_models"]), 1)


class TestDropMetric(unittest.TestCase):
    def setUp(self):
        # Pin the flag: another suite's tearDown can pop it, making apply_code_execution
        # return at the is_v2_enabled guard BEFORE it records a drop reason.
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"

    def test_no_input_records_drop_reason(self):
        from app.services.visual_v2.code_lesson_integration import apply_code_execution_to_lesson

        INV.reset()
        # graph code but the lesson states no graph/array → drop with reason no_input
        dfs = "def dfs(graph, start):\n    visited = []\n    return visited"
        lesson = {"lesson_cards": [{"blueprint_key": "worked_example", "code_snippet": dfs}],
                  "visual_models": []}
        ok = apply_code_execution_to_lesson(lesson, {"id": "t", "title": "DFS", "topic_type": "coding_implementation"}, sandboxed=False)
        self.assertFalse(ok)
        self.assertEqual(INV.snapshot()["fallbacks"].get("code_execution_drop:no_input"), 1)


if __name__ == "__main__":
    unittest.main()
