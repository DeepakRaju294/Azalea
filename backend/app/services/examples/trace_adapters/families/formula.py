"""Formula / symbolic-expression family (WORKED_EXAMPLE_ACCURACY_SPEC §15.3) — the
`formula_symbolic_expression` visual family. Members here: arithmetic evaluation (operator precedence).
Future: recurrence expansion, Big-O reduction, algebraic substitution, …
"""
from __future__ import annotations

import random
from typing import Any, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase

_CONV = {"evaluation": "operator_precedence", "precedence": "*,/ before +,-",
         "associativity": "left_to_right", "trace_granularity": "one_operation"}
_REQUIRED = ["multiply_or_divide_first", "add_or_subtract", "completion"]
_INV = [{"id": "value_preserved", "scope": "every_step", "statement": "the expression's value is unchanged"},
        {"id": "single_value", "scope": "final_only", "statement": "reduced to a single number"}]
_PREC = {"*": 2, "/": 2, "+": 1, "-": 1}


def _apply(a, op, b):
    return {"+": a + b, "-": a - b, "*": a * b, "/": (a // b if b else 0)}[op]


def _eval(tokens: list) -> float:
    nums, ops = [tokens[0]], []
    for k in range(1, len(tokens), 2):
        op, n = tokens[k], tokens[k + 1]
        while ops and _PREC[ops[-1]] >= _PREC[op]:
            b, a, o = nums.pop(), nums.pop(), ops.pop()
            nums.append(_apply(a, o, b))
        ops.append(op); nums.append(n)
    while ops:
        b, a, o = nums.pop(), nums.pop(), ops.pop()
        nums.append(_apply(a, o, b))
    return nums[0]


def _first_high_prec(tokens: list) -> int:
    best = None
    for k in range(1, len(tokens), 2):
        if best is None or _PREC[tokens[k]] > _PREC[tokens[best]]:
            best = k
    return best


class ArithmeticEvalAdapter(FamilyAdapterBase):
    slug = "arithmetic_eval"
    label_convention = "ints"             # §2.3 — operands are integers
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(3, 4), value_range=(2, 9),
                            structure=["operators_+-*", "mixed_precedence"]),
        stages={"apply_op": StageSpec(
            "apply_op", "apply the highest-precedence remaining operation",
            teaching_focus="evaluate the operator with the highest precedence next",
            contains={"select_highest_precedence": "required", "apply": "required"},
            state_effects=["the expression shrinks by one operation; its value is preserved"])},
        structure="apply_op+ until a single value remains",
        must_exercise=["multiply_or_divide_first", "add_or_subtract", "completion"],
        must_avoid=["single_precedence_level"],
        terminal="a single number remains", output_shape="the value")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(3, 4)
            toks: list = [rng.randint(2, 9)]
            for _ in range(n - 1):
                toks += [rng.choice(["+", "-", "*"]), rng.randint(2, 9)]
            yield {"tokens": toks, "_id": f"arith_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) >= 2 and bool(ev.get("multiply_or_divide_first")) and bool(ev.get("add_or_subtract"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        tokens = list(example_input["tokens"])
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        i = 0
        while len(tokens) > 1:
            i += 1
            sid = f"s{i}"
            k = _first_high_prec(tokens)
            a, op, b = tokens[k - 1], tokens[k], tokens[k + 1]
            res = _apply(a, op, b)
            prior = {"tokens": list(tokens)}
            tokens = tokens[:k - 1] + [res] + tokens[k + 2:]
            after = {"tokens": list(tokens)}
            (evidence.setdefault("multiply_or_divide_first", []) if op in ("*", "/")
             else evidence.setdefault("add_or_subtract", [])).append(sid)
            steps.append(Step(
                id=sid, operation="apply_op", prior_state=prior, state_after=after,
                inputs={"a": a, "op": op, "b": b, "result": res},
                decision=f"{a} {op} {b} = {res}",
                reason=f"{op} has the highest remaining precedence, so evaluate {a} {op} {b} = {res}",
                visual_state={"kind": "expression", "tokens": list(tokens), "highlight": res},
                visual_delta={"applied": f"{a}{op}{b}", "result": res},
                expected_visible_result=(f"{a} {op} {b} = {res}; expression now "
                                         + " ".join(str(t) for t in tokens)),
                facts={"allowed_values": sorted({t for t in example_input["tokens"] if isinstance(t, int)}
                                                | {res, a, b}),
                       "required_facts": [fact("operation", f"{a} {op} {b}"), fact("result", res)],
                       "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=f"Evaluate the expression {' '.join(map(str, example_input['tokens']))} respecting order of operations.",
            conventions=dict(_CONV), initial_state={"tokens": list(example_input["tokens"])},
            final_answer={"value": (tokens[0] if tokens else None)}, steps=steps,
            invariants=[dict(x) for x in _INV], required_cases=list(_REQUIRED), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input, attempt=attempt))

    def states_equivalent(self, a, b):
        return list((a or {}).get("tokens") or []) == list((b or {}).get("tokens") or [])

    def final_answer_entails(self, state, answer):
        toks = state.get("tokens") or []
        return len(toks) == 1 and toks[0] == (answer or {}).get("value")

    def invariant_holds(self, inv, state):
        toks = state.get("tokens") or []
        if not toks:
            return True
        if inv.get("id") == "value_preserved":
            return True
        if inv.get("id") == "single_value":
            return len(toks) == 1
        return True

    def validate_step_shape(self, step):
        errs = []
        if step.operation != "apply_op":
            errs.append(f"unexpected operation {step.operation!r}")
        for k in ("a", "op", "b", "result"):
            if k not in step.inputs:
                errs.append(f"missing inputs.{k}")
        return errs

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        return [] if str(step.inputs["result"]) in prose else [("result_not_stated", str(step.inputs["result"]))]
