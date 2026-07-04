"""CP12d — the T8a Construction Engine type gate. The engine builds a target one piece at a time; this proves,
for EVERY spec across seeds, that (1) the trace is structurally valid, (2) it is a teaching trace, (3)
select_instance accepts it, (4) EVERY partial output is valid (the T8a invariant, re-checked on the structured
state), and (5) the final answer equals an INDEPENDENT oracle. The T8a analogue of the other engine gates."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters.decl import hydrate
from app.services.examples.trace_adapters.families.construct_engine import construct_decl, registered_specs


class ConstructEngineGate(unittest.TestCase):
    def _adapter(self, spec):
        return hydrate(construct_decl(spec))

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

    def test_partial_output_is_valid_after_every_construction_step(self):
        # the load-bearing T8a property: rebuild the construction piece by piece and assert spec.valid holds at
        # every stage (empty, after piece 1, …, complete).
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(12):
                    tr = tp.select_instance(a, seed=seed)
                    state = {k: v for k, v in tr.steps[0].inputs.items()}
                    self.assertTrue(spec.valid(state), f"{spec.slug}: empty state invalid")
                    for i in range(spec.pieces(state)):
                        state, _ = spec.step(state, i)
                        self.assertTrue(spec.valid(state),
                                        f"{spec.slug}: partial output invalid after piece {i}")


if __name__ == "__main__":
    unittest.main()
