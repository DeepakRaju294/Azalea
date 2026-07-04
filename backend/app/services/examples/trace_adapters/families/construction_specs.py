"""T8a construction CONCEPT SPECS (CP12d) — incremental-construction concepts on the construct engine. Each is
DATA: build an instance, the piece count, how to add the i-th piece, render the partial output, a validity
predicate, the answer, and an independent oracle. Adding a concept = add a `ConstructSpec` to `ALL_SPECS`."""
from __future__ import annotations

import math
import random

from .construct_engine import ConstructSpec


def _seq(xs: list) -> str:
    return ", ".join(str(x) for x in xs) if xs else "(empty)"


def _term_str(c: int, e: int, var: str = "x") -> str:
    if e == 0:
        return str(c)
    base = var if e == 1 else f"{var}^{e}"
    return base if c == 1 else f"{c}{base}"


def _poly(terms: list, var: str = "x") -> str:
    return " + ".join(_term_str(c, e, var) for c, e in terms) if terms else "0"


def _fib_list(n: int) -> list:
    f: list = []
    for i in range(n):
        f.append(1 if i < 2 else f[-1] + f[-2])
    return f


def _bab_seq(a: int, n: int) -> list:
    """The first n Babylonian (Newton) square-root estimates, rounded to 3 dp so the sequence is
    deterministic. n == 0 -> [] (so partial-validity holds on the empty starting state)."""
    seq: list = []
    for i in range(n):
        if i == 0:
            seq.append(float(a))
        else:
            p = seq[-1]
            seq.append(round((p + a / p) / 2, 3))
    return seq


def _collatz(n: int) -> list:
    seq = [n]
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        seq.append(n)
    return seq


# --- prefix sums / running total ----------------------------------------------------------------------
def _prefix_setup(rng: random.Random) -> dict:
    return {"input": [rng.randint(1, 9) for _ in range(rng.randint(4, 6))], "output": []}


def _prefix_step(s: dict, i: int) -> tuple:
    prev = s["output"][-1] if s["output"] else 0
    new = prev + s["input"][i]
    rule = (f"the first running total is just {s['input'][i]}" if i == 0
            else f"add {s['input'][i]} to the previous total {prev}: {prev} + {s['input'][i]} = {new}")
    return {**s, "output": s["output"] + [new]}, rule


PREFIX_SUMS = ConstructSpec(
    slug="prefix_sums", title="prefix sums (running totals) of a list", family="sequence",
    aliases=["prefix sum", "running total", "cumulative sum"], priority=59, piece_word="running total",
    problem_template="Build the prefix sums (running totals) of the list {input}.",
    setup=_prefix_setup, pieces=lambda s: len(s["input"]), step=_prefix_step,
    render=lambda s: _seq(s["output"]),
    valid=lambda s: s["output"] == [sum(s["input"][: k + 1]) for k in range(len(s["output"]))],
    answer=lambda s: {"running_totals": _seq(s["output"])},
    oracle=lambda s0: {"running_totals": _seq([sum(s0["input"][: k + 1]) for k in range(len(s0["input"]))])},
    target="every running total is listed")


# --- running maximum ----------------------------------------------------------------------------------
def _runmax_setup(rng: random.Random) -> dict:
    return {"input": [rng.randint(1, 20) for _ in range(rng.randint(4, 6))], "output": []}


def _runmax_step(s: dict, i: int) -> tuple:
    prev = s["output"][-1] if s["output"] else None
    new = s["input"][i] if prev is None else max(prev, s["input"][i])
    rule = (f"the first running maximum is {s['input'][i]}" if prev is None
            else f"the larger of the previous max {prev} and {s['input'][i]} is {new}")
    return {**s, "output": s["output"] + [new]}, rule


RUNNING_MAXIMUM = ConstructSpec(
    slug="running_maximum", title="running maximum of a list", family="sequence",
    aliases=["running maximum", "running max", "prefix maximum"], priority=58, piece_word="running maximum",
    problem_template="Build the running maximum of the list {input}.",
    setup=_runmax_setup, pieces=lambda s: len(s["input"]), step=_runmax_step,
    render=lambda s: _seq(s["output"]),
    valid=lambda s: s["output"] == [max(s["input"][: k + 1]) for k in range(len(s["output"]))],
    answer=lambda s: {"running_maxima": _seq(s["output"])},
    oracle=lambda s0: {"running_maxima": _seq([max(s0["input"][: k + 1]) for k in range(len(s0["input"]))])},
    target="every running maximum is listed")


# --- straight-line depreciation schedule (finance, T8a) ----------------------------------------------
def _deprec_setup(rng: random.Random) -> dict:
    life = rng.randint(3, 6)
    annual = rng.randint(50, 300)
    salvage = rng.randint(0, 200)
    cost = salvage + annual * life
    return {"cost": cost, "salvage": salvage, "life": life, "annual": annual, "output": [cost]}


def _deprec_step(s: dict, i: int) -> tuple:
    prev = s["output"][-1]
    new = prev - s["annual"]
    rule = f"year {i + 1}: subtract the annual depreciation {s['annual']}: {prev} - {s['annual']} = {new}"
    return {**s, "output": s["output"] + [new]}, rule


DEPRECIATION_SCHEDULE = ConstructSpec(
    slug="depreciation_schedule", title="straight-line depreciation schedule", family="finance",
    aliases=["depreciation schedule", "straight-line depreciation", "book value schedule"], priority=57,
    piece_word="year", problem_template="An asset costs ${cost} with salvage value ${salvage} and a useful life "
                                        "of {life} years. Build the straight-line book-value schedule.",
    setup=_deprec_setup, pieces=lambda s: s["life"], step=_deprec_step,
    render=lambda s: _seq(s["output"]),
    valid=lambda s: s["output"] == [s["cost"] - s["annual"] * k for k in range(len(s["output"]))],
    answer=lambda s: {"final_book_value": s["output"][-1], "book_values": _seq(s["output"])},
    oracle=lambda s0: {"final_book_value": s0["salvage"],
                       "book_values": _seq([s0["cost"] - s0["annual"] * k for k in range(s0["life"] + 1)])},
    target="the book value reaches the salvage value")


# --- polynomial differentiation (power rule, term by term) --------------------------------------------
def _deriv_setup(rng: random.Random) -> dict:
    exps = sorted(rng.sample([1, 2, 3, 4], rng.choice([2, 3])), reverse=True)
    terms = [[rng.randint(1, 6), e] for e in exps]
    return {"input_terms": terms, "output": [], "input_poly": _poly(terms)}


def _deriv_step(s: dict, i: int) -> tuple:
    c, e = s["input_terms"][i]
    d = [c * e, e - 1]
    rule = f"differentiate {_term_str(c, e)}: multiply by the exponent {e} and lower the power to {e - 1} = {_term_str(*d)}"
    return {**s, "output": s["output"] + [d]}, rule


POLYNOMIAL_DERIVATIVE = ConstructSpec(
    slug="polynomial_derivative", title="differentiating a polynomial (power rule)", family="calculus",
    aliases=["differentiate a polynomial", "differentiating a polynomial", "polynomial derivative",
             "power rule derivative", "find the derivative"],
    priority=56, piece_word="derivative term",
    problem_template="Differentiate f(x) = {input_poly} term by term.",
    setup=_deriv_setup, pieces=lambda s: len(s["input_terms"]), step=_deriv_step,
    render=lambda s: _poly(s["output"]),
    valid=lambda s: s["output"] == [[c * e, e - 1] for c, e in s["input_terms"][: len(s["output"])]],
    answer=lambda s: {"derivative": _poly(s["output"])},
    oracle=lambda s0: {"derivative": _poly([[c * e, e - 1] for c, e in s0["input_terms"]])},
    target="every term has been differentiated")


# --- polynomial integration (reverse power rule, term by term) ----------------------------------------
def _integ_setup(rng: random.Random) -> dict:
    exps = sorted(rng.sample([0, 1, 2, 3], rng.choice([2, 3])), reverse=True)
    terms = [[rng.randint(1, 4) * (e + 1), e] for e in exps]     # coef divisible by (e+1) -> integer integral
    return {"input_terms": terms, "output": [], "input_poly": _poly(terms)}


def _integ_step(s: dict, i: int) -> tuple:
    c, e = s["input_terms"][i]
    d = [c // (e + 1), e + 1]
    rule = f"integrate {_term_str(c, e)}: raise the power to {e + 1} and divide by {e + 1} = {_term_str(*d)}"
    return {**s, "output": s["output"] + [d]}, rule


POLYNOMIAL_INTEGRAL = ConstructSpec(
    slug="polynomial_integral", title="integrating a polynomial (reverse power rule)", family="calculus",
    aliases=["integrate a polynomial", "integrating a polynomial", "polynomial integral", "antiderivative",
             "indefinite integral"],
    priority=55, piece_word="integrated term",
    problem_template="Find the indefinite integral of f(x) = {input_poly} term by term.",
    setup=_integ_setup, pieces=lambda s: len(s["input_terms"]), step=_integ_step,
    render=lambda s: (_poly(s["output"]) + " + C") if s["output"] else "C",
    valid=lambda s: s["output"] == [[c // (e + 1), e + 1] for c, e in s["input_terms"][: len(s["output"])]],
    answer=lambda s: {"integral": _poly(s["output"]) + " + C"},
    oracle=lambda s0: {"integral": _poly([[c // (e + 1), e + 1] for c, e in s0["input_terms"]]) + " + C"},
    target="every term is integrated, plus the constant C")


# --- Fibonacci sequence -------------------------------------------------------------------------------
def _fib_setup(rng: random.Random) -> dict:
    return {"count": rng.randint(6, 9), "output": []}


def _fib_step(s: dict, i: int) -> tuple:
    o = s["output"]
    val = 1 if i < 2 else o[-1] + o[-2]
    rule = ("the first two Fibonacci numbers are 1" if i < 2
            else f"add the previous two: {o[-2]} + {o[-1]} = {val}")
    return {**s, "output": o + [val]}, rule


FIBONACCI_SEQUENCE = ConstructSpec(
    slug="fibonacci_sequence", title="the Fibonacci sequence", family="sequence",
    aliases=["fibonacci"], priority=54, piece_word="Fibonacci number",
    problem_template="Build the first {count} Fibonacci numbers.",
    setup=_fib_setup, pieces=lambda s: s["count"], step=_fib_step,
    render=lambda s: _seq(s["output"]),
    valid=lambda s: s["output"] == _fib_list(len(s["output"])),
    answer=lambda s: {"sequence": _seq(s["output"])},
    oracle=lambda s0: {"sequence": _seq(_fib_list(s0["count"]))},
    target="the requested Fibonacci numbers are listed")


# --- Pascal's triangle row ----------------------------------------------------------------------------
def _pascal_setup(rng: random.Random) -> dict:
    return {"n": rng.randint(3, 6), "output": []}


def _pascal_step(s: dict, k: int) -> tuple:
    n = s["n"]
    val = math.comb(n, k)
    rule = (f"the row starts with 1 (C({n},0))" if k == 0
            else f"C({n},{k}) = {val}")
    return {**s, "output": s["output"] + [val]}, rule


PASCALS_TRIANGLE_ROW = ConstructSpec(
    slug="pascals_triangle_row", title="a row of Pascal's triangle", family="discrete",
    aliases=["pascal's triangle", "pascals triangle", "pascal triangle"], priority=53, piece_word="entry",
    problem_template="Build row n = {n} of Pascal's triangle (the binomial coefficients).",
    setup=_pascal_setup, pieces=lambda s: s["n"] + 1, step=_pascal_step,
    render=lambda s: _seq(s["output"]),
    valid=lambda s: s["output"] == [math.comb(s["n"], k) for k in range(len(s["output"]))],
    answer=lambda s: {"row": _seq(s["output"])},
    oracle=lambda s0: {"row": _seq([math.comb(s0["n"], k) for k in range(s0["n"] + 1)])},
    target="the whole row of binomial coefficients is listed")


# --- powers of two ------------------------------------------------------------------------------------
def _pow2_setup(rng: random.Random) -> dict:
    return {"count": rng.randint(5, 8), "output": []}


def _pow2_step(s: dict, k: int) -> tuple:
    o = s["output"]
    val = 1 if k == 0 else o[-1] * 2
    rule = (f"2^0 = 1" if k == 0 else f"double the previous: {o[-1]} x 2 = {val}  (2^{k})")
    return {**s, "output": o + [val]}, rule


POWERS_OF_TWO = ConstructSpec(
    slug="powers_of_two", title="powers of two", family="discrete",
    aliases=["powers of two", "powers of 2"], priority=52, piece_word="power",
    problem_template="Build the first {count} powers of two (starting at 2^0).",
    setup=_pow2_setup, pieces=lambda s: s["count"], step=_pow2_step,
    render=lambda s: _seq(s["output"]),
    valid=lambda s: s["output"] == [2 ** k for k in range(len(s["output"]))],
    answer=lambda s: {"powers": _seq(s["output"])},
    oracle=lambda s0: {"powers": _seq([2 ** k for k in range(s0["count"])])},
    target="the requested powers of two are listed")


# --- Babylonian square root (iterative refinement / Newton's method) ----------------------------------
def _bab_setup(rng: random.Random) -> dict:
    return {"a": rng.randint(10, 99), "iters": 5, "output": []}


def _bab_step(s: dict, i: int) -> tuple:
    if i == 0:
        val = float(s["a"])
        rule = f"start with the initial guess x0 = {s['a']}"
    else:
        p = s["output"][-1]
        val = round((p + s["a"] / p) / 2, 3)
        rule = f"refine: (x + a/x)/2 = ({p} + {s['a']}/{p})/2 = {val}"
    return {**s, "output": s["output"] + [val]}, rule


BABYLONIAN_SQRT = ConstructSpec(
    slug="babylonian_sqrt", title="estimating a square root (Babylonian method)", family="numerical",
    aliases=["babylonian method", "estimate a square root", "iterative square root",
             "newton's method for a square root"], priority=51, piece_word="estimate",
    problem_template="Estimate sqrt({a}) with the Babylonian method (4 refinements from the initial guess).",
    setup=_bab_setup, pieces=lambda s: s["iters"], step=_bab_step,
    render=lambda s: _seq(s["output"]),
    valid=lambda s: s["output"] == _bab_seq(s["a"], len(s["output"])),
    answer=lambda s: {"estimates": _seq(s["output"])},
    oracle=lambda s0: {"estimates": _seq(_bab_seq(s0["a"], s0["iters"]))},
    target="the estimate has converged toward the square root")


# --- Collatz (3n+1) sequence --------------------------------------------------------------------------
def _collatz_setup(rng: random.Random) -> dict:
    return {"start": rng.randint(5, 20), "output": []}


def _collatz_step(s: dict, i: int) -> tuple:
    if i == 0:
        val = s["start"]
        rule = f"start at {s['start']}"
    else:
        prev = s["output"][-1]
        val = prev // 2 if prev % 2 == 0 else 3 * prev + 1
        rule = (f"{prev} is even, so halve it: {prev}/2 = {val}" if prev % 2 == 0
                else f"{prev} is odd, so 3n+1: 3*{prev}+1 = {val}")
    return {**s, "output": s["output"] + [val]}, rule


COLLATZ_SEQUENCE = ConstructSpec(
    # register=False: Collatz length is unbounded (exceeds the T8a trace budget for larger starts) and the
    # sequence ends in a bare "1" (the terminal-formatting contract rejects a lone-digit ending). Kept as a
    # documented spec; a capped/rephrased version can be enabled later.
    slug="collatz_sequence", title="the Collatz (3n+1) sequence", family="discrete", register=False,
    aliases=["collatz", "3n+1", "hailstone sequence"], priority=50, piece_word="term",
    problem_template="Build the Collatz sequence starting from {start} until it reaches 1.",
    setup=_collatz_setup, pieces=lambda s: len(_collatz(s["start"])), step=_collatz_step,
    render=lambda s: _seq(s["output"]),
    valid=lambda s: s["output"] == _collatz(s["start"])[: len(s["output"])],
    answer=lambda s: {"sequence": _seq(s["output"])},
    oracle=lambda s0: {"sequence": _seq(_collatz(s0["start"]))},
    target="the sequence reaches 1")


ALL_SPECS = [PREFIX_SUMS, RUNNING_MAXIMUM, DEPRECIATION_SCHEDULE,
             POLYNOMIAL_DERIVATIVE, POLYNOMIAL_INTEGRAL, FIBONACCI_SEQUENCE,
             PASCALS_TRIANGLE_ROW, POWERS_OF_TWO, BABYLONIAN_SQRT, COLLATZ_SEQUENCE]
