"""Regression tests for _fix_code_layout — coding-snippet layout normalization.

Pulls a stray top-level `self` method back into the class and enforces two blank
lines between sibling functions, remapping highlight ranges to the new lines.
"""
from __future__ import annotations

import ast
import unittest

try:  # Real environment: import directly.
    from app.services.lean_lesson_generator import _fix_code_layout, _remap_line_ranges
except Exception:  # Sandbox without dotenv/openai: stub the heavy deps, then retry.
    import os
    import sys
    import types

    os.environ.setdefault("OPENAI_API_KEY", "dummy")
    for _name in ("dotenv", "openai"):
        if _name not in sys.modules:
            _mod = types.ModuleType(_name)
            if _name == "dotenv":
                _mod.load_dotenv = lambda *a, **k: None
            else:
                _mod.OpenAI = lambda *a, **k: object()
                for _exc in ("APIError", "RateLimitError", "APITimeoutError", "APIConnectionError"):
                    setattr(_mod, _exc, type(_exc, (Exception,), {}))
            sys.modules[_name] = _mod
    from app.services.lean_lesson_generator import _fix_code_layout, _remap_line_ranges


# The exact bug from the screenshot: helper emitted as a top-level function
# (outside the class), no blank-line separation.
STRAY_HELPER = """class Solution:
    def inorderTraversal(self, root):
        result = []
        self.traverse(root, result)
        return result
def traverse(self, node, result):
    if node is None:
        return
    self.traverse(node.left, result)
    result.append(node.val)
    self.traverse(node.right, result)"""

# Helper already a method but with no blank lines between methods.
METHOD_NO_BLANKS = """class Solution:
    def inorderTraversal(self, root):
        result = []
        self.traverse(root, result)
        return result
    def traverse(self, node, result):
        if node is None:
            return
        result.append(node.val)"""


class TestFixCodeLayout(unittest.TestCase):
    def test_stray_helper_pulled_into_class(self):
        new, _ = _fix_code_layout(STRAY_HELPER)
        lines = new.split("\n")
        # `def traverse` is now indented as a class method (4 spaces), not column 0.
        traverse_line = next(l for l in lines if l.lstrip().startswith("def traverse"))
        self.assertTrue(traverse_line.startswith("    def traverse"))
        self.assertFalse(traverse_line.startswith("def traverse"))
        ast.parse(new)  # valid Python

    def test_two_blank_lines_between_methods(self):
        new, _ = _fix_code_layout(STRAY_HELPER)
        lines = new.split("\n")
        idx = next(i for i, l in enumerate(lines) if l.lstrip().startswith("def traverse"))
        self.assertEqual(lines[idx - 1], "")
        self.assertEqual(lines[idx - 2], "")
        self.assertNotEqual(lines[idx - 3], "")  # exactly two, not three

    def test_first_method_has_no_leading_blanks(self):
        new, _ = _fix_code_layout(STRAY_HELPER)
        lines = new.split("\n")
        idx = next(i for i, l in enumerate(lines) if l.lstrip().startswith("def inorderTraversal"))
        self.assertNotEqual(lines[idx - 1], "")  # directly under `class Solution:`

    def test_highlight_remap(self):
        new, line_map = _fix_code_layout(STRAY_HELPER)
        # orig line 5 (`return result`) is before the helper → unchanged.
        self.assertEqual(_remap_line_ranges([[5, 5]], line_map), [[5, 5]])
        # orig line 9 (`self.traverse(node.left, ...)`) shifts by the 2 inserted blanks.
        self.assertEqual(_remap_line_ranges([[9, 9]], line_map), [[11, 11]])

    def test_method_no_blanks_gets_two(self):
        new, _ = _fix_code_layout(METHOD_NO_BLANKS)
        lines = new.split("\n")
        idx = next(i for i, l in enumerate(lines) if l.lstrip().startswith("def traverse"))
        self.assertEqual((lines[idx - 1], lines[idx - 2]), ("", ""))
        ast.parse(new)

    def test_already_correct_is_idempotent(self):
        once, _ = _fix_code_layout(STRAY_HELPER)
        twice, _ = _fix_code_layout(once)
        self.assertEqual(once, twice)

    def test_single_function_unchanged(self):
        code = "def f(x):\n    return x + 1"
        new, line_map = _fix_code_layout(code)
        self.assertEqual(new, code)

    def test_toplevel_functions_get_two_blanks_no_class(self):
        # Default (non-OOP) shape: two top-level functions, no class, no self.
        code = (
            "def inorderTraversal(root):\n    result = []\n    traverse(root, result)\n    return result\n"
            "def traverse(node, result):\n    if node is None:\n        return\n    result.append(node.val)"
        )
        new, _ = _fix_code_layout(code)
        self.assertNotIn("class", new)
        self.assertNotIn("self", new)
        ast.parse(new)
        lines = new.split("\n")
        idx = next(i for i, l in enumerate(lines) if l.startswith("def traverse"))
        self.assertEqual((lines[idx - 1], lines[idx - 2]), ("", ""))


if __name__ == "__main__":
    unittest.main()
