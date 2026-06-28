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
