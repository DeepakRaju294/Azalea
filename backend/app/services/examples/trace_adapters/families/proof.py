"""Formal-derivation family (WORKED_EXAMPLE_ACCURACY_SPEC §15.3) — the T8b shape: a PROOF, not a computation.
Each card is a step of a mathematical argument (base case → hypothesis → inductive step → conclusion), and
progress is a growing chain of established facts, not a mutating data structure.

First member: proof by induction of a summation identity. A proof cannot be "run", but its mathematical
CONTENT can be refereed: an independent oracle checks the identity numerically for many n AND checks the one
load-bearing algebraic step, closed(k) + term(k+1) == closed(k+1), for many k. So a false identity — or an
inductive step that does not actually close — can never pass as verified.
"""
from __future__ import annotations

import random
from typing import Any, Callable, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase


class _Identity:
    def __init__(self, key: str, claim: str, claim_k: str, term: Callable[[int], int],
                 closed: Callable[[int], int], next_term: str, hyp_rhs: str, concl_rhs: str):
        self.key, self.claim, self.claim_k = key, claim, claim_k
        self.term, self.closed = term, closed
        self.next_term, self.hyp_rhs, self.concl_rhs = next_term, hyp_rhs, concl_rhs


# Each identity carries both the callable math (for the oracle) and the display strings (for the prose).
_IDENTITIES: dict[str, _Identity] = {
    "sum_first_n": _Identity(
        "sum_first_n", "1 + 2 + ... + n = n(n+1)/2", "1 + 2 + ... + k = k(k+1)/2",
        term=lambda i: i, closed=lambda n: n * (n + 1) // 2,
        next_term="(k+1)", hyp_rhs="k(k+1)/2", concl_rhs="(k+1)(k+2)/2"),
    # NOTE: spaces around every "− 1" are deliberate — the prose validator reads a hyphen-glued "2n-1" as the
    # integer -1 (not in allowed_values). "2n - 1" is read as a positive 1. (Same trap as LIS "length-1".)
    "sum_odds": _Identity(
        "sum_odds", "1 + 3 + 5 + ... + (2n - 1) = n^2", "1 + 3 + ... + (2k - 1) = k^2",
        term=lambda i: 2 * i - 1, closed=lambda n: n * n,
        next_term="(2k + 1)", hyp_rhs="k^2", concl_rhs="(k+1)^2"),
    "sum_powers_two": _Identity(
        "sum_powers_two", "1 + 2 + 4 + ... + 2^(n-1) = 2^n - 1", "1 + 2 + ... + 2^(k-1) = 2^k - 1",
        term=lambda i: 2 ** (i - 1), closed=lambda n: 2 ** n - 1,
        next_term="2^k", hyp_rhs="2^k - 1", concl_rhs="2^(k+1) - 1"),
}

_IND_CONV = {"method": "mathematical_induction", "trace_granularity": "one_proof_step"}
_IND_REQ = ["base_case", "inductive_step", "conclusion"]
_IND_INV = [{"id": "identity_and_step_valid", "scope": "every_step",
             "statement": "the identity holds for all tested n, and closed(k)+term(k+1)=closed(k+1) for all k"}]


def _identity_verifies(ident: _Identity, upto: int = 40) -> bool:
    """Independent oracle: the closed form equals the brute-force sum for every n, and the inductive step
    actually closes for every k. This is what makes the PROOF verified rather than merely well-formatted."""
    total = 0
    for n in range(1, upto + 1):
        total += ident.term(n)
        if ident.closed(n) != total:
            return False                                    # the identity itself is false
    for k in range(1, upto + 1):                            # the load-bearing algebraic step
        if ident.closed(k) + ident.term(k + 1) != ident.closed(k + 1):
            return False
    return True


class InductionProofAdapter(FamilyAdapterBase):
    slug = "induction_proof"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("identity", count=(1, 1), structure=["summation_identity"]),
        stages={
            "base_case": StageSpec(
                "base_case", "check the claim for the smallest case, n = 1",
                teaching_focus="a proof by induction stands on a verified base case",
                contains={"evaluate_both_sides": "required"}, cardinality="exactly_once",
                state_effects=["the claim is confirmed true for n = 1"]),
            "hypothesis": StageSpec(
                "hypothesis", "assume the claim holds for an arbitrary n = k",
                teaching_focus="the hypothesis is the tool the inductive step is allowed to use",
                contains={"assume_for_k": "required"}, cardinality="exactly_once",
                state_effects=["the claim is assumed for n = k"]),
            "inductive_step": StageSpec(
                "inductive_step", "use the hypothesis to prove the claim for n = k+1",
                teaching_focus="add the next term and show the right-hand side becomes the formula at k+1",
                contains={"add_next_term": "required", "simplify": "aggregated_supporting"},
                cardinality="exactly_once", state_effects=["the claim for n = k implies the claim for n = k+1"]),
            "conclusion": StageSpec(
                "conclusion", "conclude the claim holds for all n by induction",
                teaching_focus="base case + step ⇒ every n", contains={"invoke_induction": "required"},
                cardinality="exactly_once", state_effects=["the claim is proved for all n >= 1"])},
        structure="base_case, hypothesis, inductive_step, conclusion",
        must_exercise=["base_case", "inductive_step", "conclusion"], must_cover=["inductive_step"],
        must_avoid=["no_base_case"],
        terminal="the base case and the inductive step are both proved, so the claim holds for all n",
        output_shape="the proved identity")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        keys = list(_IDENTITIES)
        rng.shuffle(keys)
        for i, key in enumerate(keys):
            yield {"identity": key, "_id": f"induction_{key}_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) == 4 and bool(ev.get("base_case")) and bool(ev.get("inductive_step"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        ident = _IDENTITIES[str(example_input["identity"])]
        b1 = ident.closed(1)
        # Each card is one proof step; state accumulates the established parts of the argument.
        plan = [
            ("base_case", "base_case",
             f"Base case (n = 1): the left-hand side is {ident.term(1)}; the right-hand side of "
             f"{ident.claim} at n = 1 is {b1}. Both sides equal {b1}, so the claim holds for n = 1.",
             f"Base case verified: both sides equal {b1}.", [fact("value", b1)], b1),
            ("hypothesis", "hypothesis",
             f"Inductive hypothesis: assume the claim holds for some n = k, that is {ident.claim_k}.",
             "Hypothesis assumed for n = k.", [], None),
            ("inductive_step", "inductive_step",
             f"Inductive step (n = k+1): add the next term {ident.next_term} to both sides of the hypothesis. "
             f"The right-hand side becomes {ident.hyp_rhs} + {ident.next_term}, which simplifies to "
             f"{ident.concl_rhs} — exactly the formula with n = k+1. So the claim holds for k+1.",
             f"Right-hand side becomes {ident.concl_rhs}: the claim holds for n = k+1.", [], None),
            ("conclusion", "conclusion",
             "The base case holds and each case implies the next, so by the principle of mathematical "
             "induction the claim holds for every n >= 1.",
             f"Proved by induction: {ident.claim}.", [], None),
        ]
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        established: list[str] = []
        import re as _re
        for idx, (stage, case, reason, evr, req, check) in enumerate(plan, start=1):
            sid = f"s{idx}"
            prior = {"identity": ident.key, "established": list(established)}
            established.append(stage)
            after = {"identity": ident.key, "established": list(established)}
            evidence.setdefault(case, []).append(sid)
            allowed = sorted({int(x) for x in _re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation=stage, prior_state=prior, state_after=after,
                inputs={"stage": stage, "check_value": check},
                decision=f"establish the {stage.replace('_', ' ')}", reason=reason,
                visual_state={"kind": "proof", "established": list(established)},
                visual_delta={"established": stage}, expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": req, "forbidden_claims": []}))
        return ContractTrace(
            problem=f"Prove by mathematical induction that {ident.claim}.",
            conventions=dict(_IND_CONV), initial_state={"identity": ident.key, "established": []},
            final_answer={"claim": ident.claim, "identity": ident.key, "proven": True}, steps=steps,
            invariants=[dict(x) for x in _IND_INV], required_cases=list(_IND_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return a.get("identity") == b.get("identity") and \
            list(a.get("established") or []) == list(b.get("established") or [])

    def final_answer_entails(self, state, answer):
        est = list((state or {}).get("established") or [])
        return est == ["base_case", "hypothesis", "inductive_step", "conclusion"] and \
            (state or {}).get("identity") == (answer or {}).get("identity")

    def invariant_holds(self, inv, state):
        if inv.get("id") == "identity_and_step_valid":
            key = (state or {}).get("identity")
            ident = _IDENTITIES.get(str(key))
            return ident is not None and _identity_verifies(ident)   # independent numeric referee
        return True

    def validate_step_shape(self, step):
        ok = ("base_case", "hypothesis", "inductive_step", "conclusion")
        return [] if step.operation in ok else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        check = step.inputs.get("check_value")
        if check is None:
            return []
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        return [] if str(check) in prose else [("base_value_not_stated", str(check))]
