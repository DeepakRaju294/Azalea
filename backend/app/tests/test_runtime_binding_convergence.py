import json
import unittest

from app.services.examples.runtime_binding.convergence import (
    build_offline_convergence_report,
    compare_formula_spec,
)
from app.services.examples.trace_adapters.families.formula_specs import (
    DENSITY,
    KINETIC_ENERGY,
    PYTHAGOREAN,
)


class RuntimeBindingConvergenceTests(unittest.TestCase):
    def test_exact_scalar_rows_pass_both_reports(self):
        for spec in (DENSITY, KINETIC_ENERGY):
            with self.subTest(slug=spec.slug):
                row = compare_formula_spec(spec, seeds=(0,), candidates_per_seed=4)
                self.assertEqual(row.compile_status, "compiled")
                self.assertEqual(row.execution.status, "pass", row.execution.issues)
                self.assertEqual(row.teaching.status, "pass", row.teaching.issues)
                self.assertEqual(row.execution.candidates_checked, 4)

    def test_later_wave_row_is_blocked_not_failed(self):
        row = compare_formula_spec(PYTHAGOREAN, seeds=(0,), candidates_per_seed=2)
        self.assertEqual(row.compile_status, "blocked")
        self.assertEqual(row.execution.status, "blocked")
        self.assertEqual(row.teaching.status, "blocked")

    def test_report_is_deterministic_and_separates_equivalence_dimensions(self):
        first = build_offline_convergence_report(
            [DENSITY, KINETIC_ENERGY, PYTHAGOREAN],
            seeds=(0,),
            candidates_per_seed=2,
        )
        second = build_offline_convergence_report(
            [DENSITY, KINETIC_ENERGY, PYTHAGOREAN],
            seeds=(0,),
            candidates_per_seed=2,
        )
        self.assertEqual(first.to_json(indent=None), second.to_json(indent=None))
        decoded = json.loads(first.to_json(indent=None))
        self.assertEqual(decoded["summary"]["compile_status_counts"], {"blocked": 1, "compiled": 2})
        self.assertIn("execution_status_counts", decoded["summary"])
        self.assertIn("teaching_status_counts", decoded["summary"])


if __name__ == "__main__":
    unittest.main()
