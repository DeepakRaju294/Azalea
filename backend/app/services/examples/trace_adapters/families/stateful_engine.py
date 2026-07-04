"""T10 Stateful Engine (CP12e) — the DECLARATIVE type template for STATEFUL-OPERATION concepts: a data
structure is mutated by a scripted sequence of operations (push/pop, enqueue/dequeue, insert/evict, …) and its
invariant is maintained after every operation (ADAPTER_CATALOG T10). Unlike the construction engine (which only
grows), a stateful trace both grows AND shrinks. Unlocks stacks, queues, hash tables, counters, FSM traces.

A concept is a `StatefulSpec`: build an instance (initial structure + an operation script), how many
operations, how to apply the i-th operation (+ its prose), how to render the structure, an invariant predicate,
the answer, and an INDEPENDENT oracle (replay from the initial script). The engine authors the trace by
applying each operation; the gate (`test_stateful_engine`) checks the answer vs the oracle and the invariant."""
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
class StatefulSpec:
    slug: str
    title: str
    problem_template: str
    setup: Callable[[random.Random], dict]         # rng -> initial state (structure + operation script)
    ops_count: Callable[[dict], int]               # initial state -> number of operations
    apply: Callable[[dict, int], tuple]            # (state, i) -> (new_state, operation_prose)
    render: Callable[[dict], str]                  # state -> the structure, as prose
    answer: Callable[[dict], dict]                 # final state -> {name: value}
    oracle: Callable[[dict], dict]                 # INITIAL state -> the result, replayed INDEPENDENTLY (gate)
    invariant: Callable[[dict], bool] = lambda s: True   # the structure's maintained invariant
    op_word: str = "operation"
    target: str = "all operations have been applied"     # MUST be digit-free (terminal-prose contract)
    family: str = "structures"
    aliases: list = field(default_factory=list)
    not_aliases: list = field(default_factory=list)
    priority: int = 50
    register: bool = True
    n_candidates: int = 80
    label_convention: str = "ints"


def _candidates(self, seed: int) -> Iterable[dict[str, Any]]:
    spec: StatefulSpec = self._stateful_spec
    rng = random.Random(seed)
    for i in range(spec.n_candidates):
        state = spec.setup(rng)
        state["_id"] = f"{spec.slug}_v1_case_{i}"
        yield state


def _is_teaching_trace(self, trace: ContractTrace) -> bool:
    spec: StatefulSpec = self._stateful_spec
    return len(trace.steps) == 1 + spec.ops_count({k: v for k, v in (getattr(trace.steps[0], "inputs", {}) or {}).items()})


def _reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
               attempt: int = 1, seed: int = 0) -> ContractTrace:
    spec: StatefulSpec = self._stateful_spec
    state = {k: v for k, v in example_input.items() if k != "_id"}
    n = spec.ops_count(state)

    d1 = f"start: {spec.render(state)}"
    r1 = f"begin with the initial structure and apply each {spec.op_word} in order"
    e1 = f"Start: {spec.render(state)}."
    steps = [Step(id="s1", operation="initialize", prior_state={"problem": spec.title},
                  state_after={"struct": spec.render(state)}, inputs=dict(state), decision=d1, reason=r1,
                  visual_state={"kind": "variables", "struct": spec.render(state)}, expected_visible_result=e1,
                  facts={"allowed_values": _ints(spec.render(state)),
                         "required_facts": [fact("start", spec.target)], "forbidden_claims": []})]

    for i in range(n):
        before = spec.render(state)
        state, op = spec.apply(state, i)
        after = spec.render(state)
        d = after
        r = f"{op}; the structure is now {after}"
        e = f"After the {spec.op_word}: {after}."
        steps.append(Step(id=f"s{i + 2}", operation="apply_operation", prior_state={"struct": before},
                          state_after={"struct": after}, inputs={"struct": after}, decision=d, reason=r,
                          visual_state={"kind": "variables", "struct": after}, expected_visible_result=e,
                          facts={"allowed_values": _ints(before, after, op),
                                 "required_facts": [fact("operation", after)], "forbidden_claims": []}))

    ans = spec.answer(state)
    evidence: dict[str, list[str]] = {"initialize": ["s1"], "apply_operation": [f"s{i + 2}" for i in range(n)],
                                      "completion": [f"s{len(steps)}"]}
    return ContractTrace(
        problem=spec.problem_template.format(**{k: v for k, v in example_input.items() if k != "_id"}),
        conventions={"method": "apply one operation at a time; the invariant holds after each"},
        initial_state={"problem": spec.title}, final_answer=dict(ans), steps=steps,
        invariants=[{"id": f"{spec.slug}_invariant", "scope": "every_step",
                     "statement": "the structure's invariant holds after every operation"}],
        required_cases=["initialize", "apply_operation", "completion"], case_evidence=evidence,
        provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                    attempt=attempt))


def _states_equivalent(self, a, b):
    return str((a or {}).get("struct")) == str((b or {}).get("struct"))


def _final_answer_entails(self, state, answer):
    st, an = state or {}, answer or {}
    out = str(st.get("struct", ""))
    return all(str(v) in out for v in an.values())


def _invariant_holds(self, inv, state):
    return True                                                # replayed positively by the gate


def _validate_step_shape(self, step):
    return [] if step.operation in {"initialize", "apply_operation"} else [f"unexpected operation {step.operation!r}"]


def _validate_prose_claims(self, card, step):
    return []


_METHODS = {
    "candidates": _candidates, "is_teaching_trace": _is_teaching_trace, "reference": _reference,
    "states_equivalent": _states_equivalent, "final_answer_entails": _final_answer_entails,
    "invariant_holds": _invariant_holds, "validate_step_shape": _validate_step_shape,
    "validate_prose_claims": _validate_prose_claims,
}


def build_example_spec(spec: StatefulSpec) -> ExampleSpec:
    stages = {
        "initialize": StageSpec("initialize", "state the initial structure", cardinality="exactly_once",
                                teaching_focus="the structure and its invariant",
                                contains={"start": "required"}, state_effects=["the structure is initial"]),
        "apply_operation": StageSpec("apply_operation", f"apply one {spec.op_word}", cardinality="one_or_more",
                                     teaching_focus=f"apply one {spec.op_word}; the invariant is maintained",
                                     contains={"mutate": "required"}, state_effects=["the structure is updated"])}
    return ExampleSpec(
        input=InstanceShape("operations", count=(1, 1), structure=[spec.slug]),
        stages=stages, structure="initialize apply_operation",
        must_exercise=["initialize", "apply_operation", "completion"], must_cover=[], must_avoid=[],
        terminal=spec.target, output_shape="the final structure")


def manifest_entry(spec: StatefulSpec) -> dict[str, Any]:
    return {"type": "T10", "family": spec.family, "status": "experimental",
            "verification_level": "trace_verified", "coding": False, "canonical_solution": None,
            "routing_aliases": list(spec.aliases), "negative_guards": list(spec.not_aliases), "fixtures": []}


def routing_rule(spec: StatefulSpec) -> dict[str, Any]:
    rule: dict[str, Any] = {"any": list(spec.aliases), "priority": spec.priority}
    if spec.not_aliases:
        rule["not"] = list(spec.not_aliases)
    return rule


def stateful_decl(spec: StatefulSpec) -> AdapterDecl:
    return AdapterDecl(
        slug=spec.slug, type="T10", family=spec.family, example_spec=build_example_spec(spec),
        methods=dict(_METHODS), label_convention=spec.label_convention, routing=routing_rule(spec),
        class_attrs={"_stateful_spec": spec, "provides_narration": True})


def registered_specs() -> list[StatefulSpec]:
    from . import stateful_specs
    return [s for s in stateful_specs.ALL_SPECS if s.register]
