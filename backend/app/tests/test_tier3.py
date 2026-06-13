"""Tier-3 LLM-authored, validated path (PROJECTOR_SYSTEM_SPEC §9).

A well-formed payload (real code + graph + contract) validates at T4; a hallucinated
algorithm (wrong output) or a non-resolving contract is rejected. The LLM proposes; the
tracer + validators dispose.

Run: python -m unittest app.tests.test_tier3
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.tier3 import author_and_run, run_tier3, tier3_enabled

_NODES = ["A", "B", "C", "D", "E"]
_EDGES = [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"], ["D", "E"]]
_W = [["A", "B", 1], ["A", "C", 4], ["B", "D", 5], ["C", "E", 2], ["D", "E", 3]]

# What a correct LLM proposal looks like (Prim).
GOOD_CODE = (
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
# Prim on this graph selects A-B(1), A-C(4), C-E(2), D-E(3) in that order.
GOOD_OUTPUT = [["A", "B"], ["A", "C"], ["C", "E"], ["D", "E"]]


def _payload(**over):
    p = {
        "example_id": "prim_llm",
        "code": GOOD_CODE,
        "entry_function": "prim",
        "input": {"args": [_NODES, _W, "A"]},
        "base_structure": {"nodes": _NODES, "edges": _EDGES},
        "graph_projection": {"current_from": "node", "visited_from": "in_mst", "selected_edges_from": "mst"},
        "expected_output": GOOD_OUTPUT,
    }
    p.update(over)
    return p


class TestTier3(unittest.TestCase):
    def test_good_payload_validates_at_t4(self):
        result = run_tier3(_payload(), model_id="t4")
        self.assertEqual(result["status"], "validated", result.get("errors"))
        prov = result["model"]["provenance"]
        self.assertEqual(prov["tier"], "T4")
        self.assertEqual(prov["state_source"], "llm_validated_projection")

    def test_hallucinated_output_is_rejected(self):
        result = run_tier3(_payload(expected_output=[["X", "Y"]]))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "Tier3OutputMismatch")

    def test_nonresolving_contract_is_rejected(self):
        result = run_tier3(_payload(graph_projection={"current_from": "nope", "visited_from": "in_mst"}))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "ProjectionValidator")

    def test_missing_field_is_rejected(self):
        p = _payload()
        p.pop("code")
        self.assertEqual(run_tier3(p)["stage"], "Tier3Payload")


class TestTier3Gate(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AZALEA_PROJECTOR_TIER3", None)

    def test_disabled_by_default(self):
        os.environ.pop("AZALEA_PROJECTOR_TIER3", None)
        self.assertFalse(tier3_enabled())
        self.assertIsNone(author_and_run({"title": "x"}, author=lambda t: _payload()))

    def test_enabled_runs_injected_author(self):
        os.environ["AZALEA_PROJECTOR_TIER3"] = "1"
        result = author_and_run({"title": "Prim"}, author=lambda t: _payload())
        self.assertIsNotNone(result)
        self.assertEqual(result["model"]["provenance"]["tier"], "T4")


if __name__ == "__main__":
    unittest.main()
