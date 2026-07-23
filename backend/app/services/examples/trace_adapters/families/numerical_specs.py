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


# ── Forward Euler for Newton's law of cooling: T' = -k(T - Tenv) → steady state Tenv ─────────────────────────
# a genuine TIME-STEPPING ODE method (not root-finding): with k*h = 0.5 the temperature relaxes to room temp.
NEWTON_COOLING_EULER = NumericalSpec(
    slug="euler_newton_cooling",
    title="Euler's method for Newton's law of cooling",
    problem_template="A body at T0 = {T0} degrees cools toward room temperature Tenv = {Tenv}. "
                     "Use Euler's method (T' = -k(T - Tenv), k*h = 0.5) to step it forward.",
    setup=lambda rng: {"T0": rng.randint(60, 100), "Tenv": rng.randint(15, 30)},
    initial=lambda p: float(p["T0"]),
    update=lambda p, T: (T - 0.5 * (T - p["Tenv"]), f"T <- T - 0.5*(T - {p['Tenv']})"),
    residual=lambda p, T: abs(T - p["Tenv"]),        # distance to the steady state
    true_value=lambda p: float(p["Tenv"]),           # the ODE's steady state (fixed point)
    tol=1e-2, answer_tol=1e-2, max_iters=30,
    estimate_name="steady_temperature",
    aliases=["euler's method cooling", "newton's law of cooling", "euler method ode",
             "forward euler cooling", "numerical cooling"],
    not_aliases=["square", "cube", "reciprocal"],
    priority=54,
)


# ADAPTER_TAXONOMY_SPEC.md §6 T16 backlog. Note: bisection_root/secant_method/rk4/iterative_linear_solver all
# need MORE than one scalar of iteration state (bisection/secant need a bracket or the previous TWO iterates; a
# linear solver needs a whole vector) — the engine's `update(params, x) -> x_next` signature assumes `params` is
# STATIC and `update` is a pure, replayable function of (params, x); the gate re-calls `update` independently to
# verify each iterate, so a version that carried extra state via mutating `params` was caught and rejected (see
# below). Real engine work, not a data edit. numerical_integration (trapezoid/simpson) is a one-shot sum, not an
# iterate-to-convergence process, so it does not fit this engine's grammar at all regardless of state. The item
# below stays within the proven single-scalar, pure-update shape.

# ── Newton-Raphson on a GENERAL (non-closed-form) polynomial: x^3 - x - 1 = 0, root ~= 1.324718 ────────────────
# distinct from NEWTON_SQRT/CBRT/RECIPROCAL, which are Newton's method SPECIALIZED to a target with a known
# closed form (sqrt/cbrt/1/a) — this is the general algorithm x_{n+1} = x_n - f(x_n)/f'(x_n) on a function with
# no simple inverse, the textbook motivating example for why Newton's method is needed at all.
def _newton_general_update(p: dict, x: float) -> tuple:
    fx = x ** 3 - x - 1
    fpx = 3 * x * x - 1
    return x - fx / fpx, f"x <- x - (x^3 - x - 1)/(3x^2 - 1), evaluated at x={x}"


NEWTON_RAPHSON_GENERAL = NumericalSpec(
    slug="newton_raphson_cubic",
    title="Newton-Raphson for a root of x^3 - x - 1 = 0",
    problem_template="Use the Newton-Raphson method to approximate a root of f(x) = x^3 - x - 1, "
                     "starting from x0 = {x0}.",
    setup=lambda rng: {"x0": float(rng.randint(1, 5))},
    initial=lambda p: p["x0"],
    update=_newton_general_update,
    residual=lambda p, x: abs(x ** 3 - x - 1),
    true_value=lambda p: 1.3247179572447458,
    estimate_name="root",
    aliases=["newton raphson method", "newton-raphson method", "newton raphson root finding",
             "general newton's method", "newton's method for a polynomial root", "find root of x^3 - x - 1"],
    not_aliases=["square root", "cube root", "reciprocal", "cooling", "fixed point"],
    priority=53,
)

# Bisection method attempted and DELIBERATELY NOT shipped: it needs the current bracket [lo, hi] as state beyond
# the single scalar x, and the engine's own gate re-calls `spec.update(params, x_prev)` independently to verify
# each iterate — which requires `update` to be a PURE function of (params, x), replayable at any point. A version
# that tracked the bracket by mutating `params` in place broke exactly that gate (verified: caught by
# test_each_iterate_equals_update_of_previous/test_residual_is_non_increasing, not silently wrong) — same
# engine-shape mismatch as secant_method/rk4/iterative_linear_solver, just less obvious until attempted.

ALL_SPECS = [NEWTON_SQRT, NEWTON_CBRT, FIXED_POINT_LINEAR, NEWTON_RECIPROCAL, NEWTON_COOLING_EULER,
             NEWTON_RAPHSON_GENERAL]
