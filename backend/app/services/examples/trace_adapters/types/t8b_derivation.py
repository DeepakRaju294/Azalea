"""T8B — Formal derivation. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.proof import InductionProofAdapter

INDUCTION_PROOF = declare(InductionProofAdapter, "induction_proof", "T8b")

DECLARATIONS = [INDUCTION_PROOF]
