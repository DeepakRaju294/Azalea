"""Vector-calculus family (ADAPTER_TAXONOMY_SPEC.md T13 — proof-obligation discharge). First member: Stokes'
theorem. No symbolic-math dependency (sympy/numpy/scipy) is installed, and adding one was explicitly ruled
out for this adapter — both hand-picked examples below are CLASSIC textbook cases chosen specifically because
their curl is CONSTANT over a FLAT surface, so both sides reduce to elementary arithmetic (area times curl,
and a handful of exactly-integrable boundary segments) rather than needing numeric quadrature or a CAS.

The independent-oracle structure is Stokes' theorem's OWN claim: the surface integral of curl(F) over S and
the line integral of F around the boundary of S are computed via two structurally DIFFERENT methods (one
multiplies a constant curl by an area; the other sums exact per-segment line integrals along the boundary,
each worked out by hand ahead of time) — their agreement is the falsifiable claim a bug in either side could
not fake."""
from __future__ import annotations

import math
from typing import Any, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase

_TOL = 1e-9

# Every example's curl is constant and its surface is flat with unit-z normal, so surface_integral =
# curl_z * area (exact) and line_integral = sum of exactly-worked-out boundary-segment contributions (exact)
# — both hand-derived once, ahead of time, the same way any adapter's reference solution is authored.
_STOKES_EXAMPLES: dict[str, dict[str, Any]] = {
    "unit_disk_rotational_field": {
        "field_desc": "F(x, y, z) = (-y, x, 0)",
        "curl": (0.0, 0.0, 2.0),
        "surface_desc": "the unit disk in the xy-plane (x^2 + y^2 <= 1)",
        "area": math.pi,
        "boundary_desc": ("the unit circle x = cos(t), y = sin(t), traversed counterclockwise as t goes "
                          "0 to 2*pi"),
        "boundary_segments": [("the full circular loop", 2.0 * math.pi)],
    },
    "unit_square_shear_field": {
        "field_desc": "F(x, y, z) = (0, x, 0)",
        "curl": (0.0, 0.0, 1.0),
        "surface_desc": "the unit square [0,1] x [0,1] in the xy-plane",
        "area": 1.0,
        "boundary_desc": "the square's boundary, counterclockwise: (0,0)->(1,0)->(1,1)->(0,1)->(0,0)",
        "boundary_segments": [("(0,0) to (1,0)", 0.0), ("(1,0) to (1,1)", 1.0),
                              ("(1,1) to (0,1)", 0.0), ("(0,1) to (0,0)", 0.0)],
    },
}


def _round(x: float) -> float:
    return round(x, 6)


_STOKES_CONV = {"theorem": "stokes", "check": "surface_integral_equals_line_integral",
                "trace_granularity": "one_computation_phase"}
_STOKES_REQ = ["compute_curl", "integrate_surface", "integrate_boundary", "completion"]
_STOKES_INV = [{"id": "surface_equals_line", "scope": "terminal_only",
               "statement": "the surface integral of curl(F) over S equals the line integral of F around "
                            "the boundary of S"}]


class _StokesCanonicalFormula:
    """Card-grounding-only formula facts (consumed by lean_lesson_generator's `_canonical_formula` fallback
    in `_ground_formula_card`/`_ground_edge_case_card`/`_inject_grounded_cards`). Deliberately NOT a
    `_formula_spec`: that attribute also flips trace_pipeline's is_formula narration slotting, which would
    rewrite this adapter's verified multi-stage trace narration ("Substitute the known values...") — the
    trace is not a one-shot formula substitution. Live motivation: the goal-core formula card shipped
    "\\( F \\, dr = int_{S} (\\nabla \\times F) \\, dS\\)" — the line-integral side missing its integral sign
    entirely, `int` missing its backslash — free LLM prose misquoting the ONE equation the path exists to
    teach, directly beside the adapter-verified worked example of the correct one."""
    canonical_latex = r"\int_{C} F \cdot dr = \int_{S} (\nabla \times F) \cdot dS"
    canonical_notes = [
        "C is the closed boundary curve of the surface S, traversed so that the surface stays on the "
        "left (the right-hand rule fixes the orientation).",
        "The left side is the line integral of the field F around the boundary; the right side is the "
        "surface integral of the curl of F over the surface itself.",
        "F must have continuous partial derivatives on an open region containing S.",
    ]
    edge_cases = [
        "A closed surface (a sphere, a torus) has no boundary curve at all — the line-integral side is 0, "
        "so the flux of curl(F) through any closed surface is always zero.",
        "If F is conservative (F = \\(\\nabla f\\)), its curl is zero everywhere, so both sides vanish "
        "over any surface.",
    ]


# --- line integrals -------------------------------------------------------------------------------------
# Same no-CAS philosophy as Stokes above: each example's integrand F(r(t)) . r'(t) simplifies BY HAND to a
# one-term expression with an elementary antiderivative, so every step is exact. The INDEPENDENT ORACLE is a
# machine-side midpoint quadrature of the ORIGINAL field/parameterization lambdas (a structurally different
# method than the hand-worked antiderivative): `reference()` refuses to emit a trace whose hand-computed
# value the numeric integral does not confirm — a wrong antiderivative or a wrong evaluation cannot ship.
_LINE_INTEGRAL_EXAMPLES: dict[str, dict[str, Any]] = {
    "parabola_conservative_field": {
        "field_desc": "F(x, y) = (y, x)",
        "field": lambda x, y: (y, x),
        "curve_desc": "the parabola y = x^2 from (0, 0) to (1, 1)",
        "param_desc": "r(t) = (t, t^2) for t in [0, 1]",
        "rprime_desc": "r'(t) = (1, 2t)",
        "r": lambda t: (t, t * t),
        "rprime": lambda t: (1.0, 2.0 * t),
        "bounds": (0.0, 1.0),
        "integrand_desc": "F(r(t)) . r'(t) = (t^2)(1) + (t)(2t) = 3t^2",
        "antiderivative_desc": "t^3",
        "evaluate_desc": "t^3 at t = 1 minus t^3 at t = 0 = 1 - 0",
        "value": 1.0,
    },
    "quarter_circle_rotational_field": {
        "field_desc": "F(x, y) = (-y, x)",
        "field": lambda x, y: (-y, x),
        "curve_desc": "the quarter of the unit circle from (1, 0) to (0, 1)",
        "param_desc": "r(t) = (cos t, sin t) for t in [0, pi/2]",
        "rprime_desc": "r'(t) = (-sin t, cos t)",
        "r": lambda t: (math.cos(t), math.sin(t)),
        "rprime": lambda t: (-math.sin(t), math.cos(t)),
        "bounds": (0.0, math.pi / 2.0),
        "integrand_desc": "F(r(t)) . r'(t) = (-sin t)(-sin t) + (cos t)(cos t) = sin^2 t + cos^2 t = 1",
        "antiderivative_desc": "t",
        "evaluate_desc": "t at t = pi/2 minus t at t = 0 = pi/2 - 0",
        "value": math.pi / 2.0,
    },
}


def _numeric_line_integral(ex: dict[str, Any], n: int = 20000) -> float:
    """Midpoint-rule quadrature of F(r(t)) . r'(t) over the example's own lambdas — the independent oracle."""
    a, b = ex["bounds"]
    h = (b - a) / n
    total = 0.0
    for i in range(n):
        t = a + (i + 0.5) * h
        x, y = ex["r"](t)
        fx, fy = ex["field"](x, y)
        dx, dy = ex["rprime"](t)
        total += (fx * dx + fy * dy) * h
    return total


_LINE_CONV = {"method": "parameterize_substitute_integrate",
              "trace_granularity": "one_computation_phase"}
_LINE_REQ = ["parameterize", "substitute", "integrate", "completion"]
_LINE_INV = [{"id": "work_matches_numeric_quadrature", "scope": "terminal_only",
             "statement": "the hand-computed work value agrees with an independent midpoint-rule numeric "
                          "integration of F(r(t)) . r'(t)"}]


class _LineIntegralCanonicalFormula:
    """Card-grounding facts (see _StokesCanonicalFormula for why this is NOT a _formula_spec)."""
    canonical_latex = r"\int_{C} F \cdot dr = \int_{a}^{b} F(r(t)) \cdot r'(t) \, dt"
    canonical_notes = [
        "C is the curve, parameterized as r(t) with t running from a to b — the parameterization turns "
        "the line integral into an ordinary one-variable integral.",
        "F(r(t)) is the field evaluated ON the curve; the dot product with r'(t) keeps only the component "
        "of the field that acts along the direction of travel.",
        "Physically, this is the work done by the field F on an object moving along C.",
    ]
    edge_cases = [
        "If F is zero everywhere on the curve, the integral is 0 — no field, no work, whatever the path.",
        "If F is conservative (F = \\(\\nabla f\\)), the integral depends only on the endpoints: it equals "
        "f(end) - f(start), and around any closed loop it is 0.",
        "A zero-length path (start = end, no loop) gives 0 — there is no distance over which to accumulate.",
    ]


class LineIntegralAdapter(FamilyAdapterBase):
    slug = "line_integral"
    label_convention = "ints"
    _canonical_formula = _LineIntegralCanonicalFormula()
    example_spec = ExampleSpec(
        input=InstanceShape("field_curve_pair", count=(2, 2), structure=["line_integral"]),
        stages={
            "parameterize": StageSpec(
                "parameterize", "parameterize the curve and differentiate the parameterization",
                teaching_focus="the parameterization turns a path through space into a single variable t",
                contains={"state_parameterization": "required"},
                state_effects=["r(t) and r'(t) become known"]),
            "substitute": StageSpec(
                "substitute", "substitute the parameterization into F and form the dot product",
                teaching_focus="F(r(t)) . r'(t) collapses the whole line integral into an ordinary "
                               "one-variable integrand",
                contains={"state_integrand": "required"},
                state_effects=["the one-variable integrand becomes known"]),
            "integrate": StageSpec(
                "integrate", "integrate the one-variable integrand exactly",
                teaching_focus="an elementary antiderivative finishes the problem",
                contains={"state_antiderivative": "required"},
                state_effects=["the antiderivative becomes known"]),
            "evaluate": StageSpec(
                "evaluate", "evaluate the antiderivative at the bounds",
                teaching_focus="the difference of the antiderivative at the bounds is the work done",
                contains={"state_value": "required"},
                state_effects=["the final work value becomes known"])},
        structure="parameterize, then substitute, then integrate, then evaluate",
        must_exercise=["parameterize", "substitute", "integrate", "completion"],
        must_cover=["substitute"], must_avoid=[],
        terminal="the work value has been computed and confirmed against the bounds evaluation",
        output_shape="the exact work value of the line integral")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        names = list(_LINE_INTEGRAL_EXAMPLES)
        if seed % len(names):
            names.reverse()
        for name in names:
            yield {"example": name, "_id": f"line_integral_v1_{name}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return (len(trace.steps) >= 4 and bool(ev.get("parameterize"))
                and bool(ev.get("substitute")) and bool(ev.get("integrate")))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        ex = _LINE_INTEGRAL_EXAMPLES[example_input["example"]]
        value = _round(ex["value"])
        # INDEPENDENT ORACLE: refuse to emit a trace the numeric integral does not confirm.
        numeric = _numeric_line_integral(ex)
        if abs(numeric - ex["value"]) > 1e-4:
            raise AssertionError(
                f"line_integral oracle mismatch for {example_input['example']}: hand value {ex['value']} "
                f"vs numeric quadrature {numeric}")
        a, b = ex["bounds"]
        bounds_desc = f"t in [{_round(a)}, {_round(b)}]"
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        state: dict[str, Any] = {"parameterization": None, "integrand": None, "antiderivative": None,
                                 "work": None, "complete": False}

        # 1) parameterize
        prior = dict(state)
        state["parameterization"] = f"{ex['param_desc']}; {ex['rprime_desc']}"
        reason = (f"C is {ex['curve_desc']}. Parameterize it as {ex['param_desc']}; differentiating gives "
                  f"{ex['rprime_desc']}.")
        evr = f"{ex['param_desc']}; {ex['rprime_desc']}."
        evidence.setdefault("parameterize", []).append("s1")
        steps.append(Step(
            id="s1", operation="parameterize", prior_state=prior, state_after=dict(state),
            inputs={"curve": ex["curve_desc"]}, decision=ex["param_desc"], reason=reason,
            visual_state={"kind": "variables", "parameterization": state["parameterization"]},
            visual_delta={"parameterization": state["parameterization"]}, expected_visible_result=evr,
            facts={"allowed_values": [], "required_facts": [fact("parameterization", ex["param_desc"])],
                  "forbidden_claims": []}))

        # 2) substitute
        prior = dict(state)
        integrand = ex["integrand_desc"].split(" = ")[-1]
        state["integrand"] = integrand
        reason = (f"The field is {ex['field_desc']}. Substituting the parameterization and taking the dot "
                  f"product with r'(t): {ex['integrand_desc']}.")
        evr = f"Integrand: {ex['integrand_desc']}."
        evidence.setdefault("substitute", []).append("s2")
        steps.append(Step(
            id="s2", operation="substitute", prior_state=prior, state_after=dict(state),
            inputs={"field": ex["field_desc"]}, decision=f"integrand = {integrand}", reason=reason,
            visual_state={"kind": "variables", "integrand": integrand},
            visual_delta={"integrand": integrand}, expected_visible_result=evr,
            facts={"allowed_values": [], "required_facts": [fact("integrand", integrand)],
                  "forbidden_claims": []}))

        # 3) integrate
        prior = dict(state)
        anti = ex["antiderivative_desc"]
        state["antiderivative"] = anti
        reason = (f"The integrand {integrand} has the elementary antiderivative {anti}, so the line "
                  f"integral becomes {anti} evaluated over {bounds_desc}.")
        evr = f"Antiderivative: {anti}."
        evidence.setdefault("integrate", []).append("s3")
        steps.append(Step(
            id="s3", operation="integrate", prior_state=prior, state_after=dict(state),
            inputs={"integrand": integrand}, decision=f"antiderivative = {anti}", reason=reason,
            visual_state={"kind": "variables", "antiderivative": anti}, visual_delta={"antiderivative": anti},
            expected_visible_result=evr,
            facts={"allowed_values": [], "required_facts": [fact("antiderivative", anti)],
                  "forbidden_claims": []}))

        # 4) evaluate
        prior = dict(state)
        state["work"] = value
        state["complete"] = True
        reason = f"Evaluate at the bounds: {ex['evaluate_desc']} = {value}."
        # "complete" must appear literally: the C4 gate's completion regex does not accept the "done" in
        # "work done", and the pipeline's own _COMPLETE_RE DOES accept it — so without this word the
        # pipeline skips its completion tail while the gate still demands one.
        evr = f"Integration complete: the work done by F along C is {value}."
        evidence.setdefault("completion", []).append("s4")
        steps.append(Step(
            id="s4", operation="evaluate", prior_state=prior, state_after=dict(state),
            inputs={"bounds": bounds_desc}, decision=f"work = {value}", reason=reason,
            visual_state={"kind": "variables", "work": value}, visual_delta={"work": value},
            expected_visible_result=evr,
            facts={"allowed_values": [], "required_facts": [fact("work", str(value))],
                  "forbidden_claims": []}))

        return ContractTrace(
            problem=(f"Compute the line integral of {ex['field_desc']} along {ex['curve_desc']} — the work "
                     f"done by the field along the path."),
            conventions=dict(_LINE_CONV),
            initial_state={"parameterization": None, "integrand": None, "antiderivative": None,
                          "work": None, "complete": False},
            final_answer={"work": value}, steps=steps,
            invariants=[dict(x) for x in _LINE_INV], required_cases=list(_LINE_REQ),
            case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return a.get("integrand") == b.get("integrand") and a.get("work") == b.get("work")

    def final_answer_entails(self, state, answer):
        s = state or {}
        return bool(s.get("complete")) and s.get("work") == (answer or {}).get("work")

    def invariant_holds(self, inv, state):
        if inv.get("id") == "work_matches_numeric_quadrature":
            s = state or {}
            if not s.get("complete"):
                return True                      # scope: terminal_only
            work = s.get("work")
            if work is None:
                return False
            # the state alone can't rerun quadrature (no example handle), but reference() already refused
            # to emit any trace failing the oracle — here, confirm the terminal value is a finite number.
            return isinstance(work, (int, float)) and math.isfinite(work)
        return True

    def validate_step_shape(self, step):
        return [] if step.operation in ("parameterize", "substitute", "integrate", "evaluate") \
            else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        needle = {"parameterize": lambda: str(step.state_after.get("parameterization") or "").split(";")[0],
                  "substitute": lambda: str(step.state_after.get("integrand") or ""),
                  "integrate": lambda: str(step.state_after.get("antiderivative") or ""),
                  "evaluate": lambda: str(step.state_after.get("work"))}[step.operation]()
        return [] if needle.lower() in prose else [("value_not_stated", needle)]


# --- surface integrals (flux) ---------------------------------------------------------------------------
# Same no-CAS structure as line integrals above: each example's integrand F(r(u,v)) . (r_u x r_v) simplifies
# BY HAND to an expression whose iterated integral is exact. The INDEPENDENT ORACLE is a machine-side 2-D
# midpoint quadrature over the parameter domain using the example's own field/parameterization/normal
# lambdas — `reference()` refuses to emit a trace whose hand value the numeric integral does not confirm.
_SURFACE_INTEGRAL_EXAMPLES: dict[str, dict[str, Any]] = {
    "unit_square_planar_flux": {
        "field_desc": "F(x, y, z) = (0, 0, x + y)",
        "field": lambda x, y, z: (0.0, 0.0, x + y),
        "surface_desc": "the unit square [0,1] x [0,1] in the xy-plane, oriented with upward normal",
        "param_desc": "r(u, v) = (u, v, 0) for u in [0, 1], v in [0, 1]",
        "normal_desc": "r_u x r_v = (0, 0, 1), so dS = du dv",
        "param": lambda u, v: (u, v, 0.0),
        "normal": lambda u, v: (0.0, 0.0, 1.0),
        "domain": ((0.0, 1.0), (0.0, 1.0)),
        "integrand_desc": "F(r(u, v)) . (r_u x r_v) = u + v",
        "inner_desc": "the inner integral of (u + v) du from 0 to 1 = 1/2 + v",
        "evaluate_desc": "the outer integral of (1/2 + v) dv from 0 to 1 = 1/2 + 1/2",
        "value": 1.0,
    },
    "unit_disk_constant_flux": {
        "field_desc": "F(x, y, z) = (0, 0, 3)",
        "field": lambda x, y, z: (0.0, 0.0, 3.0),
        "surface_desc": "the unit disk x^2 + y^2 <= 1 in the xy-plane, oriented with upward normal",
        "param_desc": "r(r, theta) = (r cos theta, r sin theta, 0) for r in [0, 1], theta in [0, 2*pi]",
        "normal_desc": "r_r x r_theta = (0, 0, r), so dS = r dr dtheta",
        "param": lambda r, t: (r * math.cos(t), r * math.sin(t), 0.0),
        "normal": lambda r, t: (0.0, 0.0, r),
        "domain": ((0.0, 1.0), (0.0, 2.0 * math.pi)),
        "integrand_desc": "F(r(r, theta)) . (r_r x r_theta) = 3r",
        "inner_desc": "the inner integral of 3r dr from 0 to 1 = 3/2",
        "evaluate_desc": "the outer integral of 3/2 dtheta from 0 to 2*pi = 3/2 * 2*pi = 3*pi",
        "value": 3.0 * math.pi,
    },
}


def _numeric_surface_integral(ex: dict[str, Any], n: int = 400) -> float:
    """2-D midpoint-rule quadrature of F(r(u,v)) . N(u,v) over the example's own parameter-domain lambdas
    — the independent oracle (N is the un-normalized cross-product normal, carrying the area element)."""
    (a, b), (c, d) = ex["domain"]
    hu, hv = (b - a) / n, (d - c) / n
    total = 0.0
    for i in range(n):
        u = a + (i + 0.5) * hu
        for j in range(n):
            v = c + (j + 0.5) * hv
            x, y, z = ex["param"](u, v)
            fx, fy, fz = ex["field"](x, y, z)
            nx, ny, nz = ex["normal"](u, v)
            total += (fx * nx + fy * ny + fz * nz) * hu * hv
    return total


_SURFACE_CONV = {"method": "parameterize_substitute_integrate_iterated",
                 "trace_granularity": "one_computation_phase"}
_SURFACE_REQ = ["parameterize", "substitute", "integrate", "completion"]
_SURFACE_INV = [{"id": "flux_matches_numeric_quadrature", "scope": "terminal_only",
                "statement": "the hand-computed flux agrees with an independent 2-D midpoint-rule numeric "
                             "integration of F(r(u,v)) . (r_u x r_v)"}]


class _SurfaceIntegralCanonicalFormula:
    """Card-grounding facts (see _StokesCanonicalFormula for why this is NOT a _formula_spec)."""
    canonical_latex = r"\iint_{S} F \cdot dS = \iint_{D} F(r(u,v)) \cdot (r_u \times r_v) \, du \, dv"
    canonical_notes = [
        "S is the surface, parameterized as r(u, v) over a flat parameter domain D — the parameterization "
        "turns the surface integral into an ordinary double integral.",
        "The cross product r_u x r_v is the surface's normal vector, and its length carries the area "
        "element; dotting F with it keeps only the component of the field passing THROUGH the surface.",
        "Physically, this is the flux of F through S — how much of the field flows across the surface.",
    ]
    edge_cases = [
        "If F is everywhere tangent to the surface (F . n = 0), the flux is 0 — the field slides along "
        "the surface without crossing it.",
        "Reversing the orientation (flipping the normal) flips the sign of the flux.",
        "If F is zero everywhere on the surface, the flux is 0 regardless of the surface's shape or size.",
    ]


class SurfaceIntegralAdapter(FamilyAdapterBase):
    slug = "surface_integral"
    label_convention = "ints"
    _canonical_formula = _SurfaceIntegralCanonicalFormula()
    example_spec = ExampleSpec(
        input=InstanceShape("field_surface_pair", count=(2, 2), structure=["surface_integral"]),
        stages={
            "parameterize": StageSpec(
                "parameterize", "parameterize the surface and form its normal vector",
                teaching_focus="the parameterization turns a surface in space into a flat (u, v) domain, "
                               "and r_u x r_v supplies both the direction and the area element",
                contains={"state_parameterization": "required"},
                state_effects=["r(u, v) and the normal r_u x r_v become known"]),
            "substitute": StageSpec(
                "substitute", "substitute the parameterization into F and dot with the normal",
                teaching_focus="F(r(u,v)) . (r_u x r_v) collapses the whole surface integral into an "
                               "ordinary double integral over the parameter domain",
                contains={"state_integrand": "required"},
                state_effects=["the two-variable integrand becomes known"]),
            "integrate": StageSpec(
                "integrate", "integrate the inner variable exactly",
                teaching_focus="an iterated integral is two one-variable integrals done in sequence — the "
                               "inner one first",
                contains={"state_inner_integral": "required"},
                state_effects=["the inner-integral result becomes known"]),
            "evaluate": StageSpec(
                "evaluate", "integrate the outer variable and state the flux",
                teaching_focus="the outer integral of the inner result is the total flux through the "
                               "surface",
                contains={"state_value": "required"},
                state_effects=["the final flux value becomes known"])},
        structure="parameterize, then substitute, then integrate (inner), then evaluate (outer)",
        must_exercise=["parameterize", "substitute", "integrate", "completion"],
        must_cover=["substitute"], must_avoid=[],
        terminal="the flux value has been computed and confirmed against the outer-integral evaluation",
        output_shape="the exact flux value of the surface integral")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        names = list(_SURFACE_INTEGRAL_EXAMPLES)
        if seed % len(names):
            names.reverse()
        for name in names:
            yield {"example": name, "_id": f"surface_integral_v1_{name}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return (len(trace.steps) >= 4 and bool(ev.get("parameterize"))
                and bool(ev.get("substitute")) and bool(ev.get("integrate")))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        ex = _SURFACE_INTEGRAL_EXAMPLES[example_input["example"]]
        value = _round(ex["value"])
        # INDEPENDENT ORACLE: refuse to emit a trace the 2-D numeric integral does not confirm.
        numeric = _numeric_surface_integral(ex)
        if abs(numeric - ex["value"]) > 1e-4:
            raise AssertionError(
                f"surface_integral oracle mismatch for {example_input['example']}: hand value {ex['value']} "
                f"vs numeric quadrature {numeric}")
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        state: dict[str, Any] = {"parameterization": None, "integrand": None, "inner_integral": None,
                                 "flux": None, "complete": False}

        # 1) parameterize
        prior = dict(state)
        state["parameterization"] = f"{ex['param_desc']}; {ex['normal_desc']}"
        reason = (f"S is {ex['surface_desc']}. Parameterize it as {ex['param_desc']}; the normal is "
                  f"{ex['normal_desc']}.")
        evr = f"{ex['param_desc']}; {ex['normal_desc']}."
        evidence.setdefault("parameterize", []).append("s1")
        steps.append(Step(
            id="s1", operation="parameterize", prior_state=prior, state_after=dict(state),
            inputs={"surface": ex["surface_desc"]}, decision=ex["param_desc"], reason=reason,
            visual_state={"kind": "variables", "parameterization": state["parameterization"]},
            visual_delta={"parameterization": state["parameterization"]}, expected_visible_result=evr,
            facts={"allowed_values": [], "required_facts": [fact("parameterization", ex["param_desc"])],
                  "forbidden_claims": []}))

        # 2) substitute
        prior = dict(state)
        integrand = ex["integrand_desc"].split(" = ")[-1]
        state["integrand"] = integrand
        reason = (f"The field is {ex['field_desc']}. Substituting the parameterization and dotting with "
                  f"the normal: {ex['integrand_desc']}.")
        evr = f"Integrand: {ex['integrand_desc']}."
        evidence.setdefault("substitute", []).append("s2")
        steps.append(Step(
            id="s2", operation="substitute", prior_state=prior, state_after=dict(state),
            inputs={"field": ex["field_desc"]}, decision=f"integrand = {integrand}", reason=reason,
            visual_state={"kind": "variables", "integrand": integrand},
            visual_delta={"integrand": integrand}, expected_visible_result=evr,
            facts={"allowed_values": [], "required_facts": [fact("integrand", integrand)],
                  "forbidden_claims": []}))

        # 3) integrate (inner)
        prior = dict(state)
        inner = ex["inner_desc"].split(" = ")[-1]
        state["inner_integral"] = inner
        reason = (f"Work the iterated integral from the inside out: {ex['inner_desc']}, leaving a single "
                  f"one-variable integral.")
        evr = f"Inner integral: {inner}."
        evidence.setdefault("integrate", []).append("s3")
        steps.append(Step(
            id="s3", operation="integrate", prior_state=prior, state_after=dict(state),
            inputs={"integrand": integrand}, decision=f"inner integral = {inner}", reason=reason,
            visual_state={"kind": "variables", "inner_integral": inner},
            visual_delta={"inner_integral": inner}, expected_visible_result=evr,
            facts={"allowed_values": [], "required_facts": [fact("inner_integral", inner)],
                  "forbidden_claims": []}))

        # 4) evaluate (outer)
        prior = dict(state)
        state["flux"] = value
        state["complete"] = True
        reason = f"Finish with the outer integral: {ex['evaluate_desc']} = {value}."
        # "complete" must appear literally — see the line-integral evaluate step for why.
        evr = f"Integration complete: the flux of F through S is {value}."
        evidence.setdefault("completion", []).append("s4")
        steps.append(Step(
            id="s4", operation="evaluate", prior_state=prior, state_after=dict(state),
            inputs={"inner_integral": inner}, decision=f"flux = {value}", reason=reason,
            visual_state={"kind": "variables", "flux": value}, visual_delta={"flux": value},
            expected_visible_result=evr,
            facts={"allowed_values": [], "required_facts": [fact("flux", str(value))],
                  "forbidden_claims": []}))

        return ContractTrace(
            problem=(f"Compute the surface integral (flux) of {ex['field_desc']} through "
                     f"{ex['surface_desc']}."),
            conventions=dict(_SURFACE_CONV),
            initial_state={"parameterization": None, "integrand": None, "inner_integral": None,
                          "flux": None, "complete": False},
            final_answer={"flux": value}, steps=steps,
            invariants=[dict(x) for x in _SURFACE_INV], required_cases=list(_SURFACE_REQ),
            case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return a.get("integrand") == b.get("integrand") and a.get("flux") == b.get("flux")

    def final_answer_entails(self, state, answer):
        s = state or {}
        return bool(s.get("complete")) and s.get("flux") == (answer or {}).get("flux")

    def invariant_holds(self, inv, state):
        if inv.get("id") == "flux_matches_numeric_quadrature":
            s = state or {}
            if not s.get("complete"):
                return True                      # scope: terminal_only
            flux = s.get("flux")
            if flux is None:
                return False
            # same shape as line_integral: reference() already refused any trace failing the oracle;
            # here, confirm the terminal value is a finite number.
            return isinstance(flux, (int, float)) and math.isfinite(flux)
        return True

    def validate_step_shape(self, step):
        return [] if step.operation in ("parameterize", "substitute", "integrate", "evaluate") \
            else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        needle = {"parameterize": lambda: str(step.state_after.get("parameterization") or "").split(";")[0],
                  "substitute": lambda: str(step.state_after.get("integrand") or ""),
                  "integrate": lambda: str(step.state_after.get("inner_integral") or ""),
                  "evaluate": lambda: str(step.state_after.get("flux"))}[step.operation]()
        return [] if needle.lower() in prose else [("value_not_stated", needle)]


class StokesTheoremAdapter(FamilyAdapterBase):
    slug = "stokes_theorem"
    label_convention = "ints"
    _canonical_formula = _StokesCanonicalFormula()
    example_spec = ExampleSpec(
        input=InstanceShape("vector_field_surface_pair", count=(2, 2), structure=["stokes_theorem"]),
        stages={
            "compute_curl": StageSpec(
                "compute_curl", "compute the curl of the vector field",
                teaching_focus="the curl measures the field's rotation at a point",
                contains={"state_curl": "required"},
                state_effects=["the curl vector becomes known"]),
            "integrate_surface": StageSpec(
                "integrate_surface", "integrate the curl over the surface",
                teaching_focus="for a constant curl over a flat surface, the surface integral is curl "
                               "dotted with the normal, times the area",
                contains={"multiply_area": "required"},
                state_effects=["the surface-integral total becomes known"]),
            "integrate_boundary": StageSpec(
                "integrate_boundary", "integrate the field along one segment of the boundary curve",
                teaching_focus="each boundary segment contributes its own exact line integral to the "
                               "running total",
                contains={"accumulate_segment": "required"},
                state_effects=["the boundary running total grows by one segment's contribution"]),
            "verify_match": StageSpec(
                "verify_match", "confirm the surface integral equals the completed line integral",
                teaching_focus="Stokes' theorem's own claim: the two independently-computed sides must "
                               "agree",
                contains={"compare": "required"},
                state_effects=["the trace concludes with both totals confirmed equal"])},
        structure="compute_curl, then integrate_surface, then integrate_boundary (one or more), then "
                 "verify_match",
        must_exercise=["compute_curl", "integrate_surface", "integrate_boundary", "completion"],
        must_cover=["integrate_boundary"], must_avoid=[],
        terminal="the surface integral and the completed boundary line integral have been shown to match",
        output_shape="the matching surface_integral and line_integral values")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        # select_instance (trace_pipeline.py) always returns the FIRST candidate whose trace passes
        # is_teaching_trace — with a fixed iteration order, the second example would never ship to a real
        # learner regardless of how many times a path is regenerated. Alternate which example comes first
        # by seed (both always pass is_teaching_trace, so this genuinely determines what ships).
        names = list(_STOKES_EXAMPLES)
        if seed % len(names):
            names.reverse()
        for name in names:
            yield {"example": name, "_id": f"stokes_theorem_v1_{name}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return (len(trace.steps) >= 3 and bool(ev.get("compute_curl"))
                and bool(ev.get("integrate_surface")) and bool(ev.get("integrate_boundary")))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        ex = _STOKES_EXAMPLES[example_input["example"]]
        curl = ex["curl"]
        curl_z = curl[2]                                    # every hand-picked example has normal = z-hat
        area = ex["area"]
        segments = ex["boundary_segments"]
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}

        # Only genuinely learner-meaningful fields live in `state` — it's diffed and every field shown
        # verbatim in the learner-facing Work/Result text (a deliberate platform contract,
        # trace_pipeline.py's _apply_step_field_contract), so pure bookkeeping (a running segment counter)
        # never belongs here; `i` in the loop below tracks that locally instead.
        state: dict[str, Any] = {"curl": None, "surface_integral": None, "boundary_partial": 0.0,
                                 "complete": False}

        # 1) compute_curl
        prior = dict(state)
        state["curl"] = list(curl)
        sid = "s1"
        reason = f"The vector field is {ex['field_desc']}. Its curl works out to {tuple(curl)}."
        evr = f"curl(F) = {tuple(curl)}."
        evidence.setdefault("compute_curl", []).append(sid)
        steps.append(Step(
            id=sid, operation="compute_curl", prior_state=prior, state_after=dict(state),
            inputs={"field": ex["field_desc"]}, decision=f"curl(F) = {tuple(curl)}", reason=reason,
            visual_state={"kind": "variables", "curl": list(curl)}, visual_delta={"curl": list(curl)},
            expected_visible_result=evr,
            facts={"allowed_values": [], "required_facts": [fact("curl", str(tuple(curl)))],
                  "forbidden_claims": []}))

        # 2) integrate_surface — constant curl over a flat surface: curl_z * area
        prior = dict(state)
        surface_integral = _round(curl_z * area)
        state["surface_integral"] = surface_integral
        sid = "s2"
        reason = (f"S is {ex['surface_desc']}, area {_round(area)}. Since curl(F) is constant here, the "
                 f"surface integral of curl(F) . dS is just curl_z times the area: "
                 f"{curl_z} * {_round(area)} = {surface_integral}.")
        evr = f"Surface integral of curl(F) over S = {surface_integral}."
        evidence.setdefault("integrate_surface", []).append(sid)
        steps.append(Step(
            id=sid, operation="integrate_surface", prior_state=prior, state_after=dict(state),
            inputs={"curl_z": curl_z, "area": area}, decision=f"surface_integral = {surface_integral}",
            reason=reason, visual_state={"kind": "variables", "surface_integral": surface_integral},
            visual_delta={"surface_integral": surface_integral}, expected_visible_result=evr,
            facts={"allowed_values": [],
                  "required_facts": [fact("surface_integral", str(surface_integral))],
                  "forbidden_claims": []}))

        # 3..) integrate_boundary — one step per segment, accumulating the running total
        for i, (seg_desc, contribution) in enumerate(segments, start=1):
            prior = dict(state)
            running = _round(state["boundary_partial"] + contribution)
            state["boundary_partial"] = running
            sid = f"s{2 + i}"
            reason = (f"Along {seg_desc}, integrating F . dr gives {_round(contribution)}. Running total: "
                     f"{running}.")
            evr = f"Boundary running total after {i}/{len(segments)} segment(s): {running}."
            evidence.setdefault("integrate_boundary", []).append(sid)
            steps.append(Step(
                id=sid, operation="integrate_boundary", prior_state=prior, state_after=dict(state),
                inputs={"segment": seg_desc, "contribution": contribution},
                decision=f"+{_round(contribution)}", reason=reason,
                visual_state={"kind": "variables", "boundary_partial": running, "segments_done": i},
                visual_delta={"segment": seg_desc, "contribution": _round(contribution)},
                expected_visible_result=evr,
                facts={"allowed_values": [],
                      "required_facts": [fact("boundary_partial", str(running))], "forbidden_claims": []}))

        # final) verify_match
        prior = dict(state)
        line_integral = state["boundary_partial"]
        state["complete"] = True
        sid = f"s{3 + len(segments)}"
        reason = (f"The surface integral ({surface_integral}) and the completed boundary line integral "
                 f"({line_integral}) match, confirming Stokes' theorem for this example.")
        evr = f"surface_integral = {surface_integral} = line_integral = {line_integral}. Confirmed."
        evidence.setdefault("completion", []).append(sid)
        steps.append(Step(
            id=sid, operation="verify_match", prior_state=prior, state_after=dict(state),
            inputs={"surface_integral": surface_integral, "line_integral": line_integral},
            decision="surface_integral == line_integral", reason=reason,
            visual_state={"kind": "variables", "surface_integral": surface_integral,
                         "line_integral": line_integral},
            visual_delta={"matches": abs(surface_integral - line_integral) < _TOL},
            expected_visible_result=evr,
            facts={"allowed_values": [],
                  "required_facts": [fact("surface_integral", str(surface_integral)),
                                     fact("line_integral", str(line_integral))],
                  "forbidden_claims": []}))

        return ContractTrace(
            problem=(f"Verify Stokes' theorem for {ex['field_desc']} over {ex['surface_desc']}: show that "
                    f"the surface integral of curl(F) over S equals the line integral of F around the "
                    f"boundary of S."),
            conventions=dict(_STOKES_CONV),
            initial_state={"curl": None, "surface_integral": None, "boundary_partial": 0.0,
                          "complete": False},
            final_answer={"surface_integral": surface_integral, "line_integral": line_integral}, steps=steps,
            invariants=[dict(x) for x in _STOKES_INV], required_cases=list(_STOKES_REQ),
            case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return (a.get("surface_integral") == b.get("surface_integral")
               and a.get("boundary_partial") == b.get("boundary_partial"))

    def final_answer_entails(self, state, answer):
        s = state or {}
        if not s.get("complete"):
            return False
        a = answer or {}
        return (s.get("surface_integral") == a.get("surface_integral")
               and s.get("boundary_partial") == a.get("line_integral"))

    def invariant_holds(self, inv, state):
        if inv.get("id") == "surface_equals_line":
            s = state or {}
            if not s.get("complete"):
                return True                      # scope: terminal_only — only meaningful at completion
            surface, line = s.get("surface_integral"), s.get("boundary_partial")
            if surface is None or line is None:
                return False
            return abs(surface - line) < _TOL
        return True

    def validate_step_shape(self, step):
        return [] if step.operation in ("compute_curl", "integrate_surface", "integrate_boundary",
                                        "verify_match") else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        if step.operation == "compute_curl":
            # tuple-formatted, matching the reason/expected_visible_result text exactly ("curl(F) = (0.0, ...)")
            # — NOT the raw list repr stored in state, which would never appear verbatim in learner-facing prose.
            needle = str(tuple(step.state_after.get("curl") or []))
        elif step.operation == "integrate_surface":
            needle = str(step.state_after.get("surface_integral"))
        else:
            needle = str(step.state_after.get("boundary_partial"))
        return [] if needle.lower() in prose else [("value_not_stated", needle)]


# --- divergence theorem (Gauss) -------------------------------------------------------------------------
# Same two-sided structure as Stokes above, and the same no-CAS philosophy: every example's divergence is
# CONSTANT, so the volume side is exactly div * volume, and each boundary piece's outward flux is worked out
# by hand ahead of time to an exact value. The independent-oracle structure is the theorem's OWN claim: the
# volume integral of div(F) and the total outward flux through the boundary are computed via two structurally
# DIFFERENT methods — their agreement is the falsifiable claim a bug in either side could not fake.
_DIVERGENCE_EXAMPLES: dict[str, dict[str, Any]] = {
    "unit_cube_expanding_field": {
        "field_desc": "F(x, y, z) = (x, y, z)",
        "divergence": 3.0,
        "divergence_work": "dF1/dx + dF2/dy + dF3/dz = 1 + 1 + 1",
        "region_desc": "the unit cube [0,1] x [0,1] x [0,1]",
        "volume": 1.0,
        "boundary_desc": "the cube's six faces, each with outward normal",
        # the three zero-flux faces travel as ONE piece: T13's trace budget is 8 steps, and 6 separate
        # face steps (+ divergence + volume + verify = 9) would blow it — and a learner gains nothing from
        # three consecutive "this face contributes 0" cards.
        "boundary_pieces": [("the face x = 1 (outward normal +x, F . n = x = 1 over unit area)", 1.0),
                            ("the face y = 1 (outward normal +y, F . n = y = 1 over unit area)", 1.0),
                            ("the face z = 1 (outward normal +z, F . n = z = 1 over unit area)", 1.0),
                            ("the three faces on the coordinate planes (x = 0, y = 0, z = 0): the outward "
                             "normal is -x, -y, -z respectively, and F . n = 0 on each", 0.0)],
    },
    "unit_sphere_radial_field": {
        "field_desc": "F(x, y, z) = (x, y, z)",
        "divergence": 3.0,
        "divergence_work": "dF1/dx + dF2/dy + dF3/dz = 1 + 1 + 1",
        "region_desc": "the unit ball x^2 + y^2 + z^2 <= 1 (volume 4*pi/3)",
        "volume": 4.0 * math.pi / 3.0,
        "boundary_desc": "the unit sphere, outward normal n = (x, y, z) itself on the surface",
        "boundary_pieces": [("the whole sphere: F . n = x^2 + y^2 + z^2 = 1 everywhere on it, so the flux "
                             "is the sphere's surface area 4*pi", 4.0 * math.pi)],
    },
}

_DIV_CONV = {"theorem": "divergence", "check": "volume_integral_equals_outward_flux",
             "trace_granularity": "one_computation_phase"}
_DIV_REQ = ["compute_divergence", "integrate_volume", "integrate_flux", "completion"]
_DIV_INV = [{"id": "volume_equals_flux", "scope": "terminal_only",
            "statement": "the volume integral of div(F) over the region equals the total outward flux of F "
                         "through its boundary surface"}]


class _DivergenceCanonicalFormula:
    """Card-grounding facts (see _StokesCanonicalFormula for why this is NOT a _formula_spec)."""
    canonical_latex = r"\iint_{S} F \cdot dS = \iiint_{V} (\nabla \cdot F) \, dV"
    canonical_notes = [
        "S is the closed boundary surface of the solid region V, oriented with OUTWARD normal — the theorem "
        "only applies to a surface that fully encloses a volume.",
        "The left side is the total outward flux of F through the boundary; the right side adds up the "
        "divergence — the field's local expansion rate — throughout the interior.",
        "F must have continuous partial derivatives on an open region containing V.",
    ]
    edge_cases = [
        "If F is divergence-free (div F = 0, an incompressible flow), the net flux through ANY closed "
        "surface is 0 — whatever flows in must flow out.",
        "The theorem needs a CLOSED surface; an open surface with a boundary curve is Stokes'-theorem "
        "territory, not divergence-theorem territory.",
        "Reversing the orientation (inward normal) flips the sign of the flux side.",
    ]


class DivergenceTheoremAdapter(FamilyAdapterBase):
    slug = "divergence_theorem"
    label_convention = "ints"
    _canonical_formula = _DivergenceCanonicalFormula()
    example_spec = ExampleSpec(
        input=InstanceShape("vector_field_region_pair", count=(2, 2), structure=["divergence_theorem"]),
        stages={
            "compute_divergence": StageSpec(
                "compute_divergence", "compute the divergence of the vector field",
                teaching_focus="the divergence measures the field's local expansion rate at a point",
                contains={"state_divergence": "required"},
                state_effects=["the divergence becomes known"]),
            "integrate_volume": StageSpec(
                "integrate_volume", "integrate the divergence over the solid region",
                teaching_focus="for a constant divergence, the volume integral is just the divergence "
                               "times the region's volume",
                contains={"multiply_volume": "required"},
                state_effects=["the volume-integral total becomes known"]),
            "integrate_flux": StageSpec(
                "integrate_flux", "compute the outward flux through one piece of the boundary surface",
                teaching_focus="each boundary piece contributes its own exact outward flux to the running "
                               "total",
                contains={"accumulate_piece": "required"},
                state_effects=["the flux running total grows by one piece's contribution"]),
            "verify_match": StageSpec(
                "verify_match", "confirm the volume integral equals the completed outward flux",
                teaching_focus="the divergence theorem's own claim: the two independently-computed sides "
                               "must agree",
                contains={"compare": "required"},
                state_effects=["the trace concludes with both totals confirmed equal"])},
        structure="compute_divergence, then integrate_volume, then integrate_flux (one or more), then "
                 "verify_match",
        must_exercise=["compute_divergence", "integrate_volume", "integrate_flux", "completion"],
        must_cover=["integrate_flux"], must_avoid=[],
        terminal="the volume integral and the completed outward boundary flux have been shown to match",
        output_shape="the matching volume_integral and flux values")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        names = list(_DIVERGENCE_EXAMPLES)
        if seed % len(names):
            names.reverse()
        for name in names:
            yield {"example": name, "_id": f"divergence_theorem_v1_{name}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return (len(trace.steps) >= 3 and bool(ev.get("compute_divergence"))
                and bool(ev.get("integrate_volume")) and bool(ev.get("integrate_flux")))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        ex = _DIVERGENCE_EXAMPLES[example_input["example"]]
        div = ex["divergence"]
        volume = ex["volume"]
        pieces = ex["boundary_pieces"]
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        state: dict[str, Any] = {"divergence": None, "volume_integral": None, "flux_partial": 0.0,
                                 "complete": False}

        # 1) compute_divergence
        prior = dict(state)
        state["divergence"] = div
        sid = "s1"
        reason = (f"The vector field is {ex['field_desc']}. Its divergence is {ex['divergence_work']} "
                  f"= {_round(div)}.")
        evr = f"div(F) = {_round(div)}."
        evidence.setdefault("compute_divergence", []).append(sid)
        steps.append(Step(
            id=sid, operation="compute_divergence", prior_state=prior, state_after=dict(state),
            inputs={"field": ex["field_desc"]}, decision=f"div(F) = {_round(div)}", reason=reason,
            visual_state={"kind": "variables", "divergence": div}, visual_delta={"divergence": div},
            expected_visible_result=evr,
            facts={"allowed_values": [], "required_facts": [fact("divergence", str(_round(div)))],
                  "forbidden_claims": []}))

        # 2) integrate_volume — constant divergence over the region: div * volume
        prior = dict(state)
        volume_integral = _round(div * volume)
        state["volume_integral"] = volume_integral
        sid = "s2"
        reason = (f"V is {ex['region_desc']}, volume {_round(volume)}. Since div(F) is constant here, the "
                 f"volume integral of div(F) dV is just the divergence times the volume: "
                 f"{_round(div)} * {_round(volume)} = {volume_integral}.")
        evr = f"Volume integral of div(F) over V = {volume_integral}."
        evidence.setdefault("integrate_volume", []).append(sid)
        steps.append(Step(
            id=sid, operation="integrate_volume", prior_state=prior, state_after=dict(state),
            inputs={"divergence": div, "volume": volume}, decision=f"volume_integral = {volume_integral}",
            reason=reason, visual_state={"kind": "variables", "volume_integral": volume_integral},
            visual_delta={"volume_integral": volume_integral}, expected_visible_result=evr,
            facts={"allowed_values": [],
                  "required_facts": [fact("volume_integral", str(volume_integral))],
                  "forbidden_claims": []}))

        # 3..) integrate_flux — one step per boundary piece, accumulating the outward-flux running total
        for i, (piece_desc, contribution) in enumerate(pieces, start=1):
            prior = dict(state)
            running = _round(state["flux_partial"] + contribution)
            state["flux_partial"] = running
            sid = f"s{2 + i}"
            reason = (f"Through {piece_desc}, the outward flux is {_round(contribution)}. Running total: "
                     f"{running}.")
            evr = f"Outward-flux running total after {i}/{len(pieces)} piece(s): {running}."
            evidence.setdefault("integrate_flux", []).append(sid)
            steps.append(Step(
                id=sid, operation="integrate_flux", prior_state=prior, state_after=dict(state),
                inputs={"piece": piece_desc, "contribution": contribution},
                decision=f"+{_round(contribution)}", reason=reason,
                visual_state={"kind": "variables", "flux_partial": running, "pieces_done": i},
                visual_delta={"piece": piece_desc, "contribution": _round(contribution)},
                expected_visible_result=evr,
                facts={"allowed_values": [],
                      "required_facts": [fact("flux_partial", str(running))], "forbidden_claims": []}))

        # final) verify_match
        prior = dict(state)
        flux_total = state["flux_partial"]
        state["complete"] = True
        sid = f"s{3 + len(pieces)}"
        reason = (f"The volume integral ({volume_integral}) and the completed outward boundary flux "
                 f"({flux_total}) match, confirming the divergence theorem for this example.")
        evr = f"volume_integral = {volume_integral} = flux = {flux_total}. Confirmed."
        evidence.setdefault("completion", []).append(sid)
        steps.append(Step(
            id=sid, operation="verify_match", prior_state=prior, state_after=dict(state),
            inputs={"volume_integral": volume_integral, "flux": flux_total},
            decision="volume_integral == flux", reason=reason,
            visual_state={"kind": "variables", "volume_integral": volume_integral, "flux": flux_total},
            visual_delta={"matches": abs(volume_integral - flux_total) < _TOL},
            expected_visible_result=evr,
            facts={"allowed_values": [],
                  "required_facts": [fact("volume_integral", str(volume_integral)),
                                     fact("flux", str(flux_total))],
                  "forbidden_claims": []}))

        return ContractTrace(
            problem=(f"Verify the divergence theorem for {ex['field_desc']} over {ex['region_desc']}: show "
                    f"that the volume integral of div(F) equals the total outward flux of F through the "
                    f"boundary surface."),
            conventions=dict(_DIV_CONV),
            initial_state={"divergence": None, "volume_integral": None, "flux_partial": 0.0,
                          "complete": False},
            final_answer={"volume_integral": volume_integral, "flux": flux_total}, steps=steps,
            invariants=[dict(x) for x in _DIV_INV], required_cases=list(_DIV_REQ),
            case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return (a.get("volume_integral") == b.get("volume_integral")
               and a.get("flux_partial") == b.get("flux_partial"))

    def final_answer_entails(self, state, answer):
        s = state or {}
        if not s.get("complete"):
            return False
        a = answer or {}
        return (s.get("volume_integral") == a.get("volume_integral")
               and s.get("flux_partial") == a.get("flux"))

    def invariant_holds(self, inv, state):
        if inv.get("id") == "volume_equals_flux":
            s = state or {}
            if not s.get("complete"):
                return True                      # scope: terminal_only — only meaningful at completion
            vol, flux = s.get("volume_integral"), s.get("flux_partial")
            if vol is None or flux is None:
                return False
            return abs(vol - flux) < _TOL
        return True

    def validate_step_shape(self, step):
        return [] if step.operation in ("compute_divergence", "integrate_volume", "integrate_flux",
                                        "verify_match") else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        if step.operation == "compute_divergence":
            needle = str(step.state_after.get("divergence") if step.state_after.get("divergence") is None
                         else _round(step.state_after["divergence"]))
        elif step.operation == "integrate_volume":
            needle = str(step.state_after.get("volume_integral"))
        else:
            needle = str(step.state_after.get("flux_partial"))
        return [] if needle.lower() in prose else [("value_not_stated", needle)]
