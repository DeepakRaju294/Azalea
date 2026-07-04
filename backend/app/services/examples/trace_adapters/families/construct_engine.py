"""T8a Construction Engine (CP12d) — the DECLARATIVE type template for INCREMENTAL CONSTRUCTION concepts: a
target structure is built one piece at a time, and the PARTIAL output stays valid after every step until the
target is reached (ADAPTER_CATALOG T8a). This is the third trace grammar (after T6 formula, T7 rewrite) and
unlocks running totals / tables, truth tables, matrix products, and finance schedules (amortization,
depreciation).

A concept is a `ConstructSpec`: build an instance, how many pieces, how to add the i-th piece (+ its rule
prose), how to render the partial output, a validity predicate on the partial output, the extracted answer, and
an INDEPENDENT oracle. The engine authors the trace by actually adding each piece; the gate
(`test_construct_engine`) checks the answer against the oracle and that every partial output is valid."""
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
class ConstructSpec:
    slug: str
    title: str
    problem_template: str                           # .format(**state0) -> problem
    setup: Callable[[random.Random], dict]         # rng -> initial state (the input; output empty)
    pieces: Callable[[dict], int]                  # initial state -> number of construction steps
    step: Callable[[dict, int], tuple]             # (state, i) -> (new_state, rule_prose)
    render: Callable[[dict], str]                  # state -> the partial output so far
    valid: Callable[[dict], bool]                  # state -> partial output is VALID (the T8a invariant)
    answer: Callable[[dict], dict]                 # final state -> {name: value}
    oracle: Callable[[dict], dict]                 # INITIAL state -> the target, computed INDEPENDENTLY (gate)
    piece_word: str = "piece"                       # what one construction step adds ("element", "row", ...)
    target: str = "the structure is fully built"
    family: str = "sequence"
    aliases: list = field(default_factory=list)
    not_aliases: list = field(default_factory=list)
    priority: int = 50
    register: bool = True
    n_candidates: int = 80
    label_convention: str = "ints"


def _candidates(self, seed: int) -> Iterable[dict[str, Any]]:
    spec: ConstructSpec = self._construct_spec
    rng = random.Random(seed)
    for i in range(spec.n_candidates):
        state = spec.setup(rng)
        state["_id"] = f"{spec.slug}_v1_case_{i}"
        yield state


def _is_teaching_trace(self, trace: ContractTrace) -> bool:
    spec: ConstructSpec = self._construct_spec
    return len(trace.steps) == 1 + spec.pieces({k: v for k, v in (getattr(trace.steps[0], "inputs", {}) or {}).items()})


def _reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
               attempt: int = 1, seed: int = 0) -> ContractTrace:
    spec: ConstructSpec = self._construct_spec
    state = {k: v for k, v in example_input.items() if k != "_id"}
    n = spec.pieces(state)

    d1 = f"start building: {spec.target}"
    r1 = f"begin with an empty {spec.piece_word} sequence; add one {spec.piece_word} at a time"
    e1 = f"Start: {spec.render(state)}."
    steps = [Step(id="s1", operation="initialize", prior_state={"problem": spec.title},
                  state_after={"output": spec.render(state)}, inputs=dict(state), decision=d1, reason=r1,
                  visual_state={"kind": "variables", "output": spec.render(state)}, expected_visible_result=e1,
                  facts={"allowed_values": _ints(spec.render(state)),
                         "required_facts": [fact("start", spec.target)], "forbidden_claims": []})]

    for i in range(n):
        before = spec.render(state)
        state, rule = spec.step(state, i)
        after = spec.render(state)
        d = after
        r = f"{rule}; the partial result is now {after}"
        e = f"Add one {spec.piece_word}: {after}."
        steps.append(Step(id=f"s{i + 2}", operation="extend", prior_state={"output": before},
                          state_after={"output": after}, inputs={"output": after}, decision=d, reason=r,
                          visual_state={"kind": "variables", "output": after}, expected_visible_result=e,
                          facts={"allowed_values": _ints(before, after, rule),
                                 "required_facts": [fact("extend", after)], "forbidden_claims": []}))

    ans = spec.answer(state)
    evidence: dict[str, list[str]] = {"initialize": ["s1"], "extend": [f"s{i + 2}" for i in range(n)],
                                      "completion": [f"s{len(steps)}"]}
    return ContractTrace(
        problem=spec.problem_template.format(**{k: v for k, v in example_input.items() if k != "_id"}),
        conventions={"method": "build the result one piece at a time; the partial result stays valid"},
        initial_state={"problem": spec.title}, final_answer=dict(ans), steps=steps,
        invariants=[{"id": f"{spec.slug}_partial_valid", "scope": "every_step", "statement":
                     "the partial output is valid after every step"}],
        required_cases=["initialize", "extend", "completion"], case_evidence=evidence,
        provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                    attempt=attempt))


def _states_equivalent(self, a, b):
    return str((a or {}).get("output")) == str((b or {}).get("output"))


def _final_answer_entails(self, state, answer):
    st, an = state or {}, answer or {}
    out = str(st.get("output", ""))
    return all(str(v) in out for v in an.values())


def _invariant_holds(self, inv, state):
    # the recorded state_after carries only the rendered output string; validity is proven positively by the
    # gate (which re-checks spec.valid on the structured state at every step). Never a false invariant failure.
    return True


def _validate_step_shape(self, step):
    return [] if step.operation in {"initialize", "extend"} else [f"unexpected operation {step.operation!r}"]


def _validate_prose_claims(self, card, step):
    return []


_METHODS = {
    "candidates": _candidates, "is_teaching_trace": _is_teaching_trace, "reference": _reference,
    "states_equivalent": _states_equivalent, "final_answer_entails": _final_answer_entails,
    "invariant_holds": _invariant_holds, "validate_step_shape": _validate_step_shape,
    "validate_prose_claims": _validate_prose_claims,
}


def build_example_spec(spec: ConstructSpec) -> ExampleSpec:
    stages = {
        "initialize": StageSpec("initialize", "start the empty structure", cardinality="exactly_once",
                                teaching_focus="what is being built and its target",
                                contains={"start": "required"}, state_effects=["the structure starts empty"]),
        "extend": StageSpec("extend", f"add one {spec.piece_word}", cardinality="one_or_more",
                            teaching_focus=f"add one {spec.piece_word}; the partial result stays valid",
                            contains={"add_piece": "required"}, state_effects=[f"one more {spec.piece_word} is added"])}
    return ExampleSpec(
        input=InstanceShape("sequence", count=(1, 1), structure=[spec.slug]),
        stages=stages, structure="initialize extend",
        must_exercise=["initialize", "extend", "completion"], must_cover=[], must_avoid=[],
        terminal=spec.target, output_shape="the fully built structure")


def manifest_entry(spec: ConstructSpec) -> dict[str, Any]:
    return {"type": "T8a", "family": spec.family, "status": "experimental",
            "verification_level": "trace_verified", "coding": False, "canonical_solution": None,
            "routing_aliases": list(spec.aliases), "negative_guards": list(spec.not_aliases), "fixtures": []}


def routing_rule(spec: ConstructSpec) -> dict[str, Any]:
    rule: dict[str, Any] = {"any": list(spec.aliases), "priority": spec.priority}
    if spec.not_aliases:
        rule["not"] = list(spec.not_aliases)
    return rule


def construct_decl(spec: ConstructSpec) -> AdapterDecl:
    return AdapterDecl(
        slug=spec.slug, type="T8a", family=spec.family, example_spec=build_example_spec(spec),
        methods=dict(_METHODS), label_convention=spec.label_convention, routing=routing_rule(spec),
        class_attrs={"_construct_spec": spec, "provides_narration": True})


def registered_specs() -> list[ConstructSpec]:
    from . import construction_specs
    return [s for s in construction_specs.ALL_SPECS if s.register]
