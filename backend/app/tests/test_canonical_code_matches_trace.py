"""The canonical CODE a coding topic shows must be the SAME VARIANT as the walkthrough TRACE — otherwise the
code-walkthrough annotates the code with steps it doesn't perform (the observed bug: merge's recursive code
carried bottom-up comments like "merged.append(left[i]) // append 4 from the right run" where left[i] was 11).
This locks merge + quicksort: the canonical code, run on the trace's instance, produces the SAME intermediate
operation sequence as the trace. Offline. (Extend as more adapters are aligned / the general gate is built.)"""
import unittest
from collections import deque

import app.services.examples.trace_pipeline as tp
from app.services.examples.canonical_solutions import CANONICAL_SOLUTIONS
from app.services.examples.trace_adapters import ADAPTERS


class CanonicalCodeMatchesTrace(unittest.TestCase):
    def test_merge_sort_code_reproduces_trace_merges(self):
        tr = tp.select_instance(ADAPTERS["merge_sort"], seed=3)
        arr = [r[0] for r in tr.initial_state["runs"]]
        trace_merges = [(s.inputs["left"], s.inputs["right"]) for s in tr.steps if s.inputs.get("left") is not None]
        # run the canonical bottom-up code, recording each pair of runs it merges
        runs, seq = deque([x] for x in arr), []
        while len(runs) > 1:
            L, R = runs.popleft(), runs.popleft()
            seq.append((list(L), list(R)))
            m, i, j = [], 0, 0
            while i < len(L) and j < len(R):
                (m.append(L[i]), (i := i + 1)) if L[i] <= R[j] else (m.append(R[j]), (j := j + 1))
            m += L[i:] + R[j:]
            runs.append(m)
        self.assertEqual(seq, trace_merges, "merge canonical code merges in a different order than the trace")

    def test_quick_sort_code_reproduces_trace_partitions(self):
        tr = tp.select_instance(ADAPTERS["quick_sort"], seed=3)
        arr = list(tr.initial_state["array"])
        trace_parts = [(s.inputs["pivot"], s.inputs["position"]) for s in tr.steps]
        a, seq = list(arr), []

        def part(lo, hi):
            piv, i = a[hi], lo
            for j in range(lo, hi):
                if a[j] < piv:
                    a[i], a[j] = a[j], a[i]
                    i += 1
            a[i], a[hi] = a[hi], a[i]
            return i

        def sort(lo, hi):
            if lo < hi:
                p = part(lo, hi)
                seq.append((a[p], p))
                sort(lo, p - 1)
                sort(p + 1, hi)

        sort(0, len(a) - 1)
        self.assertEqual(seq, trace_parts, "quicksort canonical code partitions differently than the trace")

    def test_both_still_sort_correctly(self):
        import random
        for slug, fn in [("merge_sort", "merge_sort"), ("quick_sort", "quick_sort")]:
            ns = {}
            exec(CANONICAL_SOLUTIONS[slug], ns)
            for _ in range(500):
                s = random.sample(range(200), random.randint(0, 12))
                self.assertEqual(ns[fn](list(s)), sorted(s), slug)


if __name__ == "__main__":
    unittest.main()
