"""T8a construction CONCEPT SPECS (CP12d) — incremental-construction concepts on the construct engine. Each is
DATA: build an instance, the piece count, how to add the i-th piece, render the partial output, a validity
predicate, the answer, and an independent oracle. Adding a concept = add a `ConstructSpec` to `ALL_SPECS`."""
from __future__ import annotations

import random

from .construct_engine import ConstructSpec


def _seq(xs: list) -> str:
    return ", ".join(str(x) for x in xs) if xs else "(empty)"


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


ALL_SPECS = [PREFIX_SUMS, RUNNING_MAXIMUM, DEPRECIATION_SCHEDULE]
