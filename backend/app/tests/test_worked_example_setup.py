"""Regression: exactly ONE worked-example setup card per run (not spliced between
steps), and the setup inherits the first step's visual (e.g. binary search array).
"""
from __future__ import annotations

import unittest

try:
    from app.services.lean_lesson_generator import _ensure_generic_worked_example_setup_cards
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
    from app.services.lean_lesson_generator import _ensure_generic_worked_example_setup_cards


def _step(n, vtype="indexed_sequence", plan=None):
    return {
        "id": str(n), "blueprint_key": "worked_example", "card_type": "worked_example",
        "title": f"Step {n}", "visual_type": vtype,
        "visual_plan": plan if plan is not None else {"type": vtype, "array_values": ["3", "7", "9"]},
    }


def _is_setup(card):
    return (card.get("metadata") or {}).get("worked_example_setup") is True


class TestSetupCards(unittest.TestCase):
    def test_exactly_one_setup_per_run(self):
        cards = [{"blueprint_key": "background", "title": "BG"}, _step(1), _step(2), _step(3)]
        _ensure_generic_worked_example_setup_cards(cards)
        setups = [c for c in cards if _is_setup(c)]
        self.assertEqual(len(setups), 1)

    def test_setup_is_before_first_step(self):
        cards = [_step(1), _step(2)]
        _ensure_generic_worked_example_setup_cards(cards)
        self.assertTrue(_is_setup(cards[0]))           # setup first
        self.assertEqual(cards[1]["title"], "Step 1")  # then step 1
        self.assertFalse(_is_setup(cards[2]))          # no setup between steps

    def test_setup_inherits_array_visual(self):
        cards = [_step(1)]
        _ensure_generic_worked_example_setup_cards(cards)
        setup = next(c for c in cards if _is_setup(c))
        self.assertEqual(setup["visual_type"], "indexed_sequence")
        self.assertEqual(setup["visual_plan"]["array_values"], ["3", "7", "9"])

    def test_node_link_setup_skipped_for_bridge(self):
        # node_link worked examples get their structured setup from the bridge.
        cards = [_step(1, vtype="node_link_diagram", plan={"type": "node_link_diagram", "nodes": [{"id": "A"}]})]
        _ensure_generic_worked_example_setup_cards(cards)
        self.assertEqual(len([c for c in cards if _is_setup(c)]), 0)


if __name__ == "__main__":
    unittest.main()
