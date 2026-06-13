"""Visual System V2 — Slice 3 (validators + orchestrator). Pure backend, no LLM.

Run: python -m unittest app.tests.test_visual_v2_slice3   (from backend/, PYTHONPATH=.)
"""
from __future__ import annotations

import unittest

from app.services.visual_v2.pipeline import run_for_registered
from app.services.visual_v2.profiles import profile_for_mode
from app.services.visual_v2.validators import (
    pedagogical_check,
    validate_model,
    validate_trace,
)

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


class TestPipelineHappyPath(unittest.TestCase):
    def setUp(self):
        self.result = run_for_registered(BFS_EXAMPLE, topic_id="t1", card_id="c1")

    def test_status_validated(self):
        self.assertEqual(self.result["status"], "validated")
        self.assertEqual(self.result["pedagogy"]["verdict"], "ok")

    def test_model_and_render_steps_produced(self):
        self.assertEqual(len(self.result["model"]["frames"]), 5)
        self.assertEqual(len(self.result["render_steps"]), 5)

    def test_debug_payload_is_reproducible(self):
        dbg = self.result["debug"]
        self.assertEqual(dbg["example_id"], "bfs_appendix")
        self.assertEqual(dbg["trace_source"], "deterministic_simulator")
        self.assertEqual(dbg["visual_status"], "validated")
        self.assertEqual(dbg["mode"], "graph_network")


class TestPipelineFailures(unittest.TestCase):
    def test_invalid_example_fails_pre_trace(self):
        ex = {**BFS_EXAMPLE, "base_structure": {"nodes": ["A"], "edges": []}}
        res = run_for_registered(ex)
        self.assertEqual(res["status"], "failed")
        self.assertEqual(res["stage"], "ExampleInvariantValidator")
        self.assertIsNone(res["model"])

    def test_unregistered_algorithm_fails(self):
        ex = {**BFS_EXAMPLE, "algorithm": "a_star"}
        res = run_for_registered(ex)
        self.assertEqual(res["status"], "failed")
        self.assertEqual(res["stage"], "not_registered")


class TestValidators(unittest.TestCase):
    def test_trace_validator_catches_empty_delta(self):
        trace = {
            "initial_state": {"active": None, "frontier": {"kind": "queue", "items": []}, "visited": [], "output": []},
            "steps": [{"step_index": 0, "delta": {}}],
        }
        errs = validate_trace(trace, {"A"}, "graph_network")
        self.assertTrue(any("empty delta" in e for e in errs))

    def test_trace_validator_passes_real_trace(self):
        res = run_for_registered(BFS_EXAMPLE)
        self.assertEqual(validate_trace(res["trace"], set(BFS_EXAMPLE["base_structure"]["nodes"]), "graph_network"), [])

    def test_model_validator_catches_missing_nodes(self):
        self.assertTrue(any("no nodes" in e for e in validate_model({"base": {"nodes": []}, "frames": []})))

    def test_model_validator_catches_unstable_ids(self):
        model = {
            "base": {"nodes": [{"id": "A"}, {"id": "B"}]},
            "frames": [
                {"state": {"active_node": "A", "node_state_map": [{"node_id": "A", "state": "current"}]}},
                {"state": {"active_node": "B", "node_state_map": [{"node_id": "B", "state": "current"}]}},
            ],
        }
        self.assertTrue(any("unstable node ids" in e for e in validate_model(model)))

    def test_pedagogical_rejects_single_node(self):
        profile = profile_for_mode("graph_network")
        model = {"base": {"nodes": [{"id": "A", "label": "A"}]}}
        self.assertEqual(pedagogical_check(model, profile)["verdict"], "reject")

    def test_pedagogical_rejects_generic_labels(self):
        profile = profile_for_mode("graph_network")
        model = {"base": {"nodes": [{"id": str(i), "label": "node"} for i in range(6)]}}
        self.assertEqual(pedagogical_check(model, profile)["verdict"], "reject")

    def test_pedagogical_accepts_real_model(self):
        profile = profile_for_mode("graph_network")
        res = run_for_registered(BFS_EXAMPLE)
        self.assertEqual(pedagogical_check(res["model"], profile)["verdict"], "ok")


if __name__ == "__main__":
    unittest.main()
