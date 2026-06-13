"""Visual System V2 — dp_table mode (grid_matrix). unique-paths DP golden.

Run: python -m unittest app.tests.test_visual_v2_grid_matrix
"""
from __future__ import annotations

import unittest

from app.services.visual_v2.compilers.grid_matrix import compile_from_trace
from app.services.visual_v2.delta_fold import DeltaFoldEngine
from app.services.visual_v2.profiles import delta_vocabulary, profile_for_mode
from app.services.visual_v2.simulators.registry import get_simulator

EXAMPLE = {
    "example_id": "up", "base_type": "grid_matrix_diagram", "mode": "dp_table",
    "algorithm": "unique_paths", "base_structure": {"rows": 3, "cols": 3},
}


class TestUniquePathsDP(unittest.TestCase):
    def setUp(self):
        self.trace = get_simulator("unique_paths")(EXAMPLE)
        self.frames = DeltaFoldEngine().fold(
            self.trace["initial_state"], self.trace["steps"], set(), delta_vocabulary("dp_table")
        )
        self.model, _ = compile_from_trace(
            trace=self.trace, frames=self.frames, rows=3, cols=3,
            profile=profile_for_mode("dp_table"), mode="dp_table", model_id="m1",
        )

    def test_step_count_is_cells(self):
        self.assertEqual(len(self.trace["steps"]), 9)  # 3x3

    def test_final_cell_value_is_unique_paths(self):
        # 3x3 grid → 6 unique paths to bottom-right.
        final = self.frames[-1]["state_after"]["cell_values"]
        self.assertEqual(final["2,2"], "6")
        self.assertEqual(final["0,0"], "1")

    def test_interior_cell_has_two_dependency_arrows(self):
        # The cell (1,1) sums (0,1)+(1,0).
        idx = next(i for i, f in enumerate(self.frames) if f["state_after"]["active_cell"] == [1, 1])
        arrows = self.frames[idx]["state_after"]["dependency_arrows"]
        self.assertEqual(len(arrows), 2)

    def test_model_matches_frontend_contract(self):
        self.assertEqual(self.model["base_type"], "grid_matrix_diagram")
        self.assertEqual(len(self.model["base"]["cells"]), 3)
        frame = self.model["frames"][-1]["state"]
        for key in ("active_cell", "completed_cells", "cell_values", "dependency_arrows"):
            self.assertIn(key, frame)
        self.assertEqual(frame["cell_values"]["2,2"], "6")


if __name__ == "__main__":
    unittest.main()
