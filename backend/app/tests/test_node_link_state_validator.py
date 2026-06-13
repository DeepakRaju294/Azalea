"""The projector guardrail (PROJECTOR_SYSTEM_SPEC §6.1, §6.2, §6.4 INV-RENDER/COMPLETE).

These make the MST-style "renders empty silently" failure impossible to ship. Every
case is asserted by the *shape of the defect* (empty / static / blank-label / dangling
edge / truncated), never by a topic name — so the suite cannot be gamed by hardcoding
an instance (§15).

Run: python -m unittest app.tests.test_node_link_state_validator
"""
from __future__ import annotations

import unittest

from app.services.visual_v2 import validators as V


def _frame(active, states):
    """One node_link frame. `states` maps node_id -> state string."""
    return {
        "state": {
            "active_node": active or "",
            "completed_nodes": [n for n, s in states.items() if s == "completed"],
            "node_state_map": [{"node_id": n, "state": s} for n, s in states.items()],
            "runtime_state": {"output": [active] if active else []},
        }
    }


def _model(nodes, edges, frames):
    return {
        "id": "m",
        "base_type": "node_link_diagram",
        "base": {
            "nodes": [{"id": n, "label": n} for n in nodes],
            "edges": [{"from": a, "to": b} for a, b in edges],
        },
        "frames": frames,
    }


def _good_model():
    # A→B→C traversal: state present every step and changing.
    nodes, edges = ["A", "B", "C"], [("A", "B"), ("B", "C")]
    frames = [
        _frame("A", {"A": "current", "B": "unvisited", "C": "unvisited"}),
        _frame("B", {"A": "completed", "B": "current", "C": "unvisited"}),
        _frame("C", {"A": "completed", "B": "completed", "C": "current"}),
    ]
    return _model(nodes, edges, frames)


class TestNodeLinkState(unittest.TestCase):
    def test_good_model_passes(self):
        self.assertEqual(V.validate_node_link_state(_good_model()), [])

    def test_empty_state_is_rejected(self):
        # The MST bug: nodes + edges, but nothing is ever active/visited.
        nodes, edges = ["A", "B", "C"], [("A", "B")]
        frames = [_frame("", {n: "unvisited" for n in nodes}) for _ in range(3)]
        errs = V.validate_node_link_state(_model(nodes, edges, frames))
        self.assertTrue(any("empty_node_state" in e for e in errs), errs)

    def test_static_state_is_rejected(self):
        nodes, edges = ["A", "B", "C"], [("A", "B")]
        f = _frame("A", {"A": "current", "B": "unvisited", "C": "unvisited"})
        errs = V.validate_node_link_state(_model(nodes, edges, [f, dict(f), dict(f)]))
        self.assertTrue(any("static_state" in e for e in errs), errs)

    def test_unknown_node_is_rejected(self):
        m = _good_model()
        m["frames"][1]["state"]["active_node"] = "Z"  # not in the graph
        errs = V.validate_node_link_state(m)
        self.assertTrue(any("not a real node" in e for e in errs), errs)

    def test_non_node_link_is_skipped(self):
        self.assertEqual(V.validate_node_link_state({"base_type": "code_execution_panel", "frames": [{}]}), [])


class TestRenderInvariant(unittest.TestCase):
    def test_good_model_passes(self):
        self.assertEqual(V.validate_node_link_render(_good_model()), [])

    def test_blank_label_rejected(self):
        m = _good_model()
        m["base"]["nodes"][1]["label"] = "  "
        self.assertTrue(any("blank label" in e for e in V.validate_node_link_render(m)))

    def test_duplicate_label_rejected(self):
        m = _good_model()
        m["base"]["nodes"][1]["label"] = "A"  # B now labelled A
        self.assertTrue(any("duplicate node labels" in e for e in V.validate_node_link_render(m)))

    def test_dangling_edge_rejected(self):
        m = _good_model()
        m["base"]["edges"].append({"from": "A", "to": "Z"})
        self.assertTrue(any("not in the graph" in e for e in V.validate_node_link_render(m)))

    def test_duplicate_edge_rejected(self):
        m = _good_model()
        m["base"]["edges"].append({"from": "B", "to": "A"})  # same as A-B undirected
        self.assertTrue(any("duplicate edge" in e for e in V.validate_node_link_render(m)))

    def test_placeholder_label_rejected(self):
        m = _good_model()
        m["base"]["nodes"][0]["label"] = "node"
        self.assertTrue(any("placeholder label" in e for e in V.validate_node_link_render(m)))


class TestCompleteness(unittest.TestCase):
    def test_terminal_reached_passes(self):
        self.assertEqual(V.validate_completeness(_good_model(), ["A", "B", "C"]), [])

    def test_truncated_to_empty_rejected(self):
        nodes, edges = ["A", "B", "C"], [("A", "B")]
        frames = [
            _frame("A", {"A": "current", "B": "unvisited", "C": "unvisited"}),
            _frame("", {"A": "unvisited", "B": "unvisited", "C": "unvisited"}),  # ends empty
        ]
        errs = V.validate_completeness(_model(nodes, edges, frames), None)
        self.assertTrue(any("INV-COMPLETE" in e for e in errs), errs)

    def test_missing_expected_node_rejected(self):
        m = _good_model()
        errs = V.validate_completeness(m, ["A", "B", "C", "D"])  # D never reached
        # D is not in the graph, so it's filtered out; expect pass here…
        self.assertEqual(errs, [])
        # …but a node that IS in the graph yet never completed must fail:
        m["base"]["nodes"].append({"id": "D", "label": "D"})
        errs2 = V.validate_completeness(m, ["A", "B", "C", "D"])
        self.assertTrue(any("missing expected nodes" in e for e in errs2), errs2)


class TestEmptyDetection(unittest.TestCase):
    def test_detects_empty(self):
        nodes = ["A", "B"]
        frames = [_frame("", {n: "unvisited" for n in nodes})]
        self.assertTrue(V.node_link_state_is_empty(_model(nodes, [], frames)))

    def test_not_empty_when_active(self):
        self.assertFalse(V.node_link_state_is_empty(_good_model()))


if __name__ == "__main__":
    unittest.main()
