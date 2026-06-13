"""Visual System V2 — static-visual path (§5.0, Phase 2). Pure backend, no LLM.

Run: python -m unittest app.tests.test_visual_v2_static
"""
from __future__ import annotations

import unittest

from app.services.visual_v2.example_invariants import validate_static_example
from app.services.visual_v2.static_visual import run_static_visual

TREE_AT_REST = {
    "example_id": "bst_def",
    "base_type": "node_link_diagram",
    "mode": "graph_network",
    "visual_intent_type": "define_structure",
    "base_structure": {
        "nodes": ["50", "30", "70", "20", "40"],
        "edges": [["50", "30"], ["50", "70"], ["30", "20"], ["30", "40"]],
    },
}


class TestStaticValidator(unittest.TestCase):
    def test_valid_structure_no_start_required(self):
        # Static visuals have no traversal start — must not demand one.
        self.assertEqual(validate_static_example(TREE_AT_REST), [])

    def test_too_trivial_rejected(self):
        ex = {**TREE_AT_REST, "base_structure": {"nodes": ["A"], "edges": []}}
        self.assertTrue(any("too trivial" in e for e in validate_static_example(ex)))


class TestRunStaticVisual(unittest.TestCase):
    def setUp(self):
        self.result = run_static_visual(TREE_AT_REST, model_id="m1")

    def test_validated_single_frame(self):
        self.assertEqual(self.result["status"], "validated")
        self.assertTrue(self.result["static"])
        self.assertEqual(len(self.result["model"]["frames"]), 1)

    def test_all_nodes_at_rest(self):
        states = {e["node_id"]: e["state"] for e in self.result["model"]["frames"][0]["state"]["node_state_map"]}
        self.assertTrue(all(s == "unvisited" for s in states.values()))
        self.assertEqual(self.result["model"]["frames"][0]["state"]["active_node"], "")

    def test_base_carries_full_structure(self):
        self.assertEqual(len(self.result["model"]["base"]["nodes"]), 5)
        self.assertEqual(len(self.result["model"]["base"]["edges"]), 4)

    def test_trivial_structure_rejected(self):
        res = run_static_visual({**TREE_AT_REST, "base_structure": {"nodes": ["A"], "edges": []}})
        self.assertEqual(res["status"], "failed")


if __name__ == "__main__":
    unittest.main()
