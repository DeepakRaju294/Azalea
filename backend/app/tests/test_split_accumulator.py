"""Regression: the broken single-function accumulator recursion is split into a
correct main + helper that ACTUALLY RUNS (the original returns None).
"""
from __future__ import annotations

import ast
import unittest

try:
    from app.services.lean_lesson_generator import (
        _split_accumulator_recursion,
        _fix_dedented_body_lines,
        _strip_module_level_strays,
        _synthesize_main_for_helper,
    )
except Exception:  # Sandbox without dotenv/openai.
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
    from app.services.lean_lesson_generator import (
        _split_accumulator_recursion,
        _fix_dedented_body_lines,
        _strip_module_level_strays,
        _synthesize_main_for_helper,
    )

# The exact bug from the screenshot: a standalone 2-arg helper, no main.
BARE_HELPER = """def postorder_helper(node, result):
    if node is None:
        return
    postorder_helper(node.left, result)
    postorder_helper(node.right, result)
    result.append(node.val)"""

BROKEN_POSTORDER = """def postorder(root):
    result = []
    if root is None:
        return result
    postorder(root.left)
    postorder(root.right)
    result.append(root.val)"""


class _TreeNode:
    def __init__(self, v, l=None, r=None):
        self.val, self.left, self.right = v, l, r


def _run(code, entry, root):
    ns = {}
    exec(compile(code, "<t>", "exec"), ns)  # noqa: S102 — trusted test code
    return ns[entry](root)


class TestSplitAccumulatorRecursion(unittest.TestCase):
    def test_splits_into_main_and_helper(self):
        out = _split_accumulator_recursion(BROKEN_POSTORDER)
        tree = ast.parse(out)
        funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        self.assertEqual(funcs, ["postorder", "traverse"])

    def test_original_is_broken_fixed_works(self):
        tree = _TreeNode(2, _TreeNode(1), _TreeNode(3))
        # Original returns None (broken).
        self.assertIsNone(_run(BROKEN_POSTORDER, "postorder", tree))
        # Transformed returns the correct postorder.
        tree2 = _TreeNode(2, _TreeNode(1), _TreeNode(3))
        self.assertEqual(_run(_split_accumulator_recursion(BROKEN_POSTORDER), "postorder", tree2), [1, 3, 2])

    def test_helper_threads_accumulator(self):
        out = _split_accumulator_recursion(BROKEN_POSTORDER)
        self.assertIn("traverse(root, result)", out)
        self.assertIn("traverse(node.left, result)", out)
        self.assertIn("result.append(node.val)", out)

    def test_correct_concat_style_untouched(self):
        code = "def inorder(root):\n    if root is None:\n        return []\n    return inorder(root.left) + [root.val] + inorder(root.right)"
        self.assertEqual(_split_accumulator_recursion(code), code)

    def test_existing_main_helper_untouched(self):
        code = ("def postorder(root):\n    result = []\n    traverse(root, result)\n    return result\n\n"
                "def traverse(node, result):\n    if node is None:\n        return\n    result.append(node.val)")
        self.assertEqual(_split_accumulator_recursion(code), code)

    def test_iterative_single_function_untouched(self):
        code = "def bfs(root):\n    result = []\n    queue = [root]\n    while queue:\n        n = queue.pop(0)\n        result.append(n.val)\n    return result"
        self.assertEqual(_split_accumulator_recursion(code), code)  # not self-recursive


class TestSynthesizeMainForHelper(unittest.TestCase):
    def test_adds_main_for_bare_helper(self):
        out = _synthesize_main_for_helper(BARE_HELPER)
        tree = ast.parse(out)
        funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        self.assertEqual(funcs, ["postorder", "postorder_helper"])

    def test_synthesized_program_runs(self):
        out = _synthesize_main_for_helper(BARE_HELPER)
        tree = _TreeNode(2, _TreeNode(1), _TreeNode(3))
        self.assertEqual(_run(out, "postorder", tree), [1, 3, 2])  # postorder

    def test_main_builds_and_returns_accumulator(self):
        out = _synthesize_main_for_helper(BARE_HELPER)
        self.assertIn("result = []", out)
        self.assertIn("postorder_helper(root, result)", out)
        self.assertIn("return result", out)

    def test_existing_main_helper_untouched(self):
        code = ("def postorder(root):\n    result = []\n    traverse(root, result)\n    return result\n\n"
                "def traverse(node, result):\n    if node is None:\n        return\n    result.append(node.val)")
        self.assertEqual(_synthesize_main_for_helper(code), code)

    def test_non_recursive_2arg_untouched(self):
        code = "def add(a, b):\n    return a + b"
        self.assertEqual(_synthesize_main_for_helper(code), code)


class TestStripModuleLevelStrays(unittest.TestCase):
    def test_removes_bare_module_level_calls(self):
        code = (
            "def f(node, result):\n    result.append(node.val)\n"
            "traverse(node.left, result)\ntraverse(node.right, result)"
        )
        out = _strip_module_level_strays(code)
        body = [type(n).__name__ for n in ast.parse(out).body]
        self.assertEqual(body, ["FunctionDef"])

    def test_keeps_clean_code(self):
        code = "def f(x):\n    return x"
        self.assertEqual(_strip_module_level_strays(code), code)


class TestFixDedentedBodyLines(unittest.TestCase):
    def test_repairs_flush_left_body_line(self):
        broken = (
            "def f(arr, t):\n    low = 0\n    high = len(arr) - 1\n"
            "mid = (low + high) // 2\n    return mid"
        )
        out = _fix_dedented_body_lines(broken)
        ast.parse(out)  # now parses
        self.assertIn("    mid = (low + high) // 2", out)

    def test_valid_code_untouched(self):
        code = "def f(x):\n    return x + 1"
        self.assertEqual(_fix_dedented_body_lines(code), code)


if __name__ == "__main__":
    unittest.main()
