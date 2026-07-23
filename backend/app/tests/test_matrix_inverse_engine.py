"""T15 matrix-inversion type gate (ADAPTER_TAXONOMY_SPEC.md T15 backlog: inverse_by_row_reduction) — a second
concept shape on the row-reduce engine: row operations on [A | I] turn it into [I | A^-1]. This proves, for
EVERY registered inverse spec across seeds, that (1) the trace is structurally valid + a teaching trace, (2)
the final answer equals an INDEPENDENT oracle (the adjugate/cofactor formula, a different algorithm than
Gauss-Jordan), and (3) the computed inverse actually satisfies A * A^-1 = I.

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_matrix_inverse_engine
"""
import os
import unittest
from fractions import Fraction

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters.decl import hydrate
from app.services.examples.trace_adapters.families import rowreduce_engine as rr
from app.services.examples.trace_adapters.families.rowreduce_engine import (
    matrix_inverse_decl, registered_inverse_specs,
)


def _matmul(X, Y):
    n = len(X)
    return [[sum(X[i][k] * Y[k][j] for k in range(n)) for j in range(n)] for i in range(n)]


class MatrixInverseUnit(unittest.TestCase):
    def test_adjugate_inverse_matches_multiplication_check(self):
        A = [[1, -1, 2], [-1, 3, 2], [3, 2, 2]]
        inv = rr.inverse_via_adjugate(A)
        prod = _matmul([[Fraction(v) for v in row] for row in A], inv)
        identity = [[Fraction(1) if i == j else Fraction(0) for j in range(3)] for i in range(3)]
        self.assertEqual(prod, identity)

    def test_rref_on_augmented_identity_reaches_the_identity_left_block(self):
        A = [[2, 1], [1, 3]]
        ops = list(rr._rref_on_matrix(rr._aug_identity(A), 2))
        final = ops[-1][1]
        self.assertEqual([final[i][j] for i in range(2) for j in range(2)],
                         [Fraction(1), Fraction(0), Fraction(0), Fraction(1)])


class MatrixInverseEngineGate(unittest.TestCase):
    def _adapter(self, spec):
        return hydrate(matrix_inverse_decl(spec))

    def test_every_spec_produces_a_valid_teaching_trace(self):
        for spec in registered_inverse_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(15):
                    tr = tp.select_instance(a, seed=seed)
                    self.assertIsNotNone(tr, f"{spec.slug}: no teaching trace at seed {seed}")
                    self.assertEqual(tp.structural_invariants(tr, a), [],
                                     f"{spec.slug}: structural not clean at seed {seed}")
                    self.assertTrue(a.is_teaching_trace(tr))

    def test_final_answer_matches_independent_adjugate_oracle(self):
        for spec in registered_inverse_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(15):
                    tr = tp.select_instance(a, seed=seed)
                    state0 = dict(tr.steps[0].inputs)
                    self.assertEqual(tr.final_answer, spec.oracle(state0),
                                     f"{spec.slug}: answer {tr.final_answer} != oracle {spec.oracle(state0)}")

    def test_computed_inverse_actually_satisfies_a_times_a_inverse_equals_identity(self):
        for spec in registered_inverse_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(15):
                    tr = tp.select_instance(a, seed=seed)
                    A = dict(tr.steps[0].inputs)["A"]
                    n = spec.n
                    inv = [[Fraction(tr.final_answer[f"inv_{i+1}_{j+1}"]) for j in range(n)] for i in range(n)]
                    prod = _matmul([[Fraction(v) for v in row] for row in A], inv)
                    identity = [[Fraction(1) if i == j else Fraction(0) for j in range(n)] for i in range(n)]
                    self.assertEqual(prod, identity, f"{spec.slug} seed {seed}: A * A^-1 != I")


if __name__ == "__main__":
    unittest.main()
