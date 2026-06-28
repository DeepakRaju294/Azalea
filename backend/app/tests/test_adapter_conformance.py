"""Every registered adapter must satisfy the Adapter Contract (ADAPTER_CONTRACT.md) — the 15 universal items
+ a Stage-0 trace that passes the structural gate. An incomplete or drifted adapter fails here, not in
production. Fully offline (no LLM)."""
import unittest

from app.services.examples.trace_adapters import ADAPTERS
from app.services.examples.trace_adapters.contract import (adapter_c1_gaps,
                                                           adapter_contract_violations)


class AdapterConformance(unittest.TestCase):
    def test_every_adapter_conforms(self):
        for slug, adapter in sorted(ADAPTERS.items()):
            with self.subTest(slug=slug):
                violations = adapter_contract_violations(adapter)
                self.assertEqual(violations, [], f"{slug} violates the adapter contract: {violations}")

    def test_every_adapter_declares_an_example_spec_matching_its_stages(self):
        # C1: each adapter ships an ExampleSpec whose surfaced stage ids cover every operation it emits.
        from app.services.examples import trace_pipeline as tp
        for slug, adapter in sorted(ADAPTERS.items()):
            with self.subTest(slug=slug):
                spec = getattr(adapter, "example_spec", None)
                self.assertIsNotNone(spec, f"{slug}: no example_spec")
                trace = tp.select_instance(adapter, seed=3)
                used = {s.operation for s in trace.steps}
                self.assertTrue(used <= spec.surfaced_stage_ids,
                                f"{slug}: ops {used - spec.surfaced_stage_ids} not in declared stages")
                self.assertTrue(set(spec.must_exercise) <= set(trace.required_cases),
                                f"{slug}: must_exercise not aligned with required_cases")

    def test_c1_gaps_are_tracked(self):
        # Informational: the existing adapters are pre-C1, so gaps are expected; the tracker must run and
        # return a list for every adapter (so progress toward C1 is observable, not a hard failure).
        for slug, adapter in sorted(ADAPTERS.items()):
            with self.subTest(slug=slug):
                self.assertIsInstance(adapter_c1_gaps(adapter), list)

    def test_contract_catches_an_incomplete_adapter(self):
        # a deliberately broken adapter must be flagged (proves the check has teeth)
        class _Broken:
            slug = "broken"
            version = 1
            def candidates(self, seed): return iter([{"x": 1}])
            # missing: reference, is_teaching_trace, states_equivalent, ...
        self.assertTrue(adapter_contract_violations(_Broken()))


if __name__ == "__main__":
    unittest.main()
