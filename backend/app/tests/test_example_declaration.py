"""Example System — Phase 1: deterministic declaration (spec §9.1).

Bad routing is silent and costly, so these are a formal gate. Pure, no LLM.
Run: python -m unittest app.tests.test_example_declaration
"""
from __future__ import annotations

import unittest

from app.core.example_applications import APPLICATION_PATTERNS, APPLICATION_PROFILES, match_application
from app.services.examples.declaration import declare_example, pick_fixture


def _topic(title, topic_type):
    return {"id": "t", "title": title, "topic_type": topic_type}


class TestRouting(unittest.TestCase):
    def test_binary_search_concept(self):
        d = declare_example(_topic("Binary Search", "algorithm_walkthrough"))
        self.assertEqual((d.application, d.resolved_example_type, d.pattern),
                         ("binary_search", "sequence_state_trace", "range_halving"))

    def test_binary_search_coding_gates_to_code(self):
        d = declare_example(_topic("Implementing Binary Search", "coding_implementation"))
        self.assertEqual((d.application, d.resolved_example_type, d.pattern),
                         ("binary_search", "code_execution_trace", "loop_execution"))

    def test_bfs(self):
        d = declare_example(_topic("BFS Traversal of a Graph", "algorithm_walkthrough"))
        self.assertEqual((d.application, d.resolved_example_type), ("bfs", "node_link_trace"))

    def test_unique_paths(self):
        d = declare_example(_topic("Unique Paths (DP)", "algorithm_walkthrough"))
        self.assertEqual((d.application, d.resolved_example_type, d.pattern),
                         ("unique_paths", "grid_table_trace", "dp_table_fill"))

    def test_quadratic_formula(self):
        d = declare_example(_topic("Quadratic Formula", "math_formula_method"))
        self.assertEqual((d.application, d.resolved_example_type), ("quadratic_formula", "symbolic_derivation"))

    def test_unknown_title_returns_none(self):
        self.assertIsNone(declare_example(_topic("History of Rome", "concept_intuition")))

    def test_intro_topic_never_declares_an_example(self):
        # study_path_introduction has no worked_example slot (background + roadmap
        # only) — even a matching title must not declare an example.
        self.assertIsNone(declare_example(_topic("Introduction to Binary Search", "study_path_introduction")))


class TestCodeVsConceptGate(unittest.TestCase):
    def test_concept_topic_never_gates_to_code(self):
        # Even with "implementing" wording, an algorithm_walkthrough stays conceptual.
        d = declare_example(_topic("Binary Search Walkthrough", "algorithm_walkthrough"))
        self.assertEqual(d.resolved_example_type, "sequence_state_trace")

    def test_coding_app_without_code_lens_stays_conceptual(self):
        # unique_paths has no code_example_type → a coding topic still resolves to grid.
        self.assertIsNone(APPLICATION_PROFILES["unique_paths"].code_example_type)
        d = declare_example(_topic("Implementing Unique Paths", "coding_implementation"))
        self.assertEqual(d.resolved_example_type, "grid_table_trace")


class TestNoPatternCollisions(unittest.TestCase):
    def test_each_canonical_title_matches_exactly_one_pattern(self):
        titles = [
            "Binary Search", "Implementing Binary Search", "BFS Traversal of a Graph",
            "Depth First Search", "Unique Paths (DP)", "Quadratic Formula",
            "Inorder Traversal of a BST",
        ]
        for title in titles:
            hits = [app for app, pat in APPLICATION_PATTERNS if pat.search(title)]
            self.assertEqual(len(hits), 1, f"{title!r} matched {hits}")


class TestPickFixture(unittest.TestCase):
    def test_selects_concept_fixture_for_concept_lens(self):
        d = declare_example(_topic("Binary Search", "algorithm_walkthrough"))
        fx = pick_fixture(d, "worked_example")
        self.assertIsNotNone(fx)
        self.assertEqual(fx.fixture_id, "binary_search_concept_found_late_01")
        self.assertEqual(fx.example_type, "sequence_state_trace")

    def test_selects_code_fixture_for_code_lens(self):
        d = declare_example(_topic("Implementing Binary Search", "coding_implementation"))
        fx = pick_fixture(d, "worked_example")
        self.assertIsNotNone(fx)
        self.assertEqual(fx.fixture_id, "binary_search_code_loop_found_late_01")
        self.assertEqual(fx.example_type, "code_execution_trace")

    def test_quadratic_formula_routes_to_symbolic_fixture(self):
        d = declare_example(_topic("Quadratic Formula", "math_formula_method"))
        fx = pick_fixture(d, "worked_example")
        self.assertIsNotNone(fx)
        self.assertEqual(fx.fixture_id, "quadratic_formula_concept_distinct_roots_01")
        self.assertEqual(fx.example_type, "symbolic_derivation")

    def test_widened_routings(self):
        cases = [
            ("Depth-First Search (DFS)", "algorithm_walkthrough", "dfs_concept_branching_graph_01"),
            ("Implementing BFS in Python", "coding_implementation", "bfs_code_queue_loop_01"),
            ("Inorder Traversal of a BST", "coding_implementation", "tree_traversal_code_recursive_inorder_01"),
            ("Linear Search", "coding_implementation", "linear_search_code_loop_found_late_01"),
            ("The Coin Change Problem", "algorithm_walkthrough", "coin_change_concept_1_3_4_amount6_01"),
            ("Solving Linear Equations", "math_formula_method", "linear_equation_concept_3x_plus_4_01"),
            ("The Distance Formula", "math_formula_method", "distance_formula_concept_3_4_5_01"),
            ("Compound Interest Explained", "math_formula_method", "compound_interest_concept_1000_10pct_2y_01"),
            ("Set Operations: Union and Intersection", "concept_intuition", "set_operation_concept_two_clubs_01"),
            ("Graphing a Quadratic Parabola", "math_formula_method", "function_graph_analysis_concept_parabola_01"),
            ("Stack vs Heap Memory", "concept_intuition", "stack_heap_allocation_concept_list_01"),
            ("The TCP Three-Way Handshake", "process_walkthrough", "protocol_sequence_concept_tcp_handshake_01"),
            ("The Pythagorean Theorem", "math_formula_method", "triangle_geometry_concept_3_4_5_01"),
            ("Proof by Induction", "proof_reasoning", "induction_proof_concept_sum_formula_01"),
            ("BFS vs DFS", "compare_distinguish", "algorithm_comparison_concept_bfs_vs_dfs_01"),
        ]
        for title, ttype, expected in cases:
            with self.subTest(title=title):
                d = declare_example(_topic(title, ttype))
                fx = pick_fixture(d, "worked_example")
                self.assertIsNotNone(fx, title)
                self.assertEqual(fx.fixture_id, expected)

    def test_traversal_variants_route_to_their_own_fixture(self):
        # The variant axis is a hard filter: postorder must NEVER get inorder code.
        cases = [
            ("Inorder Traversal of a BST", "tree_traversal_code_recursive_inorder_01"),
            ("Preorder Traversal of a BST", "tree_traversal_code_recursive_preorder_01"),
            ("Postorder Traversal of a BST", "tree_traversal_code_recursive_postorder_01"),
        ]
        for title, expected in cases:
            with self.subTest(title=title):
                d = declare_example(_topic(title, "coding_implementation"))
                fx = pick_fixture(d, "worked_example")
                self.assertIsNotNone(fx, title)
                self.assertEqual(fx.fixture_id, expected)

    def test_level_order_variant_without_fixture_stays_inert(self):
        d = declare_example(_topic("Level-Order Traversal", "coding_implementation"))
        self.assertIsNotNone(d)
        self.assertEqual(d.variant, "level_order")
        self.assertIsNone(pick_fixture(d, "worked_example"))  # legacy, never wrong content

    def test_concept_tree_traversal_stays_inert(self):
        # tree_traversal has no conceptual simulator yet — a concept topic declares
        # the concept lens, which has no fixture → legacy (never the code fixture).
        d = declare_example(_topic("Inorder Traversal of a BST", "algorithm_walkthrough"))
        self.assertIsNotNone(d)
        self.assertEqual(d.resolved_example_type, "node_link_trace")
        self.assertIsNone(pick_fixture(d, "worked_example"))


if __name__ == "__main__":
    unittest.main()
