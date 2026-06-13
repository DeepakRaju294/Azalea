"""Visual System V2 — Slice 2 (NodeLinkCompiler) tests. Pure backend, no LLM.

Proves: folded frames -> a frontend-consumable VisualModel; semantic node states
are the diff; the compiler styles but never re-decides the trace (§6.3).
Run: python -m unittest app.tests.test_visual_v2_slice2   (from backend/, PYTHONPATH=.)
"""
from __future__ import annotations

import copy
import unittest

from app.services.visual_v2.compilers.node_link import compile_from_trace
from app.services.visual_v2.delta_fold import DeltaFoldEngine
from app.services.visual_v2.profiles import delta_vocabulary, profile_for_mode
from app.services.visual_v2.simulators.registry import get_simulator

BFS_EXAMPLE = {
    "example_id": "bfs_appendix",
    "mode": "graph_network",
    "algorithm": "bfs",
    "input": {"start": "A"},
    "base_structure": {
        "nodes": ["A", "B", "C", "D", "E"],
        "edges": [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"]],
    },
}


def _state_map(frame):
    return {entry["node_id"]: entry["state"] for entry in frame["state"]["node_state_map"]}


class TestNodeLinkCompiler(unittest.TestCase):
    def setUp(self):
        self.trace = get_simulator("bfs")(BFS_EXAMPLE)
        self.profile = profile_for_mode("graph_network")
        self.frames = DeltaFoldEngine().fold(
            self.trace["initial_state"],
            self.trace["steps"],
            set(BFS_EXAMPLE["base_structure"]["nodes"]),
            delta_vocabulary("graph_network"),
        )
        self.model, self.render_steps = compile_from_trace(
            trace=self.trace,
            frames=self.frames,
            base_structure=BFS_EXAMPLE["base_structure"],
            profile=self.profile,
            mode="graph_network",
            model_id="m1",
        )

    def test_base_has_nodes_with_layout_and_edges(self):
        nodes = self.model["base"]["nodes"]
        self.assertEqual(len(nodes), 5)
        for n in nodes:
            self.assertIn("x", n)
            self.assertIn("y", n)
            self.assertTrue(0 <= n["x"] <= 100 and 0 <= n["y"] <= 100)
        self.assertEqual(len(self.model["base"]["edges"]), 4)

    def test_frame_count_matches(self):
        self.assertEqual(len(self.model["frames"]), 5)
        self.assertEqual(len(self.render_steps), 5)

    def test_node_state_snapshot_step1(self):
        # active A; B,C just discovered; D,E untouched.
        self.assertEqual(
            _state_map(self.model["frames"][0]),
            {"A": "current", "B": "newly_discovered", "C": "newly_discovered", "D": "unvisited", "E": "unvisited"},
        )

    def test_node_state_snapshot_step2(self):
        # A done, B current, C waiting in queue, D just discovered, E untouched.
        self.assertEqual(
            _state_map(self.model["frames"][1]),
            {"A": "completed", "B": "current", "C": "discovered", "D": "newly_discovered", "E": "unvisited"},
        )

    def test_node_state_snapshot_final(self):
        self.assertEqual(
            _state_map(self.model["frames"][4]),
            {"A": "completed", "B": "completed", "C": "completed", "D": "completed", "E": "current"},
        )

    def test_panels_reflect_runtime_state(self):
        final = self.model["frames"][4]["state"]["runtime_state"]
        self.assertEqual(final["output"], ["A", "B", "C", "D", "E"])
        self.assertEqual(final["frontier_kind"], "queue")
        self.assertEqual(self.model["frames"][1]["state"]["runtime_state"]["frontier"], ["C", "D"])

    def test_render_steps_aligned_with_frames(self):
        for i, rs in enumerate(self.render_steps):
            self.assertEqual(rs["frame_index"], i)
            self.assertTrue(rs["caption"])  # carries learner_should_notice
            self.assertTrue(rs["trace_step_id"])

    def test_compiler_does_not_re_decide_the_trace(self):
        # Frontend-facing state must equal the folded truth, not a recomputation.
        for frame_model, frame_state in zip(self.model["frames"], self.frames):
            after = frame_state["state_after"]
            self.assertEqual(frame_model["state"]["active_node"], after.get("active") or "")
            self.assertEqual(frame_model["state"]["completed_nodes"], after["visited"])
            self.assertEqual(frame_model["state"]["runtime_state"]["output"], after["output"])

    def test_compiler_does_not_mutate_trace(self):
        before = copy.deepcopy(self.trace)
        compile_from_trace(
            trace=self.trace,
            frames=self.frames,
            base_structure=BFS_EXAMPLE["base_structure"],
            profile=self.profile,
            mode="graph_network",
            model_id="m2",
        )
        self.assertEqual(self.trace, before)

    def test_model_carries_ids(self):
        self.assertEqual(self.model["example_id"], "bfs_appendix")
        self.assertTrue(self.model["trace_id"])


if __name__ == "__main__":
    unittest.main()
