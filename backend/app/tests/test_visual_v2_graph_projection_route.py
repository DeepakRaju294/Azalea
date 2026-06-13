"""The T2 graph_projection route end-to-end (PROJECTOR_SYSTEM_SPEC §7, §15 test 3).

Prim and Dijkstra — neither has a registered simulator — each produce a *validated*
node_link worked example from only `code + a GraphProjection contract`, routed through
the real `run_for_registered`. Same machinery, two algorithms; provenance is T2.

Run: python -m unittest app.tests.test_visual_v2_graph_projection_route
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.visual_v2.pipeline import run_for_registered

_NODES = ["A", "B", "C", "D", "E"]
_EDGES = [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"], ["D", "E"]]
_W_EDGES = [["A", "B", 1], ["A", "C", 4], ["B", "D", 5], ["C", "E", 2], ["D", "E", 3]]

PRIM_CODE = '''
def prim(nodes, edges, start):
    in_mst = [start]
    mst = []
    while len(in_mst) < len(nodes):
        best = None
        for edge in edges:
            a, b, w = edge
            if (a in in_mst) != (b in in_mst):
                if best is None or w < best[2]:
                    best = (a, b, w)
        a, b, w = best
        node = b if a in in_mst else a
        in_mst.append(node)
        mst.append((a, b))
    return mst
'''

DIJKSTRA_CODE = '''
def dijkstra(nodes, edges, start):
    import heapq
    dist = {n: 999 for n in nodes}
    dist[start] = 0
    done = []
    pq = [(0, start)]
    while pq:
        d, u = heapq.heappop(pq)
        if u in done:
            continue
        done.append(u)
        for edge in edges:
            a, b, w = edge
            if a == u or b == u:
                v = b if a == u else a
                if d + w < dist[v]:
                    dist[v] = d + w
                    heapq.heappush(pq, (dist[v], v))
    return done
'''


def _prim_example():
    return {
        "example_id": "prim_mst",
        "base_type": "node_link_diagram",
        "mode": "graph_projection",
        "code": PRIM_CODE,
        "entry_function": "prim",
        "input": {"args": [_NODES, _W_EDGES, "A"], "start": "A"},
        "base_structure": {"nodes": _NODES, "edges": _EDGES},
        "graph_projection": {"current_from": "node", "visited_from": "in_mst", "selected_edges_from": "mst"},
        "expected_output": _NODES,
        "learner_goal": "Build the MST with Prim's algorithm.",
    }


def _dijkstra_example():
    return {
        "example_id": "dijkstra_sp",
        "base_type": "node_link_diagram",
        "mode": "graph_projection",
        "code": DIJKSTRA_CODE,
        "entry_function": "dijkstra",
        "input": {"args": [_NODES, _W_EDGES, "A"], "start": "A"},
        "base_structure": {"nodes": _NODES, "edges": _EDGES},
        "graph_projection": {"current_from": "u", "visit_order_from": "done",
                             "frontier_from": "pq", "frontier_node_key": "index:1"},
        "expected_output": _NODES,
        "learner_goal": "Find shortest paths with Dijkstra's algorithm.",
    }


class TestGraphProjectionRoute(unittest.TestCase):
    def test_prim_validates_at_tier_t2(self):
        result = run_for_registered(_prim_example(), model_id="prim")
        self.assertEqual(result["status"], "validated", result.get("errors"))
        prov = result["model"]["provenance"]
        self.assertEqual(prov["tier"], "T2")
        self.assertEqual(prov["state_source"], "authored_projection")
        self.assertEqual(prov["code_source"], "inline_fixture")
        # MST edges highlighted in the terminal frame.
        final = result["model"]["frames"][-1]["state"]
        self.assertEqual(len(final["completed_edges_from"]), len(_NODES) - 1)

    def test_dijkstra_validates_at_tier_t2(self):
        result = run_for_registered(_dijkstra_example(), model_id="dij")
        self.assertEqual(result["status"], "validated", result.get("errors"))
        self.assertEqual(result["model"]["provenance"]["tier"], "T2")
        # every node finalized by the end
        final = result["model"]["frames"][-1]["state"]
        reached = {e["node_id"] for e in final["node_state_map"]
                   if e["state"] in ("completed", "current")}
        if final.get("active_node"):
            reached.add(final["active_node"])
        self.assertEqual(reached, set(_NODES))

    def test_missing_contract_infers_at_tier_t3(self):
        # No authored contract → inference recovers one (§8) → tier T3.
        ex = _prim_example()
        ex.pop("graph_projection")
        result = run_for_registered(ex, model_id="t3")
        self.assertEqual(result["status"], "validated", result.get("errors"))
        self.assertEqual(result["model"]["provenance"]["tier"], "T3")
        self.assertEqual(result["model"]["provenance"]["state_source"], "inferred_projection")
        self.assertIn(result["model"]["provenance"]["confidence_band"], ("high", "medium", "low"))

    def test_missing_code_fails_cleanly(self):
        ex = _prim_example()
        ex.pop("code")
        result = run_for_registered(ex, model_id="bad")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "graph_projection_inputs")

    def test_bad_contract_variable_fails_at_projection_validator(self):
        ex = _prim_example()
        ex["graph_projection"] = {"current_from": "nope", "visited_from": "in_mst"}
        result = run_for_registered(ex, model_id="bad2")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "ProjectionValidator")


if __name__ == "__main__":
    unittest.main()
