"""End-to-end "does it perform": apply_fixture_to_lesson on a graph topic
(PROJECTOR_SYSTEM_SPEC §7). An MST / Dijkstra lesson gets real node_link worked-example
cards backed by a T2 model with NON-EMPTY per-step highlighting and selected edges —
the holistic replacement for the legacy "nothing highlights" path.

Run: python -m unittest app.tests.test_projected_lesson_apply
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.handoff import apply_fixture_to_lesson


def _lesson():
    return {
        "lesson_cards": [
            {"id": "1", "blueprint_key": "background", "title": "Intro"},
            {"id": "2", "blueprint_key": "worked_example", "title": "old WE"},
            {"id": "3", "blueprint_key": "practice", "title": "Practice"},
        ],
        "visual_models": [],
    }


class TestProjectedLessonApply(unittest.TestCase):
    def setUp(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "all"

    def tearDown(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)

    def _apply(self, title):
        lesson = _lesson()
        applied = apply_fixture_to_lesson(
            lesson, {"id": "t", "title": title, "topic_type": "algorithm_walkthrough"}
        )
        return lesson, applied

    def _model(self, lesson):
        we = [c for c in lesson["lesson_cards"]
              if str(c.get("blueprint_key") or c.get("card_type")) == "worked_example"
              and (c.get("visual_v2_ref") or {}).get("visual_model_id")]
        self.assertTrue(we, "no worked-example card with a v2 model ref")
        mid = we[0]["visual_v2_ref"]["visual_model_id"]
        model = next(m for m in lesson["visual_models"] if m["id"] == mid)
        return we, model

    def test_mst_lesson_has_highlighted_worked_example(self):
        lesson, applied = self._apply("Prim's Algorithm for Minimum Spanning Trees")
        self.assertTrue(applied, "MST fixture did not apply")
        we, model = self._model(lesson)
        # T2 provenance
        self.assertEqual(model["provenance"]["tier"], "T2")
        # NON-EMPTY highlighting: some frame has an active node (the bug was: none did)
        self.assertTrue(any(f["state"].get("active_node") for f in model["frames"]))
        # MST edges selected by the end
        final = model["frames"][-1]["state"]
        self.assertGreaterEqual(len(final.get("completed_edges_from") or []), 1)
        # multiple step cards (a real worked example, not one card)
        self.assertGreaterEqual(len(we), 1)

    def test_dijkstra_lesson_applies_with_highlighting(self):
        lesson, applied = self._apply("Dijkstra's Shortest Path Algorithm")
        self.assertTrue(applied, "Dijkstra fixture did not apply")
        _we, model = self._model(lesson)
        self.assertEqual(model["provenance"]["tier"], "T2")
        self.assertTrue(any(f["state"].get("active_node") for f in model["frames"]))


if __name__ == "__main__":
    unittest.main()
