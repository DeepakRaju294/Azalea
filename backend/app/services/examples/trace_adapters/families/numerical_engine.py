"""T16 Numerical-Convergence Engine (ADAPTER_TAXONOMY_SPEC T16 `numerical_time_step_convergence`) — the
DECLARATIVE type template for iterative numerical methods: current approximation → update rule → residual →
stopping/convergence check.

Distinct from T8a construction ("add a valid piece"): the educational point is WHETHER/WHY the iteration
converges, so the trace carries a verified RESIDUAL and a stopping test at every step. The engine iterates for
real; the gate (`test_numerical_engine`) checks each iterate = update(previous), the residual is non-increasing
and reaches the tolerance, and the converged estimate is CLOSE to an independent oracle (numerical methods
converge within a tolerance — never exact equality).

v1 pilots Newton's method (sqrt, cbrt) + a linear fixed point. A concept is a `NumericalSpec`: initial guess,
update rule, residual, tolerance. Adding one = a one-file DATA edit."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..decl import AdapterDecl
from ..example_spec import ExampleSpec, InstanceShape, StageSpec


def _ints(*parts: Any) -> list[int]:
    found: set[int] = set()
    for m in re.findall(r"-?\d+", " ".join(str(p) for p in parts)):
        found.add(int(m)); found.add(abs(int(m)))
    return sorted(found)


@dataclass
class NumericalSpec:
    slug: str
    title: str
    problem_template: str                              # .format(**state) -> problem
    setup: Callable[[random.Random], dict]            # rng -> params (incl. the target/inputs)
    initial: Callable[[dict], float]                  # params -> x0
    update: Callable[[dict, float], tuple]            # (params, x) -> (x_next, rule_prose)
    residual: Callable[[dict, float], float]          # (params, x) -> error/residual at x (>= 0)
    true_value: Callable[[dict], float]               # params -> the exact target (independent oracle)
    estimate_name: str = "estimate"
    tol: float = 1e-4                                  # stop when residual < tol
    answer_tol: float = 1e-3                           # gate: |estimate - true| must be <= this
    max_iters: int = 30
    round_dp: int = 6
    answer_dp: int = 3
    family: str = "numerical"
    aliases: list = field(default_factory=list)
    not_aliases: list = field(default_factory=list)
    priority: int = 50
    register: bool = True
    n_candidates: int = 40
    label_convention: str = "ints"

    def iterate(self, params: dict) -> list:
        """The rounded iterate sequence [(x, residual, rule_prose)] until residual < tol or max_iters."""
        x = round(self.initial(params), self.round_dp)
        seq = [(x, round(self.residual(params, x), self.round_dp), "initial guess")]
        for _ in range(self.max_iters):
            if seq[-1][1] < self.tol:
                break
            x_next, prose = self.update(params, x)
            x_next = round(x_next, self.round_dp)
            seq.append((x_next, round(self.residual(params, x_next), self.round_dp), prose))
            x = x_next
        return seq

    def answer(self, params: dict) -> dict:
        seq = self.iterate(params)
        return {self.estimate_name: f"{round(seq[-1][0], self.answer_dp)}"}

    def oracle(self, params: dict) -> dict:
        return {self.estimate_name: f"{round(self.true_value(params), self.answer_dp)}"}


def _candidates(self, seed: int) -> Iterable[dict[str, Any]]:
    spec: NumericalSpec = self._numerical_spec
    rng = random.Random(seed)
    for i in range(spec.n_candidates):
        params = spec.setup(rng)
        params["_id"] = f"{spec.slug}_v1_case_{i}"
        yield params


def _is_teaching_trace(self, trace: ContractTrace) -> bool:
    return bool(trace.steps) and trace.steps[0].operation == "initialize" and len(trace.steps) >= 2


def _reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
               attempt: int = 1, seed: int = 0) -> ContractTrace:
    spec: NumericalSpec = self._numerical_spec
    params = {k: v for k, v in example_input.items() if k != "_id"}
    seq = spec.iterate(params)
    est = round(seq[-1][0], spec.answer_dp)
    ans = {spec.estimate_name: f"{est}"}

    steps: list[Step] = []
    evidence: dict[str, list[str]] = {"initialize": [], "iterate": [], "completion": []}
    prev_render = ""
    for idx, (x, res, prose) in enumerate(seq):
        step_id = f"s{idx + 1}"
        is_last = idx == len(seq) - 1
        rendered = f"x = {x} (residual {res})"
        state_after = {"output": rendered}
        if idx == 0:
            operation = "initialize"
            decision = f"start from the initial guess x = {x}"
            reason = f"{prose}; the residual measures how far we are from convergence (residual {res})"
            evis = f"Initial guess x = {x}, residual {res}."
            evidence["initialize"].append(step_id)
        else:
            operation = "iterate"
            decision = f"update to x = {x}"
            reason = f"{prose}; residual falls to {res}"
            evis = f"Iterate: x = {x}, residual {res}."
            evidence["iterate"].append(step_id)
        if is_last:
            summary = f"{rendered}  =>  converged: {spec.estimate_name} ≈ {est}"
            state_after = {"output": summary}
            evis = f"Residual {res} < tolerance {spec.tol}: converged. {spec.estimate_name} ≈ {est}."
            evidence["completion"].append(step_id)
        prior = {"problem": spec.title} if idx == 0 else {"output": prev_render}
        steps.append(Step(
            id=step_id, operation=operation, prior_state=prior, state_after=state_after,
            inputs=dict(example_input) if idx == 0 else {"output": state_after["output"]},
            decision=decision, reason=reason,
            visual_state={"kind": "variables", "output": state_after["output"]},
            expected_visible_result=evis,
            facts={"allowed_values": _ints(x, res, est if is_last else ""),
                   "required_facts": [fact(operation, str(x))], "forbidden_claims": []}))
        prev_render = state_after["output"]

    return ContractTrace(
        problem=spec.problem_template.format(**params),
        conventions={"method": "iterate the update rule; stop when the residual is below the tolerance"},
        initial_state={"problem": spec.title}, final_answer=dict(ans), steps=steps,
        invariants=[{"id": f"{spec.slug}_converges", "scope": "terminal",
                     "statement": "the residual decreases to below the tolerance"}],
        required_cases=["initialize", "iterate", "completion"], case_evidence=evidence,
        provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                    attempt=attempt))


def _states_equivalent(self, a, b):
    return str((a or {}).get("output")) == str((b or {}).get("output"))


def _final_answer_entails(self, state, answer):
    out = str((state or {}).get("output", ""))
    return all(str(v) in out for v in (answer or {}).values())


def _invariant_holds(self, inv, state):
    return True   # convergence is proven positively by the gate (residual monotone to < tol)


def _validate_step_shape(self, step):
    ok = {"initialize", "iterate"}
    return [] if step.operation in ok else [f"unexpected operation {step.operation!r}"]


def _validate_prose_claims(self, card, step):
    return []


_METHODS = {
    "candidates": _candidates, "is_teaching_trace": _is_teaching_trace, "reference": _reference,
    "states_equivalent": _states_equivalent, "final_answer_entails": _final_answer_entails,
    "invariant_holds": _invariant_holds, "validate_step_shape": _validate_step_shape,
    "validate_prose_claims": _validate_prose_claims,
}


def build_example_spec(spec: NumericalSpec) -> ExampleSpec:
    stages = {
        "initialize": StageSpec("initialize", "state the initial guess", cardinality="exactly_once",
                                teaching_focus="the initial guess and the residual",
                                contains={"initialize": "required"},
                                state_effects=["the iteration starts from x0"]),
        "iterate": StageSpec("iterate", "apply the update rule", cardinality="one_or_more",
                             teaching_focus="one update; the residual shrinks toward the tolerance",
                             contains={"iterate": "required"},
                             state_effects=["the estimate is updated and the residual shrinks"])}
    return ExampleSpec(
        input=InstanceShape("sequence", count=(1, 1), structure=[spec.slug]),
        stages=stages, structure="initialize iterate",
        must_exercise=["initialize", "iterate", "completion"], must_cover=[], must_avoid=[],
        terminal="the residual is below the tolerance", output_shape="the converged estimate")


def manifest_entry(spec: NumericalSpec) -> dict[str, Any]:
    return {"type": "T16", "family": spec.family, "status": "experimental",
            "verification_level": "trace_verified", "coding": False, "canonical_solution": None,
            "routing_aliases": list(spec.aliases), "negative_guards": list(spec.not_aliases), "fixtures": []}


def routing_rule(spec: NumericalSpec) -> dict[str, Any]:
    rule: dict[str, Any] = {"any": list(spec.aliases), "priority": spec.priority}
    if spec.not_aliases:
        rule["not"] = list(spec.not_aliases)
    return rule


def numerical_decl(spec: NumericalSpec) -> AdapterDecl:
    return AdapterDecl(
        slug=spec.slug, type="T16", family=spec.family, example_spec=build_example_spec(spec),
        methods=dict(_METHODS), label_convention=spec.label_convention, routing=routing_rule(spec),
        class_attrs={"_numerical_spec": spec, "provides_narration": True})


def registered_specs() -> list[NumericalSpec]:
    from . import numerical_specs
    return [s for s in numerical_specs.ALL_SPECS if s.register]
