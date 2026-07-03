"""T12 — Program execution / memory trace. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.execution import EuclidGCDAdapter

EUCLID_GCD = declare(EuclidGCDAdapter, "euclid_gcd", "T12")

DECLARATIONS = [EUCLID_GCD]
