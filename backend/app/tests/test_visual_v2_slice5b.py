"""Visual System V2 — Slice 5b (lesson integration). LLM stubbed; uses the real
legacy NodeLinkCompiler (imports cleanly, no dotenv).

Run: python -m unittest app.tests.test_visual_v2_slice5b   (from backend/, PYTHONPATH=.)
"""
from __future__ import annotations

import copy
import os
import unittest

from app.services.visual_v2.lesson_integration import (
    apply_v2_to_lesson,
    compile_model,
    to_worked_example_plan,
)
from app.services.visual_v2.pipeline import run_for_registered

BFS_EXAMPLE = {
    "example_id": "bfs_appendix",
    "base_type": "node_link_diagram",
    "mode": "graph_network",
    "algorithm": "bfs",
    "input": {"start": "A"},
    "base_structure": {
        "nodes": ["A", "B", "C", "D", "E"],
        "edges": [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"]],
    },
}
TOPIC = {"id": "t1", "title": "Breadth-First Search (BFS)", "topic_type": "algorithm_walkthrough"}


def _example_stub(**_kw):
    return dict(BFS_EXAMPLE)


def _lesson_json():
    return {
        "lesson_cards": [
            {"id": "1", "blueprint_key": "background", "card_type": "background", "title": "BFS"},
            {"id": "2", "blueprint_key": "worked_example", "card_type": "worked_example", "title": "old WE 1"},
            {"id": "3", "blueprint_key": "worked_example", "card_type": "worked_example", "title": "old WE 2"},
            {"id": "4", "blueprint_key": "practice", "card_type": "quick_practice", "title": "Practice"},
        ],
        "visual_models": [],
    }


class TestPlanAndCompile(unittest.TestCase):
    def setUp(self):
        result = run_for_registered(BFS_EXAMPLE)
        self.plan = to_worked_example_plan(
            example=BFS_EXAMPLE, frames=result["frames"], render_steps=result["render_steps"],
            prose=[], mode="graph_network",
        )

    def test_plan_has_base_and_steps(self):
        self.assertEqual(len(self.plan["base_state"]["nodes"]), 5)
        self.assertEqual(len(self.plan["base_state"]["edges"]), 4)
        self.assertEqual(len(self.plan["steps"]), 5)
        s2 = self.plan["steps"][1]["state_after"]
        self.assertEqual(s2["active_node"], "B")
        self.assertEqual(s2["runtime_state"]["frontier"], ["C", "D"])

    def test_compile_produces_renderable_model(self):
        model = compile_model(plan=self.plan, topic=TOPIC, mode="graph_network", model_id="m1")
        self.assertIsNotNone(model)
        self.assertEqual(model["id"], "m1")
        self.assertEqual(len(model["frames"]), 5)
        # Frame shape the frontend renders.
        f0 = model["frames"][0]
        self.assertIn("state", f0)
        self.assertIn("selectable_elements", f0)
        self.assertEqual(f0["index"], 0)


class TestApplyToLesson(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)

    def test_flag_off_is_noop(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)
        lesson = _lesson_json()
        before = copy.deepcopy(lesson)
        applied = apply_v2_to_lesson(lesson, TOPIC, generate_example=_example_stub)
        self.assertFalse(applied)
        self.assertEqual(lesson, before)

    def test_non_matching_topic_is_noop(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "graph_network"
        lesson = _lesson_json()
        applied = apply_v2_to_lesson(lesson, {"id": "x", "title": "Inorder Traversal", "topic_type": "algorithm_walkthrough"}, generate_example=_example_stub)
        self.assertFalse(applied)

    def test_apply_replaces_worked_cards_and_attaches_model(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "graph_network:bfs"
        lesson = _lesson_json()
        applied = apply_v2_to_lesson(lesson, TOPIC, generate_example=_example_stub)
        self.assertTrue(applied)

        # Model attached.
        self.assertEqual(len(lesson["visual_models"]), 1)
        model_id = lesson["visual_models"][0]["id"]
        self.assertEqual(len(lesson["visual_models"][0]["frames"]), 5)

        # Legacy worked cards gone; 5 V2 step cards in their place; others kept.
        worked = [c for c in lesson["lesson_cards"] if c["card_type"] == "worked_example"]
        self.assertEqual(len(worked), 5)
        self.assertTrue(all(c["title"] not in ("old WE 1", "old WE 2") for c in worked))
        self.assertEqual([c["blueprint_key"] for c in lesson["lesson_cards"]][0], "background")
        self.assertEqual(lesson["lesson_cards"][-1]["blueprint_key"], "practice")

        # Each step card references the model frame-by-frame.
        for i, card in enumerate(worked):
            ref = card["visual_v2_ref"]
            self.assertEqual(ref["visual_model_id"], model_id)
            self.assertEqual(ref["frame_index"], i)
            self.assertEqual(ref["source"], "v2_pipeline")
        self.assertEqual(lesson["metadata"]["visual_v2_applied"]["steps"], 5)


if __name__ == "__main__":
    unittest.main()
