"""Shape-agnostic legacy-visual guardrail (PROJECTOR_SYSTEM_SPEC INV-RENDER applied to
the legacy/static path). Malformed/degenerate diagrams and code-in-the-diagram-slot are
dropped; valid visuals are kept. Asserted by defect shape, not topic.

Run: python -m unittest app.tests.test_visual_gate
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

from app.services.legacy_v2_visual_bridge import gate_legacy_visuals


def _node_link(mid, nodes, edges):
    return {
        "id": mid, "base_type": "node_link_diagram",
        "base": {"nodes": [{"id": n, "label": n} for n in nodes],
                 "edges": [{"from": a, "to": b} for a, b in edges]},
        "frames": [{"state": {"node_state_map": []}}],
    }


def _lesson(models, cards):
    return {"visual_models": models, "lesson_cards": cards}


class TestVisualGate(unittest.TestCase):
    def test_single_node_graph_is_dropped(self):
        m = _node_link("bg", ["D"], [])  # the "What is BFS?" background bug
        lesson = _lesson([m], [{"id": "c", "blueprint_key": "background",
                                 "visual_v2_ref": {"visual_model_id": "bg"}}])
        gate_legacy_visuals(lesson)
        self.assertEqual(lesson["visual_models"], [])
        self.assertNotIn("visual_v2_ref", lesson["lesson_cards"][0])

    def test_dangling_edges_are_dropped(self):
        # one node D + donated edges to absent A,B,C (the phantom rings)
        m = _node_link("bg", ["D", "E"], [("A", "B"), ("B", "C")])
        lesson = _lesson([m], [{"id": "c", "blueprint_key": "background",
                                 "visual_v2_ref": {"visual_model_id": "bg"}}])
        gate_legacy_visuals(lesson)
        self.assertEqual(lesson["visual_models"], [])

    def test_valid_graph_is_kept(self):
        m = _node_link("g", ["A", "B", "C"], [("A", "B"), ("B", "C")])
        lesson = _lesson([m], [{"id": "c", "blueprint_key": "worked_example",
                                 "visual_v2_ref": {"visual_model_id": "g"}}])
        gate_legacy_visuals(lesson)
        self.assertEqual(len(lesson["visual_models"]), 1)
        self.assertIn("visual_v2_ref", lesson["lesson_cards"][0])

    def test_empty_sequence_is_dropped(self):
        m = {"id": "s", "base_type": "indexed_sequence_diagram", "base": {"values": []}, "frames": []}
        lesson = _lesson([m], [{"id": "c", "visual_v2_ref": {"visual_model_id": "s"}}])
        gate_legacy_visuals(lesson)
        self.assertEqual(lesson["visual_models"], [])

    def test_code_in_diagram_slot_is_dropped(self):
        # the "Diagram tab shows code" bug — diagram_v2_ref points at a code model
        code = {"id": "code", "base_type": "code_execution_panel", "base": {}, "frames": [{"state": {}}]}
        lesson = _lesson([code], [{
            "id": "we", "blueprint_key": "worked_example",
            "visual_v2_ref": {"visual_model_id": "code"},   # code slot — fine
            "diagram_v2_ref": {"visual_model_id": "code"},  # diagram slot pointing at code — wrong
        }])
        gate_legacy_visuals(lesson)
        card = lesson["lesson_cards"][0]
        self.assertNotIn("diagram_v2_ref", card)        # code-as-diagram removed
        self.assertIn("visual_v2_ref", card)            # code slot untouched
        self.assertEqual(len(lesson["visual_models"]), 1)  # the code model still used by the code slot


if __name__ == "__main__":
    unittest.main()
