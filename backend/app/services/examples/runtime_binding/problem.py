"""Neutral structured problem statement (spec §5.8, §5.10).

The authoritative problem is STRUCTURED: target symbol, requested operation, display unit, and given/assumption
refs. `question_display_text` is a deterministic PURE-SUBSTITUTION rendering of those fields (no evaluation, no
nested templates) and is validated against them — it can never be the source of target/operation/unit identity.
Milestone B uses only the grammar's neutral template; contextual scenario templates are post-v1.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from app.services.examples.runtime_binding.binding import ValidatedBinding
from app.services.examples.runtime_binding.generation import GeneratedInstance


class ProblemError(ValueError):
    pass


@dataclass(frozen=True)
class ProblemStatement:
    problem_statement_id: str
    template_id: str
    given_refs: tuple[str, ...]
    target_symbol: str
    requested_operation: str
    requested_display_unit: str
    visible_assumption_refs: tuple[str, ...]
    question_display_text: str


def build_problem_statement(binding: ValidatedBinding, instance: GeneratedInstance) -> ProblemStatement:
    contract = binding.contract
    visible = instance.visible_fractions()
    output = contract.output
    given_clause = ", ".join(
        f"{s.symbol} = {visible[s.symbol]} {s.unit}".rstrip() for s in contract.input_symbols
    )
    # neutral pure-substitution template: no scenario prose, no evaluation
    question = f"Given {given_clause}, find {output.meaning} ({output.symbol}) in {output.unit}.".replace(" in .", ".")
    stmt = ProblemStatement(
        problem_statement_id=f"{contract.contract_id}:{instance.instance_digest[:12]}",
        template_id="neutral_direct_formula_v1",
        given_refs=tuple(s.symbol for s in contract.input_symbols),
        target_symbol=output.symbol,
        requested_operation="compute",
        requested_display_unit=output.unit,
        visible_assumption_refs=tuple(
            a.artifact_id for a in (*contract.assumptions, *contract.applicability_conditions)
        ),
        question_display_text=question,
    )
    validate_problem_statement(stmt, binding, instance)
    return stmt


def validate_problem_statement(
    stmt: ProblemStatement, binding: ValidatedBinding, instance: GeneratedInstance
) -> None:
    """Display text must be faithful to the structured fields (spec §5.10): it names the target and every
    given, and requests the declared unit. It must never request a different target/unit."""
    text = stmt.question_display_text
    output = binding.contract.output
    if stmt.target_symbol != output.symbol:
        raise ProblemError(f"target {stmt.target_symbol!r} != contract output {output.symbol!r}")
    if stmt.requested_display_unit != output.unit:
        raise ProblemError("requested display unit differs from contract output unit")
    if f"({output.symbol})" not in text:
        raise ProblemError("display text does not name the target symbol")
    visible = instance.visible_fractions()
    for symbol in stmt.given_refs:
        if f"{symbol} = {visible[symbol]}" not in text:
            raise ProblemError(f"display text omits given {symbol}")
    # the target must not appear as a supplied given (it is the unknown)
    if f"{output.symbol} = " in text:
        raise ProblemError("display text supplies the unknown as a given")
