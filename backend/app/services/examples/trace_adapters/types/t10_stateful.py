"""T10 — Stateful invariant maintenance. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.structures import UnionFindAdapter

UNION_FIND = declare(UnionFindAdapter, "union_find", "T10")

DECLARATIONS = [UNION_FIND]
