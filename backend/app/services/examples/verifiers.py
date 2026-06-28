"""Stage-2 verifiers (WORKED_EXAMPLE_REASONING_SPEC.md §10). A verifier proves a ContractTrace is
correct and returns the FIRST illegal transition for targeted retry.

  * `verify_arithmetic` — HARD where evaluable: re-applies each step and checks value preservation.
  * `verify_via_critic` — SOFT: an injected LLM critic judges each transition (proofs / open-ended).

Deterministic adapters whose trace came from their own reference run don't need a verifier (the
structural gate is sufficient); these cover the non-reference and soft classes.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from .trace_contract import ContractTrace, VerifyResult

CriticFn = Callable[[dict[str, Any]], Optional[dict[str, Any]]]


def verify_arithmetic(trace: ContractTrace) -> VerifyResult:
    """Re-apply each `a op b = result` step and confirm the expression's value never changes."""
    from .trace_adapters.families.formula import _apply, _eval
    init = (trace.initial_state or {}).get("tokens")
    target = _eval(init) if init else None
    for s in trace.steps:
        a, op, b, res = (s.inputs.get(k) for k in ("a", "op", "b", "result"))
        if None in (a, op, b) or _apply(a, op, b) != res:
            return VerifyResult(False, {"id": s.id, "reason": f"{a} {op} {b} != {res}"})
        toks = (s.state_after or {}).get("tokens")
        if toks and target is not None and _eval(toks) != target:
            return VerifyResult(False, {"id": s.id, "reason": "step did not preserve the expression value"})
    return VerifyResult(True)


def build_critic_payload(trace: ContractTrace) -> dict[str, str]:
    import json
    steps = [{"id": s.id, "operation": s.operation, "prior_state": s.prior_state,
              "state_after": s.state_after, "reason": s.reason} for s in trace.steps]
    return {
        "system": ("You are an independent verifier. Given a problem and a step-by-step trace, find the "
                   "FIRST step whose transition is NOT validly justified by its prior state. "
                   'Return ONLY JSON: {"illegal_step": {"id": "...", "reason": "..."}} or {"illegal_step": null}.'),
        "user": f"PROBLEM: {trace.problem}\nSTEPS: {json.dumps(steps, default=str)}",
    }


def verify_via_critic(trace: ContractTrace, *, critic_fn: CriticFn) -> VerifyResult:
    """SOFT verification for proof / open-ended classes. A `None` critic result (offline) does NOT block —
    it flags low confidence; an explicit illegal_step blocks. Never claims 'verified' like a hard pass."""
    out = critic_fn(build_critic_payload(trace))
    if out is None:
        return VerifyResult(True, errors=["critic_unavailable_soft_pass"])
    bad = out.get("illegal_step")
    if bad:
        return VerifyResult(False, {"id": bad.get("id", ""), "reason": bad.get("reason", "")})
    return VerifyResult(True)
