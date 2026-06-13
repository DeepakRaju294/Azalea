"""Concept-visual compilers: folded FrameState[] -> models for the set/coordinate/
memory/timeline/geometric renderers (EXAMPLE_SYSTEM_SPEC §9.4). Each builds the
renderer's static `base` from the example and the per-frame `state` from the trace,
matching the existing frontend component contracts exactly.
"""
from __future__ import annotations

import math
from typing import Any

from ..schemas import FrameState, RenderStep, Trace, VisualModel


def _frames(frames: list[FrameState], state_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    out = []
    for i, frame in enumerate(frames):
        after = frame["state_after"]
        out.append({
            "index": i,
            "state": {k: after.get(k) for k in state_keys},
            "highlights": {}, "annotations": [], "selectable_elements": [], "transitions": [],
        })
    return out


def _render_steps(trace: Trace, frames: list[FrameState]) -> list[RenderStep]:
    steps = list(trace.get("steps") or [])
    return [
        RenderStep(
            step_index=int(f.get("step_index", i)), frame_index=i,
            trace_step_id=str((steps[i] if i < len(steps) else {}).get("trace_step_id", f"s{i}")),
            primary_change=str((steps[i] if i < len(steps) else {}).get("primary_change", "")),
            caption=str((steps[i] if i < len(steps) else {}).get("learner_should_notice", "")),
        )
        for i, f in enumerate(frames)
    ]


def _model(model_id, base_type, mode, trace, base, model_frames) -> VisualModel:
    return VisualModel(
        id=model_id, base_type=base_type, mode=mode,
        example_id=str(trace.get("example_id", "")), trace_id=str(trace.get("trace_id", "")),
        base=base, frames=model_frames, element_catalog=[],
    )


def compile_set_region(*, trace, frames, example, profile, mode, model_id):
    b = example.get("base_structure") or {}
    only_a, only_b, both = int(b.get("only_a", 0)), int(b.get("only_b", 0)), int(b.get("both", 0))
    sets = [
        {"id": "A", "label": str(b.get("label_a", "A")), "x": 40, "y": 50, "r": 28},
        {"id": "B", "label": str(b.get("label_b", "B")), "x": 60, "y": 50, "r": 28},
    ]
    elements = []

    def place(region, count, cx):
        for k in range(count):
            y = 38 + (k * 9) % 26
            elements.append({"id": f"{region}_{k}", "label": "•", "x": cx, "y": y, "regions": [region]})

    place("only_a", only_a, 28)
    place("both", both, 50)
    place("only_b", only_b, 72)
    base = {"sets": sets, "elements": elements, "caption": str(b.get("caption", ""))}
    model_frames = _frames(frames, ("active_set", "active_region", "shaded_regions"))
    return _model(model_id, "set_region_diagram", mode, trace, base, model_frames), _render_steps(trace, frames)


def compile_coordinate(*, trace, frames, example, profile, mode, model_id):
    p = dict(example.get("input") or {})
    a, bb, c = float(p.get("a", 1)), float(p.get("b", 0)), float(p.get("c", 0))
    xs = [x / 2 for x in range(-12, 13)]
    curve_pts = [{"x": x, "y": a * x * x + bb * x + c} for x in xs]
    ys = [pt["y"] for pt in curve_pts]
    points = [{"id": "y_intercept", "label": "y-int", "x": 0.0, "y": c}]
    disc = bb * bb - 4 * a * c
    vx = -bb / (2 * a)
    vy = a * vx * vx + bb * vx + c
    if disc >= 0:
        r = math.sqrt(disc)
        points.append({"id": "roots", "label": "roots", "x": (-bb - r) / (2 * a), "y": 0.0})
    points.append({"id": "vertex", "label": "vertex", "x": vx, "y": vy})
    base = {
        "axes": {"x_min": -6, "x_max": 6, "y_min": math.floor(min(ys + [vy, 0])),
                 "y_max": math.ceil(max(ys + [vy, 0])), "x_label": "x", "y_label": "y"},
        "curves": [{"id": "f", "label": "f(x)", "points": curve_pts}],
        "points": points, "caption": "",
    }
    model_frames = _frames(frames, ("active_point", "active_curve"))
    return _model(model_id, "coordinate_graph", mode, trace, base, model_frames), _render_steps(trace, frames)


def compile_memory(*, trace, frames, example, profile, mode, model_id):
    arr = list(example.get("input", {}).get("array") or [1, 2, 3])
    base = {
        "frames": [{"id": "main", "label": "main()", "variables": [{"name": "x", "value": "→ heap"}]}],
        "objects": [{"id": "arr", "label": "list",
                     "fields": [{"name": str(i), "value": str(v)} for i, v in enumerate(arr)]}],
        "pointers": [{"id": "x_to_arr", "from": "main", "to": "arr", "label": "x"}],
        "caption": "",
    }
    model_frames = _frames(frames, ("active_frame", "active_object", "active_pointer", "visible_frames", "visible_objects"))
    return _model(model_id, "memory_layout_diagram", mode, trace, base, model_frames), _render_steps(trace, frames)


def compile_timeline(*, trace, frames, example, profile, mode, model_id):
    b = example.get("base_structure") or {}
    base = {
        "actors": [dict(a) for a in (b.get("actors") or [])],
        "messages": [dict(m) for m in (b.get("messages") or [])],
        "caption": str(b.get("caption", "")),
    }
    model_frames = _frames(frames, ("active_actor", "active_message", "visible_messages", "actor_states"))
    return _model(model_id, "timeline_sequence_interaction", mode, trace, base, model_frames), _render_steps(trace, frames)


def compile_geometric(*, trace, frames, example, profile, mode, model_id):
    p = dict(example.get("input") or {})
    la, lb = float(p.get("a", 3)), float(p.get("b", 4))
    points = [
        {"id": "R", "label": "", "x": 0.0, "y": 0.0},
        {"id": "P", "label": "", "x": la, "y": 0.0},
        {"id": "Q", "label": "", "x": 0.0, "y": lb},
    ]
    segments = [
        {"id": "a", "from": "R", "to": "P", "label": "a"},
        {"id": "b", "from": "R", "to": "Q", "label": "b"},
        {"id": "c", "from": "P", "to": "Q", "label": "c"},
    ]
    base = {"points": points, "segments": segments, "regions": [], "caption": ""}
    model_frames = _frames(frames, ("active_point", "active_segment", "shaded_regions", "measurements"))
    return _model(model_id, "geometric_diagram", mode, trace, base, model_frames), _render_steps(trace, frames)


COMPILERS = {
    "venn_diagram": compile_set_region,
    "function_curve": compile_coordinate,
    "stack_heap": compile_memory,
    "protocol_sequence": compile_timeline,
    "triangle_geometry": compile_geometric,
}


def compile_comparison_table(*, trace, frames, example, profile, mode, model_id):
    b = example.get("base_structure") or {}
    base = {
        "columns": list(b.get("columns") or []),
        "rows": [[str(c) for c in row] for row in (b.get("rows") or [])],
        "row_labels": [], "caption": str(b.get("caption", "")), "mode": mode,
    }
    model_frames = _frames(frames, ("active_row", "active_cell", "changed_cells"))
    return _model(model_id, "table_diagram", mode, trace, base, model_frames), _render_steps(trace, frames)


COMPILERS["comparison_table"] = compile_comparison_table
