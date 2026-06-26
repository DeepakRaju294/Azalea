"""Reference-first worked-example construction for algorithmic families (the correctness fix for
walkthroughs and non-executable code).

For graph/MST topics the model can't be trusted to hand-simulate the algorithm: it truncates, picks
wrong edges, and invents pseudo-code (see the disconnected/over-long examples). When there is no
executable user code to trace (algorithm walkthroughs) or the code won't run, we build the worked
example from a TRUSTED INTERNAL reference run of the algorithm on the real input — so the steps,
states, and final answer are COMPUTED, not guessed. Same correctness guarantee as trace_first
(``build_cards_from_trace``), sourced from the reference rather than from user code.

Pure: graph input in, card skeletons out. A downstream narration pass writes prose around the
verified states; it never changes a state or the final answer.
"""
from __future__ import annotations

import heapq
from collections import defaultdict
from typing import Any

from .property_checks import _node_labels, _weighted_edges
from .trace_first import canonical_final_answer


def _algorithm_for(title: str) -> str:
    """Pick the algorithm the topic is teaching so the trace matches it (Prim grows a frontier from a
    start vertex; Kruskal sorts edges globally). Same MST, different teaching narrative."""
    return "prim" if "prim" in (title or "").lower() else "kruskal"


def _components_str(find, nodes: set[str]) -> str:
    groups: dict[str, list[str]] = defaultdict(list)
    for n in sorted(nodes):
        groups[find(n)].append(n)
    return ", ".join("{" + ", ".join(g) + "}" for g in groups.values())


def kruskal_steps(nodes: set[str], edges: list[tuple[str, str, float]]):
    """One step per edge considered in weight order: select (joins two components) or skip (cycle).
    Returns (steps, mst) where each step carries the real running MST + component partition."""
    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    mst: list[tuple[str, str, float]] = []
    target = len(nodes) - 1
    steps: list[dict[str, Any]] = []
    for u, v, w in sorted(edges, key=lambda e: (e[2], str(e[0]), str(e[1]))):
        if u not in parent or v not in parent:
            continue
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
            mst.append((u, v, w))
            action = "select"
        else:
            action = "skip"
        steps.append({"action": action, "edge": (u, v, w), "mst": list(mst),
                      "components": _components_str(find, nodes)})
        if len(mst) >= target:
            break
    return steps, mst


def prim_steps(nodes: set[str], edges: list[tuple[str, str, float]], start: str):
    """One step per cheapest frontier edge popped: select (reaches a new vertex) or skip (already in).
    Returns (steps, mst) where each step carries the real running MST + visited set."""
    adj: dict[str, list[tuple[float, str, str]]] = defaultdict(list)
    for u, v, w in edges:
        adj[u].append((w, u, v))
        adj[v].append((w, v, u))
    visited = {start}
    mst: list[tuple[str, str, float]] = []
    heap = list(adj[start])
    heapq.heapify(heap)
    steps: list[dict[str, Any]] = []
    while heap and len(visited) < len(nodes):
        w, frm, to = heapq.heappop(heap)
        if to in visited:
            steps.append({"action": "skip", "edge": (frm, to, w), "mst": list(mst),
                          "visited": sorted(visited)})
            continue
        visited.add(to)
        mst.append((frm, to, w))
        steps.append({"action": "select", "edge": (frm, to, w), "mst": list(mst),
                      "visited": sorted(visited)})
        for w2, _f, nxt in adj[to]:
            if nxt not in visited:
                heapq.heappush(heap, (w2, to, nxt))
    return steps, mst


def _fmt_edge(e: tuple[str, str, float]) -> str:
    u, v, w = e
    return f"({u}, {v}, {w:g})"


def _fmt_mst(mst: list[tuple[str, str, float]]) -> str:
    return ", ".join(_fmt_edge(e) for e in mst) or "(empty)"


def build_reference_cards(topic_family: str, title: str, example_input: Any) -> dict[str, Any]:
    """Build COMPLETE, state-accurate worked-example cards from a trusted reference run of the MST
    algorithm. Returns {cards, final_answer, ...} or {} when this isn't an MST topic / has no graph.

    The cards mirror ``trace_first`` card shape (goal/reasoning/work/result + real ``state``), so the
    same renderer, validators, and gate-skip semantics apply. ``final_answer`` is the real MST."""
    if "mst" not in (topic_family or "").lower():
        return {}
    nodes = _node_labels(example_input)
    edges = _weighted_edges(example_input)
    if len(nodes) < 2 or not edges:
        return {}

    algo = _algorithm_for(title)
    if algo == "prim":
        steps, mst = prim_steps(nodes, edges, start=sorted(nodes)[0])
    else:
        steps, mst = kruskal_steps(nodes, edges)
    if not steps:
        return {}

    cards: list[dict[str, Any]] = []
    prior: dict[str, Any] | None = None
    for idx, s in enumerate(steps, start=1):
        edge = s["edge"]
        es = _fmt_edge(edge)
        u, v, _w = edge
        mst_str = _fmt_mst(s["mst"])
        if s["action"] == "select":
            if algo == "prim":
                goal = f"Add edge {es} to the tree, reaching vertex {v}."
                reasoning = f"{es} is the cheapest edge leaving the visited set, and {v} is not yet in it."
                work = [f"select {es} // cheapest frontier edge — add {v} to the tree"]
            else:
                goal = f"Add edge {es} to the MST."
                reasoning = f"{es} is the smallest remaining edge joining two separate components, so it forms no cycle."
                work = [f"select {es} // {u} and {v} are in different components — no cycle"]
            result = f"MST so far: {mst_str}"
        else:
            if algo == "prim":
                goal = f"Discard edge {es}."
                reasoning = f"{v} is already in the tree, so {es} would revisit a reached vertex."
                work = [f"skip {es} // {v} already visited"]
            else:
                goal = f"Skip edge {es}."
                reasoning = f"{u} and {v} are already connected, so {es} would create a cycle."
                work = [f"skip {es} // {u} and {v} already in the same component"]
            result = f"MST unchanged: {mst_str}"

        state: dict[str, Any] = {"mst": [list(e) for e in s["mst"]]}
        if "components" in s:
            state["components"] = s["components"]
        if "visited" in s:
            state["visited"] = s["visited"]
        cards.append({
            "card_id": f"step_{idx}",
            "title": goal,
            "goal": goal,
            "reasoning": reasoning,
            "work": work,
            "result": result,
            "prior_state": prior,
            "state": state,
            "code_refs": [],
            "state_relevance": "none",
            "state_delta": None,
            "cases_covered": [],
            "trace_backed": True,
        })
        prior = state

    # Problem statement built from the SAME input the cards solve, so the stated graph and the worked
    # solution can never disagree (single source of truth).
    edge_list = ", ".join(_fmt_edge(e) for e in sorted(edges, key=lambda e: (str(e[0]), str(e[1]))))
    problem = (f"Find a minimum spanning tree of the weighted graph with vertices "
               f"{{{', '.join(sorted(nodes))}}} and edges {edge_list}.")

    final = [list(e) for e in mst]
    return {
        "cards": cards,
        "problem": problem,
        "final_answer": final,
        "final_answer_struct": canonical_final_answer(final),
        "trace_backed": True,
        "source": "reference_first",
        "total_weight": sum(w for _u, _v, w in mst),
    }
