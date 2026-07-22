"""Orphaned/malformed LaTeX-delimiter repair in lean card bullets (_repair_latex_delimiters).

The model sometimes leaves a lone backslash ("take \\ and add/subtract it") or a doubled inline-math delimiter
("\\)" instead of "\\)") in bullet text. The repair cleans both while preserving the "  - " subpoint indent and
leaving legitimate LaTeX untouched. Offline.
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_latex_delimiter_repair
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.lean_lesson_generator import _repair_latex_delimiters as fix


class LatexDelimiterRepair(unittest.TestCase):
    def test_orphaned_backslash_removed(self):
        self.assertEqual(fix("Calculate the constant: take \\ and add/subtract it:"),
                         "Calculate the constant: take and add/subtract it:")

    def test_doubled_delimiter_collapsed_and_indent_preserved(self):
        # the "  - " subpoint indent (nesting convention) MUST survive
        self.assertEqual(fix("  - \\((b/2)^2\\\\)"), "  - \\((b/2)^2\\)")

    def test_legit_inline_math_untouched(self):
        self.assertEqual(fix("Use \\(x^2\\) here"), "Use \\(x^2\\) here")

    def test_legit_command_untouched(self):
        self.assertEqual(fix("Half is \\frac{b}{2}"), "Half is \\frac{b}{2}")

    def test_no_backslash_is_noop(self):
        self.assertEqual(fix("plain bullet, no slashes"), "plain bullet, no slashes")
        self.assertEqual(fix("  - a normal subpoint"), "  - a normal subpoint")

    def test_trailing_orphan_backslash(self):
        self.assertEqual(fix("ends with a stray slash \\"), "ends with a stray slash")

    def test_unclosed_inline_math_with_trailing_linebreak_gets_closed(self):
        # live: a Stokes' theorem bullet opened "\(" and ended with a bare "\\" (LaTeX line-break) with no "\)"
        # anywhere — KaTeX never terminates the span. Strip the noise, close the delimiter that was left open.
        self.assertEqual(
            fix(r"  - \(\int_C \mathbf{F} \cdot d\mathbf{r} = \int_S (\nabla \times \mathbf{F}) \cdot d\mathbf{S}\\"),
            r"  - \(\int_C \mathbf{F} \cdot d\mathbf{r} = \int_S (\nabla \times \mathbf{F}) \cdot d\mathbf{S}\)")

    def test_doubled_backslash_before_command_collapsed(self):
        # live: "\\\\ int_C" (a doubled backslash + stray space in front of a bare command name) instead of the
        # intended "\int_C" — no legitimate bullet prose contains a literal doubled backslash.
        self.assertEqual(fix(r"  - \\ int_C F \cdot dr"), r"  - \int_C F \cdot dr")
        self.assertEqual(fix(r"  - \\ nabla \times F"), r"  - \nabla \times F")

    def test_balanced_trailing_linebreak_is_a_noop(self):
        # a bullet that's already properly closed must not gain a spurious extra "\)"
        self.assertEqual(fix(r"  - \(x^2\)"), r"  - \(x^2\)")


if __name__ == "__main__":
    unittest.main()
