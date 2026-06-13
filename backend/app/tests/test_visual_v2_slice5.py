"""Visual System V2 — Slice 5a (flag-gated integration seam). LLM stubbed.

Run: python -m unittest app.tests.test_visual_v2_slice5   (from backend/, PYTHONPATH=.)
"""
from __future__ import annotations

import os
import unittest

from app.services.visual_v2.integration import detect_mode_algorithm, maybe_build_v2_visual

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


def _example_stub(**_kw):
    return dict(BFS_EXAMPLE)


class TestDetect(unittest.TestCase):
    def test_bfs_walkthrough(self):
        self.assertEqual(
            detect_mode_algorithm({"title": "Breadth-First Search (BFS) Overview", "topic_type": "algorithm_walkthrough"}),
            ("graph_network", "bfs"),
        )

    def test_dfs_walkthrough(self):
        self.assertEqual(
            detect_mode_algorithm({"title": "Depth-First Search", "topic_type": "algorithm_walkthrough"}),
            ("graph_network", "dfs"),
        )

    def test_coding_topic_skipped(self):
        self.assertEqual(
            detect_mode_algorithm({"title": "Implementing BFS", "topic_type": "coding_implementation"}),
            (None, None),
        )

    def test_unrelated_topic_skipped(self):
        self.assertEqual(
            detect_mode_algorithm({"title": "Inorder Traversal of a BST", "topic_type": "algorithm_walkthrough"}),
            (None, None),
        )


class TestMaybeBuild(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)

    def test_returns_none_when_flag_off(self):
        os.environ.pop("AZALEA_VISUAL_V2_MODES", None)
        topic = {"id": "t1", "title": "Breadth-First Search", "topic_type": "algorithm_walkthrough"}
        self.assertIsNone(maybe_build_v2_visual(topic, generate_example=_example_stub, generate_prose=None))

    def test_returns_none_for_non_matching_topic(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "graph_network"
        topic = {"id": "t1", "title": "Inorder Traversal", "topic_type": "algorithm_walkthrough"}
        self.assertIsNone(maybe_build_v2_visual(topic, generate_example=_example_stub, generate_prose=None))

    def test_builds_when_enabled(self):
        os.environ["AZALEA_VISUAL_V2_MODES"] = "graph_network:bfs"
        topic = {"id": "t1", "title": "Breadth-First Search (BFS)", "topic_type": "algorithm_walkthrough"}
        result = maybe_build_v2_visual(topic, generate_example=_example_stub, generate_prose=None)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "validated")
        self.assertEqual(len(result["model"]["frames"]), 5)


if __name__ == "__main__":
    unittest.main()
