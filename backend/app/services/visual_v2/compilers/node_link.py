"""NodeLinkCompiler — FrameState[] -> VisualModel + RenderStep[] (graph/tree).

Derives each node's SEMANTIC state from the folded frame (active/visited/frontier
+ the per-step diff), lays out nodes deterministically, and packs the side-panel
runtime state. It reads the trace/frames read-only and never alters their
semantics (§6.3). No LLM, no regex — state comes from the fold, not prose.
"""
from __future__ import annotations

import math
from typing import Any

from ..schemas import FrameState, RenderStep, Trace, TraceStep, VisualModel


def _layout(nodes: list[str]) -> dict[str, tuple[float, float]]:
    """Deterministic circular spread so edges stay visible (graph 'spread' layout)."""
    n = max(len(nodes), 1)
    pos: dict[str, tuple[float, float]] = {}
    for i, node in enumerate(nodes):
        angle = (2 * math.pi * i / n) - (math.pi / 2)  # start at top
        pos[node] = (round(50 + 36 * math.cos(angle), 1), round(50 + 36 * math.sin(angle), 1))
    return pos


def _node_state(node: str, active: str | None, visited: list[str], frontier: list[str], newly: set[str]) -> str:
    if node == active:
        return "current"
    if node in visited:
        return "completed"
    if node in newly:
        return "newly_discovered"
    if node in frontier:
        return "discovered"
    return "unvisited"


def compile_node_link(
    *,
    base_structure: dict[str, Any],
    frames: list[FrameState],
    trace_steps: list[TraceStep],
    profile: dict[str, Any],
    mode: str,
    model_id: str,
    example_id: str = "",
    trace_id: str = "",
) -> tuple[VisualModel, list[RenderStep]]:
    nodes = list(base_structure.get("nodes") or [])
    edges = list(base_structure.get("edges") or [])
    pos = _layout(nodes)

    base_nodes = [
        {"id": n, "label": n, "relation": "node", "x": pos[n][0], "y": pos[n][1]} for n in nodes
    ]
    base_edges = [
        {"from": e[0], "to": e[1], "label": "", "style": "solid"}
        for e in edges
        if isinstance(e, (list, tuple)) and len(e) == 2
    ]

    model_frames: list[dict[str, Any]] = []
    for frame in frames:
        after = frame["state_after"]
        diff = frame.get("diff") or {}
        active = after.get("active")
        visited = list(after.get("visited") or [])
        frontier = list((after.get("frontier") or {}).get("items") or [])
        newly = set(diff.get("newly_added") or []) | set(diff.get("newly_completed") or [])
        node_state_map = [
            {"node_id": n, "state": _node_state(n, active, visited, frontier, newly)} for n in nodes
        ]
        # Edge-selection state (PROJECTOR_SYSTEM_SPEC §4.1) — present for MST /
        # shortest-path-tree algorithms; empty/blank for plain traversals.
        active_edge = after.get("active_edge") or ["", ""]
        selected_edges = list(after.get("selected_edges") or [])
        model_frames.append(
            {
                "state": {
                    "active_node": active or "",
                    "completed_nodes": visited,
                    "node_state_map": node_state_map,
                    "active_edge_from": active_edge[0] if active_edge else "",
                    "active_edge_to": active_edge[1] if active_edge else "",
                    "completed_edges_from": [e[0] for e in selected_edges],
                    "completed_edges_to": [e[1] for e in selected_edges],
                    "runtime_state": {
                        "frontier": frontier,
                        "frontier_kind": (after.get("frontier") or {}).get("kind", ""),
                        "output": list(after.get("output") or []),
                    },
                }
            }
        )

    model = VisualModel(
        id=model_id,
        base_type=str(profile.get("base_type", "node_link_diagram")),
        mode=mode,
        example_id=example_id,
        trace_id=trace_id,
        base={"nodes": base_nodes, "edges": base_edges},
        frames=model_frames,
    )

    render_steps: list[RenderStep] = []
    for i, frame in enumerate(frames):
        step = trace_steps[i] if i < len(trace_steps) else {}
        render_steps.append(
            RenderStep(
                step_index=int(frame.get("step_index", i)),
                frame_index=i,
                trace_step_id=str(step.get("trace_step_id", f"s{i}")),
                primary_change=str(step.get("primary_change", "")),
                caption=str(step.get("learner_should_notice", "")),
            )
        )

    return model, render_steps


def compile_from_trace(
    *,
    trace: Trace,
    frames: list[FrameState],
    base_structure: dict[str, Any],
    profile: dict[str, Any],
    mode: str,
    model_id: str,
) -> tuple[VisualModel, list[RenderStep]]:
    """Convenience wrapper that pulls ids/steps off the trace."""
    return compile_node_link(
        base_structure=base_structure,
        frames=frames,
        trace_steps=list(trace.get("steps") or []),
        profile=profile,
        mode=mode,
        model_id=model_id,
        example_id=str(trace.get("example_id", "")),
        trace_id=str(trace.get("trace_id", "")),
    )
