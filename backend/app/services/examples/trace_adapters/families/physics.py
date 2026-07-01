"""Physics family (ADAPTER_CATALOG B5) — quantitative science worked examples. Members here: kinematics with
constant acceleration. Future: projectile motion, Newton's second law, energy/momentum, Ohm's law, gas laws.

TEMPLATE — this is the reference *science* adapter every new science concept follows. Like the math template
it is a NON-coding computation (no code), with the same contract (ExampleSpec · verified `reference()` trace ·
required cases · structured facts). The science-specific shape is: known quantities WITH UNITS -> apply the
governing equation(s) -> the result WITH UNITS. The verified `reference()` computes the real physics, so the
worked example can never state a wrong number or unit."""
from __future__ import annotations

import random
import re
from typing import Any, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase

_CONV = {"model": "constant (uniform) acceleration", "units": "SI (m, s, m/s, m/s^2)",
         "v_equation": "v = u + a*t", "s_equation": "s = u*t + (a*t^2)/2", "sign": "positive = direction of motion"}
_REQUIRED = ["identify_knowns", "compute_final_velocity", "compute_displacement", "completion"]
_INV = [{"id": "consistent_units", "scope": "every_step", "statement": "quantities carry SI units"},
        {"id": "kinematics_hold", "scope": "final_only", "statement": "v = u + a*t and s = u*t + a*t^2/2"}]


def _ints(*parts: Any) -> list[int]:
    """Integers appearing in a step's OWN verified prose -> `allowed_values` (faithful card passes; an invented
    number is caught). Shared computation-adapter pattern."""
    found: set[int] = set()
    for m in re.findall(r"-?\d+", " ".join(str(p) for p in parts)):
        found.add(int(m))
        found.add(abs(int(m)))
    return sorted(found)


def _num(x: float) -> Any:
    return int(x) if float(x).is_integer() else round(x, 2)


class KinematicsAdapter(FamilyAdapterBase):
    slug = "kinematics"
    label_convention = "ints"                  # §2.3 — quantities are integer SI values
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(3, 3), value_range=(0, 12),
                            structure=["u_initial", "a_constant", "t_positive"]),
        stages={
            "identify_knowns": StageSpec(
                "identify_knowns", "list the given quantities with units", cardinality="exactly_once",
                teaching_focus="separate knowns (u, a, t) from unknowns (v, s)",
                contains={"read_quantities": "required"}, state_effects=["u, a, t are named with units"]),
            "compute_final_velocity": StageSpec(
                "compute_final_velocity", "apply v = u + a*t", cardinality="exactly_once",
                teaching_focus="the first kinematic equation gives final velocity",
                contains={"substitute": "required", "evaluate": "required"}, state_effects=["v is known"]),
            "compute_displacement": StageSpec(
                "compute_displacement", "apply s = u*t + (a*t^2)/2", cardinality="exactly_once",
                teaching_focus="the second kinematic equation gives displacement",
                contains={"substitute": "required", "evaluate": "required"}, state_effects=["s is known"])},
        structure="identify_knowns compute_final_velocity compute_displacement",
        must_exercise=["identify_knowns", "compute_final_velocity", "compute_displacement", "completion"],
        must_cover=["zero_initial_velocity", "nonzero_initial_velocity"],
        must_avoid=["zero_time"],
        terminal="final velocity and displacement are stated with units", output_shape="v (m/s) and s (m)")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            u = rng.randint(0, 10)
            a = rng.randint(1, 6)
            t = rng.randint(1, 6)
            yield {"u": u, "a": a, "t": t, "_id": f"kinematics_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) == 3 and bool(ev.get("compute_final_velocity")) and bool(ev.get("compute_displacement"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        u, a, t = example_input["u"], example_input["a"], example_input["t"]
        v = _num(u + a * t)
        s = _num(u * t + (a * t * t) / 2)
        st_known = {"u": u, "a": a, "t": t}
        st_v = {**st_known, "v": v}
        st_s = {**st_v, "s": s}

        d1 = f"u = {u} m/s, a = {a} m/s^2, t = {t} s"
        r1 = f"the object starts at u = {u} m/s, accelerates at a = {a} m/s^2 for t = {t} s"
        e1 = f"Knowns: u = {u} m/s, a = {a} m/s^2, t = {t} s."
        f1 = [fact("known", f"u = {u}"), fact("known", f"a = {a}"), fact("known", f"t = {t}")]
        d2 = f"v = {v} m/s"
        r2 = f"v = u + a*t = {u} + {a}*{t} = {v} m/s"
        e2 = f"Final velocity v = u + a*t = {u} + {a}*{t} = {v} m/s."
        f2 = [fact("final_velocity", f"v = {v}")]
        d3 = f"s = {s} m"
        r3 = f"s = u*t + (a*t^2)/2 = {u}*{t} + ({a}*{t}^2)/2 = {s} m"
        e3 = f"Displacement s = u*t + (a*t^2)/2 = {s} m."
        f3 = [fact("displacement", f"s = {s}")]

        steps = [
            Step(id="s1", operation="identify_knowns", prior_state={"problem": "constant acceleration"},
                 state_after=dict(st_known), inputs={"u": u, "a": a, "t": t}, decision=d1, reason=r1,
                 visual_state={"kind": "equation", "u": u, "a": a, "t": t}, expected_visible_result=e1,
                 facts={"allowed_values": _ints(d1, r1, e1, *(x["text"] for x in f1)),
                        "required_facts": f1, "forbidden_claims": []}),
            Step(id="s2", operation="compute_final_velocity", prior_state=dict(st_known),
                 state_after=dict(st_v), inputs={"v": v}, decision=d2, reason=r2,
                 visual_state={"kind": "equation", "v": v}, expected_visible_result=e2,
                 facts={"allowed_values": _ints(d2, r2, e2, *(x["text"] for x in f2)),
                        "required_facts": f2, "forbidden_claims": []}),
            Step(id="s3", operation="compute_displacement", prior_state=dict(st_v),
                 state_after=dict(st_s), inputs={"s": s}, decision=d3, reason=r3,
                 visual_state={"kind": "equation", "s": s}, expected_visible_result=e3,
                 # the LAST step's allowed set also covers the final-answer values (v, s) — the completion
                 # suffix restates the full answer {v, s}, and v was computed a step earlier.
                 facts={"allowed_values": _ints(d3, r3, e3, v, s, *(x["text"] for x in f3)),
                        "required_facts": f3, "forbidden_claims": []}),
        ]
        case = "zero_initial_velocity" if u == 0 else "nonzero_initial_velocity"
        evidence = {"identify_knowns": ["s1"], "compute_final_velocity": ["s2"],
                    "compute_displacement": ["s3"], "completion": ["s3"], case: ["s1"]}
        return ContractTrace(
            problem=(f"An object moving at u = {u} m/s accelerates uniformly at a = {a} m/s^2 for t = {t} s. "
                     f"Find its final velocity and displacement."),
            conventions=dict(_CONV), initial_state={"problem": "constant acceleration"},
            final_answer={"v": v, "s": s}, steps=steps,
            invariants=[dict(x) for x in _INV], required_cases=list(_REQUIRED), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        ka, kb = a or {}, b or {}
        return all(str(ka.get(k)) == str(kb.get(k)) for k in (set(ka) | set(kb)))

    def final_answer_entails(self, state, answer):
        st, an = state or {}, answer or {}
        return str(st.get("v")) == str(an.get("v")) and str(st.get("s")) == str(an.get("s"))

    def invariant_holds(self, inv, state):
        if inv.get("id") != "kinematics_hold":
            return True
        u, a, t, v, s = (state or {}).get("u"), state.get("a"), state.get("t"), state.get("v"), state.get("s")
        if None in (u, a, t, v, s):
            return True
        return abs(v - (u + a * t)) < 1e-6 and abs(s - (u * t + (a * t * t) / 2)) < 1e-6

    def validate_step_shape(self, step):
        allowed = {"identify_knowns", "compute_final_velocity", "compute_displacement"}
        return [] if step.operation in allowed else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        if step.operation == "compute_final_velocity":
            return [] if str(step.inputs["v"]) in prose else [("velocity_not_stated", str(step.inputs["v"]))]
        if step.operation == "compute_displacement":
            return [] if str(step.inputs["s"]) in prose else [("displacement_not_stated", str(step.inputs["s"]))]
        return []
