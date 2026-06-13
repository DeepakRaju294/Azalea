"""Projector telemetry rollups (PROJECTOR_SYSTEM_SPEC §14).

Running T1 (registered), T2 (authored projection), and T3 (inferred) records per-tier
counts + inference outcomes, so the legacy tail and inference quality are measured.

Run: python -m unittest app.tests.test_projector_telemetry
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.visual_v2.invariant_metrics import GLOBAL as INV
from app.services.visual_v2.pipeline import run_for_registered

_NODES = ["A", "B", "C", "D", "E"]
_EDGES = [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"], ["D", "E"]]
_W = [["A", "B", 1], ["A", "C", 4], ["B", "D", 5], ["C", "E", 2], ["D", "E", 3]]
_GRAPH = {"A": ["B", "C"], "B": ["A", "D"], "C": ["A", "E"], "D": ["B", "E"], "E": ["C", "D"]}

PRIM = (
    "def prim(nodes, edges, start):\n"
    "    in_mst = [start]\n"
    "    mst = []\n"
    "    while len(in_mst) < len(nodes):\n"
    "        best = None\n"
    "        for edge in edges:\n"
    "            a, b, w = edge\n"
    "            if (a in in_mst) != (b in in_mst):\n"
    "                if best is None or w < best[2]:\n"
    "                    best = (a, b, w)\n"
    "        a, b, w = best\n"
    "        node = b if a in in_mst else a\n"
    "        in_mst.append(node)\n"
    "        mst.append((a, b))\n"
    "    return mst"
)


def _t1():
    return {"example_id": "bfs", "base_type": "node_link_diagram", "mode": "graph_network",
            "algorithm": "bfs", "input": {"start": "A"},
            "base_structure": {"nodes": _NODES, "edges": _EDGES}, "learner_goal": "x"}


def _prim(with_contract: bool):
    ex = {"example_id": "prim", "base_type": "node_link_diagram", "mode": "graph_projection",
          "code": PRIM, "entry_function": "prim",
          "input": {"args": [_NODES, _W, "A"], "start": "A"},
          "base_structure": {"nodes": _NODES, "edges": _EDGES}, "expected_output": _NODES}
    if with_contract:
        ex["graph_projection"] = {"current_from": "node", "visited_from": "in_mst", "selected_edges_from": "mst"}
    return ex


class TestTelemetry(unittest.TestCase):
    def setUp(self):
        INV.reset()

    def test_tiers_and_inference_recorded(self):
        self.assertEqual(run_for_registered(_t1(), model_id="a")["status"], "validated")
        self.assertEqual(run_for_registered(_prim(True), model_id="b")["status"], "validated")
        self.assertEqual(run_for_registered(_prim(False), model_id="c")["status"], "validated")

        snap = INV.snapshot()
        self.assertEqual(snap["by_tier"].get("T1"), 1)
        self.assertEqual(snap["by_tier"].get("T2"), 1)
        self.assertEqual(snap["by_tier"].get("T3"), 1)
        self.assertEqual(snap["inference"].get("accepted"), 1)   # only the no-contract run inferred
        self.assertEqual(sum(snap["confidence_bands"].values()), 1)

    def test_endpoint_includes_projector_block(self):
        from app.api.routes.health import v2_metrics

        body = v2_metrics()
        self.assertIn("projector", body)
        self.assertIn("by_tier", body["projector"])


if __name__ == "__main__":
    unittest.main()
