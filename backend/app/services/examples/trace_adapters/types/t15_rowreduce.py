"""T15 — Matrix row-operation elimination. Adapter declarations from the row-reduce engine.

Each `RowReduceSpec` (families/rowreduce_specs.py) becomes an adapter; its family + routing come from the spec,
so adding a linear-system concept is a one-file edit. Mirrors the T6/T7/T8a/T8b/T10 declarative type files."""
from ..families.rowreduce_engine import registered_specs, rowreduce_decl

_ROWREDUCE_DECLS = [rowreduce_decl(s) for s in registered_specs()]

DECLARATIONS = [*_ROWREDUCE_DECLS]
