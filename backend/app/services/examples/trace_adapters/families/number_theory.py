"""Number-theory family (WORKED_EXAMPLE_ACCURACY_SPEC §15.3, catalog A9). Members: sieve of Eratosthenes.

First member: the Sieve of Eratosthenes (T8a incremental construction — cross composites out of a fixed range
one prime at a time). Refereed by an INDEPENDENT primality oracle (trial division), so a crossed-out prime or
a surviving composite can never pass as verified.
"""
from __future__ import annotations

import random
import re
from typing import Any, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase


def _is_prime(x: int) -> bool:
    if x < 2:
        return False
    d = 2
    while d * d <= x:
        if x % d == 0:
            return False
        d += 1
    return True


_SIEVE_CONV = {"algorithm": "sieve_of_eratosthenes", "rule": "the first uncrossed number is prime; cross out "
               "its multiples", "trace_granularity": "one_prime"}
_SIEVE_REQ = ["mark_prime", "completion"]
_SIEVE_INV = [{"id": "crossed_are_composite", "scope": "every_step",
               "statement": "every crossed-out number is composite (no prime is ever crossed)"}]


class SieveAdapter(FamilyAdapterBase):
    slug = "sieve_of_eratosthenes"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(1, 1), value_range=(20, 30), structure=["range_upper_bound"]),
        stages={"sieve": StageSpec(
            "sieve", "take the next uncrossed number as prime and cross out its multiples",
            teaching_focus="the smallest uncrossed number must be prime; its multiples are composite",
            contains={"identify_prime": "required", "cross_multiples": "aggregated_supporting"},
            state_effects=["one prime is confirmed; its still-standing multiples are crossed as composite"])},
        structure="sieve+ while p*p <= n; the survivors are the primes",
        must_exercise=["mark_prime", "completion"], must_cover=["mark_prime"], must_avoid=["n_below_4"],
        terminal="every prime up to sqrt(n) has crossed its multiples, so the survivors are exactly the primes",
        output_shape="the list of primes up to n")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(60):
            yield {"n": rng.randint(20, 30), "_id": f"sieve_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        return len(trace.steps) >= 2 and bool(trace.case_evidence.get("mark_prime"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        n = int(example_input["n"])
        is_prime = [True] * (n + 1)
        is_prime[0] = is_prime[1] = False
        crossed: list[int] = []
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        idx = 0
        p = 2
        while p * p <= n:
            if is_prime[p]:
                idx += 1
                sid = f"s{idx}"
                prior = {"crossed": sorted(crossed)}
                newly = []
                m = p * p
                while m <= n:
                    if is_prime[m]:
                        is_prime[m] = False
                        crossed.append(m)
                        newly.append(m)
                    m += p
                after = {"crossed": sorted(crossed)}
                shown = ", ".join(map(str, newly))
                reason = (f"{p} is still uncrossed, so {p} is prime. Starting at {p}x{p} = {p * p}, cross out "
                          f"every multiple of {p} that still stands — {shown} — because each is divisible by "
                          f"{p} and therefore composite.")
                evr = f"Cross out the multiples of {p}: {shown}."
                evidence.setdefault("mark_prime", []).append(sid)
                allowed = sorted(set(range(n + 1)) | {int(x) for x in re.findall(r"\d+", reason + " " + evr)})
                steps.append(Step(
                    id=sid, operation="sieve", prior_state=prior, state_after=after,
                    inputs={"prime": p, "crossed_now": list(newly)},
                    decision=f"{p} is prime; cross out its multiples", reason=reason,
                    visual_state={"kind": "array", "array": list(range(n + 1)), "crossed": sorted(crossed),
                                  "active": p},
                    visual_delta={"prime": p, "crossed": list(newly)},
                    expected_visible_result=evr,
                    facts={"allowed_values": allowed, "required_facts": [fact("prime", p)],
                           "forbidden_claims": []}))
            p += 1
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        primes = [i for i in range(2, n + 1) if is_prime[i]]
        return ContractTrace(
            problem=(f"Find all prime numbers up to {n} using the Sieve of Eratosthenes."),
            conventions=dict(_SIEVE_CONV), initial_state={"crossed": []},
            final_answer={"primes": primes}, steps=steps,
            invariants=[dict(x) for x in _SIEVE_INV], required_cases=list(_SIEVE_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        # the learner-facing state is the crossed-out set; the loop counter is an implementation detail that
        # skips non-prime p (no card), so it is deliberately NOT part of state equivalence.
        return sorted((a or {}).get("crossed") or []) == sorted((b or {}).get("crossed") or [])

    def final_answer_entails(self, state, answer):
        # the surviving numbers (2..n not crossed) are exactly the primes
        crossed = set((state or {}).get("crossed") or [])
        primes = list((answer or {}).get("primes") or [])
        if not primes:
            return False
        n = max(primes + list(crossed))
        survivors = [i for i in range(2, n + 1) if i not in crossed]
        return survivors == primes

    def invariant_holds(self, inv, state):
        if inv.get("id") == "crossed_are_composite":
            return all(not _is_prime(int(c)) for c in ((state or {}).get("crossed") or []))
        return True

    def validate_step_shape(self, step):
        return [] if step.operation == "sieve" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        pv = str(step.inputs["prime"])
        return [] if pv in prose else [("prime_not_stated", pv)]
