import json
import unittest

from app.services.examples.runtime_binding.capability import build_capability_report
from app.services.examples.runtime_binding.compiler import compile_formula_spec
from app.services.examples.runtime_binding.inventory import inventory_live_catalog
from app.services.examples.trace_adapters.families.formula_specs import ALL_SPECS


class RuntimeBindingCapabilityTests(unittest.TestCase):
    def test_inventory_and_compiler_classifications_agree(self):
        report = inventory_live_catalog()
        for row, spec in zip(report.rows, ALL_SPECS):
            with self.subTest(slug=row.slug):
                self.assertEqual(row.compile_result.status, compile_formula_spec(spec).status)

    def test_freeze_is_deterministic_and_measured(self):
        first = build_capability_report().to_json(indent=None)
        second = build_capability_report().to_json(indent=None)
        self.assertEqual(first, second)
        decoded = json.loads(first)
        self.assertEqual(decoded["summary"]["registered_rows"], 132)
        self.assertGreater(decoded["summary"]["eligible_registered_rows"], 0)
        traffic = decoded["summary"]["traffic_coverage"]
        self.assertIn(traffic["status"], {"available", "unavailable"})
        if traffic["status"] == "available":
            self.assertGreater(traffic["total_formula_executions"], 0)


if __name__ == "__main__":
    unittest.main()
