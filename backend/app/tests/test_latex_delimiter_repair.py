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


if __name__ == "__main__":
    unittest.main()
