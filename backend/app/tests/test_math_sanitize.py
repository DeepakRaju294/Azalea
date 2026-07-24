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

    def test_doubled_open_delimiter_before_a_wrapped_atom_is_collapsed(self):
        # Live regression (Line Integrals card): the model wrote ONE unbalanced stray "\(" that never got a
        # matching "\)" anywhere in the string (a truncated attempt to delimit the whole equation).
        # _wrap_bare_latex, unable to tell a broken delimiter from ordinary text, then wrapped the bare
        # \int_C immediately following it, producing "Written as \(\(\int_C\) F \cdot dr = ...".
        s = r"Written as \(\int_C F \cdot dr = \int_S (\nabla \times F) \cdot dS where C is the boundary."
        out = _sanitize_math_in_text(s)
        self.assertNotIn(r"\(\(", out)

    def test_doubled_close_delimiter_is_collapsed(self):
        out = _sanitize_math_in_text(r"the result \(x = y\)\) follows")
        self.assertNotIn(r"\)\)", out)

    def test_backslash_less_textbf_is_stripped(self):
        # Live regression (Divergence Theorem card): "\(\nabla\) \(\cdot\) textbf{F}" — nabla and cdot were
        # correctly escaped but textbf{F} was missing its leading backslash, so the old backslash-required
        # pattern let it sail through as literal "textbf{F}" text.
        out = _sanitize_math_in_text(r"div textbf{F} and textbf{S} \(\cdot\) dS")
        self.assertNotIn("textbf", out)
        self.assertIn("F", out)
        self.assertIn("S", out)

    def test_backslash_less_command_mid_word_is_not_falsely_matched(self):
        s = "the subtext{ignore this} stays as prose"
        self.assertEqual(_sanitize_math_in_text(s), s)

    def test_ordinary_word_text_without_braces_is_untouched(self):
        s = "read the text explaining the theorem"
        self.assertEqual(_sanitize_math_in_text(s), s)

    def test_applies_across_card_points(self):
        cards = [{"points": [r"\text{I} = \frac{\text{V}}{\text{R}}", "plain bullet", r"$$x = y$$"]}]
        _sanitize_card_math(cards)
        self.assertEqual(cards[0]["points"][0], r"\(I = \frac{V}{R}\)")
        self.assertEqual(cards[0]["points"][1], "plain bullet")
        self.assertEqual(cards[0]["points"][2], r"$$x = y$$")


class SanitizeMathDecisionTrace(unittest.TestCase):
    """A repair that actually changes text is recorded to the decision trace (with topic given) — the
    doubled-escape and stray-linebreak bugs both went undiagnosed this session precisely because nothing
    recorded that the sanitizer had touched the text at all."""

    def test_a_repair_is_recorded_with_its_fix_category(self):
        topic = {"title": "Ohm's Law"}
        cards = [{"points": [r"\text{I} = \frac{\text{V}}{\text{R}}"]}]
        _sanitize_card_math(cards, topic)
        trace = topic["decomposition_metadata"]["decision_trace"]
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]["stage"], "lesson.math_sanitized")
        self.assertEqual(trace[0]["detail"]["fix_counts"], {"unsupported_text_command": 1})

    def test_multiple_bullets_are_aggregated_into_one_entry(self):
        topic = {"title": "Stokes' Theorem"}
        cards = [{"points": [r"\\(\int\)_S \textbf{F}", "plain bullet", r"\frac{V}{R}"]}]
        _sanitize_card_math(cards, topic)
        trace = topic["decomposition_metadata"]["decision_trace"]
        self.assertEqual(len(trace), 1)                    # one entry per call, not one per bullet
        counts = trace[0]["detail"]["fix_counts"]
        self.assertEqual(sum(counts.values()), 2)           # only the 2 changed bullets counted

    def test_clean_text_records_nothing(self):
        topic = {"title": "Ohm's Law"}
        cards = [{"points": ["plain bullet", r"$$x = y$$"]}]
        _sanitize_card_math(cards, topic)
        self.assertNotIn("decomposition_metadata", topic)

    def test_no_topic_given_skips_recording_without_raising(self):
        cards = [{"points": [r"\text{I}"]}]
        _sanitize_card_math(cards)   # topic omitted — must not raise
        self.assertEqual(cards[0]["points"][0], "I")


if __name__ == "__main__":
    unittest.main()
