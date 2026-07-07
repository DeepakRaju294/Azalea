"""Trace-to-teaching validator (Q23 §10) — run C1–C5, collect EVERY failure, run C6 only if clean, decide.

`run_checks` validates one prose span against its step (the unit Q24's L3 reuses). `validate_card` runs it across a
card's prose-bearing fields with §10.1 field scope. The result is layered so deterministic facts and the judge
never blur, and a retry gets the complete failure set.
"""
from __future__ import annotations

from dataclasses import dataclass, field as _field
from typing import Dict, List, Optional, Tuple

from . import checks, grammar

# decision
PASS = "pass"
RETRY = "retry"
WITHHOLD = "withhold"

# failure class
PRIMARY = "primary"
INDEPENDENT = "independent"
SUPPRESSED = "suppressed"


@dataclass
class Failure:
    check: str
    failure_class: str
    field: str
    detail: str
    trace_step_id: Optional[str] = None
    quantity_id: Optional[str] = None
    output_name: Optional[str] = None
    fact_id: Optional[str] = None
    candidate_quantity_ids: Tuple[str, ...] = ()


@dataclass
class TraceTeachingValidationResult:
    c1: Optional[checks.CheckResult] = None
    c2: Optional[checks.CheckResult] = None
    c3: List[checks.CheckResult] = _field(default_factory=list)
    c4: Optional[checks.CheckResult] = None
    c5: Optional[checks.CheckResult] = None
    c6: Optional[checks.CheckResult] = None
    decision: str = PASS
    failures: List[Failure] = _field(default_factory=list)
    telemetry: Dict[str, object] = _field(default_factory=dict)

    @property
    def hard_failed(self) -> bool:
        return any(f.check in ("C1", "C2", "C4", "C5", "C6") for f in self.failures
                   if f.failure_class != checks.NOT_APPLICABLE)


def run_checks(
    prose: str,
    step: grammar.Step,
    *,
    field_name: str = "",
    prose_bearing: bool = True,
    action_bearing: bool = False,
    required_field: bool = False,
    judge: checks.Judge = checks.default_judge,
    run_c6: bool = True,
    trace_id: str = "",
) -> TraceTeachingValidationResult:
    result = TraceTeachingValidationResult()
    failures: List[Failure] = []

    c1 = checks.c1_value_containment(prose, step) if prose_bearing else checks.CheckResult("C1", checks.NOT_APPLICABLE)
    c2 = checks.c2_forbidden_claims(prose, step)
    c4 = checks.c4_unit_fidelity(prose, step) if prose_bearing else checks.CheckResult("C4", checks.NOT_APPLICABLE)
    c5 = (checks.c5_operation(prose, step.operation_contract) if action_bearing
          else checks.CheckResult("C5", checks.NOT_APPLICABLE))
    c3_list = checks.c3_required_facts(field_name, prose, step) if required_field else []

    result.c1, result.c2, result.c4, result.c5, result.c3 = c1, c2, c4, c5, c3_list

    # a field whose math won't parse (C1 unrecognized) SUPPRESSES C3 on that field (§10)
    c1_parse_failure = c1.status == checks.FAIL and c1.detail == "unrecognized_numeric_token"

    for cr in (c1, c2, c4, c5):
        if cr.status == checks.FAIL:
            failures.append(Failure(cr.check, PRIMARY if cr.check == "C1" else INDEPENDENT, field_name,
                                    cr.detail, trace_step_id=step.id, quantity_id=cr.quantity_id,
                                    output_name=cr.output_name, candidate_quantity_ids=cr.candidate_quantity_ids))
    for cr in c3_list:
        if cr.status == checks.REPAIRABLE:
            cls = SUPPRESSED if c1_parse_failure else INDEPENDENT
            failures.append(Failure("C3", cls, field_name, cr.detail, trace_step_id=step.id, fact_id=cr.fact_id))

    hard_det = any(f.check in ("C1", "C2", "C4", "C5") and f.failure_class != SUPPRESSED for f in failures)

    # C6 runs ONLY if no unsuppressed hard deterministic failure
    if run_c6 and not hard_det:
        c6 = checks.c6_semantic(prose, step.state_after, judge=judge)
        result.c6 = c6
        if c6.status == checks.FAIL:
            failures.append(Failure("C6", PRIMARY, field_name, c6.detail, trace_step_id=step.id))
    else:
        result.c6 = checks.CheckResult("C6", checks.NOT_APPLICABLE, "skipped_deterministic_failure" if hard_det
                                       else "not_run")

    result.failures = failures
    if any(f.check in ("C1", "C2", "C4", "C5", "C6") for f in failures):
        result.decision = WITHHOLD
    elif any(f.check == "C3" and f.failure_class != SUPPRESSED for f in failures):
        result.decision = RETRY
    else:
        result.decision = PASS

    result.telemetry = {
        "trace_id": trace_id, "trace_step_id": step.id, "operation": step.operation,
        "field": field_name, "decision": result.decision,
        "primary_failure": failures[0].check if failures else None,
        "failure_checks": [f.check for f in failures],
    }
    return result
