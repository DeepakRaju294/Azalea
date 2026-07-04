"""T6 — Formula application. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.algebra import QuadraticEquationAdapter
from ..families.physics import KinematicsAdapter
from ..families.formula_engine import formula_decl
from ..families import formula_specs as _fs
from ..manifest import MANIFEST, ROUTING_RULES

QUADRATIC = declare(QuadraticEquationAdapter, "quadratic", "T6")
KINEMATICS = declare(KinematicsAdapter, "kinematics", "T6")

# CP12b — Formula Engine concept rows. Each FormulaSpec becomes an adapter via formula_decl, pulling its family
# from the manifest + its routing from ROUTING_RULES (single source of truth). The hand-coded KINEMATICS above
# keeps its slot; the engine's own kinematics spec stays gate-only (test_formula_engine) to avoid a duplicate.
_FORMULA_SPECS = [_fs.KINETIC_ENERGY, _fs.OHMS_LAW, _fs.SIMPLE_INTEREST, _fs.COMPOUND_INTEREST,
                  _fs.MOLARITY, _fs.DENSITY, _fs.DESCRIPTIVE_STATS, _fs.MEDIAN_RANGE]
_FORMULA_DECLS = [formula_decl(s, routing={**ROUTING_RULES.get(s.slug, {}),
                                           "family": MANIFEST[s.slug]["family"]}) for s in _FORMULA_SPECS]

DECLARATIONS = [QUADRATIC, KINEMATICS, *_FORMULA_DECLS]
