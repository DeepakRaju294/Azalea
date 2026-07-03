"""Executed-reference gate (WORKED_EXAMPLE_ACCURACY_SPEC) — the code shown beside a coding walkthrough must
be the SAME variant as the verified trace. The gate RUNS the canonical code on the trace's own instance and
requires it to reproduce the trace (same final answer + every step's state occurs in the code's real
execution). Catches variant drift the value/state checks miss (a lookalike still computes the right answer).
Fully offline."""
import unittest

from app.services.examples import trace_pipeline as tp
from app.services.examples.canonical_solutions import CANONICAL_SOLUTIONS
from app.services.examples.code_execution_check import (code_reproduces_trace, reproduces_trace_applies)
from app.services.examples.trace_adapters import ADAPTERS

_ARRAY_SORTS = ["bubble_sort", "selection_sort", "insertion_sort", "merge_sort", "quick_sort", "heap_sort"]


class CanonicalCodeReproducesItsTrace(unittest.TestCase):
    def test_every_canonical_sort_reproduces_its_trace(self):
        for slug in _ARRAY_SORTS:
            code = CANONICAL_SOLUTIONS.get(slug)
            self.assertIsNotNone(code, slug)
            a = ADAPTERS[slug]
            for seed in range(20):
                tr = tp.select_instance(a, seed=seed)
                with self.subTest(slug=slug, seed=seed):
                    self.assertTrue(reproduces_trace_applies(tr, code), f"{slug}: gate should apply")
                    self.assertEqual(code_reproduces_trace(code, tr), [],
                                     f"{slug}: canonical code drifted from its own trace")


class DriftIsCaught(unittest.TestCase):
    def test_topdown_merge_code_beside_bottom_up_trace_is_flagged(self):
        # the exact bug the gate exists for: a correct-but-DIFFERENT merge variant. It still sorts, so a
        # final-answer/property check passes — but its per-line annotations would contradict the code.
        topdown = ("def merge_sort(arr):\n"
                   "    if len(arr) <= 1:\n        return arr\n"
                   "    mid = len(arr) // 2\n"
                   "    left = merge_sort(arr[:mid]); right = merge_sort(arr[mid:])\n"
                   "    out = []; i = j = 0\n"
                   "    while i < len(left) and j < len(right):\n"
                   "        if left[i] <= right[j]: out.append(left[i]); i += 1\n"
                   "        else: out.append(right[j]); j += 1\n"
                   "    out.extend(left[i:]); out.extend(right[j:]); return out\n")
        tr = tp.select_instance(ADAPTERS["merge_sort"], seed=3)
        drift = code_reproduces_trace(topdown, tr)
        self.assertTrue(drift, "top-down merge code beside a bottom-up trace must be flagged as drift")

    def test_wrong_algorithm_code_is_flagged(self):
        # quicksort trace beside merge-sort code: same final answer, totally different intermediate states.
        tr = tp.select_instance(ADAPTERS["quick_sort"], seed=5)
        drift = code_reproduces_trace(CANONICAL_SOLUTIONS["merge_sort"], tr)
        self.assertTrue(drift)

    def test_non_array_shape_skips_gracefully(self):
        # a graph adapter has no array instance — the gate must SKIP (never a false withhold).
        tr = tp.select_instance(ADAPTERS["kruskal"], seed=1)
        self.assertFalse(reproduces_trace_applies(tr, CANONICAL_SOLUTIONS["kruskal"]))
        self.assertEqual(code_reproduces_trace(CANONICAL_SOLUTIONS["kruskal"], tr), [])


class WiredIntoPipeline(unittest.TestCase):
    def test_coding_topic_withholds_on_drifted_code(self):
        # end-to-end: a coding topic whose canonical code drifts from the trace withholds (returns None)
        # rather than shipping a self-contradicting code + walkthrough pair.
        from unittest import mock
        topdown = ("def merge_sort(arr):\n    if len(arr) <= 1:\n        return arr\n"
                   "    mid = len(arr)//2\n    left = merge_sort(arr[:mid]); right = merge_sort(arr[mid:])\n"
                   "    out=[]; i=j=0\n    while i<len(left) and j<len(right):\n"
                   "        if left[i]<=right[j]: out.append(left[i]); i+=1\n"
                   "        else: out.append(right[j]); j+=1\n"
                   "    out.extend(left[i:]); out.extend(right[j:]); return out\n")
        topic = {"id": "t", "title": "Implementing Merge Sort", "topic_type": "coding_implementation"}

        def boom(*a, **k):
            raise AssertionError("must withhold before formatting a drifted coding topic")

        res = tp.solve_trace_pipeline(topic, format_fn=boom, code=topdown, seed=3)
        self.assertIsNone(res, "drifted coding code must withhold, not ship")


if __name__ == "__main__":
    unittest.main()
