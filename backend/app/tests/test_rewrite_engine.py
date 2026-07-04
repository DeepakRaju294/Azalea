"""CP12c — the T7 Rewrite Engine type gate. The engine authors a rewrite concept's trace by applying one rule
per step; this proves, for EVERY spec across seeds, that (1) the trace is structurally valid, (2) it is a
teaching trace, (3) select_instance accepts it, (4) every step shows a before -> after rewrite, and — the
load-bearing check — (5) the final answer equals an INDEPENDENT oracle on the initial state (gate-passing !=
authored-correct). The T7 analogue of test_formula_engine / test_code_reproduces_trace."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters.decl import hydrate
from app.services.examples.trace_adapters.families.rewrite_engine import registered_specs, rewrite_decl


class RewriteEngineGate(unittest.TestCase):
    def _adapter(self, spec):
        return hydrate(rewrite_decl(spec))

    def test_every_spec_produces_a_valid_teaching_trace(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(12):
                    tr = tp.select_instance(a, seed=seed)
                    self.assertIsNotNone(tr, f"{spec.slug}: no teaching trace at seed {seed}")
                    self.assertEqual(tp.structural_invariants(tr, a), [], f"{spec.slug}: structural not clean")
                    self.assertTrue(a.is_teaching_trace(tr))
                    self.assertEqual(len(tr.steps), 1 + len(spec.steps))

    def test_final_answer_matches_independent_oracle(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(12):
                    tr = tp.select_instance(a, seed=seed)
                    state0 = {k: v for k, v in tr.steps[0].inputs.items()}
                    self.assertEqual(tr.final_answer, spec.oracle(state0),
                                     f"{spec.slug}: trace answer {tr.final_answer} != oracle {spec.oracle(state0)}")

    def test_each_rewrite_step_shows_before_and_after(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            tr = tp.select_instance(a, seed=4)
            with self.subTest(slug=spec.slug):
                for step in tr.steps[1:]:                       # every rewrite step (not the initial statement)
                    self.assertIn("->", step.reason, f"{spec.slug}: step {step.id} does not show a rewrite")

    def test_linear_equation_solution_satisfies_the_original(self):
        # end-to-end algebra check: the solved x, put back into a*x + b, gives c.
        from app.services.examples.trace_adapters.families import algebra_specs as al
        a = self._adapter(al.LINEAR_EQUATION)
        for seed in range(20):
            tr = tp.select_instance(a, seed=seed)
            s0 = tr.steps[0].inputs
            x = tr.final_answer["x"]
            with self.subTest(seed=seed):
                self.assertEqual(s0["coef"] * x + s0["const"], s0["rhs"])


if __name__ == "__main__":
    unittest.main()
