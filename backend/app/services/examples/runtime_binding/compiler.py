"""Fail-closed FormulaSpec-to-descriptor compiler for the Milestone A scalar subset."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.services.examples.runtime_binding.artifacts import (
    AuthoredConstant,
    AuthoredRelationshipDescriptor,
    AuthoredSymbol,
    NonzeroConstraint,
)
from app.services.examples.runtime_binding.restricted_expression import (
    Binary,
    Negate,
    RestrictedExpression,
    RestrictedExpressionError,
    compile_restricted_expression,
    expression_variables,
)
from app.services.examples.runtime_binding.units import DIMENSIONLESS, Unit, UnitError, parse_unit
from app.services.examples.trace_adapters.families.formula_engine import FormulaSpec


@dataclass(frozen=True)
class DescriptorCompileResult:
    status: Literal["compiled", "blocked", "invalid"]
    descriptor: AuthoredRelationshipDescriptor | None
    blockers: tuple[str, ...]


def _denominators(expression: RestrictedExpression) -> tuple[RestrictedExpression, ...]:
    if isinstance(expression, Binary):
        nested = _denominators(expression.left) + _denominators(expression.right)
        return nested + ((expression.right,) if expression.op == "divide" else ())
    if isinstance(expression, Negate):
        return _denominators(expression.operand)
    return ()


def _expression_unit(expression: RestrictedExpression, units: dict[str, Unit]) -> Unit:
    from app.services.examples.runtime_binding.restricted_expression import Literal, Variable

    if isinstance(expression, Literal):
        return DIMENSIONLESS
    if isinstance(expression, Variable):
        return units[expression.name]
    if isinstance(expression, Negate):
        return _expression_unit(expression.operand, units)
    left = _expression_unit(expression.left, units)
    right = _expression_unit(expression.right, units)
    if expression.op in {"add", "subtract"}:
        if left.dimensions != right.dimensions:
            raise UnitError(f"{expression.op} operands have incompatible dimensions")
        return left
    if expression.op == "multiply":
        return left.multiply(right)
    if expression.op == "divide":
        return left.divide(right)
    if expression.op == "power":
        from app.services.examples.runtime_binding.restricted_expression import Literal

        if not isinstance(expression.right, Literal):
            raise UnitError("unit power requires a literal exponent")
        return left.power(expression.right.value.numerator)
    raise UnitError(f"unsupported unit operation: {expression.op}")


def compile_formula_spec(spec: FormulaSpec) -> DescriptorCompileResult:
    blockers: set[str] = set()
    if spec.dataset is not None or spec.dataset2 is not None:
        blockers.add("dataset_input")
    if len(spec.outputs) != 1:
        blockers.add("requires_single_output")
    if spec.instance_ok is not None:
        blockers.add("custom_instance_predicate")
    if spec.interpret is not None:
        blockers.add("custom_interpretation_callback")
    if spec.cases:
        blockers.add("custom_coverage_cases")
    if blockers:
        return DescriptorCompileResult("blocked", None, tuple(sorted(blockers)))

    output = spec.outputs[0]
    try:
        expression = compile_restricted_expression(output.expr)
    except RestrictedExpressionError as exc:
        return DescriptorCompileResult("blocked", None, (str(exc),))

    inputs = {given.name: given for given in spec.givens}
    constants = set(spec.constants)
    referenced = expression_variables(expression)
    undeclared = sorted(referenced - set(inputs) - constants)
    if undeclared:
        return DescriptorCompileResult(
            "invalid", None, tuple(f"undeclared_symbol:{name}" for name in undeclared)
        )

    if constants - set(spec.constant_units):
        return DescriptorCompileResult(
            "invalid",
            None,
            tuple(f"missing_constant_unit:{name}" for name in sorted(constants - set(spec.constant_units))),
        )
    authored_constants = tuple(
        AuthoredConstant(
            constant_id=f"{spec.slug}:constant:{name}",
            source_row_id=spec.slug,
            symbol=name,
            exact_value=Fraction(str(spec.constants[name])) * parse_unit(spec.constant_units[name]).scale_to_canonical,
            unit=spec.constant_units[name],
            resolved_unit=parse_unit(spec.constant_units[name]),
        )
        for name in sorted(constants)
    )
    try:
        resolved_inputs = {name: parse_unit(given.unit) for name, given in inputs.items()}
        resolved_constants = {item.symbol: item.resolved_unit for item in authored_constants}
        resolved_output = parse_unit(output.unit)
        expression_unit = _expression_unit(expression, {**resolved_inputs, **resolved_constants})
    except UnitError as exc:
        return DescriptorCompileResult("blocked", None, (f"unit_capability:{exc}",))
    if expression_unit.dimensions != resolved_output.dimensions:
        return DescriptorCompileResult(
            "invalid",
            None,
            ("output_unit_dimension_mismatch",),
        )
    symbols = tuple(
        [AuthoredSymbol(name=name, role="input", unit=inputs[name].unit, resolved_unit=resolved_inputs[name]) for name in sorted(inputs)]
        + [AuthoredSymbol(name=name, role="constant", unit=spec.constant_units[name], resolved_unit=resolved_constants[name]) for name in sorted(constants)]
        + [AuthoredSymbol(name=output.name, role="output", unit=output.unit, resolved_unit=resolved_output)]
    )
    descriptor = AuthoredRelationshipDescriptor(
        relationship_id=spec.slug,
        expression=expression,
        symbols=symbols,
        constants=authored_constants,
        domain_constraints=tuple(NonzeroConstraint(item) for item in _denominators(expression)),
        output_symbol=output.name,
        output_unit=output.unit,
        resolved_output_unit=resolved_output,
    )
    return DescriptorCompileResult("compiled", descriptor, ())
