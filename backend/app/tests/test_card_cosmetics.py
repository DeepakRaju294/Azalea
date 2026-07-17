"""Final deterministic cosmetic sweep (_polish_card_cosmetics): phantom 'this diagram' body refs when no
visual, code-style // comments in non-coding worked examples, numbered-list point prefixes, a broken
'the formula is —' purpose lead-in, and a stale learning_goal on an adapter-grounded edge card."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _polish_card_cosmetics


class _Topic:
    def __init__(self, ctype="math_formula_method"):
        self.course_type = self.topic_type = ctype


def _run(cards, topic=None, grounded_edge=False):
    _polish_card_cosmetics(cards, topic or _Topic(), grounded_edge=grounded_edge)
    return cards


class PhantomVisual(unittest.TestCase):
    def test_diagram_body_dropped_when_no_visual(self):
        c = [{"card_type": "purpose_context",
              "body": ["This node-link diagram illustrates the structure of combinatorial analysis."],
              "points": ["Real content."]}]
        _run(c)
        self.assertIsNone(c[0]["body"])
        self.assertEqual(c[0]["points"], ["Real content."])

    def test_kept_when_a_visual_is_present(self):
        c = [{"card_type": "background", "visual_type": "node_link_diagram",
              "body": ["This diagram shows the graph."], "points": ["p"]}]
        _run(c)
        self.assertEqual(c[0]["body"], ["This diagram shows the graph."])

    def test_ordinary_body_untouched(self):
        c = [{"card_type": "purpose_context", "body": ["Combinatorics counts arrangements."], "points": ["p"]}]
        _run(c)
        self.assertEqual(c[0]["body"], ["Combinatorics counts arrangements."])


class CodeCommentsInMathWork(unittest.TestCase):
    def test_slash_comment_becomes_prose_annotation(self):
        c = [{"card_type": "worked_example",
              "points": ["Work:", "  - Total letters = 6 // the word BANANA has 6 letters"]}]
        _run(c)
        self.assertEqual(c[0]["points"][1], "  - Total letters = 6 — the word BANANA has 6 letters")

    def test_math_topic_strips_comments_even_with_code_lines(self):
        # gen_foundation spuriously sets code_lines on a MATH worked example — the topic type governs, so // is
        # still stripped (it's code-leakage, not real code).
        c = [{"card_type": "worked_example", "code_lines": [[1, 3]],
              "points": ["  - factorial_n = 6! = 720 // calculating factorial of n"]}]
        _run(c, topic=_Topic("problem_solving_application"))
        self.assertEqual(c[0]["points"][0], "  - factorial_n = 6! = 720 — calculating factorial of n")

    def test_coding_topic_keeps_comments(self):
        c = [{"card_type": "worked_example", "points": ["  - x = 0 // initialize"]}]
        _run(c, topic=_Topic("coding_implementation"))
        self.assertEqual(c[0]["points"][0], "  - x = 0 // initialize")


class NumberedListPrefix(unittest.TestCase):
    def test_short_label_prefix_stripped(self):
        c = [{"card_type": "purpose_context", "points": ["1. Permutations", "  - Order matters",
                                                         "2. Combinations", "  - Order does not matter"]}]
        _run(c)
        self.assertEqual(c[0]["points"][0], "Permutations")
        self.assertEqual(c[0]["points"][2], "Combinations")

    def test_numbered_step_sentence_untouched(self):
        c = [{"card_type": "method_process", "points": ["1. Substitute the values into the formula"]}]
        _run(c)
        self.assertEqual(c[0]["points"][0], "1. Substitute the values into the formula")

    def test_decimal_not_stripped(self):
        c = [{"card_type": "purpose_context", "points": ["3.14 is pi"]}]
        _run(c)
        self.assertEqual(c[0]["points"][0], "3.14 is pi")


class DanglingFormulaLeadIn(unittest.TestCase):
    def test_broken_formula_lead_in_dropped(self):
        c = [{"card_type": "purpose_context",
              "points": ["Permutations arrange items.",
                         "The formula is — calculates arrangements of r from n items:"]}]
        _run(c)
        self.assertEqual(c[0]["points"], ["Permutations arrange items."])

    def test_clean_formula_lead_in_with_math_kept(self):
        c = [{"card_type": "purpose_context", "points": ["The formula is P(n,r) = n!/(n-r)!"]}]
        _run(c)
        self.assertEqual(len(c[0]["points"]), 1)

    def test_formula_mention_without_dash_kept(self):
        c = [{"card_type": "purpose_context", "points": ["Understanding the formula helps solve problems."]}]
        _run(c)
        self.assertEqual(len(c[0]["points"]), 1)


class GroundedEdgeLearningGoal(unittest.TestCase):
    def test_stale_learning_goal_dropped_on_grounded_edge(self):
        c = [{"card_type": "edge_case", "learning_goal": "Understand what happens when r is zero.",
              "points": [r"Requires \(0 \leq r \leq n\)."]}]
        _run(c, grounded_edge=True)
        self.assertNotIn("learning_goal", c[0])

    def test_kept_when_edge_not_grounded(self):
        c = [{"card_type": "edge_case", "learning_goal": "goal", "points": ["p"]}]
        _run(c, grounded_edge=False)
        self.assertEqual(c[0]["learning_goal"], "goal")


if __name__ == "__main__":
    unittest.main()
