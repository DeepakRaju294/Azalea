"""Regression: generated cards conform to the course-blueprint card structure —
intro is background+roadmap only; non-code cards carry no code visual.
"""
from __future__ import annotations

import unittest

try:
    from app.services.lean_lesson_generator import (
        _enforce_blueprint_cards,
        _strip_misplaced_code_visuals,
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
        _enforce_blueprint_cards,
        _strip_misplaced_code_visuals,
    )


def _c(key, **extra):
    return {"blueprint_key": key, **extra}


class TestEnforceBlueprintCards(unittest.TestCase):
    def test_intro_keeps_only_background_and_roadmap(self):
        cards = [_c("background"), _c("worked_example"), _c("edge_case"), _c("components_terms"), _c("roadmap"), _c("practice")]
        kept = [c["blueprint_key"] for c in _enforce_blueprint_cards(cards, "study_path_introduction")]
        self.assertEqual(set(kept), {"background", "roadmap"})

    def test_coding_drops_disallowed_keys(self):
        cards = [_c("background"), _c("components_terms"), _c("code_walkthrough"), _c("worked_example"),
                 _c("edge_case"), _c("practice"), _c("roadmap"), _c("proof_plan")]
        kept = {c["blueprint_key"] for c in _enforce_blueprint_cards(cards, "coding_implementation")}
        self.assertNotIn("roadmap", kept)      # roadmap is not part of coding
        self.assertNotIn("proof_plan", kept)
        self.assertIn("code_walkthrough", kept)
        self.assertIn("worked_example", kept)

    def test_never_empties_the_lesson(self):
        cards = [_c("nonsense_key")]  # nothing allowed → keep original rather than empty
        self.assertEqual(_enforce_blueprint_cards(cards, "concept_intuition"), cards)


class TestStripMisplacedCodeVisuals(unittest.TestCase):
    def test_components_card_loses_code_visual(self):
        cards = [_c("components_terms", visual_type="code_trace", code_snippet="def f(): pass",
                    visual_plan={"type": "code_trace", "code": "def f(): pass"})]
        _strip_misplaced_code_visuals(cards)
        self.assertEqual(cards[0]["visual_type"], "none")
        self.assertEqual(cards[0]["code_snippet"], "")
        self.assertEqual(cards[0]["visual_plan"], {})

    def test_code_walkthrough_keeps_code(self):
        cards = [_c("code_walkthrough", visual_type="code_trace", code_snippet="def f(): pass")]
        _strip_misplaced_code_visuals(cards)
        self.assertEqual(cards[0]["visual_type"], "code_trace")
        self.assertEqual(cards[0]["code_snippet"], "def f(): pass")

    def test_non_code_visual_untouched(self):
        cards = [_c("components_terms", visual_type="node_link_diagram", visual_plan={"type": "node_link_diagram", "nodes": []})]
        _strip_misplaced_code_visuals(cards)
        self.assertEqual(cards[0]["visual_type"], "node_link_diagram")


if __name__ == "__main__":
    unittest.main()
