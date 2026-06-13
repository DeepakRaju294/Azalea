"""Milestone cap + composite multi-array diagram (merge sort).

A: cap_milestones keeps a worked example readable (no 60-card explosion), unchanged for
small ones. B: build_multi_sequence_diagram_from_trace renders multiple sub-arrays
(left/right/result) for divide-and-conquer code. Asserted by behavior, not topic.

Run: python -m unittest app.tests.test_multi_sequence_and_cap
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.code_diagram import build_diagram_from_trace, build_multi_sequence_diagram_from_trace
from app.services.visual_v2.code_lesson_integration import cap_milestones
from app.services.visual_v2.simulators.code_tracer import trace_execution

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


class TestCap(unittest.TestCase):
    def test_caps_large_keeps_endpoints(self):
        capped = cap_milestones(list(range(60)), cap=12)
        self.assertLessEqual(len(capped), 12)
        self.assertEqual(capped[0], 0)
        self.assertEqual(capped[-1], 59)

    def test_small_unchanged(self):
        self.assertEqual(cap_milestones([0, 1, 2, 3]), [0, 1, 2, 3])


class TestMultiSequence(unittest.TestCase):
    def test_merge_sort_yields_composite_arrays(self):
        steps, _ = trace_execution(MERGE_SORT, "merge_sort", {"args": [[5, 2, 8, 1, 9, 3]]})
        d = build_diagram_from_trace(steps, model_id="ms")
        self.assertIsNotNone(d)
        self.assertEqual(d["model"]["mode"], "multi_sequence")
        # every frame carries 2+ labelled sub-arrays (the divide & conquer state)
        for f in d["model"]["frames"]:
            seqs = f["state"]["sequences"]
            self.assertGreaterEqual(len(seqs), 2)
            for s in seqs:
                self.assertIn("label", s)
                self.assertTrue(s["values"])
        labels = {s["label"] for f in d["model"]["frames"] for s in f["state"]["sequences"]}
        self.assertTrue({"left", "right", "result"} & labels)  # the merge collections appear

    def test_frame_count_capped(self):
        steps, _ = trace_execution(MERGE_SORT, "merge_sort", {"args": [list(range(12, 0, -1))]})
        d = build_multi_sequence_diagram_from_trace(steps, model_id="ms", max_frames=16)
        self.assertIsNotNone(d)
        self.assertLessEqual(d["frame_count"], 16)

    def test_single_collection_is_not_multi(self):
        # a plain loop has only one list → multi-sequence declines (None)
        code = "def f(arr):\n    t = 0\n    for x in arr:\n        t = t + x\n    return t"
        steps, _ = trace_execution(code, "f", {"args": [[1, 2, 3, 4]]})
        self.assertIsNone(build_multi_sequence_diagram_from_trace(steps, model_id="x"))


if __name__ == "__main__":
    unittest.main()
