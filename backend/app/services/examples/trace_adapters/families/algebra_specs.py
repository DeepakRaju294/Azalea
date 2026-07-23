"""T7 rewrite CONCEPT SPECS (CP12c) — algebra rewrite concepts on the rewrite engine. Each is DATA: how to build
an instance, render its equation, the ordered inverse-operation rules, the answer, and an independent oracle the
gate checks against. Adding a concept = add a `RewriteSpec` and list it in `ALL_SPECS`."""
from __future__ import annotations

import random
from math import gcd

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
    aliases=["linear equation", "solve for x", "two-step equation", "one variable equation"],
    not_aliases=["one-step", "one step", "both sides"], priority=95,
    problem_template="Solve the equation {eqn} for {var}.",
    setup=_linear_setup, render=_render_linear,
    steps=[
        RewriteStep("isolate_variable_term", "move the constant to the other side", _sub_const, _describe_sub),
        RewriteStep("solve_for_variable", "divide by the coefficient", _div_coef, _describe_div)],
    answer=lambda s: {s.get("var", "x"): s["rhs"]},
    oracle=lambda s0: {s0.get("var", "x"): int(round((s0["rhs"] - s0["const"]) / s0["coef"]))},
    invariant=lambda s: s["coef"] * s["sol"] + s["const"] == s["rhs"],   # solution preserved by every rule
    preserved="every step keeps the same solution x", goal="the variable is alone on one side")


# --- linear equation with the variable on BOTH sides:  cl*x + kl = cr*x + kr -------------------------
def _term(coef: int, var: str) -> str:
    if coef == 1:
        return var
    if coef == -1:
        return f"-{var}"
    return f"{coef}{var}"


def _side(coef: int, const: int, var: str) -> str:
    parts = []
    if coef != 0:
        parts.append(_term(coef, var))
    if const != 0 or not parts:
        if not parts:
            parts.append(str(const))
        else:
            parts.append(f"+ {const}" if const > 0 else f"- {abs(const)}")
    return " ".join(parts)


def _render_both(s: dict) -> str:
    v = s.get("var", "x")
    return f"{_side(s['cl'], s['kl'], v)} = {_side(s['cr'], s['kr'], v)}"


def _both_setup(rng: random.Random) -> dict:
    x = rng.randint(1, 9)
    cl = rng.randint(3, 7)
    cr = rng.randint(1, cl - 1)                      # cr < cl so the x-coefficient stays positive
    kl = rng.choice([n for n in range(-8, 9) if n != 0])
    kr = (cl - cr) * x + kl
    return {"cl": cl, "kl": kl, "cr": cr, "kr": kr, "var": "x", "sol": x}


EQUATION_BOTH_SIDES = RewriteSpec(
    slug="equation_both_sides", title="solving an equation with the variable on both sides", family="algebra",
    aliases=["variable on both sides", "variables on both sides", "equation with x on both"], priority=94,
    problem_template="Solve the equation {eqn} for {var}.",
    setup=_both_setup, render=_render_both,
    steps=[
        RewriteStep("collect_variable", "gather the variable on one side",
                    lambda s: {**s, "cl": s["cl"] - s["cr"], "cr": 0},
                    lambda s: f"subtract {_term(s['cr'], s.get('var', 'x'))} from both sides"),
        RewriteStep("isolate_variable_term", "move the constant across",
                    lambda s: {**s, "kl": 0, "kr": s["kr"] - s["kl"]},
                    lambda s: (f"subtract {s['kl']} from both sides" if s["kl"] > 0
                               else f"add {abs(s['kl'])} to both sides")),
        RewriteStep("solve_for_variable", "divide by the coefficient",
                    lambda s: {**s, "cl": 1, "kr": int(round(s["kr"] / s["cl"]))},
                    lambda s: f"divide both sides by {s['cl']}")],
    answer=lambda s: {s.get("var", "x"): s["kr"]},
    oracle=lambda s0: {s0.get("var", "x"): int(round((s0["kr"] - s0["kl"]) / (s0["cl"] - s0["cr"])))},
    invariant=lambda s: s["cl"] * s["sol"] + s["kl"] == s["cr"] * s["sol"] + s["kr"],
    preserved="every step keeps the same solution x", goal="the variable is alone on one side")


# --- simplification: combine like terms   c1*x + k1 + c2*x + k2  ->  (c1+c2)x + (k1+k2) ----------------
def _poly_render(terms: list, var: str) -> str:
    parts = []
    for i, (c, e) in enumerate(terms):
        t = (var if c == 1 else f"{c}{var}") if e == 1 else str(c)
        parts.append(t if i == 0 else f"+ {t}")
    return " ".join(parts)


def _poly_eval(terms: list, x: int) -> int:
    return sum(c * (x ** e) for c, e in terms)


def _combine_setup(rng: random.Random) -> dict:
    c1, c2 = rng.randint(1, 6), rng.randint(1, 6)
    k1, k2 = rng.randint(1, 9), rng.randint(1, 9)
    terms = [[c1, 1], [k1, 0], [c2, 1], [k2, 0]]
    return {"terms": terms, "var": "x", "check": _poly_eval(terms, 2)}


COMBINE_LIKE_TERMS = RewriteSpec(
    slug="combine_like_terms", title="combining like terms", family="algebra", task="simplify",
    aliases=["combine like terms", "like terms", "simplify the expression"], priority=93,
    problem_template="Simplify {eqn}.",
    setup=_combine_setup, render=lambda s: _poly_render(s["terms"], s.get("var", "x")),
    steps=[
        RewriteStep("combine_like_terms", "add the coefficients of like terms",
                    lambda s: {**s, "terms": [[sum(c for c, e in s["terms"] if e == 1), 1],
                                              [sum(c for c, e in s["terms"] if e == 0), 0]]},
                    lambda s: "add the x-terms together and add the constants together")],
    answer=lambda s: {"x_coefficient": s["terms"][0][0], "constant": s["terms"][1][0]},
    oracle=lambda s0: {"x_coefficient": sum(c for c, e in s0["terms"] if e == 1),
                       "constant": sum(c for c, e in s0["terms"] if e == 0)},
    invariant=lambda s: _poly_eval(s["terms"], 2) == s["check"],
    preserved="the expression has the same value for every x", goal="like terms are combined")


# --- simplification: distribute   a(b*x + c)  ->  a*b*x + a*c ------------------------------------------
def _distribute_setup(rng: random.Random) -> dict:
    a, b, c = rng.randint(2, 6), rng.randint(2, 6), rng.randint(1, 9)
    return {"a": a, "b": b, "c": c, "done": False, "var": "x", "check": a * (b * 2 + c)}


DISTRIBUTE = RewriteSpec(
    slug="distribute", title="distributing over a sum", family="algebra", task="simplify",
    aliases=["distribute", "distributing", "distributive property", "expand the expression"], priority=92,
    problem_template="Simplify {eqn}.",
    setup=_distribute_setup,
    render=lambda s: (f"{s['a'] * s['b']}{s.get('var', 'x')} + {s['a'] * s['c']}" if s["done"]
                      else f"{s['a']}({s['b']}{s.get('var', 'x')} + {s['c']})"),
    steps=[
        RewriteStep("distribute", "multiply each inside term by the factor",
                    lambda s: {**s, "done": True},
                    lambda s: f"multiply each term inside by {s['a']}")],
    answer=lambda s: {"x_coefficient": s["a"] * s["b"], "constant": s["a"] * s["c"]},
    oracle=lambda s0: {"x_coefficient": s0["a"] * s0["b"], "constant": s0["a"] * s0["c"]},
    invariant=lambda s: (s["a"] * s["b"] * 2 + s["a"] * s["c"] if s["done"] else s["a"] * (s["b"] * 2 + s["c"]))
    == s["check"],
    preserved="the expression has the same value for every x", goal="the product is expanded")


# --- one-step equation:  x + b = c  ->  x = c - b -----------------------------------------------------
def _one_step_setup(rng: random.Random) -> dict:
    x = rng.randint(1, 15)
    b = rng.choice([n for n in range(-9, 10) if n != 0])
    return {"coef": 1, "const": b, "rhs": x + b, "var": "x", "sol": x}


ONE_STEP_EQUATION = RewriteSpec(
    slug="one_step_equation", title="solving a one-step linear equation", family="algebra",
    aliases=["one-step equation", "one step equation"], priority=91,
    problem_template="Solve the equation {eqn} for {var}.",
    setup=_one_step_setup, render=_render_linear,
    steps=[RewriteStep("solve_for_variable", "undo the constant", _sub_const, _describe_sub)],
    answer=lambda s: {s.get("var", "x"): s["rhs"]},
    oracle=lambda s0: {s0.get("var", "x"): s0["rhs"] - s0["const"]},
    invariant=lambda s: s["coef"] * s["sol"] + s["const"] == s["rhs"],
    preserved="every step keeps the same solution x", goal="the variable is alone on one side")


# --- proportion:  a/b = x/c  ->  cross-multiply  ->  x = a*c/b ---------------------------------------
def _prop_setup(rng: random.Random) -> dict:
    b = rng.randint(2, 5)
    k = rng.randint(2, 6)
    c = rng.randint(2, 6)
    a = b * k                                            # a/b = k is exact; x = a*c/b = k*c is an integer
    return {"a": a, "b": b, "c": c, "sol": k * c, "phase": 0, "var": "x"}


def _prop_render(s: dict) -> str:
    a, b, c, p = s["a"], s["b"], s["c"], s["phase"]
    if p == 0:
        return f"{a}/{b} = x/{c}"
    if p == 1:
        return f"{a} * {c} = {b} * x"
    return f"x = {a * c // b}"


SOLVE_PROPORTION = RewriteSpec(
    slug="solve_proportion", title="solving a proportion by cross-multiplication", family="algebra",
    aliases=["proportion", "cross-multiply", "cross multiplication", "solve the proportion"], priority=90,
    problem_template="Solve the proportion {eqn} for {var}.",
    setup=_prop_setup, render=_prop_render,
    steps=[
        RewriteStep("cross_multiply", "cross-multiply", lambda s: {**s, "phase": 1},
                    lambda s: f"cross-multiply: {s['a']} x {s['c']} = {s['b']} x x"),
        RewriteStep("solve_for_variable", "divide to isolate the variable", lambda s: {**s, "phase": 2},
                    lambda s: f"compute {s['a']} x {s['c']} = {s['a'] * s['c']} and divide by {s['b']}: "
                              f"{s['a'] * s['c']} / {s['b']} = {s['a'] * s['c'] // s['b']}")],
    answer=lambda s: {s.get("var", "x"): s["a"] * s["c"] // s["b"]},
    oracle=lambda s0: {s0.get("var", "x"): s0["a"] * s0["c"] // s0["b"]},
    invariant=lambda s: s["a"] * s["c"] == s["b"] * s["sol"],
    preserved="every step keeps the same solution x", goal="the variable is isolated")


# --- multiplication equation:  a*x = c  ->  x = c/a --------------------------------------------------
def _mult_setup(rng: random.Random) -> dict:
    x = rng.randint(2, 12)
    a = rng.randint(2, 9)
    return {"coef": a, "const": 0, "rhs": a * x, "var": "x", "sol": x}


MULTIPLICATION_EQUATION = RewriteSpec(
    slug="multiplication_equation", title="solving a multiplication equation", family="algebra",
    aliases=["multiplication equation", "one-step multiplication"], priority=89,
    problem_template="Solve the equation {eqn} for {var}.",
    setup=_mult_setup, render=_render_linear,
    steps=[RewriteStep("solve_for_variable", "divide by the coefficient", _div_coef, _describe_div)],
    answer=lambda s: {s.get("var", "x"): s["rhs"]},
    oracle=lambda s0: {s0.get("var", "x"): int(round(s0["rhs"] / s0["coef"]))},
    invariant=lambda s: s["coef"] * s["sol"] + s["const"] == s["rhs"],
    preserved="every step keeps the same solution x", goal="the variable is alone on one side")


# --- simplify a fraction to lowest terms:  a/b  ->  (a/g)/(b/g) ---------------------------------------
def _frac_setup(rng: random.Random) -> dict:
    g = rng.randint(2, 6)
    while True:
        p, q = rng.randint(1, 8), rng.randint(2, 9)
        if gcd(p, q) == 1 and p != q:
            return {"a": g * p, "b": g * q, "g": g, "p": p, "q": q, "phase": 0}


SIMPLIFY_FRACTION = RewriteSpec(
    slug="simplify_fraction", title="simplifying a fraction to lowest terms", family="algebra", task="simplify",
    aliases=["simplify a fraction", "reduce a fraction", "lowest terms"], priority=88,
    problem_template="Simplify {eqn} to lowest terms.",
    setup=_frac_setup, render=lambda s: f"{s['a']}/{s['b']}" if s["phase"] == 0 else f"{s['p']}/{s['q']}",
    steps=[RewriteStep("reduce", "divide by the GCF", lambda s: {**s, "phase": 1},
                       lambda s: f"the GCF of {s['a']} and {s['b']} is {s['g']}; divide both by {s['g']}: "
                                 f"{s['a']}/{s['g']} = {s['p']}, {s['b']}/{s['g']} = {s['q']}")],
    answer=lambda s: {"numerator": s["p"], "denominator": s["q"]},
    oracle=lambda s0: {"numerator": s0["p"], "denominator": s0["q"]},
    invariant=lambda s: s["a"] * s["q"] == s["b"] * s["p"],
    preserved="the fraction keeps the same value", goal="the fraction is in lowest terms")


# --- factor a monic quadratic:  x^2 + bx + c  ->  (x - r1)(x - r2), given integer roots r1, r2 -----------
def _factor_term(r: int) -> str:
    return f"(x - {r})" if r >= 0 else f"(x + {-r})"


def _quad_render(s: dict) -> str:
    b, c, var = s["b"], s["c"], s.get("var", "x")
    if s["phase"] == 1:
        return f"{_factor_term(s['r1'])}{_factor_term(s['r2'])}"
    left = f"{var}^2"
    if b != 0:
        left += f" + {b}{var}" if b > 0 else f" - {abs(b)}{var}"
    if c != 0:
        left += f" + {c}" if c > 0 else f" - {abs(c)}"
    return left


def _quad_setup(rng: random.Random) -> dict:
    # distinct integer roots so the factored form is never a repeated-root degenerate case
    r1 = rng.randint(-9, 9)
    r2 = rng.choice([r for r in range(-9, 10) if r != r1])
    b, c = -(r1 + r2), r1 * r2
    return {"r1": r1, "r2": r2, "b": b, "c": c, "phase": 0, "var": "x", "check": 5 * 5 + b * 5 + c}


FACTOR_QUADRATIC = RewriteSpec(
    slug="factor_quadratic", title="factoring a monic quadratic", family="algebra", task="simplify",
    aliases=["factor the quadratic", "factoring a quadratic", "factor quadratics",
             "factor a quadratic expression"],
    not_aliases=["completing the square", "quadratic formula"], priority=91,
    problem_template="Factor {eqn}.",
    setup=_quad_setup, render=_quad_render,
    steps=[RewriteStep(
        "factor", "find two numbers that multiply to c and add to b", lambda s: {**s, "phase": 1},
        lambda s: f"look for two integers that multiply to {s['c']} and add to {s['b']}: "
                  f"{s['r1']} and {s['r2']} work")],
    # Reports the literal PRETTY-PRINTED factor strings (e.g. "(x + 8)"), not bare signed roots — the roots
    # themselves don't always appear literally in the sign-flipped display ("(x + 8)" never contains "-8"),
    # and the double-negative literal form "(x - -8)" is confusing for a first-time learner despite being
    # mathematically valid, so it is intentionally NOT used just to satisfy the entailment check. Sorted by
    # root value (smaller first) so `answer` and the independently-recomputed `oracle` below use the SAME
    # canonical order regardless of which order r1/r2 happened to be generated in.
    answer=lambda s: dict(zip(("factor_1", "factor_2"),
                              (_factor_term(r) for r in sorted((s["r1"], s["r2"]))))),
    # independent of `answer`: recomputed via the quadratic formula (a different method than factoring by
    # inspection), not by re-reading the stored r1/r2 fields.
    oracle=lambda s0: dict(zip(("factor_1", "factor_2"), (_factor_term(round(rt)) for rt in sorted((
        (-s0["b"] - (s0["b"] ** 2 - 4 * s0["c"]) ** 0.5) / 2,
        (-s0["b"] + (s0["b"] ** 2 - 4 * s0["c"]) ** 0.5) / 2))))),
    invariant=lambda s: (25 + s["b"] * 5 + s["c"] if s["phase"] == 0
                         else (5 - s["r1"]) * (5 - s["r2"])) == s["check"],
    preserved="the expression has the same value for every x", goal="the expression is written as a product")


# --- linear inequality:  a*x + b > c  ->  x > (c-b)/a, with a always positive (no sign flip in v1) --------
def _ineq_render(s: dict) -> str:
    a, b, c, var, op = s["a"], s["b"], s["c"], s.get("var", "x"), s["op"]
    if s["phase"] == 1:
        return f"{var} {op} {s['sol_display']}"
    left = f"{a}{var}" if a != 1 else var
    if b != 0:
        left += f" + {b}" if b > 0 else f" - {abs(b)}"
    return f"{left} {op} {c}"


def _ineq_setup(rng: random.Random) -> dict:
    a = rng.randint(2, 8)
    b = rng.choice([n for n in range(-9, 10) if n != 0])
    sol = rng.randint(-6, 12)
    op = rng.choice([">", "<", ">=", "<="])
    c = a * sol + b
    return {"a": a, "b": b, "c": c, "op": op, "phase": 0, "var": "x", "sol": sol,
            "sol_display": str(sol)}


INEQUALITY_SOLVING = RewriteSpec(
    slug="linear_inequality", title="solving a linear inequality", family="algebra",
    aliases=["linear inequality", "solving an inequality", "inequality solving", "solve the inequality"],
    priority=53,
    problem_template="Solve the inequality {eqn} for {var}.",
    setup=_ineq_setup, render=_ineq_render,
    steps=[
        RewriteStep("isolate_variable_term", "move the constant to the other side",
                    lambda s: {**s, "b": 0, "c": s["c"] - s["b"]},
                    lambda s: f"subtract {s['b']} from both sides" if s["b"] > 0
                              else f"add {abs(s['b'])} to both sides"),
        RewriteStep("solve_for_variable", "divide by the (positive) coefficient",
                    lambda s: {**s, "a": 1, "phase": 1, "sol_display": str(s["sol"])},
                    lambda s: f"divide both sides by {s['a']} (positive, so the inequality direction does "
                              f"NOT flip)")],
    answer=lambda s: {"solution": f"{s.get('var', 'x')} {s['op']} {s['sol']}"},
    # independent of `answer`: recomputed from the INITIAL a/b/c via real division, not the stored `sol` field
    oracle=lambda s0: {"solution": f"{s0.get('var', 'x')} {s0['op']} "
                                   f"{int(round((s0['c'] - s0['b']) / s0['a']))}"},
    invariant=lambda s: True,
    preserved="the solution set is preserved (dividing by a POSITIVE number never flips the inequality)",
    goal="the variable is alone on one side")


# --- logarithmic equation:  log_base(x) = exponent  ->  x = base^exponent --------------------------------
def _log_render(s: dict) -> str:
    if s["phase"] == 1:
        return f"x = {s['base']}^{s['exponent']} = {s['base'] ** s['exponent']}"
    return f"log_{s['base']}(x) = {s['exponent']}"


def _log_setup(rng: random.Random) -> dict:
    base = rng.randint(2, 5)
    exponent = rng.randint(1, 4)
    return {"base": base, "exponent": exponent, "phase": 0, "var": "x", "sol": base ** exponent}


LOG_EQUATION = RewriteSpec(
    slug="log_equation", title="solving a logarithmic equation", family="algebra",
    aliases=["logarithmic equation", "log equation", "solve a log equation", "solving logarithms"],
    priority=53,
    problem_template="Solve the equation {eqn} for {var}.",
    setup=_log_setup, render=_log_render,
    steps=[RewriteStep(
        "exponentiate", "rewrite the log equation in exponential form",
        lambda s: {**s, "phase": 1},
        lambda s: f"log_{s['base']}(x) = {s['exponent']} means x = {s['base']}^{s['exponent']}")],
    answer=lambda s: {s.get("var", "x"): s["sol"]},
    oracle=lambda s0: {s0.get("var", "x"): s0["base"] ** s0["exponent"]},
    invariant=lambda s: True,
    preserved="the logarithmic and exponential forms name the same solution",
    goal="x is isolated in exponential form")


ALL_SPECS = [LINEAR_EQUATION, EQUATION_BOTH_SIDES, COMBINE_LIKE_TERMS, DISTRIBUTE, ONE_STEP_EQUATION,
             SOLVE_PROPORTION, MULTIPLICATION_EQUATION, SIMPLIFY_FRACTION, FACTOR_QUADRATIC,
             INEQUALITY_SOLVING, LOG_EQUATION]
