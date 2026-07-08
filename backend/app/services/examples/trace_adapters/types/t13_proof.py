"""T13 — Proof-obligation discharge. Adapter declarations from the induction engine.

Each `InductionSpec` (families/induction_specs.py) becomes an adapter; its family + routing come from the spec, so
adding an induction concept is a one-file edit. Mirrors the other declarative type files."""
from ..families.induction_engine import induction_decl, registered_specs

_INDUCTION_DECLS = [induction_decl(s) for s in registered_specs()]

DECLARATIONS = [*_INDUCTION_DECLS]
