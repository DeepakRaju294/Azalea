"""L3 — sibling-trace consistency (Q24 §3, deterministic).

Two parts:
1. BINDING classification (the novel Q24 contribution — never bind by proximity): a general rule/definition must
   NOT be checked against a concrete example's values just because it sits next to it. Only a span that EXPLICITLY
   references an example value/operation/result binds to that sibling fact.
2. The consistency checks themselves REUSE the shared trace-to-teaching module (Q23): C1 value containment · C2
   forbidden claims · C4 unit fidelity · C5 operation. L3 builds a sibling Step from the referenced facts and calls
   `trace_teaching.validator.run_checks`. C2/C5 are exercised only when the sibling step declares forbidden_claims /
   an operation_contract; otherwise the shared checks return `not_applicable` (nothing to check, never a silent pass).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from app.services.trace_teaching import checks as _tt_checks
from app.services.trace_teaching import grammar as _tt_grammar
from app.services.trace_teaching import validator as _ttv

# binding classes
EXPLICIT_EXAMPLE_REFERENCE = "explicit_example_reference"
TOPIC_GENERAL_RULE = "topic_general_rule"
MIXED = "mixed"

# results
PASS = "pass"
FAIL = "fail"
NOT_APPLICABLE = "not_applicable"

_EXAMPLE_MARKERS = ("in this example", "in the example", "our example", "here we", "here the",
                    "above,", "as shown", "in this case")
_GENERAL_MARKERS = ("in general", "for any", "for all", "relates", "is defined as", "in every")


@dataclass(frozen=True)
class SiblingFact:
    trace_id: str
    trace_step_id: str
    output_name: str            # e.g. "net force"
    value: str                  # normalized numeric string, e.g. "20"
    unit: Optional[str] = None  # e.g. "N"


@dataclass(frozen=True)
class L3Result:
    binding_class: str
    c1_values: str              # PASS | FAIL | NOT_APPLICABLE  (shared Q23 C1)
    c2_forbidden: str           # shared Q23 C2 (n/a unless the sibling step declares forbidden_claims)
    c4_units: str               # shared Q23 C4
    c5_action: str              # shared Q23 C5 (n/a unless action_bearing + an operation_contract)
    conflicting_facts: Tuple[str, ...] = ()

    @property
    def status(self) -> str:
        return FAIL if FAIL in (self.c1_values, self.c2_forbidden, self.c4_units, self.c5_action) else PASS


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def classify_binding(span_text: str, sibling_facts: Tuple[SiblingFact, ...]) -> str:
    """Decide whether the span binds to example values. Default is topic_general_rule (never bind by proximity)."""
    low = span_text.lower()
    references_example = any(m in low for m in _EXAMPLE_MARKERS)
    # a span that cites an example-specific value (a number matching a sibling fact) also references the example
    span_nums = set(_NUM_RE.findall(span_text))
    references_example = references_example or any(f.value in span_nums for f in sibling_facts)
    is_general = any(m in low for m in _GENERAL_MARKERS)

    if references_example and is_general:
        return MIXED
    if references_example:
        return EXPLICIT_EXAMPLE_REFERENCE
    return TOPIC_GENERAL_RULE


def _sibling_step(sibling_facts, forbidden_claims, operation_contract, trace_field_values):
    return _tt_grammar.Step(
        id="sibling", operation="",
        allowed_values=tuple(f.value for f in sibling_facts),
        allowed_quantities=tuple(_tt_grammar.AllowedQuantity(
            quantity_id=f"{f.trace_id}.{f.trace_step_id}.{f.output_name}",
            name=f.output_name, value=f.value, unit=f.unit, output_name=f.output_name)
            for f in sibling_facts),
        forbidden_claims=tuple(forbidden_claims),
        operation_contract=operation_contract,
        trace_field_values=dict(trace_field_values or {}),
    )


def check_sibling_consistency(
    span_text: str,
    sibling_facts: Tuple[SiblingFact, ...],
    *,
    forbidden_claims: Tuple = (),
    operation_contract=None,
    trace_field_values: Optional[dict] = None,
    action_bearing: bool = False,
) -> L3Result:
    """Reuse the shared Q23 checks (C1/C2/C4/C5) against ONLY the facts a span explicitly references.

    A general rule/definition is never bound to a neighboring example's values (returns not_applicable). An explicit
    example reference builds a sibling Step and delegates to trace_teaching.validator.run_checks."""
    binding = classify_binding(span_text, sibling_facts)

    if binding == TOPIC_GENERAL_RULE:
        return L3Result(binding, NOT_APPLICABLE, NOT_APPLICABLE, NOT_APPLICABLE, NOT_APPLICABLE)

    step = _sibling_step(sibling_facts, forbidden_claims, operation_contract, trace_field_values)
    r = _ttv.run_checks(span_text, step, field_name="sibling", prose_bearing=True,
                        action_bearing=action_bearing, run_c6=False)

    def _st(cr):
        return cr.status if cr is not None else NOT_APPLICABLE

    conflicts = tuple(f"{f.check}:{f.detail}" for f in r.failures)
    return L3Result(binding, _st(r.c1), _st(r.c2), _st(r.c4), _st(r.c5), conflicts)
