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
        # Force the LLM path — merge coding now ships deterministic (CP10), which would bypass the formatter.
        from unittest import mock
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
        # force the LLM coding path — merge is on the deterministic-coding whitelist (would bypass the formatter)
        with mock.patch("app.services.examples.trace_adapters.DETERMINISTIC_CODING_SLUGS", frozenset()):
            res = tp.solve_trace_pipeline(topic, format_fn=bad, code=CANONICAL_SOLUTIONS["merge_sort"], seed=0)
        self.assertGreater(calls["n"], 1, "must retry on a value-mismatch comment, not ship it")
        self.assertIsNotNone(res)                                    # ships the trace-preserving narration
        self.assertNotIn("999", " ".join(w for c in res["cards"] for w in c["work"]))
        gr.finish_and_persist()


class RobustRegionMapping(unittest.TestCase):
    """CP10 foundation (ACCURACY_SPEC §18.4): segment the execution into one slice per trace step ROBUSTLY.
    The state-first-match heuristic collapsed on a NO-OP step (an insertion element that stays put shares the
    previous array); the anchor-line mapper gives every step its full slice. This unblocks deterministic
    coding generation."""
    _SORTS = ["insertion_sort", "selection_sort", "quick_sort", "bubble_sort", "merge_sort"]

    def _exec(self, slug, tr):
        from app.services.examples.canonical_solutions import canonical_python
        from app.services.visual_v2.simulators.code_tracer import trace_execution
        init = tr.initial_state
        arr = init.get("array") or [x for r in init["runs"] for x in r]
        code = canonical_python(slug)
        entry = [l for l in code.splitlines() if l.startswith("def ")][-1].split("def ")[1].split("(")[0]
        return trace_execution(code, entry, {"array": list(arr)})[0]

    def test_every_core_sort_maps_one_slice_per_step_with_no_degenerate_region(self):
        from app.services.examples.code_execution_check import map_step_regions
        for slug in self._SORTS:
            a = ADAPTERS[slug]
            for seed in range(25):
                tr = tp.select_instance(a, seed=seed)
                regions = map_step_regions(self._exec(slug, tr), tr)
                with self.subTest(slug=slug, seed=seed):
                    self.assertIsNotNone(regions, f"{slug}: no robust mapping")
                    self.assertEqual(len(regions), len(tr.steps))
                    # non-init operation slices must span real work, not collapse to a single event
                    self.assertTrue(all(e - s + 1 >= 2 for s, e in regions[1:]), f"{slug}: degenerate region")

    def test_insertion_no_op_step_is_no_longer_a_single_event(self):
        # the exact regression: an insertion step whose element stays put must still get its full slice
        from app.services.examples.code_execution_check import map_step_regions
        a = ADAPTERS["insertion_sort"]
        tr = a.reference({"array": [10, 20, 5, 30, 25]})     # 20 and 30 stay put -> no-op steps
        regions = map_step_regions(self._exec("insertion_sort", tr), tr)
        self.assertIsNotNone(regions)
        noop = [k for k, s in enumerate(tr.steps)
                if k > 0 and s.prior_state["array"] == s.state_after["array"]]
        self.assertTrue(noop, "instance should have a no-op insertion step")
        for k in noop:
            a2, b2 = regions[k]
            self.assertGreaterEqual(b2 - a2 + 1, 2, "a no-op step must still map to its full slice")


class CoreDecisionShown(unittest.TestCase):
    """A coding walkthrough must step through the loop that drives the algorithm (selection's min-scan,
    quicksort's partition compare) — not jump from init to the outcome. A quality nudge (retry, never blocks)."""
    def test_selection_omitting_the_min_scan_is_detected(self):
        from app.services.examples.code_execution_check import coding_omits_core_decision
        code = CANONICAL_SOLUTIONS["selection_sort"]
        skipped = [{"work": ["min_idx = i  // init", "arr[i], arr[min_idx] = arr[min_idx], arr[i]  // swap"]}]
        self.assertTrue(coding_omits_core_decision(skipped, code))
        shown = [{"work": ["for j in range(i+1, len(arr)):  // scan",
                           "if arr[j] < arr[min_idx]:  // found a smaller value"]}]
        self.assertFalse(coding_omits_core_decision(shown, code))

    def test_bare_control_flow_if_is_not_the_decision(self):
        # quicksort's `if lo < hi:` (no index) is control flow, not the decision — showing only it still omits
        from app.services.examples.code_execution_check import coding_omits_core_decision
        code = CANONICAL_SOLUTIONS["quick_sort"]
        only_control = [{"work": ["if lo < hi:  // recurse while the slice has 2+ elements"]}]
        self.assertTrue(coding_omits_core_decision(only_control, code))
        with_compare = [{"work": ["if arr[j] < pivot:  // arr[j] is below the pivot"]}]
        self.assertFalse(coding_omits_core_decision(with_compare, code))

    def test_no_decision_line_in_code_never_flags(self):
        from app.services.examples.code_execution_check import coding_omits_core_decision
        self.assertFalse(coding_omits_core_decision([{"work": ["x = 1  // set"]}], "def f(a):\n    return a\n"))


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


class DeterministicCodingGeneration(unittest.TestCase):
    """CP10 (ACCURACY_SPEC §18.4): a coding topic of a core-sort adapter is authored from the EXECUTED
    REFERENCE, not the LLM — the decision loop is always shown and every value is correct by construction."""
    _SORTS = ["insertion_sort", "selection_sort", "quick_sort", "bubble_sort", "merge_sort"]

    def test_generated_cards_pass_all_gates_every_seed(self):
        from app.services.examples.coding_narration import generate_coding_cards
        from app.services.examples.code_execution_check import (coding_omits_core_decision,
                                                                executed_reference_violations)
        from app.services.examples.trace_contract import (validate_prose, hard_prose_violations,
                                                          validate_fidelity)
        for slug in self._SORTS:
            a, code = ADAPTERS[slug], CANONICAL_SOLUTIONS[slug]
            for seed in range(20):
                tr = tp.select_instance(a, seed=seed)
                cards = generate_coding_cards(tr, code, tp._deterministic_narration(tr, a))
                with self.subTest(slug=slug, seed=seed):
                    self.assertIsNotNone(cards)
                    self.assertFalse(coding_omits_core_decision(cards, code))     # decision loop shown
                    self.assertEqual(executed_reference_violations(cards, code, tr), [])  # values correct
                    self.assertEqual(hard_prose_violations(validate_prose(cards, tr, a, code_anchored=True)), [])
                    self.assertTrue(validate_fidelity(cards, tr, a, validate_visual_state=False).ok)
                    for c in cards:
                        for w in c["work"]:
                            if w.startswith("…"):                                 # the repeat-collapse note
                                continue
                            self.assertIn("//", w)                                # every code line annotated
                            self.assertNotIn("carry out this step", w)            # no weak fallback

    def test_ships_deterministically_without_the_llm(self):
        from app.services.examples.canonical_solutions import display_solution
        def boom(*a, **k):
            raise AssertionError("the LLM must not be called — coding is deterministic (CP10)")
        for title, slug in [("Implementing Selection Sort", "selection_sort"),
                            ("Implementing Merge Sort", "merge_sort")]:      # merge = the import-stripped case
            topic = {"id": "t", "title": title, "topic_type": "coding_implementation"}
            res = tp.solve_trace_pipeline(topic, format_fn=boom, code=display_solution(slug), seed=3)
            with self.subTest(title=title):
                self.assertIsNotNone(res)
                # code_lines anchor into the DISPLAYED (import-stripped) code — valid indices, none dangling
                disp_len = len(display_solution(slug).splitlines())
                for c in res["cards"]:
                    for anchors in (c.get("code_lines") or []):
                        for ln in anchors:
                            self.assertTrue(1 <= ln <= disp_len, f"{title}: code_lines {ln} out of range")


class GraphFamilyDeterministicCoding(unittest.TestCase):
    """CP11a first new family: BFS coding is authored from the executed reference (instance recovered from the
    adapter's seeded candidate pool — the graph is NOT on the trace). Proves the deterministic path generalizes
    beyond arrays. Recursive/other graph shapes (DFS) that don't map cleanly fall back to the LLM."""
    def _cards(self, slug, seed):
        from app.services.examples.canonical_solutions import display_solution
        from app.services.examples.coding_narration import generate_coding_cards
        a = ADAPTERS[slug]
        tr = tp.select_instance(a, seed=seed)
        return a, tr, generate_coding_cards(tr, display_solution(slug), tp._deterministic_narration(tr, a))

    def test_topological_sort_coding_generates_cleanly_across_seeds(self):
        # CP11b — Kahn's algorithm (in-degree queue) is BFS-shaped, so it maps to the anchor-line model. Its
        # steps carry decision "emit X" (vs BFS/DFS "visit X"), which routes the annotations to the topo
        # vocabulary (in-degree / prerequisites / ready queue) instead of borrowing the BFS or merge-run wording.
        from app.services.examples.trace_contract import (validate_prose, hard_prose_violations,
                                                          validate_fidelity)
        from app.services.examples.code_execution_check import executed_reference_violations
        from app.services.examples.canonical_solutions import display_solution
        from app.services.examples.trace_adapters import DETERMINISTIC_CODING_SLUGS
        self.assertIn("topological_sort", DETERMINISTIC_CODING_SLUGS)
        code = display_solution("topological_sort")
        for seed in range(20):
            a, tr, cards = self._cards("topological_sort", seed)
            with self.subTest(seed=seed):
                self.assertIsNotNone(cards, "topo should generate deterministically")
                self.assertEqual(hard_prose_violations(validate_prose(cards, tr, a, code_anchored=True)), [])
                self.assertTrue(validate_fidelity(cards, tr, a, validate_visual_state=False).ok)
                self.assertEqual(executed_reference_violations(cards, code, tr), [])
                for c in cards:
                    for w in c["work"]:
                        self.assertNotIn("carry out this step", w)            # no weak fallback
                        self.assertNotIn("merged run", w)                     # no leaked SORT template
                        self.assertNotIn("front of the queue", w)             # no borrowed BFS wording

    def test_tree_levelorder_coding_generates_cleanly_across_seeds(self):
        # CP11b — level-order is BFS over a binary tree. Two fixes make it map: (1) the code-tracer builds the
        # tree from the adapter's adjacency dict + root (not by packing values into a complete tree), so the code
        # walks the SAME tree the trace did; (2) tree-node templates (visit / queue left|right child) name the
        # current node from the verified "visit N" step. Regression-guards the tree-build bug (wrong shape → the
        # code's order silently diverged from the trace).
        from app.services.examples.trace_contract import (validate_prose, hard_prose_violations,
                                                          validate_fidelity)
        from app.services.examples.code_execution_check import executed_reference_violations, _execute_on_instance
        from app.services.examples.canonical_solutions import display_solution
        from app.services.examples.trace_adapters import DETERMINISTIC_CODING_SLUGS
        self.assertIn("tree_levelorder", DETERMINISTIC_CODING_SLUGS)
        code = display_solution("tree_levelorder")
        for seed in range(20):
            a, tr, cards = self._cards("tree_levelorder", seed)
            with self.subTest(seed=seed):
                self.assertIsNotNone(cards, "tree_levelorder should generate deterministically")
                # the code must reproduce the trace's visit order (proves the tree was built from the adjacency)
                _, result, _ = _execute_on_instance(code, tr)
                self.assertEqual(result, (tr.final_answer or {}).get("visit_order"))
                self.assertEqual(hard_prose_violations(validate_prose(cards, tr, a, code_anchored=True)), [])
                self.assertTrue(validate_fidelity(cards, tr, a, validate_visual_state=False).ok)
                self.assertEqual(executed_reference_violations(cards, code, tr), [])
                for c in cards:
                    for w in c["work"]:
                        self.assertNotIn("carry out this step", w)
                        self.assertNotIn("neighbour", w)                      # tree wording, not graph adjacency

    def test_tree_build_from_adjacency_matches_the_trace_order(self):
        # Direct guard on the code-tracer fix: build_tree_from_adjacency must follow the explicit left/right
        # links, NOT pack the dict keys into a complete binary tree (which silently reordered the BFS).
        from app.services.visual_v2.simulators.code_tracer import build_tree_from_adjacency
        adj = {38: {"left": 35, "right": 39}, 35: {"left": 9, "right": None},
               9: {"left": None, "right": 24}, 24: {"left": None, "right": None},
               39: {"left": None, "right": None}}
        root = build_tree_from_adjacency(adj, 38)
        from collections import deque
        order, q = [], deque([root])
        while q:
            nd = q.popleft(); order.append(nd.val)
            if nd.left: q.append(nd.left)
            if nd.right: q.append(nd.right)
        self.assertEqual(order, [38, 35, 39, 9, 24])                          # true level order, not [38,35,9,24,39]

    def test_bfs_coding_generates_cleanly_across_seeds(self):
        from app.services.examples.trace_contract import (validate_prose, hard_prose_violations,
                                                          validate_fidelity)
        for seed in range(20):
            a, tr, cards = self._cards("bfs", seed)
            with self.subTest(seed=seed):
                self.assertIsNotNone(cards, "BFS should generate deterministically (instance recovered)")
                self.assertEqual(hard_prose_violations(validate_prose(cards, tr, a)), [])
                self.assertTrue(validate_fidelity(cards, tr, a, validate_visual_state=False).ok)
                for c in cards:
                    for w in c["work"]:
                        self.assertNotIn("carry out this step", w)         # no weak fallback
                        self.assertNotIn("sorted prefix", w)               # no leaked SORT template
                        self.assertNotIn("merged run", w)

    def test_bfs_names_the_visited_node_and_enqueued_neighbours(self):
        a, tr, cards = self._cards("bfs", 3)                               # A → B, E; …
        visit_a = next(c for c in cards if c["title"].startswith("Visit A"))
        work = " ".join(visit_a["work"])
        self.assertIn("take A from the front of the queue", work)          # the popped node from the verified step
        self.assertIn("visited", work)
        self.assertTrue("B, E" in work or "E, B" in work)                  # both neighbours aggregated

    def test_bfs_ships_deterministically_without_the_llm(self):
        from app.services.examples.canonical_solutions import display_solution
        def boom(*a, **k):
            raise AssertionError("BFS coding must not call the LLM")
        res = tp.solve_trace_pipeline({"id": "t", "title": "Implementing BFS",
                                       "topic_type": "coding_implementation"},
                                      format_fn=boom, code=display_solution("bfs"), seed=3)
        self.assertIsNotNone(res)

    def test_translated_language_coding_falls_back_to_llm(self):
        # Deterministic coding annotates the EXECUTED (Python) canonical and anchors each work line to the
        # DISPLAYED code by exact stripped-text match. When the display is a translation (java/cpp), nothing
        # matches → empty `code_lines` → an unrenderable card (this is why "Implementing BFS" hung on a Java
        # path). The path must DEFER to the LLM (which translates faithfully) for any non-Python display, while
        # Python still ships deterministically.
        from app.services.examples.canonical_solutions import display_solution
        from app.services.examples.coding_narration import generate_coding_cards
        for slug in ("bfs", "bubble_sort", "merge_sort"):
            a = ADAPTERS[slug]
            tr = tp.select_instance(a, seed=3)
            base = tp._deterministic_narration(tr, a)
            with self.subTest(slug=slug):
                py = generate_coding_cards(tr, display_solution(slug, "python"), base)
                self.assertIsNotNone(py, "Python display must still ship deterministically")
                self.assertTrue(any(cl for c in py for cl in c["code_lines"]))   # real anchors
                for lang in ("java", "cpp"):
                    self.assertIsNone(generate_coding_cards(tr, display_solution(slug, lang), base),
                                      f"{slug} {lang}: translated display must fall back to the LLM")

    def test_recursive_dfs_walkthrough_narrates_recursion_and_falls_back_for_coding(self):
        # DFS is presented RECURSIVELY (more intuitive than an explicit stack): the adapter's trace narrates
        # the depth-first descent + backtracking, and the canonical code is recursive. Recursive accumulation
        # (order += dfs(...)) does not map to one slice per step, so coding falls back to the LLM (not on the
        # deterministic whitelist) — and the code/walkthrough are both recursive, so they no longer conflict.
        from app.services.examples.canonical_solutions import display_solution, canonical_python
        from app.services.examples.coding_narration import generate_coding_cards
        from app.services.examples.trace_adapters import DETERMINISTIC_CODING_SLUGS
        self.assertNotIn("dfs_iter", DETERMINISTIC_CODING_SLUGS)
        self.assertIn("order += dfs", canonical_python("dfs_iter"))             # recursive code
        a = ADAPTERS["dfs_iter"]
        tr = tp.select_instance(a, seed=3)
        prose = " ".join(s.decision + " " + s.reason for s in tr.steps).lower()
        self.assertIn("recurse", prose)                                        # recursion narrated
        self.assertIn("backtrack", prose)                                      # and backtracking (is_teaching_trace)
        self.assertIsNone(generate_coding_cards(tr, display_solution("dfs_iter"), tp._deterministic_narration(tr, a)))


class DeterministicCodingIsWhitelisted(unittest.TestCase):
    """Gate-passing is necessary but NOT sufficient — a spurious region mapping (LIS's pre-allocated dp) or a
    missing template ships misaligned/robotic content. Deterministic coding is an explicit VERIFIED whitelist;
    an un-verified narration adapter must fall back to the LLM, not ship generated cards."""
    def test_whitelist_is_a_subset_of_narration_and_holds_the_verified_families(self):
        from app.services.examples.trace_adapters import DETERMINISTIC_CODING_SLUGS, NARRATION_SLUGS
        self.assertTrue(DETERMINISTIC_CODING_SLUGS <= NARRATION_SLUGS)
        for s in ("bubble_sort", "selection_sort", "insertion_sort", "merge_sort", "quick_sort", "bfs",
                  "topological_sort"):
            self.assertIn(s, DETERMINISTIC_CODING_SLUGS)

    def test_unverified_adapters_do_not_ship_generated_coding(self):
        # LIS (spurious dp mapping) and bst_search (missing templates -> weak fallback) must return None so the
        # pipeline keeps the LLM coding path — never ship the misaligned/robotic content. (topological_sort was
        # here until CP11b added its templates; it now ships deterministically.)
        from app.services.examples.coding_narration import generate_coding_cards
        from app.services.examples.canonical_solutions import display_solution
        for slug in ("longest_increasing_subsequence", "bst_search"):
            a = ADAPTERS[slug]
            tr = tp.select_instance(a, seed=3)
            with self.subTest(slug=slug):
                self.assertIsNone(generate_coding_cards(tr, display_solution(slug),
                                                        tp._deterministic_narration(tr, a)))

    def test_lis_constant_input_array_does_not_yield_a_spurious_mapping(self):
        # the growing-dp trace never matches the code's pre-allocated dp; the unchanging input array must not
        # let a wrong mapping validate.
        from app.services.examples.code_execution_check import _execute_on_instance, map_step_regions
        from app.services.examples.canonical_solutions import display_solution
        a = ADAPTERS["longest_increasing_subsequence"]; tr = tp.select_instance(a, seed=3)
        es, _, _ = _execute_on_instance(display_solution("longest_increasing_subsequence"), tr)
        self.assertIsNone(map_step_regions(es, tr))
