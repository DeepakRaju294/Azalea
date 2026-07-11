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

    def test_leadin_header_falls_through_to_its_payload(self):
        # regression: the edge-case header "When the prior probability, P(H), is zero:" was surfaced as a
        # truncated takeaway; the real claim lives in the sub-bullet beneath it.
        cards = [_card("background", ["Bayes' Theorem updates a prior probability using new evidence."]),
                 _card("edge_case", ["When the prior probability, P(H), is zero:",
                                     "  - The posterior probability P(H|E) is also zero, so the theorem cannot support that hypothesis."])]
        tk = _derive_key_takeaways(cards)
        self.assertFalse(any(t.rstrip().endswith("is zero") for t in tk))     # no dangling condition
        self.assertTrue(any("posterior probability P(H|E) is also zero" in t for t in tk))

    def test_complete_claim_ending_in_colon_is_kept(self):
        # regression: "Bayes' theorem calculates conditional probabilities:" is a complete claim (the colon
        # introduces a sub-bullet); it must survive as a takeaway, not be dropped as a lead-in header.
        cards = [_card("background", ["Bayes' theorem calculates conditional probabilities:",
                                      "  - Expressed as: P(A|B) = \\frac{P(B|A)P(A)}{P(B)}",
                                      "  - Here, P(A|B) is the posterior probability of A given B."]),
                 _card("formula_breakdown", ["$$P(A|B) = \\frac{P(B|A)P(A)}{P(B)}$$"]),
                 _card("edge_case", ["When P(B) = 0 the conditional probability is undefined."])]
        tk = _derive_key_takeaways(cards)
        self.assertTrue(any("Bayes' theorem calculates conditional probabilities" in t for t in tk))
        self.assertGreaterEqual(len(tk), 2)                          # not emptied out

    def test_process_step_imperatives_are_not_takeaways(self):
        # regression: "Identify the event and possible partitions" (a process step) surfaced as a takeaway.
        cards = [_card("background", ["The Law of Total Probability combines conditional probabilities over a partition."]),
                 _card("process", ["Identify the event and possible partitions",
                                   "State the conditional probability for each partition"]),
                 _card("edge_case", ["With a single partition the formula reduces to one conditional term."])]
        tk = _derive_key_takeaways(cards)
        self.assertFalse(any(t.lower().startswith(("identify", "state")) for t in tk))

    def test_formula_restatement_in_background_does_not_become_a_takeaway(self):
        # regression: a background card that restates the formula as prose ("P(A|B) = ... where ...,") produced
        # a run-on takeaway and stole it from the clean formula card. The formula card should own it; the
        # background should fall through to its real insight.
        cards = [_card("background", ["Bayes' Theorem states",
                                      "  - P(A|B) = \\frac{P(B|A)P(A)}{P(B)} where P(A|B) is the conditional probability of A given B,",
                                      "  - P(B|A) is the likelihood of event B given A,",
                                      "  - P(A) is the prior probability of event A,",
                                      "Key insight",
                                      "  - It allows updating probabilities based on new evidence."]),
                 _card("formula_breakdown", ["$$P(A|B) = \\frac{P(B|A)P(A)}{P(B)}$$"]),
                 _card("edge_case", ["When P(B) = 0 the conditional probability is undefined."])]
        tk = _derive_key_takeaways(cards)
        self.assertFalse(any(t.rstrip().endswith(",") for t in tk))       # no run-on/dangling comma
        self.assertTrue(any("updating probabilities based on new evidence" in t for t in tk))  # real insight
        self.assertTrue(any(t == "P(A|B) = (P(B|A)P(A))/(P(B))" for t in tk))   # clean formula from the card

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
