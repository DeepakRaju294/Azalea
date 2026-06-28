"""Reason→extract trace source (WORKED_EXAMPLE_REASONING_SPEC.md §8/§9, Phase 2/3).

For non-executor classes (proofs, mechanisms, open-ended) there is no reference run, so the trace comes
from the model: (1a) reason in FREE PROSE (no schema, so reasoning isn't suppressed), then (1b) EXTRACT a
structured ContractTrace from that prose (the derivability rule — values must follow from input /
conventions / prior state / an explicit operation). Both calls are injected, so this is testable offline;
it returns None (defer) when unavailable. Stage 2 (verifiers.verify_via_critic) checks the result.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from .trace_contract import ContractTrace, Step

ModelFn = Callable[[dict[str, str]], Optional[Any]]


def build_reason_payload(topic: dict[str, Any], example_input: Any) -> dict[str, str]:
    return {
        "system": ("You are a precise tutor. Solve ONE concrete instance completely, step by step, showing "
                   "your work. Reach and state the final answer. Verify it satisfies the task's defining "
                   "property before finishing. Free-form prose only — no JSON, no schema."),
        "user": f"Topic: {topic.get('title') or topic.get('name')}\nInstance: {example_input}",
    }


def build_extract_payload(topic: dict[str, Any], solution_text: str) -> dict[str, str]:
    return {
        "system": ("Extract a canonical machine-checkable trace from the solution below. Every value must be "
                   "derivable from the input, conventions, the prior state, or an explicit operation — it "
                   "need not appear literally in the prose. "
                   'Return ONLY JSON: {"problem","initial_state","final_answer","conventions",'
                   '"invariants":[{"id","scope","statement"}],"steps":[{"id","operation","inputs",'
                   '"prior_state","state_after","reason","facts":{"allowed_values","required_facts",'
                   '"forbidden_claims"}}]}'),
        "user": f"Topic: {topic.get('title')}\nSOLUTION:\n{solution_text}",
    }


def _to_contract_trace(out: dict[str, Any]) -> Optional[ContractTrace]:
    try:
        steps = [Step(
            id=str(s["id"]), operation=str(s.get("operation", "")),
            prior_state=s.get("prior_state") or {}, state_after=s.get("state_after") or {},
            inputs=s.get("inputs") or {}, decision=str(s.get("decision", "")), reason=str(s.get("reason", "")),
            facts=s.get("facts") or {}, expected_visible_result=str(s.get("expected_visible_result", "")),
        ) for s in (out.get("steps") or [])]
        if not steps:
            return None
        return ContractTrace(
            problem=str(out.get("problem", "")), conventions=out.get("conventions") or {},
            initial_state=out.get("initial_state") or {}, final_answer=out.get("final_answer"),
            steps=steps, invariants=out.get("invariants") or [],
            required_cases=out.get("required_cases") or [], case_evidence=out.get("case_evidence") or {},
            provenance={"source": "reason_extract", "verification_level": "soft"},
            solution_text=str(out.get("solution_text", "")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def produce_via_reason_extract(topic: dict[str, Any], example_input: Any, *,
                               reason_fn: ModelFn, extract_fn: ModelFn) -> Optional[ContractTrace]:
    prose = reason_fn(build_reason_payload(topic, example_input))
    if not prose:
        return None
    text = prose if isinstance(prose, str) else (prose.get("solution_text") or prose.get("text") or "")
    out = extract_fn(build_extract_payload(topic, str(text)))
    if not isinstance(out, dict):
        return None
    return _to_contract_trace(out)
