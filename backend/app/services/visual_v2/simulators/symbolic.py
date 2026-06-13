"""Deterministic symbolic-derivation simulators (formula_substitution mode).

`simulate_quadratic_formula` evaluates x = (-b ± sqrt(b^2 - 4ac)) / 2a on concrete
coefficients and emits one step per derivation move: substitute → discriminant →
square root → the ± split → each root → the result. The arithmetic is computed,
never asserted — the trace is the source of truth (EXAMPLE_SYSTEM_SPEC §3.4
pattern `formula_substitution`).
"""

from __future__ import annotations

import math
from typing import Any

from ..schemas import CanonicalExample, Trace


def _fmt(value: float) -> str:
    """Integers as integers, everything else as a short float."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return f"{value:g}"


def _signed(value: float) -> str:
    """Render a coefficient for display inside the substituted formula."""
    return f"({_fmt(value)})" if value < 0 else _fmt(value)


def simulate_quadratic_formula(example: CanonicalExample) -> Trace:
    params = dict(example.get("input") or {})
    a = float(params.get("a", 1))
    b = float(params.get("b", 0))
    c = float(params.get("c", 0))
    if a == 0:
        raise ValueError("quadratic_formula requires a != 0")

    disc = b * b - 4 * a * c
    steps: list[dict[str, Any]] = []

    def step(kind: str, delta: dict[str, Any], notice: str) -> None:
        steps.append({
            "trace_step_id": f"s{len(steps) + 1}",
            "kind": kind,
            "delta": delta,
            "primary_change": next(iter(delta)),
            "learner_should_notice": notice,
            "code_line_refs": [],
            "runtime_label": "",
        })

    substituted = (
        f"x = (-({_fmt(b)}) ± √({_signed(b)}² − 4·{_signed(a)}·{_signed(c)})) / (2·{_signed(a)})"
    )
    step("substitute", {"set_substituted": substituted},
         f"Replace a, b, c with {_fmt(a)}, {_fmt(b)}, {_fmt(c)}.")

    step("apply_rule", {"add_computation": {
        "label": "discriminant",
        "calc": f"b² − 4ac = {_signed(b)}² − 4·{_signed(a)}·{_signed(c)} = {_fmt(b * b)} − {_fmt(4 * a * c)} = {_fmt(disc)}",
    }}, "The discriminant decides how many real roots exist.")

    if disc < 0:
        step("state_result", {"set_result": "no real roots (discriminant < 0)"},
             "A negative discriminant means no real solutions.")
        initial = {"formula": "x = (-b ± √(b² − 4ac)) / (2a)", "substituted": None,
                   "computations": [], "result": None}
        return Trace(
            trace_id=f"{example.get('example_id', 'ex')}:quadratic_formula",
            example_id=str(example.get("example_id", "")),
            trace_source="deterministic_simulator",
            initial_state=initial,
            steps=steps,
            final_state={},
            simulator_version="1",
        )

    root = math.sqrt(disc)
    step("apply_rule", {"add_computation": {
        "label": "square root",
        "calc": f"√{_fmt(disc)} = {_fmt(root)}",
    }}, "Take the square root of the discriminant.")

    minus_b = -b
    two_a = 2 * a
    step("apply_rule", {"add_computation": {
        "label": "the ± split",
        "calc": f"x = ({_fmt(minus_b)} ± {_fmt(root)}) / {_fmt(two_a)}",
    }}, "The ± produces the two candidate roots.")

    x1 = (minus_b + root) / two_a
    x2 = (minus_b - root) / two_a
    step("apply_rule", {"add_computation": {
        "label": "x₁ (take +)",
        "calc": f"({_fmt(minus_b)} + {_fmt(root)}) / {_fmt(two_a)} = {_fmt(x1)}",
    }}, "Evaluate the + branch.")
    if disc > 0:
        step("apply_rule", {"add_computation": {
            "label": "x₂ (take −)",
            "calc": f"({_fmt(minus_b)} − {_fmt(root)}) / {_fmt(two_a)} = {_fmt(x2)}",
        }}, "Evaluate the − branch.")
        result = f"x = {_fmt(x1)} or x = {_fmt(x2)}"
    else:
        result = f"x = {_fmt(x1)} (a double root)"
    step("state_result", {"set_result": result}, "State both solutions of the equation.")

    initial = {"formula": "x = (-b ± √(b² − 4ac)) / (2a)", "substituted": None,
               "computations": [], "result": None}
    return Trace(
        trace_id=f"{example.get('example_id', 'ex')}:quadratic_formula",
        example_id=str(example.get("example_id", "")),
        trace_source="deterministic_simulator",
        initial_state=initial,
        steps=steps,
        final_state={},
        simulator_version="1",
    )


# --- shared scaffolding for the simpler formula derivations ---------------------

def _steps_builder():
    steps: list[dict[str, Any]] = []

    def step(kind: str, delta: dict[str, Any], notice: str) -> None:
        steps.append({
            "trace_step_id": f"s{len(steps) + 1}",
            "kind": kind,
            "delta": delta,
            "primary_change": next(iter(delta)),
            "learner_should_notice": notice,
            "code_line_refs": [],
            "runtime_label": "",
        })

    return steps, step


def _formula_trace(example: CanonicalExample, formula: str, steps: list[dict[str, Any]], key: str) -> Trace:
    return Trace(
        trace_id=f"{example.get('example_id', 'ex')}:{key}",
        example_id=str(example.get("example_id", "")),
        trace_source="deterministic_simulator",
        initial_state={"formula": formula, "substituted": None, "computations": [], "result": None},
        steps=steps,
        final_state={},
        simulator_version="1",
    )


def simulate_linear_equation(example: CanonicalExample) -> Trace:
    """Solve ax + b = c by inverse operations (pattern: equation_solving)."""
    p = dict(example.get("input") or {})
    a, b, c = float(p.get("a", 1)), float(p.get("b", 0)), float(p.get("c", 0))
    if a == 0:
        raise ValueError("linear_equation requires a != 0")
    steps, step = _steps_builder()

    step("substitute", {"set_substituted": f"{_fmt(a)}x + {_signed(b)} = {_fmt(c)}"},
         "The concrete equation to solve.")
    rhs = c - b
    step("apply_rule", {"add_computation": {
        "label": f"subtract {_fmt(b)} from both sides",
        "calc": f"{_fmt(a)}x = {_fmt(c)} − {_signed(b)} = {_fmt(rhs)}",
    }}, "Undo the addition first to isolate the x term.")
    x = rhs / a
    step("apply_rule", {"add_computation": {
        "label": f"divide both sides by {_fmt(a)}",
        "calc": f"x = {_fmt(rhs)} / {_fmt(a)} = {_fmt(x)}",
    }}, "Undo the multiplication to isolate x.")
    step("apply_rule", {"add_computation": {
        "label": "check",
        "calc": f"{_fmt(a)}·{_fmt(x)} + {_signed(b)} = {_fmt(a * x + b)}",
    }}, "Substitute back: both sides match.")
    step("state_result", {"set_result": f"x = {_fmt(x)}"}, "The solution.")
    return _formula_trace(example, "ax + b = c", steps, "linear_equation")


def simulate_distance_formula(example: CanonicalExample) -> Trace:
    """Distance between two points (pattern: formula_substitution)."""
    p = dict(example.get("input") or {})
    x1, y1 = float(p.get("x1", 0)), float(p.get("y1", 0))
    x2, y2 = float(p.get("x2", 0)), float(p.get("y2", 0))
    steps, step = _steps_builder()

    step("substitute", {"set_substituted":
         f"d = √(({_fmt(x2)} − {_signed(x1)})² + ({_fmt(y2)} − {_signed(y1)})²)"},
         "Substitute both points into the formula.")
    dx, dy = x2 - x1, y2 - y1
    step("apply_rule", {"add_computation": {
        "label": "horizontal difference",
        "calc": f"Δx = {_fmt(x2)} − {_signed(x1)} = {_fmt(dx)}",
    }}, "How far apart the points are horizontally.")
    step("apply_rule", {"add_computation": {
        "label": "vertical difference",
        "calc": f"Δy = {_fmt(y2)} − {_signed(y1)} = {_fmt(dy)}",
    }}, "How far apart the points are vertically.")
    sq = dx * dx + dy * dy
    step("apply_rule", {"add_computation": {
        "label": "sum of squares",
        "calc": f"{_fmt(dx)}² + {_fmt(dy)}² = {_fmt(dx * dx)} + {_fmt(dy * dy)} = {_fmt(sq)}",
    }}, "Square both differences and add (this is the Pythagorean theorem).")
    d = math.sqrt(sq)
    step("apply_rule", {"add_computation": {
        "label": "square root",
        "calc": f"d = √{_fmt(sq)} = {_fmt(d)}",
    }}, "The distance is the hypotenuse.")
    step("state_result", {"set_result": f"d = {_fmt(d)}"}, "The distance between the points.")
    return _formula_trace(example, "d = √((x₂ − x₁)² + (y₂ − y₁)²)", steps, "distance_formula")


def simulate_compound_interest(example: CanonicalExample) -> Trace:
    """A = P(1 + r/n)^(nt) (pattern: formula_substitution)."""
    p = dict(example.get("input") or {})
    P, r = float(p.get("P", 0)), float(p.get("r", 0))
    n, t = float(p.get("n", 1)), float(p.get("t", 1))
    if n <= 0:
        raise ValueError("compound_interest requires n > 0")
    steps, step = _steps_builder()

    step("substitute", {"set_substituted":
         f"A = {_fmt(P)} · (1 + {_fmt(r)}/{_fmt(n)})^({_fmt(n)}·{_fmt(t)})"},
         "Substitute principal, rate, compounding count, and years.")
    growth = 1 + r / n
    step("apply_rule", {"add_computation": {
        "label": "growth factor per period",
        "calc": f"1 + {_fmt(r)}/{_fmt(n)} = {_fmt(growth)}",
    }}, "Each compounding period multiplies the balance by this factor.")
    periods = n * t
    step("apply_rule", {"add_computation": {
        "label": "number of periods",
        "calc": f"{_fmt(n)} · {_fmt(t)} = {_fmt(periods)}",
    }}, "Compounding events over the whole term.")
    factor = growth ** periods
    step("apply_rule", {"add_computation": {
        "label": "total growth",
        "calc": f"{_fmt(growth)}^{_fmt(periods)} = {round(factor, 6):g}",
    }}, "Apply the factor once per period.")
    A = P * factor
    step("apply_rule", {"add_computation": {
        "label": "final amount",
        "calc": f"{_fmt(P)} · {round(factor, 6):g} = {round(A, 2):g}",
    }}, "Scale the principal by the total growth.")
    step("state_result", {"set_result": f"A = {round(A, 2):g}"}, "The balance after the full term.")
    return _formula_trace(example, "A = P(1 + r/n)^(nt)", steps, "compound_interest")


def simulate_induction_proof(example: CanonicalExample) -> Trace:
    """Proof by induction that 1 + 2 + ... + n = n(n+1)/2 (pattern: proof chain,
    rendered with the formula renderer — claim → base case → step → QED)."""
    steps, step = _steps_builder()

    step("substitute", {"set_substituted": "Claim: 1 + 2 + ... + n = n(n+1)/2 for all n ≥ 1"},
         "State the claim to prove for every positive integer n.")
    step("apply_rule", {"add_computation": {
        "label": "Base case (n = 1)",
        "calc": "left side = 1; right side = 1·(1+1)/2 = 1 — they match.",
    }}, "The claim holds at the smallest case.")
    step("apply_rule", {"add_computation": {
        "label": "Inductive hypothesis",
        "calc": "Assume 1 + 2 + ... + k = k(k+1)/2 holds for some k ≥ 1.",
    }}, "Assume the claim for an arbitrary k.")
    step("apply_rule", {"add_computation": {
        "label": "Inductive step (n = k+1)",
        "calc": "1 + ... + k + (k+1) = k(k+1)/2 + (k+1) = (k+1)(k+2)/2.",
    }}, "Add the next term to the hypothesis — it becomes the formula at k+1.")
    step("state_result", {"set_result": "By induction, the formula holds for all n ≥ 1.  ∎"},
         "Base case + step prove every case, like dominoes falling.")
    return _formula_trace(example, "1 + 2 + ... + n = n(n+1)/2", steps, "induction_proof")
