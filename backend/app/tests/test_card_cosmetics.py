"""Final deterministic cosmetic sweep (_polish_card_cosmetics): phantom 'this diagram' body refs when no
visual, code-style // comments in non-coding worked examples, numbered-list point prefixes, a broken
'the formula is —' purpose lead-in, and a stale learning_goal on an adapter-grounded edge card."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import (
    _fix_partial_derivative_notation, _polish_card_cosmetics, _repair_latex_delimiters, _wrap_bare_latex)


class LatexDelimiterRepair(unittest.TestCase):
    def test_dollar_wrapped_inline_math_collapsed(self):
        # Live bug: "the mean ($\(\mu\)$)" — $ wrapping \(…\) renders as literal dollar signs + broken math.
        self.assertEqual(_repair_latex_delimiters("the mean ($\\(\\mu\\)$)"), "the mean (\\(\\mu\\))")
        self.assertEqual(_repair_latex_delimiters("std dev ($\\(\\sigma\\)$)"), "std dev (\\(\\sigma\\))")

    def test_plain_dollar_math_untouched(self):
        self.assertEqual(_repair_latex_delimiters("the value $x$ here"), "the value $x$ here")

    def test_legit_inline_math_untouched(self):
        self.assertEqual(_repair_latex_delimiters("above (\\(z>0\\)) or below"), "above (\\(z>0\\)) or below")


class BareLatexWrapping(unittest.TestCase):
    def test_bare_frac_gets_wrapped(self):
        # Live bug: "z = \frac{x - mean}{\text{std dev}} — valid…" rendered as literal LaTeX source.
        out = _wrap_bare_latex("z = \\frac{x - mean}{\\text{std dev}} — valid")
        self.assertEqual(out, "z = \\(\\frac{x - mean}{\\text{std dev}}\\) — valid")

    def test_already_delimited_frac_untouched(self):
        s = "$$z = \\frac{x - \\mu}{\\sigma}$$"
        self.assertEqual(_wrap_bare_latex(s), s)
        s2 = "here \\(\\frac{a}{b}\\) done"
        self.assertEqual(_wrap_bare_latex(s2), s2)

    def test_no_latex_command_is_noop(self):
        self.assertEqual(_wrap_bare_latex("just some prose with a \\ stray"), "just some prose with a \\ stray")

    def test_bare_vector_calculus_operators_get_wrapped(self):
        # live: "\(\nabla\) \times \mathbf{F}" — nabla alone was delimited but "\times" right next to it stayed
        # bare and rendered as literal source, since none of these operators were in the command list.
        self.assertEqual(_wrap_bare_latex("\\(\\nabla\\) \\times \\mathbf{F}"),
                         "\\(\\nabla\\) \\(\\times\\) \\mathbf{F}")
        self.assertEqual(_wrap_bare_latex("A \\cdot B"), "A \\(\\cdot\\) B")

    def test_subscripted_bare_command_still_wrapped(self):
        # \b does not fire between "int" and its subscript "_C" (both \w) — a naive \b boundary would silently
        # skip every subscripted command, which is the normal way integrals over a named curve are written.
        # Live rendering bug: the subscript must stay INSIDE the delimiter with its command — the frontend
        # only positions \int's sub/sup when they're captured in the SAME \(...\) span; a stray "_C" left
        # outside renders as literal text glued onto plain prose next to the (oversized) integral glyph.
        self.assertEqual(_wrap_bare_latex("\\int_C \\mathbf{F} \\cdot d\\mathbf{r}"),
                         "\\(\\int_C\\) \\mathbf{F} \\(\\cdot\\) d\\mathbf{r}")

    def test_integral_with_superscript_and_subscript_stays_together(self):
        self.assertEqual(_wrap_bare_latex("\\int_a^b f(x) dx"), "\\(\\int_a^b\\) f(x) dx")

    def test_sum_with_braced_bounds_stays_together(self):
        self.assertEqual(_wrap_bare_latex("\\sum_{i=1}^{n} i"), "\\(\\sum_{i=1}^{n}\\) i")


from app.services.lean_lesson_generator import _polish_card_cosmetics


class _Topic:
    def __init__(self, ctype="math_formula_method"):
        self.course_type = self.topic_type = ctype


def _run(cards, topic=None, grounded_edge=False):
    _polish_card_cosmetics(cards, topic or _Topic(), grounded_edge=grounded_edge)
    return cards


class PhantomVisual(unittest.TestCase):
    def test_diagram_body_dropped_when_no_visual(self):
        c = [{"card_type": "purpose_context",
              "body": ["This node-link diagram illustrates the structure of combinatorial analysis."],
              "points": ["Real content."]}]
        _run(c)
        self.assertIsNone(c[0]["body"])
        self.assertEqual(c[0]["points"], ["Real content."])

    def test_kept_when_a_visual_is_present(self):
        c = [{"card_type": "background", "visual_type": "node_link_diagram",
              "body": ["This diagram shows the graph."], "points": ["p"]}]
        _run(c)
        self.assertEqual(c[0]["body"], ["This diagram shows the graph."])

    def test_ordinary_body_untouched(self):
        c = [{"card_type": "purpose_context", "body": ["Combinatorics counts arrangements."], "points": ["p"]}]
        _run(c)
        self.assertEqual(c[0]["body"], ["Combinatorics counts arrangements."])


class CodeCommentsInMathWork(unittest.TestCase):
    def test_slash_comment_becomes_prose_annotation(self):
        c = [{"card_type": "worked_example",
              "points": ["Work:", "  - Total letters = 6 // the word BANANA has 6 letters"]}]
        _run(c)
        self.assertEqual(c[0]["points"][1], "  - Total letters = 6 — the word BANANA has 6 letters")

    def test_math_topic_strips_comments_even_with_code_lines(self):
        # gen_foundation spuriously sets code_lines on a MATH worked example — the topic type governs, so // is
        # still stripped (it's code-leakage, not real code).
        c = [{"card_type": "worked_example", "code_lines": [[1, 3]],
              "points": ["  - factorial_n = 6! = 720 // calculating factorial of n"]}]
        _run(c, topic=_Topic("problem_solving_application"))
        self.assertEqual(c[0]["points"][0], "  - factorial_n = 6! = 720 — calculating factorial of n")

    def test_coding_topic_keeps_comments(self):
        c = [{"card_type": "worked_example", "points": ["  - x = 0 // initialize"]}]
        _run(c, topic=_Topic("coding_implementation"))
        self.assertEqual(c[0]["points"][0], "  - x = 0 // initialize")


class NumberedListPrefix(unittest.TestCase):
    def test_short_label_prefix_stripped(self):
        c = [{"card_type": "purpose_context", "points": ["1. Permutations", "  - Order matters",
                                                         "2. Combinations", "  - Order does not matter"]}]
        _run(c)
        self.assertEqual(c[0]["points"][0], "Permutations")
        self.assertEqual(c[0]["points"][2], "Combinations")

    def test_numbered_step_sentence_untouched(self):
        c = [{"card_type": "method_process", "points": ["1. Substitute the values into the formula"]}]
        _run(c)
        self.assertEqual(c[0]["points"][0], "1. Substitute the values into the formula")

    def test_decimal_not_stripped(self):
        c = [{"card_type": "purpose_context", "points": ["3.14 is pi"]}]
        _run(c)
        self.assertEqual(c[0]["points"][0], "3.14 is pi")


class DanglingFormulaLeadIn(unittest.TestCase):
    def test_broken_formula_lead_in_dropped(self):
        c = [{"card_type": "purpose_context",
              "points": ["Permutations arrange items.",
                         "The formula is — calculates arrangements of r from n items:"]}]
        _run(c)
        self.assertEqual(c[0]["points"], ["Permutations arrange items."])

    def test_clean_formula_lead_in_with_math_kept(self):
        c = [{"card_type": "purpose_context", "points": ["The formula is P(n,r) = n!/(n-r)!"]}]
        _run(c)
        self.assertEqual(len(c[0]["points"]), 1)

    def test_formula_mention_without_dash_kept(self):
        c = [{"card_type": "purpose_context", "points": ["Understanding the formula helps solve problems."]}]
        _run(c)
        self.assertEqual(len(c[0]["points"]), 1)


class DoubledColonPunctuation(unittest.TestCase):
    def test_doubled_colon_collapsed(self):
        c = [{"card_type": "formula_breakdown", "points": ["Formula for Stokes' Theorem: :"]}]
        _run(c)
        self.assertEqual(c[0]["points"][0], "Formula for Stokes' Theorem:")

    def test_colon_period_collapsed(self):
        c = [{"card_type": "formula_breakdown", "points": ["Where:."]}]
        _run(c)
        self.assertEqual(c[0]["points"][0], "Where:")

    def test_ratio_and_decimal_time_untouched(self):
        c = [{"card_type": "background", "points": ["The odds are 2:1.", "Class starts at 3:00."]}]
        _run(c)
        self.assertEqual(c[0]["points"], ["The odds are 2:1.", "Class starts at 3:00."])


class PartialDerivativeNotation(unittest.TestCase):
    """Live bug (Divergence Theorem topic, no adapter to verify it): the LLM wrote ordinary total-
    derivative notation (d/dx) for divergence/curl/gradient, which are only ever defined via partials —
    mathematically wrong notation for a first-time learner. Fixed with a tightly-scoped rewrite: only
    inside a card that names one of those operators, so a real total derivative elsewhere is untouched."""

    def test_divergence_formula_rewritten_to_partial(self):
        c = [{"card_type": "process", "points": [
            r"State the divergence, calculated as div(F) = \(\frac{dF_1}{dx}\) + \(\frac{dF_2}{dy}\)."]}]
        _fix_partial_derivative_notation(c)
        self.assertEqual(
            c[0]["points"][0],
            r"State the divergence, calculated as div(F) = \(\frac{\partial F_1}{\partial x}\) + "
            r"\(\frac{\partial F_2}{\partial y}\).")

    def test_parenthesized_numerator_rewritten(self):
        c = [{"card_type": "practice", "points": [
            r"Calculate the divergence: \( div F = \frac{d( y^2)}{dx} + \frac{d(2xy)}{dy} \)"]}]
        _fix_partial_derivative_notation(c)
        self.assertIn(r"\frac{\partial y^2}{\partial x}", c[0]["points"][0])
        self.assertIn(r"\frac{\partial 2xy}{\partial y}", c[0]["points"][0])

    def test_curl_and_gradient_also_trigger(self):
        for word in ("curl", "gradient", "\\nabla \\times", "\\nabla \\cdot"):
            with self.subTest(word=word):
                c = [{"card_type": "process",
                     "points": [f"Using {word}: \\(\\frac{{dF}}{{dx}}\\)"]}]
                _fix_partial_derivative_notation(c)
                self.assertIn(r"\partial", c[0]["points"][0])

    def test_unrelated_total_derivative_untouched(self):
        # A curve parameterization's dr/dt IS a genuine total derivative — no divergence/curl/gradient
        # mention nearby, so the rewrite must never fire.
        c = [{"card_type": "process", "points": [
            r"Calculate the differential element: \(dr = \frac{dr}{dt} dt\)"]}]
        _fix_partial_derivative_notation(c)
        self.assertEqual(c[0]["points"][0], r"Calculate the differential element: \(dr = \frac{dr}{dt} dt\)")


class GroundedEdgeLearningGoal(unittest.TestCase):
    def test_stale_learning_goal_dropped_on_grounded_edge(self):
        c = [{"card_type": "edge_case", "learning_goal": "Understand what happens when r is zero.",
              "points": [r"Requires \(0 \leq r \leq n\)."]}]
        _run(c, grounded_edge=True)
        self.assertNotIn("learning_goal", c[0])

    def test_kept_when_edge_not_grounded(self):
        c = [{"card_type": "edge_case", "learning_goal": "goal", "points": ["p"]}]
        _run(c, grounded_edge=False)
        self.assertEqual(c[0]["learning_goal"], "goal")


if __name__ == "__main__":
    unittest.main()
