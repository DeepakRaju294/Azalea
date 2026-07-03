"""T11 — Constraint search / backtracking. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.backtracking import NQueensAdapter

N_QUEENS = declare(NQueensAdapter, "n_queens", "T11")

DECLARATIONS = [N_QUEENS]
