"""Visual System V2 — Slice 6 (binary search, second mode). §11.2 golden.

Proves the architecture generalises beyond graphs: a DIFFERENT delta vocabulary
flows through the SAME DeltaFoldEngine. Pure backend, no LLM.
Run: python -m unittest app.tests.test_visual_v2_slice6   (from backend/, PYTHONPATH=.)
"""
from __future__ import annotations

import unittest

from app.services.visual_v2.delta_fold import DeltaFoldEngine
from app.services.visual_v2.example_invariants import validate_example
from app.services.visual_v2.profiles import delta_vocabulary, profile_for_mode
from app.services.visual_v2.simulators.registry import get_simulator, is_registered

# §11.2 appendix: sorted array, target 18.
BS_EXAMPLE = {
    "example_id": "bs_appendix",
    "base_type": "indexed_sequence_diagram",
    "mode": "binary_search_range",
    "algorithm": "binary_search",
    "input": {"target": 18},
    "base_structure": {"array": [3, 7, 9, 12, 18, 21, 30]},
}


def _frames(example):
    trace = get_simulator("binary_search")(example)
    return trace, DeltaFoldEngine().fold(
        trace["initial_state"], trace["steps"], set(range(len(example["base_structure"]["array"]))),
        delta_vocabulary("binary_search_range"),
    )


class TestBinarySearchInvariants(unittest.TestCase):
    def test_valid_sorted_array(self):
        self.assertEqual(validate_example(BS_EXAMPLE), [])

    def test_unsorted_rejected(self):
        ex = {**BS_EXAMPLE, "base_structure": {"array": [3, 9, 7, 12, 18, 21, 30]}}
        self.assertTrue(any("not sorted" in e for e in validate_example(ex)))

    def test_too_short_rejected(self):
        ex = {**BS_EXAMPLE, "base_structure": {"array": [1, 2, 3]}}
        self.assertTrue(any("too trivial" in e for e in validate_example(ex)))

    def test_non_numeric_target_rejected(self):
        ex = {**BS_EXAMPLE, "input": {"target": "x"}}
        self.assertTrue(any("not a number" in e for e in validate_example(ex)))


class TestBinarySearchGolden(unittest.TestCase):
    def setUp(self):
        self.trace, self.frames = _frames(BS_EXAMPLE)

    def test_registered(self):
        self.assertTrue(is_registered("binary_search"))

    def test_one_card_per_probe_plus_setup(self):
        # setup + probe(mid=3, <) + probe(mid=5, >) + probe(mid=4, found) = 4 cards.
        self.assertEqual(len(self.trace["steps"]), 4)
        self.assertEqual(self.trace["steps"][0]["kind"], "initialize")
        self.assertNotIn("mark_mid", self.trace["steps"][0]["delta"])  # setup has no midpoint
        self.assertEqual(self.trace["steps"][1]["delta"]["mark_mid"], 3)
        self.assertEqual(self.trace["steps"][1]["decision"]["evaluated_to"], "less_than")
        self.assertEqual(self.trace["steps"][2]["decision"]["evaluated_to"], "greater_than")
        self.assertEqual(self.trace["steps"][3]["decision"]["evaluated_to"], "equal")
        self.assertEqual(self.trace["steps"][3]["delta"]["mark_found"], 4)

    def test_folded_range_narrows_each_probe(self):
        # Each probe carries the current [low, high] range; it narrows as we go.
        self.assertEqual((self.frames[1]["state_after"]["low"], self.frames[1]["state_after"]["high"]), (0, 6))
        self.assertEqual((self.frames[2]["state_after"]["low"], self.frames[2]["state_after"]["high"]), (4, 6))
        self.assertEqual((self.frames[3]["state_after"]["low"], self.frames[3]["state_after"]["high"]), (4, 4))

    def test_final_found(self):
        final = self.frames[-1]["state_after"]
        self.assertEqual(final["found"], 4)
        self.assertEqual(final["mid"], 4)
        self.assertEqual(BS_EXAMPLE["base_structure"]["array"][final["found"]], 18)

    def test_diff_metadata(self):
        self.assertEqual(self.frames[1]["diff"]["mid"], 3)
        self.assertEqual(self.frames[-1]["diff"]["found"], 4)

    def test_target_absent_terminates_not_found(self):
        ex = {**BS_EXAMPLE, "input": {"target": 100}}
        trace, frames = _frames(ex)
        self.assertIsNone(frames[-1]["state_after"]["found"])
        self.assertTrue(len(frames) >= 1)


if __name__ == "__main__":
    unittest.main()
