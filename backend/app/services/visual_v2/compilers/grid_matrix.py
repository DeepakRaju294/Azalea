"""GridMatrixCompiler — folded FrameState[] -> a grid_matrix_diagram model.

Targets the frontend `GridMatrixVisual.tsx` contract:
  base  = { cells:[[str]], row_labels, column_labels, mode }
  state = { active_cell:[r,c], completed_cells:[[r,c]], cell_values:{"r,c":str},
            dependency_arrows:[{from:[r,c],to:[r,c]}], highlighted_row, highlighted_column }
Serves DP tables / matrices / grids.
"""
from __future__ import annotations

from typing import Any

from ..schemas import FrameState, RenderStep, Trace, TraceStep, VisualModel


def compile_grid_matrix(
    *,
    rows: int,
    cols: int,
    frames: list[FrameState],
    trace_steps: list[TraceStep],
    profile: dict[str, Any],
    mode: str,
    model_id: str,
    example_id: str = "",
    trace_id: str = "",
) -> tuple[VisualModel, list[RenderStep]]:
    base = {
        "cells": [["" for _ in range(cols)] for _ in range(rows)],
        "row_labels": [str(i) for i in range(rows)],
        "column_labels": [str(j) for j in range(cols)],
        "mode": mode,
    }
    model_frames = [
        {
            "index": i,
            "state": {
                "active_cell": frame["state_after"].get("active_cell"),
                "completed_cells": list(frame["state_after"].get("completed_cells") or []),
                "cell_values": dict(frame["state_after"].get("cell_values") or {}),
                "dependency_arrows": list(frame["state_after"].get("dependency_arrows") or []),
                "highlighted_row": None,
                "highlighted_column": None,
            },
            "highlights": {},
            "annotations": [],
            "selectable_elements": [],
            "transitions": [],
        }
        for i, frame in enumerate(frames)
    ]

    model = VisualModel(
        id=model_id,
        base_type=str(profile.get("base_type", "grid_matrix_diagram")),
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
            primary_change="fill_cell",
            caption=str((trace_steps[i] if i < len(trace_steps) else {}).get("learner_should_notice", "")),
        )
        for i, frame in enumerate(frames)
    ]
    return model, render_steps


def compile_from_trace(
    *,
    trace: Trace,
    frames: list[FrameState],
    rows: int,
    cols: int,
    profile: dict[str, Any],
    mode: str,
    model_id: str,
) -> tuple[VisualModel, list[RenderStep]]:
    return compile_grid_matrix(
        rows=rows, cols=cols, frames=frames, trace_steps=list(trace.get("steps") or []),
        profile=profile, mode=mode, model_id=model_id,
        example_id=str(trace.get("example_id", "")), trace_id=str(trace.get("trace_id", "")),
    )
