"""Phase 1.5 visual contract (WORKED_EXAMPLE_REASONING_SPEC §12/§Scope): every adapter must emit a
renderer-well-formed `visual_state` on every step — a non-empty dict, a `kind` in the renderer's vocabulary
(VISUAL_KINDS), carrying that kind's required fields. `visual_state` is a faithful PROJECTION of the verified
machine state (may hide/rename fields), so the enforced contract is well-formedness, not field-equality.

This is the backend half of Phase 1.5. The remaining half — the renderer consuming `visual_state` — lives in
the frontend and is validated there. Fully offline (no LLM)."""
import dataclasses
import unittest

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_contract import (VISUAL_KINDS, validate_fidelity,
                                                  visual_contract_violations)


def _with_bad_visual(trace):
    """A copy of the trace whose first step carries an unknown visual kind (Step is frozen)."""
    steps = list(trace.steps)
    steps[0] = dataclasses.replace(steps[0], visual_state={"kind": "not_a_real_kind"})
    return dataclasses.replace(trace, steps=steps)


class VisualContract(unittest.TestCase):
    def test_every_adapter_is_render_ready(self):
        # §Scope: every registered adapter, across seeds, must produce a Phase-1.5 render-ready trace.
        for slug, adapter in sorted(ADAPTERS.items()):
            for seed in range(1, 8):
                trace = tp.select_instance(adapter, seed=seed)
                if trace is None:
                    continue
                with self.subTest(slug=slug, seed=seed):
                    self.assertEqual(visual_contract_violations(trace), [],
                                     f"{slug}: visual_state is not renderer-well-formed")

    def test_fidelity_enforces_the_contract_in_phase_1_5(self):
        # With validate_visual_state=True (Phase 1.5), faithful cards pass; a bad kind is caught.
        adapter = ADAPTERS["binary_search"]
        trace = tp.select_instance(adapter, seed=3)
        cards = tp._deterministic_narration(trace, adapter)
        self.assertTrue(validate_fidelity(cards, trace, adapter, validate_visual_state=True).ok)
        # a step with an unknown visual kind -> the contract must fail
        bad = _with_bad_visual(trace)
        res = validate_fidelity(tp._deterministic_narration(bad, adapter), bad, adapter,
                                validate_visual_state=True)
        self.assertFalse(res.ok)
        self.assertEqual(res.code, "visual_contract")

    def test_phase_1_default_ignores_visual(self):
        # Phase 1 (default) must NOT enforce the visual contract — a bad visual still ships (metadata only).
        adapter = ADAPTERS["binary_search"]
        bad = _with_bad_visual(tp.select_instance(adapter, seed=3))
        self.assertTrue(validate_fidelity(tp._deterministic_narration(bad, adapter), bad, adapter).ok)

    def test_vocabulary_is_closed(self):
        # The registry is the closed vocabulary; a stray kind is rejected (guards against silent drift).
        self.assertIn("array", VISUAL_KINDS)
        self.assertNotIn("", VISUAL_KINDS)


if __name__ == "__main__":
    unittest.main()
