"""Grid (DP) projector + multi-array pointer alignment (F3, F4).

A DP table coding topic gets a grid_matrix diagram from its trace; the multi-array
view places each pointer on the sub-array it actually indexes (via light AST), not on
every array it happens to fit. Asserted by behavior, not topic.

Run: python -m unittest app.tests.test_grid_and_alignment
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.code_diagram import (
    _pointer_array_map,
    build_diagram_from_trace,
    build_grid_diagram_from_trace,
    derive_grid_from_trace,
)
from app.services.visual_v2.simulators.code_tracer import trace_execution

UNIQUE_PATHS = '''def unique_paths(m, n):
    dp = [[0] * n for _ in range(m)]
    for i in range(m):
        dp[i][0] = 1
    for j in range(n):
        dp[0][j] = 1
    for i in range(1, m):
        for j in range(1, n):
            dp[i][j] = dp[i-1][j] + dp[i][j-1]
    return dp[m-1][n-1]'''

MERGE_SORT = '''def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return merge(left, right)

def merge(left, right):
    result = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i]); i = i + 1
        else:
            result.append(right[j]); j = j + 1
    while i < len(left):
        result.append(left[i]); i = i + 1
    while j < len(right):
        result.append(right[j]); j = j + 1
    return result'''


class TestGrid(unittest.TestCase):
    def test_unique_paths_builds_grid(self):
        steps, ret = trace_execution(UNIQUE_PATHS, "unique_paths", {"args": [3, 4]})
        self.assertEqual(derive_grid_from_trace(steps), ("dp", 3, 4))
        d = build_diagram_from_trace(steps, model_id="dp")
        self.assertIsNotNone(d)
        self.assertEqual(d["model"]["base_type"], "grid_matrix_diagram")
        final = d["model"]["frames"][-1]["state"]
        self.assertEqual(final["active_cell"], [2, 3])         # terminal cell
        self.assertTrue(final["cell_values"])                  # cells filled
        self.assertEqual(ret, 10)

    def test_non_grid_code_has_no_grid(self):
        code = "def f(arr):\n    t = 0\n    for x in arr:\n        t = t + x\n    return t"
        steps, _ = trace_execution(code, "f", {"args": [[1, 2, 3]]})
        self.assertIsNone(derive_grid_from_trace(steps))


class TestPointerAlignment(unittest.TestCase):
    def test_pointer_array_map(self):
        m = _pointer_array_map(MERGE_SORT)
        self.assertEqual(m.get("i"), "left")
        self.assertEqual(m.get("j"), "right")

    def test_cursors_land_on_their_own_array(self):
        steps, _ = trace_execution(MERGE_SORT, "merge_sort", {"args": [[5, 2, 8, 1]]})
        d = build_diagram_from_trace(steps, model_id="ms", code=MERGE_SORT)
        self.assertEqual(d["model"]["mode"], "multi_sequence")
        misplaced = 0
        for frame in d["model"]["frames"]:
            for seq in frame["state"]["sequences"]:
                for cur in seq["pointers"]:
                    if cur["id"] == "i" and seq["label"] != "left":
                        misplaced += 1
                    if cur["id"] == "j" and seq["label"] != "right":
                        misplaced += 1
        self.assertEqual(misplaced, 0)  # i only on left, j only on right


if __name__ == "__main__":
    unittest.main()
