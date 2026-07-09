"""LaTeX-safe LLM JSON decode (_loads_llm_json / _repair_latex_escapes).

The model emits LaTeX with single backslashes inside JSON strings; json.loads either silently corrupts them
(\\frac → form-feed + "rac") or raises (\\alpha). The repair doubles a lone LaTeX backslash before decoding
without touching real escapes. Fully offline.
Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_llm_json_latex
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.llm_client import _loads_llm_json, _repair_latex_escapes


class LatexSafeJsonDecode(unittest.TestCase):
    def test_frac_survives_as_literal_backslash(self):
        # the exact observed bug: "\frac" (single backslash) → form-feed + "rac"
        out = _loads_llm_json(r'{"x": "Compute \frac{(b/2)^2}{a}"}')
        self.assertEqual(out["x"], r"Compute \frac{(b/2)^2}{a}")
        self.assertNotIn("\x0c", out["x"])       # no form-feed control char leaked

    def test_ambiguous_commands_repaired(self):
        # \n \t \r \b -initial commands (would corrupt to whitespace) are repaired when a letter follows
        for cmd in (r"\theta", r"\nabla", r"\times", r"\right", r"\begin", r"\beta"):
            out = _loads_llm_json('{"x": "' + cmd + '"}')
            self.assertEqual(out["x"], cmd)

    def test_invalid_escapes_repaired_not_raised(self):
        # \a \s \c \D … are INVALID JSON escapes → plain json.loads raises; repair keeps the backslash
        for cmd in (r"\alpha", r"\sqrt", r"\cdot", r"\Delta", r"\pi", r"\le"):
            out = _loads_llm_json('{"x": "' + cmd + '"}')
            self.assertEqual(out["x"], cmd)

    def test_unicode_escape_preserved(self):
        self.assertEqual(_loads_llm_json(r'{"x": "café"}')["x"], "café")

    def test_idempotent_on_already_escaped(self):
        # a correctly double-escaped backslash must not be doubled again
        self.assertEqual(_loads_llm_json(r'{"x": "\\frac"}')["x"], r"\frac")
        self.assertEqual(_repair_latex_escapes(r'{"x": "\\frac"}'), r'{"x": "\\frac"}')

    def test_genuine_whitespace_escape_preserved(self):
        # a real newline escape (\n not followed by a letter) stays a newline
        out = _loads_llm_json('{"x": "line1\\n line2"}')
        self.assertEqual(out["x"], "line1\n line2")

    def test_plain_json_unaffected(self):
        self.assertEqual(_loads_llm_json('{"a": 1, "b": [true, null, "x"]}'),
                         {"a": 1, "b": [True, None, "x"]})


if __name__ == "__main__":
    unittest.main()
