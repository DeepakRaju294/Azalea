"""Adapter manifest — the machine-readable operational source of truth (ADAPTER_DEVELOPMENT_SPEC §manifest).

One entry per adapter: its TYPE (T1-T8), family, rollout status, verification level, routing aliases +
negative guards, canonical-solution key (coding only), and named regression fixtures. The Markdown spec stays
readable for humans; THIS is what code enforces — `manifest_gaps()` cross-checks it against the live registry,
so an adapter cannot ship without a complete manifest entry, and the manifest cannot name a phantom adapter."""
from __future__ import annotations

from typing import Any

# The 8 structural types (ADAPTER_DEVELOPMENT_SPEC §2). T2 = "greedy frontier update" (frontier/relaxation,
# not merely accept/reject). T8 splits into T8a (incremental construction) / T8b (formal derivation).
ADAPTER_TYPES = {
    "T1": "iterative_traversal", "T2": "greedy_frontier_update", "T3": "divide_and_conquer",
    "T4": "search_narrowing", "T5": "dp_table_fill", "T6": "formula_application",
    "T7": "reduction_rewriting", "T8a": "incremental_construction", "T8b": "formal_derivation",
}
_REQUIRED_FIELDS = ("type", "family", "status", "verification_level", "coding", "routing_aliases")
_STATUSES = {"production", "pilot", "experimental"}


MANIFEST: dict[str, dict[str, Any]] = {
    "binary_search": {
        "type": "T4", "family": "sequence", "status": "production", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "binary_search",
        "routing_aliases": ["binary search"], "negative_guards": ["binary search tree", "bst"],
        "fixtures": ["target_present_left", "target_present_right", "target_absent",
                     "single_element_present", "single_element_absent"]},
    "bfs": {
        "type": "T1", "family": "graph", "status": "production", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "bfs",
        "routing_aliases": ["breadth-first", "breadth first", "bfs"], "negative_guards": ["tree", "bst"],
        "fixtures": ["queue_fifo_order", "disconnected_start"]},
    "dfs_iter": {
        "type": "T1", "family": "graph", "status": "production", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "dfs_iter",
        "routing_aliases": ["depth-first", "depth first", "dfs"], "negative_guards": ["tree", "bst"],
        "fixtures": ["reverse_push_order", "deep_first_before_wide"]},
    "kruskal": {
        "type": "T2", "family": "graph", "status": "production", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "kruskal",
        "routing_aliases": ["kruskal"], "negative_guards": [],
        "fixtures": ["accept_edge", "cycle_skip", "sorted_edge_order"]},
    "prim": {
        "type": "T2", "family": "graph", "status": "production", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "prim",
        "routing_aliases": ["prim"], "negative_guards": [],
        "fixtures": ["settle_lightest_crossing_edge", "skip_visited"]},
    "dijkstra": {
        "type": "T2", "family": "graph", "status": "production", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "dijkstra",
        "routing_aliases": ["dijkstra", "shortest path", "shortest-path"], "negative_guards": [],
        "fixtures": ["relax_improves", "relax_no_improvement", "settle_node"]},
    "merge_sort": {
        "type": "T3", "family": "sequence", "status": "production", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "merge_sort",
        "routing_aliases": ["merge sort", "merge_sort"], "negative_guards": [],
        "fixtures": ["split", "base_case", "merge_selection", "tail_copy"]},
    "arithmetic_eval": {
        "type": "T7", "family": "formula", "status": "production", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "arithmetic_eval",
        "routing_aliases": ["order of operations", "evaluate expression", "arithmetic expression"],
        "negative_guards": [], "fixtures": ["multiply_before_add", "left_to_right_same_precedence"]},
    "tree_inorder": {
        "type": "T1", "family": "trees", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "tree_inorder",
        "routing_aliases": ["inorder"], "negative_guards": [],
        "fixtures": ["ascending_output", "leftmost_first"]},
    "quadratic": {
        "type": "T6", "family": "algebra", "status": "pilot", "verification_level": "trace_verified",
        "coding": False, "canonical_solution": None,
        "routing_aliases": ["quadratic"], "negative_guards": [],
        "fixtures": ["two_real_roots", "repeated_root", "complex_roots"]},
    "kinematics": {
        "type": "T6", "family": "physics", "status": "pilot", "verification_level": "trace_verified",
        "coding": False, "canonical_solution": None,
        "routing_aliases": ["kinematic", "constant acceleration", "uniform acceleration"],
        "negative_guards": [], "fixtures": ["zero_initial_velocity", "nonzero_initial_velocity"]},
}


def manifest_gaps() -> list[str]:
    """Cross-check the manifest against the live registry + canonical solutions. Empty = consistent. Every
    registered adapter must have a complete entry; the manifest must name no phantom; coding <-> canonical
    solution must agree; type/status must be valid."""
    from app.services.examples.canonical_solutions import CANONICAL_SOLUTIONS
    from app.services.examples.trace_adapters import ADAPTERS

    gaps: list[str] = []
    for slug in ADAPTERS:
        if slug not in MANIFEST:
            gaps.append(f"{slug}: registered adapter has no manifest entry")
    for slug, entry in MANIFEST.items():
        if slug not in ADAPTERS:
            gaps.append(f"{slug}: manifest entry names a non-registered adapter")
            continue
        for field in _REQUIRED_FIELDS:
            if field not in entry:
                gaps.append(f"{slug}: manifest missing required field {field!r}")
        if entry.get("type") not in ADAPTER_TYPES:
            gaps.append(f"{slug}: invalid type {entry.get('type')!r}")
        if entry.get("status") not in _STATUSES:
            gaps.append(f"{slug}: invalid status {entry.get('status')!r}")
        # coding <-> canonical solution must agree
        if entry.get("coding") and entry.get("canonical_solution") not in CANONICAL_SOLUTIONS:
            gaps.append(f"{slug}: coding adapter but canonical_solution {entry.get('canonical_solution')!r} "
                        f"not in CANONICAL_SOLUTIONS")
        if not entry.get("coding") and entry.get("canonical_solution") is not None:
            gaps.append(f"{slug}: non-coding adapter must not declare a canonical_solution")
    return gaps


def by_type() -> dict[str, list[str]]:
    """Adapter slugs grouped by type — used by the type-level invariant test suites and coverage reporting."""
    out: dict[str, list[str]] = {}
    for slug, entry in MANIFEST.items():
        out.setdefault(str(entry.get("type")), []).append(slug)
    return out
