"""Adapter manifest — the machine-readable operational source of truth (ADAPTER_DEVELOPMENT_SPEC §manifest).

One entry per adapter: its TYPE (T1-T8), family, rollout status, verification level, routing aliases +
negative guards, canonical-solution key (coding only), and named regression fixtures. The Markdown spec stays
readable for humans; THIS is what code enforces — `manifest_gaps()` cross-checks it against the live registry,
so an adapter cannot ship without a complete manifest entry, and the manifest cannot name a phantom adapter."""
from __future__ import annotations

from typing import Any, Optional

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
    # T13 proof-obligation discharge (induction etc.): assumptions -> discharged obligations -> conclusion; NOT an
    # equality chain like T8b. Obligations are machine-checkable (base case + inductive-step polynomial identity).
    "T13": "proof_obligation_discharge",
    # T14 indexed table evaluation: independent per-cell evaluation + a table invariant (exhaustive rows) —
    # distinct from T5 DP recurrence. T15 matrix row-operation elimination (Gauss-Jordan): pivot + structured
    # row op over a matrix, invariant = solution-set preservation — distinct from T7 scalar rewriting.
    "T14": "indexed_table_evaluation",
    "T15": "matrix_row_operation_elimination",
    # T16 numerical time-step convergence: iterate + residual + stopping/convergence check — distinct from T8a's
    # "add a valid piece" (models tolerance/residual/convergence).
    "T16": "numerical_time_step_convergence",
}

# Raw-trace ceiling per type — the MAX learner-facing steps a bounded instance may produce (headroom above the
# observed maxima). Guards against a new adapter of a type exploding into a 40-card lesson. The tighter
# PEDAGOGICAL targets live in the spec (§ trace budgets); adapters near the ceiling use teaching-projection
# grouping (§2.5.2) rather than raising this.
# Three SEPARATE size limits (spec §7.1). The generator's `candidates()` owns the INSTANCE cap (InstanceShape).
# TYPE_TRACE_BUDGET is the SEMANTIC-EVENT ceiling — the max full-trace steps a bounded instance may retain
# (enforced on len(trace.steps) across seeds). TYPE_TEACHING_TARGET is the learner-facing checkpoint count the
# adapter's teaching projection (base.select_teaching_checkpoints) should aim for — always <= the ceiling.
TYPE_TRACE_BUDGET = {
    "T1": 12, "T2": 16, "T3": 12, "T4": 8, "T5": 16, "T6": 8,
    "T7": 12, "T8a": 16, "T8b": 16, "T9a": 20, "T9b": 18, "T10": 16,
    "T11": 18, "T12": 16, "T13": 8, "T14": 16, "T15": 16, "T16": 34,
}
TYPE_TEACHING_TARGET = {
    "T1": 10, "T2": 12, "T3": 10, "T4": 7, "T5": 12, "T6": 6,
    "T7": 10, "T8a": 12, "T8b": 12, "T9a": 14, "T9b": 10, "T10": 12,
    "T11": 12, "T12": 12, "T13": 6, "T14": 12, "T15": 12, "T16": 14,
}


def _vb(focus_roles: list[str], emphasis: str) -> dict[str, Any]:
    # A frame may hold COMPLETE semantic state in data, but must EMPHASIZE only these — numeric so a visual
    # compiler / golden test can reject a frame that highlights 14 things at once.
    return {"max_focus_entities": 3, "max_new_labels": 4, "max_changed_entities": 5,
            "max_visible_state_groups": 4, "focus_roles": list(focus_roles), "emphasis": emphasis}


# Per-type VISUAL budget (spec §7.2) — machine-testable numeric limits + the allowed focus roles.
TYPE_VISUAL_BUDGET = {
    "T1": _vb(["current", "frontier", "visited"], "current node + frontier + visited set"),
    "T2": _vb(["candidate", "changed", "result"], "current candidate + the distances/edges that changed"),
    "T3": _vb(["active_frame", "child_runs"], "the active split/merge frame + its two child runs"),
    "T4": _vb(["probe", "eliminated"], "the current probe + the eliminated region"),
    "T5": _vb(["active_cell", "dependencies"], "one active cell + its direct dependency cells"),
    "T6": _vb(["current_equation", "substituted"], "the current equation + the values just substituted"),
    "T7": _vb(["reducible_part", "result"], "the reducible part being rewritten + its result"),
    "T8a": _vb(["added_piece", "validity_region"], "the piece just added + the local validity region"),
    "T8b": _vb(["derivation_step", "rule"], "the current derivation step + the rule cited"),
    "T9a": _vb(["relax_edge", "changed_distance", "pass"], "one active relax + its edge + the changed distance"),
    "T9b": _vb(["active_cell_k", "dependencies"], "current k + active dist[i][j] + its two dependency entries"),
    "T10": _vb(["operation_target", "repaired_region"], "one operation + the local invariant region repaired"),
    "T11": _vb(["current_choice", "violated_constraint", "undo_target"], "current branch + one backtrack path"),
    "T12": _vb(["current_line", "affected_vars", "active_frame"], "current line + only affected variables/frame"),
    "T13": _vb(["current_obligation", "hypothesis"], "the obligation being discharged + the assumption used"),
    "T14": _vb(["active_row", "cell_value"], "the row being evaluated + the cell value just computed"),
    "T15": _vb(["pivot_row", "target_row", "eliminated_column"],
               "the pivot row + the row being reduced + the column being cleared"),
    "T16": _vb(["current_estimate", "residual"], "the current estimate + how the residual shrank"),
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
    "insertion_sort": {
        "type": "T8a", "family": "sequence", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "insertion_sort",
        "routing_aliases": ["insertion sort", "insertion_sort"], "negative_guards": [],
        "fixtures": ["shift_insert", "stay_in_place"]},
    "selection_sort": {
        "type": "T8a", "family": "sequence", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "selection_sort",
        "routing_aliases": ["selection sort", "selection_sort"], "negative_guards": [],
        "fixtures": ["swap_needed", "already_min"]},
    "bubble_sort": {
        "type": "T8a", "family": "sequence", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "bubble_sort",
        "routing_aliases": ["bubble sort", "bubble_sort"], "negative_guards": [],
        "fixtures": ["swap_needed", "no_swap_early_exit"]},
    "quick_sort": {
        "type": "T3", "family": "sequence", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "quick_sort",
        "routing_aliases": ["quicksort", "quick sort", "quick_sort"], "negative_guards": [],
        "fixtures": ["multi_element_partition", "completion"]},
    "heap_sort": {
        "type": "T8a", "family": "sequence", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "heap_sort",
        "routing_aliases": ["heapsort", "heap sort", "heap_sort"], "negative_guards": [],
        "fixtures": ["build_sift", "extract_max", "sift_swap"]},
    "longest_increasing_subsequence": {
        "type": "T5", "family": "dynamic_programming", "status": "pilot",
        "verification_level": "trace_verified", "coding": True,
        "canonical_solution": "longest_increasing_subsequence",
        "routing_aliases": ["longest increasing subsequence", "increasing subsequence",
                            "longest_increasing_subsequence"],
        "negative_guards": [], "fixtures": ["fresh_start", "extend_from_predecessor"]},
    "coin_change": {
        "type": "T5", "family": "dynamic_programming", "status": "pilot",
        "verification_level": "trace_verified", "coding": True, "canonical_solution": "coin_change",
        "routing_aliases": ["coin change", "coin_change", "fewest coins", "minimum coins", "making change"],
        "negative_guards": [], "fixtures": ["single_coin", "build_from_subproblem"]},
    "house_robber": {
        "type": "T5", "family": "dynamic_programming", "status": "pilot",
        "verification_level": "trace_verified", "coding": False, "canonical_solution": None,
        "routing_aliases": ["house robber", "house_robber", "rob houses", "max non-adjacent sum",
                            "maximum non adjacent sum", "non-adjacent sum"],
        "negative_guards": [], "fixtures": ["rob_house", "skip_house"]},
    "max_subarray": {
        "type": "T5", "family": "dynamic_programming", "status": "pilot",
        "verification_level": "trace_verified", "coding": False, "canonical_solution": None,
        "routing_aliases": ["maximum subarray", "max subarray", "max_subarray", "largest contiguous sum",
                            "kadane's algorithm", "kadane algorithm", "maximum subarray sum"],
        "negative_guards": [], "fixtures": ["extend", "restart"]},
    "rod_cutting": {
        "type": "T5", "family": "dynamic_programming", "status": "pilot",
        "verification_level": "trace_verified", "coding": False, "canonical_solution": None,
        "routing_aliases": ["rod cutting", "rod_cutting", "cut the rod", "rod cutting problem",
                            "maximize rod revenue"],
        "negative_guards": [], "fixtures": ["single_piece", "combine_pieces"]},
    "edit_distance": {
        "type": "T5", "family": "dynamic_programming", "status": "pilot",
        "verification_level": "trace_verified", "coding": False, "canonical_solution": None,
        "routing_aliases": ["edit distance", "edit_distance", "levenshtein distance", "levenshtein",
                            "string edit distance", "minimum edits"],
        "negative_guards": [], "fixtures": ["match", "edit"]},
    "n_queens": {
        "type": "T11", "family": "backtracking", "status": "pilot",
        "verification_level": "trace_verified", "coding": True, "canonical_solution": "n_queens",
        "routing_aliases": ["n-queens", "n queens", "nqueens", "eight queens", "queens problem"],
        "negative_guards": [], "fixtures": ["place", "backtrack"]},
    "topological_sort": {
        "type": "T1", "family": "graph", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "topological_sort",
        "routing_aliases": ["topological sort", "topological ordering", "topological_sort", "topo sort",
                            "kahn"],
        "negative_guards": [], "fixtures": ["frees_dependents", "completion"]},
    "bellman_ford": {
        "type": "T9a", "family": "graph", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "bellman_ford",
        "routing_aliases": ["bellman-ford", "bellman ford", "bellman_ford", "bellmanford"],
        "negative_guards": [], "fixtures": ["relax_improves", "converged"]},
    "floyd_warshall": {
        "type": "T9b", "family": "graph", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "floyd_warshall",
        "routing_aliases": ["floyd-warshall", "floyd warshall", "floyd_warshall", "all-pairs shortest paths"],
        "negative_guards": [], "fixtures": ["layer_improves", "layer_no_change"]},
    "union_find": {
        "type": "T10", "family": "structures", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "union_find",
        "routing_aliases": ["union-find", "union find", "disjoint set", "disjoint-set", "union_find"],
        "negative_guards": [], "fixtures": ["merge", "already_connected"]},
    "euclid_gcd": {
        "type": "T12", "family": "execution", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "euclid_gcd",
        "routing_aliases": ["euclid", "euclidean algorithm", "gcd", "greatest common divisor"],
        "negative_guards": [], "fixtures": ["reduce", "loop_ends"]},
    "sieve_of_eratosthenes": {
        "type": "T8a", "family": "number_theory", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "sieve_of_eratosthenes",
        "routing_aliases": ["sieve", "sieve of eratosthenes", "eratosthenes"],
        "negative_guards": [], "fixtures": ["mark_prime", "completion"]},
    "induction_proof": {
        "type": "T8b", "family": "proof", "status": "pilot", "verification_level": "trace_verified",
        "coding": False, "canonical_solution": None,
        "routing_aliases": ["induction", "proof by induction", "mathematical induction", "prove that"],
        "negative_guards": [], "fixtures": ["base_case", "inductive_step"]},
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
    "tree_preorder": {
        "type": "T1", "family": "trees", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "tree_preorder",
        "routing_aliases": ["preorder", "pre-order"], "negative_guards": [],
        "fixtures": ["root_first", "right_branch"]},
    "tree_postorder": {
        "type": "T1", "family": "trees", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "tree_postorder",
        "routing_aliases": ["postorder", "post-order"], "negative_guards": [],
        "fixtures": ["leaf", "root_last"]},
    "tree_levelorder": {
        "type": "T1", "family": "trees", "status": "pilot", "verification_level": "trace_verified",
        "coding": True, "canonical_solution": "tree_levelorder",
        "routing_aliases": ["level order", "level-order", "levelorder"], "negative_guards": [],
        "fixtures": ["root_level", "deeper_level"]},
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
    # T6 Formula Engine concepts (CP12b) are injected below from families/formula_specs.py — each FormulaSpec
    # carries its own family + aliases + priority, so the manifest, routing table, and registry are all derived
    # from ONE source (adding a concept is a one-file edit). See _inject_formula_specs().
}


def _inject_formula_specs() -> None:
    """Derive the manifest entry + routing rule for every registered FormulaSpec (T6) and RewriteSpec (T7) from
    the spec itself, so those concepts have exactly ONE source of truth (families/*_specs.py). Imported lazily
    to avoid an import cycle at module load (the engines import decl/example_spec, not this module)."""
    from .families import construct_engine as ce
    from .families import derivation_engine as de
    from .families import formula_engine as fe
    from .families import induction_engine as ie
    from .families import rewrite_engine as re_
    from .families import rowreduce_engine as rr
    from .families import numerical_engine as ne
    from .families import stateful_engine as se
    from .families import table_engine as te
    for mod in (fe, re_, ce, de, se, rr, te, ne, ie):
        for spec in mod.registered_specs():
            MANIFEST.setdefault(spec.slug, mod.manifest_entry(spec))
            ROUTING_RULES.setdefault(spec.slug, mod.routing_rule(spec))


def _fill_defaults() -> None:
    """Fill the forward-looking metadata (§2 of the catalog) so every entry satisfies the schema without
    hand-writing it 11×: telemetry_key defaults to the slug, feature_flag to None (production = always on),
    visual_contract to a per-family placeholder until the real contract is authored."""
    for slug, entry in MANIFEST.items():
        entry.setdefault("telemetry_key", slug)
        entry.setdefault("feature_flag", None)
        entry.setdefault("visual_contract", f"{entry.get('family', 'generic')}_state_v1")


# NOTE: _inject_formula_specs() + _fill_defaults() are invoked at the BOTTOM of the module, after ROUTING_RULES
# is defined (injection writes into it) and so the injected entries also receive the schema defaults.


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
        if tid not in TYPE_TEACHING_TARGET:
            gaps.append(f"type {tid} has no TYPE_TEACHING_TARGET entry")
        elif TYPE_TEACHING_TARGET.get(tid, 0) > TYPE_TRACE_BUDGET.get(tid, 0):
            gaps.append(f"type {tid}: teaching target > semantic ceiling")
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


def teaching_target(slug: str) -> int:
    """The learner-facing checkpoint target for an adapter's type (the projection should aim for this)."""
    return TYPE_TEACHING_TARGET.get(str(MANIFEST.get(slug, {}).get("type")), 12)


def visual_budget(slug: str) -> dict[str, Any]:
    """The machine-testable visual budget for an adapter's type (numeric focus limits + allowed roles)."""
    return TYPE_VISUAL_BUDGET.get(str(MANIFEST.get(slug, {}).get("type")), _vb([], ""))


def failure_policy(slug: str) -> dict[str, str]:
    """The per-failure behavior for an adapter: its manifest override merged over the default. A correct trace
    with a visual/render failure ships verified TEXT; an invalid trace ships nothing."""
    policy = dict(DEFAULT_FAILURE_POLICY)
    policy.update((MANIFEST.get(slug, {}) or {}).get("failure_policy") or {})
    return policy


# --- Declarative routing (data-driven; replaces the hand-written if-chain in trace_pipeline) --------------
# Each rule: any=OR substrings · word=OR whole-word tokens (boundary-matched) · all=AND substrings (checked
# AFTER `strip`) · strip=substrings removed before the `all` check · not=blocking substrings · priority=
# match precedence (higher wins; set to the old if-chain order so "highest-priority match" == "first `if`").
# This is the single source of truth for routing — adding an adapter adds ONE rule here, no code change.
_IS_TREE = ["tree", "bst", "inorder", "preorder", "postorder", "level order", "level-order", "subtree", "leaf"]

ROUTING_RULES: dict[str, dict[str, Any]] = {
    # Space forms are FULL PHRASES ("in order traversal", never bare "in order") — decomposition emits
    # un-hyphenated titles ("Implementing Post Order Traversal"), and without these the coding topics failed
    # to route, so canonical verified code was never stamped and inconsistent LLM code shipped (live bug).
    "tree_inorder": {"any": ["inorder", "in-order", "in order traversal"], "priority": 290},
    "tree_preorder": {"any": ["preorder", "pre-order", "pre order traversal"], "priority": 280},
    "tree_postorder": {"any": ["postorder", "post-order", "post order traversal"], "priority": 270},
    "tree_levelorder": {"any": ["level order", "level-order", "levelorder"], "priority": 260},
    # a BST *search* is a tree probe, not array binary search: needs a 'search' OPERATION that survives
    # stripping the structure name "binary search tree" (so the bare structure doesn't self-trigger).
    "bst_search": {"any": ["bst", "binary search tree"], "all": ["search"],
                   "strip": ["binary search tree", "binary-search tree"], "priority": 250},
    # the quadratic adapter solves via the discriminant/quadratic formula; a topic that explicitly asks for
    # "completing the square" wants that METHOD, so don't route it here (it falls to complete_the_square / legacy).
    "quadratic": {"any": ["quadratic"], "not": ["completing the square", "complete the square",
                                                "completing square", "complete square"], "priority": 240},
    "kinematics": {"any": ["kinematic", "constant acceleration", "uniform acceleration"], "priority": 230},
    "binary_search": {"any": ["binary search", "binary_search"], "not": _IS_TREE, "priority": 220},
    "kruskal": {"any": ["kruskal"], "priority": 210},
    "prim": {"any": ["prim"], "not": ["prime", "primitive", "primary"], "priority": 200},
    "merge_sort": {"any": ["merge sort", "merge_sort"], "priority": 190},
    "quick_sort": {"any": ["quicksort", "quick sort", "quick_sort"], "priority": 180},
    "insertion_sort": {"any": ["insertion sort", "insertion_sort"], "priority": 170},
    "selection_sort": {"any": ["selection sort", "selection_sort"], "priority": 160},
    "bubble_sort": {"any": ["bubble sort", "bubble_sort"], "priority": 150},
    "heap_sort": {"any": ["heapsort", "heap sort", "heap_sort"], "priority": 140},
    "bfs": {"any": ["breadth-first", "breadth first"], "word": ["bfs"], "not": _IS_TREE, "priority": 130},
    "dfs_iter": {"any": ["depth-first", "depth first"], "word": ["dfs"], "not": _IS_TREE, "priority": 120},
    "n_queens": {"any": ["n-queens", "n queens", "nqueens", "eight queens", "queens problem"], "priority": 110},
    "topological_sort": {"any": ["topological sort", "topological ordering", "topological_sort", "topo sort", "kahn"], "priority": 108},
    "induction_proof": {"any": ["induction", "prove that", "proof by induction", "mathematical induction"],
                        "priority": 100},
    "sieve_of_eratosthenes": {"any": ["sieve", "eratosthenes"], "priority": 90},
    "euclid_gcd": {"any": ["euclid", "euclidean", "gcd", "greatest common divisor"], "priority": 80},
    "union_find": {"any": ["union-find", "union find", "disjoint set", "disjoint-set", "union_find"],
                   "priority": 70},
    "coin_change": {"any": ["coin change", "coin_change", "fewest coins", "minimum coins", "making change"],
                    "priority": 60},
    "house_robber": {"any": ["house robber", "house_robber", "rob houses", "max non-adjacent sum",
                             "maximum non adjacent sum", "non-adjacent sum"], "priority": 60},
    "max_subarray": {"any": ["maximum subarray", "max subarray", "max_subarray", "largest contiguous sum",
                             "kadane's algorithm", "kadane algorithm", "maximum subarray sum"], "priority": 60},
    "rod_cutting": {"any": ["rod cutting", "rod_cutting", "cut the rod", "rod cutting problem",
                            "maximize rod revenue"], "priority": 60},
    "edit_distance": {"any": ["edit distance", "edit_distance", "levenshtein distance", "levenshtein",
                              "string edit distance", "minimum edits"], "priority": 60},
    "longest_increasing_subsequence": {"any": ["increasing subsequence", "longest_increasing_subsequence"],
                                       "priority": 50},
    "arithmetic_eval": {"any": ["order of operations", "evaluate expression", "arithmetic expression"],
                        "priority": 40},
    "floyd_warshall": {"any": ["floyd-warshall", "floyd warshall", "floyd_warshall", "all-pairs",
                               "all pairs shortest"], "priority": 30},
    "bellman_ford": {"any": ["bellman-ford", "bellman ford", "bellman_ford", "bellmanford"], "priority": 20},
    "dijkstra": {"any": ["dijkstra", "shortest path", "shortest-path"], "priority": 10},
    # T6 Formula Engine concepts (CP12b) — distinct alias phrases; compound_interest must win over
    # simple_interest when both "compound" and "interest" appear (higher priority + simple's `not` guard).
    # 'turbulent' guard: "Turbulent Kinetic Energy" is a different quantity (fluctuation energy, the k in
    # k-epsilon) with its own adapter — a ½mv² example there would be verified-but-irrelevant. NOTE: this
    # STATIC entry wins over the spec-derived rule (registration uses setdefault), so the guard must live here.
    "kinetic_energy": {"any": ["kinetic energy"], "not": ["turbulent", "turbulence", "tke"], "priority": 96},
    "ohms_law": {"any": ["ohm's law", "ohms law", "ohm law"], "priority": 95},
    "compound_interest": {"any": ["compound interest"], "priority": 94},
    "simple_interest": {"any": ["simple interest"], "not": ["compound"], "priority": 93},
    # T6 Formula Engine routing rules (CP12b) are injected below from families/formula_specs.py.
}

# Now that both MANIFEST and ROUTING_RULES exist, derive the formula-concept entries from their specs, then
# fill schema defaults across ALL entries (static + injected).
_inject_formula_specs()
_fill_defaults()


def _rule_hits(text: str, rule: dict[str, Any]) -> bool:
    stripped = text
    for s in rule.get("strip", []):
        stripped = stripped.replace(s, " ")
    hit = any(a in text for a in rule.get("any", [])) or \
        any(f" {w}" in f" {text}" for w in rule.get("word", []))
    if not hit:
        return False
    if not all(a in stripped for a in rule.get("all", [])):
        return False
    if any(g in text for g in rule.get("not", [])):
        return False
    return True


def match_routing_slug(text: str) -> "Optional[str]":
    """The declarative alias matcher: the highest-priority rule that fires (== the first `if` in the old
    hand-written chain). Returns the adapter slug or None. Pure string logic — no adapter imports."""
    best, best_pri = None, None
    for slug, rule in ROUTING_RULES.items():
        if _rule_hits(text, rule) and (best_pri is None or rule.get("priority", 0) > best_pri):
            best, best_pri = slug, rule.get("priority", 0)
    return best
