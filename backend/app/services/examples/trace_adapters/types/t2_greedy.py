"""T2 — Greedy frontier update. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.graph import DijkstraAdapter, KruskalAdapter, PrimAdapter

KRUSKAL = declare(KruskalAdapter, "kruskal", "T2")
PRIM = declare(PrimAdapter, "prim", "T2")
DIJKSTRA = declare(DijkstraAdapter, "dijkstra", "T2")

DECLARATIONS = [KRUSKAL, PRIM, DIJKSTRA]
