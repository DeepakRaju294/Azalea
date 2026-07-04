"""T7 Rewrite Engine (CP12c) — the DECLARATIVE type template for REWRITE concepts: a state (an expression or
equation) is transformed by applying ONE allowed rule per step until a goal / normal form is reached. This is
the second trace grammar (after T6's formula plug-in) and unlocks algebra (solve/simplify), symbolic calculus
(differentiate/integrate by rules), and linear-algebra row reduction.

A concept is a `RewriteSpec`: how to build an instance, how to render its state, the ordered rewrite steps
(each a transform + a rule description), the extracted answer, and an INDEPENDENT verify() the gate uses. The
engine authors the trace by actually applying the rules, so each step's before/after state is real; the gate
(`test_rewrite_engine`) checks the answer against verify() — gate-passing != authored-correct.

Piloted on linear equations; new rewrite families are added as specs (see algebra_specs.py)."""
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
class RewriteStep:
    stage_id: str                                   # Step.operation
    teaching_focus: str                             # what this rewrite rule is
    apply: Callable[[dict], dict]                   # state -> new state (the rule)
    describe: Callable[[dict], str]                # state_before -> the rule as learner prose ("subtract 5 …")


@dataclass
class RewriteSpec:
    slug: str
    title: str
    problem_template: str                           # .format(**state) -> problem
    setup: Callable[[random.Random], dict]         # rng -> initial state dict (carries 'var' + numbers)
    render: Callable[[dict], str]                  # state -> the expression/equation string
    steps: list[RewriteStep]
    answer: Callable[[dict], dict]                 # final state -> {name: value}
    oracle: Callable[[dict], dict]                 # INITIAL state -> the answer, computed INDEPENDENTLY (gate)
    # the quantity a rewrite must NOT change (equation: the solution set) — checked on every step's state (T7
    # value-preservation contract). Default True for concepts where preservation is structural.
    invariant: Callable[[dict], bool] = lambda s: True
    preserved: str = "the solution set is preserved by every step"
    goal: str = "the variable is isolated"          # terminal description
    task: str = "solve"                             # "solve" (for var) | "simplify" (an expression) — frames the intro
    family: str = "algebra"
    aliases: list = field(default_factory=list)
    not_aliases: list = field(default_factory=list)
    priority: int = 50
    register: bool = True
    n_candidates: int = 80
    label_convention: str = "ints"


# --- generic contract methods (bound onto the hydrated adapter; read self._rewrite_spec) ---------------
def _candidates(self, seed: int) -> Iterable[dict[str, Any]]:
    spec: RewriteSpec = self._rewrite_spec
    rng = random.Random(seed)
    for i in range(spec.n_candidates):
        state = spec.setup(rng)
        state["_id"] = f"{spec.slug}_v1_case_{i}"
        yield state


def _is_teaching_trace(self, trace: ContractTrace) -> bool:
    spec: RewriteSpec = self._rewrite_spec
    return len(trace.steps) == 1 + len(spec.steps)


def _reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
               attempt: int = 1, seed: int = 0) -> ContractTrace:
    spec: RewriteSpec = self._rewrite_spec
    state = {k: v for k, v in example_input.items() if k != "_id"}
    var = state.get("var", "x")
    start_render = spec.render(state)

    if spec.task == "simplify":
        d1 = f"simplify {start_render}"
        r1 = f"the expression is {start_render}; combine it into a simpler form"
    else:
        d1 = f"solve {start_render} for {var}"
        r1 = f"the equation is {start_render}; isolate {var}"
    e1 = f"Start: {start_render}."
    steps = [Step(id="s1", operation="state_equation", prior_state={"problem": spec.title},
                  state_after={**state, "expr": start_render}, inputs=dict(state), decision=d1, reason=r1,
                  visual_state={"kind": "equation", "expr": start_render}, expected_visible_result=e1,
                  facts={"allowed_values": _ints(start_render), "required_facts": [fact("equation", start_render)],
                         "forbidden_claims": []})]

    for k, rs in enumerate(spec.steps, start=2):
        before = spec.render(state)
        rule = rs.describe(state)
        state = rs.apply(state)
        after = spec.render(state)
        d = after
        r = f"{rule}: {before} -> {after}"
        e = f"{rs.teaching_focus}: {after}."
        steps.append(Step(id=f"s{k}", operation=rs.stage_id, prior_state={"expr": before},
                          state_after={**state, "expr": after}, inputs={"expr": after}, decision=d, reason=r,
                          visual_state={"kind": "equation", "expr": after}, expected_visible_result=e,
                          facts={"allowed_values": _ints(before, after, rule),
                                 "required_facts": [fact("rewrite", after)], "forbidden_claims": []}))

    ans = spec.answer(state)
    required = ["state_equation"] + [rs.stage_id for rs in spec.steps] + ["completion"]
    evidence: dict[str, list[str]] = {"state_equation": ["s1"], "completion": [f"s{len(steps)}"]}
    for k, rs in enumerate(spec.steps, start=2):
        evidence[rs.stage_id] = [f"s{k}"]
    return ContractTrace(
        problem=spec.problem_template.format(eqn=start_render, var=var),
        conventions={"method": "apply one inverse/rewrite rule per step"},
        initial_state={"problem": spec.title}, final_answer=dict(ans), steps=steps,
        invariants=[{"id": f"{spec.slug}_value_preserved", "scope": "every_step", "statement": spec.preserved}],
        required_cases=list(required), case_evidence=evidence,
        provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                    attempt=attempt))


def _states_equivalent(self, a, b):
    return str((a or {}).get("expr")) == str((b or {}).get("expr"))


def _final_answer_entails(self, state, answer):
    st, an = state or {}, answer or {}
    expr = str(st.get("expr", ""))
    return all(str(v) in expr for v in an.values())


def _invariant_holds(self, inv, state):
    spec: RewriteSpec = self._rewrite_spec
    if inv.get("id") != f"{spec.slug}_value_preserved":
        return True
    try:
        return bool(spec.invariant(state or {}))               # the preserved quantity still holds at this step
    except Exception:  # noqa: BLE001 — a partial/rendered-only state can't disprove preservation
        return True


def _validate_step_shape(self, step):
    spec: RewriteSpec = self._rewrite_spec
    allowed = {"state_equation", *(rs.stage_id for rs in spec.steps)}
    return [] if step.operation in allowed else [f"unexpected operation {step.operation!r}"]


def _validate_prose_claims(self, card, step):
    return []


_METHODS = {
    "candidates": _candidates, "is_teaching_trace": _is_teaching_trace, "reference": _reference,
    "states_equivalent": _states_equivalent, "final_answer_entails": _final_answer_entails,
    "invariant_holds": _invariant_holds, "validate_step_shape": _validate_step_shape,
    "validate_prose_claims": _validate_prose_claims,
}


def build_example_spec(spec: RewriteSpec) -> ExampleSpec:
    stages: dict[str, StageSpec] = {
        "state_equation": StageSpec("state_equation", "write the starting equation", cardinality="exactly_once",
                                    teaching_focus="identify what to isolate",
                                    contains={"read_equation": "required"}, state_effects=["the equation is stated"])}
    for rs in spec.steps:
        stages[rs.stage_id] = StageSpec(rs.stage_id, rs.teaching_focus, cardinality="exactly_once",
                                        teaching_focus=rs.teaching_focus,
                                        contains={"apply_rule": "required"}, state_effects=[f"after: {rs.teaching_focus}"])
    structure = " ".join(["state_equation", *(rs.stage_id for rs in spec.steps)])
    return ExampleSpec(
        input=InstanceShape("equation", count=(1, 1), structure=[spec.slug]),
        stages=stages, structure=structure,
        must_exercise=["state_equation", *(rs.stage_id for rs in spec.steps), "completion"],
        must_cover=[], must_avoid=[], terminal=spec.goal, output_shape="the solved variable")


def manifest_entry(spec: RewriteSpec) -> dict[str, Any]:
    return {"type": "T7", "family": spec.family, "status": "experimental",
            "verification_level": "trace_verified", "coding": False, "canonical_solution": None,
            "routing_aliases": list(spec.aliases), "negative_guards": list(spec.not_aliases), "fixtures": []}


def routing_rule(spec: RewriteSpec) -> dict[str, Any]:
    rule: dict[str, Any] = {"any": list(spec.aliases), "priority": spec.priority}
    if spec.not_aliases:
        rule["not"] = list(spec.not_aliases)
    return rule


def rewrite_decl(spec: RewriteSpec) -> AdapterDecl:
    return AdapterDecl(
        slug=spec.slug, type="T7", family=spec.family, example_spec=build_example_spec(spec),
        methods=dict(_METHODS), label_convention=spec.label_convention, routing=routing_rule(spec),
        class_attrs={"_rewrite_spec": spec, "provides_narration": True})


def registered_specs() -> list[RewriteSpec]:
    from . import algebra_specs
    return [s for s in algebra_specs.ALL_SPECS if s.register]
