"""key_takeaways are derived from the finished lesson cards (the lean path used to leave them empty)."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _derive_key_takeaways, _estimate_minutes


def _card(bp, points):
    return {"blueprint_key": bp, "card_type": bp, "points": points}


class KeyTakeaways(unittest.TestCase):
    def _sample(self):
        return [
            _card("background", ["Bayes' Theorem states:", "Bayes' Theorem updates a prior probability using new evidence."]),
            _card("components_terms", ["P(A): The prior probability of event A occurring."]),
            _card("formula_breakdown", ["The formula is:", "P(A|B) = (P(B|A) * P(A)) / P(B)"]),
            _card("process", ["Identify the givens and the quantity to find — name each symbol."]),
            _card("edge_case", ["Edge Case: when P(A) = 0, the posterior P(A|B) is 0 regardless of the evidence."]),
        ]

    def test_derives_strong_takeaways(self):
        tk = _derive_key_takeaways(self._sample())
        self.assertTrue(tk)
        joined = " | ".join(tk)
        self.assertIn("P(A|B) = (P(B|A) * P(A)) / P(B)", joined)          # the formula
        self.assertTrue(any("updates a prior" in t for t in tk))          # background claim, not the lead-in
        self.assertTrue(any("posterior" in t for t in tk))               # edge case

    def test_drops_leadins_glossary_and_labels(self):
        tk = _derive_key_takeaways(self._sample())
        self.assertFalse(any(t.strip().endswith("states") for t in tk))  # no "Bayes' Theorem states"
        self.assertFalse(any(t.startswith("P(A):") for t in tk))         # no glossary entry
        self.assertFalse(any(t.lower().startswith("edge case") for t in tk))  # label stripped

    def test_explicit_summary_card_wins(self):
        cards = [_card("summary", ["The theorem inverts a conditional probability.",
                                   "Always compute the evidence P(B) first."]),
                 _card("background", ["Something else entirely here to ignore."])]
        tk = _derive_key_takeaways(cards)
        self.assertEqual(tk[0], "The theorem inverts a conditional probability.")

    def test_dedupes_repeated_formula(self):
        cards = [_card("background", ["P(A|B) = (P(B|A) * P(A)) / P(B) is the core relationship."]),
                 _card("formula_breakdown", ["P(A|B) = (P(B|A) * P(A)) / P(B)"]),
                 _card("edge_case", ["When P(B) = 0 the conditional probability is undefined."])]
        tk = _derive_key_takeaways(cards)
        self.assertEqual(len([t for t in tk if "P(B|A)" in t]), 1)   # formula appears once, not twice
        self.assertEqual(len(tk), 2)                                 # formula + edge case

    def test_intro_topic_gets_no_takeaways(self):
        tk = _derive_key_takeaways(self._sample(), topic_type="study_path_introduction")
        self.assertEqual(tk, [])   # an orientation intro has nothing to consolidate

    def test_single_weak_takeaway_is_suppressed(self):
        # only one usable claim -> not "key takeaways"; return [] rather than a hollow one-item list
        cards = [_card("background", ["This lesson introduces the idea at a high level and why it matters."])]
        self.assertEqual(_derive_key_takeaways(cards), [])


class EstimateMinutes(unittest.TestCase):
    def test_light_intro_is_a_few_minutes(self):
        intro = [_card(bp, ["x"]) for bp in ("background", "prerequisites", "components_terms", "roadmap")]
        self.assertEqual(_estimate_minutes(intro), 6)          # not the LLM's 30

    def test_worked_example_steps_are_cheap_practice_is_pricier(self):
        cards = ([_card(bp, ["x"]) for bp in ("background", "formula_breakdown", "process", "edge_case")]
                 + [_card("worked_example", ["x"]) for _ in range(5)]
                 + [_card("practice", ["x"])])
        # 4*1.5 + 5*0.75 + 1*3 = 6 + 3.75 + 3 = 12.75 -> 13
        self.assertEqual(_estimate_minutes(cards), 13)

    def test_floor(self):
        self.assertGreaterEqual(_estimate_minutes([_card("background", ["x"])]), 3)


if __name__ == "__main__":
    unittest.main()
