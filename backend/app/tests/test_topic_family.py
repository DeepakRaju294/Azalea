"""Tests for topic-family derivation (activates the property gate / executor on coding topics)."""
import unittest

from app.core.topic_family import derive_topic_family


class DeriveFamilyTests(unittest.TestCase):
    def test_mst_titles(self):
        for title in ["Implementing Kruskal's Algorithm", "Understanding Prim's Algorithm",
                      "Minimum Spanning Tree Basics", "Union-Find for MST"]:
            self.assertEqual(derive_topic_family(title), "graph_mst", title)

    def test_other_families(self):
        self.assertEqual(derive_topic_family("Implementing Dijkstra's Shortest Path"), "graph_shortest_path")
        self.assertEqual(derive_topic_family("Breadth-First Search Traversal"), "graph_traversal_bfs")
        self.assertEqual(derive_topic_family("Implementing Quicksort"), "array_sort")
        self.assertEqual(derive_topic_family("Binary Search Tree Insertion"), "tree_bst")

    def test_explicit_family_respected(self):
        self.assertEqual(derive_topic_family("anything", existing="custom_family"), "custom_family")

    def test_no_guess_when_unknown(self):
        self.assertEqual(derive_topic_family("Introduction to Recursion"), "")
        self.assertEqual(derive_topic_family(None), "")

    def test_derived_family_triggers_mst_gate(self):
        # the whole point: a derived 'graph_mst' makes the claimed-answer MST check dispatch
        from app.services.gen_foundation.property_checks import claimed_answer_violations
        fam = derive_topic_family("Implementing Kruskal's Algorithm")
        viol = claimed_answer_violations(fam, {"nodes": list("ABCDEFGH")},
                                         "MST: [(A,B,4),(B,C,9),(C,D,5)]")  # 3 edges on 8 nodes
        self.assertTrue(viol)  # now fires (would have been silent with empty family)


if __name__ == "__main__":
    unittest.main()
