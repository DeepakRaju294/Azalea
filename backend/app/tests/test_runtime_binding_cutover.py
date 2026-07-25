import unittest

from app.services.examples.runtime_binding.cutover import RowCutoverState, run_offline_dual
from app.services.examples.trace_adapters.families.formula_specs import DENSITY


class OfflineCutoverTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {"m": 8, "V": 4, "_id": "density:test"}
        self.state = RowCutoverState("density")

    def test_both_staged_modes_match_without_changing_visible_result(self):
        for mode in ("legacy_primary", "substrate_primary"):
            with self.subTest(mode=mode):
                event = run_offline_dual(DENSITY, self.candidate, self.state, mode=mode)
                self.assertEqual(event.outcome, "match")
                self.assertEqual(event.learner_result, 2)
                self.assertFalse(event.alert_required)

    def test_executor_failure_falls_back_explicitly(self):
        def broken(*args, **kwargs):
            raise TimeoutError("fixture")

        event = run_offline_dual(
            DENSITY, self.candidate, self.state,
            mode="substrate_primary", substrate_runner=broken,
        )
        self.assertEqual(event.outcome, "fallback")
        self.assertEqual(event.learner_result, 2)
        self.assertTrue(event.alert_required)

    def test_substantive_mismatch_quarantines_row(self):
        class Wrong:
            value = 999

        event = run_offline_dual(
            DENSITY, self.candidate, self.state,
            mode="legacy_primary", substrate_runner=lambda *args, **kwargs: Wrong(),
        )
        self.assertEqual(event.outcome, "quarantined")
        self.assertEqual(event.next_state.substrate_status, "quarantined")
        self.assertEqual(event.next_state.status_version, 2)
        self.assertTrue(event.alert_required)


if __name__ == "__main__":
    unittest.main()
