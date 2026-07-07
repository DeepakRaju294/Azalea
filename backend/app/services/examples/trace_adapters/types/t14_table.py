"""T14 — Indexed table evaluation. Adapter declarations from the table engine.

Each `TableSpec` (families/table_specs.py) becomes an adapter; its family + routing come from the spec, so adding
a table concept is a one-file edit. Mirrors the other declarative type files."""
from ..families.table_engine import registered_specs, table_decl

_TABLE_DECLS = [table_decl(s) for s in registered_specs()]

DECLARATIONS = [*_TABLE_DECLS]
