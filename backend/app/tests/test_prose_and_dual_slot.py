"""Step 6 — INV-PROSE-SYNC + INV-DUAL-SLOT + edge-aware prose (PROJECTOR_SYSTEM_SPEC §6.4).

MST prose narrates the EDGE added (not a phantom dequeue); Dijkstra reads as a priority
queue; prose is grounded to the frame (INV-PROSE-SYNC); the dual-slot validator catches a
code worked example missing its diagram. Asserted by content/defect, not topic.

Run: python -m unittest app.tests.test_prose_and_dual_slot
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.handoff import fixture_to_canonical_example
from app.services.examples.prose_slot import build_prose_slots, validate_prose_sync
from app.services.visual_v2.pipeline import run_for_registered
from app.services.visual_v2.validators import validate_dual_slot
from app.core.example_fixtures import fixtures_for


def _run(application):
    fx = fixtures_for(application)[0]
    result = run_for_registered(fixture_to_canonical_example(fx), model_id="t")
    assert result["status"] == "validated", result.get("errors")
    return fx, result


class TestEdgeAwareProse(unittest.TestCase):
    def test_mst_prose_mentions_edges_not_a_queue(self):
        fx, result = _run("minimum_spanning_tree")
        slots = build_prose_slots(result, list(range(len(result["frames"]))), fx)
        text = " ".join(b for s in slots for b in s.bullets).lower()
        self.assertIn("edge", text)               # narrates edge selection
        self.assertIn("tree", text)
        self.assertNotIn("dequeue", text)          # NOT a traversal
        self.assertNotIn("oldest node", text)

    def test_dijkstra_prose_reads_as_priority_queue(self):
        fx, result = _run("shortest_path")
        slots = build_prose_slots(result, list(range(len(result["frames"]))), fx)
        text = " ".join(b for s in slots for b in s.bullets).lower()
        # priority-queue framing, not "oldest in the queue"
        self.assertTrue("closest" in text or "priority queue" in text, text)
        self.assertNotIn("oldest node waiting", text)


class TestProseSync(unittest.TestCase):
    def test_grounded_prose_passes(self):
        fx, result = _run("minimum_spanning_tree")
        node_ids = fx.base_structure["nodes"]
        for fi, frame in enumerate(result["frames"]):
            slots = build_prose_slots(result, [fi], fx)
            errs = validate_prose_sync(list(slots[0].bullets), frame["state_after"], node_ids)
            self.assertEqual(errs, [], f"frame {fi}: {errs}")

    def test_citing_absent_node_is_flagged(self):
        after = {"active": "A", "visited": ["A"], "selected_edges": [["A", "B"]]}
        errs = validate_prose_sync(["Now visit Z next."], after, ["A", "B", "Z"])
        self.assertTrue(any("Z" in e for e in errs), errs)


class TestDualSlot(unittest.TestCase):
    def test_code_worked_example_without_diagram_flagged(self):
        card = {"blueprint_key": "worked_example", "code_snippet": "x = 1"}
        errs = validate_dual_slot(card)
        self.assertTrue(any("no supporting diagram" in e for e in errs), errs)

    def test_code_worked_example_with_diagram_passes(self):
        card = {"blueprint_key": "worked_example", "code_snippet": "x = 1",
                "diagram_v2_ref": {"visual_model_id": "m"}}
        self.assertEqual(validate_dual_slot(card), [])

    def test_desynced_event_ids_flagged(self):
        card = {"blueprint_key": "worked_example", "code_snippet": "x = 1",
                "visual_v2_ref": {"event_id": "visit:C:01"},
                "diagram_v2_ref": {"visual_model_id": "m", "event_id": "visit:D:02"}}
        self.assertTrue(any("desynced" in e for e in validate_dual_slot(card)))

    def test_non_code_card_ignored(self):
        self.assertEqual(validate_dual_slot({"blueprint_key": "worked_example", "visual_type": "node_link_diagram"}), [])


if __name__ == "__main__":
    unittest.main()
