"""Reference-first worked-example construction: correct, complete MST cards from a trusted run."""
import unittest

from app.services.gen_foundation.reference_first import (
    build_reference_cards, kruskal_steps, prim_steps, _algorithm_for,
)
from app.services.gen_foundation.property_checks import _node_labels, _weighted_edges, _reference_mst

GRAPH = {"graph": {"nodes": ["A", "B", "C", "D", "E"],
                   "edges": [["A", "B", 6], ["A", "C", 1], ["C", "B", 2], ["B", "D", 5],
                             ["C", "D", 8], ["D", "E", 3], ["C", "E", 7]]}}


class ReferenceFirstTests(unittest.TestCase):
    def setUp(self):
        self.nodes = _node_labels(GRAPH)
        self.edges = _weighted_edges(GRAPH)
        self.ref_w, self.ref_c = _reference_mst(self.nodes, self.edges)

    def _weight(self, mst):
        return sum(w for _u, _v, w in mst)

    def test_kruskal_matches_reference(self):
        _steps, mst = kruskal_steps(self.nodes, self.edges)
        self.assertEqual(len(mst), self.ref_c)
        self.assertAlmostEqual(self._weight(mst), self.ref_w)

    def test_prim_matches_reference(self):
        _steps, mst = prim_steps(self.nodes, self.edges, start="A")
        self.assertEqual(len(mst), self.ref_c)
        self.assertAlmostEqual(self._weight(mst), self.ref_w)

    def test_prim_and_kruskal_same_total(self):
        _s1, m1 = kruskal_steps(self.nodes, self.edges)
        _s2, m2 = prim_steps(self.nodes, self.edges, start="A")
        self.assertAlmostEqual(self._weight(m1), self._weight(m2))

    def test_algorithm_detection(self):
        self.assertEqual(_algorithm_for("Understanding Prim's Algorithm"), "prim")
        self.assertEqual(_algorithm_for("Kruskal's Algorithm for MST"), "kruskal")

    def test_cards_are_correct_and_complete(self):
        for title in ["Kruskal's Algorithm", "Understanding Prim's Algorithm"]:
            r = build_reference_cards("graph_mst", title, GRAPH)
            self.assertTrue(r["cards"])
            self.assertEqual(len(r["final_answer"]), self.ref_c, title)
            self.assertAlmostEqual(self._weight([tuple(e) for e in r["final_answer"]]), self.ref_w, msg=title)
            self.assertEqual(r["source"], "reference_first")
            self.assertTrue(r["trace_backed"])
            # every step card has the liked format fields
            for c in r["cards"]:
                self.assertTrue(c["goal"] and c["work"] and c["result"])
                self.assertTrue(c["trace_backed"])

    def test_problem_states_same_graph(self):
        r = build_reference_cards("graph_mst", "Kruskal's Algorithm", GRAPH)
        self.assertIn("minimum spanning tree", r["problem"].lower())
        for n in ["A", "B", "C", "D", "E"]:
            self.assertIn(n, r["problem"])

    def test_non_mst_family_skipped(self):
        self.assertEqual(build_reference_cards("sorting", "Bubble Sort", GRAPH), {})

    def test_no_edges_skipped(self):
        self.assertEqual(build_reference_cards("graph_mst", "Kruskal", {"nodes": ["A", "B"]}), {})


class SortReferenceTests(unittest.TestCase):
    ARR = [5, 2, 8, 1, 9, 3, 3]

    def test_each_sort_is_correct_and_conceptual(self):
        for title in ["Understanding Bubble Sort", "How Selection Sort Works", "Insertion Sort Walkthrough"]:
            r = build_reference_cards("array_sort", title, {"array": list(self.ARR)})
            self.assertTrue(r["cards"], title)
            self.assertEqual(r["final_answer"], sorted(self.ARR), title)
            self.assertEqual(r["source"], "reference_first")
            for c in r["cards"]:                       # conceptual: no executed code refs
                self.assertTrue(c["goal"] and c["work"] and c["result"])
                self.assertEqual(c["code_refs"], [])

    def test_problem_states_the_array(self):
        r = build_reference_cards("array_sort", "Bubble Sort", {"array": [4, 1, 2]})
        self.assertIn("[4, 1, 2]", r["problem"])

    def test_unknown_algorithm_skipped(self):
        self.assertEqual(build_reference_cards("array_sort", "Quantum Teleportation", {"array": [1, 2]}), {})

    def test_single_element_skipped(self):
        self.assertEqual(build_reference_cards("array_sort", "Bubble Sort", {"array": [1]}), {})


class TraversalReferenceTests(unittest.TestCase):
    G = {"graph": {"A": ["B", "C"], "B": ["A", "D"], "C": ["A", "D"], "D": ["B", "C", "E"], "E": ["D"]}}

    def test_bfs_order_correct(self):
        r = build_reference_cards("graph_traversal", "Breadth-First Search", self.G)
        self.assertEqual(r["final_answer"], ["A", "B", "C", "D", "E"])
        self.assertEqual(r["source"], "reference_first")

    def test_dfs_order_correct(self):
        r = build_reference_cards("graph_traversal", "Depth-First Search", self.G)
        self.assertEqual(r["final_answer"], ["A", "B", "D", "C", "E"])

    def test_visits_every_node_once(self):
        for title in ["BFS", "DFS"]:
            r = build_reference_cards("graph_traversal", title, self.G)
            self.assertEqual(sorted(r["final_answer"]), ["A", "B", "C", "D", "E"], title)

    def test_unknown_traversal_skipped(self):
        self.assertEqual(build_reference_cards("graph_traversal", "Topological", self.G), {})

    def test_weighted_graph_not_treated_as_traversal(self):
        weighted = {"graph": {"nodes": ["A", "B"], "edges": [["A", "B", 3]]}}
        self.assertEqual(build_reference_cards("graph_traversal", "BFS", weighted), {})


class BinarySearchReferenceTests(unittest.TestCase):
    NUMS = [10, 20, 30, 40, 50, 60, 70]

    def test_finds_present_targets(self):
        from app.services.gen_foundation.reference_first import binary_search_steps
        for i, t in enumerate(self.NUMS):
            _steps, idx = binary_search_steps(self.NUMS, t)
            self.assertEqual(idx, i, t)

    def test_missing_target_returns_minus_one(self):
        from app.services.gen_foundation.reference_first import binary_search_steps
        _steps, idx = binary_search_steps(self.NUMS, 35)
        self.assertEqual(idx, -1)

    def test_cards_correct(self):
        r = build_reference_cards("array_binary_search", "Binary Search", {"nums": self.NUMS, "target": 60})
        self.assertEqual(r["final_answer"], 5)
        self.assertEqual(r["source"], "reference_first")
        self.assertTrue(all(c["goal"] and c["work"] for c in r["cards"]))


class BSTReferenceTests(unittest.TestCase):
    TREE = [15, 6, 48, None, None, None, 56, 49, 58]  # 15 -> (6, 48); 48 -> (_, 56); 56 -> (49, 58)

    def test_search_walks_to_present_value(self):
        r = build_reference_cards("tree_bst", "BST Search", {"tree": self.TREE})
        self.assertEqual(r["source"], "reference_first")
        self.assertIn("found", r["cards"][-1]["result"].lower() + r["cards"][-1]["goal"].lower())

    def test_insert_places_a_new_value(self):
        r = build_reference_cards("tree_bst", "BST Insertion", {"tree": self.TREE})
        self.assertTrue(r["cards"])
        self.assertIn("insert", r["cards"][-1]["goal"].lower())

    def test_non_bst_op_skipped(self):
        self.assertEqual(build_reference_cards("tree_bst", "BST Height", {"tree": self.TREE}), {})

    def test_rebuild_from_level_order(self):
        from app.services.gen_foundation.reference_first import _bst_from_level_order
        root = _bst_from_level_order(self.TREE)
        self.assertEqual(root["val"], 15)
        self.assertEqual(root["left"]["val"], 6)
        self.assertEqual(root["right"]["val"], 48)


class LabelRestoreTests(unittest.TestCase):
    """Executed integer indices map back to the input's own labels, without corrupting weights."""
    L = ["A", "B", "C", "D"]

    def test_edge_triple_maps_endpoints_keeps_weight(self):
        from app.services.gen_foundation.trace_first import _restore_node_labels
        self.assertEqual(_restore_node_labels([0, 2, 7], self.L), ["A", "C", 7])

    def test_list_of_edges(self):
        from app.services.gen_foundation.trace_first import _restore_node_labels
        self.assertEqual(_restore_node_labels([[0, 1, 6], [2, 3, 9]], self.L),
                         [["A", "B", 6], ["C", "D", 9]])

    def test_node_set_all_mapped(self):
        from app.services.gen_foundation.trace_first import _restore_node_labels
        self.assertEqual(_restore_node_labels({0, 1, 3}, self.L), {"A", "B", "D"})

    def test_weight_scalar_untouched(self):
        from app.services.gen_foundation.trace_first import _restore_node_labels
        self.assertEqual(_restore_node_labels({"cost": 6, "mst": [[0, 1, 6]]}, self.L),
                         {"cost": 6, "mst": [["A", "B", 6]]})

    def test_no_labels_is_noop(self):
        from app.services.gen_foundation.trace_first import _restore_node_labels
        self.assertEqual(_restore_node_labels([0, 1, 6], []), [0, 1, 6])

    def test_out_of_range_index_left_alone(self):
        from app.services.gen_foundation.trace_first import _restore_node_labels
        self.assertEqual(_restore_node_labels([0, 99, 6], self.L), ["A", 99, 6])


if __name__ == "__main__":
    unittest.main()
