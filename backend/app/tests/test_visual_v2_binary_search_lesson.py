"""binary_search lesson integration. Run: python -m unittest app.tests.test_visual_v2_binary_search_lesson"""
from __future__ import annotations

import os
import unittest

from app.services.visual_v2.array_lesson_integration import (
    _is_binary_search_topic,
    apply_binary_search_to_lesson,
)

TOPIC = {"id": "t1", "title": "Binary Search on a Sorted Array", "topic_type": "algorithm_walkthrough"}


def _lesson():
    return {
        "lesson_cards": [
            {"id": "1", "blueprint_key": "background", "title": "BS"},
            {"id": "2", "blueprint_key": "worked_example", "title": "old WE"},
            {"id": "3", "blueprint_key": "practice", "title": "Practice"},
        ],
        "visual_models": [],
    }


class TestBinarySearchLesson(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)

    def test_detect(self):
        self.assertTrue(_is_binary_search_topic(TOPIC))
        self.assertFalse(_is_binary_search_topic({"title": "Implementing Binary Search", "topic_type": "coding_implementation"}))

    def test_flag_off_noop(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)
        lesson = _lesson()
        self.assertFalse(apply_binary_search_to_lesson(lesson, TOPIC))

    def test_applies(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "binary_search_range"
        lesson = _lesson()
        self.assertTrue(apply_binary_search_to_lesson(lesson, TOPIC))
        model = lesson["visual_models"][0]
        self.assertEqual(model["base_type"], "indexed_sequence_diagram")
        self.assertEqual(model["base"]["values"], ["3", "7", "9", "12", "18", "21", "30"])
        worked = [c for c in lesson["lesson_cards"] if c.get("card_type") == "worked_example"]
        self.assertEqual(len(worked), len(model["frames"]))
        for i, card in enumerate(worked):
            self.assertEqual(card["visual_v2_ref"], {"visual_model_id": model["id"], "frame_index": i, "source": "v2_binary_search"})
        self.assertEqual(lesson["lesson_cards"][-1]["blueprint_key"], "practice")


if __name__ == "__main__":
    unittest.main()
