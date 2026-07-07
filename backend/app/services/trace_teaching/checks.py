"""C1–C6 deterministic + bounded-judge checks (Q23 §9). Each check names its authoritative basis and returns a
typed CheckResult; C6 is reject-only and injectable (never authors facts).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from . import grammar, numeric

# check status
PASS = "pass"
FAIL = "fail"              # hard
REPAIRABLE = "repairable"
NOT_APPLICABLE = "not_applicable"

# C6 judge verdicts
C6_PASS = "pass"
C6_REJECT = "reject"
C6_UNAVAILABLE = "unavailable"


@dataclass
class CheckResult:
    check: str
    status: str
    detail: str = ""
    offending: Tuple[str, ...] = ()          # tokens/phrases/fact_ids/quantity_ids
    quantity_id: Optional[str] = None
    output_name: Optional[str] = None
    fact_id: Optional[str] = None
    candidate_quantity_ids: Tuple[str, ...] = ()


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


# ── C1 — value containment ───────────────────────────────────────────────────────────────────────────────────
def c1_value_containment(prose: str, step: grammar.Step) -> CheckResult:
    allowed = set()
    for v in step.all_allowed_values():
        n = numeric.canonical_number(str(v))
        if n is not None:
            allowed.add(n)
    invented: List[str] = []
    unrecognized: List[str] = []
    for nt in numeric.extract_numbers(prose):
        if nt.unrecognized:
            unrecognized.append(nt.token)
        elif nt.value not in allowed:
            invented.append(nt.token)
    if unrecognized:
        return CheckResult("C1", FAIL, "unrecognized_numeric_token", tuple(unrecognized))
    if invented:
        return CheckResult("C1", FAIL, "invented_value", tuple(invented))
    return CheckResult("C1", PASS)


# ── C2 — forbidden claims (first-pass; C6 backstops paraphrases) ─────────────────────────────────────────────
def c2_forbidden_claims(prose: str, step: grammar.Step) -> CheckResult:
    low = _norm(prose)
    for fc in step.forbidden_claims:
        pred = fc.forbidden_when or {}
        field_name, equals = pred.get("trace_field"), pred.get("equals")
        holds = field_name is not None and str(step.trace_field_values.get(field_name)) == str(equals)
        if not holds:
            continue
        for phrasing in fc.known_phrasings:
            if _norm(phrasing) in low:
                return CheckResult("C2", FAIL, f"forbidden_claim:{fc.claim_type}", (phrasing,))
    return CheckResult("C2", PASS)


# ── C3 — required facts (repairable; carries fact_id) ────────────────────────────────────────────────────────
def c3_required_facts(field_name: str, prose: str, step: grammar.Step) -> List[CheckResult]:
    low = _norm(prose)
    results: List[CheckResult] = []
    for rf in step.required_facts:
        if field_name not in rf.required_in_fields:
            continue
        matched = any(_norm(r) in low for r in rf.acceptable_renderings)
        if matched:
            results.append(CheckResult("C3", PASS, fact_id=rf.fact_id))
        else:
            results.append(CheckResult("C3", REPAIRABLE, "required_fact_missing", (rf.fact_id,), fact_id=rf.fact_id))
    return results


# ── C4 — unit fidelity per attributed quantity (§10.1 tie-break) ─────────────────────────────────────────────
def c4_unit_fidelity(prose: str, step: grammar.Step) -> CheckResult:
    quantities = step.allowed_quantities
    if not quantities:
        return CheckResult("C4", NOT_APPLICABLE)
    low = _norm(prose)
    for val, unit in numeric.extract_value_unit_pairs(prose):
        if unit is None:
            continue  # a bare magnitude is C1's concern, not C4
        # 1. explicit quantity name in prose + value matches
        by_name = [q for q in quantities
                   if q.name and _norm(q.name) in low and numeric.canonical_number(q.value) == val]
        # 2. (source mapping — not modeled here)  3. unique (value, unit) pair
        by_value_unit = [q for q in quantities
                         if numeric.canonical_number(q.value) == val and numeric.units_equal(q.unit, unit)]
        # value-only (to catch a unit mutation informatively rather than as bare "ambiguous")
        by_value = [q for q in quantities if numeric.canonical_number(q.value) == val]

        cands = by_name or by_value_unit or by_value
        if len(cands) != 1:
            return CheckResult("C4", FAIL, "quantity_attribution_ambiguous",
                               candidate_quantity_ids=tuple(q.quantity_id for q in cands) or
                               tuple(q.quantity_id for q in quantities))
        q = cands[0]
        if not numeric.units_equal(q.unit, unit):
            return CheckResult("C4", FAIL, f"unit_mutation:{unit}!={q.unit}", (unit or "",),
                               quantity_id=q.quantity_id, output_name=q.output_name)
    return CheckResult("C4", PASS)


# ── C5 — operation / action-intent fidelity ─────────────────────────────────────────────────────────────────
def c5_operation(prose: str, contract: Optional[grammar.OperationContract]) -> CheckResult:
    if contract is None:
        return CheckResult("C5", NOT_APPLICABLE)
    low = _norm(prose)
    for intent in contract.forbidden_action_intents:
        if _norm(intent) in low:
            return CheckResult("C5", FAIL, f"forbidden_action:{intent}", (intent,))
    for intent in contract.allowed_action_intents:
        if _norm(intent) in low:
            return CheckResult("C5", PASS, detail=f"intent:{intent}")
    return CheckResult("C5", FAIL, "unmapped_action")


def c5_order(operation: str, position: int, required_operations: Tuple[str, ...]) -> CheckResult:
    """Card position must respect required_operations order (§8)."""
    if not required_operations or operation not in required_operations:
        return CheckResult("C5", NOT_APPLICABLE)
    expected = required_operations.index(operation)
    if position == expected:
        return CheckResult("C5", PASS)
    return CheckResult("C5", FAIL, f"operation_order:{operation}@{position}!={expected}")


# ── C6 — bounded judge (reject-only, injectable, NEVER certifies) ────────────────────────────────────────────
# A judge takes (prose, authoritative_facts) and returns C6_PASS | C6_REJECT | C6_UNAVAILABLE. Default: unavailable.
Judge = Callable[[str, Dict[str, str]], str]


def default_judge(prose: str, authoritative_facts: Dict[str, str]) -> str:
    return C6_UNAVAILABLE


def c6_semantic(prose: str, authoritative_facts: Dict[str, str], judge: Judge = default_judge) -> CheckResult:
    verdict = judge(prose, authoritative_facts)
    if verdict == C6_REJECT:
        return CheckResult("C6", FAIL, "semantic_contradiction")
    if verdict == C6_UNAVAILABLE:
        return CheckResult("C6", NOT_APPLICABLE, "judge_unavailable")
    return CheckResult("C6", PASS)
