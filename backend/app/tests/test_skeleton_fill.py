"""Phase 5 — blueprint skeleton-fill generation (spec §6). Deterministic structure
(no live LLM); plus end-to-end with the fixture handoff filling example slots.

Run: python -m unittest app.tests.test_skeleton_fill
"""
from __future__ import annotations

import os
import sys
import types
import unittest

# Sandbox guard for the handoff's lean_lesson_generator import.
os.environ.setdefault("OPENAI_API_KEY", "dummy")
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

from app.services.examples.skeleton_fill import (
    Slot,
    build_card_skeleton,
    fill_skeleton_lesson,
)


def _topic(title, topic_type):
    return {"id": "t", "title": title, "topic_type": topic_type}


class TestSkeleton(unittest.TestCase):
    def test_skeleton_follows_blueprint(self):
        keys = [s.blueprint_key for s in build_card_skeleton(_topic("BFS", "algorithm_walkthrough"))]
        # algorithm_walkthrough blueprint order.
        self.assertEqual(keys[0], "background")
        self.assertIn("worked_example", keys)
        self.assertIn("practice", keys)

    def test_intro_skeleton_is_background_and_roadmap_only(self):
        keys = [s.blueprint_key for s in build_card_skeleton(_topic("Intro", "study_path_introduction"))]
        self.assertEqual(keys, ["background", "roadmap"])


class TestFill(unittest.TestCase):
    def test_deterministic_fill_is_valid_and_ordered(self):
        lesson = fill_skeleton_lesson(_topic("Binary Search", "algorithm_walkthrough"))
        self.assertEqual(lesson["metadata"]["generation"], "skeleton_fill")
        keys = [c["blueprint_key"] for c in lesson["lesson_cards"]]
        self.assertEqual(keys[0], "background")
        # Every card has a non-empty title; non-example cards have content.
        for c in lesson["lesson_cards"]:
            self.assertTrue(c["title"].strip())

    def test_example_slots_are_placeholders(self):
        lesson = fill_skeleton_lesson(_topic("Binary Search", "algorithm_walkthrough"))
        we = [c for c in lesson["lesson_cards"] if c["blueprint_key"] == "worked_example"]
        self.assertTrue(we)
        self.assertEqual(we[0]["points"], [])  # left for the fixture handoff

    def test_optional_slot_omitted_when_filler_returns_none(self):
        # components_terms is optional in concept_intuition; a filler that returns
        # None for it must omit it, not emit a blank card.
        def filler(slot, topic, chunks):
            return None if slot.blueprint_key == "components_terms" else {"title": "x", "points": ["p"]}

        lesson = fill_skeleton_lesson(_topic("Recursion", "concept_intuition"), slot_filler=filler)
        keys = [c["blueprint_key"] for c in lesson["lesson_cards"]]
        self.assertNotIn("components_terms", keys)

    def test_failing_filler_falls_back_never_blank(self):
        def boom(slot, topic, chunks):
            raise RuntimeError("LLM down")

        lesson = fill_skeleton_lesson(_topic("Recursion", "concept_intuition"), slot_filler=boom)
        # Required slots still present with deterministic content; no exception.
        bg = [c for c in lesson["lesson_cards"] if c["blueprint_key"] == "background"]
        self.assertTrue(bg and bg[0]["points"])


class TestEndToEndWithHandoff(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)

    def test_skeleton_plus_handoff_fills_examples(self):
        # The skeleton lays out structure; the fixture handoff swaps the example slots
        # with verified content — the two halves of Phase 5 + §4.5 together.
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"
        from app.services.examples.handoff import apply_fixture_to_lesson, validate_and_order_cards

        topic = _topic("Implementing Binary Search", "coding_implementation")
        lesson = fill_skeleton_lesson(topic)
        applied = apply_fixture_to_lesson(lesson, topic)
        validate_and_order_cards(lesson, topic)
        self.assertTrue(applied)
        worked = [c for c in lesson["lesson_cards"] if c.get("card_type") == "worked_example"]
        self.assertGreaterEqual(len(worked), 4)  # real fixture steps, not the placeholder
        self.assertTrue(any(c.get("visual_v2_ref") for c in worked))
        # Blueprint order preserved.
        keys = [c["blueprint_key"] for c in lesson["lesson_cards"]]
        self.assertEqual(keys[0], "background")


if __name__ == "__main__":
    unittest.main()
