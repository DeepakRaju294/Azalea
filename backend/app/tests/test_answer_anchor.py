"""Tier-2 coverage ladder (§3): the independent answer anchor verifies the FINAL answer of an unsupported
computational topic — agree -> answer_anchored, disagree -> guided_fallback (downgrade), no oracle ->
model_only. The oracle is injectable, so this is exercised deterministically without a network call."""
import unittest

from app.services.examples import answer_anchor as aa
from app.services.examples.answer_anchor import (VERIFICATION_ANSWER_ANCHORED, VERIFICATION_GUIDED,
                                                 VERIFICATION_MODEL_ONLY, anchor_final_answer,
                                                 set_answer_oracle)


class AnswerAnchor(unittest.TestCase):
    def setUp(self):
        self._orig = aa._oracle

    def tearDown(self):
        set_answer_oracle(self._orig)

    def test_agreement_anchors_the_answer(self):
        set_answer_oracle(lambda topic, problem: "42")
        level, expected, agree = anchor_final_answer({}, "6 * 7", "42")
        self.assertEqual(level, VERIFICATION_ANSWER_ANCHORED)
        self.assertTrue(agree)

    def test_numeric_match_ignores_formatting(self):
        set_answer_oracle(lambda topic, problem: "the answer is 42")
        level, _, agree = anchor_final_answer({}, "6 * 7", "x = 42")
        self.assertEqual(level, VERIFICATION_ANSWER_ANCHORED)   # compared by numeric value
        self.assertTrue(agree)

    def test_disagreement_downgrades_to_guided(self):
        set_answer_oracle(lambda topic, problem: "41")
        level, expected, agree = anchor_final_answer({}, "6 * 7", "42")
        self.assertEqual(level, VERIFICATION_GUIDED)            # never ship a wrong answer as verified
        self.assertFalse(agree)
        self.assertEqual(expected, "41")

    def test_no_oracle_is_model_only(self):
        set_answer_oracle(lambda topic, problem: None)
        level, expected, agree = anchor_final_answer({}, "6 * 7", "42")
        self.assertEqual(level, VERIFICATION_MODEL_ONLY)
        self.assertIsNone(agree)

    def test_string_answer_match(self):
        set_answer_oracle(lambda topic, problem: "True")
        level, _, agree = anchor_final_answer({}, "is 7 prime?", "true")
        self.assertEqual(level, VERIFICATION_ANSWER_ANCHORED)
        self.assertTrue(agree)

    def test_display_rounding_still_agrees(self):
        set_answer_oracle(lambda topic, problem: "0.307692")   # exact
        _, _, agree = anchor_final_answer({}, "bayes", "0.31")  # example shows 2-dp
        self.assertTrue(agree)                                  # rounding is not a mismatch

    def test_percent_vs_fraction_agrees(self):
        set_answer_oracle(lambda topic, problem: "0.0833")
        _, _, agree = anchor_final_answer({}, "bayes", "8.33%")
        self.assertTrue(agree)                                  # same quantity, different unit convention


class MathEvalOracle(unittest.TestCase):
    def test_extracts_then_evaluates_deterministically(self):
        # the injected LLM only TRANSLATES to an expression; the arithmetic is done deterministically here.
        got = aa.math_eval_oracle({}, "posterior with P(D)=0.1, sens 0.9, fpr 0.2",
                                  extract_fn=lambda p: "0.9*0.1 / (0.9*0.1 + 0.2*0.9)")
        self.assertAlmostEqual(float(got), 0.333333, places=5)   # 0.09 / 0.27

    def test_unreducible_problem_defers(self):
        # extract yields nothing and (offline dummy key) the LLM fallback is unavailable -> None (no downgrade)
        self.assertIsNone(aa.math_eval_oracle({}, "explain the intuition", extract_fn=lambda p: ""))


if __name__ == "__main__":
    unittest.main()
