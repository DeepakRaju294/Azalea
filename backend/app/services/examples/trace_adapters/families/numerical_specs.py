"""T16 numerical-convergence CONCEPT SPECS — iterative methods on the numerical engine. Each is DATA: an initial
guess, an update rule, a residual, and a tolerance. Adding one = append a `NumericalSpec`."""
from __future__ import annotations

import math
import random

from .numerical_engine import NumericalSpec


# ── Newton's method for √a: x_{n+1} = (x_n + a/x_n)/2 ────────────────────────────────────────────────────────
NEWTON_SQRT = NumericalSpec(
    slug="newton_sqrt",
    title="Newton's method for a square root",
    problem_template="Use Newton's method to approximate sqrt({a}).",
    setup=lambda rng: {"a": rng.randint(2, 80)},
    initial=lambda p: float(p["a"]),
    update=lambda p, x: ((x + p["a"] / x) / 2, f"x <- (x + {p['a']}/x)/2"),
    residual=lambda p, x: abs(x * x - p["a"]),
    true_value=lambda p: math.sqrt(p["a"]),
    aliases=["newton's method square root", "newton method sqrt", "newton square root",
             "square root by newton", "newton raphson square root", "approximate square root iteratively"],
    not_aliases=["cube"],
    priority=54,
)

# ── Newton's method for ∛a: x_{n+1} = (2 x_n + a/x_n²)/3 ─────────────────────────────────────────────────────
NEWTON_CBRT = NumericalSpec(
    slug="newton_cbrt",
    title="Newton's method for a cube root",
    problem_template="Use Newton's method to approximate the cube root of {a}.",
    setup=lambda rng: {"a": rng.randint(2, 120)},
    initial=lambda p: float(p["a"]),
    update=lambda p, x: ((2 * x + p["a"] / (x * x)) / 3, f"x <- (2x + {p['a']}/x^2)/3"),
    residual=lambda p, x: abs(x ** 3 - p["a"]),
    true_value=lambda p: p["a"] ** (1.0 / 3.0),
    tol=1e-3,
    aliases=["newton's method cube root", "newton method cbrt", "newton cube root",
             "cube root by newton", "approximate cube root iteratively"],
    priority=54,
)

# ── Linear fixed-point iteration: x_{n+1} = 0.5 x_n + 3  →  fixed point 6 ────────────────────────────────────
FIXED_POINT_LINEAR = NumericalSpec(
    slug="fixed_point_linear",
    title="fixed-point iteration for a linear map",
    problem_template="Find the fixed point of g(x) = 0.5x + {c} by iteration.",
    setup=lambda rng: {"c": 3, "x0": rng.randint(-6, 18)},
    initial=lambda p: float(p["x0"]),
    update=lambda p, x: (0.5 * x + p["c"], f"x <- 0.5x + {p['c']}"),
    residual=lambda p, x: abs((0.5 * x + p["c"]) - x),      # |g(x) - x|
    true_value=lambda p: p["c"] / 0.5,                       # solve x = 0.5x + c  ->  x = 2c
    max_iters=40,
    aliases=["fixed point iteration", "fixed-point iteration", "linear fixed point", "iterate to a fixed point"],
    not_aliases=["newton", "square root", "cube"],
    priority=52,
)


# ── Newton's method for the reciprocal 1/a (division-free): x_{n+1} = x_n(2 - a x_n) ─────────────────────────
# converges to 1/a from any 0 < x0 < 2/a; start at 1/(a+1) < 1/a to stay in the basin.
NEWTON_RECIPROCAL = NumericalSpec(
    slug="newton_reciprocal",
    title="Newton's method for a reciprocal (division-free)",
    problem_template="Use Newton's method to approximate 1/{a} without dividing.",
    setup=lambda rng: {"a": rng.randint(2, 9)},
    initial=lambda p: 1.0 / (p["a"] + 1),
    update=lambda p, x: (x * (2 - p["a"] * x), f"x <- x(2 - {p['a']}x)"),
    residual=lambda p, x: abs(p["a"] * x - 1),
    true_value=lambda p: 1.0 / p["a"],
    aliases=["newton's method reciprocal", "newton reciprocal", "division-free reciprocal",
             "compute reciprocal by newton", "approximate 1/a iteratively"],
    not_aliases=["square", "cube"],
    priority=52,
)


ALL_SPECS = [NEWTON_SQRT, NEWTON_CBRT, FIXED_POINT_LINEAR, NEWTON_RECIPROCAL]
