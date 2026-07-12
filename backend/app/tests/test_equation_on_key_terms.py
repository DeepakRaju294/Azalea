"""For a math/science formula topic, the key-terms (components/definition) card must show the EQUATION as its
first point — alone — so the learner sees the equation while reading the terms it uses; and a `references` field
holds it. No-op for a non-formula topic."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _lean_card_to_legacy, _prepend_equation_to_key_terms

_EQ = r"$$P(A) = \sum_i P(A|B_i)P(B_i)$$"


class EquationOnKeyTerms(unittest.TestCase):
    def _cards(self):
        return [
            {"card_type": "formula", "title": "F", "points": [_EQ, "A is the event."]},
            {"card_type": "definition", "title": "Key Components",
             "points": ["P(A): probability of A.", "P(B_i): partition probability."]},
        ]

    def test_equation_is_first_point_of_key_terms_card(self):
        out = _prepend_equation_to_key_terms(self._cards())
        defn = next(c for c in out if c["card_type"] == "definition")
        self.assertEqual(defn["points"][0], _EQ)                 # equation first, alone
        self.assertEqual(defn["points"][1], "P(A): probability of A.")
        self.assertEqual(defn.get("references"), [_EQ])

    def test_not_duplicated_when_already_leads_with_math(self):
        cards = [
            {"card_type": "formula", "points": [_EQ]},
            {"card_type": "definition", "points": [_EQ, "P(A): ..."]},   # already leads with the equation
        ]
        out = _prepend_equation_to_key_terms(cards)
        defn = next(c for c in out if c["card_type"] == "definition")
        self.assertEqual(defn["points"].count(_EQ), 1)

    def test_no_equation_is_noop(self):
        cards = [{"card_type": "definition", "points": ["Event: an outcome."]}]
        self.assertEqual(_prepend_equation_to_key_terms(cards)[0]["points"], ["Event: an outcome."])

    def test_references_carried_through_conversion(self):
        legacy = _lean_card_to_legacy({"card_type": "definition", "points": [_EQ, "P(A): ..."],
                                       "references": [_EQ]}, 0, [])
        self.assertEqual(legacy["references"], [_EQ])


if __name__ == "__main__":
    unittest.main()
