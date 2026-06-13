"""ExampleInvariantValidator (VISUAL_SYSTEM_SPEC §6.0).

A correct simulator will faithfully trace a BAD example, so the example's domain
invariants must hold BEFORE tracing. A failure retries example SELECTION, not the
trace. Slice 1 covers graph_network + BFS/DFS.
"""
from __future__ import annotations

import ast
from collections import Counter
from typing import Any

from .profiles import profile_for_mode
from .schemas import CanonicalExample


def validate_example(example: CanonicalExample) -> list[str]:
    """Return a list of invariant violations ([] means the example is valid)."""
    errors: list[str] = []
    mode = example.get("mode") or ""
    profile = profile_for_mode(mode)
    if profile is None:
        return [f"no profile registered for mode {mode!r}"]

    if profile["base_type"] == "node_link_diagram" and mode == "graph_network":
        errors.extend(_validate_graph(example, profile))
    elif mode == "binary_search_range":
        errors.extend(_validate_binary_search(example, profile))
    elif mode == "code_execution":
        errors.extend(_validate_code_execution(example, profile))
    return errors


def _validate_code_execution(example: CanonicalExample, profile: dict[str, Any]) -> list[str]:
    """Pre-trace checks for code: it parses, defines the entry function, and has a
    constructible input. Termination is bounded by the tracer's step cap."""
    errors: list[str] = []
    code = str(example.get("code") or (example.get("base_structure") or {}).get("code") or "")
    entry = str(example.get("entry_function") or (example.get("input") or {}).get("entry_function") or "")
    if not code.strip():
        return ["no code provided"]
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"code does not parse: {exc.msg} (line {exc.lineno})"]
    defined = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if not entry:
        errors.append("no entry_function specified")
    elif entry not in defined:
        errors.append(f"entry function {entry!r} is not defined in the code")
    input_spec = example.get("input") or {}
    if not any(key in input_spec for key in ("tree", "array", "args")):
        errors.append("no constructible input (expected one of: tree, array, args)")
    return errors


def _validate_binary_search(example: CanonicalExample, profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    array = list((example.get("base_structure") or {}).get("array") or [])
    min_length = int((profile.get("richness") or {}).get("min_length", 0))
    if len(array) < min_length:
        errors.append(f"too trivial: need >= {min_length} elements, got {len(array)}")
    if any(array[i] > array[i + 1] for i in range(len(array) - 1)):
        errors.append("array is not sorted ascending (binary search requires a sorted array)")
    target = (example.get("input") or {}).get("target")
    if not isinstance(target, (int, float)):
        errors.append(f"target {target!r} is not a number")
    return errors


def _validate_graph_structure(example: CanonicalExample, profile: dict[str, Any]) -> list[str]:
    """Structure-only graph checks (no start node) — shared by the dynamic and
    static (define_structure) paths."""
    errors: list[str] = []
    base = example.get("base_structure") or {}
    nodes = list(base.get("nodes") or [])
    edges = list(base.get("edges") or [])
    node_set = set(nodes)

    if len(nodes) != len(node_set):
        errors.append("duplicate node ids")

    richness = profile.get("richness") or {}
    min_nodes = int(richness.get("min_nodes", 0))
    if len(node_set) < min_nodes:
        errors.append(f"too trivial: need >= {min_nodes} nodes, got {len(node_set)}")

    degree: Counter[str] = Counter()
    for edge in edges:
        if not (isinstance(edge, (list, tuple)) and len(edge) == 2):
            errors.append(f"malformed edge {edge!r}")
            continue
        a, b = edge[0], edge[1]
        if a not in node_set or b not in node_set:
            errors.append(f"edge {edge!r} references an unknown node")
            continue
        if a == b:
            errors.append(f"self-loop at {a!r}")
        degree[a] += 1
        degree[b] += 1

    if richness.get("min_branching") and not any(d >= 2 for d in degree.values()):
        errors.append("no branching: need at least one node with degree >= 2")

    return errors


def _validate_graph(example: CanonicalExample, profile: dict[str, Any]) -> list[str]:
    errors = _validate_graph_structure(example, profile)
    node_set = set((example.get("base_structure") or {}).get("nodes") or [])
    start = (example.get("input") or {}).get("start")
    if start not in node_set:
        errors.append(f"start node {start!r} is not in the graph")
    return errors


def validate_static_example(example: CanonicalExample) -> list[str]:
    """§5.0 — a static visual is base + one at-rest state; validate the structure
    only (no trace, no start/target)."""
    mode = example.get("mode") or ""
    profile = profile_for_mode(mode)
    if profile is None:
        return [f"no profile registered for mode {mode!r}"]
    if profile["base_type"] == "node_link_diagram":
        return _validate_graph_structure(example, profile)
    return []
