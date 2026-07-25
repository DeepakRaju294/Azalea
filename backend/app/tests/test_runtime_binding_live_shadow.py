"""Milestone C unit 10e — live-route shadow observer (offline). Proves the observer is off by default,
records on a genuine registered miss that resolves to a reviewed contract, never fires on a registered hit,
stays within the 5s budget, and is exception-safe. No learner-visible effect."""

import os
import unittest
from unittest import mock

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples.runtime_binding import live_shadow


class LiveShadowObserver(unittest.TestCase):
    def test_off_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AZALEA_RUNTIME_BINDING_SHADOW", None)
            self.assertFalse(live_shadow.is_observing())
            self.assertIsNone(live_shadow.observe_runtime_binding({"title": "Volumetric Flow Rate"}, write=False))

    def test_records_verified_evidence_on_resolvable_miss(self):
        with mock.patch.dict(os.environ, {"AZALEA_RUNTIME_BINDING_SHADOW": "observe"}):
            rec = live_shadow.observe_runtime_binding(
                {"title": "Volumetric Flow Rate", "topic_type": "math_formula_method"},
                registered_lookup=lambda t: None, write=False,
            )
        self.assertIsNotNone(rec)
        self.assertEqual(rec["decision"], "runtime_binding_evidence")
        self.assertTrue(rec["verification_passed"])
        self.assertEqual(rec["trust_level"], "reviewed_contract_runtime_binding")
        self.assertFalse(rec["learner_visible"])
        self.assertTrue(rec["within_budget"])

    def test_never_fires_on_registered_hit(self):
        with mock.patch.dict(os.environ, {"AZALEA_RUNTIME_BINDING_SHADOW": "observe"}):
            rec = live_shadow.observe_runtime_binding(
                {"title": "Kinetic Energy"}, registered_lookup=lambda t: object(), write=False,
            )
        self.assertIsNone(rec)

    def test_unresolved_concept_is_withheld_not_error(self):
        with mock.patch.dict(os.environ, {"AZALEA_RUNTIME_BINDING_SHADOW": "observe"}):
            rec = live_shadow.observe_runtime_binding(
                {"title": "Some Concept With No Reviewed Contract"},
                registered_lookup=lambda t: None, write=False,
            )
        self.assertEqual(rec["decision"], "withheld")
        self.assertIsNone(rec["evidence_id"])

    def test_observer_is_exception_safe(self):
        # a lookup that raises must not propagate; the observer returns None (records an observer_error)
        with mock.patch.dict(os.environ, {"AZALEA_RUNTIME_BINDING_SHADOW": "observe"}):
            def boom(_):
                raise RuntimeError("lookup blew up")
            self.assertIsNone(live_shadow.observe_runtime_binding({"title": "X"}, registered_lookup=boom, write=False))


if __name__ == "__main__":
    unittest.main()
