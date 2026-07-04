"""T10 — Stateful invariant maintenance. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.structures import UnionFindAdapter
from ..families.stateful_engine import registered_specs, stateful_decl

UNION_FIND = declare(UnionFindAdapter, "union_find", "T10")

# CP12e — Stateful Engine concept rows (families/stateful_specs.py). Each StatefulSpec becomes an adapter; its
# family + routing come from the spec, so adding a stateful concept is a one-file edit.
_STATEFUL_DECLS = [stateful_decl(s) for s in registered_specs()]

DECLARATIONS = [UNION_FIND, *_STATEFUL_DECLS]
