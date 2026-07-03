"""T9 — Repeated relaxation / iterative refinement. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.graph import BellmanFordAdapter, FloydWarshallAdapter

BELLMAN_FORD = declare(BellmanFordAdapter, "bellman_ford", "T9a")
FLOYD_WARSHALL = declare(FloydWarshallAdapter, "floyd_warshall", "T9b")

DECLARATIONS = [BELLMAN_FORD, FLOYD_WARSHALL]
