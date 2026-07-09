"""Domain-gate title normalization: strip algorithm/coding framing when remapping a topic OUT of a coding type.

A math topic remapped from algorithm_walkthrough must not keep an "Algorithm for …" title (the type is fixed but
the learner still reads "algorithm" — the exact bug seen on a live "completing the square" path). Offline.
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_domain_gate_title_framing
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.domain_gate import _normalize_title, rewrite_topic_contract


class TitleFraming(unittest.TestCase):
    def test_algorithm_for_prefix_stripped_to_math(self):
        self.assertEqual(_normalize_title("Algorithm for Completing the Square", "math_formula_method"),
                         "Completing the Square")

    def test_algorithm_walkthrough_prefix_stripped(self):
        self.assertEqual(_normalize_title("Algorithm Walkthrough for Completing the Square", "math_formula_method"),
                         "Completing the Square")

    def test_walkthrough_and_colon_and_suffix_forms(self):
        self.assertEqual(_normalize_title("Algorithm: Newton's Method", "math_formula_method"), "Newton's Method")
        self.assertEqual(_normalize_title("Walkthrough of Gaussian Elimination", "math_formula_method"),
                         "Gaussian Elimination")
        self.assertEqual(_normalize_title("Completing the Square Algorithm", "math_formula_method"),
                         "Completing the Square")

    def test_existing_coding_prefixes_still_stripped(self):
        self.assertEqual(_normalize_title("Implementing Dijkstra", "math_formula_method"), "Dijkstra")

    def test_coding_target_keeps_its_title(self):
        # remapping INTO / staying a coding type must not strip — an algorithm topic legitimately says "Algorithm"
        self.assertEqual(_normalize_title("Algorithm for Dijkstra", "algorithm_walkthrough"),
                         "Algorithm for Dijkstra")

    def test_non_framed_math_title_untouched(self):
        self.assertEqual(_normalize_title("Completing the Square", "math_formula_method"), "Completing the Square")
        self.assertEqual(_normalize_title("Finding the Vertex", "math_formula_method"), "Finding the Vertex")

    def test_full_remap_rewrites_title(self):
        topic = {"title": "Algorithm for Completing the Square", "course_type": "algorithm_walkthrough"}
        rewrite_topic_contract(topic, "math_formula_method", "math", reason="gate_remap")
        self.assertEqual(topic["title"], "Completing the Square")
        self.assertEqual(topic["course_type"], "math_formula_method")


if __name__ == "__main__":
    unittest.main()
