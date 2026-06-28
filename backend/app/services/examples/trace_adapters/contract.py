"""Adapter contract enforcement (ADAPTER_CONTRACT.md, repo root).

Two conformance levels (see the doc):
  * `adapter_contract_violations(adapter)` — the **[now]** bar (L0). Empty = conforms; the machine definition
    of "done" today. Runs a Stage-0 trace and checks the section-A items the current adapters expose, plus
    `structural_invariants == []`.
  * `adapter_c1_gaps(adapter)` — informational list of missing **[C1]** items (the raw→teaching layer split,
    `TeachingTracePolicy`, structured predicate facts). Not yet failing — it tracks progress toward C1 so
    these flip from "documented" to "enforced" when the adapters are upgraded.

`tests/test_adapter_conformance.py` runs both over every registered adapter.
"""
from __future__ import annotations

from typing import Any

from ..trace_contract import structural_invariants

# Section A — the methods/attributes every adapter must expose (statically).
_REQUIRED_CALLABLES = (
    "candidates", "reference", "is_teaching_trace", "states_equivalent",
    "final_answer_entails", "invariant_holds", "validate_step_shape", "validate_prose_claims",
)
_FACT_KEYS = ("allowed_values", "required_facts", "forbidden_claims")


def adapter_contract_violations(adapter: Any) -> list[str]:
    """Return the contract items `adapter` fails (empty list = fully conforms). See ADAPTER_CONTRACT.md."""
    v: list[str] = []

    # 1 — identity
    if not isinstance(getattr(adapter, "slug", None), str) or not getattr(adapter, "slug", ""):
        v.append("1: missing/empty `slug`")
    if not isinstance(getattr(adapter, "version", None), int):
        v.append("1: missing int `version`")
    # methods (2,3,8,9,10,11,13)
    for m in _REQUIRED_CALLABLES:
        if not callable(getattr(adapter, m, None)):
            v.append(f"missing method `{m}`")
    if v:
        return v  # can't exercise reference() without these

    # Produce a Stage-0 teaching trace (covers required cases) — done lazily to avoid an import cycle.
    from ..trace_pipeline import select_instance
    try:
        trace = select_instance(adapter, seed=7)
    except Exception as exc:  # noqa: BLE001
        return v + [f"3/8: reference()/is_teaching_trace raised: {exc!r}"]
    if trace is None:
        return v + ["2/8: Stage-0 found no teaching instance (candidates too weak or gate too tight)"]

    # 5 — conventions declared
    if not isinstance(trace.conventions, dict) or not trace.conventions:
        v.append("5: trace.conventions is empty (declared variant missing)")
    # 7 — required cases + evidence
    if not trace.required_cases:
        v.append("7: no required_cases")
    for c in trace.required_cases:
        if not trace.case_evidence.get(c):
            v.append(f"7: required case {c!r} has no case_evidence")
    # 10 — invariants
    if not trace.invariants:
        v.append("10: no invariants declared")
    # 15 — final answer
    if trace.final_answer is None:
        v.append("15: final_answer is None")
    if not trace.steps:
        v.append("3: trace has no steps")

    # 4/6/12/14 — per-step shape (sample first + last step)
    for s in ([trace.steps[0], trace.steps[-1]] if trace.steps else []):
        if not isinstance(s.prior_state, dict) or not isinstance(s.state_after, dict):
            v.append(f"4: {s.id}: prior_state/state_after must be dicts")
        if not s.operation:
            v.append(f"6: {s.id}: missing `operation` (the step unit)")
        if not (s.decision or s.reason):
            v.append(f"6: {s.id}: missing decision/reason")
        if not (s.visual_state or {}).get("kind"):
            v.append(f"14: {s.id}: visual_state missing `kind`")
        facts = s.facts or {}
        for k in _FACT_KEYS:
            if k not in facts:
                v.append(f"12: {s.id}: facts missing `{k}`")

    # §0 — if the adapter declares an ExampleSpec, every step must be one declared STAGE instance
    # ("each step falls within the declared stages"). Enforced once an adapter is C1-upgraded; a no-op today.
    spec = getattr(adapter, "example_spec", None)
    if spec is not None:
        transition = _spec_field(spec, "transition") or {}
        stages = set((transition.get("stages") or transition.get("operations") or {}).keys())
        if stages:
            stray = {s.operation for s in trace.steps} - stages
            if stray:
                v.append(f"0: step operations {sorted(stray)} not in declared stages {sorted(stages)}")
        # declared per-instance coverage must be a subset of what the trace actually declares
        me = set(_spec_field(spec, "must_exercise") or [])
        missing = me - set(trace.required_cases)
        if missing:
            v.append(f"0: example_spec.must_exercise {sorted(missing)} not in trace.required_cases")

    # the produced trace must pass its own structural gate (chain, endpoint, case evidence, step shape)
    errs = structural_invariants(trace, adapter)
    if errs:
        v.append(f"structural gate: {errs[:3]}")
    return v


def _spec_field(spec: Any, name: str) -> Any:
    """Read a field from an ExampleSpec whether it's a dict or a dataclass/object."""
    if isinstance(spec, dict):
        return spec.get(name)
    return getattr(spec, name, None)


# --- [C1] target gaps (informational, not yet failing) ------------------------------------------

_C1_METHODS = ("run_reference", "build_teaching_trace", "required_transition_ids")
_C1_ATTRS = {
    "example_spec": "item 0: missing `example_spec` (the declarative envelope: input/must_exercise/transition/terminal)",
    "teaching_trace_policy": "item 5: missing `teaching_trace_policy` (TeachingTracePolicy)",
}


def adapter_c1_gaps(adapter: Any) -> list[str]:
    """List the [C1] items `adapter` does not yet provide (ADAPTER_CONTRACT.md §A items 3/4/5/12). Empty
    once the adapter is C1-upgraded. Informational — does not fail conformance."""
    gaps: list[str] = []
    for m in _C1_METHODS:
        if not callable(getattr(adapter, m, None)):
            gaps.append(f"item 3/4/9: missing C1 method `{m}` (raw->teaching layer / stable ids)")
    for a, msg in _C1_ATTRS.items():
        if getattr(adapter, a, None) is None:
            gaps.append(msg)
    try:
        from ..trace_pipeline import select_instance
        trace = select_instance(adapter, seed=7)
        if trace and trace.steps:
            req = (trace.steps[0].facts or {}).get("required_facts") or []
            if req and all(isinstance(x, str) for x in req):
                gaps.append("item 12: facts are string lists (C1: structured predicate objects)")
    except Exception:  # noqa: BLE001
        pass
    return gaps
