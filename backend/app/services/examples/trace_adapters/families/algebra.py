"""Algebra family (ADAPTER_CATALOG B1) — symbolic equation solving. Members here: solving a quadratic
equation. Future: linear equations, systems, factoring, completing the square, inequalities.

TEMPLATE — this is the reference *non-coding* adapter every new NON-coding concept follows. It is IDENTICAL
in contract to a coding adapter (ExampleSpec · candidates · reference-verified trace · required cases ·
structured facts · equivalence/entailment hooks) with ONE difference: **there is no code**. The worked
example is the calculation itself — identify coefficients -> discriminant -> roots — and the adapter ships
NO canonical_solution. Everything else (the executable-truth `reference()`, the verified trace, the teaching
boundaries) is the same, which is exactly why the framework covers concepts that "just won't have code"."""
from __future__ import annotations

import math
import random
import re
from typing import Any, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase

_CONV = {"form": "ax^2 + bx + c = 0", "method": "quadratic formula",
         "formula": "x = (-b +/- sqrt(b^2 - 4ac)) / (2a)", "discriminant": "D = b^2 - 4ac"}
_REQUIRED = ["identify_coefficients", "compute_discriminant", "state_roots", "completion"]
_INV = [{"id": "roots_satisfy", "scope": "final_only",
         "statement": "each stated root r satisfies a*r^2 + b*r + c = 0"}]


def _ints(*parts: Any) -> list[int]:
    """The integers that legitimately appear in a step's OWN verified prose — used as `allowed_values`, so a
    faithful card passes while an invented number (a wrong root / discriminant) is still caught. Robust to
    formula constants (the `2` in b^2, the `4` in 4ac) and signs. (Shared pattern across computation adapters.)"""
    found: set[int] = set()
    for m in re.findall(r"-?\d+", " ".join(str(p) for p in parts)):
        found.add(int(m))
        found.add(abs(int(m)))
    return sorted(found)


def _fmt_eq(a: int, b: int, c: int) -> str:
    def term(coef, var):
        if coef == 0:
            return ""
        sign = " + " if coef > 0 else " - "
        mag = abs(coef)
        body = var if (mag == 1 and var) else f"{mag}{var}"
        return f"{sign}{body}"
    lead = f"{a}x^2" if a != 1 else "x^2"
    return (lead + term(b, "x") + term(c, "")).replace("+ -", "- ") + " = 0"


class QuadraticEquationAdapter(FamilyAdapterBase):
    slug = "quadratic"
    label_convention = "ints"                  # §2.3 — coefficients / roots are integers
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(3, 3), value_range=(-6, 6),
                            structure=["a_nonzero", "integer_roots"]),
        stages={
            "identify_coefficients": StageSpec(
                "identify_coefficients", "read a, b, c off the standard form",
                teaching_focus="match the equation to ax^2 + bx + c = 0", cardinality="exactly_once",
                contains={"read_a_b_c": "required"}, state_effects=["a, b, c are named"]),
            "compute_discriminant": StageSpec(
                "compute_discriminant", "evaluate D = b^2 - 4ac", cardinality="exactly_once",
                teaching_focus="the discriminant decides how many real roots there are",
                contains={"substitute": "required", "evaluate": "required"},
                state_effects=["D is known; its sign classifies the roots"]),
            "state_roots": StageSpec(
                "state_roots", "apply the quadratic formula", cardinality="exactly_once",
                teaching_focus="x = (-b +/- sqrt(D)) / (2a)",
                contains={"apply_formula": "required"}, state_effects=["the root(s) are stated"])},
        structure="identify_coefficients compute_discriminant state_roots",
        must_exercise=["identify_coefficients", "compute_discriminant", "state_roots", "completion"],
        must_cover=["two_real_roots", "repeated_root", "complex_roots"],   # per-SUITE (a single instance is one)
        must_avoid=["a_equals_zero"],
        terminal="the root(s) are stated", output_shape="the set of roots")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            r1, r2 = rng.randint(-6, 6), rng.randint(-6, 6)   # integer roots -> clean template
            a = 1
            b = -(r1 + r2)
            c = r1 * r2
            yield {"a": a, "b": b, "c": c, "roots": sorted({r1, r2}), "_id": f"quadratic_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) == 3 and bool(ev.get("compute_discriminant")) and bool(ev.get("state_roots"))

    def _classify(self, disc: int) -> str:
        return "two_real_roots" if disc > 0 else ("repeated_root" if disc == 0 else "complex_roots")

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        a, b, c = example_input["a"], example_input["b"], example_input["c"]
        disc = b * b - 4 * a * c
        case = self._classify(disc)
        if disc >= 0:
            root = math.isqrt(disc) if int(math.isqrt(disc)) ** 2 == disc else disc ** 0.5
            roots = sorted({(-b + root) / (2 * a), (-b - root) / (2 * a)})
            roots = [int(r) if float(r).is_integer() else round(r, 3) for r in roots]
            roots_text = " and ".join(f"x = {r}" for r in roots)
        else:
            real, imag = -b / (2 * a), (abs(disc) ** 0.5) / (2 * a)
            roots = [f"{real:g} + {imag:g}i", f"{real:g} - {imag:g}i"]
            roots_text = " and ".join(roots)

        eq = _fmt_eq(a, b, c)
        st_coef = {"a": a, "b": b, "c": c}
        st_disc = {**st_coef, "discriminant": disc}
        st_roots = {**st_disc, "roots": roots}

        d1 = f"a = {a}, b = {b}, c = {c}"
        r1 = f"matching {eq} to ax^2 + bx + c = 0 gives a = {a}, b = {b}, c = {c}"
        e1 = f"Coefficients: a = {a}, b = {b}, c = {c}."
        f1 = [fact("coefficient", f"a = {a}"), fact("coefficient", f"c = {c}")]
        d2 = f"D = {disc}"
        r2 = f"D = b^2 - 4ac = ({b})^2 - 4({a})({c}) = {disc}, so there are {case.replace('_', ' ')}"
        e2 = f"Discriminant D = ({b})^2 - 4({a})({c}) = {disc}."
        f2 = [fact("discriminant", f"D = {disc}"), fact("nature", case.replace("_", " "))]
        d3 = roots_text
        r3 = f"x = (-b +/- sqrt(D)) / (2a) = ({-b} +/- sqrt({disc})) / {2 * a} gives {roots_text}"
        e3 = f"Roots: {roots_text}."
        f3 = [fact("roots", roots_text)]

        steps = [
            Step(id="s1", operation="identify_coefficients", prior_state={"equation": eq},
                 state_after=dict(st_coef), inputs={"a": a, "b": b, "c": c}, decision=d1, reason=r1,
                 visual_state={"kind": "equation", "a": a, "b": b, "c": c}, expected_visible_result=e1,
                 facts={"allowed_values": _ints(d1, r1, e1, *(x["text"] for x in f1)),
                        "required_facts": f1, "forbidden_claims": []}),
            Step(id="s2", operation="compute_discriminant", prior_state=dict(st_coef),
                 state_after=dict(st_disc), inputs={"discriminant": disc}, decision=d2, reason=r2,
                 visual_state={"kind": "equation", "discriminant": disc}, expected_visible_result=e2,
                 facts={"allowed_values": _ints(d2, r2, e2, *(x["text"] for x in f2)),
                        "required_facts": f2, "forbidden_claims": []}),
            Step(id="s3", operation="state_roots", prior_state=dict(st_disc), state_after=dict(st_roots),
                 inputs={"roots": roots}, decision=d3, reason=r3,
                 visual_state={"kind": "equation", "roots": roots}, expected_visible_result=e3,
                 facts={"allowed_values": _ints(d3, r3, e3, *(x["text"] for x in f3)),
                        "required_facts": f3, "forbidden_claims": []}),
        ]
        evidence = {"identify_coefficients": ["s1"], "compute_discriminant": ["s2"],
                    "state_roots": ["s3"], "completion": ["s3"], case: ["s2"]}
        return ContractTrace(
            problem=f"Solve the quadratic equation {eq} using the quadratic formula.",
            conventions=dict(_CONV), initial_state={"equation": eq},
            final_answer={"roots": roots}, steps=steps,
            invariants=[dict(x) for x in _INV], required_cases=list(_REQUIRED), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        ka, kb = a or {}, b or {}
        keys = set(ka) | set(kb)
        return all(str(ka.get(k)) == str(kb.get(k)) for k in keys)

    def final_answer_entails(self, state, answer):
        return list((state or {}).get("roots") or []) == list((answer or {}).get("roots") or [])

    def invariant_holds(self, inv, state):
        if inv.get("id") != "roots_satisfy":
            return True
        roots = (state or {}).get("roots")
        a, b, c = state.get("a"), state.get("b"), state.get("c")
        if not roots or a is None:
            return True                                     # only checkable once roots are stated
        ok = True
        for r in roots:
            if isinstance(r, (int, float)):
                ok = ok and abs(a * r * r + b * r + c) < 1e-6
        return ok

    def validate_step_shape(self, step):
        allowed = {"identify_coefficients", "compute_discriminant", "state_roots"}
        return [] if step.operation in allowed else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        if step.operation == "compute_discriminant":
            d = str(step.inputs["discriminant"])
            return [] if d in prose else [("discriminant_not_stated", d)]
        return []
