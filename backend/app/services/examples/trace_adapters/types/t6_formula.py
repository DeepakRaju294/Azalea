"""T6 — Formula application. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.algebra import QuadraticEquationAdapter
from ..families.physics import KinematicsAdapter
from ..families.formula_engine import formula_decl, registered_specs

QUADRATIC = declare(QuadraticEquationAdapter, "quadratic", "T6")
KINEMATICS = declare(KinematicsAdapter, "kinematics", "T6")

# CP12b — Formula Engine concept rows. Every registered FormulaSpec (families/formula_specs.py) becomes an
# adapter via formula_decl; its family + routing come from the spec itself (formula_decl -> routing_rule), so
# adding a concept is a one-file edit. The hand-coded KINEMATICS above keeps its slot; the engine's own
# kinematics spec is register=False (gate-only) to avoid a duplicate.
_FORMULA_DECLS = [formula_decl(s) for s in registered_specs()]

DECLARATIONS = [QUADRATIC, KINEMATICS, *_FORMULA_DECLS]
