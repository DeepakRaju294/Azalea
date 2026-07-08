"""C.2 — LLM tie-break resolver for the ambiguous minority (DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §3).

Fully offline: the LLM call is injected, so the resolver's contract is tested without an API key or a route import
(avoids the .env/load_dotenv landmine). Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_domain_classifier_llm
"""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.domain_classifier import DomainSignals
from app.services.domain_classifier_llm import resolve_with_llm


def _ambiguous() -> DomainSignals:
    return DomainSignals("unknown", "", 0.0, "ambiguous", scores={"coding": 0.0})


def _classified() -> DomainSignals:
    return DomainSignals("coding", "coding", 1.0, "classified")


class LlmTieBreak(unittest.TestCase):
    def test_disabled_is_a_noop(self):
        # even with a would-be answer, the flag being off leaves the deterministic result untouched
        out = resolve_with_llm("union find", _ambiguous(), classify_fn=lambda g: "coding", force_enabled=False)
        self.assertEqual(out, _ambiguous())

    def test_confident_deterministic_is_never_second_guessed(self):
        called = []
        out = resolve_with_llm("graph bfs", _classified(),
                               classify_fn=lambda g: called.append(g) or "math", force_enabled=True)
        self.assertEqual(out, _classified())
        self.assertEqual(called, [])                          # the LLM is not even consulted when confident

    def test_ambiguous_is_resolved_by_the_llm(self):
        out = resolve_with_llm("how does encryption work", _ambiguous(),
                               classify_fn=lambda g: "coding", force_enabled=True)
        self.assertEqual(out.classification_status, "classified")
        self.assertEqual(out.gate_family, "coding")
        self.assertEqual(out.domain, "coding")
        self.assertEqual(out.source, "llm")

    def test_expository_maps_to_concept_fine_domain(self):
        out = resolve_with_llm("the meaning of justice", _ambiguous(),
                               classify_fn=lambda g: "expository", force_enabled=True)
        self.assertEqual(out.gate_family, "expository")
        self.assertEqual(out.domain, "concept")

    def test_abstain_keeps_ambiguous(self):
        out = resolve_with_llm("???", _ambiguous(), classify_fn=lambda g: None, force_enabled=True)
        self.assertEqual(out, _ambiguous())                   # non-gating fallback preserved

    def test_invalid_reply_keeps_ambiguous(self):
        out = resolve_with_llm("???", _ambiguous(), classify_fn=lambda g: "banana", force_enabled=True)
        self.assertEqual(out.classification_status, "ambiguous")

    def test_llm_error_is_best_effort(self):
        def boom(_g):
            raise RuntimeError("timeout")
        out = resolve_with_llm("???", _ambiguous(), classify_fn=boom, force_enabled=True)
        self.assertEqual(out, _ambiguous())                   # error never blocks; deterministic stands

    def test_flag_env_toggles_default(self):
        # with no force_enabled, the env flag decides; default (unset) is off
        prev = os.environ.pop("AZALEA_DOMAIN_LLM_FALLBACK", None)
        try:
            self.assertEqual(resolve_with_llm("x", _ambiguous(), classify_fn=lambda g: "math"), _ambiguous())
            os.environ["AZALEA_DOMAIN_LLM_FALLBACK"] = "1"
            self.assertEqual(
                resolve_with_llm("x", _ambiguous(), classify_fn=lambda g: "math").gate_family, "math")
        finally:
            os.environ.pop("AZALEA_DOMAIN_LLM_FALLBACK", None)
            if prev is not None:
                os.environ["AZALEA_DOMAIN_LLM_FALLBACK"] = prev


if __name__ == "__main__":
    unittest.main()
