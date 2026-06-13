"""Regression test: code_walkthrough must include the MAIN function, not just the
helper. When the walkthrough collapses to a bare self-recursive helper, the
complete main+helper program from the worked_example is adopted.
"""
from __future__ import annotations

import unittest

try:
    from app.services.lean_lesson_generator import (
        _accumulate_code_walkthrough_visuals,
        _complete_code_from_worked_examples,
        _is_bare_helper,
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
        _accumulate_code_walkthrough_visuals,
        _complete_code_from_worked_examples,
        _is_bare_helper,
    )

BARE_HELPER = """def traverse(node, result):
    if node is None:
        return
    traverse(node.left, result)
    traverse(node.right, result)
    result.append(node.val)"""

COMPLETE = """def postorderTraversal(root):
    result = []
    traverse(root, result)
    return result


def traverse(node, result):
    if node is None:
        return
    traverse(node.left, result)
    traverse(node.right, result)
    result.append(node.val)"""


class TestIsBareHelper(unittest.TestCase):
    def test_bare_helper_true(self):
        self.assertTrue(_is_bare_helper(BARE_HELPER))

    def test_main_plus_helper_false(self):
        self.assertFalse(_is_bare_helper(COMPLETE))

    def test_iterative_single_function_false(self):
        code = "def bfs(graph, start):\n    queue = [start]\n    while queue:\n        node = queue.pop(0)"
        self.assertFalse(_is_bare_helper(code))  # not self-recursive

    def test_one_arg_recursive_false(self):
        code = "def inorder(root):\n    if root is None:\n        return []\n    return inorder(root.left)"
        self.assertFalse(_is_bare_helper(code))  # no accumulator param


class TestGuardAdoptsCompleteCode(unittest.TestCase):
    def test_walkthrough_gets_main_from_worked_example(self):
        cards = [
            {"blueprint_key": "code_walkthrough", "code_snippet": BARE_HELPER, "points": ["a"]},
            {"blueprint_key": "code_walkthrough", "code_snippet": BARE_HELPER, "points": ["b"]},
            {"blueprint_key": "worked_example", "code_snippet": COMPLETE},
        ]
        _accumulate_code_walkthrough_visuals(cards)
        walk = [c for c in cards if c["blueprint_key"] == "code_walkthrough"]
        for card in walk:
            self.assertIn("def postorderTraversal(root):", card["code_snippet"])
            self.assertIn("def traverse(node, result):", card["code_snippet"])
        # Final card reveals the whole program.
        self.assertEqual(walk[-1]["visual_plan"]["max_line"], len(COMPLETE.split("\n")))

    def test_complete_helper_from_worked_examples(self):
        cards = [{"blueprint_key": "worked_example", "code_snippet": COMPLETE}]
        self.assertEqual(_complete_code_from_worked_examples(cards), COMPLETE)

    def test_no_worked_example_leaves_walkthrough_as_is(self):
        cards = [{"blueprint_key": "code_walkthrough", "code_snippet": BARE_HELPER, "points": ["a"]}]
        _accumulate_code_walkthrough_visuals(cards)
        # Nothing to adopt — stays the helper (no crash, no main invented).
        self.assertNotIn("postorderTraversal", cards[0]["code_snippet"])


if __name__ == "__main__":
    unittest.main()
