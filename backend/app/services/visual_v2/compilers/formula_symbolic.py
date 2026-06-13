"""FormulaSymbolicCompiler — folded FrameState[] -> a formula_symbolic_expression model.

Targets the EXISTING frontend `FormulaVisual.tsx` contract:
  base  = { expression: str, symbols: [{symbol, meaning?, value?}], mode }
  state = { substitution: {sym: val}, transformed_expression: str|null,
            equivalence_chain: [str], active_symbol?, active_expression? }
Serves symbolic derivations (formula substitution, e.g. the quadratic formula).
"""
from __future__ import annotations

from typing import Any

from ..schemas import FrameState, RenderStep, Trace, TraceStep, VisualModel


def compile_formula_symbolic(
    *,
    formula: str,
    symbols: dict[str, Any],
    frames: list[FrameState],
    trace_steps: list[TraceStep],
    profile: dict[str, Any],
    mode: str,
    model_id: str,
    example_id: str = "",
    trace_id: str = "",
) -> tuple[VisualModel, list[RenderStep]]:
    base = {
        "expression": formula,
        "symbols": [{"symbol": k, "value": str(v)} for k, v in symbols.items()],
        "mode": mode,
    }

    model_frames = []
    for i, frame in enumerate(frames):
        after = frame["state_after"]
        substituted = after.get("substituted")
        computations = list(after.get("computations") or [])
        result = after.get("result")
        model_frames.append({
            "index": i,
            "state": {
                "substitution": {k: str(v) for k, v in symbols.items()} if substituted else {},
                "transformed_expression": result or substituted or formula,
                "equivalence_chain": [f"{c['label']}: {c['calc']}" for c in computations],
                "active_expression": bool(result),
            },
            "highlights": {},
            "annotations": [],
            "selectable_elements": [],
            "transitions": [],
        })

    model = VisualModel(
        id=model_id,
        base_type=str(profile.get("base_type", "formula_symbolic_expression")),
        mode=mode,
        example_id=example_id,
        trace_id=trace_id,
        base=base,
        frames=model_frames,
        element_catalog=[],
    )

    render_steps = [
        RenderStep(
            step_index=int(frame.get("step_index", i)),
            frame_index=i,
            trace_step_id=str((trace_steps[i] if i < len(trace_steps) else {}).get("trace_step_id", f"s{i}")),
            primary_change=str((trace_steps[i] if i < len(trace_steps) else {}).get("primary_change", "")),
            caption=str((trace_steps[i] if i < len(trace_steps) else {}).get("learner_should_notice", "")),
        )
        for i, frame in enumerate(frames)
    ]
    return model, render_steps


def compile_from_trace(
    *,
    trace: Trace,
    frames: list[FrameState],
    formula: str,
    symbols: dict[str, Any],
    profile: dict[str, Any],
    mode: str,
    model_id: str,
) -> tuple[VisualModel, list[RenderStep]]:
    return compile_formula_symbolic(
        formula=formula, symbols=symbols, frames=frames,
        trace_steps=list(trace.get("steps") or []),
        profile=profile, mode=mode, model_id=model_id,
        example_id=str(trace.get("example_id", "")), trace_id=str(trace.get("trace_id", "")),
    )
