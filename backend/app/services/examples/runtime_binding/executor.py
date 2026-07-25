"""Exact rational executor for compiled Milestone A descriptors."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Mapping

from app.services.examples.runtime_binding.artifacts import AuthoredRelationshipDescriptor
from app.services.examples.runtime_binding.restricted_expression import Binary, Literal, Negate, RestrictedExpression, Variable


class ExecutionError(ValueError):
    pass


@dataclass(frozen=True)
class ExecutionLimits:
    max_abs_integer: int = 10**12
    max_power: int = 12
    max_fraction_bits: int = 4096


@dataclass(frozen=True)
class ExecutionResult:
    value: Fraction
    canonical_value: Fraction
    output_symbol: str
    output_unit: str


def _fraction(value: int | str | Decimal | Fraction) -> Fraction:
    if isinstance(value, bool):
        raise ExecutionError("boolean is not a numeric input")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, (str, Decimal)):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise ExecutionError(f"invalid exact numeric input: {value!r}") from exc
    raise ExecutionError(f"unsupported numeric input type: {type(value).__name__}")


def _bounded(value: Fraction, limits: ExecutionLimits) -> Fraction:
    if value.numerator.bit_length() > limits.max_fraction_bits:
        raise ExecutionError("fraction numerator exceeds resource bound")
    if value.denominator.bit_length() > limits.max_fraction_bits:
        raise ExecutionError("fraction denominator exceeds resource bound")
    return value


def evaluate_expression(
    expression: RestrictedExpression,
    environment: Mapping[str, Fraction],
    *,
    limits: ExecutionLimits,
) -> Fraction:
    if isinstance(expression, Literal):
        return expression.value
    if isinstance(expression, Variable):
        try:
            return environment[expression.name]
        except KeyError as exc:
            raise ExecutionError(f"missing variable: {expression.name}") from exc
    if isinstance(expression, Negate):
        return _bounded(-evaluate_expression(expression.operand, environment, limits=limits), limits)

    left = evaluate_expression(expression.left, environment, limits=limits)
    right = evaluate_expression(expression.right, environment, limits=limits)
    if expression.op == "add":
        value = left + right
    elif expression.op == "subtract":
        value = left - right
    elif expression.op == "multiply":
        value = left * right
    elif expression.op == "divide":
        if right == 0:
            raise ExecutionError("division by zero")
        value = left / right
    elif expression.op == "power":
        if right.denominator != 1:
            raise ExecutionError("power exponent must be an integer")
        exponent = right.numerator
        if abs(exponent) > limits.max_power:
            raise ExecutionError("power exponent exceeds resource bound")
        if left == 0 and exponent < 0:
            raise ExecutionError("zero cannot be raised to a negative power")
        value = left ** exponent
    else:  # pragma: no cover - frozen type union makes this defensive only
        raise ExecutionError(f"unknown operation: {expression.op}")
    return _bounded(value, limits)


def execute_descriptor(
    descriptor: AuthoredRelationshipDescriptor,
    inputs: Mapping[str, int | str | Decimal | Fraction],
    *,
    limits: ExecutionLimits | None = None,
) -> ExecutionResult:
    policy = limits or ExecutionLimits()
    input_units = {symbol.name: symbol.resolved_unit for symbol in descriptor.symbols if symbol.role == "input"}
    unexpected = sorted(set(inputs) - set(input_units))
    if unexpected:
        raise ExecutionError(f"unexpected inputs: {', '.join(unexpected)}")
    environment = {
        name: _fraction(value) * input_units[name].scale_to_canonical
        for name, value in inputs.items()
        if name in input_units
    }
    for value in environment.values():
        if value.denominator == 1 and abs(value.numerator) > policy.max_abs_integer:
            raise ExecutionError("integer input exceeds resource bound")
        _bounded(value, policy)
    for constant in descriptor.constants:
        environment[constant.symbol] = constant.exact_value
    for symbol in descriptor.symbols:
        if symbol.role == "input" and symbol.name not in environment:
            raise ExecutionError(f"missing input: {symbol.name}")
    for constraint in descriptor.domain_constraints:
        if evaluate_expression(constraint.expression, environment, limits=policy) == 0:
            raise ExecutionError("nonzero domain constraint failed")
    canonical_value = evaluate_expression(descriptor.expression, environment, limits=policy)
    value = _bounded(canonical_value / descriptor.resolved_output_unit.scale_to_canonical, policy)
    return ExecutionResult(
        value=value,
        canonical_value=canonical_value,
        output_symbol=descriptor.output_symbol,
        output_unit=descriptor.output_unit,
    )
