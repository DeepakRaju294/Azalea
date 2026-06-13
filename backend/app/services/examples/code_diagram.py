"""Build the DIAGRAM slot of a coding worked example from the code's OWN trace
(PROJECTOR_SYSTEM_SPEC §6.4 INV-DUAL-SLOT generation).

The diagram is derived from the same trace as the code — one source of truth, so it can
never contradict the code. We reuse the already-computed frames (no second execution),
derive the graph structure from the runtime variables, infer a projection, and project
to a validated node_link model. **Validate-or-degrade:** if the trace isn't graph-shaped
or nothing validates, we return None and the caller ships clean code-only — never a wrong
or empty diagram. Deterministic, zero-LLM, computed once and cached in `visual_models`.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

_log = logging.getLogger(__name__)


def derive_graph_from_trace(trace_steps: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Find an adjacency-map variable in the trace (dict[node -> list[node]]) and build
    {nodes, edges}. Returns None when the trace has no graph shape (→ code-only)."""
    from app.services.visual_v2.projectors.node_link import locals_of

    candidates: dict[str, dict[str, Any]] = {}
    for step in trace_steps:
        for name, val in locals_of(step).items():
            if isinstance(val, dict) and val and all(isinstance(v, list) for v in val.values()):
                candidates.setdefault(name, val)
    if not candidates:
        return None

    # The adjacency map is the dict with the most keys (the graph, not a small lookup).
    _name, adj = max(candidates.items(), key=lambda kv: len(kv[1]))
    nodes: list[str] = [str(k) for k in adj.keys()]
    node_set = set(nodes)
    edges: list[list[str]] = []
    seen: set[frozenset] = set()
    for a, neighbours in adj.items():
        for b in neighbours:
            sa, sb = str(a), str(b)
            if sb not in node_set:
                nodes.append(sb)
                node_set.add(sb)
            key = frozenset((sa, sb))
            if sa != sb and key not in seen:
                seen.add(key)
                edges.append([sa, sb])
    if len(nodes) < 2 or not edges:
        return None
    return {"nodes": nodes, "edges": edges}


def build_node_link_diagram_from_trace(
    trace_steps: list[dict[str, Any]], *, model_id: str, start: Any = None
) -> Optional[dict[str, Any]]:
    """Reuse an existing code trace to build a validated node_link diagram model.
    Returns {"model", "event_ids", "frame_count"} or None (→ code-only). Never raises."""
    try:
        from app.services.visual_v2.compilers import node_link as node_link_compiler
        from app.services.visual_v2.delta_fold import DeltaFoldEngine
        from app.services.visual_v2.profiles import delta_vocabulary, profile_for_mode
        from app.services.visual_v2.projectors.node_link import (
            infer_projection,
            project_node_link,
            validate_projection,
        )
        from app.services.visual_v2.provenance import make_provenance, stamp
        from app.services.visual_v2.validators import validate_visual_invariants

        base_graph = derive_graph_from_trace(trace_steps)
        if base_graph is None:
            return None  # not graph-shaped → clean code-only

        candidate = infer_projection(trace_steps, base_graph)
        if candidate is None:
            return None
        if validate_projection(trace_steps, base_graph, candidate.projection):
            return None  # contract didn't resolve → degrade, never ship a wrong diagram

        result = project_node_link(
            trace_steps, base_graph, candidate.projection, projection_source="inferred"
        )
        if not result.deltas:
            return None

        valid_ids = {str(n) for n in base_graph["nodes"]}
        frontier_kind = (
            "priority_queue"
            if (candidate.projection.frontier_priority_key or candidate.projection.frontier_node_key)
            else "queue"
        )
        frames = DeltaFoldEngine().fold(
            result.initial_state(start, frontier_kind=frontier_kind),
            result.deltas, valid_ids, delta_vocabulary("graph_network"),
        )
        model, _render = node_link_compiler.compile_from_trace(
            trace={"steps": result.deltas}, frames=frames, base_structure=base_graph,
            profile=profile_for_mode("graph_network"), mode="graph_network", model_id=model_id,
        )
        # The diagram is gated by the SAME guardrail as any node_link model.
        if validate_visual_invariants(model, None):
            return None
        stamp(model, make_provenance(
            "inferred_projection",
            projection_source="inferred",
            projection_contract=result.projection_contract,
            projector_version=result.projector_version,
            inference_version=result.inference_version,
            confidence_band=candidate.confidence_band,
            validation_summary={"source": "code_trace_diagram", "frames": len(frames)},
        ))
        return {
            "model": model,
            "event_ids": [d.get("event_id") for d in result.deltas],
            "frame_count": len(frames),
        }
    except Exception as exc:  # noqa: BLE001 — the diagram is additive; degrade to code-only
        _log.warning("code_diagram: build failed (%s); shipping code-only", exc)
        return None


# ---------------------------------------------------------------------------
# Sequence (indexed_sequence) diagram from a code trace — the array family
# (two-pointer / sliding-window / linear scan). Same pattern as node_link.
# ---------------------------------------------------------------------------

from dataclasses import dataclass


@dataclass(frozen=True)
class SequenceProjection:
    array_from: str                 # the list variable being scanned (fixed values)
    pointers_from: tuple[str, ...]  # index variables (i, j, lo, hi, left, right, ...)


def derive_array_from_trace(trace_steps: list[dict[str, Any]]) -> Optional[tuple[str, list[Any]]]:
    """Find the data array: the longest list-of-scalars whose length AND values are
    stable across the trace (not a churning stack or a mutating/growing accumulator).
    Returns (name, values) or None. Mutating arrays (sorting) are skipped for now."""
    from app.services.visual_v2.projectors.node_link import locals_of

    series: dict[str, list[list[Any]]] = {}
    for step in trace_steps:
        for name, val in locals_of(step).items():
            if isinstance(val, list) and val and all(
                isinstance(x, (int, float, str)) and not isinstance(x, bool) for x in val
            ):
                series.setdefault(name, []).append(val)
    best: Optional[tuple[str, list[Any]]] = None
    for name, observed in series.items():
        if len({len(v) for v in observed}) != 1 or len(observed[0]) < 3:
            continue  # length churned → not the data array
        if any(v != observed[0] for v in observed):
            continue  # values mutate (sorting) → fixed-base compiler can't show it
        if best is None or len(observed[0]) > len(best[1]):
            best = (name, observed[0])
    return best


# Conventional index-variable names. A pointer must be named like an index — an in-range
# int that ISN'T (a sum/count that coincidentally lands in [0, n) is not a cursor).
_POINTER_NAME_HINTS = frozenset({
    "i", "j", "k", "l", "r", "lo", "hi", "low", "high", "left", "right", "mid", "m",
    "start", "end", "p", "q", "idx", "index", "pos", "cur", "curr", "fast", "slow",
    "first", "last", "lt", "gt", "hare", "tortoise",
})


def infer_sequence_projection(
    trace_steps: list[dict[str, Any]], array_name: str, array: list[Any]
) -> Optional[SequenceProjection]:
    """Pointers = integer variables with a conventional index name that hold valid
    indices into the array and move (the name hint rules out sums/counts in range)."""
    from app.services.visual_v2.projectors.node_link import locals_of

    n = len(array)
    seen: dict[str, set[int]] = {}
    for step in trace_steps:
        for name, val in locals_of(step).items():
            if name == array_name or name.lower() not in _POINTER_NAME_HINTS:
                continue
            if isinstance(val, int) and not isinstance(val, bool) and 0 <= val < n:
                seen.setdefault(name, set()).add(val)
    pointers = tuple(name for name, vals in seen.items() if len(vals) >= 2)
    return SequenceProjection(array_from=array_name, pointers_from=pointers) if pointers else None


def project_indexed_sequence(
    trace_steps: list[dict[str, Any]], array: list[Any], projection: SequenceProjection
) -> list[dict[str, Any]]:
    """Emit one indexed_sequence step each time a cursor moves."""
    from app.services.visual_v2.projectors.node_link import locals_of

    n = len(array)
    deltas: list[dict[str, Any]] = []
    prev: Optional[dict[str, int]] = None
    emit = 0
    for step in trace_steps:
        loc = locals_of(step)
        cursors = {
            p: loc[p] for p in projection.pointers_from
            if isinstance(loc.get(p), int) and not isinstance(loc.get(p), bool) and 0 <= loc[p] < n
        }
        if not cursors or cursors == prev:
            continue
        tag = "-".join(f"{k}{v}" for k, v in sorted(cursors.items()))
        deltas.append({
            "step_index": emit, "trace_step_id": f"s{emit}", "kind": "scan",
            "delta": {"set_cursor": cursors},
            "primary_change": "set_cursor",
            "event_id": f"scan:{tag}:{emit:02d}",
            "step_role": "scan",
            "learner_should_notice": f"Cursors at {cursors}.",
        })
        prev = dict(cursors)
        emit += 1
    return deltas


def build_sequence_diagram_from_trace(
    trace_steps: list[dict[str, Any]], *, model_id: str
) -> Optional[dict[str, Any]]:
    """Reuse a code trace to build a validated indexed_sequence diagram, or None."""
    try:
        from app.services.visual_v2.compilers import indexed_sequence as seq_compiler
        from app.services.visual_v2.delta_fold import DeltaFoldEngine
        from app.services.visual_v2.profiles import delta_vocabulary, profile_for_mode
        from app.services.visual_v2.provenance import make_provenance, stamp

        derived = derive_array_from_trace(trace_steps)
        if derived is None:
            return None
        array_name, array = derived
        projection = infer_sequence_projection(trace_steps, array_name, array)
        if projection is None:
            return None
        deltas = project_indexed_sequence(trace_steps, array, projection)
        if len(deltas) < 2:
            return None

        frames = DeltaFoldEngine().fold(
            {"cursors": {}}, deltas, set(), delta_vocabulary("indexed_sequence_scan")
        )
        model, _render = seq_compiler.compile_from_trace(
            trace={"steps": deltas}, frames=frames, array=array,
            profile=profile_for_mode("indexed_sequence_scan"),
            mode="indexed_sequence_scan", model_id=model_id,
        )
        if not any(f["state"].get("pointers") for f in model["frames"]):
            return None
        stamp(model, make_provenance(
            "inferred_projection", projection_source="inferred",
            projection_contract={"array_from": array_name, "pointers_from": list(projection.pointers_from)},
            validation_summary={"source": "code_trace_diagram", "frames": len(frames)},
        ))
        return {"model": model, "event_ids": [d["event_id"] for d in deltas], "frame_count": len(frames)}
    except Exception as exc:  # noqa: BLE001 — additive; degrade to code-only
        _log.warning("code_diagram: sequence build failed (%s); code-only", exc)
        return None


def _is_scalar_list(val: Any) -> bool:
    return (
        isinstance(val, list) and bool(val)
        and all(isinstance(x, (int, float, str)) and not isinstance(x, bool) for x in val)
    )


def build_multi_sequence_diagram_from_trace(
    trace_steps: list[dict[str, Any]], *, model_id: str, max_frames: int = 16
) -> Optional[dict[str, Any]]:
    """Composite (multiple-array) diagram for divide-and-conquer / multi-collection code
    (merge sort's left/right/result, partition, k-way merge). Each frame carries a LIST of
    labeled sub-arrays with their cursors, rendered together on one page. Built only when
    2+ data arrays are live at once; else None (→ single-array or code-only)."""
    try:
        from app.services.visual_v2.projectors.node_link import locals_of
        from app.services.visual_v2.provenance import make_provenance, stamp

        frames: list[dict[str, Any]] = []
        prev_sig = None
        for step in trace_steps:
            loc = locals_of(step)
            arrays = {name: val for name, val in loc.items() if _is_scalar_list(val)}
            if len(arrays) < 2:
                continue
            pointers = {
                name: val for name, val in loc.items()
                if isinstance(val, int) and not isinstance(val, bool) and name.lower() in _POINTER_NAME_HINTS
            }
            sequences = []
            for aname, avals in arrays.items():
                cursors = [
                    {"id": p, "position": v, "label": p}
                    for p, v in pointers.items() if 0 <= v < len(avals)
                ]
                sequences.append({
                    "label": str(aname),
                    "values": [str(x) for x in avals],
                    "pointers": cursors,
                    "highlighted_cells": [c["position"] for c in cursors],
                })
            sig = tuple((s["label"], tuple(s["values"]), tuple(c["position"] for c in s["pointers"])) for s in sequences)
            if sig == prev_sig:
                continue
            frames.append({"index": len(frames), "state": {"sequences": sequences},
                           "highlights": {}, "annotations": [], "selectable_elements": [], "transitions": []})
            prev_sig = sig

        if len(frames) < 2:
            return None
        if len(frames) > max_frames:  # keep it readable: first, last, evenly-spaced
            mid = frames[1:-1]
            keep = max_frames - 2
            step_n = len(mid) / keep
            frames = [frames[0]] + [mid[min(int(i * step_n), len(mid) - 1)] for i in range(keep)] + [frames[-1]]
            for i, f in enumerate(frames):
                f["index"] = i

        model = {
            "id": model_id, "base_type": "indexed_sequence_diagram", "mode": "multi_sequence",
            "example_id": "", "trace_id": "",
            "base": {"values": [], "mode": "multi_sequence", "pointer_definitions": []},
            "frames": frames,
        }
        stamp(model, make_provenance(
            "inferred_projection", projection_source="inferred",
            validation_summary={"source": "code_trace_multi_sequence", "frames": len(frames)},
        ))
        return {"model": model, "event_ids": [f"multi:{i:02d}" for i in range(len(frames))], "frame_count": len(frames)}
    except Exception as exc:  # noqa: BLE001 — additive; degrade
        _log.warning("code_diagram: multi-sequence build failed (%s); code-only", exc)
        return None


def build_diagram_from_trace(trace_steps: list[dict[str, Any]], *, model_id: str) -> Optional[dict[str, Any]]:
    """The shape dispatcher: node_link (graph) → single array → multi-array (composite).
    Returns the first that validates, or None (→ clean code-only)."""
    return (
        build_node_link_diagram_from_trace(trace_steps, model_id=model_id)
        or build_sequence_diagram_from_trace(trace_steps, model_id=model_id)
        or build_multi_sequence_diagram_from_trace(trace_steps, model_id=model_id)
    )


def attach_diagram_to_cards(
    lesson_json: dict[str, Any],
    cards: list[dict[str, Any]],
    frames: list[dict[str, Any]],
    diagram: Optional[dict[str, Any]],
    *,
    source: str = "v2_code_diagram",
) -> bool:
    """Attach a built diagram to the code worked-example cards, synced by visit-progress
    + event_id, with the INV-COMPLETE cross-check. Shared by both code paths so they
    behave identically. Returns True iff attached (False → clean code-only)."""
    if diagram is None:
        return False
    model = diagram["model"]
    event_ids = diagram["event_ids"]
    n_frames = diagram["frame_count"]
    is_node_link = str(model.get("base_type")) == "node_link_diagram"

    # Completion cross-check (idea 3, node_link only): the diagram's terminal visited set
    # must equal the code's actual terminal output — else it's misaligned; code-only.
    if is_node_link:
        code_terminal = {str(x) for x in ((frames[-1].get("state_after") or {}).get("output") or [])} if frames else set()
        diag_terminal = {
            e["node_id"] for e in model["frames"][-1]["state"]["node_state_map"]
            if e["state"] in ("completed", "current")
        }
        if code_terminal and code_terminal != diag_terminal:
            _log.warning("code_diagram: terminal mismatch (diagram %s != code %s); code-only", diag_terminal, code_terminal)
            return False

    models = lesson_json.setdefault("visual_models", [])
    models[:] = [m for m in models if m.get("id") != model["id"]]
    models.append(model)

    # Sync per card. node_link: align by how many nodes visited at that code frame.
    # sequence: align by card ordinal (both advance one step per loop iteration).
    ordinal = 0
    for card in cards:
        ref = card.get("visual_v2_ref") or {}
        fi = ref.get("frame_index")
        if is_node_link:
            visited_count = (
                len((frames[fi].get("state_after") or {}).get("output") or [])
                if isinstance(fi, int) and 0 <= fi < len(frames) else 0
            )
            dfi = max(0, min(visited_count - 1 if visited_count > 0 else 0, n_frames - 1))
        else:
            dfi = min(ordinal, n_frames - 1)
            ordinal += 1
        diagram_ref = {"visual_model_id": model["id"], "frame_index": dfi, "source": source}
        if 0 <= dfi < len(event_ids) and event_ids[dfi]:
            diagram_ref["event_id"] = event_ids[dfi]
            ref["event_id"] = event_ids[dfi]
            card["visual_v2_ref"] = ref
        card["diagram_v2_ref"] = diagram_ref
    return True
