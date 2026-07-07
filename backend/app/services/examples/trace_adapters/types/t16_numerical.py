"""T16 — Numerical time-step convergence. Adapter declarations from the numerical engine.

Each `NumericalSpec` (families/numerical_specs.py) becomes an adapter; its family + routing come from the spec, so
adding an iterative-method concept is a one-file edit. Mirrors the other declarative type files."""
from ..families.numerical_engine import numerical_decl, registered_specs

_NUMERICAL_DECLS = [numerical_decl(s) for s in registered_specs()]

DECLARATIONS = [*_NUMERICAL_DECLS]
