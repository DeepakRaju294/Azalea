"""Program-execution family (WORKED_EXAMPLE_ACCURACY_SPEC §15.3) — the T12 shape: TRACE a running program,
one card per step, showing how the variables (the "memory") change. The learner follows the machine, not a
mathematical structure.

First member: Euclid's GCD loop (`while b: a, b = b, a % b`). Correctness is refereed by an INDEPENDENT
oracle — the gcd is invariant across every step and equals math.gcd — so a wrong reduction can't pass.
"""
from __future__ import annotations

import math
import random
import re
from typing import Any, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase


_GCD_CONV = {"program": "euclid_gcd", "loop": "while b != 0: a, b = b, a % b",
             "invariant": "gcd(a, b) is unchanged every step", "trace_granularity": "one_loop_iteration"}
_GCD_REQ = ["reduce", "loop_ends", "completion"]
_GCD_INV = [{"id": "gcd_preserved", "scope": "every_step",
             "statement": "gcd(a, b) equals the answer at every step (the loop never changes it)"}]


class EuclidGCDAdapter(FamilyAdapterBase):
    slug = "euclid_gcd"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(2, 2), value_range=(2, 90), structure=["gcd_pair"]),
        stages={"iterate": StageSpec(
            "iterate", "run one loop iteration: replace (a, b) with (b, a mod b)",
            teaching_focus="each iteration shrinks b via the remainder; the loop ends when b hits 0",
            contains={"compute_remainder": "internal", "update_variables": "required"},
            state_effects=["a and b take their next values; when b becomes 0 the current a is the gcd"])},
        structure="iterate+ until b == 0",
        must_exercise=["reduce", "loop_ends", "completion"], must_cover=["reduce"],
        must_avoid=["already_zero"],
        terminal="b reaches zero, so the loop stops and the current a is the greatest common divisor",
        output_shape="the greatest common divisor")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            a = rng.randint(20, 90)
            b = rng.randint(6, a - 1)
            yield {"a": a, "b": b, "_id": f"euclid_gcd_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) >= 2 and bool(ev.get("reduce")) and bool(ev.get("loop_ends"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        a0, b0 = int(example_input["a"]), int(example_input["b"])
        target = math.gcd(a0, b0)
        a, b = a0, b0
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        idx = 0
        while b != 0:
            idx += 1
            sid = f"s{idx}"
            r = a % b
            prior = {"a": a, "b": b, "gcd_target": target}
            reason = (f"b = {b} is not zero, so run the loop: set a, b = b, a mod b. Here a mod b = "
                      f"{a} mod {b} = {r}, so a becomes {b} and b becomes {r}.")
            na, nb = b, r
            if nb == 0:
                evr = f"a = {na}, b = 0; the loop ends, so the gcd is {na}."
                evidence.setdefault("loop_ends", []).append(sid)
            else:
                evr = f"a = {na}, b = {nb}; the loop continues."
            a, b = na, nb
            after = {"a": a, "b": b, "gcd_target": target}
            evidence.setdefault("reduce", []).append(sid)
            allowed = sorted({int(x) for x in re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation="iterate", prior_state=prior, state_after=after,
                inputs={"a_before": prior["a"], "b_before": prior["b"], "remainder": r},
                decision=f"a, b = {prior['b']}, {r}", reason=reason,
                visual_state={"kind": "variables", "a": a, "b": b}, visual_delta={"a": a, "b": b},
                expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": [fact("remainder", r)],
                       "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Trace gcd({a0}, {b0}) with the Euclidean algorithm: while b != 0, replace (a, b) with "
                     f"(b, a mod b). Give the greatest common divisor."),
            conventions=dict(_GCD_CONV), initial_state={"a": a0, "b": b0, "gcd_target": target},
            final_answer={"gcd": target}, steps=steps,
            invariants=[dict(x) for x in _GCD_INV], required_cases=list(_GCD_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return a.get("a") == b.get("a") and a.get("b") == b.get("b")

    def final_answer_entails(self, state, answer):
        # the loop terminates with b == 0 and a == gcd
        return (state or {}).get("b") == 0 and (state or {}).get("a") == (answer or {}).get("gcd")

    def invariant_holds(self, inv, state):
        if inv.get("id") == "gcd_preserved":
            a, b = (state or {}).get("a"), (state or {}).get("b")
            if a is None or b is None:
                return True
            return math.gcd(int(a), int(b)) == (state or {}).get("gcd_target")   # independent oracle
        return True

    def validate_step_shape(self, step):
        return [] if step.operation == "iterate" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        rv = str(step.inputs["remainder"])
        return [] if rv in prose else [("remainder_not_stated", rv)]
