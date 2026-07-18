"""T15 Row-Reduction Engine type gate. The engine solves a linear system by Gauss-Jordan elimination; this proves,
for EVERY spec across seeds, that (1) the trace is structurally valid + a teaching trace, (2) select_instance
accepts it, (3) the extracted solution equals an INDEPENDENT Cramer's-rule oracle, and (4) the true solution
satisfies EVERY intermediate augmented matrix (each row operation preserved the solution set — the T15 invariant).

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_rowreduce_engine
"""
import os
import unittest
from fractions import Fraction

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters.decl import hydrate
from app.services.examples.trace_adapters.families import rowreduce_engine as rr
from app.services.examples.trace_adapters.families.rowreduce_engine import registered_specs, rowreduce_decl


class RowReduceUnit(unittest.TestCase):
    def test_rref_matches_cramer(self):
        A, b = [[2, 1], [1, 3]], [5, 10]      # x=1, y=3
        self.assertEqual(rr.rref_solution(A, b), rr.cramer_solve(A, b))
        self.assertEqual(rr.rref_solution(A, b), [Fraction(1), Fraction(3)])

    def test_solution_preserved_across_snapshots(self):
        A, b, x = [[2, 1], [1, 3]], [5, 10], [1, 3]
        for snap in rr.rref_snapshots(A, b):
            for row in snap:
                lhs = sum(row[j] * x[j] for j in range(len(x)))
                self.assertEqual(lhs, row[len(x)])   # A_k x* == b_k at every step


class RowReduceEngineGate(unittest.TestCase):
    def _adapter(self, spec):
        return hydrate(rowreduce_decl(spec))

    def test_every_spec_produces_a_valid_teaching_trace(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(12):
                    tr = tp.select_instance(a, seed=seed)
                    self.assertIsNotNone(tr, f"{spec.slug}: no teaching trace at seed {seed}")
                    self.assertEqual(tp.structural_invariants(tr, a), [],
                                     f"{spec.slug}: structural not clean at seed {seed}")
                    self.assertTrue(a.is_teaching_trace(tr))

    def test_final_answer_matches_independent_oracle(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(12):
                    tr = tp.select_instance(a, seed=seed)
                    state0 = dict(tr.steps[0].inputs)
                    self.assertEqual(tr.final_answer, spec.oracle(state0),
                                     f"{spec.slug}: answer {tr.final_answer} != oracle {spec.oracle(state0)}")

    def test_solution_preserved_after_every_row_operation(self):
        for spec in registered_specs():
            with self.subTest(slug=spec.slug):
                a = self._adapter(spec)
                for seed in range(12):
                    tr = tp.select_instance(a, seed=seed)
                    s0 = dict(tr.steps[0].inputs)
                    A, b, x = s0["A"], s0["b"], s0["x_star"]
                    for snap in rr.rref_snapshots(A, b):
                        for row in snap:
                            lhs = sum(row[j] * x[j] for j in range(len(x)))
                            self.assertEqual(lhs, row[len(x)],
                                             f"{spec.slug}: row op did not preserve the solution")

    def test_ref_spec_stops_at_row_echelon_form(self):
        # The REF variant must do FORWARD elimination only: every eliminate targets a row strictly BELOW its
        # pivot, the terminal card reads the solution via back-substitution, and back-substitution from the
        # engine's own REF matrix equals the independent Cramer oracle.
        import re
        from fractions import Fraction

        specs = [s for s in registered_specs() if s.stop_at == "ref"]
        self.assertTrue(specs, "no REF-stop spec registered")
        for spec in specs:
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(12):
                    tr = tp.select_instance(a, seed=seed)
                    for s in tr.steps[1:]:
                        m = re.match(r"eliminate column (\d+) from row (\d+)", s.decision)
                        if m:
                            self.assertGreater(int(m.group(2)), int(m.group(1)),
                                               f"{spec.slug}: above-pivot elimination {s.decision!r}")
                    self.assertIn("Back-substitution", tr.steps[-1].expected_visible_result)
                    s0 = dict(tr.steps[0].inputs)
                    ref = [snap for _, snap, _, _, _ in rr._ref_ops(s0["A"], s0["b"])][-1]
                    back = rr.back_substitute(ref, spec.n)
                    self.assertEqual(back, rr.cramer_solve(s0["A"], s0["b"]),
                                     f"{spec.slug}: back-substitution from REF != Cramer")


if __name__ == "__main__":
    unittest.main()
