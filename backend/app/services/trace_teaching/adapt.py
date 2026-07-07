"""Adapt the live example-pipeline trace (examples/trace_contract.Step) into the typed Q23 grammar.

Duck-typed (reads attributes, imports nothing heavy) so the shadow path stays landmine-safe. The live `facts` dict
is loose today; the §§6-8 typed shapes (acceptable_renderings, structural forbidden_claims, operation contract)
are engine-side additions — so C2/C3/C5 map only when the engine already supplies the structured form, else they
are simply absent (the shadow measures what the trace actually declares, no invented structure).
"""
from __future__ import annotations

from typing import Any, Dict

from . import grammar


def step_from_live(s: Any) -> grammar.Step:
    facts: Dict[str, Any] = getattr(s, "facts", None) or {}

    forbidden = []
    for c in facts.get("forbidden_claims", []) or []:
        if isinstance(c, dict) and c.get("known_phrasings"):
            forbidden.append(grammar.ForbiddenClaim(
                claim_type=str(c.get("claim_type", "")), subject=str(c.get("subject", "")),
                forbidden_when=dict(c.get("forbidden_when") or {}),
                known_phrasings=tuple(str(p) for p in (c.get("known_phrasings") or ()))))

    quantities = []
    for q in facts.get("allowed_quantities", []) or []:
        if isinstance(q, dict) and q.get("value") is not None:
            quantities.append(grammar.AllowedQuantity(
                quantity_id=str(q.get("quantity_id") or q.get("name") or ""),
                name=str(q.get("name") or ""), value=str(q.get("value")),
                unit=(str(q["unit"]) if q.get("unit") is not None else None),
                output_name=(str(q["output_name"]) if q.get("output_name") else None),
                fact_id=(str(q["fact_id"]) if q.get("fact_id") else None)))

    required = []
    for rf in facts.get("required_facts", []) or []:
        if isinstance(rf, dict) and rf.get("fact_id") and rf.get("acceptable_renderings"):
            required.append(grammar.RequiredFact(
                fact_id=str(rf["fact_id"]), kind=str(rf.get("kind", "")), subject=str(rf.get("subject", "")),
                relation=str(rf.get("relation", "")), value=str(rf.get("value", "")),
                acceptable_renderings=tuple(str(r) for r in rf["acceptable_renderings"]),
                required_in_fields=tuple(str(f) for f in (rf.get("required_in_fields") or ()))))

    state_after = {str(k): str(v) for k, v in (getattr(s, "state_after", None) or {}).items()}

    return grammar.Step(
        id=str(getattr(s, "id", "")),
        operation=str(getattr(s, "operation", "")),
        expected_visible_result=str(getattr(s, "expected_visible_result", "") or ""),
        state_after=state_after,
        allowed_values=tuple(str(x) for x in (facts.get("allowed_values") or [])),
        allowed_quantities=tuple(quantities),
        required_facts=tuple(required),
        forbidden_claims=tuple(forbidden),
        trace_field_values=state_after,   # forbidden_when predicates key off state fields
        operation_contract=None,          # loose today — engine-side addition
    )


def steps_by_id(trace: Any) -> Dict[str, grammar.Step]:
    """Map a live trace (with `.steps`) → {step_id: typed Step}."""
    steps = getattr(trace, "steps", None) or []
    return {str(getattr(s, "id", "")): step_from_live(s) for s in steps}
