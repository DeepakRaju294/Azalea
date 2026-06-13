"""Phase 1.6 — code_execution lesson integration. In-process tracer (sandboxed=False).

Run: python -m unittest app.tests.test_visual_v2_code_lesson
"""
from __future__ import annotations

import os
import unittest

from app.services.visual_v2.code_lesson_integration import (
    _detect_input_spec,
    _extract_code_and_entry,
    _is_coding_topic,
    _loop_line_numbers,
    _milestone_frame_indices,
    apply_code_execution_to_lesson,
)

BINARY_SEARCH = (
    "def binary_search(arr, target):\n    low = 0\n    high = len(arr) - 1\n"
    "    while low <= high:\n        mid = (low + high) // 2\n"
    "        if arr[mid] == target:\n            return mid\n"
    "        elif target < arr[mid]:\n            high = mid - 1\n"
    "        else:\n            low = mid + 1\n    return -1"
)

CODE = (
    "def postorder(root):\n    result = []\n    traverse(root, result)\n    return result\n\n\n"
    "def traverse(node, result):\n    if node is None:\n        return\n"
    "    traverse(node.left, result)\n    traverse(node.right, result)\n    result.append(node.val)"
)
TOPIC = {"id": "t1", "title": "Implementing Postorder Traversal of a BST", "topic_type": "coding_implementation"}


def _lesson():
    return {
        "lesson_cards": [
            {"id": "1", "blueprint_key": "background", "title": "BST"},
            {"id": "2", "blueprint_key": "worked_example", "title": "old WE 1", "code_snippet": CODE},
            {"id": "3", "blueprint_key": "worked_example", "title": "old WE 2", "code_snippet": CODE},
            {"id": "4", "blueprint_key": "practice", "title": "Practice"},
        ],
        "visual_models": [],
    }


class TestHelpers(unittest.TestCase):
    def test_detect_coding_topic(self):
        self.assertTrue(_is_coding_topic(TOPIC))
        self.assertTrue(_is_coding_topic({"title": "Implementing Binary Search", "topic_type": "coding_implementation"}))
        self.assertFalse(_is_coding_topic({"title": "BFS", "topic_type": "algorithm_walkthrough"}))

    def test_extract_code_and_entry(self):
        code, entry = _extract_code_and_entry(_lesson())
        self.assertEqual(entry, "postorder")
        self.assertIn("def traverse", code)

    def test_input_detection_tree_vs_array(self):
        self.assertIn("tree", _detect_input_spec(CODE, "postorder"))
        spec = _detect_input_spec(BINARY_SEARCH, "binary_search")
        self.assertIn("array", spec)
        self.assertIn("target", spec)  # 2-arg search gets a target

    def test_loop_line_detection(self):
        self.assertTrue(_loop_line_numbers(BINARY_SEARCH))  # has a while loop
        self.assertEqual(_loop_line_numbers(CODE), frozenset())  # recursion, no loop


class TestApply(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)

    def test_flag_off_noop(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)
        lesson = _lesson()
        self.assertFalse(apply_code_execution_to_lesson(lesson, TOPIC, sandboxed=False))
        self.assertEqual(lesson["visual_models"], [])

    def test_applies_real_trace(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "code_execution"
        lesson = _lesson()
        applied = apply_code_execution_to_lesson(lesson, TOPIC, sandboxed=False)
        self.assertTrue(applied)

        # A code_execution_panel model is attached.
        self.assertEqual(len(lesson["visual_models"]), 1)
        model = lesson["visual_models"][0]
        self.assertEqual(model["base_type"], "code_execution_panel")
        self.assertEqual(model["base"]["code"], CODE)
        self.assertTrue(len(model["frames"]) > 8)  # real per-line frames

        # Worked cards replaced by milestone step cards referencing real frames.
        worked = [c for c in lesson["lesson_cards"] if c.get("card_type") == "worked_example"]
        self.assertTrue(0 < len(worked) <= len(model["frames"]))
        for card in worked:
            ref = card["visual_v2_ref"]
            self.assertEqual(ref["visual_model_id"], model["id"])
            self.assertEqual(ref["source"], "v2_code_execution")
            self.assertTrue(0 <= ref["frame_index"] < len(model["frames"]))
        # Surrounding cards kept.
        self.assertEqual(lesson["lesson_cards"][0]["blueprint_key"], "background")
        self.assertEqual(lesson["lesson_cards"][-1]["blueprint_key"], "practice")

    def test_milestones_track_output_growth(self):
        # A 7-node BST → 7 appended values → 7 milestones.
        os.environ["AZALEA_VISUAL_V2_MODES"] = "code_execution"
        lesson = _lesson()
        apply_code_execution_to_lesson(lesson, TOPIC, sandboxed=False)
        worked = [c for c in lesson["lesson_cards"] if c.get("card_type") == "worked_example"]
        self.assertEqual(len(worked), 7)


class TestBinarySearchCodeExecution(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)

    def test_binary_search_traces_via_array(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"
        # The array comes from the lesson's OWN content (no hardcoded values).
        lesson = {
            "lesson_cards": [
                {"id": "1", "blueprint_key": "background"},
                {"id": "2", "blueprint_key": "worked_example", "code_snippet": BINARY_SEARCH,
                 "points": ["Search the array [1, 3, 5, 7, 9, 11, 13] for the target 13."]},
                {"id": "3", "blueprint_key": "practice"},
            ],
            "visual_models": [],
        }
        topic = {"id": "bs", "title": "Implementing Binary Search", "topic_type": "coding_implementation"}
        applied = apply_code_execution_to_lesson(lesson, topic, sandboxed=False)
        self.assertTrue(applied)

        model = lesson["visual_models"][0]
        self.assertEqual(model["base_type"], "code_execution_panel")
        self.assertIn("binary_search", model["base"]["code"])

        worked = [c for c in lesson["lesson_cards"] if c.get("card_type") == "worked_example"]
        # setup lines (low, high) + several probe iterations → at least 4 cards.
        self.assertGreaterEqual(len(worked), 4)
        for card in worked:
            self.assertEqual(card["visual_v2_ref"]["source"], "v2_code_execution")

    def test_broken_code_falls_back_to_canonical(self):
        # The canonical fallback is now an OPT-IN escape hatch (hardcoded contents are
        # off by default so real LLM performance is visible). With the flag ON, broken
        # code still falls back to a canonical implementation.
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"
        os.environ["AZALEA_CODE_CANONICAL_FALLBACK"] = "1"
        self.addCleanup(lambda: os.environ.pop("AZALEA_CODE_CANONICAL_FALLBACK", None))
        broken = "left = 0\n    right = len(arr) - 1\nwhile left <= right:\nif arr[mid] == target:\n    return mid"
        lesson = {
            "lesson_cards": [
                {"id": "1", "blueprint_key": "worked_example", "code_snippet": broken},
                {"id": "2", "blueprint_key": "practice"},
            ],
            "visual_models": [],
        }
        topic = {"id": "bs", "title": "Implementing Binary Search", "topic_type": "coding_implementation"}
        self.assertTrue(apply_code_execution_to_lesson(lesson, topic, sandboxed=False))
        code = lesson["visual_models"][0]["base"]["code"]
        self.assertIn("def binary_search(arr, target):", code)  # function name present
        self.assertIn("mid = (low + high) // 2", code)          # mid computed
        worked = [c for c in lesson["lesson_cards"] if c.get("card_type") == "worked_example"]
        self.assertGreaterEqual(len(worked), 4)

    def test_setup_lines_lead_the_cards(self):
        # The first milestone cards are the variable-init lines (before the loop).
        from app.services.visual_v2.delta_fold import DeltaFoldEngine
        from app.services.visual_v2.profiles import delta_vocabulary
        from app.services.visual_v2.simulators.code_tracer import simulate_code_execution

        trace = simulate_code_execution(
            {"example_id": "bs", "mode": "code_execution", "code": BINARY_SEARCH,
             "entry_function": "binary_search", "input": {"array": list(range(1, 16)), "target": 1}},
        )
        frames = DeltaFoldEngine().fold(trace["initial_state"], trace["steps"], set(), delta_vocabulary("code_execution"))
        milestones = _milestone_frame_indices(frames, _loop_line_numbers(BINARY_SEARCH))
        # first milestone frame highlights line 2 (low = 0), before any loop line.
        self.assertEqual(frames[milestones[0]]["state_after"]["highlight_lines"], [2])


if __name__ == "__main__":
    unittest.main()
