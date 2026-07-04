"""T8B — Formal derivation. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.proof import InductionProofAdapter
from ..families.derivation_engine import derivation_decl, registered_specs

INDUCTION_PROOF = declare(InductionProofAdapter, "induction_proof", "T8b")

# CP12d — Derivation Engine concept rows (families/derivation_specs.py). Each DerivationSpec becomes an adapter;
# its family + routing come from the spec, so adding a derivation concept is a one-file edit.
_DERIVATION_DECLS = [derivation_decl(s) for s in registered_specs()]

DECLARATIONS = [INDUCTION_PROOF, *_DERIVATION_DECLS]
