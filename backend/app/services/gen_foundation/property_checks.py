"""Family property checks (Layer 3): cheap invariants that catch a *correct-looking* wrong answer.

Execution (Layer 1) proves the trace matches the code; it does NOT prove the code solves the problem.
These per-family invariants are the first, cheapest correctness oracle — e.g. an MST on V nodes has
exactly V-1 edges, so the reviewer's phantom-`(0, start)` edge (V entries) is caught here even though
the total weight is right and the completeness gate passed.

Run as SHADOW telemetry (record violations, don't gate) until a family's reliability is measured —
properties precede gating (the agreed rollout). Defensive by construction: any parse ambiguity returns
NO violation (never crash the pipeline, never false-reject a valid example we can't confidently read).
"""
from __future__ import annotations

from typing import Any, Callable, Optional


def _as_number_list(value: Any) -> Optional[list[float]]:
    """The value as a flat list of numbers, or None if it isn't cleanly one."""
    if not isinstance(value, (list, tuple)) or not value:
        return None
    out: list[float] = []
    for v in value:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        out.append(v)
    return out


def _node_count(example_input: Any) -> Optional[int]:
    if isinstance(example_input, dict):
        nodes = example_input.get("nodes")
        if isinstance(nodes, (list, tuple)):
            return len(nodes)
        graph = example_input.get("graph")
        if isinstance(graph, dict):
            return len(graph)
        if all(isinstance(v, (list, tuple)) for v in example_input.values()) and example_input:
            return len(example_input)  # the input IS an adjacency map
    return None


def _node_labels(example_input: Any) -> set[str]:
    if isinstance(example_input, dict):
        nodes = example_input.get("nodes")
        if isinstance(nodes, (list, tuple)):
            return {str(n) for n in nodes}
        graph = example_input.get("graph")
        if isinstance(graph, dict):
            return {str(k) for k in graph}
        if all(isinstance(v, (list, tuple)) for v in example_input.values()):
            return {str(k) for k in example_input}
    return set()


def _mst_edges(output: Any) -> Optional[list]:
    """The edge list inside an MST return like ``(weight, edges)`` or ``{'edges': [...]}``, else None."""
    if isinstance(output, dict) and isinstance(output.get("edges"), (list, tuple)):
        return list(output["edges"])
    if isinstance(output, (list, tuple)):
        for part in output:
            if isinstance(part, (list, tuple)) and part and all(isinstance(e, (list, tuple)) for e in part):
                return list(part)
    return None


# --- per-family checks --------------------------------------------------------

def check_sort(example_input: Any, output: Any) -> list[str]:
    src = _as_number_list(example_input if not isinstance(example_input, dict)
                          else example_input.get("array"))
    res = _as_number_list(output)
    if res is None:
        return []
    viol: list[str] = []
    if any(res[i] > res[i + 1] for i in range(len(res) - 1)):
        viol.append("sort: output is not in nondecreasing order")
    if src is not None and sorted(src) != sorted(res):
        viol.append("sort: output is not a permutation of the input (values added/dropped)")
    return viol


def check_mst(example_input: Any, output: Any) -> list[str]:
    v = _node_count(example_input)
    edges = _mst_edges(output)
    viol: list[str] = []
    if v and edges is not None and len(edges) != v - 1:
        viol.append(f"mst: {len(edges)} edges, but an MST on {v} connected nodes has exactly "
                    f"V-1={v - 1} (likely a phantom seed edge or a missing/duplicate edge)")
    return viol


def check_traversal(example_input: Any, output: Any) -> list[str]:
    seq = output[0] if (isinstance(output, (list, tuple)) and output
                        and isinstance(output[0], (list, tuple))) else output
    if not isinstance(seq, (list, tuple)) or not seq:
        return []
    labels = _node_labels(example_input)
    viol: list[str] = []
    as_str = [str(x) for x in seq]
    if len(as_str) != len(set(as_str)):
        viol.append("traversal: output visits the same node more than once")
    if labels and any(x not in labels for x in as_str):
        viol.append("traversal: output contains nodes that are not in the graph")
    return viol


_CHECKS: list[tuple[tuple[str, ...], Callable[[Any, Any], list[str]]]] = [
    (("sort",), check_sort),
    (("mst", "spanning", "prim", "kruskal"), check_mst),
    (("bfs", "dfs", "traversal", "breadth", "depth"), check_traversal),
]


def family_properties(topic_family: str, example_input: Any, output: Any) -> list[str]:
    """Run the property checks whose keyword matches the family. Never raises."""
    fam = (topic_family or "").lower()
    violations: list[str] = []
    for keywords, check in _CHECKS:
        if any(k in fam for k in keywords):
            try:
                violations.extend(check(example_input, output))
            except Exception:  # noqa: BLE001 — telemetry must never break generation
                pass
    return violations
