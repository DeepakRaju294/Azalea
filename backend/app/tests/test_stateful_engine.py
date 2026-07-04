"""CP12e — the T10 Stateful Engine type gate. The engine mutates a structure by a scripted sequence of
operations; this proves, for EVERY spec across seeds, that the trace is structurally valid + a teaching trace,
select_instance accepts it, every step shows the updated structure, and the final answer equals an INDEPENDENT
replay oracle."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters.decl import hydrate
from app.services.examples.trace_adapters.families.stateful_engine import registered_specs, stateful_decl


class StatefulEngineGate(unittest.TestCase):
    def _adapter(self, spec):
        return hydrate(stateful_decl(spec))

    def test_every_spec_produces_a_valid_teaching_trace(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(12):
                    tr = tp.select_instance(a, seed=seed)
                    self.assertIsNotNone(tr, f"{spec.slug}: no teaching trace at seed {seed}")
                    self.assertEqual(tp.structural_invariants(tr, a), [], f"{spec.slug}: structural not clean")
                    self.assertTrue(a.is_teaching_trace(tr))
                    self.assertNotRegex(str(spec.target), r"\d", "terminal must be digit-free")

    def test_final_answer_matches_independent_replay_oracle(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(12):
                    tr = tp.select_instance(a, seed=seed)
                    state0 = {k: v for k, v in tr.steps[0].inputs.items()}
                    self.assertEqual(tr.final_answer, spec.oracle(state0),
                                     f"{spec.slug}: answer {tr.final_answer} != replay {spec.oracle(state0)}")

    def test_each_operation_step_updates_the_structure(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            tr = tp.select_instance(a, seed=4)
            with self.subTest(slug=spec.slug):
                for step in tr.steps[1:]:
                    self.assertEqual(step.operation, "apply_operation")
                    self.assertIn("structure is now", step.reason)


if __name__ == "__main__":
    unittest.main()
