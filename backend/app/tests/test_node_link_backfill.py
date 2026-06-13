"""Regression: a node_link card with nodes but NO edges (the MST-background bug —
disconnected dots) is repaired from an edge-bearing donor card.
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


def _graph_card(blueprint_key, nodes, edges):
    return {
        "id": blueprint_key,
        "blueprint_key": blueprint_key,
        "visual_type": "node_link_diagram",
        "visual_plan": {"type": "node_link_diagram", "nodes": nodes, "edges": edges},
    }


class TestNodeLinkBackfill(unittest.TestCase):
    def setUp(self):
        self._orig = bridge._blueprint_card_allows_base_type
        bridge._blueprint_card_allows_base_type = lambda card, rules, bt: bt == "node_link_diagram"

    def tearDown(self):
        bridge._blueprint_card_allows_base_type = self._orig

    def test_nodes_without_edges_get_repaired(self):
        nodes = [{"id": c, "label": c} for c in "ABCDEFG"]
        background = _graph_card("background", nodes, [])  # the bug: nodes, no edges
        worked = _graph_card("worked_example", nodes,
                             [{"from": "A", "to": "B", "label": "4"}, {"from": "B", "to": "C", "label": "2"}])
        cards = [background, worked]

        bridge._backfill_missing_node_link_structure(cards, None, {})

        bg_edges = background["visual_plan"]["edges"]
        self.assertTrue(bg_edges, "background still has no edges after backfill")
        self.assertEqual({(e["from"], e["to"]) for e in bg_edges}, {("A", "B"), ("B", "C")})
        self.assertEqual(background["metadata"]["node_link_structure_backfilled_from"], "worked_example")

    def test_card_with_edges_is_left_alone(self):
        nodes = [{"id": c, "label": c} for c in "ABC"]
        a = _graph_card("worked_example", nodes, [{"from": "A", "to": "B"}])
        b = _graph_card("worked_example", nodes, [{"from": "B", "to": "C", "label": "9"}])
        bridge._backfill_missing_node_link_structure([a, b], None, {})
        # Each keeps its own distinct edges (not overwritten by the other).
        self.assertEqual([(e["from"], e["to"]) for e in a["visual_plan"]["edges"]], [("A", "B")])
        self.assertEqual([(e["from"], e["to"]) for e in b["visual_plan"]["edges"]], [("B", "C")])

    def test_no_donor_with_edges_leaves_card_unchanged(self):
        nodes = [{"id": c, "label": c} for c in "ABC"]
        only = _graph_card("background", nodes, [])      # nobody has edges → can't repair
        bridge._backfill_missing_node_link_structure([only, _graph_card("x", nodes, [])], None, {})
        self.assertEqual(only["visual_plan"]["edges"], [])  # unchanged, not fabricated


if __name__ == "__main__":
    unittest.main()
