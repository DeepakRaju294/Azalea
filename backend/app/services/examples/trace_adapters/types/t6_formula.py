"""T6 — Formula application. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.algebra import QuadraticEquationAdapter
from ..families.physics import KinematicsAdapter

QUADRATIC = declare(QuadraticEquationAdapter, "quadratic", "T6")
KINEMATICS = declare(KinematicsAdapter, "kinematics", "T6")

DECLARATIONS = [QUADRATIC, KINEMATICS]
