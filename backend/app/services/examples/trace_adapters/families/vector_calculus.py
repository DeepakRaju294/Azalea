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
