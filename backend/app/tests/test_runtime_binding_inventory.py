import json
import unittest

from app.services.examples.runtime_binding.inventory import (
    INVENTORY_SCHEMA_VERSION,
    inventory_formula_specs,
    inventory_live_catalog,
)
from app.services.examples.trace_adapters.families.formula_engine import FormulaSpec, Given, Output
from app.services.examples.trace_adapters.families.formula_specs import ALL_SPECS


def _spec(expr: str, *, slug: str = "fixture") -> FormulaSpec:
    return FormulaSpec(
        slug=slug,
        title=slug,
        problem_template="Given x={x}",
        givens=[Given("x", "", 1, 2)],
        outputs=[Output("y", "y = expression", expr)],
        register=False,
    )


class RuntimeBindingInventoryTests(unittest.TestCase):
    def test_live_catalog_is_complete_unique_and_source_linked(self):
        report = inventory_live_catalog()
        self.assertEqual(report.schema_version, INVENTORY_SCHEMA_VERSION)
        self.assertEqual(len(report.rows), len(ALL_SPECS))
        self.assertEqual([row.row_index for row in report.rows], list(range(len(ALL_SPECS))))
        self.assertEqual(report.summary["duplicate_slugs"], [])
        self.assertTrue(all(row.compile_result.source_locations for row in report.rows))

    def test_output_is_deterministic_and_json_serializable(self):
        first = inventory_live_catalog().to_json(indent=None)
        second = inventory_live_catalog().to_json(indent=None)
        self.assertEqual(first, second)
        decoded = json.loads(first)
        self.assertEqual(decoded["schema_version"], INVENTORY_SCHEMA_VERSION)
        self.assertEqual(len(decoded["rows"]), len(ALL_SPECS))

    def test_invalid_syntax_is_invalid_not_blocked(self):
        row = inventory_formula_specs([_spec("x +")]).rows[0]
        self.assertEqual(row.compile_result.status, "invalid")
        self.assertIsNone(row.compile_result.required_wave)
        self.assertTrue(row.outputs[0].parse_error)

    def test_unsupported_call_fails_closed_without_execution(self):
        row = inventory_formula_specs([_spec("dangerous(x)")]).rows[0]
        self.assertEqual(row.compile_result.status, "blocked")
        self.assertIn("unknown_call:dangerous", row.compile_result.unsupported_constructs)

    def test_expression_is_parsed_but_never_executed(self):
        # Division by zero would raise if the inventory evaluated the expression.
        row = inventory_formula_specs([_spec("1 / 0")]).rows[0]
        self.assertEqual(row.compile_result.status, "compiled")
        self.assertEqual(row.outputs[0].operators, ("Div",))

    def test_known_later_wave_call_is_classified(self):
        row = inventory_formula_specs([_spec("sqrt(x)")]).rows[0]
        self.assertEqual(row.compile_result.status, "blocked")
        self.assertEqual(row.compile_result.required_wave, 2)
        self.assertEqual(row.outputs[0].calls, ("sqrt",))

    def test_multi_output_dependency_is_reported(self):
        spec = FormulaSpec(
            slug="multi",
            title="multi",
            problem_template="Given x={x}",
            givens=[Given("x", "", 1, 2)],
            outputs=[
                Output("a", "a = x + 1", "x + 1"),
                Output("b", "b = a * 2", "a * 2"),
            ],
            register=False,
        )
        row = inventory_formula_specs([spec]).rows[0]
        self.assertEqual(row.compile_result.status, "blocked")
        self.assertIn("multi_output_dependency_shape", row.compile_result.execution_shape_blockers)
        self.assertEqual(row.outputs[1].prior_output_dependencies, ("a",))


if __name__ == "__main__":
    unittest.main()
