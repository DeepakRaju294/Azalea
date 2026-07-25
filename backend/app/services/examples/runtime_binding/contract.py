"""Reviewed ConceptContract for Milestone B (offline runtime-binding evidence).

A ConceptContract is the reviewed, executable declaration of ONE relationship: its normalized expression,
typed/united symbols, assumptions, applicability conditions, and result interpretation. Milestone B contracts
are hand-authored fixtures (grounding_status='reviewed'); there is no runtime extraction and no model-inferred
executable field. The contract's reviewed relationship compiles — fail-closed, reusing the Milestone A
substrate — into an `AuthoredRelationshipDescriptor`, so execution/units/domain reuse the proven executor and
this layer never introduces new execution semantics (spec §0 invariant).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal, Mapping

from app.services.examples.runtime_binding.artifacts import (
    AuthoredConstant,
    AuthoredRelationshipDescriptor,
    AuthoredSymbol,
    NonzeroConstraint,
)
from app.services.examples.runtime_binding.compiler import _denominators, _expression_unit
from app.services.examples.runtime_binding.restricted_expression import (
    RestrictedExpression,
    RestrictedExpressionError,
    compile_restricted_expression,
    expression_variables,
)
from app.services.examples.runtime_binding.units import UnitError, parse_unit

Authority = Literal["reviewed", "authoritative_retrieval", "user_source", "model_inferred"]


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class GroundedArtifact:
    """A single grounded fact (definition/assumption/applicability/convention/interpretation) with its
    authority and source. Executable fields in v1 are always `reviewed`."""

    artifact_id: str
    kind: Literal[
        "definition", "assumption", "applicability", "convention", "interpretation", "invariant"
    ]
    normalized_value: str
    source_ref: str
    authority: Authority = "reviewed"


@dataclass(frozen=True)
class SymbolContract:
    symbol: str
    role: Literal["input", "output", "constant"]
    unit: str
    meaning: str
    # inclusive rational bounds for inputs (generation samples inside these); None = unbounded
    domain_min: Fraction | None = None
    domain_max: Fraction | None = None


@dataclass(frozen=True)
class NormalizedRelationship:
    relationship_id: str
    grammar_id: str
    expression_source: str           # reviewed expression string (compiles to RestrictedExpression)
    output_symbol: str


@dataclass(frozen=True)
class ConceptContract:
    contract_id: str
    version: int
    contract_concept_id: str
    variant: str
    definition: GroundedArtifact
    relationship: NormalizedRelationship
    symbols: tuple[SymbolContract, ...]
    constants: Mapping[str, str] = field(default_factory=dict)          # symbol -> exact value string
    assumptions: tuple[GroundedArtifact, ...] = ()
    applicability_conditions: tuple[GroundedArtifact, ...] = ()
    conventions: tuple[GroundedArtifact, ...] = ()
    expected_interpretations: tuple[GroundedArtifact, ...] = ()
    grounding_status: Authority = "reviewed"

    def symbol(self, name: str) -> SymbolContract:
        for s in self.symbols:
            if s.symbol == name:
                return s
        raise ContractError(f"unknown symbol: {name}")

    @property
    def input_symbols(self) -> tuple[SymbolContract, ...]:
        return tuple(s for s in self.symbols if s.role == "input")

    @property
    def output(self) -> SymbolContract:
        outs = [s for s in self.symbols if s.role == "output"]
        if len(outs) != 1:
            raise ContractError(f"{self.contract_id}: exactly one output symbol required, found {len(outs)}")
        return outs[0]


def compile_contract_descriptor(contract: ConceptContract) -> AuthoredRelationshipDescriptor:
    """Compile the reviewed relationship into a substrate descriptor. Fail-closed: any expression node, symbol,
    unit, or dimension outside the frozen Wave-0 grammar raises `ContractError` before any execution."""
    if contract.grounding_status != "reviewed":
        raise ContractError(f"{contract.contract_id}: v1 executes reviewed contracts only")
    try:
        expression: RestrictedExpression = compile_restricted_expression(
            contract.relationship.expression_source
        )
    except RestrictedExpressionError as exc:
        raise ContractError(f"{contract.contract_id}: relationship not Wave-0 compilable: {exc}") from exc

    declared = {s.symbol for s in contract.symbols}
    constant_names = set(contract.constants)
    referenced = expression_variables(expression)
    undeclared = sorted(referenced - declared - constant_names)
    if undeclared:
        raise ContractError(f"{contract.contract_id}: undeclared symbols {undeclared}")

    output = contract.output
    if contract.relationship.output_symbol != output.symbol:
        raise ContractError(
            f"{contract.contract_id}: relationship output {contract.relationship.output_symbol!r} "
            f"!= symbol-contract output {output.symbol!r}"
        )

    try:
        resolved_inputs = {s.symbol: parse_unit(s.unit) for s in contract.symbols if s.role == "input"}
        authored_constants = tuple(
            AuthoredConstant(
                constant_id=f"{contract.contract_id}:constant:{name}",
                source_row_id=contract.contract_id,
                symbol=name,
                exact_value=Fraction(str(contract.constants[name]))
                * parse_unit(contract.symbol(name).unit).scale_to_canonical,
                unit=contract.symbol(name).unit,
                resolved_unit=parse_unit(contract.symbol(name).unit),
            )
            for name in sorted(constant_names)
        )
        resolved_constants = {c.symbol: c.resolved_unit for c in authored_constants}
        resolved_output = parse_unit(output.unit)
        expression_unit = _expression_unit(expression, {**resolved_inputs, **resolved_constants})
    except (UnitError, ContractError) as exc:
        raise ContractError(f"{contract.contract_id}: unit resolution failed: {exc}") from exc

    if expression_unit.dimensions != resolved_output.dimensions:
        raise ContractError(
            f"{contract.contract_id}: expression dimensions {dict(expression_unit.dimensions)} "
            f"!= output dimensions {dict(resolved_output.dimensions)}"
        )

    symbols = tuple(
        [
            AuthoredSymbol(name=s.symbol, role="input", unit=s.unit, resolved_unit=resolved_inputs[s.symbol])
            for s in contract.input_symbols
        ]
        + [
            AuthoredSymbol(
                name=name,
                role="constant",
                unit=contract.symbol(name).unit,
                resolved_unit=resolved_constants[name],
            )
            for name in sorted(constant_names)
        ]
        + [AuthoredSymbol(name=output.symbol, role="output", unit=output.unit, resolved_unit=resolved_output)]
    )
    return AuthoredRelationshipDescriptor(
        relationship_id=contract.relationship.relationship_id,
        expression=expression,
        symbols=symbols,
        constants=authored_constants,
        domain_constraints=tuple(NonzeroConstraint(d) for d in _denominators(expression)),
        output_symbol=output.symbol,
        output_unit=output.unit,
        resolved_output_unit=resolved_output,
    )
