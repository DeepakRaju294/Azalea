"""Adapter manifest — the machine-readable operational source of truth (ADAPTER_DEVELOPMENT_SPEC §manifest).

One entry per adapter: its TYPE (T1-T8), family, rollout status, verification level, routing aliases +
negative guards, canonical-solution key (coding only), and named regression fixtures. The Markdown spec stays
readable for humans; THIS is what code enforces — `manifest_gaps()` cross-checks it against the live registry,
so an adapter cannot ship without a complete manifest entry, and the manifest cannot name a phantom adapter."""
from __future__ import annotations

from typing import Any

# The structural types (ADAPTER_DEVELOPMENT_SPEC §2). T2 = "greedy frontier update" (frontier/relaxation, not
# merely accept/reject). T8 splits into T8a/T8b. T9/T10 keep distinct trace shapes out of T2/T3: Bellman-Ford
# is pass-based repeated relaxation (NOT a frontier greedy); heap sort is heap-invariant restoration (NOT
# split/combine divide-and-conquer).
ADAPTER_TYPES = {
    "T1": "structured_traversal",              # queue / stack / recursion / parent-pointer frontier (not only iterative)
    "T2": "greedy_frontier_update", "T3": "divide_and_conquer",
    "T4": "search_narrowing", "T5": "dp_table_fill", "T6": "formula_application",
    "T7": "reduction_rewriting", "T8a": "incremental_construction", "T8b": "formal_derivation",
    # T9 splits: T9a edge-pass relaxation (Bellman-Ford; pass-based) vs T9b layered state refinement
    # (Floyd-Warshall; "shortest path using only intermediates in the processed set") — different invariants.
    "T9a": "edge_pass_relaxation", "T9b": "layered_state_refinement",
    "T10": "stateful_operation_invariant_maintenance",   # mutate/probe/rotate/resize/evict/restore/compress/schedule
    # T11 backtracking (choose/explore/undo); T12 program-execution / memory trace (variables/loops/stack/pointers).
    "T11": "constraint_search_backtracking", "T12": "program_execution_memory_trace",
}

# Raw-trace ceiling per type — the MAX learner-facing steps a bounded instance may produce (headroom above the
# observed maxima). Guards against a new adapter of a type exploding into a 40-card lesson. The tighter
# PEDAGOGICAL targets live in the spec (§ trace budgets); adapters near the ceiling use teaching-projection
# grouping (§2.5.2) rather than raising this.
TYPE_TRACE_BUDGET = {
    "T1": 12, "T2": 16, "T3": 12, "T4": 8, "T5": 16, "T6": 8,
    "T7": 12, "T8a": 16, "T8b": 16, "T9a": 20, "T9b": 18, "T10": 16,
    "T11": 18, "T12": 16,
}

# Per-type VISUAL budget — the maximum ACTIVE emphasis a single frame may show. A frame may hold complete
# semantic state in DATA, but must visually emphasize only the minimum needed for the current transition
# (guards against dense, text-heavy snapshots). Declared here; enforced by the visual compiler.
TYPE_VISUAL_BUDGET = {
    "T1": "current node + frontier + visited set",
    "T2": "current candidate + the distances/edges that changed",
    "T3": "the active split/merge frame + its two child runs",
    "T4": "the current probe + the eliminated region",
    "T5": "one active cell + its direct dependency cells",
    "T6": "the current equation + the values just substituted",
    "T7": "the reducible part being rewritten + its result",
    "T8a": "the piece just added + the local validity region",
    "T8b": "the current derivation step + the rule cited",
    "T9a": "one active relax + its edge + the changed distance",
    "T9b": "one active update + the relevant row/column/k-layer",
    "T10": "one operation + the local invariant region it repairs",
    "T11": "the current branch + one shown backtrack path",
    "T12": "the current line + only the affected variables/frames",
}

# Per-failure behavior. A correct trace whose VISUAL compile or FRONTEND render fails must still ship the
# verified TEXT cards — losing a whole lesson over a rendering hiccup is worse than degrading gracefully. But
# an INVALID trace ships nothing. Default for all adapters; a manifest entry may override `failure_policy`.
DEFAULT_FAILURE_POLICY = {
    "invalid_trace": "retry_then_withhold",               # nothing ships from a wrong trace
    "prose_claim_violation": "regenerate_prose_then_withhold",
    "visual_compile_failure": "show_verified_text_trace_if_available",
    "frontend_render_failure": "show_safe_text_fallback_and_log",
}

_REQUIRED_FIELDS = ("type", "family", "status", "verification_level", "coding", "routing_aliases",
                    "telemetry_key", "visual_contract", "feature_flag")
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
    "bst_search": {
        "type": "T4", "family": "trees", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "bst_search",
        "routing_aliases": ["bst search", "binary search tree search"],
        "negative_guards": ["binary search array"],
        "fixtures": ["found_after_left", "found_after_right", "absent"]},
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


def _fill_defaults() -> None:
    """Fill the forward-looking metadata (§2 of the catalog) so every entry satisfies the schema without
    hand-writing it 11×: telemetry_key defaults to the slug, feature_flag to None (production = always on),
    visual_contract to a per-family placeholder until the real contract is authored."""
    for slug, entry in MANIFEST.items():
        entry.setdefault("telemetry_key", slug)
        entry.setdefault("feature_flag", None)
        entry.setdefault("visual_contract", f"{entry.get('family', 'generic')}_state_v1")


_fill_defaults()


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
    for tid in ADAPTER_TYPES:
        if tid not in TYPE_TRACE_BUDGET:
            gaps.append(f"type {tid} has no TYPE_TRACE_BUDGET entry")
        if tid not in TYPE_VISUAL_BUDGET:
            gaps.append(f"type {tid} has no TYPE_VISUAL_BUDGET entry")
    return gaps


def by_type() -> dict[str, list[str]]:
    """Adapter slugs grouped by type — used by the type-level invariant test suites and coverage reporting."""
    out: dict[str, list[str]] = {}
    for slug, entry in MANIFEST.items():
        out.setdefault(str(entry.get("type")), []).append(slug)
    return out


def trace_budget(slug: str) -> int:
    """The raw-trace step ceiling for an adapter's type (a bounded instance must not exceed it)."""
    return TYPE_TRACE_BUDGET.get(str(MANIFEST.get(slug, {}).get("type")), 20)


def visual_budget(slug: str) -> str:
    """The max active visual emphasis for an adapter's type (a frame shows no more than this)."""
    return TYPE_VISUAL_BUDGET.get(str(MANIFEST.get(slug, {}).get("type")), "")


def failure_policy(slug: str) -> dict[str, str]:
    """The per-failure behavior for an adapter: its manifest override merged over the default. A correct trace
    with a visual/render failure ships verified TEXT; an invalid trace ships nothing."""
    policy = dict(DEFAULT_FAILURE_POLICY)
    policy.update((MANIFEST.get(slug, {}) or {}).get("failure_policy") or {})
    return policy
