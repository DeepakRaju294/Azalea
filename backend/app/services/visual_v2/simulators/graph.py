"""Graph traversal simulators — BFS and DFS (VISUAL_SYSTEM_SPEC §6.1).

The simulator OWNS the delta timeline for a registered algorithm: the LLM only
picks the example structure + input; this computes the authoritative trace. Edges
are treated as undirected; neighbours are visited in sorted order for determinism.
Matches the §11 BFS appendix exactly for that graph.
"""
from __future__ import annotations

from typing import Any

from ..schemas import (
    DELTA_SCHEMA_VERSION,
    SIMULATOR_VERSION,
    VISUAL_SPEC_VERSION,
    CanonicalExample,
    Trace,
    TraceStep,
)


def _adjacency(nodes: list[str], edges: list[Any]) -> dict[str, list[str]]:
    adj: dict[str, set[str]] = {n: set() for n in nodes}
    for edge in edges:
        if isinstance(edge, (list, tuple)) and len(edge) == 2:
            a, b = edge[0], edge[1]
            if a in adj and b in adj and a != b:
                adj[a].add(b)
                adj[b].add(a)
    return {n: sorted(adj[n]) for n in nodes}


def _trace(example: CanonicalExample, frontier_kind: str, start: str, steps: list[TraceStep]) -> Trace:
    return Trace(
        trace_id=f"{example.get('example_id', 'ex')}:{example.get('algorithm', '')}",
        example_id=str(example.get("example_id", "")),
        trace_source="deterministic_simulator",
        initial_state={
            "active": None,
            "frontier": {"kind": frontier_kind, "items": [start]},
            "visited": [],
            "output": [],
        },
        steps=steps,
        visual_spec_version=VISUAL_SPEC_VERSION,
        delta_schema_version=DELTA_SCHEMA_VERSION,
        simulator_version=SIMULATOR_VERSION,
    )


def _step(index: int, node: str, new_neighbours: list[str], kind: str) -> TraceStep:
    note = (
        f"Visit {node}; queue its unvisited neighbours {', '.join(new_neighbours)}."
        if new_neighbours
        else f"Visit {node}; it has no unvisited neighbours to queue."
    )
    return TraceStep(
        step_index=index,
        trace_step_id=f"s{index}",
        kind=kind,
        delta={
            "set_active": node,
            "remove_from_frontier": [node],
            "newly_visited": [node],
            "add_to_frontier": new_neighbours,
            "append_to_output": [node],
        },
        primary_change="newly_visited",
        learner_should_notice=note,
    )


def simulate_bfs(example: CanonicalExample) -> Trace:
    base = example.get("base_structure") or {}
    nodes = list(base.get("nodes") or [])
    adj = _adjacency(nodes, list(base.get("edges") or []))
    start = (example.get("input") or {}).get("start")

    frontier: list[str] = [start]
    visited: list[str] = []
    steps: list[TraceStep] = []
    while frontier:
        node = frontier.pop(0)  # queue front
        new = [n for n in adj.get(node, []) if n not in visited and n not in frontier and n != node]
        steps.append(_step(len(steps), node, new, kind="dequeue"))
        visited.append(node)
        frontier.extend(new)
    return _trace(example, "queue", start, steps)


def simulate_dfs(example: CanonicalExample) -> Trace:
    base = example.get("base_structure") or {}
    nodes = list(base.get("nodes") or [])
    adj = _adjacency(nodes, list(base.get("edges") or []))
    start = (example.get("input") or {}).get("start")

    # Mark-when-pushed so a node is never visited twice; push reverse-sorted so the
    # smallest neighbour pops (is explored) first.
    stack: list[str] = [start]
    discovered: set[str] = {start}
    visited: list[str] = []
    steps: list[TraceStep] = []
    while stack:
        node = stack.pop()  # stack top
        new = [n for n in adj.get(node, []) if n not in discovered]
        steps.append(_step(len(steps), node, new, kind="visit"))
        visited.append(node)
        for n in new:
            discovered.add(n)
        stack.extend(reversed(new))
    return _trace(example, "stack", start, steps)
