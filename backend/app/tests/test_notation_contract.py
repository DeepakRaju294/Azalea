"""Notation contract: an adapter-backed formula topic feeds its CANONICAL equation + variable letters into the
lesson prompt, so the LLM writes every card in the same notation the (deterministically grounded) formula card
uses — fixing the root cause of the P(H|E)-vs-P(A|B) drift (two independent sources, no shared contract)."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.prompts.lean_lesson_prompt import _formula_notation_contract, _path_notation_directive


class _Topic:
    def __init__(self, title, ctype="math_formula_method"):
        self.title = title
        self.course_type = self.topic_type = ctype
        self.study_path = None


class _Path:
    def __init__(self, topics):
        self.topics = topics
        for t in topics:
            t.study_path = self


class NotationContract(unittest.TestCase):
    def test_bayes_pins_A_B_and_forbids_H_E(self):
        c = _formula_notation_contract(_Topic("Bayes' Theorem"), "math_formula_method")
        self.assertIsNotNone(c)
        self.assertIn(r"P(A|B) = \frac{P(B|A)P(A)}{P(B)}", c)
        self.assertIn("EXACT variable letters everywhere: A, B", c)
        self.assertIn("H/E", c)                         # names the wrong convention to avoid

    def test_ltp_pins_its_equation(self):
        c = _formula_notation_contract(_Topic("Law of Total Probability"), "math_formula_method")
        self.assertIn(r"P(A) = \sum_{i} P(A|B_i)P(B_i)", c)
        self.assertIn("A, B", c)

    def test_combinations_pins_lowercase_n_r(self):
        # Generalized past probability's uppercase A/B: C(n, r) must pin n, r so the topic doesn't drift to C(n,k).
        c = _formula_notation_contract(_Topic("Combinations"), "math_formula_method")
        self.assertIsNotNone(c)
        self.assertIn("EXACT variable letters everywhere: n, r", c)

    def test_none_for_non_formula_topic_type(self):
        self.assertIsNone(_formula_notation_contract(_Topic("Bayes' Theorem", "concept_intuition"),
                                                     "concept_intuition"))

    def test_none_when_no_adapter_matches(self):
        self.assertIsNone(_formula_notation_contract(_Topic("Some Bespoke Topic With No Formula"),
                                                     "math_formula_method"))


class PathNotationDirective(unittest.TestCase):
    def test_non_adapter_topic_borrows_sibling_notation(self):
        # Binomial Theorem has no formula adapter; it should be steered to the C(n, r) its sibling
        # Combinations establishes — so it doesn't drift to C(n, k).
        binom = _Topic("Binomial Theorem")
        _Path([_Topic("Permutations"), _Topic("Combinations"), binom])
        d = _path_notation_directive(binom, "math_formula_method")
        self.assertIsNotNone(d)
        self.assertIn("C(n,r)", d)
        self.assertIn("never C(n, k)", d)

    def test_adapter_topic_gets_no_path_directive(self):
        # Combinations pins its own notation via _formula_notation_contract, so no path directive.
        combos = _Topic("Combinations")
        _Path([_Topic("Permutations"), combos, _Topic("Binomial Theorem")])
        self.assertIsNone(_path_notation_directive(combos, "math_formula_method"))

    def test_none_when_no_sibling_establishes_notation(self):
        solo = _Topic("Binomial Theorem")
        _Path([_Topic("Some Bespoke Topic"), solo])
        self.assertIsNone(_path_notation_directive(solo, "math_formula_method"))


if __name__ == "__main__":
    unittest.main()
