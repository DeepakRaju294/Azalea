"""Live routing of projected (T2) fixtures (PROJECTOR_SYSTEM_SPEC §7 + Example System).

A real MST / Dijkstra *topic title* now flows declare → pick_fixture →
fixture_to_canonical_example → run_for_registered and lands a validated node_link
worked example at tier T2 — without a registered simulator. This is the holistic fix
for the MST "nothing highlights" bug: graph algorithms come off the legacy cliff.

Run: python -m unittest app.tests.test_projected_fixture_chain
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.core.example_applications import match_application
from app.services.examples.declaration import declare_example, pick_fixture
from app.services.examples.handoff import fixture_to_canonical_example
from app.services.visual_v2.pipeline import run_for_registered


def _run_topic(title: str):
    declared = declare_example({"id": "t", "title": title, "topic_type": "algorithm_walkthrough"})
    assert declared is not None, f"no application for {title!r}"
    fx = pick_fixture(declared, "worked_example")
    assert fx is not None, f"no fixture for {declared}"
    example = fixture_to_canonical_example(fx)
    return declared, fx, run_for_registered(example, model_id="chain")


class TestTitleRouting(unittest.TestCase):
    def test_mst_titles_match(self):
        for title in ["Prim's Algorithm", "Minimum Spanning Tree", "Kruskal's MST"]:
            self.assertEqual(match_application(title), "minimum_spanning_tree", title)

    def test_dijkstra_titles_match(self):
        for title in ["Dijkstra's Algorithm", "Shortest Path in a Graph"]:
            self.assertEqual(match_application(title), "shortest_path", title)


class TestProjectedFixtureChain(unittest.TestCase):
    def test_prim_topic_lands_validated_t2(self):
        declared, fx, result = _run_topic("Prim's Algorithm for Minimum Spanning Trees")
        self.assertEqual(declared.application, "minimum_spanning_tree")
        self.assertEqual(fx.fixture_id, "minimum_spanning_tree_prim_concept_01")
        self.assertEqual(result["status"], "validated", result.get("errors"))
        self.assertEqual(result["model"]["provenance"]["tier"], "T2")
        final = result["model"]["frames"][-1]["state"]
        self.assertEqual(len(final["completed_edges_from"]), len(fx.base_structure["nodes"]) - 1)

    def test_dijkstra_topic_lands_validated_t2(self):
        declared, fx, result = _run_topic("Dijkstra's Shortest Path Algorithm")
        self.assertEqual(declared.application, "shortest_path")
        self.assertEqual(result["status"], "validated", result.get("errors"))
        self.assertEqual(result["model"]["provenance"]["tier"], "T2")
        # node highlighting is non-empty (the MST-bug guardrail would have rejected empty)
        self.assertFalse(
            all(not f["state"].get("active_node") for f in result["model"]["frames"])
        )


if __name__ == "__main__":
    unittest.main()
