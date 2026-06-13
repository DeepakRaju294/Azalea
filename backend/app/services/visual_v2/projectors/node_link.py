"""node_link projector — contract, value normalization, and the §6.3 validator
(PROJECTOR_SYSTEM_SPEC §3, §6.3; the projector itself and inference land in §4/§8).

This module is the ONE place that reads node_link per-step state out of a runtime
trace. Per §2.6 it contains NO algorithm logic, and per §8 / §18 rule 8 it never
branches on the application/algorithm name — it only reads the variables named by a
`GraphProjection` and normalizes their values to node ids / edges.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# ---------------------------------------------------------------------------
# §3 — the projection contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GraphProjection:
    """Names which traced runtime variables hold which pieces of graph state. The
    *only* per-topic artifact the projected tiers need (§3)."""

    current_from: str                          # scalar: the node processed this step
    visited_from: Optional[str] = None         # set/list: membership of done nodes
    visit_order_from: Optional[str] = None     # ordered list: insertion order
    selected_edges_from: Optional[str] = None  # list of pairs: chosen edges (MST, ...)
    frontier_from: Optional[str] = None        # list/heap: queue / stack / PQ
    node_key: str = "identity"                 # identity | index | val | value | attr:<n> | index:<n>
    edge_key: str = "identity"                 # identity | index:0,1 | attr:u,v
    frontier_node_key: Optional[str] = None    # identity | index:<n> | attr:<name>
    frontier_priority_key: Optional[str] = None


# ---------------------------------------------------------------------------
# Value normalization — shared by the validator (§6.3) and the projector (§4).
# ---------------------------------------------------------------------------

_PROJECTION_FIELDS = (
    "current_from",
    "visited_from",
    "visit_order_from",
    "selected_edges_from",
    "frontier_from",
)


def locals_of(step: dict[str, Any]) -> dict[str, Any]:
    """The per-line variable snapshot, whether the step is a raw tracer step
    (`{"vars": ...}`) or a folded TraceStep (`{"delta": {"set_locals": ...}}`)."""
    if "vars" in step:
        return step.get("vars") or {}
    return (step.get("delta") or {}).get("set_locals") or {}


def apply_node_key(value: Any, key: str) -> Any:
    """Map a runtime value to a node id per `node_key`. Returns None when the key
    cannot be applied (caller treats that as 'no node here')."""
    if value is None:
        return None
    key = key or "identity"
    if key == "identity":
        return value
    if key in ("val", "value"):
        if isinstance(value, dict):
            return value.get("val", value.get("value"))
        return value
    if key == "index":
        return value[0] if isinstance(value, (list, tuple)) and value else None
    if key.startswith("index:"):
        try:
            i = int(key.split(":", 1)[1])
        except ValueError:
            return None
        if isinstance(value, (list, tuple)) and -len(value) <= i < len(value):
            return value[i]
        return None
    if key.startswith("attr:"):
        attr = key.split(":", 1)[1]
        return value.get(attr) if isinstance(value, dict) else None
    return value


def to_node_id(value: Any, node_key: str) -> Optional[str]:
    nid = apply_node_key(value, node_key)
    return None if nid is None else str(nid)


def normalize_edge(value: Any, edge_key: str = "identity") -> Optional[tuple[str, str]]:
    """A runtime edge value -> a (from, to) string pair, or None."""
    key = edge_key or "identity"
    if key.startswith("attr:"):
        parts = (key.split(":", 1)[1].split(",") + ["", ""])[:2]
        if isinstance(value, dict):
            a, b = value.get(parts[0]), value.get(parts[1])
            return (str(a), str(b)) if a is not None and b is not None else None
        return None
    # identity / index:0,1 — value is a 2+ element sequence.
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (str(value[0]), str(value[1]))
    return None


def _node_id_set(base_graph: dict[str, Any]) -> set[str]:
    return {str(n) for n in (base_graph.get("nodes") or [])}


def _edge_set(base_graph: dict[str, Any]) -> set[frozenset]:
    out: set[frozenset] = set()
    for e in base_graph.get("edges") or []:
        if isinstance(e, (list, tuple)) and len(e) >= 2:
            out.add(frozenset((str(e[0]), str(e[1]))))
    return out


# ---------------------------------------------------------------------------
# §6.3 — the projection validator. "Verified, never asserted" applies to the
# contract itself: a projection that fails any check is discarded and the ladder
# drops to the next tier.
# ---------------------------------------------------------------------------


def validate_projection(
    trace_steps: list[dict[str, Any]],
    base_graph: dict[str, Any],
    projection: GraphProjection,
    *,
    min_steps: int = 2,
) -> list[str]:
    """Assert a `GraphProjection` resolves cleanly against a real trace (§6.3):
    named vars exist, values resolve to real node ids / edges, and the projected
    state is non-empty and changes across >= `min_steps` distinct states."""
    errors: list[str] = []

    # Contract shape.
    if not projection.current_from:
        errors.append("current_from is required")
    if not (projection.visited_from or projection.visit_order_from):
        errors.append("one of visited_from / visit_order_from is required")

    # Every named variable must actually appear somewhere in the trace.
    seen_vars: set[str] = set()
    for step in trace_steps:
        seen_vars |= set(locals_of(step).keys())
    for fname in _PROJECTION_FIELDS:
        var = getattr(projection, fname)
        if var and var not in seen_vars:
            errors.append(f"{fname}={var!r} never appears in the trace")
    if errors:
        return errors  # a malformed contract can't be value-resolved

    node_ids = _node_id_set(base_graph)
    edge_set = _edge_set(base_graph)
    visit_var = projection.visit_order_from or projection.visited_from

    signatures: list[tuple] = []
    any_nonempty = False
    for step in trace_steps:
        loc = locals_of(step)

        active = to_node_id(loc.get(projection.current_from), projection.node_key)
        if active is not None and active not in node_ids:
            errors.append(f"current resolves to {active!r}, not a node in base_structure")
            active = None

        vids: set[str] = set()
        raw_visited = loc.get(visit_var)
        if isinstance(raw_visited, (list, tuple, set)):
            for v in raw_visited:
                nid = to_node_id(v, projection.node_key)
                if nid is None:
                    continue
                if nid not in node_ids:
                    errors.append(f"visited contains {nid!r}, not a node in base_structure")
                else:
                    vids.add(nid)

        if projection.selected_edges_from:
            for ev in (loc.get(projection.selected_edges_from) or []):
                edge = normalize_edge(ev, projection.edge_key)
                if edge and frozenset(edge) not in edge_set:
                    errors.append(f"selected edge {edge} not in base_structure.edges")

        if active or vids:
            any_nonempty = True
        signatures.append((active, frozenset(vids)))

    if not any_nonempty:
        errors.append("projection resolves to empty state (no node ever active/visited)")
    distinct = len(set(signatures))
    if distinct < min_steps:
        errors.append(f"projection produces {distinct} distinct state(s), need >= {min_steps}")

    return list(dict.fromkeys(errors))  # de-dup, preserve order


# ---------------------------------------------------------------------------
# §4 — the projector. Reads the trace through the contract and emits node_link
# deltas (the SAME vocabulary simulate_bfs produces, plus the §4.1 edge ops), one
# step per meaningful graph event, each with a stable semantic event_id.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectionResult:
    shape: str
    projection_source: str               # "authored" | "inferred" | "llm_authored"
    projection_contract: dict[str, Any]
    deltas: list[dict[str, Any]]         # drop-in TraceSteps for DeltaFoldEngine + compiler
    raw_step_count: int
    emitted_step_count: int
    dropped_step_count: int
    warnings: list[str]
    debug: dict[str, Any]
    projector_version: str
    inference_version: Optional[str]
    state_entity_map: dict[str, Any]     # event_id -> {nodes, edges, variables}

    def initial_state(self, start: Any = None, *, frontier_kind: str = "queue") -> dict[str, Any]:
        """The fold seed mirroring graph.py's (§4 step 6). `frontier_kind` lets the
        route mark a priority-queue frontier (Dijkstra/Prim) so prose reads correctly."""
        return {
            "active": None,
            "frontier": {"kind": frontier_kind, "items": [start] if start is not None else []},
            "visited": [],
            "output": [],
            "selected_edges": [],
        }


def _frontier_node_ids(loc: dict[str, Any], projection: GraphProjection) -> Optional[list[str]]:
    if not projection.frontier_from:
        return None
    items = loc.get(projection.frontier_from)
    if not isinstance(items, (list, tuple)):
        return None
    key = projection.frontier_node_key or projection.node_key
    out: list[str] = []
    for it in items:
        nid = to_node_id(it, key)
        if nid is not None:
            out.append(nid)
    return out


def project_node_link(
    trace_steps: list[dict[str, Any]],
    base_graph: dict[str, Any],
    projection: GraphProjection,
    *,
    projection_source: str = "authored",
    inference_version: Optional[str] = None,
) -> ProjectionResult:
    """Turn a runtime trace into node_link deltas (§4). One emitted step per
    meaningful event (a node visited or an edge selected); 600 raw line-steps
    collapse to a handful. Each step carries a stable `event_id` (§4 step 5)."""
    from ..provenance import PROJECTOR_VERSION

    node_ids = _node_id_set(base_graph)
    edge_set = _edge_set(base_graph)
    visit_var = projection.visit_order_from or projection.visited_from
    uses_edges = bool(projection.selected_edges_from)

    warnings: list[str] = []
    deltas: list[dict[str, Any]] = []
    state_entity_map: dict[str, Any] = {}

    prev_active: Optional[str] = None
    prev_visited: set[str] = set()
    prev_selected: set[frozenset] = set()
    prev_frontier: list[str] = []
    emit = 0

    for step in trace_steps:
        loc = locals_of(step)

        active = to_node_id(loc.get(projection.current_from), projection.node_key)
        if active is not None and active not in node_ids:
            active = None

        order: list[str] = []
        seen: set[str] = set()
        raw_visited = loc.get(visit_var)
        if isinstance(raw_visited, (list, tuple, set)):
            for v in raw_visited:
                nid = to_node_id(v, projection.node_key)
                if nid in node_ids and nid not in seen:
                    seen.add(nid)
                    order.append(nid)

        cur_selected: list[tuple[str, str]] = []
        if uses_edges:
            for ev in (loc.get(projection.selected_edges_from) or []):
                edge = normalize_edge(ev, projection.edge_key)
                if edge and frozenset(edge) in edge_set and frozenset(edge) not in {frozenset(e) for e in cur_selected}:
                    cur_selected.append(edge)

        newly_visited = [n for n in order if n not in prev_visited]
        newly_selected = [e for e in cur_selected if frozenset(e) not in prev_selected]

        # The meaningful event: an EDGE chosen (edge-selection algos like MST), else a
        # node visited (traversals). Triggering on the edge avoids a premature "visit"
        # frame when the visited set updates one line before the edge list does.
        trigger = newly_selected if uses_edges else newly_visited
        if not trigger:
            continue

        emit_active = active if active is not None else (newly_visited[-1] if newly_visited else prev_active)
        delta: dict[str, Any] = {}
        if emit_active is not None and emit_active != prev_active:
            delta["set_active"] = emit_active
        if newly_visited:
            delta["newly_visited"] = newly_visited
            delta["append_to_output"] = newly_visited

        cur_frontier = _frontier_node_ids(loc, projection)
        if cur_frontier is not None:
            added = [n for n in cur_frontier if n not in prev_frontier]
            removed = [n for n in prev_frontier if n not in cur_frontier]
            if added:
                delta["add_to_frontier"] = added
            if removed:
                delta["remove_from_frontier"] = removed
            prev_frontier = cur_frontier

        if newly_selected:
            if len(newly_selected) > 1:
                warnings.append(f"step emitted {len(newly_selected)} new edges; only the last is highlighted active")
            for e in newly_selected:
                # add_selected_edge folds one edge; emit the growing set across the step.
                delta.setdefault("_selected_batch", []).append(list(e))
            delta["set_active_edge"] = list(newly_selected[-1])
            delta["add_selected_edge"] = list(newly_selected[-1])

        # Event identity (§4 step 5): kind + entity + emitted index, structured + stable.
        if newly_selected:
            kind, entity = "commit_edge", "-".join(newly_selected[-1])
            primary = "add_selected_edge"
        else:
            kind, entity = "visit", newly_visited[-1]
            primary = "newly_visited"
        event_id = f"{kind}:{entity}:{emit:02d}"
        delta.pop("_selected_batch", None)

        deltas.append({
            "step_index": emit,
            "trace_step_id": f"s{emit}",
            "kind": kind,
            "delta": delta,
            "primary_change": primary,
            "event_id": event_id,
            "step_role": kind,
            "learner_should_notice": (
                f"Select edge {entity}." if newly_selected else f"Visit {entity}."
            ),
        })
        state_entity_map[event_id] = {
            "nodes": ([emit_active] if emit_active else []) + [n for n in newly_visited if n != emit_active],
            "edges": [list(e) for e in newly_selected],
            "variables": [v for v in (projection.current_from, visit_var, projection.selected_edges_from) if v],
        }

        prev_active = emit_active if emit_active is not None else prev_active
        prev_visited |= set(newly_visited)
        prev_selected |= {frozenset(e) for e in newly_selected}
        emit += 1

    raw = len(trace_steps)
    return ProjectionResult(
        shape="node_link",
        projection_source=projection_source,
        projection_contract=_contract_dict(projection),
        deltas=deltas,
        raw_step_count=raw,
        emitted_step_count=len(deltas),
        dropped_step_count=raw - len(deltas),
        warnings=list(dict.fromkeys(warnings)),
        debug={d["event_id"]: d["delta"] for d in deltas},
        projector_version=PROJECTOR_VERSION,
        inference_version=inference_version,
        state_entity_map=state_entity_map,
    )


def _contract_dict(projection: GraphProjection) -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(projection)


# ---------------------------------------------------------------------------
# §8 — projection inference. Derive a GraphProjection from the trace structurally
# (typed + name-hinted), validate it, and never branch on the application name.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InferredProjectionCandidate:
    projection: GraphProjection
    confidence: float
    confidence_band: str       # "high" | "medium" | "low"
    evidence: dict[str, Any]


_CURRENT_HINTS = ("u", "v", "node", "current", "cur")
_VISITED_HINTS = ("visited", "seen", "explored", "in_mst", "done", "included")
_ORDER_HINTS = ("order", "result", "path", "output")
_EDGE_HINTS = ("mst", "tree", "edges", "path", "result")
_FRONTIER_HINTS = ("queue", "stack", "pq", "heap", "frontier")


def _hint(name: str, hints: tuple[str, ...]) -> float:
    n = name.lower()
    return 1.0 if n in hints else (0.5 if any(h in n for h in hints) else 0.0)


def _monotonic_nondecreasing(lengths: list[int]) -> bool:
    return all(b >= a for a, b in zip(lengths, lengths[1:]))


def _churns(lengths: list[int]) -> bool:
    return any(b > a for a, b in zip(lengths, lengths[1:])) and any(b < a for a, b in zip(lengths, lengths[1:]))


def infer_projection(
    trace_steps: list[dict[str, Any]], base_graph: dict[str, Any]
) -> Optional[InferredProjectionCandidate]:
    """Recover a GraphProjection from a trace by variable type + name hints, accepted
    ONLY if it passes §6.3 against the same trace (§8). No per-algorithm branches."""
    node_ids = _node_id_set(base_graph)
    if not node_ids:
        return None

    series: dict[str, list[Any]] = {}
    for step in trace_steps:
        for name, value in locals_of(step).items():
            series.setdefault(name, []).append(value)

    current: list[tuple[str, float]] = []
    visited: list[tuple[str, float]] = []
    order: list[tuple[str, float]] = []
    edges: list[tuple[str, float]] = []
    frontier: list[tuple[str, float, Optional[str]]] = []

    def is_node(x: Any) -> bool:
        return isinstance(x, (str, int)) and not isinstance(x, bool) and str(x) in node_ids

    for name, values in series.items():
        scalars = [v for v in values if isinstance(v, (str, int)) and not isinstance(v, bool)]
        node_hits = sum(1 for v in scalars if str(v) in node_ids)
        if node_hits >= max(2, len(values) // 3) and len({str(v) for v in scalars if str(v) in node_ids}) >= 2:
            current.append((name, node_hits / max(1, len(values)) + _hint(name, _CURRENT_HINTS)))

        list_vals = [v for v in values if isinstance(v, (list, tuple))]
        if not list_vals:
            continue
        lengths = [len(v) for v in list_vals]
        last = list_vals[-1]
        mono = _monotonic_nondecreasing(lengths)

        if last and all(is_node(x) for x in last) and mono and len(last) >= 2:
            if _hint(name, _ORDER_HINTS) > _hint(name, _VISITED_HINTS):
                order.append((name, 1.0 + _hint(name, _ORDER_HINTS)))
            else:
                visited.append((name, 1.0 + _hint(name, _VISITED_HINTS)))

        if last and all(isinstance(x, (list, tuple)) and len(x) >= 2 and is_node(x[0]) and is_node(x[1]) for x in last) and mono:
            edges.append((name, 1.0 + _hint(name, _EDGE_HINTS)))

        if _churns(lengths):
            # frontier items may be node ids or (priority, node) tuples.
            fkey = None
            sample = next((it for v in list_vals for it in v), None)
            if isinstance(sample, (list, tuple)) and len(sample) >= 2 and is_node(sample[1]) and not is_node(sample[0]):
                fkey = "index:1"
            frontier.append((name, _hint(name, _FRONTIER_HINTS), fkey))

    if not current or not (visited or order):
        return None

    best_current = max(current, key=lambda x: x[1])
    best_visited = max(visited, default=None, key=lambda x: x[1]) if visited else None
    best_order = max(order, default=None, key=lambda x: x[1]) if order else None
    best_edge = max(edges, default=None, key=lambda x: x[1]) if edges else None
    best_frontier = max(frontier, default=None, key=lambda x: x[1]) if frontier else None

    projection = GraphProjection(
        current_from=best_current[0],
        visited_from=best_visited[0] if best_visited else None,
        visit_order_from=best_order[0] if best_order else None,
        selected_edges_from=best_edge[0] if best_edge else None,
        frontier_from=best_frontier[0] if best_frontier else None,
        frontier_node_key=best_frontier[2] if best_frontier else None,
    )

    if validate_projection(trace_steps, base_graph, projection):
        return None  # inference proposes; the validator disposes

    hinted = sum(1 for n, h in (
        (best_current[0], _CURRENT_HINTS),
        ((best_order or best_visited)[0], _ORDER_HINTS + _VISITED_HINTS),
    ) if _hint(n, h) > 0)
    if best_edge and _hint(best_edge[0], _EDGE_HINTS) > 0:
        hinted += 1
    confidence = min(0.95, 0.5 + 0.15 * hinted)
    band = "high" if confidence >= 0.75 else ("medium" if confidence >= 0.6 else "low")
    return InferredProjectionCandidate(
        projection=projection,
        confidence=round(confidence, 3),
        confidence_band=band,
        evidence={
            "current_from": f"{best_current[0]} (scalar resolving to node ids)",
            "visited_from": best_visited[0] if best_visited else None,
            "visit_order_from": best_order[0] if best_order else None,
            "selected_edges_from": best_edge[0] if best_edge else None,
            "frontier_from": best_frontier[0] if best_frontier else None,
        },
    )
