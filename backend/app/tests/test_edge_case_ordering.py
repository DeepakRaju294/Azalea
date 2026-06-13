"""Regression tests: edge cases must not interleave with worked-example steps and
must not be trace re-walks of the example.
"""
from __future__ import annotations

import unittest

try:
    from app.services.lean_lesson_generator import (
        _drop_trace_style_edge_cases,
        _group_edge_cases_after_worked_examples,
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
        _drop_trace_style_edge_cases,
        _group_edge_cases_after_worked_examples,
    )


def _card(key, title="", points=None):
    return {"blueprint_key": key, "title": title, "points": points or []}


class TestDropTraceStyleEdgeCases(unittest.TestCase):
    def test_drops_call_stack_edge_case(self):
        cards = [
            _card("worked_example", "Postorder Step 3"),
            _card("edge_case", "Reaching Leaf Node 61", ["Call stack: [75, 60, 61]", "append to result"]),
        ]
        _drop_trace_style_edge_cases(cards)
        self.assertEqual([c["blueprint_key"] for c in cards], ["worked_example"])

    def test_drops_visit_title_edge_case(self):
        cards = [_card("edge_case", "Step 3: Visit 14", ["current = 14"])]
        _drop_trace_style_edge_cases(cards)
        self.assertEqual(cards, [])

    def test_keeps_real_edge_case(self):
        cards = [
            _card("edge_case", "Edge Case: Empty Tree",
                  ["When the tree is empty, the traversal returns immediately.",
                   "Example: an empty tree → output is []."]),
        ]
        _drop_trace_style_edge_cases(cards)
        self.assertEqual(len(cards), 1)

    def test_non_edge_cards_untouched(self):
        cards = [_card("worked_example", "Step 1", ["Call stack: [A]"]), _card("process", "p")]
        _drop_trace_style_edge_cases(cards)
        self.assertEqual(len(cards), 2)  # worked_example keeps its call-stack bullet


class TestGroupEdgeCasesAfterWorkedExamples(unittest.TestCase):
    def test_moves_interleaved_edge_case_after_worked_block(self):
        cards = [
            _card("background"), _card("worked_example", "Step 1"),
            _card("edge_case", "Empty Tree"), _card("worked_example", "Step 2"),
            _card("practice"),
        ]
        _group_edge_cases_after_worked_examples(cards)
        keys = [c["blueprint_key"] for c in cards]
        self.assertEqual(keys, ["background", "worked_example", "worked_example", "edge_case", "practice"])

    def test_edge_case_already_after_is_unchanged(self):
        cards = [_card("worked_example"), _card("edge_case"), _card("practice")]
        before = list(cards)
        _group_edge_cases_after_worked_examples(cards)
        self.assertEqual(cards, before)

    def test_no_worked_example_is_noop(self):
        cards = [_card("background"), _card("edge_case"), _card("practice")]
        before = list(cards)
        _group_edge_cases_after_worked_examples(cards)
        self.assertEqual(cards, before)


if __name__ == "__main__":
    unittest.main()
