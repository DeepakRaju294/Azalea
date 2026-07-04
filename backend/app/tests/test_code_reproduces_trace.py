"""Executed-reference gate (WORKED_EXAMPLE_ACCURACY_SPEC) — the code shown beside a coding walkthrough must
be the SAME variant as the verified trace. The gate RUNS the canonical code on the trace's own instance and
requires it to reproduce the trace (same final answer + every step's state occurs in the code's real
execution). Catches variant drift the value/state checks miss (a lookalike still computes the right answer).
Fully offline."""
import unittest

from app.services.examples import trace_pipeline as tp
from app.services.examples.canonical_solutions import CANONICAL_SOLUTIONS
from app.services.examples.code_execution_check import (code_reproduces_trace, executed_reference_violations,
                                                        reproduces_trace_applies)
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

    def test_importless_displayed_code_verifies_via_canonical_fallback(self):
        # the DISPLAYED code strips imports (design choice) -> merge's `deque` is undefined and the displayed
        # form cannot run. Rather than skip (which would blind the check for merge/heap), the gate falls back
        # to the CANONICAL source (imports intact) for the same adapter and still verifies. It must never
        # WITHHOLD over the stripped import (regression), but it must still catch a real merge bug.
        tr = tp.select_instance(ADAPTERS["merge_sort"], seed=0)
        importless = "\n".join(l for l in CANONICAL_SOLUTIONS["merge_sort"].splitlines() if "import" not in l)
        self.assertIn("deque", importless)
        self.assertNotIn("import", importless)
        self.assertEqual(code_reproduces_trace(importless, tr), [])   # verified via canonical, not a withhold

    def test_merge_append_misattribution_caught_despite_stripped_import(self):
        # #375: `merged.append(left[i]) // append 20` where left[i] is 26 — the per-line check must catch it
        # even though the DISPLAYED merge code (stripped `deque`) can't run, via the canonical fallback.
        a = ADAPTERS["merge_sort"]
        tr = a.reference({"array": [26, 20, 49, 16, 35]})             # first merge: left=[26], right=[20]
        importless = "\n".join(l for l in CANONICAL_SOLUTIONS["merge_sort"].splitlines() if "import" not in l)
        cards = [{"work": ["x"], "code_lines": [[1]]} for _ in tr.steps]
        cards[1] = {"work": ["merged.append(left[i])  // append 20 to the merged run"], "code_lines": [[1]]}
        v = executed_reference_violations(cards, importless, tr)
        self.assertTrue(any(c == "code_comment_value_mismatch" for c, _ in v))


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

    def test_value_mismatch_comment_retries_then_falls_back(self):
        # a coding formatter that attributes a wrong value to left[i] must NOT ship that card: the pipeline
        # retries, then ships the correct trace-preserving narration (never the contradicted comment).
        from app.services.examples import generation_report as gr
        calls = {"n": 0}

        def bad(payload):
            calls["n"] += 1
            import json
            steps = json.loads(payload["user"].split("STEPS (verified, describe faithfully):", 1)[1])
            cards = []
            for i, s in enumerate(steps):
                work = (["runs = deque([x] for x in arr)  // init runs"] if i == 0
                        else ["merged.append(left[i])  // append value 999"])   # 999 never a real left[i]
                cards.append({"title": "c", "goal": "", "reasoning": "", "work": work,
                              "result": s["expected_visible_result"], "code_lines": [[3 if i == 0 else 12]]})
            return {"cards": cards}

        topic = {"id": "t", "title": "Implementing Merge Sort", "topic_type": "coding_implementation"}
        gr.start(topic)
        res = tp.solve_trace_pipeline(topic, format_fn=bad, code=CANONICAL_SOLUTIONS["merge_sort"], seed=0)
        self.assertGreater(calls["n"], 1, "must retry on a value-mismatch comment, not ship it")
        self.assertIsNotNone(res)                                    # ships the trace-preserving narration
        self.assertNotIn("999", " ".join(w for c in res["cards"] for w in c["work"]))
        gr.finish_and_persist()


class PerLineValueAttribution(unittest.TestCase):
    """The finer executed-reference check: a card's // comment must not attribute a value an indexed
    expression never held at that step (the merge `append(left[i]) // value 9` bug where left[i] is 30)."""
    def _merge_cards(self, tr, comment):
        # one card per step; card for the first real merge references left[i] with the given comment
        cards = [{"work": ["x"], "code_lines": [[1]]} for _ in tr.steps]
        cards[1] = {"work": [f"merged.append(left[i])  // {comment}"], "code_lines": [[1]]}
        return cards

    def test_wrong_value_is_flagged(self):
        tr = tp.select_instance(ADAPTERS["merge_sort"], seed=0)     # first merge: left=[49]
        code = CANONICAL_SOLUTIONS["merge_sort"]
        v = executed_reference_violations(self._merge_cards(tr, "append value 999 to merged"), code, tr)
        self.assertTrue(any(c == "code_comment_value_mismatch" for c, _ in v))

    def test_misattributed_value_is_flagged(self):
        # 57 is the OTHER run's value; attributing it to left[i] (which is 49) is the real bug class
        tr = tp.select_instance(ADAPTERS["merge_sort"], seed=0)
        code = CANONICAL_SOLUTIONS["merge_sort"]
        v = executed_reference_violations(self._merge_cards(tr, "append 57 from left"), code, tr)
        self.assertTrue(any(c == "code_comment_value_mismatch" for c, _ in v))

    def test_correct_value_is_not_flagged(self):
        tr = tp.select_instance(ADAPTERS["merge_sort"], seed=0)
        code = CANONICAL_SOLUTIONS["merge_sort"]
        self.assertEqual(executed_reference_violations(self._merge_cards(tr, "append 49 from the left run"),
                                                       code, tr), [])

    def test_comparison_comment_two_values_is_not_flagged(self):
        # a legitimate comparison aside ("6 < 31 so take left") introduces TWO values -> never flagged
        tr = tp.select_instance(ADAPTERS["merge_sort"], seed=0)
        code = CANONICAL_SOLUTIONS["merge_sort"]
        cards = [{"work": ["x"], "code_lines": [[1]]} for _ in tr.steps]
        cards[1] = {"work": ["if left[i] <= right[j]:  // compare 49 and 57"], "code_lines": [[1]]}
        self.assertEqual(executed_reference_violations(cards, code, tr), [])

    def test_out_of_scope_returns_empty(self):
        tr = tp.select_instance(ADAPTERS["kruskal"], seed=1)        # non-array shape
        self.assertEqual(executed_reference_violations([{"work": ["x[i]  // 5"]}],
                                                       CANONICAL_SOLUTIONS["kruskal"], tr), [])


if __name__ == "__main__":
    unittest.main()
