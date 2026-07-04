"""Algorithm trace adapters (WORKED_EXAMPLE_REASONING_SPEC §15) — the bounded per-algorithm surface.

Adapters are now built from DECLARATIONS (scalable-adapters infra): grouped by TYPE in `types/` (t1..t12),
each declaration carrying identity + type + family + routing + the behavior (either a type template's methods
or the migrated class's methods). Shared MACHINERY still lives by FAMILY in `families/`. `decl.hydrate` turns
each declaration into a runtime adapter with the exact `FamilyAdapterBase` interface, so routing, the
pipeline, and every contract test consume it unchanged. Routing is data-driven (manifest.ROUTING_RULES).

Adding an adapter = add one declaration to its `types/tN_*.py` file (+ its family machinery if new).
"""
from .decl import hydrate as _hydrate
from .types import (t1_traversal, t2_greedy, t3_divide_conquer, t4_search, t5_dp, t6_formula, t7_rewrite,
                    t8a_incremental, t8b_derivation, t9_relaxation, t10_stateful, t11_backtracking,
                    t12_execution)

# One module per TYPE; each exposes DECLARATIONS. The order here is the registration order.
_TYPE_MODULES = [t1_traversal, t2_greedy, t3_divide_conquer, t4_search, t5_dp, t6_formula, t7_rewrite,
                 t8a_incremental, t8b_derivation, t9_relaxation, t10_stateful, t11_backtracking,
                 t12_execution]

DECLARATIONS = [d for mod in _TYPE_MODULES for d in mod.DECLARATIONS]

# Explicit slug -> adapter registry. Every adapter is a hydrated declaration (no fuzzy matching; routing is
# data-driven in trace_pipeline via manifest.ROUTING_RULES, §17).
ADAPTERS = {d.slug: _hydrate(d) for d in DECLARATIONS}

# Tier 2 — deterministic-first narration (single source of truth). These adapters ship their WALKTHROUGH cards
# straight from the verified trace (no LLM re-authoring): each is verified to pass fidelity + hard-prose on its
# OWN deterministic narration across many seeds (test_deterministic_narration_primary), and its step
# decision/reason/expected_visible_result read as learner-facing prose. The trace is the content; the LLM's
# re-authoring here is pure downside (leaked labels, wrong values, dropped mechanism). Coding topics still use
# the code-anchored LLM path (they need per-line anchors the trace does not carry).
NARRATION_SLUGS = frozenset({
    "bubble_sort", "selection_sort", "insertion_sort", "merge_sort", "quick_sort", "heap_sort",
    "bfs", "dfs_iter", "tree_inorder", "tree_preorder", "tree_postorder", "tree_levelorder",
    "kruskal", "prim", "dijkstra", "bellman_ford", "floyd_warshall", "topological_sort",
    "coin_change", "longest_increasing_subsequence", "n_queens", "union_find",
    "sieve_of_eratosthenes", "euclid_gcd", "bst_search", "binary_search",
    "quadratic", "kinematics", "arithmetic_eval", "induction_proof",
})
# T6 Formula (CP12b) + T7 Rewrite (CP12c) concepts also ship their walkthrough from the trace — fold in every
# registered spec slug so a new concept needs no edit here (source of truth = families/*_specs.py).
from .families.formula_engine import registered_specs as _formula_specs  # noqa: E402
from .families.rewrite_engine import registered_specs as _rewrite_specs  # noqa: E402
NARRATION_SLUGS = NARRATION_SLUGS | frozenset(
    s.slug for s in (*_formula_specs(), *_rewrite_specs()))
for _slug in NARRATION_SLUGS:
    if _slug in ADAPTERS:
        type(ADAPTERS[_slug]).provides_narration = True

# CP10/CP11a — deterministic CODING generation (`coding_narration`) is enabled per-family only AFTER its code
# shape is verified to map cleanly AND its annotation templates give correct, non-robotic output (hand-checked
# + gated). Gate-passing is necessary but NOT sufficient: a spurious region mapping (LIS's pre-allocated dp) or
# a missing template can still ship misaligned/robotic content. So this is an explicit VERIFIED whitelist, grown
# one family at a time; every other narration adapter keeps the LLM coding path. (Walkthroughs use the full
# NARRATION_SLUGS set — only the coding walkthrough is gated here.)
DETERMINISTIC_CODING_SLUGS = frozenset({
    "bubble_sort", "selection_sort", "insertion_sort", "merge_sort", "quick_sort",  # arrays (CP10)
    "bfs",                                                                         # graph traversal (CP11a)
    "topological_sort",                                                            # Kahn's in-degree queue (CP11b)
    "tree_levelorder",                                                             # BFS over a binary tree (CP11b)
    "heap_sort",                                                                   # two-phase heapify+extract (CP11c)
})

__all__ = ["ADAPTERS", "DECLARATIONS", "NARRATION_SLUGS", "DETERMINISTIC_CODING_SLUGS"]
