"""Generated code is the clean algorithm — no main/driver scaffolding.

A merge-sort answer should be `merge_sort` + `merge`, not a runnable script with an
`if __name__ == "__main__"` block or bare example/print calls. Asserted by behavior.

Run: python -m unittest app.tests.test_strip_driver_code
"""
from __future__ import annotations

import os
import sys
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")
for _name in ("dotenv", "openai"):
    if _name not in sys.modules:
        try:
            __import__(_name)
        except ImportError:
            _m = types.ModuleType(_name)
            if _name == "dotenv":
                _m.load_dotenv = lambda *a, **k: None
            else:
                _m.OpenAI = lambda *a, **k: object()
                for _e in ("APIError", "RateLimitError", "APITimeoutError", "APIConnectionError"):
                    setattr(_m, _e, type(_e, (Exception,), {}))
            sys.modules[_name] = _m

from app.services.lean_lesson_generator import _strip_driver_code

MERGE_SORT = '''def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    return merge(merge_sort(arr[:mid]), merge_sort(arr[mid:]))


def merge(left, right):
    return sorted(left + right)


if __name__ == "__main__":
    print(merge_sort([5, 2, 8, 1]))'''


class TestStripDriverCode(unittest.TestCase):
    def test_strips_main_guard_and_example_calls(self):
        out = _strip_driver_code(MERGE_SORT)
        self.assertNotIn("__main__", out)
        self.assertNotIn("print(", out)
        self.assertIn("def merge_sort", out)        # the two algorithm functions are kept
        self.assertIn("def merge(", out)

    def test_strips_bare_example_usage(self):
        code = "def f(x):\n    return x + 1\n\nf(3)\nprint(f(3))"
        out = _strip_driver_code(code)
        self.assertIn("def f", out)
        self.assertNotIn("print(", out)
        self.assertNotIn("f(3)", out.replace("def f", ""))  # no bare call left

    def test_clean_code_untouched(self):
        clean = "def merge_sort(arr):\n    return arr\n\n\ndef merge(a, b):\n    return a"
        self.assertEqual(_strip_driver_code(clean), clean)  # nothing to strip, formatting preserved


if __name__ == "__main__":
    unittest.main()
