"""The declarative routing table (manifest.ROUTING_RULES) is the single source of truth for adapter routing
(scalable-adapters infra). These tests lock its behavior: every alias routes to its adapter, the tricky
overlaps resolve as designed, and meta/guarded topics defer. If someone adds a rule that mis-orders or
collides, a case here fails."""
import unittest

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters.manifest import ROUTING_RULES, match_routing_slug


class RoutingTable(unittest.TestCase):
    def test_every_alias_routes_to_its_owner(self):
        for slug, rule in ROUTING_RULES.items():
            extra = " ".join(rule.get("all", []))          # rules with require_all (bst_search) need those too
            for alias in rule.get("any", []) + rule.get("word", []):
                got = match_routing_slug(f"x {alias} {extra}".strip())
                with self.subTest(slug=slug, alias=alias):
                    self.assertEqual(got, slug, f"{alias!r} routed to {got}, expected {slug}")

    def test_overlap_precedence(self):
        # floyd/bellman beat dijkstra on shared 'shortest'/'all-pairs' terms; bare shortest-path -> dijkstra
        self.assertEqual(match_routing_slug("all-pairs shortest paths"), "floyd_warshall")
        self.assertEqual(match_routing_slug("bellman-ford shortest path"), "bellman_ford")
        self.assertEqual(match_routing_slug("dijkstra shortest path"), "dijkstra")
        self.assertEqual(match_routing_slug("shortest path"), "dijkstra")

    def test_bst_search_needs_a_search_operation_not_just_the_structure(self):
        self.assertIsNone(match_routing_slug("binary search tree"))          # bare structure -> defer
        self.assertEqual(match_routing_slug("binary search tree search"), "bst_search")
        self.assertEqual(match_routing_slug("searching a bst"), "bst_search")

    def test_tree_blocks_array_binary_search_and_graph_traversal(self):
        self.assertIsNone(match_routing_slug("binary search in a tree"))     # is_tree guard blocks binary_search
        self.assertIsNone(match_routing_slug("bfs in a tree"))               # is_tree guard blocks bfs
        self.assertEqual(match_routing_slug("binary search"), "binary_search")

    def test_bfs_word_boundary(self):
        self.assertEqual(match_routing_slug("run bfs"), "bfs")
        self.assertIsNone(match_routing_slug("subfscription"))               # 'bfs' inside a word must not match

    def test_induction_proof_does_not_collide_with_electromagnetic_induction(self):
        # bare "induction" is a math-proof alias; without a guard it also matched EM-induction topic titles
        # and shipped a "prove by mathematical induction" trace as the verified example for an AC-circuits
        # topic (live bug). EM-flavored titles must defer instead of claiming the proof adapter.
        self.assertIsNone(match_routing_slug("electromagnetic induction in ac circuits"))
        self.assertIsNone(match_routing_slug("applying faraday's law of induction"))
        self.assertIsNone(match_routing_slug("lenz's law and induced current"))
        self.assertIsNone(match_routing_slug("induction motor"))
        # a genuine math-induction proof still routes correctly
        self.assertEqual(match_routing_slug("prove by mathematical induction that 1+2+...+n=n(n+1)/2"),
                         "induction_proof")

    def test_meta_and_intro_topics_defer(self):
        self.assertIsNone(tp.route_adapter({"title": "Introduction to Binary Search"}))
        self.assertIsNone(tp.route_adapter({"title": "Merge Sort", "topic_type": "study_path_introduction"}))


if __name__ == "__main__":
    unittest.main()
