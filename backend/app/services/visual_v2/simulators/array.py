"""Array simulators — binary search (VISUAL_SYSTEM_SPEC §6.1, §11.2).

The simulator owns the delta timeline. Each probe is a `compare` step (set the
midpoint + record the three-way decision); if not equal, a following
`discard_range` step shrinks the active range and marks the eliminated half. The
final equal probe carries `mark_found`. Uses the binary-search delta vocabulary —
the same DeltaFoldEngine renders it, proving the vocabulary generalises.
"""
from __future__ import annotations

from typing import Any

from ..schemas import (
    DELTA_SCHEMA_VERSION,
    SIMULATOR_VERSION,
    VISUAL_SPEC_VERSION,
    CanonicalExample,
    Trace,
    TraceStep,
)


def _trace(example: CanonicalExample, low: int, high: int, steps: list[TraceStep]) -> Trace:
    return Trace(
        trace_id=f"{example.get('example_id', 'ex')}:binary_search",
        example_id=str(example.get("example_id", "")),
        trace_source="deterministic_simulator",
        initial_state={"low": low, "high": high, "mid": None, "discarded": [], "found": None},
        steps=steps,
        visual_spec_version=VISUAL_SPEC_VERSION,
        delta_schema_version=DELTA_SCHEMA_VERSION,
        simulator_version=SIMULATOR_VERSION,
    )


def simulate_binary_search(example: CanonicalExample) -> Trace:
    """One card per PROBE CYCLE: each step takes the midpoint of the current range,
    compares it to the target, and (in the same card) states how the range updates.
    A leading setup step shows the whole array at rest — so a learner sees whole
    cycles ('mid → compare → narrow'), not isolated micro-actions."""
    array = list((example.get("base_structure") or {}).get("array") or [])
    target = (example.get("input") or {}).get("target")
    low, high = 0, len(array) - 1
    steps: list[TraceStep] = []

    # Setup: the full array, no midpoint yet.
    steps.append(
        TraceStep(
            step_index=0,
            trace_step_id="s0",
            kind="initialize",
            delta={"set_pointer": {"low": low, "high": high}},
            primary_change="set_pointer",
            learner_should_notice=(
                f"Search the whole sorted array for {target}: low={low}, high={high}."
            ),
        )
    )

    while low <= high:
        mid = (low + high) // 2
        a_mid = array[mid]
        outcome = "equal" if a_mid == target else ("less_than" if a_mid < target else "greater_than")
        if outcome == "equal":
            delta = {"set_pointer": {"low": low, "high": high, "mid": mid}, "mark_mid": mid, "mark_found": mid}
            notice = f"Range [{low}..{high}], mid={mid}: a[{mid}]={a_mid} == {target} → found at index {mid}."
        elif outcome == "less_than":
            delta = {"set_pointer": {"low": low, "high": high, "mid": mid}, "mark_mid": mid}
            notice = f"Range [{low}..{high}], mid={mid}: a[{mid}]={a_mid} < {target} → search right, low becomes {mid + 1}."
        else:
            delta = {"set_pointer": {"low": low, "high": high, "mid": mid}, "mark_mid": mid}
            notice = f"Range [{low}..{high}], mid={mid}: a[{mid}]={a_mid} > {target} → search left, high becomes {mid - 1}."
        steps.append(
            TraceStep(
                step_index=len(steps),
                trace_step_id=f"s{len(steps)}",
                kind="compare",
                delta=delta,
                primary_change="mark_mid",
                decision={
                    "condition": f"a[{mid}]={a_mid} vs target {target}",
                    "evaluated_to": outcome,
                    "reason": {"equal": "match", "less_than": "go right", "greater_than": "go left"}[outcome],
                },
                learner_should_notice=notice,
            )
        )
        if outcome == "equal":
            break
        if outcome == "less_than":
            low = mid + 1
        else:
            high = mid - 1

    return _trace(example, 0, len(array) - 1, steps)
