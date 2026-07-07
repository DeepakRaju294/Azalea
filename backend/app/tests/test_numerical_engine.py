"""T16 Numerical-Convergence Engine type gate. The engine iterates a numerical method to a tolerance; this proves,
for EVERY spec across seeds, that (1) the trace is structurally valid + a teaching trace, (2) select_instance
accepts it, (3) the residual is non-increasing and reaches the tolerance (convergence — the T16 invariant), (4)
each iterate equals update(previous), and (5) the converged estimate is CLOSE to an independent oracle (numerical
methods converge WITHIN a tolerance, not exactly).

Run: OPENAI_API_KEY=dummy python -m unittest app.tests.test_numerical_engine
"""
import math
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.examples import trace_pipeline as tp
from app.services.examples.trace_adapters.decl import hydrate
from app.services.examples.trace_adapters.families.numerical_engine import numerical_decl, registered_specs


class NumericalUnit(unittest.TestCase):
    def test_newton_sqrt_converges(self):
        [spec] = [s for s in registered_specs() if s.slug == "newton_sqrt"]
        seq = spec.iterate({"a": 50})
        self.assertLess(seq[-1][1], spec.tol)                       # final residual under tolerance
        self.assertAlmostEqual(seq[-1][0], math.sqrt(50), places=2)


class NumericalEngineGate(unittest.TestCase):
    def _adapter(self, spec):
        return hydrate(numerical_decl(spec))

    def test_every_spec_produces_a_valid_teaching_trace(self):
        for spec in registered_specs():
            a = self._adapter(spec)
            with self.subTest(slug=spec.slug):
                for seed in range(10):
                    tr = tp.select_instance(a, seed=seed)
                    self.assertIsNotNone(tr, f"{spec.slug}: no trace at seed {seed}")
                    self.assertEqual(tp.structural_invariants(tr, a), [], f"{spec.slug}: structural not clean")
                    self.assertTrue(a.is_teaching_trace(tr))

    def test_residual_is_non_increasing_and_reaches_tolerance(self):
        for spec in registered_specs():
            with self.subTest(slug=spec.slug):
                for seed in range(10):
                    import random
                    params = spec.setup(random.Random(seed))
                    seq = spec.iterate(params)
                    residuals = [r for _x, r, _p in seq]
                    for a, b in zip(residuals, residuals[1:]):
                        self.assertLessEqual(b, a + 1e-9, f"{spec.slug}: residual increased")
                    self.assertLess(residuals[-1], spec.tol, f"{spec.slug}: did not reach tolerance")

    def test_each_iterate_equals_update_of_previous(self):
        for spec in registered_specs():
            with self.subTest(slug=spec.slug):
                import random
                params = spec.setup(random.Random(1))
                seq = spec.iterate(params)
                for (x_prev, _r, _p), (x_next, _r2, _p2) in zip(seq, seq[1:]):
                    expected = round(spec.update(params, x_prev)[0], spec.round_dp)
                    self.assertEqual(x_next, expected, f"{spec.slug}: iterate != update(previous)")

    def test_converged_estimate_close_to_independent_oracle(self):
        for spec in registered_specs():
            with self.subTest(slug=spec.slug):
                for seed in range(10):
                    import random
                    params = spec.setup(random.Random(seed))
                    est = float(spec.answer(params)[spec.estimate_name])
                    tru = float(spec.oracle(params)[spec.estimate_name])
                    self.assertLessEqual(abs(est - tru), spec.answer_tol + 1e-9,
                                         f"{spec.slug}: estimate {est} not within tol of oracle {tru}")


if __name__ == "__main__":
    unittest.main()
