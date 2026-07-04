"""T8b derivation CONCEPT SPECS (CP12d) — rule-justified algebra-law derivations on the derivation engine. Each
is DATA: build an instance, render its state, the ordered rule-cited steps, the conclusion, the answer, and an
independent oracle. Adding a concept = add a `DerivationSpec` to `ALL_SPECS`."""
from __future__ import annotations

import random

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
    aliases=["evaluate a logarithm", "logarithm evaluation", "log base", "logarithm law"], priority=93,
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


ALL_SPECS = [EXPONENT_LAWS, POWER_OF_POWER, LOG_EVALUATION]
