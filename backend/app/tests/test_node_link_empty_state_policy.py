"""§6.2 + T5 display policy end-to-end (PROJECTOR_SYSTEM_SPEC).

A node_link worked example that resolves to empty per-step state (the MST-style
"nothing highlights" bug) must be (a) counted as `empty_node_state` telemetry and
(b) rendered text-only — its broken progressive diagram ref dropped, never shipped.
A healthy model keeps its ref. Asserted by state shape, not topic.

Run: python -m unittest app.tests.test_node_link_empty_state_policy
"""
from __future__ import annotations

import os
import sys
import types
import unittest

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

from app.services import legacy_v2_visual_bridge as bridge
from app.services.visual_v2.invariant_metrics import GLOBAL as INV


def _node_link_model(model_id, frames):
    return {
        "id": model_id,
        "base_type": "node_link_diagram",
        "base": {"nodes": [{"id": n, "label": n} for n in "ABC"], "edges": [{"from": "A", "to": "B"}]},
        "frames": frames,
    }


def _empty_frames():
    # nodes + edges present, but nothing ever active/visited (the MST bug).
    return [
        {"state": {"active_node": "", "completed_nodes": [],
                   "node_state_map": [{"node_id": n, "state": "unvisited"} for n in "ABC"]}}
        for _ in range(3)
    ]


def _live_frames():
    return [
        {"state": {"active_node": "A", "completed_nodes": [],
                   "node_state_map": [{"node_id": "A", "state": "current"}]}},
        {"state": {"active_node": "B", "completed_nodes": ["A"],
                   "node_state_map": [{"node_id": "A", "state": "completed"}, {"node_id": "B", "state": "current"}]}},
    ]


def _lesson(model):
    return {
        "lesson_cards": [
            {
                "id": "wc",
                "blueprint_key": "worked_example",
                "visual_v2_ref": {"visual_model_id": model["id"], "frame_index": 0},
            }
        ],
        "visual_models": [model],
    }


class TestEmptyStatePolicy(unittest.TestCase):
    def setUp(self):
        INV.reset()
        self.context = {"topic_id": "t1", "topic_hint": "Minimum Spanning Tree", "topic_type": "algorithm_walkthrough"}

    def test_empty_worked_example_is_suppressed_and_counted(self):
        lesson = _lesson(_node_link_model("mst_empty", _empty_frames()))
        bridge._apply_node_link_empty_state_policy(lesson, self.context)
        card = lesson["lesson_cards"][0]
        self.assertNotIn("visual_v2_ref", card)  # broken diagram dropped → text-only
        self.assertEqual(card["metadata"]["v2_visual_suppressed"], "empty_node_state")
        self.assertEqual(INV.snapshot()["fallbacks"].get("empty_node_state"), 1)

    def test_healthy_worked_example_keeps_its_ref(self):
        lesson = _lesson(_node_link_model("bfs_live", _live_frames()))
        bridge._apply_node_link_empty_state_policy(lesson, self.context)
        card = lesson["lesson_cards"][0]
        self.assertIn("visual_v2_ref", card)  # untouched
        self.assertEqual(INV.snapshot()["fallbacks"].get("empty_node_state"), None)

    def test_non_worked_example_card_is_ignored(self):
        lesson = _lesson(_node_link_model("mst_empty", _empty_frames()))
        lesson["lesson_cards"][0]["blueprint_key"] = "background"  # not a worked example
        bridge._apply_node_link_empty_state_policy(lesson, self.context)
        self.assertIn("visual_v2_ref", lesson["lesson_cards"][0])  # only worked examples are policed


if __name__ == "__main__":
    unittest.main()
