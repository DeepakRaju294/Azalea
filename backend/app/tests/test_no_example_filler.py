"""The LLM sometimes fills a card's `example` field with a meta-sentence saying no example is needed
("No example role is necessary for this overview.") instead of leaving it blank, which renders as an empty
"Example" box. _is_no_example_filler detects that class so the field is blanked. Kept NARROW: real
illustrative examples (code, traces, prose) must never be flagged.

Run: python -m unittest app.tests.test_no_example_filler
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _is_no_example_filler as f


class NoExampleFiller(unittest.TestCase):
    def test_flags_meta_filler(self):
        for s in [
            "No example role is necessary for this overview.",
            "No example role is needed for this card.",
            "No example is necessary.",
            "No example needed.",
            "An example is not necessary here.",
            "Example is not required for this section.",
            "Not applicable.",
            "N/A",
            "n/a",
        ]:
            self.assertTrue(f(s), s)

    def test_keeps_real_examples(self):
        for s in [
            "inorder(root) on a BST with values [40,30,50,25,35]",
            "def dfs(graph, start):",
            "A -> B -> C",
            "factorial(5) = 5 * factorial(4)",
            "y = 2x^2 + 3x + 4 is a classic quadratic function.",
            "Consider a tree representing a family hierarchy.",
            "In GPS navigation, distances are represented in weighted graphs.",
            "Final order: [1, 2, 3, 4, 5, 6, 7]",
            "Example: sorting [3,1,2] yields [1,2,3].",  # a REAL example that opens with 'Example:'
        ]:
            self.assertFalse(f(s), s)

    def test_empty_is_not_filler(self):
        self.assertFalse(f(""))
        self.assertFalse(f(None))


if __name__ == "__main__":
    unittest.main()
