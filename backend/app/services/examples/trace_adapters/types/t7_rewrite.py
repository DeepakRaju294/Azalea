"""T7 — Reduction / rewriting. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.formula import ArithmeticEvalAdapter
from ..families.rewrite_engine import registered_specs, rewrite_decl

ARITHMETIC_EVAL = declare(ArithmeticEvalAdapter, "arithmetic_eval", "T7")

# CP12c — Rewrite Engine concept rows (families/algebra_specs.py). Each RewriteSpec becomes an adapter; its
# family + routing come from the spec, so adding a rewrite concept is a one-file edit.
_REWRITE_DECLS = [rewrite_decl(s) for s in registered_specs()]

DECLARATIONS = [ARITHMETIC_EVAL, *_REWRITE_DECLS]
