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

__all__ = ["ADAPTERS", "DECLARATIONS"]
