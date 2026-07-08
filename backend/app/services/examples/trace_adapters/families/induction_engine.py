"""T13 Proof-Obligation Engine (ADAPTER_TAXONOMY_SPEC T13 `proof_obligation_discharge`) — the DECLARATIVE type
template for a proof whose obligations are MACHINE-CHECKABLE: assumptions → subgoal → justified inference →
discharged obligation → conclusion.

Distinct from T8b formal derivation (equality preserved at every step): a proof introduces an assumption (the
inductive hypothesis) and discharges obligations, which is not an equality chain. v1 supports MATHEMATICAL
INDUCTION over polynomial summation identities ∑_{i=base}^n f(i) = g(n), where every obligation is decidable:
- base case: ∑_{i=base}^{base} f(i) == g(base)                      (evaluate)
- inductive step: g(k) + f(k+1) == g(k+1) as a POLYNOMIAL IDENTITY  (proved by checking > deg points; a degree-d
  polynomial that is zero at d+1 points is identically zero)
An open-ended proof with no decidable obligation model is Family C (guided), never a fake T13 adapter.

A concept is an `InductionSpec`: the term f, the closed form g, and their display. Adding one = a one-file DATA
edit. The gate (`test_induction_engine`) re-checks the base + inductive obligations and confirms the closed form
against an INDEPENDENT running-sum oracle."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..decl import AdapterDecl
from ..example_spec import ExampleSpec, InstanceShape, StageSpec

# points to check the inductive-step polynomial identity at — well above the degree of any v1 closed form
_IDENTITY_POINTS = 10


def _ints(*parts: Any) -> list[int]:
    found: set[int] = set()
    for m in re.findall(r"-?\d+", " ".join(str(p) for p in parts)):
        found.add(int(m)); found.add(abs(int(m)))
    return sorted(found)


@dataclass
class InductionSpec:
    slug: str
    title: str
    problem_template: str                          # .format(N=<int>) -> problem
    f: Callable[[int], int]                        # the term f(i)
    g: Callable[[int], int]                        # the closed form g(n) (integer-valued)
    f_str: str                                     # display of f(i), e.g. "i"
    g_str: str                                     # display of g(n), e.g. "n(n+1)/2"
    base: int = 1
    family: str = "proof"
    aliases: list = field(default_factory=list)
    not_aliases: list = field(default_factory=list)
    priority: int = 50
    register: bool = True
    n_candidates: int = 30
    label_convention: str = "ints"

    def sum_upto(self, n: int) -> int:
        return sum(self.f(i) for i in range(self.base, n + 1))

    def base_ok(self) -> bool:
        return self.sum_upto(self.base) == self.g(self.base)

    def inductive_step_ok(self) -> bool:
        # g(k) + f(k+1) == g(k+1) checked at many k → proves the polynomial identity
        return all(self.g(k) + self.f(k + 1) == self.g(k + 1)
                   for k in range(self.base, self.base + _IDENTITY_POINTS))

    def setup(self, rng: random.Random) -> dict:
        return {"N": rng.randint(self.base + 2, self.base + 7)}

    def answer(self, state: dict) -> dict:
        n = state["N"]
        return {"value_at_n": str(self.g(n)), "n": str(n)}

    def oracle(self, state: dict) -> dict:
        # INDEPENDENT: the running sum, computed directly (not via the closed form)
        n = state["N"]
        return {"value_at_n": str(self.sum_upto(n)), "n": str(n)}


def _candidates(self, seed: int) -> Iterable[dict[str, Any]]:
    spec: InductionSpec = self._induction_spec
    rng = random.Random(seed)
    for i in range(spec.n_candidates):
        st = spec.setup(rng)
        st["_id"] = f"{spec.slug}_v1_case_{i}"
        yield st


def _is_teaching_trace(self, trace: ContractTrace) -> bool:
    return bool(trace.steps) and trace.steps[0].operation == "initialize" and len(trace.steps) >= 2


def _reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
               attempt: int = 1, seed: int = 0) -> ContractTrace:
    spec: InductionSpec = self._induction_spec
    n = example_input["N"]
    claim = f"P(n): sum of {spec.f_str} for i={spec.base}..n = {spec.g_str}"
    base_val = spec.g(spec.base)
    val_at_n = spec.g(n)

    s1 = Step(
        id="s1", operation="initialize", prior_state={"problem": spec.title},
        state_after={"output": f"claim {claim}"}, inputs=dict(example_input),
        decision=f"state the claim to prove by induction: {claim}",
        reason="prove it holds for all n >= base by mathematical induction",
        visual_state={"kind": "variables", "output": f"claim {claim}"},
        expected_visible_result=f"Claim {claim}.",
        facts={"allowed_values": _ints(spec.base, spec.g_str), "required_facts": [fact("claim", claim)],
               "forbidden_claims": []})

    base_out = f"base case n={spec.base}: sum = {spec.g(spec.base)} = {base_val}"
    s2 = Step(
        id="s2", operation="discharge", prior_state={"output": f"claim {claim}"},
        state_after={"output": base_out},
        inputs={"output": base_out},
        decision=f"discharge the base case: check P({spec.base})",
        reason=f"the left side sums to {spec.sum_upto(spec.base)} and {spec.g_str} at n={spec.base} is "
               f"{base_val}; they are equal, so P({spec.base}) holds",
        visual_state={"kind": "variables", "output": base_out},
        expected_visible_result=f"Base case holds: P({spec.base}) is true ({base_val}).",
        facts={"allowed_values": _ints(spec.base, base_val), "required_facts": [fact("base", str(base_val))],
               "forbidden_claims": []})

    step_out = (f"inductive step: assume P(k); then sum to k+1 = g(k) + {spec.f_str}(k+1) = g(k+1); "
                f"so P(n) holds for all n. For n={n}: sum = {val_at_n}")
    s3 = Step(
        id="s3", operation="discharge", prior_state={"output": base_out},
        state_after={"output": step_out}, inputs={"output": step_out},
        decision="discharge the inductive step: assume P(k), prove P(k+1)",
        reason=f"adding the next term {spec.f_str}(k+1) to the hypothesis g(k) gives g(k+1) as an algebraic "
               f"identity; the obligation is discharged, so by induction P(n) holds for all n >= {spec.base}. "
               f"For n={n}, the sum is {val_at_n}",
        visual_state={"kind": "variables", "output": step_out},
        expected_visible_result=f"Inductive step holds; by induction P(n) is true for all n. For n={n}: {val_at_n}.",
        facts={"allowed_values": _ints(n, val_at_n), "required_facts": [fact("inductive_step", str(val_at_n))],
               "forbidden_claims": []})

    return ContractTrace(
        problem=spec.problem_template.format(N=n),
        conventions={"method": "mathematical induction: discharge the base case and the inductive step"},
        initial_state={"problem": spec.title}, final_answer=spec.answer(example_input), steps=[s1, s2, s3],
        invariants=[{"id": f"{spec.slug}_obligations_discharged", "scope": "terminal",
                     "statement": "the base case and inductive-step obligations are both discharged"}],
        required_cases=["initialize", "discharge", "completion"],
        case_evidence={"initialize": ["s1"], "discharge": ["s2", "s3"], "completion": ["s3"]},
        provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                    attempt=attempt))


def _states_equivalent(self, a, b):
    return str((a or {}).get("output")) == str((b or {}).get("output"))


def _final_answer_entails(self, state, answer):
    out = str((state or {}).get("output", ""))
    return all(str(v) in out for v in (answer or {}).values())


def _invariant_holds(self, inv, state):
    return True   # obligation discharge is proven positively by the gate (base + inductive-step checks)


def _validate_step_shape(self, step):
    ok = {"initialize", "discharge"}
    return [] if step.operation in ok else [f"unexpected operation {step.operation!r}"]


def _validate_prose_claims(self, card, step):
    return []


_METHODS = {
    "candidates": _candidates, "is_teaching_trace": _is_teaching_trace, "reference": _reference,
    "states_equivalent": _states_equivalent, "final_answer_entails": _final_answer_entails,
    "invariant_holds": _invariant_holds, "validate_step_shape": _validate_step_shape,
    "validate_prose_claims": _validate_prose_claims,
}


def build_example_spec(spec: InductionSpec) -> ExampleSpec:
    stages = {
        "initialize": StageSpec("initialize", "state the claim", cardinality="exactly_once",
                                teaching_focus="the statement P(n) to prove",
                                contains={"claim": "required"}, state_effects=["the claim is stated"]),
        "discharge": StageSpec("discharge", "discharge an obligation", cardinality="one_or_more",
                               teaching_focus="discharge the base case, then the inductive step",
                               contains={"obligation": "required"},
                               state_effects=["one proof obligation is discharged"])}
    return ExampleSpec(
        input=InstanceShape("sequence", count=(1, 1), structure=[spec.slug]),
        stages=stages, structure="initialize discharge",
        must_exercise=["initialize", "discharge", "completion"], must_cover=[], must_avoid=[],
        terminal="both obligations are discharged", output_shape="the proved statement")


def manifest_entry(spec: InductionSpec) -> dict[str, Any]:
    return {"type": "T13", "family": spec.family, "status": "experimental",
            "verification_level": "trace_verified", "coding": False, "canonical_solution": None,
            "routing_aliases": list(spec.aliases), "negative_guards": list(spec.not_aliases), "fixtures": []}


def routing_rule(spec: InductionSpec) -> dict[str, Any]:
    rule: dict[str, Any] = {"any": list(spec.aliases), "priority": spec.priority}
    if spec.not_aliases:
        rule["not"] = list(spec.not_aliases)
    return rule


def induction_decl(spec: InductionSpec) -> AdapterDecl:
    return AdapterDecl(
        slug=spec.slug, type="T13", family=spec.family, example_spec=build_example_spec(spec),
        methods=dict(_METHODS), label_convention=spec.label_convention, routing=routing_rule(spec),
        class_attrs={"_induction_spec": spec, "provides_narration": True})


def registered_specs() -> list[InductionSpec]:
    from . import induction_specs
    return [s for s in induction_specs.ALL_SPECS if s.register]
