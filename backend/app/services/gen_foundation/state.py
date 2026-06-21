"""Semantic state — the shared keystone (spec §7, §7.1).

The model emits a compact ``state_delta`` (generic ops against a closed per-family
``state_schema``); the backend derives ``resolved_state_after`` from an explicit
``initial_resolved_state``. This module owns:

* the closed op vocabulary + per-family schemas (§7.1 delta-key discipline),
* deterministic delta application + chain derivation (§7),
* payload-size bounds (§7).

Pure: ``apply_delta`` deep-copies and never mutates its input. Anything malformed
raises :class:`InvalidStateDeltaError` so a bad delta is contained to its card (§7)
rather than corrupting the chain.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

# Closed op vocabulary (§7.1). An op on an undeclared path is rejected.
Op = Literal["set", "append", "remove", "push", "pop", "add", "move", "clear"]
ALLOWED_OPS: frozenset[str] = frozenset(
    {"set", "append", "remove", "push", "pop", "add", "move", "clear"}
)

# What kind of value a declared path holds — used to reject e.g. `append` to a scalar.
PathKind = Literal["list", "number", "scalar"]


class StateOp(TypedDict, total=False):
    op: Op
    path: str            # must exist in the family state_schema (§7.1)
    value: Any           # set / push / add / remove(by value)
    values: list[Any]    # append (extend)
    source: str          # move: the path to pop from (into `path`)


class StateDelta(TypedDict):
    ops: list[StateOp]


class InvalidStateDeltaError(ValueError):
    """A delta references an undeclared path, a bad op, or an impossible operation."""


@dataclass(frozen=True)
class StateSchema:
    """A closed set of allowed paths for one topic family (§7.1).

    ``paths`` maps an allowed path name to its :data:`PathKind`. Only declared paths
    may appear in a delta; ``list`` ops (append/push/pop/remove/clear) require a list
    path, ``add`` requires a number path.
    """

    name: str
    paths: dict[str, PathKind]

    def kind(self, path: str) -> PathKind:
        if path not in self.paths:
            raise InvalidStateDeltaError(
                f"path {path!r} is not declared in state_schema {self.name!r}"
            )
        return self.paths[path]


# Per-family resolved shapes (§7). Registry is intentionally small + explicit; a new
# concept registers its own schema rather than inventing free-form keys.
STATE_SCHEMAS: dict[str, StateSchema] = {
    "merge_state_v1": StateSchema(
        "merge_state_v1",
        {
            "left": "list", "right": "list", "merged": "list",
            "i": "number", "j": "number", "k": "number",
            "frame": "scalar", "return_value": "scalar",
        },
    ),
    "binary_search_v1": StateSchema(
        "binary_search_v1",
        {
            "nums": "list", "low": "number", "mid": "number", "high": "number",
            "target": "scalar", "active_range": "scalar", "eliminated_range": "scalar",
        },
    ),
    "graph_traversal_v1": StateSchema(
        "graph_traversal_v1",
        {
            "current_node": "scalar", "queue": "list", "stack": "list",
            "visited": "list", "frontier": "list", "discovered_edges": "list",
        },
    ),
}


def get_schema(name: str) -> StateSchema:
    if name not in STATE_SCHEMAS:
        raise InvalidStateDeltaError(f"unknown state_schema {name!r}")
    return STATE_SCHEMAS[name]


# --- bounds (§7: payload size is bounded) --------------------------------------

@dataclass(frozen=True)
class StateBounds:
    max_ops_per_delta: int = 12
    max_collection_len: int = 64
    max_nested_depth: int = 4
    max_call_stack_frames: int = 32


DEFAULT_BOUNDS = StateBounds()


def _require_list(state: dict[str, Any], path: str) -> list[Any]:
    cur = state.get(path)
    if cur is None:
        cur = []
        state[path] = cur
    if not isinstance(cur, list):
        raise InvalidStateDeltaError(f"path {path!r} is not a list (got {type(cur).__name__})")
    return cur


def _apply_op(state: dict[str, Any], op: StateOp, schema: StateSchema) -> None:
    name = op.get("op")
    if name not in ALLOWED_OPS:
        raise InvalidStateDeltaError(f"unknown op {name!r}")
    path = op.get("path")
    if not isinstance(path, str) or not path:
        raise InvalidStateDeltaError("op is missing a string 'path'")
    kind = schema.kind(path)

    if name == "set":
        state[path] = copy.deepcopy(op.get("value"))
    elif name == "add":
        if kind != "number":
            raise InvalidStateDeltaError(f"'add' requires a number path, {path!r} is {kind}")
        delta = op.get("value")
        if not isinstance(delta, (int, float)) or isinstance(delta, bool):
            raise InvalidStateDeltaError("'add' requires a numeric 'value'")
        state[path] = (state.get(path) or 0) + delta
    elif name in ("append", "push", "pop", "remove", "clear"):
        if kind != "list":
            raise InvalidStateDeltaError(f"'{name}' requires a list path, {path!r} is {kind}")
        lst = _require_list(state, path)
        if name == "append":
            values = op.get("values")
            if not isinstance(values, list):
                raise InvalidStateDeltaError("'append' requires a list 'values'")
            lst.extend(copy.deepcopy(values))
        elif name == "push":
            lst.append(copy.deepcopy(op.get("value")))
        elif name == "pop":
            if not lst:
                raise InvalidStateDeltaError(f"'pop' on empty list at {path!r}")
            lst.pop()
        elif name == "remove":
            target = op.get("value")
            if target not in lst:
                raise InvalidStateDeltaError(f"'remove' value not present in {path!r}")
            lst.remove(target)
        elif name == "clear":
            lst.clear()
    elif name == "move":
        # pop the last element of `source` (a list path) and push onto `path` (a list path).
        src = op.get("source")
        if not isinstance(src, str) or not src:
            raise InvalidStateDeltaError("'move' requires a string 'source' path")
        if schema.kind(src) != "list" or kind != "list":
            raise InvalidStateDeltaError("'move' requires list 'source' and 'path'")
        src_list = _require_list(state, src)
        if not src_list:
            raise InvalidStateDeltaError(f"'move' from empty list {src!r}")
        dst_list = _require_list(state, path)
        dst_list.append(src_list.pop())


def apply_delta(
    resolved_before: dict[str, Any], delta: StateDelta, schema: StateSchema
) -> dict[str, Any]:
    """Return ``resolved_before`` + ``delta`` as a NEW dict (input is not mutated)."""
    ops = (delta or {}).get("ops")
    if not isinstance(ops, list):
        raise InvalidStateDeltaError("state_delta must have an 'ops' list")
    state = copy.deepcopy(resolved_before)
    for op in ops:
        if not isinstance(op, dict):
            raise InvalidStateDeltaError("each op must be an object")
        _apply_op(state, op, schema)  # type: ignore[arg-type]
    return state


def derive_chain(
    initial_resolved_state: dict[str, Any],
    deltas: list[StateDelta | None],
    schema: StateSchema,
) -> list[dict[str, Any]]:
    """Fold deltas over the origin state (§7): initial -> +d1 -> r1 -> +d2 -> r2 ...

    A ``None`` delta (a ``static``/``none`` state step, §4.1/§7) carries state forward
    unchanged. Returns one ``resolved_state_after`` per delta.
    """
    snapshots: list[dict[str, Any]] = []
    current = copy.deepcopy(initial_resolved_state)
    for delta in deltas:
        if delta is None:
            current = copy.deepcopy(current)
        else:
            current = apply_delta(current, delta, schema)
        snapshots.append(current)
    return snapshots


# --- bound checks (return error lists; §7) -------------------------------------

def _depth(value: Any) -> int:
    if isinstance(value, dict):
        return 1 + max((_depth(v) for v in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_depth(v) for v in value), default=0)
    return 0


def validate_delta_bounds(delta: StateDelta, bounds: StateBounds = DEFAULT_BOUNDS) -> list[str]:
    errors: list[str] = []
    ops = (delta or {}).get("ops") or []
    if len(ops) > bounds.max_ops_per_delta:
        errors.append(
            f"delta has {len(ops)} ops (> max {bounds.max_ops_per_delta}); split the card"
        )
    for i, op in enumerate(ops):
        values = op.get("values") if isinstance(op, dict) else None
        if isinstance(values, list) and len(values) > bounds.max_collection_len:
            errors.append(
                f"op {i}: embeds {len(values)} values (> max {bounds.max_collection_len}); "
                "store a reference/range, not a copy"
            )
    return errors


def validate_state_bounds(
    resolved_state: dict[str, Any], bounds: StateBounds = DEFAULT_BOUNDS
) -> list[str]:
    errors: list[str] = []
    for path, value in (resolved_state or {}).items():
        if isinstance(value, list) and len(value) > bounds.max_collection_len:
            errors.append(f"path {path!r}: collection length {len(value)} > max {bounds.max_collection_len}")
        if _depth(value) > bounds.max_nested_depth:
            errors.append(f"path {path!r}: nested depth > max {bounds.max_nested_depth}")
    stack = resolved_state.get("call_stack")
    if isinstance(stack, list) and len(stack) > bounds.max_call_stack_frames:
        errors.append(f"call_stack has {len(stack)} frames > max {bounds.max_call_stack_frames}")
    return errors
