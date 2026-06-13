"""Regeneration / feedback interface (PROJECTOR_SYSTEM_SPEC §11).

A correction targets the contract/input/code and re-derives deterministically; success
requires the model to change in the targeted way (not just re-validate). Issue types map
to targets; patches default to the narrowest scope and need a golden gate to widen.

Run: python -m unittest app.tests.test_feedback
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.feedback import (
    FeedbackRecord,
    RegenerationRequest,
    issue_to_target,
    promotion_gate,
    propose_patch,
    regenerate,
)

_NODES = ["A", "B", "C", "D", "E"]
_EDGES = [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"], ["D", "E"]]
_W = [["A", "B", 1], ["A", "C", 4], ["B", "D", 5], ["C", "E", 2], ["D", "E", 3]]

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


def _example(contract):
    return {
        "example_id": "prim", "base_type": "node_link_diagram", "mode": "graph_projection",
        "code": PRIM, "entry_function": "prim",
        "input": {"args": [_NODES, _W, "A"], "start": "A"},
        "base_structure": {"nodes": _NODES, "edges": _EDGES},
        "graph_projection": contract, "expected_output": _NODES,
    }


class TestIssueMapping(unittest.TestCase):
    def test_known_mappings(self):
        self.assertEqual(issue_to_target("wrong_active_node"), "projection")
        self.assertEqual(issue_to_target("wrong_base_structure"), "input")
        self.assertEqual(issue_to_target("trace_truncated"), "code")
        self.assertEqual(issue_to_target("prose_visual_mismatch"), "prose")


class TestRegenerate(unittest.TestCase):
    def test_projection_correction_changes_the_model(self):
        # Start with current_from="a"; correct it to "node" — must change highlighting.
        ex = _example({"current_from": "a", "visited_from": "in_mst", "selected_edges_from": "mst"})
        req = RegenerationRequest("t", "node_link", "projection", {"current_from": "node"})
        out = regenerate(ex, req)
        self.assertTrue(out["validators_passed"])
        self.assertTrue(out["targeted_change_observed"])
        self.assertTrue(out["success"])
        self.assertTrue(out["diff"].changed_frames)

    def test_noop_correction_is_not_a_success(self):
        # Re-applying the SAME contract must not count as a successful regeneration.
        contract = {"current_from": "node", "visited_from": "in_mst", "selected_edges_from": "mst"}
        ex = _example(contract)
        req = RegenerationRequest("t", "node_link", "projection", {"current_from": "node"})
        out = regenerate(ex, req)
        self.assertTrue(out["validators_passed"])
        self.assertFalse(out["targeted_change_observed"])  # nothing changed
        self.assertFalse(out["success"])


class TestPatchPromotion(unittest.TestCase):
    def _record(self):
        return FeedbackRecord(
            topic_id="t", application="minimum_spanning_tree", pattern="edge_selection",
            shape="node_link", tier="T2", fixture_id="fx", visual_model_id="m", frame_index=2,
            issue_type="wrong_active_node", user_text="wrong node", severity="blocking",
            user_confidence="high", system_confidence=0.9, correction_target="projection",
            accepted_correction={"current_from": "node"}, post_regen_validation_status="validated",
            targeted_change_observed=True,
        )

    def test_fixture_scope_needs_no_gate(self):
        patch = propose_patch(self._record(), scope="fixture")
        self.assertTrue(promotion_gate(patch, [])["approved"])

    def test_widening_requires_three_passing_checks(self):
        patch = propose_patch(self._record(), scope="application_profile")
        self.assertFalse(promotion_gate(patch, [lambda: True])["approved"])  # too few checks
        self.assertTrue(promotion_gate(patch, [lambda: True, lambda: True, lambda: True])["approved"])
        self.assertFalse(promotion_gate(patch, [lambda: True, lambda: False, lambda: True])["approved"])


if __name__ == "__main__":
    unittest.main()
