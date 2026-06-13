"""Visual System V2 — IndexedSequenceCompiler (Phase 3.1). §11.2 binary search.

Run: python -m unittest app.tests.test_visual_v2_indexed_sequence
"""
from __future__ import annotations

import unittest

from app.services.visual_v2.compilers.indexed_sequence import compile_from_trace
from app.services.visual_v2.delta_fold import DeltaFoldEngine
from app.services.visual_v2.profiles import delta_vocabulary, profile_for_mode
from app.services.visual_v2.simulators.registry import get_simulator

BS_EXAMPLE = {
    "example_id": "bs", "base_type": "indexed_sequence_diagram", "mode": "binary_search_range",
    "algorithm": "binary_search", "input": {"target": 18},
    "base_structure": {"array": [3, 7, 9, 12, 18, 21, 30]},
}


class TestIndexedSequenceCompiler(unittest.TestCase):
    def setUp(self):
        self.array = BS_EXAMPLE["base_structure"]["array"]
        trace = get_simulator("binary_search")(BS_EXAMPLE)
        frames = DeltaFoldEngine().fold(
            trace["initial_state"], trace["steps"], set(range(len(self.array))),
            delta_vocabulary("binary_search_range"),
        )
        self.model, self.render_steps = compile_from_trace(
            trace=trace, frames=frames, array=self.array,
            profile=profile_for_mode("binary_search_range"), mode="binary_search_range", model_id="m1",
        )

    def _state(self, frame_index):
        return self.model["frames"][frame_index]["state"]

    def test_base_matches_frontend_contract(self):
        self.assertEqual(self.model["base"]["values"], [str(v) for v in self.array])
        self.assertEqual(self.model["base"]["indices"], list(range(len(self.array))))

    def test_frame_wrapper_present(self):
        frame = self.model["frames"][0]
        for key in ("index", "state", "selectable_elements", "transitions"):
            self.assertIn(key, frame)

    def test_setup_then_first_compare(self):
        # Step 0 = setup (full range, no mid); step 1 = first probe, mid index 3.
        self.assertEqual(self._state(0)["highlighted_cells"], [])
        self.assertEqual(self._state(1)["highlighted_cells"], [3])

    def test_range_narrows_after_first_probe(self):
        # Second probe's range starts at 4 (left half eliminated).
        ranges = self._state(2)["ranges"]
        self.assertEqual(ranges[0]["start"], 4)
        self.assertEqual(ranges[0]["end"], 6)

    def test_final_highlights_found(self):
        final = self._state(len(self.model["frames"]) - 1)
        self.assertEqual(final["highlighted_cells"], [4])  # value 18 at index 4

    def test_pointers_are_objects(self):
        pointers = self._state(1)["pointers"]
        self.assertTrue(any(p["id"] == "low" and "position" in p for p in pointers))


if __name__ == "__main__":
    unittest.main()
