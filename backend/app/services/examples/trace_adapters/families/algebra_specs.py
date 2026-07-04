"""T7 rewrite CONCEPT SPECS (CP12c) — algebra rewrite concepts on the rewrite engine. Each is DATA: how to build
an instance, render its equation, the ordered inverse-operation rules, the answer, and an independent oracle the
gate checks against. Adding a concept = add a `RewriteSpec` and list it in `ALL_SPECS`."""
from __future__ import annotations

import random

from .rewrite_engine import RewriteSpec, RewriteStep


# --- linear equation  a*x + b = c  -> x = (c-b)/a -----------------------------------------------------
def _render_linear(s: dict) -> str:
    coef, const, rhs, var = s["coef"], s["const"], s["rhs"], s.get("var", "x")
    if coef == 0:
        left = f"{const}"
    else:
        cterm = var if coef == 1 else f"{coef}{var}"
        left = cterm if const == 0 else (f"{cterm} + {const}" if const > 0 else f"{cterm} - {abs(const)}")
    return f"{left} = {rhs}"


def _linear_setup(rng: random.Random) -> dict:
    # construct a clean integer solution: pick x and a, a non-zero constant b, then c = a*x + b.
    x = rng.randint(1, 9)
    a = rng.randint(2, 6)
    b = rng.choice([n for n in range(-9, 10) if n != 0])
    # carry the true solution `sol` so every rewritten equation can be checked to still have that solution
    # (the T7 value-preservation invariant): coef*sol + const == rhs holds before and after each rule.
    return {"coef": a, "const": b, "rhs": a * x + b, "var": "x", "sol": x}


def _sub_const(s: dict) -> dict:
    return {**s, "const": 0, "rhs": s["rhs"] - s["const"]}


def _describe_sub(s: dict) -> str:
    b = s["const"]
    return f"subtract {b} from both sides" if b > 0 else f"add {abs(b)} to both sides"


def _div_coef(s: dict) -> dict:
    return {**s, "coef": 1, "rhs": int(round(s["rhs"] / s["coef"]))}


def _describe_div(s: dict) -> str:
    return f"divide both sides by {s['coef']}"


LINEAR_EQUATION = RewriteSpec(
    slug="linear_equation", title="solving a two-step linear equation", family="algebra",
    aliases=["linear equation", "solve for x", "two-step equation", "one variable equation"], priority=95,
    problem_template="Solve the equation {eqn} for {var}.",
    setup=_linear_setup, render=_render_linear,
    steps=[
        RewriteStep("isolate_variable_term", "move the constant to the other side", _sub_const, _describe_sub),
        RewriteStep("solve_for_variable", "divide by the coefficient", _div_coef, _describe_div)],
    answer=lambda s: {s.get("var", "x"): s["rhs"]},
    oracle=lambda s0: {s0.get("var", "x"): int(round((s0["rhs"] - s0["const"]) / s0["coef"]))},
    invariant=lambda s: s["coef"] * s["sol"] + s["const"] == s["rhs"],   # solution preserved by every rule
    preserved="every step keeps the same solution x", goal="the variable is alone on one side")


ALL_SPECS = [LINEAR_EQUATION]
