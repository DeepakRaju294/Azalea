"""IndexedSequenceCompiler — folded FrameState[] -> an indexed_sequence_diagram model.

Targets the frontend `IndexedSequenceVisual.tsx` contract:
  base  = { values:[str], indices:[int], pointer_definitions:[{id,label}], mode }
  state = { pointers:[{id,position,label}], ranges:[{id,start,end,label}],
            highlighted_cells:[int], swapped_cells, sorted_prefix_end }
Serves binary search / two-pointer / sliding window / sort. Discarded cells fall
OUT of `ranges` (rendered dim); the found index is highlighted.
"""
from __future__ import annotations

from typing import Any

from ..schemas import FrameState, RenderStep, Trace, TraceStep, VisualModel

_POINTER_KEYS = ("low", "high", "mid", "left", "right", "start", "end")


def _frame_state(after: dict[str, Any]) -> dict[str, Any]:
    low, high, mid, found = after.get("low"), after.get("high"), after.get("mid"), after.get("found")
    pointers = [
        {"id": k, "position": after[k], "label": k}
        for k in _POINTER_KEYS
        if isinstance(after.get(k), int)
    ]
    ranges = []
    if isinstance(low, int) and isinstance(high, int) and low <= high:
        ranges.append({"id": "range", "start": low, "end": high, "label": "search range"})
    if found is not None:
        highlighted = [found]
    elif isinstance(mid, int):
        highlighted = [mid]
    else:
        highlighted = []
    # Generic scan state (SequenceProjection): named cursors + window + marked cells,
    # rendered alongside the binary-search keys above (additive — keeps BS working).
    for name, pos in (after.get("cursors") or {}).items():
        if isinstance(pos, int):
            pointers.append({"id": str(name), "position": pos, "label": str(name)})
            highlighted.append(pos)
    window = after.get("window")
    if isinstance(window, list) and len(window) == 2 and all(isinstance(w, int) for w in window) and window[0] <= window[1]:
        ranges.append({"id": "window", "start": window[0], "end": window[1], "label": "window"})
    marked = after.get("marked")
    if isinstance(marked, list):
        highlighted.extend(c for c in marked if isinstance(c, int))
    return {
        "pointers": pointers,
        "ranges": ranges,
        "highlighted_cells": highlighted,
        "swapped_cells": after.get("swapped_cells"),
        "sorted_prefix_end": after.get("sorted_prefix_end"),
    }


def compile_indexed_sequence(
    *,
    array: list[Any],
    frames: list[FrameState],
    trace_steps: list[TraceStep],
    profile: dict[str, Any],
    mode: str,
    model_id: str,
    example_id: str = "",
    trace_id: str = "",
) -> tuple[VisualModel, list[RenderStep]]:
    base = {
        "values": [str(v) for v in array],
        "indices": list(range(len(array))),
        "pointer_definitions": [{"id": k, "label": k} for k in ("low", "high", "mid")],
        "mode": mode,
    }
    model_frames = [
        {
            "index": i,
            "state": _frame_state(frame["state_after"]),
            "highlights": {},
            "annotations": [],
            "selectable_elements": [],
            "transitions": [],
        }
        for i, frame in enumerate(frames)
    ]

    model = VisualModel(
        id=model_id,
        base_type=str(profile.get("base_type", "indexed_sequence_diagram")),
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
    array: list[Any],
    profile: dict[str, Any],
    mode: str,
    model_id: str,
) -> tuple[VisualModel, list[RenderStep]]:
    return compile_indexed_sequence(
        array=array,
        frames=frames,
        trace_steps=list(trace.get("steps") or []),
        profile=profile,
        mode=mode,
        model_id=model_id,
        example_id=str(trace.get("example_id", "")),
        trace_id=str(trace.get("trace_id", "")),
    )
