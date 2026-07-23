"""T15 — Matrix row-operation elimination. Adapter declarations from the row-reduce engine.

Each `RowReduceSpec` (families/rowreduce_specs.py) becomes an adapter; its family + routing come from the spec,
so adding a linear-system concept is a one-file edit. Mirrors the T6/T7/T8a/T8b/T10 declarative type files.

Also includes `MatrixInverseSpec` declarations — a second T15 concept shape (same row-operation grammar, but
the represented object is [A|I]->[I|A^-1] rather than a solution vector), so it has its own decl-builder."""
from ..families.rowreduce_engine import (
    matrix_inverse_decl, registered_inverse_specs, registered_specs, rowreduce_decl,
)

_ROWREDUCE_DECLS = [rowreduce_decl(s) for s in registered_specs()]
_MATRIX_INVERSE_DECLS = [matrix_inverse_decl(s) for s in registered_inverse_specs()]

DECLARATIONS = [*_ROWREDUCE_DECLS, *_MATRIX_INVERSE_DECLS]
