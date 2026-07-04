"""End-to-end Phase-1 tests for every deterministic trace adapter — fully offline (no LLM)."""
import unittest

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_contract import (structural_invariants, validate_fidelity, validate_prose)


def faithful(trace):
    """A correct stub formatter: states each step's required_facts + its expected_visible_result."""
    def fmt(_payload):
        cards = []
        for s in trace.steps:
            work = list(s.facts.get("required_facts", [])) + [s.expected_visible_result]
            cards.append({"title": s.operation, "goal": s.decision or s.operation,
                          "reasoning": s.reason, "work": work, "result": s.expected_visible_result})
        return {"cards": cards}
    return fmt


class AllAdaptersPhase1(unittest.TestCase):
    def test_each_adapter_produces_a_verified_renderable_example(self):
        for slug, adapter in ADAPTERS.items():
            with self.subTest(slug=slug):
                trace = tp.select_instance(adapter, seed=3)
                self.assertIsNotNone(trace, f"{slug}: Stage 0 found no teaching instance")
                self.assertEqual(structural_invariants(trace, adapter), [], f"{slug}: structural gate")
                cards = tp._normalize_and_attach(faithful(trace)(None), trace)
                self.assertIsNotNone(cards, f"{slug}: normalize/attach")
                self.assertEqual(len(cards), len(trace.steps), f"{slug}: one card per step")
                self.assertTrue(validate_fidelity(cards, trace, adapter).ok, f"{slug}: machine-state fidelity")
                self.assertEqual(validate_prose(cards, trace, adapter), [], f"{slug}: prose fidelity")


class AdapterCorrectness(unittest.TestCase):
    def test_bfs_visit_order_is_correct(self):
        a = ADAPTERS["bfs"]
        g = {"A": ["B", "C"], "B": ["A", "D"], "C": ["A", "D"], "D": ["B", "C"]}
        tr = a.reference({"graph": g, "start": "A"})
        self.assertEqual(tr.final_answer["visit_order"], ["A", "B", "C", "D"])
        self.assertEqual(structural_invariants(tr, a), [])

    def test_dfs_visit_order_is_correct(self):
        a = ADAPTERS["dfs_iter"]
        g = {"A": ["B", "C"], "B": ["A", "D"], "C": ["A", "D"], "D": ["B", "C"]}
        tr = a.reference({"graph": g, "start": "A"})
        self.assertEqual(tr.final_answer["visit_order"], ["A", "B", "D", "C"])
        self.assertEqual(structural_invariants(tr, a), [])

    def test_kruskal_mst_is_minimal(self):
        a = ADAPTERS["kruskal"]
        edges = [["A", "B", 1], ["B", "C", 2], ["C", "D", 3], ["A", "D", 10], ["B", "D", 1]]
        tr = a.reference({"graph": {"nodes": ["A", "B", "C", "D"], "edges": edges}})
        self.assertEqual(tr.final_answer["total_weight"], 4)            # 1+1+2
        self.assertEqual(len(tr.final_answer["mst_edges"]), 3)          # V-1
        self.assertEqual(structural_invariants(tr, a), [])

    def test_prim_mst_is_minimal(self):
        a = ADAPTERS["prim"]
        g = {"nodes": ["A", "B", "C", "D"],
             "edges": [["A", "B", 1], ["B", "C", 2], ["C", "D", 3], ["A", "D", 10], ["B", "D", 1]]}
        tr = a.reference({"graph": g, "start": "A"})
        self.assertEqual(tr.final_answer["total_weight"], 4)            # 1+1+2, same MST weight as Kruskal
        self.assertEqual(len(tr.final_answer["mst_edges"]), 3)          # V-1
        self.assertEqual(structural_invariants(tr, a), [])

    def test_merge_sort_sorts(self):
        a = ADAPTERS["merge_sort"]
        tr = a.reference({"array": [5, 2, 8, 1, 9, 3]})
        self.assertEqual(tr.final_answer["sorted"], [1, 2, 3, 5, 8, 9])
        self.assertEqual(structural_invariants(tr, a), [])

    def test_quick_sort_first_partition_is_never_a_no_op(self):
        # The opening card must visibly move values — reject instances whose first pivot (the last
        # element) is already the min/max, which would "partition" while nothing changes.
        from app.services.examples import trace_pipeline as tp
        a = ADAPTERS["quick_sort"]
        for seed in range(12):
            tr = tp.select_instance(a, seed=seed)
            arr = tr.initial_state["array"]
            first = tr.steps[0]
            with self.subTest(seed=seed):
                self.assertLess(min(arr), arr[-1])
                self.assertLess(arr[-1], max(arr))
                self.assertNotEqual(first.prior_state["array"], first.state_after["array"])
                self.assertEqual(tr.final_answer["sorted"], sorted(arr))

    def test_quick_sort_partition_names_true_smaller_set(self):
        # The adapter must state the ACTUAL smaller values (never let the formatter guess). The two observed
        # bugs: (a) "no values are less than 50" when 39/40/27 all are; (b) "smaller values (24,18)" for
        # pivot 7 when 24,18 are LARGER. Both must be caught; the faithful reason must be clean.
        a = ADAPTERS["quick_sort"]
        tr = a.reference({"array": [41, 24, 18, 7, 26, 30, 56]})
        s7 = next(s for s in tr.steps if s.inputs["pivot"] == 7)
        self.assertEqual(s7.inputs["smaller"], [])                          # 7 is the slice minimum
        bug = {"reasoning": "shift smaller values (24, 18) left", "work": [], "result": "pivot 7"}
        self.assertTrue(any(c == "larger_value_called_smaller" for c, _ in a.validate_prose_claims(bug, s7)))

        tr2 = a.reference({"array": [11, 50, 39, 40, 27, 18]})
        s50 = next(s for s in tr2.steps if s.inputs["pivot"] == 50)
        self.assertEqual(s50.inputs["smaller"], [27, 39, 40])
        bug2 = {"reasoning": "since no values are less than 50 it stays", "work": [], "result": "pivot 50"}
        self.assertTrue(any(c == "false_no_smaller_values" for c, _ in a.validate_prose_claims(bug2, s50)))

        for s in (s7, s50):                                                # faithful reason never flagged
            faithful = {"reasoning": s.reason, "work": [], "result": s.expected_visible_result}
            self.assertEqual(a.validate_prose_claims(faithful, s), [])

    def test_quick_sort_walkthrough_narrates_recursion_and_names_noops(self):
        # Tier 3 pedagogy: the pivot ORDER must not read as arbitrary — each partition states which side of
        # which parent pivot it is, and a partition that changes nothing is named (not a silently 'frozen'
        # array). [55,11,13,2,19,34,52,9] ends sorted early, then recurses down the right side with no-ops.
        a = ADAPTERS["quick_sort"]
        tr = a.reference({"array": [55, 11, 13, 2, 19, 34, 52, 9]})
        reasons = [s.reason for s in tr.steps]
        joined = " ".join(reasons)
        self.assertIn("Start with the whole array", reasons[0])
        self.assertTrue(any("RIGHT side of pivot" in r for r in reasons))   # recursion descent narrated
        self.assertTrue(any("LEFT side" in r for r in reasons))
        # a no-op partition (pivot already in order) is explicitly named, not silently identical
        noop = [s for s in tr.steps if s.prior_state["array"] == s.state_after["array"]]
        self.assertTrue(noop, "this instance should have a no-op partition on the right side")
        for s in noop:
            self.assertIn("nothing moves", s.reason)
        # the visual carries the active slice window so recursion progress shows even on a no-op
        for s in tr.steps:
            self.assertIn("window", s.visual_state)
            self.assertEqual(len(s.visual_state["window"]), 2)


class RoutingTests(unittest.TestCase):
    def test_explicit_routing(self):
        cases = {
            "Understanding Binary Search": "binary_search",
            "Understanding Kruskal's Algorithm": "kruskal",
            "Understanding Prim's Algorithm": "prim",
            "Bottom-up Merge Sort": "merge_sort",
            "Breadth-First Search Walkthrough": "bfs",
            "Depth-First Search (DFS)": "dfs_iter",
            "Dijkstra's Shortest Path": "dijkstra",
        }
        for title, slug in cases.items():
            with self.subTest(title=title):
                ad = tp.route_adapter({"title": title})
                self.assertIsNotNone(ad)
                self.assertEqual(ad.slug, slug)

    def test_unrelated_topics_defer(self):
        for title in ["Graph Algorithms Overview", "Hash Tables", "Recursion Basics"]:
            self.assertIsNone(tp.route_adapter({"title": title}), title)


if __name__ == "__main__":
    unittest.main()
