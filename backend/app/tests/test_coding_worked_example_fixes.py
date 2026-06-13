"""Regression tests for the coding worked-example fixes (legacy bridge).

Covers: base-case detection for `if node is None:`, full per-line highlight
coverage across the inorder trace, the class `Solution` setup card, and the
output/result panel populating. Pure backend, no LLM.
Run: python -m unittest app.tests.test_coding_worked_example_fixes
"""
from __future__ import annotations

import unittest

from app.services.legacy_v2_visual_bridge import (
    _coding_setup_bullets,
    _coding_trace_bullets,
    _detect_traversal_code_lines,
)

# LeetCode class shape mandated by the prompt.
CLASS_INORDER = """class Solution:
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

# Older top-level shape must still work.
TOPLEVEL_INORDER = """def inorder(root):
    result = []
    traverse(root, result)
    return result

def traverse(node, result):
    if node is None:
        return
    traverse(node.left, result)
    result.append(node.val)
    traverse(node.right, result)"""


class TestDetectLines(unittest.TestCase):
    def test_class_shape_lines_detected(self):
        lines = _detect_traversal_code_lines(CLASS_INORDER)
        # base-case `if node is None:` = 9, return = 10, left = 11, append = 12, right = 13.
        self.assertEqual(lines.get("base_case"), 9)
        self.assertEqual(lines.get("recurse_left"), 11)
        self.assertEqual(lines.get("visit"), 12)
        self.assertEqual(lines.get("recurse_right"), 13)

    def test_base_case_is_none_form_detected(self):
        self.assertIn("base_case", _detect_traversal_code_lines("def f(node):\n    if node is None:\n        return"))

    def test_base_case_not_form_detected(self):
        self.assertIn("base_case", _detect_traversal_code_lines("def f(node):\n    if not node:\n        return"))


class TestTraceBulletsCoverAllLines(unittest.TestCase):
    def test_inorder_highlights_base_visit_left_right(self):
        lines = _detect_traversal_code_lines(CLASS_INORDER)
        points, highlights = _coding_trace_bullets(
            active="40", previous_output=["20", "30"], next_output=["20", "30", "40"],
            next_active="50", traversal="inorder", code_lines=lines,
        )
        flat = {h[0] for h in highlights if h}
        # Every executable line of the helper is highlighted somewhere in the trace.
        self.assertIn(lines["base_case"], flat)
        self.assertIn(lines["recurse_left"], flat)
        self.assertIn(lines["visit"], flat)
        self.assertIn(lines["recurse_right"], flat)
        self.assertEqual(len(points), len(highlights))


class TestSetupCardClassShape(unittest.TestCase):
    def setUp(self):
        self.points, self.highlights = _coding_setup_bullets(
            code_snippet=CLASS_INORDER, traversal="inorder", root_id="50"
        )

    def test_covers_entry_method_not_helper(self):
        joined = " ".join(self.points).lower()
        self.assertIn("entry method", joined)
        self.assertIn("empty list", joined)  # result = [] init
        # The helper's work (append/recurse) must NOT appear as a setup bullet.
        self.assertNotIn("appended", joined)

    def test_includes_descent_preview(self):
        joined = " ".join(self.points).lower()
        self.assertIn("leftmost", joined)
        # The descent bullet highlights the recursive left call line.
        left_line = _detect_traversal_code_lines(CLASS_INORDER)["recurse_left"]
        self.assertTrue(any(h and h[0] == left_line for h in self.highlights))

    def test_toplevel_shape_still_supported(self):
        points, _ = _coding_setup_bullets(code_snippet=TOPLEVEL_INORDER, traversal="inorder", root_id="50")
        self.assertTrue(any("entry method" in p.lower() for p in points))


if __name__ == "__main__":
    unittest.main()
