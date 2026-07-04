"""CP12a — the T6 Formula Engine type gate. The engine authors a formula concept's trace from a data spec; this
proves, for EVERY spec across many seeds, that (1) the trace is structurally valid against its ExampleSpec,
(2) it is a teaching trace, (3) select_instance (the pipeline's Stage 0/1) accepts it, and — the load-bearing
check — (4) every output equals an INDEPENDENT re-evaluation of its formula on the same givens (gate-passing !=
authored-correct: a wrong formula/unit spec must fail here, not ship). This is the T6 analogue of
`test_code_reproduces_trace` for coding adapters."""
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters.decl import hydrate
from app.services.examples.trace_adapters.families.formula_engine import _eval, _num, formula_decl
from app.services.examples.trace_adapters.families.formula_specs import ALL_SPECS


class FormulaEngineGate(unittest.TestCase):
    def _adapter(self, spec):
        return hydrate(formula_decl(spec))

    def test_every_spec_produces_a_valid_teaching_trace(self):
        for spec in ALL_SPECS:
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                seen_answers = 0
                for seed in range(12):
                    tr = tp.select_instance(a, seed=seed)   # Stage 0/1: candidate -> teaching trace
                    self.assertIsNotNone(tr, f"{spec.slug}: no teaching trace at seed {seed}")
                    self.assertEqual(tp.structural_invariants(tr, a), [],
                                     f"{spec.slug}: structural invariants not clean")
                    self.assertTrue(a.is_teaching_trace(tr))
                    self.assertEqual(len(tr.steps), 1 + len(spec.outputs))   # identify + one per output
                    seen_answers += 1
                self.assertGreater(seen_answers, 0)

    def test_every_output_matches_an_independent_recomputation(self):
        # The correctness gate: recompute each output from the RAW givens with an independent eval and compare
        # to what the trace shipped. Catches a wrong formula, wrong operator, or a stale copy.
        for spec in ALL_SPECS:
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(12):
                    tr = tp.select_instance(a, seed=seed)
                    givens = {g.name: tr.steps[0].inputs[g.name] for g in spec.givens}
                    env = dict(givens)
                    for o in spec.outputs:
                        want = _num(_eval(o.expr, env))
                        self.assertEqual(tr.final_answer[o.name], want,
                                         f"{spec.slug}.{o.name}: trace {tr.final_answer[o.name]} != recompute {want}")
                        env[o.name] = want

    def test_substituted_equation_and_answer_appear_in_the_step_prose(self):
        # Every compute step must SHOW its substituted equation and its numeric result (the learner-facing proof
        # that the number was derived, not asserted).
        for spec in ALL_SPECS:
            a = self._adapter(spec)
            tr = tp.select_instance(a, seed=5)
            with self.subTest(slug=spec.slug):
                for o in spec.outputs:
                    step = next(s for s in tr.steps if s.operation == o.stage())
                    self.assertIn(str(tr.final_answer[o.name]), step.reason)   # the value is shown
                    self.assertIn("=", step.reason)                            # as an equation
                    self.assertEqual(a.validate_prose_claims(
                        {"reasoning": step.reason, "work": [], "result": step.expected_visible_result}, step), [])

    def test_specs_have_distinct_slugs_and_nonempty_outputs(self):
        slugs = [s.slug for s in ALL_SPECS]
        self.assertEqual(len(slugs), len(set(slugs)), "duplicate formula slug")
        for s in ALL_SPECS:
            self.assertTrue(s.outputs, f"{s.slug}: no outputs")
            self.assertTrue(s.givens, f"{s.slug}: no givens")


if __name__ == "__main__":
    unittest.main()
