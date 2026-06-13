"""Visual System V2 — Slice 1 (deterministic trace core) tests.

Pure backend, no LLM/API. The §11 BFS appendix is the golden trace.
Run: python -m unittest app.tests.test_visual_v2_slice1   (from backend/, PYTHONPATH=.)
"""
from __future__ import annotations

import unittest

from app.services.visual_v2.delta_fold import DeltaFoldEngine, InvalidDeltaError
from app.services.visual_v2.example_invariants import validate_example
from app.services.visual_v2.profiles import delta_vocabulary
from app.services.visual_v2.simulators.registry import (
    get_simulator,
    is_registered,
    registered_algorithms,
)

# §11 appendix graph: A-B, A-C, B-D, C-E ; start A.
BFS_EXAMPLE = {
    "example_id": "bfs_appendix",
    "domain_object": "graph",
    "base_type": "node_link_diagram",
    "mode": "graph_network",
    "algorithm": "bfs",
    "input": {"start": "A"},
    "base_structure": {
        "nodes": ["A", "B", "C", "D", "E"],
        "edges": [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"]],
    },
    "why_this_example": "Small branching graph that shows level order.",
    "learner_goal": "Trace BFS order.",
}


def _ids(example):
    return set(example["base_structure"]["nodes"])


class TestExampleInvariants(unittest.TestCase):
    def test_valid_example_has_no_errors(self):
        self.assertEqual(validate_example(BFS_EXAMPLE), [])

    def test_too_trivial_rejected(self):
        ex = {**BFS_EXAMPLE, "base_structure": {"nodes": ["A"], "edges": []}, "input": {"start": "A"}}
        errs = validate_example(ex)
        self.assertTrue(any("too trivial" in e for e in errs), errs)

    def test_edge_to_unknown_node_rejected(self):
        ex = {**BFS_EXAMPLE, "base_structure": {"nodes": ["A", "B", "C", "D", "E"], "edges": [["A", "Z"]]}}
        self.assertTrue(any("unknown node" in e for e in validate_example(ex)))

    def test_start_not_in_graph_rejected(self):
        ex = {**BFS_EXAMPLE, "input": {"start": "Z"}}
        self.assertTrue(any("start node" in e for e in validate_example(ex)))

    def test_no_branching_rejected(self):
        ex = {
            **BFS_EXAMPLE,
            "base_structure": {"nodes": ["A", "B", "C", "D", "E"], "edges": [["A", "B"]]},
        }
        self.assertTrue(any("branching" in e for e in validate_example(ex)))


class TestBfsSimulatorGolden(unittest.TestCase):
    def setUp(self):
        self.trace = get_simulator("bfs")(BFS_EXAMPLE)

    def test_trace_source_is_simulator(self):
        self.assertEqual(self.trace["trace_source"], "deterministic_simulator")

    def test_initial_state_matches_appendix(self):
        self.assertEqual(
            self.trace["initial_state"],
            {"active": None, "frontier": {"kind": "queue", "items": ["A"]}, "visited": [], "output": []},
        )

    def test_step1_delta_matches_appendix(self):
        self.assertEqual(
            self.trace["steps"][0]["delta"],
            {
                "set_active": "A",
                "remove_from_frontier": ["A"],
                "newly_visited": ["A"],
                "add_to_frontier": ["B", "C"],
                "append_to_output": ["A"],
            },
        )

    def test_step2_delta_matches_appendix(self):
        self.assertEqual(
            self.trace["steps"][1]["delta"],
            {
                "set_active": "B",
                "remove_from_frontier": ["B"],
                "newly_visited": ["B"],
                "add_to_frontier": ["D"],
                "append_to_output": ["B"],
            },
        )


class TestDeltaFoldGolden(unittest.TestCase):
    def setUp(self):
        self.trace = get_simulator("bfs")(BFS_EXAMPLE)
        self.frames = DeltaFoldEngine().fold(
            self.trace["initial_state"],
            self.trace["steps"],
            _ids(BFS_EXAMPLE),
            delta_vocabulary("graph_network"),
        )

    def test_step2_folded_state_matches_spec_appendix(self):
        # §11: state_after step 2 = {visited:[A,B], queue:[C,D], output:[A,B]}.
        after = self.frames[1]["state_after"]
        self.assertEqual(after["visited"], ["A", "B"])
        self.assertEqual(after["frontier"]["items"], ["C", "D"])
        self.assertEqual(after["output"], ["A", "B"])

    def test_full_state_after_sequence(self):
        expected_visited = [["A"], ["A", "B"], ["A", "B", "C"], ["A", "B", "C", "D"], ["A", "B", "C", "D", "E"]]
        expected_frontier = [["B", "C"], ["C", "D"], ["D", "E"], ["E"], []]
        self.assertEqual(len(self.frames), 5)
        for frame, vis, fr in zip(self.frames, expected_visited, expected_frontier):
            self.assertEqual(frame["state_after"]["visited"], vis)
            self.assertEqual(frame["state_after"]["frontier"]["items"], fr)
        self.assertEqual(self.frames[-1]["state_after"]["output"], ["A", "B", "C", "D", "E"])

    def test_diff_metadata_step1(self):
        diff = self.frames[0]["diff"]
        self.assertEqual(diff["set_active"], "A")
        self.assertEqual(diff["newly_added"], ["B", "C"])
        self.assertEqual(diff["newly_completed"], ["A"])

    def test_state_before_equals_prior_state_after(self):
        for i in range(1, len(self.frames)):
            self.assertEqual(self.frames[i]["state_before"], self.frames[i - 1]["state_after"])


class TestDeltaFoldErrors(unittest.TestCase):
    def test_unknown_op_raises(self):
        steps = [{"delta": {"teleport": "A"}}]
        with self.assertRaises(InvalidDeltaError):
            DeltaFoldEngine().fold(
                {"active": None, "frontier": {"kind": "queue", "items": []}, "visited": [], "output": []},
                steps,
                {"A"},
                delta_vocabulary("graph_network"),
            )

    def test_unknown_id_raises(self):
        steps = [{"delta": {"set_active": "Z"}}]
        with self.assertRaises(InvalidDeltaError):
            DeltaFoldEngine().fold(
                {"active": None, "frontier": {"kind": "queue", "items": []}, "visited": [], "output": []},
                steps,
                {"A"},
                delta_vocabulary("graph_network"),
            )

    def test_no_op_folds_without_state_change(self):
        init = {"active": "A", "frontier": {"kind": "queue", "items": ["B"]}, "visited": ["A"], "output": ["A"]}
        steps = [{"delta": {"no_op": True, "checked_element_ids": ["B"], "reason": "B already visited"}}]
        frames = DeltaFoldEngine().fold(init, steps, {"A", "B"}, delta_vocabulary("graph_network"))
        self.assertEqual(frames[0]["state_after"], init)
        self.assertTrue(frames[0]["diff"]["no_op"])


class TestDfsSimulator(unittest.TestCase):
    def test_dfs_registered_and_traces_all_nodes(self):
        self.assertTrue(is_registered("dfs"))
        ex = {**BFS_EXAMPLE, "example_id": "dfs_ex", "algorithm": "dfs"}
        trace = get_simulator("dfs")(ex)
        self.assertEqual(trace["initial_state"]["frontier"]["kind"], "stack")
        frames = DeltaFoldEngine().fold(
            trace["initial_state"], trace["steps"], _ids(ex), delta_vocabulary("graph_network")
        )
        # Every node visited exactly once, A first.
        output = frames[-1]["state_after"]["output"]
        self.assertEqual(sorted(output), ["A", "B", "C", "D", "E"])
        self.assertEqual(output[0], "A")
        self.assertEqual(len(output), len(set(output)))

    def test_registry_lists_bfs_dfs(self):
        registered = set(registered_algorithms())
        self.assertEqual(registered_algorithms(), sorted(registered))  # sorted
        self.assertTrue({"bfs", "dfs"} <= registered)  # core graph sims present


if __name__ == "__main__":
    unittest.main()
