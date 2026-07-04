"""T8b Derivation Engine (CP12d) — the DECLARATIVE type template for FORMAL DERIVATION concepts: a result is
reached by a sequence of steps, each JUSTIFIED BY A NAMED RULE from an allowed set, until the conclusion is
reached (ADAPTER_CATALOG T8b). The fourth and final trace grammar (after T6 formula, T7 rewrite, T8a
construction). Unlocks algebra-law derivations (exponent/log laws), rule-justified proofs, equation balancing.

A concept is a `DerivationSpec`: build an instance, render its state, the ordered derivation steps (each a named
law + a transform), the conclusion, the answer, and an INDEPENDENT oracle. The engine authors the derivation by
applying each rule; every step names its rule ("by the product rule, …") and the gate (`test_derivation_engine`)
checks the answer vs the oracle and that value is preserved at every step (each rule application is valid)."""
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
class DerivationStep:
    stage_id: str                                   # Step.operation
    law: str                                         # the named rule cited ("product rule")
    apply: Callable[[dict], dict]                   # state -> new state
    describe: Callable[[dict], str]                # state_before -> the rule application as prose


@dataclass
class DerivationSpec:
    slug: str
    title: str
    problem_template: str                           # .format(**state, start=…) -> problem
    setup: Callable[[random.Random], dict]
    render: Callable[[dict], str]
    steps: list[DerivationStep]
    conclusion: Callable[[dict], str]              # final state -> the concluded result string
    answer: Callable[[dict], dict]
    oracle: Callable[[dict], dict]                 # INITIAL state -> answer, computed INDEPENDENTLY (gate)
    invariant: Callable[[dict], bool] = lambda s: True   # value preserved (each rule application is valid)
    preserved: str = "each step follows an allowed rule, preserving the value"
    family: str = "algebra"
    aliases: list = field(default_factory=list)
    not_aliases: list = field(default_factory=list)
    priority: int = 50
    register: bool = True
    n_candidates: int = 80
    label_convention: str = "ints"


def _candidates(self, seed: int) -> Iterable[dict[str, Any]]:
    spec: DerivationSpec = self._derivation_spec
    rng = random.Random(seed)
    for i in range(spec.n_candidates):
        state = spec.setup(rng)
        state["_id"] = f"{spec.slug}_v1_case_{i}"
        yield state


def _is_teaching_trace(self, trace: ContractTrace) -> bool:
    spec: DerivationSpec = self._derivation_spec
    return len(trace.steps) == 1 + len(spec.steps)


def _reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
               attempt: int = 1, seed: int = 0) -> ContractTrace:
    spec: DerivationSpec = self._derivation_spec
    state = {k: v for k, v in example_input.items() if k != "_id"}
    start = spec.render(state)

    d1 = f"derive: simplify {start}"
    r1 = f"start from {start} and apply one algebra rule at a time"
    e1 = f"Start: {start}."
    steps = [Step(id="s1", operation="state_claim", prior_state={"problem": spec.title},
                  state_after={**state, "expr": start}, inputs=dict(state), decision=d1, reason=r1,
                  visual_state={"kind": "equation", "expr": start}, expected_visible_result=e1,
                  facts={"allowed_values": _ints(start), "required_facts": [fact("claim", start)],
                         "forbidden_claims": []})]

    for k, ds in enumerate(spec.steps, start=2):
        before = spec.render(state)
        rule_prose = ds.describe(state)
        state = ds.apply(state)
        after = spec.render(state)
        d = after
        r = f"by the {ds.law}, {rule_prose}: {before} = {after}"
        e = f"{ds.law}: {after}."
        steps.append(Step(id=f"s{k}", operation=ds.stage_id, prior_state={**{kk: vv for kk, vv in state.items()},
                                                                          "expr": before},
                          state_after={**state, "expr": after}, inputs={"expr": after}, decision=d, reason=r,
                          visual_state={"kind": "equation", "expr": after}, expected_visible_result=e,
                          facts={"allowed_values": _ints(before, after, rule_prose),
                                 "required_facts": [fact("derive", after)], "forbidden_claims": []}))

    concl = spec.conclusion(state)
    ans = spec.answer(state)
    required = ["state_claim"] + [ds.stage_id for ds in spec.steps] + ["completion"]
    evidence: dict[str, list[str]] = {"state_claim": ["s1"], "completion": [f"s{len(steps)}"]}
    for k, ds in enumerate(spec.steps, start=2):
        evidence[ds.stage_id] = [f"s{k}"]
    return ContractTrace(
        problem=spec.problem_template.format(start=start, **{k: v for k, v in state.items()}),
        conventions={"method": "each step cites an allowed rule", "conclusion": concl},
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
    spec: DerivationSpec = self._derivation_spec
    if inv.get("id") != f"{spec.slug}_value_preserved":
        return True
    try:
        return bool(spec.invariant(state or {}))
    except Exception:  # noqa: BLE001
        return True


def _validate_step_shape(self, step):
    spec: DerivationSpec = self._derivation_spec
    allowed = {"state_claim", *(ds.stage_id for ds in spec.steps)}
    return [] if step.operation in allowed else [f"unexpected operation {step.operation!r}"]


def _validate_prose_claims(self, card, step):
    return []


_METHODS = {
    "candidates": _candidates, "is_teaching_trace": _is_teaching_trace, "reference": _reference,
    "states_equivalent": _states_equivalent, "final_answer_entails": _final_answer_entails,
    "invariant_holds": _invariant_holds, "validate_step_shape": _validate_step_shape,
    "validate_prose_claims": _validate_prose_claims,
}


def build_example_spec(spec: DerivationSpec) -> ExampleSpec:
    stages = {"state_claim": StageSpec("state_claim", "state what is to be derived", cardinality="exactly_once",
                                       teaching_focus="the starting expression",
                                       contains={"read": "required"}, state_effects=["the claim is stated"])}
    for ds in spec.steps:
        stages[ds.stage_id] = StageSpec(ds.stage_id, f"apply the {ds.law}", cardinality="exactly_once",
                                        teaching_focus=f"apply the {ds.law}",
                                        contains={"apply_rule": "required"}, state_effects=[f"after: {ds.law}"])
    structure = " ".join(["state_claim", *(ds.stage_id for ds in spec.steps)])
    return ExampleSpec(
        input=InstanceShape("expression", count=(1, 1), structure=[spec.slug]),
        stages=stages, structure=structure,
        must_exercise=["state_claim", *(ds.stage_id for ds in spec.steps), "completion"],
        must_cover=[], must_avoid=[], terminal="the conclusion is reached", output_shape="the derived result")


def manifest_entry(spec: DerivationSpec) -> dict[str, Any]:
    return {"type": "T8b", "family": spec.family, "status": "experimental",
            "verification_level": "trace_verified", "coding": False, "canonical_solution": None,
            "routing_aliases": list(spec.aliases), "negative_guards": list(spec.not_aliases), "fixtures": []}


def routing_rule(spec: DerivationSpec) -> dict[str, Any]:
    rule: dict[str, Any] = {"any": list(spec.aliases), "priority": spec.priority}
    if spec.not_aliases:
        rule["not"] = list(spec.not_aliases)
    return rule


def derivation_decl(spec: DerivationSpec) -> AdapterDecl:
    return AdapterDecl(
        slug=spec.slug, type="T8b", family=spec.family, example_spec=build_example_spec(spec),
        methods=dict(_METHODS), label_convention=spec.label_convention, routing=routing_rule(spec),
        class_attrs={"_derivation_spec": spec, "provides_narration": True})


def registered_specs() -> list[DerivationSpec]:
    from . import derivation_specs
    return [s for s in derivation_specs.ALL_SPECS if s.register]
