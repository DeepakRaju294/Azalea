"""Edge-case correctness — CARD_CONTENT_CHARTER_SPEC §6.4.

A legitimate boundary case is HANDLED by the method, not a failure of it. Two live errors motivated this:
x^2+4 "can't complete the square" (wrong — already a perfect square) and a zero prior "renders Bayes ineffective"
(wrong — yields a zero posterior). The deterministic corrector rewrites the false-failure framing; the EDGE
charter directive prescribes the correct framing. Offline.
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_edge_case_correctness
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _correct_edge_case_failure_framing as fix
from app.core.card_charters import SLOT_DIRECTIVES


class EdgeFailureFraming(unittest.TestCase):
    def test_completing_square_no_linear_term(self):
        self.assertEqual(fix("With x^2 + 4, the expression cannot complete the square."),
                         "With x^2 + 4, the expression is already a complete square.")

    def test_bayes_zero_prior(self):
        out = fix("A prior probability of zero renders Bayes' Theorem ineffective.")
        self.assertNotIn("ineffective", out)
        self.assertIn("does not prevent using", out)

    def test_does_not_apply_and_is_ineffective(self):
        self.assertIn("still applies", fix("When P(B_i) = 0, the law does not apply."))
        self.assertIn("still applies", fix("In this degenerate case the method is ineffective."))

    def test_legit_text_untouched(self):
        s = "The vertex form reveals the minimum point of the parabola."
        self.assertEqual(fix(s), s)

    def test_empty_is_noop(self):
        self.assertEqual(fix(""), "")

    def test_EDGE_directive_prescribes_correct_framing(self):
        d = SLOT_DIRECTIVES["EDGE"].include
        self.assertIn("HANDLED by the method", d)
        self.assertIn("NEVER", d)


if __name__ == "__main__":
    unittest.main()
