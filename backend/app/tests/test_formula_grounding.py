"""Adapter-backed formula topics use the adapter's CANONICAL formula in the formula card, replacing the
free-prose one the lean LLM sometimes gets wrong (and so the derived takeaway is correct too)."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import (
    _ground_formula_card, _derive_key_takeaways, _dedupe_formula_from_prose, _is_bare_equation,
)


class _T:
    def __init__(self, title):
        self.title = title
        self.topic_type = "math_formula_method"
        self.course_type = "math_formula_method"


def _wrong_formula_cards(title, wrong):
    return [
        {"blueprint_key": "background", "points": [f"{title} is a probability rule you will apply."]},
        {"blueprint_key": "formula_breakdown", "points": ["The formula:", wrong, "Where:", "P(A|B_i): a term"]},
        {"blueprint_key": "edge_case", "points": ["When a probability is zero the term drops out entirely."]},
    ]


class FormulaGrounding(unittest.TestCase):
    def test_total_probability_formula_is_corrected(self):
        cards = _wrong_formula_cards("Law of Total Probability", "P(A) + P(B) + ... = P(+)")
        self.assertTrue(_ground_formula_card(cards, _T("Law of Total Probability")))
        fc = next(c for c in cards if c["blueprint_key"] == "formula_breakdown")
        joined = " ".join(fc["points"])
        self.assertIn("$$", joined)                                  # isolated math, not buried in prose
        self.assertIn("\\sum_{i} P(A|B_i)P(B_i)", joined)            # canonical GENERAL n-partition form
        self.assertNotIn("P(+)", joined)                             # garbled free-prose gone
        tk = _derive_key_takeaways(cards)
        self.assertTrue(any("P(A|B_i)P(B_i)" in t for t in tk))      # takeaway carries the correct formula
        self.assertFalse(any("$$" in t for t in tk))                 # takeaways render clean, no raw delimiters
        self.assertNotIn("The formula:", fc["points"])               # no dangling colon lead-in bullet
        self.assertEqual(fc["points"][0], "$$P(A) = \\sum_{i} P(A|B_i)P(B_i)$$")   # equation is the first bullet
        # subscript symbols in the PROSE are wrapped in inline math so B_i renders as a subscript too.
        self.assertTrue(any("\\(B_i\\)" in p for p in fc["points"]))

    def test_bayes_formula_is_corrected(self):
        cards = _wrong_formula_cards("Bayes' Theorem", "P(A|B) = P(A) + P(B)")
        self.assertTrue(_ground_formula_card(cards, _T("Bayes' Theorem")))
        fc = next(c for c in cards if c["blueprint_key"] == "formula_breakdown")
        joined = " ".join(fc["points"])
        self.assertIn("$$P(A|B) = \\frac{P(B|A)P(A)}{P(B)}$$", joined)   # canonical form, standard A|B notation
        self.assertNotIn("P(A|B) = P(A) + P(B)", joined)                # wrong free-prose gone

    def test_bare_equation_is_deduped_from_background(self):
        # the equation lives in the formula card; a restatement in the background card is redundant.
        cards = [{"blueprint_key": "background",
                  "points": ["Bayes' theorem updates a prior using new evidence.",
                             "P(A|B) = \\frac{P(B|A) \\cdot P(A)}{P(B)}",
                             "Goal: find the probability of A given B."]},
                 {"blueprint_key": "formula_breakdown", "points": ["The formula:", "grounded"]}]
        _dedupe_formula_from_prose(cards)
        bg = next(c for c in cards if c["blueprint_key"] == "background")
        self.assertNotIn("P(A|B) = \\frac{P(B|A) \\cdot P(A)}{P(B)}", bg["points"])   # bare equation gone
        self.assertTrue(any("updates a prior" in p for p in bg["points"]))            # prose kept

    def test_prose_mentioning_a_symbol_is_kept(self):
        self.assertFalse(_is_bare_equation("The prior P(A) is your belief before seeing evidence."))
        self.assertTrue(_is_bare_equation("P(A|B) = \\frac{P(B|A)P(A)}{P(B)}"))

    def test_non_adapter_topic_is_untouched(self):
        cards = [{"blueprint_key": "formula_breakdown", "points": ["Z = made up"]}]
        self.assertFalse(_ground_formula_card(cards, _T("Zorble Coefficient")))
        self.assertEqual(cards[0]["points"], ["Z = made up"])

    def test_no_double_article_in_glossary(self):
        cards = _wrong_formula_cards("Law of Total Probability", "P(+) = wrong")
        _ground_formula_card(cards, _T("Law of Total Probability"))
        fc = next(c for c in cards if c["blueprint_key"] == "formula_breakdown")
        self.assertFalse(any("the the" in p for p in fc["points"]))


if __name__ == "__main__":
    unittest.main()
