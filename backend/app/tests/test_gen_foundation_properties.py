"""Tests for Layer 3 family property checks (gen_foundation)."""
import unittest

from app.services.gen_foundation.property_checks import (
    family_properties, check_sort, check_mst, check_traversal,
)


class SortPropertyTests(unittest.TestCase):
    def test_valid_sort_passes(self):
        self.assertEqual(check_sort([3, 1, 2], [1, 2, 3]), [])

    def test_unordered_output_flagged(self):
        self.assertTrue(any("nondecreasing" in v for v in check_sort([3, 1, 2], [1, 3, 2])))

    def test_dropped_value_flagged(self):
        self.assertTrue(any("permutation" in v for v in check_sort([3, 1, 2], [1, 2])))

    def test_input_dict_array(self):
        self.assertEqual(check_sort({"array": [2, 1]}, [1, 2]), [])


class MstPropertyTests(unittest.TestCase):
    def test_correct_edge_count_passes(self):
        # 4 nodes -> MST has 3 edges
        out = (10, [("A", "B"), ("B", "C"), ("C", "D")])
        self.assertEqual(check_mst({"nodes": ["A", "B", "C", "D"]}, out), [])

    def test_phantom_seed_edge_flagged(self):
        # the reviewer's bug: V entries (incl. the (0, start) seed) instead of V-1
        out = (10, [(0, "A"), (3, "B"), (1, "C"), (2, "D")])  # 4 'edges' on 4 nodes
        viol = check_mst({"nodes": ["A", "B", "C", "D"]}, out)
        self.assertTrue(viol and "V-1=3" in viol[0])

    def test_node_count_from_adjacency_map(self):
        graph = {"A": [("B", 1)], "B": [("A", 1), ("C", 2)], "C": [("B", 2)]}
        out = (3, [("A", "B"), ("B", "C")])  # 3 nodes -> 2 edges, correct
        self.assertEqual(check_mst({"graph": graph}, out), [])


class TraversalPropertyTests(unittest.TestCase):
    def test_valid_bfs_passes(self):
        self.assertEqual(check_traversal({"nodes": ["A", "B", "C"]}, ["A", "B", "C"]), [])

    def test_duplicate_visit_flagged(self):
        self.assertTrue(any("more than once" in v
                            for v in check_traversal({"nodes": ["A", "B"]}, ["A", "B", "A"])))

    def test_unknown_node_flagged(self):
        self.assertTrue(any("not in the graph" in v
                            for v in check_traversal({"nodes": ["A", "B"]}, ["A", "Z"])))


class DispatchTests(unittest.TestCase):
    def test_family_keyword_dispatch(self):
        # "graph_mst" family routes to the MST check
        viol = family_properties("graph_mst", {"nodes": ["A", "B", "C"]},
                                 (5, [(0, "A"), (2, "B"), (3, "C")]))
        self.assertTrue(viol)

    def test_prim_family_routes_to_mst(self):
        viol = family_properties("prim_algorithm", {"nodes": ["A", "B"]}, (1, [(0, "A"), (1, "B")]))
        self.assertTrue(viol)  # 2 'edges' on 2 nodes -> phantom seed

    def test_unknown_family_no_checks(self):
        self.assertEqual(family_properties("number_theory", [1, 2, 3], "anything"), [])

    def test_never_raises_on_garbage(self):
        self.assertEqual(family_properties("graph_mst", None, None), [])
        self.assertEqual(family_properties("array_sort", {"weird": 1}, {"also": "weird"}), [])


if __name__ == "__main__":
    unittest.main()
