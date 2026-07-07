"""Q23 shadow-parallel hook + live-trace adapter (TRACE_TO_TEACHING_CONTRACT_SPEC.md §14).

Verifies the adapter maps the live trace into the typed grammar, and the shadow hook is a strict no-op until a
family is enrolled, measures C1 over trace-bound cards, and never mutates them. Tests the modules directly (the
trace_pipeline wiring point isn't imported). Run: OPENAI_API_KEY=dummy python -m unittest
app.tests.test_trace_teaching_shadow
"""
import copy
import os
import types
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.narration import rollout
from app.services.trace_teaching import adapt, shadow


def _live_step(sid, allowed, **facts):
    f = {"allowed_values": allowed}
    f.update(facts)
    return types.SimpleNamespace(
        id=sid, operation="compute_force", state_after={"F": "20"},
        expected_visible_result="F = 20 N", facts=f)


def _live_trace(*steps):
    return types.SimpleNamespace(steps=list(steps))


class Adapter(unittest.TestCase):
    def test_maps_allowed_values_and_state(self):
        by_id = adapt.steps_by_id(_live_trace(_live_step("s3", ["4", "5", "20"])))
        step = by_id["s3"]
        self.assertEqual(step.operation, "compute_force")
        self.assertIn("20", step.all_allowed_values())
        self.assertEqual(step.expected_visible_result, "F = 20 N")

    def test_maps_structured_forbidden_claim(self):
        s = _live_step("s3", ["20"], forbidden_claims=[{
            "claim_type": "direction_reversal", "subject": "object",
            "forbidden_when": {"trace_field": "F", "equals": "20"},
            "known_phrasings": ["reverses"]}])
        step = adapt.steps_by_id(_live_trace(s))["s3"]
        self.assertEqual(len(step.forbidden_claims), 1)
        self.assertEqual(step.forbidden_claims[0].claim_type, "direction_reversal")


class ShadowHook(unittest.TestCase):
    def setUp(self):
        self._orig = shadow._TELEMETRY_PATH
        shadow._TELEMETRY_PATH = os.devnull

    def tearDown(self):
        shadow._TELEMETRY_PATH = self._orig
        rollout._FAMILY_MODES.clear()

    def _cards(self):
        return [{"card_type": "worked_example", "trace_step_ids": ["s3"],
                 "points": ["the net force is 25 N"]}]   # 25 is invented (allowed 4,5,20)

    def _by_id(self):
        return adapt.steps_by_id(_live_trace(_live_step("s3", ["4", "5", "20"])))

    def test_strict_noop_when_not_enrolled(self):
        self.assertIsNone(shadow.evaluate(self._cards(), self._by_id()))

    def test_noop_without_trace_binding(self):
        rollout.set_family_mode("coding", "worked_example", rollout.SHADOW_VALIDATE)
        unbound = [{"card_type": "worked_example", "points": ["the net force is 25 N"]}]  # no trace_step_ids
        self.assertIsNone(shadow.evaluate(unbound, self._by_id()))

    def test_measures_c1_and_never_mutates(self):
        rollout.set_family_mode("coding", "worked_example", rollout.SHADOW_VALIDATE)
        cards = self._cards()
        before = copy.deepcopy(cards)
        report = shadow.evaluate(cards, self._by_id(), topic_id="t1")
        self.assertIsNotNone(report)
        self.assertGreaterEqual(report["summary"]["c1_fail"], 1)   # the invented 25 is caught
        self.assertEqual(cards, before)                            # never mutated

    def test_clean_card_passes(self):
        rollout.set_family_mode("coding", "worked_example", rollout.SHADOW_VALIDATE)
        cards = [{"card_type": "worked_example", "trace_step_ids": ["s3"],
                  "points": ["substitute 4 and 5 to get 20"]}]
        report = shadow.evaluate(cards, self._by_id())
        self.assertEqual(report["summary"]["c1_fail"], 0)


if __name__ == "__main__":
    unittest.main()
