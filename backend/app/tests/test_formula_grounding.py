"""Adapter-backed formula topics use the adapter's CANONICAL formula in the formula card, replacing the
free-prose one the lean LLM sometimes gets wrong (and so the derived takeaway is correct too)."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import (
    _ground_formula_card, _ground_edge_case_card, _derive_key_takeaways, _dedupe_formula_from_prose,
    _is_bare_equation, _inject_grounded_cards,
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

    def test_bayes_edge_case_replaces_wrong_llm_claim(self):
        # the LLM's "P(A)=0 -> indeterminate" is wrong; grounding installs the correct boundary facts.
        cards = [{"blueprint_key": "edge_case",
                  "points": ["When P(A) = 0, Bayes' theorem gives indeterminate results."]}]
        self.assertTrue(_ground_edge_case_card(cards, _T("Bayes' Theorem")))
        joined = " ".join(cards[0]["points"])
        self.assertNotIn("indeterminate", joined.lower())            # wrong claim gone
        self.assertIn("P(B) = 0", joined)                            # undefined when the evidence is impossible
        self.assertIn("P(A|B) = 0", joined)                          # prior 0 -> posterior 0 (determinate)
        self.assertTrue(cards[0].get("_edge_case_grounded"))
        self.assertEqual(cards[0]["title"], "Edge Cases")            # narrow LLM title neutralized (2 cases)

    def test_total_probability_edge_case_is_grounded(self):
        cards = [{"blueprint_key": "edge_case", "points": ["maybe-wrong edge case"]}]
        self.assertTrue(_ground_edge_case_card(cards, _T("Law of Total Probability")))
        self.assertIn("P(B_i) = 0", " ".join(cards[0]["points"]))

    def test_grounded_cards_injected_when_mechanism_topic_has_none(self):
        # Ohm's law decomposed as science_mechanism emits no formula/edge card; inject the grounded ones.
        class M:
            def __init__(s): s.title = "Understanding Ohm's Law"; s.course_type = "science_mechanism"; s.topic_type = "science_mechanism"
        cards = [{"blueprint_key": "definition", "points": ["V, I, R defined"]},
                 {"blueprint_key": "method_process", "points": ["apply it"]},
                 {"blueprint_key": "quick_practice", "points": ["practice"]}]
        _inject_grounded_cards(cards, M(), have_formula=False, have_edge=False)
        kinds = [c.get("blueprint_key") for c in cards]
        self.assertIn("formula_breakdown", kinds)                # a formula card now exists
        self.assertIn("edge_case", kinds)
        fc = next(c for c in cards if c["blueprint_key"] == "formula_breakdown")
        self.assertTrue(fc["points"][0].startswith("$$") and "I = \\frac{V}{R}" in fc["points"][0])
        # placed after the definition, before the method
        self.assertLess(kinds.index("definition"), kinds.index("formula_breakdown"))
        self.assertLess(kinds.index("formula_breakdown"), kinds.index("method_process"))

    def test_injection_is_noop_when_already_grounded_or_no_adapter(self):
        class Z:
            def __init__(s): s.title = "Zorble Coefficient"; s.course_type = "science_mechanism"; s.topic_type = "science_mechanism"
        cards = [{"blueprint_key": "definition", "points": ["x"]}]
        _inject_grounded_cards(cards, Z(), have_formula=False, have_edge=False)   # no adapter
        self.assertEqual([c["blueprint_key"] for c in cards], ["definition"])

    def test_edge_case_grounding_is_noop_for_non_adapter(self):
        cards = [{"blueprint_key": "edge_case", "points": ["Zorble edge case."]}]
        self.assertFalse(_ground_edge_case_card(cards, _T("Zorble Coefficient")))
        self.assertEqual(cards[0]["points"], ["Zorble edge case."])

    def test_statistics_family_is_grounded(self):
        # grounding extends beyond probability: the statistics family is grounded too.
        for title in ("Standard Deviation", "Z-score", "Weighted Mean"):
            fc = [{"blueprint_key": "formula_breakdown", "points": ["The formula:", "WRONG"]},
                  {"blueprint_key": "edge_case", "points": ["x"]}]
            self.assertTrue(_ground_formula_card(fc, _T(title)), f"formula {title}")
            self.assertTrue(_ground_edge_case_card(fc, _T(title)), f"edge {title}")
            self.assertIn("$$", " ".join(fc[0]["points"]))

    def test_every_formula_spec_is_grounded(self):
        # uniformity invariant: EVERY formula adapter carries canonical_latex + edge_cases, so no formula
        # topic falls back to an LLM-written formula/edge card. A new FormulaSpec must add grounding.
        from app.services.examples.trace_adapters.families.formula_engine import FormulaSpec
        from app.services.examples.trace_adapters.families import formula_specs as FS
        specs = [v for v in vars(FS).values() if isinstance(v, FormulaSpec)]
        self.assertGreater(len(specs), 100)
        self.assertEqual([s.slug for s in specs if not s.canonical_latex], [])   # all have a formula
        self.assertEqual([s.slug for s in specs if not s.edge_cases], [])        # all have edge cases

    def test_physics_geometry_finance_chemistry_are_grounded(self):
        # grounding spans families: physics / geometry / finance / chemistry all ground with $$ math and edges.
        for title in ("Kinetic Energy", "Ohm law", "Compound Interest", "Pythagorean", "Density", "Ideal Gas"):
            fc = [{"blueprint_key": "formula_breakdown", "points": ["The formula:", "WRONG"]},
                  {"blueprint_key": "edge_case", "points": ["x"]}]
            self.assertTrue(_ground_formula_card(fc, _T(title)), f"formula {title}")
            self.assertTrue(_ground_edge_case_card(fc, _T(title)), f"edge {title}")
            self.assertTrue(fc[0]["points"][0].startswith("$$"), title)

    def test_greek_and_roots_render_plain_in_takeaways(self):
        cards = [{"blueprint_key": "background",
                  "points": ["Standard deviation measures how spread out a dataset is around its mean."]},
                 {"blueprint_key": "formula_breakdown", "points": ["The formula:", "WRONG"]}]
        _ground_formula_card(cards, _T("Standard Deviation"))
        tk = _derive_key_takeaways(cards)
        self.assertFalse(any("\\sigma" in t or "\\sqrt" in t or "\\frac" in t for t in tk))  # no raw LaTeX
        self.assertTrue(any("σ" in t and "√" in t for t in tk))                              # glyphs instead

    def test_no_double_article_in_glossary(self):
        cards = _wrong_formula_cards("Law of Total Probability", "P(+) = wrong")
        _ground_formula_card(cards, _T("Law of Total Probability"))
        fc = next(c for c in cards if c["blueprint_key"] == "formula_breakdown")
        self.assertFalse(any("the the" in p for p in fc["points"]))


if __name__ == "__main__":
    unittest.main()
