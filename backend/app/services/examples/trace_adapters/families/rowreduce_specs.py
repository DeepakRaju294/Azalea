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
)

GAUSSIAN_ELIMINATION = RowReduceSpec(
    slug="gaussian_elimination",
    title="Gaussian elimination on a 3×3 system",
    problem_template="Use Gaussian elimination (to reduced row-echelon form) to solve: {system}.",
    n=3,
    setup=_make_system,
    aliases=["gaussian elimination", "gauss jordan", "gauss-jordan", "row reduction", "reduced row echelon",
             "rref", "row echelon form", "elimination method 3x3"],
    not_aliases=["differential", "inequality"],
    priority=55,
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
)


ALL_SPECS = [SOLVE_2X2, GAUSSIAN_ELIMINATION, SOLVE_3X3]
