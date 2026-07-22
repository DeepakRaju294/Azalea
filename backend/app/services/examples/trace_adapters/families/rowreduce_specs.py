"""T15 row-reduction CONCEPT SPECS — solving a linear system by Gauss-Jordan elimination on the row-reduce engine.

Each is DATA: a solvable integer system generator + naming/routing. The elimination + oracle are generic, so
adding a linear-system concept is a one-file edit (append a `RowReduceSpec` to `ALL_SPECS`)."""
from __future__ import annotations

import random

from .rowreduce_engine import RowReduceSpec, _rref_ops


def _no_zero_pivot(A: list[list[int]], b: list[int]) -> bool:
    """True iff Gauss-Jordan on (A, b) never hits a zero diagonal pivot (so v1 needs no row swaps)."""
    try:
        for _op, snap, _f, prow, _t in _rref_ops(A, b):
            if prow is not None and snap[prow][prow] == 0:
                return False
    except Exception:  # noqa: BLE001
        return False
    return True


def _make_system(rng: random.Random, n: int) -> tuple:
    """A solvable n×n integer system with small entries, an integer solution, and no zero pivot (rejection)."""
    for _ in range(400):
        A = [[rng.randint(-3, 3) for _ in range(n)] for _ in range(n)]
        x = [rng.randint(-4, 4) for _ in range(n)]
        b = [sum(A[i][j] * x[j] for j in range(n)) for i in range(n)]
        # need a nonzero leading pivot to start, a unique solution, and no zero pivot mid-elimination
        if A[0][0] == 0:
            continue
        if not _no_zero_pivot(A, b):
            continue
        return A, b, x
    # deterministic fallback (identity-like), always valid
    A = [[1 if i == j else 0 for j in range(n)] for i in range(n)]
    x = [rng.randint(-4, 4) for _ in range(n)]
    b = [x[i] for i in range(n)]
    return A, b, x


# Correct boundary facts shared by the linear-system specs (the LLM's edge card on a live path presented a
# DEPENDENT system, 4x+6y=10 = 2*(2x+3y=5), as a "no solutions" example — that system has infinitely many).
_LINEAR_SYSTEM_EDGE_CASES = [
    "NO solution: elimination produces a row \\(0 = c\\) with \\(c \\neq 0\\) — the equations are inconsistent "
    "(e.g. \\(2x + 3y = 5\\) and \\(4x + 6y = 11\\): same left side scaled, different constants).",
    "INFINITELY many solutions: elimination produces an all-zero row \\(0 = 0\\) — one equation is a multiple "
    "of another (e.g. \\(2x + 3y = 5\\) and \\(4x + 6y = 10\\) are the SAME line, not a contradiction).",
    "A zero pivot is handled by SWAPPING rows, never by dividing by zero.",
]

SOLVE_2X2 = RowReduceSpec(
    slug="solve_linear_system_2x2",
    title="solving a 2×2 linear system by elimination",
    problem_template="Solve the system by Gauss-Jordan elimination: {system}.",
    n=2,
    setup=_make_system,
    aliases=["solve linear system", "2x2 system", "system of two equations", "two equations two unknowns",
             "solve system of equations", "linear system"],
    not_aliases=["differential", "inequality"],
    priority=55,
    edge_cases=_LINEAR_SYSTEM_EDGE_CASES,
)

GAUSSIAN_ELIMINATION = RowReduceSpec(
    slug="gaussian_elimination",
    title="Gaussian elimination on a 3×3 system",
    problem_template="Use Gaussian elimination (to reduced row-echelon form) to solve: {system}.",
    n=3,
    setup=_make_system,
    aliases=["gaussian elimination", "gauss jordan", "gauss-jordan", "row reduction", "reduced row echelon",
             "rref", "elimination method 3x3",
             # a 'Row Operations' topic is taught BY row-reducing a system — route it to the verified trace
             # (live failure: an LLM-authored RREF worked example shipped with wrong arithmetic).
             "row operations", "elementary row operations", "basic row operations", "row operation"],
    not_aliases=["differential", "inequality"],
    priority=55,
    edge_cases=_LINEAR_SYSTEM_EDGE_CASES,
)

# A 'Row Echelon Form' topic's example must STOP at REF (forward elimination; solution via back-substitution)
# rather than solving to RREF — a live Gaussian path's REF topic over-shot its own subject with a full solve.
# not_aliases 'reduced' keeps 'reduced row echelon form' routing to the full gaussian_elimination solve.
ROW_ECHELON_FORM = RowReduceSpec(
    slug="row_echelon_form",
    title="reducing a system to row echelon form",
    problem_template="Reduce the system's augmented matrix to ROW ECHELON FORM (forward elimination): {system}.",
    n=3,
    setup=_make_system,
    stop_at="ref",
    aliases=["row echelon form", "row-echelon form", "echelon form", "forming row echelon",
             "forward elimination"],
    not_aliases=["reduced", "rref", "differential", "inequality"],
    priority=60,
    edge_cases=_LINEAR_SYSTEM_EDGE_CASES,
)

SOLVE_3X3 = RowReduceSpec(
    slug="solve_linear_system_3x3",
    title="solving a 3×3 linear system by elimination",
    problem_template="Solve the 3-variable system by row reduction: {system}.",
    n=3,
    setup=_make_system,
    aliases=["3x3 system", "three equations three unknowns", "solve 3 variable system",
             "system of three equations"],
    not_aliases=["differential", "inequality"],
    priority=52,
    edge_cases=_LINEAR_SYSTEM_EDGE_CASES,
)

# ADAPTER_TAXONOMY_SPEC.md §6 T15 backlog: "EE: nodal_analysis, mesh_analysis" — both reduce to exactly this
# engine's shape once KCL/KVL has produced the equations (an unknown-per-node or unknown-per-mesh linear
# system), so they are pure data: same elimination + Cramer oracle, EE variable names/problem framing only.
NODAL_ANALYSIS = RowReduceSpec(
    slug="nodal_analysis",
    title="nodal analysis by Kirchhoff's Current Law",
    problem_template="Apply Kirchhoff's Current Law (KCL) at each node to solve for the unknown node "
                     "voltages: {system}.",
    n=3,
    setup=_make_system,
    var_names=["V1", "V2", "V3"],
    family="electrical_engineering",
    aliases=["nodal analysis", "node voltage analysis", "kirchhoff's current law", "kirchhoffs current law",
             "kcl analysis", "node equations", "solving for node voltages"],
    not_aliases=["differential", "inequality", "mesh"],
    priority=57,
    edge_cases=_LINEAR_SYSTEM_EDGE_CASES,
)

MESH_ANALYSIS = RowReduceSpec(
    slug="mesh_analysis",
    title="mesh analysis by Kirchhoff's Voltage Law",
    problem_template="Apply Kirchhoff's Voltage Law (KVL) around each mesh to solve for the unknown mesh "
                     "currents: {system}.",
    n=3,
    setup=_make_system,
    var_names=["I1", "I2", "I3"],
    family="electrical_engineering",
    aliases=["mesh analysis", "mesh current analysis", "kirchhoff's voltage law", "kirchhoffs voltage law",
             "kvl analysis", "loop analysis", "loop current analysis", "solving for mesh currents"],
    not_aliases=["differential", "inequality", "nodal"],
    priority=57,
    edge_cases=_LINEAR_SYSTEM_EDGE_CASES,
)


ALL_SPECS = [SOLVE_2X2, GAUSSIAN_ELIMINATION, SOLVE_3X3, ROW_ECHELON_FORM, NODAL_ANALYSIS, MESH_ANALYSIS]
