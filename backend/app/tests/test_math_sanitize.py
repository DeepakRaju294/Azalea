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

    def test_function_call_lhs_wraps_whole_equation(self):
        # Regression (3 consecutive live paths): the LHS class couldn't match the comma in "C(n, r)", so the
        # wrap started MID-CALL and produced the malformed "C(n, \(r) = ...\)".
        out = _sanitize_math_in_text(r"C(n, r) = \frac{n!}{r!(n-r)!} handles the calculation")
        self.assertEqual(out, r"\(C(n, r) = \frac{n!}{r!(n-r)!}\) handles the calculation")

    def test_malformed_nested_inline_is_healed(self):
        # Already-malformed text (stored lessons / model-authored) is stripped and re-wrapped cleanly.
        out = _sanitize_math_in_text(r"C(n, \(r) = \frac{n!}{r!(n-r)!}\) handles the calculation")
        self.assertEqual(out, r"\(C(n, r) = \frac{n!}{r!(n-r)!}\) handles the calculation")

    def test_conditional_probability_lhs_still_wraps(self):
        out = _sanitize_math_in_text(r"P(A|B) = \frac{P(B|A)P(A)}{P(B)}")
        self.assertEqual(out, r"\(P(A|B) = \frac{P(B|A)P(A)}{P(B)}\)")

    def test_doubled_backslash_before_delimiter_is_collapsed(self):
        # Live regression (Stokes' theorem "formula" card): the model over-escaped the OPENING delimiter
        # ("\\(" instead of "\(") while the rest of the equation was correctly single-escaped. The old
        # "already delimited, leave alone" check ("\\(" in s) was fooled — "\\(" (two backslashes) CONTAINS
        # the substring "\(" (one backslash) — so this slipped through unrepaired and rendered as literal
        # backslash-garbage instead of a valid delimiter.
        s = r"\\(\int\)_S (\(\nabla\) \(\times\) \textbf{F}) \bullet d\textbf{S} = \\(\int\)_{C}"
        out = _sanitize_math_in_text(s)
        self.assertNotIn("\\\\(", out)   # no doubled opening delimiter survives
        self.assertNotIn("\\\\)", out)   # no doubled closing delimiter survives
        self.assertNotIn("\\textbf", out)   # unsupported command stripped (bare content kept)
        self.assertEqual(out, r"\(\int\)_S (\(\nabla\) \(\times\) F) \bullet dS = \(\int\)_{C}")

    def test_doubled_bracket_delimiter_is_collapsed(self):
        out = _sanitize_math_in_text(r"a display block: \\[x = y\\]")
        self.assertEqual(out, r"a display block: \[x = y\]")

    def test_stray_latex_linebreak_is_stripped_even_alongside_valid_delimiters(self):
        # Live regression (Divergence Theorem card): the model wrote a bare "\\" (LaTeX's own line-break
        # command, meaningless in a flat prose bullet) right before an otherwise-correctly-delimited
        # equation. The old "already delimited, leave alone" short-circuit let the stray "\\" survive
        # because the SAME string also contained valid "\(...\)" spans elsewhere.
        s = r"Mathematically \\ \(\iint\)_{S} \mathbf{F} \(\cdot\) d\mathbf{S} = \(\iiint\)_{V} dV"
        out = _sanitize_math_in_text(s)
        self.assertNotIn("\\\\", out)
        self.assertEqual(out, r"Mathematically \(\iint\)_{S} F \(\cdot\) dS = \(\iiint\)_{V} dV")

    def test_mathbf_outside_a_delimiter_is_stripped_even_alongside_valid_delimiters(self):
        # \mathbf{}/\textbf{} are just as unsupported as \text{}, unconditionally — a bare \mathbf{F}
        # sitting OUTSIDE any \(...\) span (or even one nested inside a valid span) must not survive just
        # because the rest of the same string is already properly delimited.
        out = _sanitize_math_in_text(r"the curl \(\nabla \times \mathbf{F}\) and the field \mathbf{F} itself")
        self.assertNotIn("\\mathbf", out)
        self.assertEqual(out, r"the curl \(\nabla \times F\) and the field F itself")

    def test_applies_across_card_points(self):
        cards = [{"points": [r"\text{I} = \frac{\text{V}}{\text{R}}", "plain bullet", r"$$x = y$$"]}]
        _sanitize_card_math(cards)
        self.assertEqual(cards[0]["points"][0], r"\(I = \frac{V}{R}\)")
        self.assertEqual(cards[0]["points"][1], "plain bullet")
        self.assertEqual(cards[0]["points"][2], r"$$x = y$$")


if __name__ == "__main__":
    unittest.main()
