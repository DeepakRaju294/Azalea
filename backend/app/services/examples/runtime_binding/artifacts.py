"""Reduced Milestone A substrate artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from app.services.examples.runtime_binding.restricted_expression import RestrictedExpression
from app.services.examples.runtime_binding.units import Unit


@dataclass(frozen=True)
class AuthoredSymbol:
    name: str
    role: Literal["input", "constant", "output"]
    unit: str
    resolved_unit: Unit


@dataclass(frozen=True)
class AuthoredConstant:
    constant_id: str
    source_row_id: str
    symbol: str
    exact_value: Fraction
    unit: str
    resolved_unit: Unit


@dataclass(frozen=True)
class NonzeroConstraint:
    expression: RestrictedExpression


@dataclass(frozen=True)
class AuthoredRelationshipDescriptor:
    relationship_id: str
    expression: RestrictedExpression
    symbols: tuple[AuthoredSymbol, ...]
    constants: tuple[AuthoredConstant, ...]
    domain_constraints: tuple[NonzeroConstraint, ...]
    output_symbol: str
    output_unit: str
    resolved_output_unit: Unit
    numeric_policy_ref: str = "rational_exact_v1"
