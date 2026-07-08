"""T13 Proof-Obligation (Induction) Engine type gate. The engine proves a polynomial summation identity by
induction; this proves, for EVERY spec across seeds, that (1) the trace is structurally valid + a teaching trace,
(2) select_instance accepts it, (3) the BASE-case obligation holds, (4) the INDUCTIVE-STEP polynomial identity
g(k)+f(k+1)=g(k+1) holds at many points (proving it for all k — the T13 obligation), and (5) the closed form
matches an INDEPENDENT running-sum oracle at the instance value.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_induction_engine
"""
import os
import random
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters.decl import hydrate
from app.services.examples.trace_adapters.families.induction_engine import induction_decl, registered_specs


class InductionObligations(unittest.TestCase):
    def test_base_and_inductive_step_obligations_hold(self):
        for spec in registered_specs():
            with self.subTest(slug=spec.slug):
                self.assertTrue(spec.base_ok(), f"{spec.slug}: base case obligation failed")
                self.assertTrue(spec.inductive_step_ok(), f"{spec.slug}: inductive-step identity failed")

    def test_closed_form_matches_running_sum_oracle(self):
        # the closed form g(n) equals the DIRECT running sum for a wide range of n (independent of the proof)
        for spec in registered_specs():
            with self.subTest(slug=spec.slug):
                for n in range(spec.base, spec.base + 20):
                    self.assertEqual(spec.g(n), spec.sum_upto(n), f"{spec.slug}: g({n}) != running sum")

    def test_a_wrong_closed_form_is_rejected(self):
        # the gate must REJECT a bogus identity — proves the check isn't vacuous
        from app.services.examples.trace_adapters.families.induction_engine import InductionSpec
        bogus = InductionSpec(slug="bogus", title="", problem_template="{N}",
                              f=lambda i: i, g=lambda n: n * n, f_str="i", g_str="n^2")   # sum i != n^2
        self.assertFalse(bogus.inductive_step_ok())


class InductionEngineGate(unittest.TestCase):
    def _adapter(self, spec):
        return hydrate(induction_decl(spec))

    def test_every_spec_produces_a_valid_teaching_trace(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(10):
                    tr = tp.select_instance(a, seed=seed)
                    self.assertIsNotNone(tr, f"{spec.slug}: no trace at seed {seed}")
                    self.assertEqual(tp.structural_invariants(tr, a), [], f"{spec.slug}: structural not clean")
                    self.assertTrue(a.is_teaching_trace(tr))

    def test_final_answer_matches_independent_oracle(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(10):
                    tr = tp.select_instance(a, seed=seed)
                    state0 = dict(tr.steps[0].inputs)
                    self.assertEqual(tr.final_answer, spec.oracle(state0),
                                     f"{spec.slug}: answer {tr.final_answer} != oracle {spec.oracle(state0)}")


if __name__ == "__main__":
    unittest.main()
