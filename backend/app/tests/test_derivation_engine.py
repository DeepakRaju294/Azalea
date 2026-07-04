"""CP12d — the T8b Derivation Engine type gate. The engine authors a rule-justified derivation; this proves,
for EVERY spec across seeds, that (1) the trace is structurally valid, (2) it is a teaching trace, (3)
select_instance accepts it, (4) every step CITES a named rule and shows the transformation, and (5) the final
answer equals an INDEPENDENT oracle with value preserved at each step."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters.decl import hydrate
from app.services.examples.trace_adapters.families.derivation_engine import derivation_decl, registered_specs


class DerivationEngineGate(unittest.TestCase):
    def _adapter(self, spec):
        return hydrate(derivation_decl(spec))

    def test_every_spec_produces_a_valid_teaching_trace(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(12):
                    tr = tp.select_instance(a, seed=seed)
                    self.assertIsNotNone(tr, f"{spec.slug}: no teaching trace at seed {seed}")
                    self.assertEqual(tp.structural_invariants(tr, a), [], f"{spec.slug}: structural not clean")
                    self.assertTrue(a.is_teaching_trace(tr))

    def test_final_answer_matches_independent_oracle(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(12):
                    tr = tp.select_instance(a, seed=seed)
                    state0 = {k: v for k, v in tr.steps[0].inputs.items()}
                    self.assertEqual(tr.final_answer, spec.oracle(state0),
                                     f"{spec.slug}: answer {tr.final_answer} != oracle {spec.oracle(state0)}")

    def test_each_step_cites_a_named_rule(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            tr = tp.select_instance(a, seed=4)
            with self.subTest(slug=spec.slug):
                for step, ds in zip(tr.steps[1:], spec.steps):
                    self.assertIn(ds.law, step.reason, f"{spec.slug}: step {step.id} does not cite {ds.law!r}")
                    self.assertIn("=", step.reason)

    def test_value_preservation_invariant_holds_every_step(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            tr = tp.select_instance(a, seed=6)
            inv = tr.invariants[0]
            with self.subTest(slug=spec.slug):
                for s in tr.steps:
                    self.assertTrue(a.invariant_holds(inv, s.state_after), f"{spec.slug}: value not preserved")


if __name__ == "__main__":
    unittest.main()
