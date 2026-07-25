import unittest
from fractions import Fraction

from app.services.examples.runtime_binding.compiler import compile_formula_spec
from app.services.examples.runtime_binding.executor import ExecutionError, ExecutionLimits, execute_descriptor
from app.services.examples.runtime_binding.restricted_expression import (
    RestrictedExpressionError,
    compile_restricted_expression,
    expression_canonical_digest,
    expression_canonical_json,
)
from app.services.examples.runtime_binding.policy import execution_input_digest, numeric_unit_policy_digest
from app.services.examples.runtime_binding.units import UnitError, parse_unit
from app.services.examples.trace_adapters.families.formula_engine import FormulaSpec, Given, Output
from app.services.examples.trace_adapters.families.formula_specs import (
    DENSITY,
    KINETIC_ENERGY,
    WEIGHT_FORCE,
)


class RestrictedExpressionTests(unittest.TestCase):
    def test_formatting_does_not_change_canonical_identity(self):
        a = compile_restricted_expression("m*v**2/2")
        b = compile_restricted_expression("m * v ** 2 / 2")
        self.assertEqual(expression_canonical_json(a), expression_canonical_json(b))
        self.assertEqual(expression_canonical_digest(a), expression_canonical_digest(b))

    def test_noncommutative_order_changes_identity(self):
        a = compile_restricted_expression("x-y")
        b = compile_restricted_expression("y-x")
        self.assertNotEqual(expression_canonical_digest(a), expression_canonical_digest(b))

    def test_decimal_literal_is_exact(self):
        expression = compile_restricted_expression("0.1 + x")
        self.assertIn('"numerator":"1"', expression_canonical_json(expression))
        self.assertIn('"denominator":"10"', expression_canonical_json(expression))

    def test_calls_and_noninteger_powers_fail_closed(self):
        with self.assertRaises(RestrictedExpressionError):
            compile_restricted_expression("sqrt(x)")
        with self.assertRaises(RestrictedExpressionError):
            compile_restricted_expression("x ** 0.5")


class DescriptorCompilerTests(unittest.TestCase):
    def test_density_compiles_with_nonzero_constraint(self):
        result = compile_formula_spec(DENSITY)
        self.assertEqual(result.status, "compiled")
        self.assertEqual(len(result.descriptor.domain_constraints), 1)

    def test_reviewed_constant_retains_identity(self):
        result = compile_formula_spec(WEIGHT_FORCE)
        self.assertEqual(result.status, "compiled")
        constant = result.descriptor.constants[0]
        self.assertEqual(constant.constant_id, "weight_force:constant:g")
        self.assertEqual(constant.exact_value, Fraction(49, 5))

    def test_undeclared_symbol_is_invalid(self):
        spec = FormulaSpec(
            slug="bad",
            title="bad",
            problem_template="x={x}",
            givens=[Given("x", "", 1, 2)],
            outputs=[Output("y", "y=x+z", "x+z")],
            register=False,
        )
        result = compile_formula_spec(spec)
        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.blockers, ("undeclared_symbol:z",))


class ExactExecutorTests(unittest.TestCase):
    def test_kinetic_energy_executes_exactly(self):
        compiled = compile_formula_spec(KINETIC_ENERGY)
        result = execute_descriptor(compiled.descriptor, {"m": 3, "v": 5})
        self.assertEqual(result.value, Fraction(75, 2))
        self.assertEqual(result.output_unit, "J")

    def test_density_zero_volume_fails_domain_constraint(self):
        compiled = compile_formula_spec(DENSITY)
        with self.assertRaisesRegex(ExecutionError, "nonzero"):
            execute_descriptor(compiled.descriptor, {"m": 5, "V": 0})

    def test_float_input_is_rejected(self):
        compiled = compile_formula_spec(KINETIC_ENERGY)
        with self.assertRaisesRegex(ExecutionError, "float"):
            execute_descriptor(compiled.descriptor, {"m": 3.0, "v": 5})

    def test_power_bound_is_enforced(self):
        spec = FormulaSpec(
            slug="power",
            title="power",
            problem_template="x={x}",
            givens=[Given("x", "", 1, 2)],
            outputs=[Output("y", "y=x^20", "x**20")],
            register=False,
        )
        compiled = compile_formula_spec(spec)
        with self.assertRaisesRegex(ExecutionError, "power exponent"):
            execute_descriptor(compiled.descriptor, {"x": 2}, limits=ExecutionLimits(max_power=12))

    def test_multiplicative_units_convert_to_canonical_and_back(self):
        compiled = compile_formula_spec(DENSITY)
        result = execute_descriptor(compiled.descriptor, {"m": 2, "V": 4})
        self.assertEqual(result.value, Fraction(1, 2))
        self.assertEqual(result.canonical_value, Fraction(500))

    def test_affine_units_fail_closed(self):
        with self.assertRaises(UnitError):
            parse_unit("deg C")

    def test_execution_digest_is_order_independent_and_policy_is_stable(self):
        self.assertEqual(
            execution_input_digest("x", {"a": "0.5", "b": 2}),
            execution_input_digest("x", {"b": 2, "a": Fraction(1, 2)}),
        )
        self.assertEqual(len(numeric_unit_policy_digest()), 64)


if __name__ == "__main__":
    unittest.main()
