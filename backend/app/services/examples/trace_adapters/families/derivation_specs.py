"""T8b derivation CONCEPT SPECS (CP12d) — rule-justified algebra-law derivations on the derivation engine. Each
is DATA: build an instance, render its state, the ordered rule-cited steps, the conclusion, the answer, and an
independent oracle. Adding a concept = add a `DerivationSpec` to `ALL_SPECS`."""
from __future__ import annotations

import random

from math import gcd

from .derivation_engine import DerivationSpec, DerivationStep


# --- exponent laws:  x^a · x^b / x^c  =  x^(a+b-c) ---------------------------------------------------
def _exp_setup(rng: random.Random) -> dict:
    a = rng.randint(3, 7)
    b = rng.randint(2, 5)
    c = rng.randint(1, a + b - 2)                     # keep the final exponent >= 1
    return {"base": "x", "a": a, "b": b, "c": c, "phase": 0}


def _exp_render(s: dict) -> str:
    base, a, b, c, p = s["base"], s["a"], s["b"], s["c"], s["phase"]
    if p == 0:
        return f"{base}^{a} · {base}^{b} / {base}^{c}"
    if p == 1:
        return f"{base}^{a + b} / {base}^{c}"
    return f"{base}^{a + b - c}"


EXPONENT_LAWS = DerivationSpec(
    slug="exponent_laws", title="simplifying with the laws of exponents", family="algebra",
    aliases=["laws of exponents", "exponent rules", "exponent laws", "product and quotient rule"], priority=95,
    problem_template="Simplify {start} using the laws of exponents.",
    setup=_exp_setup, render=_exp_render,
    steps=[
        DerivationStep("product_rule", "product rule", lambda s: {**s, "phase": 1},
                       lambda s: f"add the exponents of the like bases: {s['a']} + {s['b']} = {s['a'] + s['b']}"),
        DerivationStep("quotient_rule", "quotient rule", lambda s: {**s, "phase": 2},
                       lambda s: f"subtract the divisor's exponent: {s['a'] + s['b']} - {s['c']} = "
                                 f"{s['a'] + s['b'] - s['c']}")],
    conclusion=lambda s: f"{s['base']}^{s['a'] + s['b'] - s['c']}",
    answer=lambda s: {"exponent": s["a"] + s["b"] - s["c"]},
    oracle=lambda s0: {"exponent": s0["a"] + s0["b"] - s0["c"]},
    invariant=lambda s: (2 ** s["a"] * 2 ** s["b"]) // (2 ** s["c"]) == 2 ** (s["a"] + s["b"] - s["c"]),
    preserved="the expression keeps the same value at every step")


# --- power of a power:  (x^a)^b  =  x^(a*b) ----------------------------------------------------------
def _pow_setup(rng: random.Random) -> dict:
    return {"base": "x", "a": rng.randint(2, 5), "b": rng.randint(2, 4), "phase": 0}


def _pow_render(s: dict) -> str:
    base, a, b, p = s["base"], s["a"], s["b"], s["phase"]
    return f"({base}^{a})^{b}" if p == 0 else f"{base}^{a * b}"


POWER_OF_POWER = DerivationSpec(
    slug="power_of_power", title="power of a power", family="algebra",
    aliases=["power of a power", "power rule for exponents", "raising a power to a power"], priority=94,
    problem_template="Simplify {start}.",
    setup=_pow_setup, render=_pow_render,
    steps=[DerivationStep("power_rule", "power-of-a-power rule", lambda s: {**s, "phase": 1},
                          lambda s: f"multiply the exponents: {s['a']} x {s['b']} = {s['a'] * s['b']}")],
    conclusion=lambda s: f"{s['base']}^{s['a'] * s['b']}",
    answer=lambda s: {"exponent": s["a"] * s["b"]},
    oracle=lambda s0: {"exponent": s0["a"] * s0["b"]},
    invariant=lambda s: (2 ** s["a"]) ** s["b"] == 2 ** (s["a"] * s["b"]),
    preserved="the expression keeps the same value at every step")


# --- logarithm evaluation:  log_b(b^k) = k ----------------------------------------------------------
def _log_setup(rng: random.Random) -> dict:
    b = rng.randint(2, 5)
    k = rng.randint(2, 5)
    return {"base": b, "k": k, "x": b ** k, "phase": 0}


def _log_render(s: dict) -> str:
    b, k, x, p = s["base"], s["k"], s["x"], s["phase"]
    if p == 0:
        return f"log_{b}({x})"
    if p == 1:
        return f"log_{b}({b}^{k})"
    return f"{k}"


LOG_EVALUATION = DerivationSpec(
    slug="log_evaluation", title="evaluating a logarithm with the power law", family="algebra",
    aliases=["evaluate a logarithm", "evaluating a logarithm", "logarithm evaluation", "log base"], priority=93,
    problem_template="Evaluate {start}.",
    setup=_log_setup, render=_log_render,
    steps=[
        DerivationStep("rewrite_argument", "rewrite-as-a-power rule", lambda s: {**s, "phase": 1},
                       lambda s: f"express {s['x']} as a power of {s['base']}: {s['x']} = {s['base']}^{s['k']}"),
        DerivationStep("log_power_law", "logarithm power law", lambda s: {**s, "phase": 2},
                       lambda s: f"log base {s['base']} of {s['base']}^{s['k']} is {s['k']}")],
    conclusion=lambda s: f"{s['k']}",
    answer=lambda s: {"value": s["k"]},
    oracle=lambda s0: {"value": s0["k"]},
    invariant=lambda s: s["x"] == s["base"] ** s["k"],
    preserved="the value of the logarithm is fixed throughout")


# --- logarithm product law:  log_b(x·y) = log_b(x) + log_b(y) = p + q  (x=b^p, y=b^q) ----------------
def _logprod_setup(rng: random.Random) -> dict:
    b = rng.randint(2, 4)
    p = rng.randint(1, 4)
    q = rng.randint(1, 4)
    return {"base": b, "p": p, "q": q, "x": b ** p, "y": b ** q, "phase": 0}


def _logprod_render(s: dict) -> str:
    b, x, y, p, q, ph = s["base"], s["x"], s["y"], s["p"], s["q"], s["phase"]
    if ph == 0:
        return f"log_{b}({x} · {y})"
    if ph == 1:
        return f"log_{b}({x}) + log_{b}({y})"
    return f"{p + q}"


LOG_PRODUCT_LAW = DerivationSpec(
    slug="log_product_law", title="the logarithm product law", family="algebra",
    aliases=["log product", "logarithm product", "log of a product"], priority=86,
    problem_template="Evaluate {start} using the product law.",
    setup=_logprod_setup, render=_logprod_render,
    steps=[
        DerivationStep("product_law", "logarithm product law", lambda s: {**s, "phase": 1},
                       lambda s: f"the log of a product is the sum of the logs"),
        DerivationStep("evaluate_logs", "power law", lambda s: {**s, "phase": 2},
                       lambda s: f"log_{s['base']}({s['x']}) = {s['p']} and log_{s['base']}({s['y']}) = {s['q']}, "
                                 f"so {s['p']} + {s['q']} = {s['p'] + s['q']}")],
    conclusion=lambda s: f"{s['p'] + s['q']}",
    answer=lambda s: {"value": s["p"] + s["q"]},
    oracle=lambda s0: {"value": s0["p"] + s0["q"]},
    invariant=lambda s: s["x"] * s["y"] == s["base"] ** (s["p"] + s["q"]),
    preserved="the value of the logarithm is fixed throughout")


# --- logarithm quotient law:  log_b(x/y) = log_b(x) - log_b(y) = p - q  (x=b^p, y=b^q, p>q) -----------
def _logquot_setup(rng: random.Random) -> dict:
    b = rng.randint(2, 4)
    q = rng.randint(1, 3)
    p = rng.randint(q + 1, q + 4)                     # p > q so the result is positive
    return {"base": b, "p": p, "q": q, "x": b ** p, "y": b ** q, "phase": 0}


def _logquot_render(s: dict) -> str:
    b, x, y, p, q, ph = s["base"], s["x"], s["y"], s["p"], s["q"], s["phase"]
    if ph == 0:
        return f"log_{b}({x} / {y})"
    if ph == 1:
        return f"log_{b}({x}) - log_{b}({y})"
    return f"{p - q}"


LOG_QUOTIENT_LAW = DerivationSpec(
    slug="log_quotient_law", title="the logarithm quotient law", family="algebra",
    aliases=["log quotient", "logarithm quotient", "log of a quotient"], priority=85,
    problem_template="Evaluate {start} using the quotient law.",
    setup=_logquot_setup, render=_logquot_render,
    steps=[
        DerivationStep("quotient_law", "logarithm quotient law", lambda s: {**s, "phase": 1},
                       lambda s: f"the log of a quotient is the difference of the logs"),
        DerivationStep("evaluate_logs", "power law", lambda s: {**s, "phase": 2},
                       lambda s: f"log_{s['base']}({s['x']}) = {s['p']} and log_{s['base']}({s['y']}) = {s['q']}, "
                                 f"so {s['p']} - {s['q']} = {s['p'] - s['q']}")],
    conclusion=lambda s: f"{s['p'] - s['q']}",
    answer=lambda s: {"value": s["p"] - s["q"]},
    oracle=lambda s0: {"value": s0["p"] - s0["q"]},
    invariant=lambda s: s["x"] // s["y"] == s["base"] ** (s["p"] - s["q"]),
    preserved="the value of the logarithm is fixed throughout")


# --- FOIL: (x + a)(x + b) = x^2 + (a+b)x + ab --------------------------------------------------------
def _foil_setup(rng: random.Random) -> dict:
    return {"a": rng.randint(1, 6), "b": rng.randint(1, 6), "phase": 0}


def _foil_render(s: dict) -> str:
    a, b, p = s["a"], s["b"], s["phase"]
    if p == 0:
        return f"(x + {a})(x + {b})"
    if p == 1:
        return f"x^2 + {b}x + {a}x + {a * b}"
    return f"x^2 + {a + b}x + {a * b}"


FOIL_EXPANSION = DerivationSpec(
    slug="foil_expansion", title="expanding two binomials (FOIL)", family="algebra",
    aliases=["foil", "multiply two binomials", "expand the binomials", "product of binomials"], priority=84,
    problem_template="Expand {start} using FOIL.",
    setup=_foil_setup, render=_foil_render,
    steps=[
        DerivationStep("foil", "distributive property (FOIL)", lambda s: {**s, "phase": 1},
                       lambda s: f"multiply first, outer, inner, last: x*x + {s['b']}x + {s['a']}x + "
                                 f"{s['a']}*{s['b']}"),
        DerivationStep("combine_middle", "combine like terms", lambda s: {**s, "phase": 2},
                       lambda s: f"combine the like middle terms: {s['a']}x + {s['b']}x = {s['a'] + s['b']}x")],
    conclusion=lambda s: f"x^2 + {s['a'] + s['b']}x + {s['a'] * s['b']}",
    answer=lambda s: {"linear_coefficient": s["a"] + s["b"], "constant": s["a"] * s["b"]},
    oracle=lambda s0: {"linear_coefficient": s0["a"] + s0["b"], "constant": s0["a"] * s0["b"]},
    invariant=lambda s: (2 + s["a"]) * (2 + s["b"]) == 4 + (s["a"] + s["b"]) * 2 + s["a"] * s["b"],
    preserved="the expression keeps the same value for every x")


# --- difference of squares:  x^2 - a^2 = (x - a)(x + a) ----------------------------------------------
def _dos_setup(rng: random.Random) -> dict:
    return {"a": rng.randint(2, 9), "phase": 0}


def _dos_render(s: dict) -> str:
    a, p = s["a"], s["phase"]
    if p == 0:
        return f"x^2 - {a * a}"
    if p == 1:
        return f"x^2 - {a}^2"
    return f"(x - {a})(x + {a})"


DIFFERENCE_OF_SQUARES = DerivationSpec(
    slug="difference_of_squares", title="factoring a difference of squares", family="algebra",
    aliases=["difference of squares", "factor the difference"], priority=83,
    problem_template="Factor {start}.",
    setup=_dos_setup, render=_dos_render,
    steps=[
        DerivationStep("recognize_squares", "recognizing perfect squares", lambda s: {**s, "phase": 1},
                       lambda s: f"write {s['a'] * s['a']} as {s['a']}^2, giving a difference of two squares"),
        DerivationStep("apply_pattern", "difference-of-squares pattern", lambda s: {**s, "phase": 2},
                       lambda s: f"a^2 - b^2 = (a - b)(a + b), so it factors as (x - {s['a']})(x + {s['a']})")],
    conclusion=lambda s: f"(x - {s['a']})(x + {s['a']})",
    answer=lambda s: {"root": s["a"]},
    oracle=lambda s0: {"root": s0["a"]},
    invariant=lambda s: 10 ** 2 - s["a"] ** 2 == (10 - s["a"]) * (10 + s["a"]),
    preserved="the expression keeps the same value for every x")


# --- perfect square of a binomial:  (x + a)^2 = x^2 + 2ax + a^2 --------------------------------------
def _psq_setup(rng: random.Random) -> dict:
    return {"a": rng.randint(1, 7), "phase": 0}


def _psq_render(s: dict) -> str:
    a, p = s["a"], s["phase"]
    return f"(x + {a})^2" if p == 0 else f"x^2 + {2 * a}x + {a * a}"


PERFECT_SQUARE = DerivationSpec(
    slug="perfect_square_expansion", title="expanding a perfect-square binomial", family="algebra",
    aliases=["perfect square", "square a binomial", "perfect square trinomial"], priority=82,
    problem_template="Expand {start}.",
    setup=_psq_setup, render=_psq_render,
    steps=[DerivationStep("square_binomial", "perfect-square rule", lambda s: {**s, "phase": 1},
                          lambda s: f"(x + a)^2 = x^2 + 2ax + a^2 with a = {s['a']}: "
                                    f"x^2 + {2 * s['a']}x + {s['a'] * s['a']}")],
    conclusion=lambda s: f"x^2 + {2 * s['a']}x + {s['a'] * s['a']}",
    answer=lambda s: {"linear_coefficient": 2 * s["a"], "constant": s["a"] * s["a"]},
    oracle=lambda s0: {"linear_coefficient": 2 * s0["a"], "constant": s0["a"] * s0["a"]},
    invariant=lambda s: (2 + s["a"]) ** 2 == 4 + 2 * s["a"] * 2 + s["a"] * s["a"],
    preserved="the expression keeps the same value for every x")


# --- factoring out the greatest common factor:  (g*p)x + (g*q) = g(px + q) ---------------------------
def _gcf_setup(rng: random.Random) -> dict:
    g = rng.randint(2, 6)
    while True:
        p, q = rng.randint(2, 6), rng.randint(2, 9)
        if gcd(p, q) == 1:                                # so g is exactly the GCF
            return {"g": g, "p": p, "q": q, "phase": 0}


def _gcf_render(s: dict) -> str:
    g, p, q, ph = s["g"], s["p"], s["q"], s["phase"]
    if ph == 0:
        return f"{g * p}x + {g * q}"
    if ph == 1:
        return f"{g}*{p}x + {g}*{q}"
    return f"{g}({p}x + {q})"


FACTOR_GCF = DerivationSpec(
    slug="factor_gcf", title="factoring out the greatest common factor", family="algebra",
    aliases=["factor out the gcf", "greatest common factor", "factoring gcf", "common factor"], priority=81,
    problem_template="Factor {start} by taking out the greatest common factor.",
    setup=_gcf_setup, render=_gcf_render,
    steps=[
        DerivationStep("find_gcf", "greatest common factor", lambda s: {**s, "phase": 1},
                       lambda s: f"the GCF of {s['g'] * s['p']} and {s['g'] * s['q']} is {s['g']}"),
        DerivationStep("factor_out", "distributive property (in reverse)", lambda s: {**s, "phase": 2},
                       lambda s: f"divide each term by {s['g']} and write it outside: "
                                 f"{s['g']}({s['p']}x + {s['q']})")],
    conclusion=lambda s: f"{s['g']}({s['p']}x + {s['q']})",
    answer=lambda s: {"gcf": s["g"]},
    oracle=lambda s0: {"gcf": s0["g"]},
    invariant=lambda s: s["g"] * s["p"] + s["g"] * s["q"] == s["g"] * (s["p"] + s["q"]),
    preserved="the expression keeps the same value for every x")


# --- sum of 1..n by the arithmetic-series formula (Gauss pairing) ------------------------------------
def _sumn_setup(rng: random.Random) -> dict:
    return {"n": rng.randint(5, 12), "phase": 0}


def _sumn_render(s: dict) -> str:
    n, p = s["n"], s["phase"]
    if p == 0:
        return f"1 + 2 + ... + {n}"
    if p == 1:
        return f"{n}({n} + 1)/2"
    return f"{n * (n + 1) // 2}"


SUM_ARITHMETIC_SERIES = DerivationSpec(
    slug="sum_first_n", title="sum of the first n integers (Gauss)", family="algebra",
    aliases=["sum of the first n", "sum 1 to n", "gauss sum", "arithmetic series sum"], priority=80,
    problem_template="Find the sum {start} using the arithmetic-series formula.",
    setup=_sumn_setup, render=_sumn_render,
    steps=[
        DerivationStep("apply_formula", "arithmetic-series (Gauss pairing) formula", lambda s: {**s, "phase": 1},
                       lambda s: f"pairing terms gives sum = n(n+1)/2 with n = {s['n']}"),
        DerivationStep("evaluate", "arithmetic", lambda s: {**s, "phase": 2},
                       lambda s: f"{s['n']} x {s['n'] + 1} / 2 = {s['n'] * (s['n'] + 1) // 2}")],
    conclusion=lambda s: f"{s['n'] * (s['n'] + 1) // 2}",
    answer=lambda s: {"sum": s["n"] * (s["n"] + 1) // 2},
    oracle=lambda s0: {"sum": s0["n"] * (s0["n"] + 1) // 2},
    invariant=lambda s: sum(range(1, s["n"] + 1)) == s["n"] * (s["n"] + 1) // 2,
    preserved="the value of the sum is fixed")


# --- completing the square:  x^2 + 2h x  ->  (x + h)^2 - h^2 -----------------------------------------
def _cts_setup(rng: random.Random) -> dict:
    return {"h": rng.randint(1, 6), "phase": 0}


def _cts_render(s: dict) -> str:
    h, p = s["h"], s["phase"]
    if p == 0:
        return f"x^2 + {2 * h}x"
    if p == 1:                                            # add AND subtract (b/2)^2 -- the load-bearing step
        return f"x^2 + {2 * h}x + {h * h} - {h * h}"
    return f"(x + {h})^2 - {h * h}"


COMPLETE_THE_SQUARE = DerivationSpec(
    slug="complete_the_square", title="completing the square", family="algebra",
    aliases=["complete the square", "completing the square"], priority=79,
    problem_template="Complete the square for {start}.",
    setup=_cts_setup, render=_cts_render,
    steps=[
        DerivationStep("add_and_subtract_square", "completing-the-square rule", lambda s: {**s, "phase": 1},
                       lambda s: f"half of {2 * s['h']} is {s['h']}, and {s['h']}^2 = {s['h'] * s['h']}; add and "
                                 f"subtract {s['h'] * s['h']} so the value is unchanged"),
        DerivationStep("factor_the_trinomial", "perfect-square pattern", lambda s: {**s, "phase": 2},
                       lambda s: f"the first three terms x^2 + {2 * s['h']}x + {s['h'] * s['h']} are the perfect "
                                 f"square (x + {s['h']})^2")],
    conclusion=lambda s: f"(x + {s['h']})^2 - {s['h'] * s['h']}",
    answer=lambda s: {"h": s["h"]},
    oracle=lambda s0: {"h": s0["h"]},
    invariant=lambda s: 1 + 2 * s["h"] == (1 + s["h"]) ** 2 - s["h"] ** 2,
    preserved="the expression keeps the same value for every x")


# --- geometric series sum:  1 + 2 + 4 + ... + 2^(n-1) = 2^n - 1 --------------------------------------
def _geo_setup(rng: random.Random) -> dict:
    return {"n": rng.randint(3, 6), "phase": 0}


def _geo_render(s: dict) -> str:
    n, p = s["n"], s["phase"]
    if p == 0:
        return f"1 + 2 + 4 + ... + {2 ** (n - 1)}"
    if p == 1:
        return f"(2^{n} - 1)/(2 - 1)"
    return f"{2 ** n - 1}"


SUM_GEOMETRIC_SERIES = DerivationSpec(
    slug="sum_geometric_series", title="sum of a geometric series (ratio 2)", family="algebra",
    aliases=["geometric series sum", "sum of a geometric series", "sum of powers of two"], priority=78,
    problem_template="Find the sum {start} using the geometric-series formula.",
    setup=_geo_setup, render=_geo_render,
    steps=[
        DerivationStep("apply_formula", "geometric-series formula", lambda s: {**s, "phase": 1},
                       lambda s: f"sum = (r^n - 1)/(r - 1) with r = 2, n = {s['n']}"),
        DerivationStep("evaluate", "arithmetic", lambda s: {**s, "phase": 2},
                       lambda s: f"(2^{s['n']} - 1)/1 = {2 ** s['n'] - 1}")],
    conclusion=lambda s: f"{2 ** s['n'] - 1}",
    answer=lambda s: {"sum": 2 ** s["n"] - 1},
    oracle=lambda s0: {"sum": 2 ** s0["n"] - 1},
    invariant=lambda s: sum(2 ** i for i in range(s["n"])) == 2 ** s["n"] - 1,
    preserved="the value of the sum is fixed")


# --- difference of cubes:  x^3 - a^3 = (x - a)(x^2 + ax + a^2) ---------------------------------------
def _doc_setup(rng: random.Random) -> dict:
    return {"a": rng.randint(2, 5), "phase": 0}


def _doc_render(s: dict) -> str:
    a, p = s["a"], s["phase"]
    if p == 0:
        return f"x^3 - {a ** 3}"
    if p == 1:
        return f"x^3 - {a}^3"
    return f"(x - {a})(x^2 + {a}x + {a * a})"


DIFFERENCE_OF_CUBES = DerivationSpec(
    slug="difference_of_cubes", title="factoring a difference of cubes", family="algebra",
    aliases=["difference of cubes"], priority=77,
    problem_template="Factor {start}.",
    setup=_doc_setup, render=_doc_render,
    steps=[
        DerivationStep("recognize_cubes", "recognizing perfect cubes", lambda s: {**s, "phase": 1},
                       lambda s: f"write {s['a'] ** 3} as {s['a']}^3, giving a difference of two cubes"),
        DerivationStep("apply_pattern", "difference-of-cubes pattern", lambda s: {**s, "phase": 2},
                       lambda s: f"a^3 - b^3 = (a - b)(a^2 + ab + b^2), so it factors as "
                                 f"(x - {s['a']})(x^2 + {s['a']}x + {s['a'] * s['a']})")],
    conclusion=lambda s: f"(x - {s['a']})(x^2 + {s['a']}x + {s['a'] * s['a']})",
    answer=lambda s: {"root": s["a"]},
    oracle=lambda s0: {"root": s0["a"]},
    invariant=lambda s: 10 ** 3 - s["a"] ** 3 == (10 - s["a"]) * (100 + 10 * s["a"] + s["a"] ** 2),
    preserved="the expression keeps the same value for every x")


# --- cube of a binomial:  (x + a)^3 = x^3 + 3ax^2 + 3a^2 x + a^3 -------------------------------------
def _cub_setup(rng: random.Random) -> dict:
    return {"a": rng.randint(1, 5), "phase": 0}


def _cub_render(s: dict) -> str:
    a, p = s["a"], s["phase"]
    return (f"(x + {a})^3" if p == 0
            else f"x^3 + {3 * a}x^2 + {3 * a * a}x + {a ** 3}")


CUBE_OF_BINOMIAL = DerivationSpec(
    slug="cube_of_binomial", title="expanding the cube of a binomial", family="algebra",
    aliases=["cube of a binomial", "cube a binomial", "binomial cubed"], priority=76,
    problem_template="Expand {start}.",
    setup=_cub_setup, render=_cub_render,
    steps=[DerivationStep("cube_binomial", "binomial-cube rule", lambda s: {**s, "phase": 1},
                          lambda s: f"(x + a)^3 = x^3 + 3ax^2 + 3a^2x + a^3 with a = {s['a']}: "
                                    f"x^3 + {3 * s['a']}x^2 + {3 * s['a'] * s['a']}x + {s['a'] ** 3}")],
    conclusion=lambda s: f"x^3 + {3 * s['a']}x^2 + {3 * s['a'] * s['a']}x + {s['a'] ** 3}",
    answer=lambda s: {"a_cubed": s["a"] ** 3},
    oracle=lambda s0: {"a_cubed": s0["a"] ** 3},
    invariant=lambda s: (2 + s["a"]) ** 3 == 8 + 3 * s["a"] * 4 + 3 * s["a"] ** 2 * 2 + s["a"] ** 3,
    preserved="the expression keeps the same value for every x")


# --- sum of the first n odd numbers:  1 + 3 + ... + (2n-1) = n^2 ------------------------------------
def _odd_setup(rng: random.Random) -> dict:
    return {"n": rng.randint(4, 9), "phase": 0}


def _odd_render(s: dict) -> str:
    n, p = s["n"], s["phase"]
    if p == 0:
        return f"1 + 3 + 5 + ... + {2 * n - 1}"
    if p == 1:
        return f"{n}^2"
    return f"{n * n}"


SUM_ODD_NUMBERS = DerivationSpec(
    slug="sum_odd_numbers", title="sum of the first n odd numbers", family="algebra",
    aliases=["sum of odd numbers", "sum of consecutive odd", "odd numbers sum"], priority=75,
    problem_template="Find the sum {start}.",
    setup=_odd_setup, render=_odd_render,
    steps=[
        DerivationStep("apply_identity", "sum-of-odds identity", lambda s: {**s, "phase": 1},
                       lambda s: f"the sum of the first n odd numbers is n^2, with n = {s['n']}"),
        DerivationStep("evaluate", "arithmetic", lambda s: {**s, "phase": 2},
                       lambda s: f"{s['n']}^2 = {s['n'] * s['n']}")],
    conclusion=lambda s: f"{s['n'] * s['n']}",
    answer=lambda s: {"sum": s["n"] * s["n"]},
    oracle=lambda s0: {"sum": s0["n"] * s0["n"]},
    invariant=lambda s: sum(2 * i - 1 for i in range(1, s["n"] + 1)) == s["n"] * s["n"],
    preserved="the value of the sum is fixed")


ALL_SPECS = [EXPONENT_LAWS, POWER_OF_POWER, LOG_EVALUATION, LOG_PRODUCT_LAW, LOG_QUOTIENT_LAW, FOIL_EXPANSION,
             DIFFERENCE_OF_SQUARES, PERFECT_SQUARE, FACTOR_GCF, SUM_ARITHMETIC_SERIES,
             COMPLETE_THE_SQUARE, SUM_GEOMETRIC_SERIES, DIFFERENCE_OF_CUBES, CUBE_OF_BINOMIAL, SUM_ODD_NUMBERS]
