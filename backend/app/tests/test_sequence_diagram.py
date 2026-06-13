"""Sequence (indexed_sequence) diagram from a code trace — the array family
(PROJECTOR_SYSTEM_SPEC §13 SequenceProjection). One builder covers two-pointer,
sliding-window, and linear scan; non-index ints (sums/counts) and mutating arrays
degrade to code-only. Asserted by behavior, not topic.

Run: python -m unittest app.tests.test_sequence_diagram
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.code_diagram import (
    build_diagram_from_trace,
    build_sequence_diagram_from_trace,
    derive_array_from_trace,
    infer_sequence_projection,
)
from app.services.visual_v2.simulators.code_tracer import trace_execution

TWO_POINTER = '''def two_sum(arr, target):
    left = 0
    right = len(arr) - 1
    while left < right:
        s = arr[left] + arr[right]
        if s == target:
            return [left, right]
        elif s < target:
            left = left + 1
        else:
            right = right - 1
    return [-1, -1]'''

LINEAR = '''def find(arr, target):
    i = 0
    while i < len(arr):
        if arr[i] == target:
            return i
        i = i + 1
    return -1'''

SUM = '''def total(arr):
    s = 0
    for x in arr:
        s = s + x
    return s'''

SORT = '''def bubble(arr):
    n = len(arr)
    for i in range(n):
        for j in range(n - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr'''


def _cursors(model):
    return [{p["id"]: p["position"] for p in f["state"]["pointers"]} for f in model["frames"]]


class TestSequenceFamily(unittest.TestCase):
    def test_two_pointer_diagram(self):
        steps, _ = trace_execution(TWO_POINTER, "two_sum", {"args": [[1, 3, 5, 7, 9, 11], 13]})
        d = build_diagram_from_trace(steps, model_id="tp")
        self.assertIsNotNone(d)
        self.assertEqual(d["model"]["base_type"], "indexed_sequence_diagram")
        ids = {k for fr in _cursors(d["model"]) for k in fr}
        self.assertEqual(ids, {"left", "right"})
        self.assertGreaterEqual(d["frame_count"], 4)

    def test_linear_scan_diagram(self):
        steps, _ = trace_execution(LINEAR, "find", {"args": [[5, 3, 8, 1, 9, 2], 9]})
        d = build_diagram_from_trace(steps, model_id="ls")
        self.assertIsNotNone(d)
        ids = {k for fr in _cursors(d["model"]) for k in fr}
        self.assertEqual(ids, {"i"})


class TestSequenceDegrade(unittest.TestCase):
    def test_sum_accumulator_is_not_a_pointer(self):
        # `s` lands in [0, n) coincidentally but isn't an index name → no diagram.
        steps, _ = trace_execution(SUM, "total", {"args": [[1, 2, 3, 4]]})
        da = derive_array_from_trace(steps)
        self.assertIsNotNone(da)
        self.assertIsNone(infer_sequence_projection(steps, da[0], da[1]))
        self.assertIsNone(build_sequence_diagram_from_trace(steps, model_id="x"))

    def test_mutating_array_is_skipped(self):
        # Bubble sort rewrites the array in place → fixed-base compiler can't show it.
        steps, _ = trace_execution(SORT, "bubble", {"args": [[3, 1, 2]]})
        self.assertIsNone(derive_array_from_trace(steps))


if __name__ == "__main__":
    unittest.main()
