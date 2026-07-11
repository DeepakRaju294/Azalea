"""LLM-authored card math must render: strip unsupported \\text{}, delimit bare \\frac/\\sqrt/greek, and never
touch already-grounded ($$ / \\() content."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _sanitize_card_math, _sanitize_math_in_text


class SanitizeMath(unittest.TestCase):
    def test_text_command_is_stripped_and_fraction_delimited(self):
        out = _sanitize_math_in_text(r"Apply Ohm's Law formula \text{I} = \frac{\text{V}}{\text{R}}")
        self.assertEqual(out, r"Apply Ohm's Law formula \(I = \frac{V}{R}\)")
        self.assertNotIn(r"\text", out)

    def test_text_only_bullet_is_stripped(self):
        out = _sanitize_math_in_text(r"resistance (\text{R}) and current (\text{I})")
        self.assertEqual(out, "resistance (R) and current (I)")

    def test_bare_fraction_without_lhs_is_wrapped(self):
        self.assertEqual(_sanitize_math_in_text(r"\frac{V}{R}"), r"\(\frac{V}{R}\)")

    def test_bare_sqrt_is_wrapped(self):
        self.assertIn(r"\(c = \sqrt{a^2 + b^2}\)", _sanitize_math_in_text(r"then c = \sqrt{a^2 + b^2} follows"))

    def test_standalone_greek_is_wrapped(self):
        out = _sanitize_math_in_text(r"the mean \mu and deviation \sigma")
        self.assertEqual(out, r"the mean \(\mu\) and deviation \(\sigma\)")

    def test_grounded_dollar_math_is_untouched(self):
        s = r"$$P(A) = \sum_{i} P(A|B_i)P(B_i)$$"
        self.assertEqual(_sanitize_math_in_text(s), s)

    def test_grounded_paren_note_is_untouched(self):
        s = r"\(P(A|B_i)\): probability within partition."
        self.assertEqual(_sanitize_math_in_text(s), s)

    def test_plain_text_equation_is_untouched(self):
        s = "Ohm's law is written as V = IR, a product of current and resistance."
        self.assertEqual(_sanitize_math_in_text(s), s)

    def test_applies_across_card_points(self):
        cards = [{"points": [r"\text{I} = \frac{\text{V}}{\text{R}}", "plain bullet", r"$$x = y$$"]}]
        _sanitize_card_math(cards)
        self.assertEqual(cards[0]["points"][0], r"\(I = \frac{V}{R}\)")
        self.assertEqual(cards[0]["points"][1], "plain bullet")
        self.assertEqual(cards[0]["points"][2], r"$$x = y$$")


if __name__ == "__main__":
    unittest.main()
