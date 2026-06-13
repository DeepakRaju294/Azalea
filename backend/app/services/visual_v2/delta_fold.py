"""DeltaFoldEngine (VISUAL_SYSTEM_SPEC §6.5).

The single core service that folds `initial_state` + `TraceStep[]` into
`FrameState[]` (state_before / delta / state_after + diff metadata). Deltas are
applied via a per-operation handler registry, so a new mode contributes new ops
(e.g. binary search's `shrink_range`) without changing the engine — proving the
vocabulary generalises. Op names are globally unique; the mode's `delta_vocabulary`
gates which ops are permitted.
"""
from __future__ import annotations

import copy
from typing import Any, Callable, Iterable

from .schemas import FrameState, TraceStep


class InvalidDeltaError(ValueError):
    """A delta uses an op outside the mode vocabulary or references an unknown id."""


# --- operation handlers (mutate the working state in place) ----------------

def _op_set_active(state: dict, value: Any, ids: set) -> None:
    if value is not None and value not in ids:
        raise InvalidDeltaError(f"set_active references unknown id {value!r}")
    state["active"] = value


def _op_remove_from_frontier(state: dict, value: Any, ids: set) -> None:
    items = state.setdefault("frontier", {"kind": "queue", "items": []}).setdefault("items", [])
    for rid in value or []:
        if rid in items:
            items.remove(rid)


def _op_add_to_frontier(state: dict, value: Any, ids: set) -> None:
    items = state.setdefault("frontier", {"kind": "queue", "items": []}).setdefault("items", [])
    for aid in value or []:
        if aid not in ids:
            raise InvalidDeltaError(f"add_to_frontier references unknown id {aid!r}")
        items.append(aid)


def _op_newly_visited(state: dict, value: Any, ids: set) -> None:
    visited = state.setdefault("visited", [])
    for vid in value or []:
        if vid not in ids:
            raise InvalidDeltaError(f"newly_visited references unknown id {vid!r}")
        if vid not in visited:
            visited.append(vid)


def _op_append_to_output(state: dict, value: Any, ids: set) -> None:
    state.setdefault("output", []).extend(value or [])


# Edge-selection ops (PROJECTOR_SYSTEM_SPEC §4.1) — MST / shortest-path trees.
def _op_set_active_edge(state: dict, value: Any, ids: set) -> None:
    state["active_edge"] = [value[0], value[1]] if value and len(value) == 2 else None


def _op_add_selected_edge(state: dict, value: Any, ids: set) -> None:
    if not value or len(value) != 2:
        return
    selected = state.setdefault("selected_edges", [])
    pair = [value[0], value[1]]
    if pair not in selected and [value[1], value[0]] not in selected:  # undirected
        selected.append(pair)


def _op_set_vars(state: dict, value: Any, ids: set) -> None:
    for key, val in (value or {}).items():
        state[key] = val


def _op_mark_mid(state: dict, value: Any, ids: set) -> None:
    if value is not None and value not in ids:
        raise InvalidDeltaError(f"mark_mid references unknown index {value!r}")
    state["mid"] = value


def _op_shrink_range(state: dict, value: Any, ids: set) -> None:
    if value and len(value) == 2:
        state["low"], state["high"] = value[0], value[1]


def _op_mark_discarded(state: dict, value: Any, ids: set) -> None:
    discarded = state.setdefault("discarded", [])
    for idx in value or []:
        if idx not in ids:
            raise InvalidDeltaError(f"mark_discarded references unknown index {idx!r}")
        if idx not in discarded:
            discarded.append(idx)


def _op_mark_found(state: dict, value: Any, ids: set) -> None:
    state["found"] = value


# --- code_execution ops (state: highlight_lines / variables / call_stack / output)

def _op_set_highlight_lines(state: dict, value: Any, ids: set) -> None:
    state["highlight_lines"] = list(value or [])


def _op_set_locals(state: dict, value: Any, ids: set) -> None:
    state["variables"] = dict(value or {})


def _op_set_call_stack(state: dict, value: Any, ids: set) -> None:
    state["call_stack"] = list(value or [])


def _op_set_output(state: dict, value: Any, ids: set) -> None:
    state["output"] = value


# --- dp_table / grid ops (state: active_cell / completed_cells / cell_values / dependency_arrows)

def _op_set_active_cell(state: dict, value: Any, ids: set) -> None:
    state["active_cell"] = list(value) if value else None


def _op_fill_cell(state: dict, value: Any, ids: set) -> None:
    cell = (value or {}).get("cell")
    if cell is not None:
        state.setdefault("cell_values", {})[f"{cell[0]},{cell[1]}"] = str((value or {}).get("value"))


def _op_complete_cell(state: dict, value: Any, ids: set) -> None:
    state.setdefault("completed_cells", []).append(list(value))


def _op_set_dependency_arrows(state: dict, value: Any, ids: set) -> None:
    state["dependency_arrows"] = list(value or [])


# --- formula_substitution ops (state: formula / substituted / computations / result)

def _op_set_substituted(state: dict, value: Any, ids: set) -> None:
    state["substituted"] = str(value) if value is not None else None


def _op_add_computation(state: dict, value: Any, ids: set) -> None:
    state.setdefault("computations", []).append({
        "label": str((value or {}).get("label") or ""),
        "calc": str((value or {}).get("calc") or ""),
    })


def _op_set_result(state: dict, value: Any, ids: set) -> None:
    state["result"] = str(value) if value is not None else None


# --- set_region ops -------------------------------------------------------------

def _op_set_active_set(state: dict, value: Any, ids: set) -> None:
    state["active_set"] = value


def _op_set_shaded_regions(state: dict, value: Any, ids: set) -> None:
    state["shaded_regions"] = list(value or [])


def _op_set_region_counts(state: dict, value: Any, ids: set) -> None:
    state["region_counts"] = dict(value or {})


# --- coordinate ops -------------------------------------------------------------

def _op_set_active_curve(state: dict, value: Any, ids: set) -> None:
    state["active_curve"] = value


def _op_set_active_point(state: dict, value: Any, ids: set) -> None:
    state["active_point"] = value


def _op_set_point_value(state: dict, value: Any, ids: set) -> None:
    state["point_value"] = str(value) if value is not None else None


# --- memory ops -----------------------------------------------------------------

def _op_set_visible_frames(state: dict, value: Any, ids: set) -> None:
    state["visible_frames"] = list(value or [])


def _op_set_visible_objects(state: dict, value: Any, ids: set) -> None:
    state["visible_objects"] = list(value or [])


def _op_set_active_object(state: dict, value: Any, ids: set) -> None:
    state["active_object"] = value


def _op_set_active_pointer(state: dict, value: Any, ids: set) -> None:
    state["active_pointer"] = value


# --- timeline ops ---------------------------------------------------------------

def _op_set_active_message(state: dict, value: Any, ids: set) -> None:
    state["active_message"] = value


def _op_set_visible_messages(state: dict, value: Any, ids: set) -> None:
    state["visible_messages"] = list(value or [])


def _op_set_actor_states(state: dict, value: Any, ids: set) -> None:
    state["actor_states"] = dict(value or {})


# --- geometric ops --------------------------------------------------------------

def _op_set_active_segment(state: dict, value: Any, ids: set) -> None:
    state["active_segment"] = value


def _op_add_measurement(state: dict, value: Any, ids: set) -> None:
    m = state.setdefault("measurements", {})
    if isinstance(value, dict):
        m.update({str(k): str(v) for k, v in value.items()})


# --- table / comparison ops -----------------------------------------------------

def _op_set_active_row(state: dict, value: Any, ids: set) -> None:
    state["active_row"] = value


# --- indexed_sequence_scan ops (PROJECTOR_SYSTEM_SPEC §13 SequenceProjection) ---
# Generic array scan: named index cursors + an optional window + highlighted cells.
def _op_set_cursor(state: dict, value: Any, ids: set) -> None:
    state["cursors"] = {str(k): v for k, v in (value or {}).items() if isinstance(v, int)}


def _op_set_window(state: dict, value: Any, ids: set) -> None:
    state["window"] = [value[0], value[1]] if value and len(value) == 2 else None


def _op_mark_cells(state: dict, value: Any, ids: set) -> None:
    state["marked"] = [c for c in (value or []) if isinstance(c, int)]


# Canonical apply order (e.g. remove-before-add for the frontier), so folding is
# deterministic regardless of the delta dict's key order.
_OP_ORDER: list[tuple[str, Callable[[dict, Any, set], None]]] = [
    ("set_active", _op_set_active),
    ("remove_from_frontier", _op_remove_from_frontier),
    ("add_to_frontier", _op_add_to_frontier),
    ("newly_visited", _op_newly_visited),
    ("append_to_output", _op_append_to_output),
    ("set_active_edge", _op_set_active_edge),
    ("add_selected_edge", _op_add_selected_edge),
    ("set_pointer", _op_set_vars),  # alias
    ("set_vars", _op_set_vars),
    ("mark_mid", _op_mark_mid),
    ("shrink_range", _op_shrink_range),
    ("mark_discarded", _op_mark_discarded),
    ("mark_found", _op_mark_found),
    ("set_highlight_lines", _op_set_highlight_lines),
    ("set_locals", _op_set_locals),
    ("set_call_stack", _op_set_call_stack),
    ("set_output", _op_set_output),
    ("set_active_cell", _op_set_active_cell),
    ("fill_cell", _op_fill_cell),
    ("complete_cell", _op_complete_cell),
    ("set_dependency_arrows", _op_set_dependency_arrows),
    ("set_substituted", _op_set_substituted),
    ("add_computation", _op_add_computation),
    ("set_result", _op_set_result),
    ("set_active_set", _op_set_active_set),
    ("set_shaded_regions", _op_set_shaded_regions),
    ("set_region_counts", _op_set_region_counts),
    ("set_active_curve", _op_set_active_curve),
    ("set_active_point", _op_set_active_point),
    ("set_point_value", _op_set_point_value),
    ("set_visible_frames", _op_set_visible_frames),
    ("set_visible_objects", _op_set_visible_objects),
    ("set_active_object", _op_set_active_object),
    ("set_active_pointer", _op_set_active_pointer),
    ("set_active_message", _op_set_active_message),
    ("set_visible_messages", _op_set_visible_messages),
    ("set_actor_states", _op_set_actor_states),
    ("set_active_segment", _op_set_active_segment),
    ("add_measurement", _op_add_measurement),
    ("set_active_row", _op_set_active_row),
    ("set_cursor", _op_set_cursor),
    ("set_window", _op_set_window),
    ("mark_cells", _op_mark_cells),
]
_KNOWN_OPS = {name for name, _ in _OP_ORDER} | {"no_op", "checked_element_ids", "reason"}


def apply_delta(state: dict[str, Any], delta: dict[str, Any], valid_ids: set) -> dict[str, Any]:
    s = copy.deepcopy(state)
    if delta.get("no_op"):
        return s
    for op, value in delta.items():
        if op not in _KNOWN_OPS:
            raise InvalidDeltaError(f"unknown delta op {op!r}")
    for name, handler in _OP_ORDER:
        if name in delta:
            handler(s, delta[name], valid_ids)
    return s


def _compute_diff(delta: dict[str, Any]) -> dict[str, Any]:
    if delta.get("no_op"):
        return {"no_op": True, "checked_element_ids": list(delta.get("checked_element_ids") or [])}
    return {
        # graph
        "set_active": delta.get("set_active"),
        "newly_added": list(delta.get("add_to_frontier") or []),
        "newly_completed": list(delta.get("newly_visited") or []),
        "appended_to_output": list(delta.get("append_to_output") or []),
        "active_edge": delta.get("set_active_edge"),
        "newly_selected_edge": delta.get("add_selected_edge"),
        # array / binary search
        "mid": delta.get("mark_mid", (delta.get("set_pointer") or {}).get("mid")),
        "newly_discarded": list(delta.get("mark_discarded") or []),
        "found": delta.get("mark_found"),
        # code_execution
        "highlight_lines": list(delta.get("set_highlight_lines") or []),
        "no_op": False,
    }


class DeltaFoldEngine:
    """Folds a trace into per-step frame states. Pure + deterministic."""

    def fold(
        self,
        initial_state: dict[str, Any],
        steps: Iterable[TraceStep],
        valid_ids: Iterable[Any],
        allowed_ops: Iterable[str],
    ) -> list[FrameState]:
        ids = set(valid_ids)
        allowed = set(allowed_ops)
        frames: list[FrameState] = []
        state = copy.deepcopy(initial_state)
        for i, step in enumerate(steps):
            delta = dict(step.get("delta") or {})
            unknown = set(delta) - allowed
            if unknown:
                raise InvalidDeltaError(
                    f"step {i}: delta ops {sorted(unknown)} not in mode vocabulary {sorted(allowed)}"
                )
            before = copy.deepcopy(state)
            after = apply_delta(before, delta, ids)
            frames.append(
                FrameState(
                    step_index=int(step.get("step_index", i)),
                    state_before=before,
                    delta=delta,
                    state_after=after,
                    diff=_compute_diff(delta),
                )
            )
            state = after
        return frames
