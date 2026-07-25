"""Offline-only staged cutover demonstration for Milestone A.

This module is deliberately not connected to lesson routing. It exercises the required comparison,
fallback, alert, and quarantine semantics using reviewed FormulaSpec candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Literal

from app.services.examples.runtime_binding.compiler import compile_formula_spec
from app.services.examples.runtime_binding.executor import execute_descriptor
from app.services.examples.trace_adapters.families.formula_engine import FormulaSpec, _num


CutoverMode = Literal["legacy_primary", "substrate_primary"]
SubstrateStatus = Literal["enabled", "shadow_only", "quarantined", "disabled"]


@dataclass(frozen=True)
class RowCutoverState:
    slug: str
    substrate_status: SubstrateStatus = "shadow_only"
    status_version: int = 1
    reason: str = "milestone_a_offline_shadow"


@dataclass(frozen=True)
class CutoverEvent:
    slug: str
    mode: CutoverMode
    outcome: Literal["match", "fallback", "quarantined", "skipped"]
    learner_result: Any
    legacy_result: Any
    substrate_result: Any | None
    mismatch_kind: str | None
    alert_required: bool
    next_state: RowCutoverState


def _exact_inputs(candidate: dict[str, Any]) -> dict[str, int | str]:
    result: dict[str, int | str] = {}
    for key, value in candidate.items():
        if key.startswith("_"):
            continue
        if isinstance(value, bool):
            result[key] = int(value)
        elif isinstance(value, int):
            result[key] = value
        elif isinstance(value, float):
            result[key] = str(value)
        else:
            raise ValueError(f"unsupported scalar candidate value: {key}")
    return result


def run_offline_dual(
    spec: FormulaSpec,
    candidate: dict[str, Any],
    state: RowCutoverState,
    *,
    mode: CutoverMode,
    substrate_runner: Callable[..., Any] = execute_descriptor,
) -> CutoverEvent:
    output = spec.outputs[0]
    legacy_result = spec.compute(candidate)[output.name]
    compiled = compile_formula_spec(spec)
    if state.substrate_status in {"quarantined", "disabled"} or compiled.descriptor is None:
        return CutoverEvent(
            spec.slug, mode, "skipped", legacy_result, legacy_result, None,
            "substrate_unavailable", False, state,
        )
    try:
        substrate_execution = substrate_runner(compiled.descriptor, _exact_inputs(candidate))
        substrate_result = _num(float(substrate_execution.value))
    except Exception as exc:
        # Infrastructure failure is an explicit, observable legacy fallback in either staged mode.
        return CutoverEvent(
            spec.slug, mode, "fallback", legacy_result, legacy_result, None,
            f"substrate_exception:{type(exc).__name__}", True, state,
        )
    if substrate_result != legacy_result:
        quarantined = replace(
            state,
            substrate_status="quarantined",
            status_version=state.status_version + 1,
            reason="substantive_result_mismatch",
        )
        return CutoverEvent(
            spec.slug, mode, "quarantined", legacy_result, legacy_result, substrate_result,
            "displayed_result", True, quarantined,
        )
    learner_result = legacy_result if mode == "legacy_primary" else substrate_result
    return CutoverEvent(
        spec.slug, mode, "match", learner_result, legacy_result, substrate_result, None, False, state,
    )
