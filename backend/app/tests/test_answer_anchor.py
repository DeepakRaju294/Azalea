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


if __name__ == "__main__":
    unittest.main()
