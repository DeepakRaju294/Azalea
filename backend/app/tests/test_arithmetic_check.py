"""Deterministic arithmetic-consistency checker — regressions from the real broken probability examples."""
import unittest

from app.services.examples.arithmetic_check import check_arithmetic_consistency as chk


class ArithmeticCheck(unittest.TestCase):
    def test_correct_example_is_clean(self):
        cards = [
            {"points": ["P(A) = 0.6*0.5 + 0.3*0.4 + 0.2*0.1 // weighted contributions",
                        "P(A) = 0.3 + 0.12 + 0.02", "P(A) = 0.44"]},
            {"points": ["Result: The total probability P(A) is 0.44."]},
        ]
        self.assertEqual(chk(cards), [])

    def test_fraction_slip_is_caught(self):
        # the real 19:49 Bayes bug: 1900/11700 = 19/117, NOT 19/95.
        cards = [{"points": ["P(Disease | Positive) = 1,900 / 11,700 = 19 / 95"]}]
        v = chk(cards)
        self.assertTrue(v, "expected a violation for 1900/11700 = 19/95")
        self.assertIn("does not hold", v[0])

    def test_self_contradicting_final_answer_is_caught(self):
        # the real 20:02 Total-Probability bug: Step 4 computes 0.68 but declares P(A) = 0.88.
        cards = [
            {"points": ["P(A) = P(B and A) + P(C and A) + P(B and C)", "P(A) = 0.48 + 0.2 + 0.2 = 0.88"]},
            {"points": ["Verify: P(A) = P(B and A) + P(C and A)", "P(A) = 0.48 + 0.2 = 0.68"]},
        ]
        v = chk(cards)
        self.assertTrue(v, "expected a violation for P(A) bound to both 0.88 and 0.68")
        self.assertTrue(any("conflicting values" in x for x in v))

    def test_intermediate_arithmetic_error_is_caught(self):
        cards = [{"points": ["P(pos) = 0.9 * 0.01 + 0.1 * 0.99 = 0.009 + 0.099 = 0.76"]}]  # really 0.108
        self.assertTrue(chk(cards))

    def test_prose_without_equations_is_clean(self):
        cards = [{"points": ["Bayes' Theorem updates a prior with evidence.", "Use it in medical testing."]}]
        self.assertEqual(chk(cards), [])


if __name__ == "__main__":
    unittest.main()
