"""Dynamic-programming family (WORKED_EXAMPLE_ACCURACY_SPEC §15.3) — problems solved by filling a table of
sub-answers, each cell computed from earlier cells via a recurrence. The teaching arc is "one card per cell:
here is the sub-answer, and here is the earlier cell(s) it is built from."

First member: longest increasing subsequence (the canonical O(n^2) 1-D DP). Its correctness is refereed by an
INDEPENDENT brute-force oracle (recompute the true DP straight from the array), not by trusting the trace's
own stored table — so a table-assembly bug can never pass as verified.
"""
from __future__ import annotations

import random
import re
from typing import Any, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase


def _true_lis_dp(arr: list[int]) -> list[int]:
    """The INDEPENDENT oracle: the correct dp array where dp[i] = length of the longest strictly-increasing
    subsequence of arr[0..i] ending exactly at arr[i]. Recomputed from the array alone (never reads the
    trace's stored table), so it refereess the adapter's output rather than echoing it."""
    dp = [1] * len(arr)
    for i in range(len(arr)):
        for j in range(i):
            if arr[j] < arr[i] and dp[j] + 1 > dp[i]:
                dp[i] = dp[j] + 1
    return dp


_LIS_CONV = {"algorithm_variant": "lis_n_squared_dp", "subsequence": "strictly_increasing",
             "cell_meaning": "dp[i] = longest increasing subsequence ending at index i",
             "trace_granularity": "one_cell"}
_LIS_REQ = ["fresh_start", "extend_from_predecessor", "completion"]
_LIS_INV = [{"id": "dp_matches_true_lis", "scope": "every_step",
             "statement": "every filled cell equals the true longest-increasing-subsequence-ending-here"}]


class LongestIncreasingSubsequenceAdapter(FamilyAdapterBase):
    slug = "longest_increasing_subsequence"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(5, 7), value_range=(1, 40), structure=["distinct", "unsorted"]),
        stages={"fill_cell": StageSpec(
            "fill_cell", "compute one dp cell — the longest increasing subsequence ending at this element",
            teaching_focus="each cell reuses the best earlier cell it can extend; the answer is the largest cell",
            contains={"scan_predecessors": "internal", "extend_best": "required"},
            state_effects=["dp grows by one cell; each cell is a solved sub-answer later cells build on"])},
        structure="fill_cell left to right; the answer is the maximum cell",
        must_exercise=["fresh_start", "extend_from_predecessor", "completion"],
        must_cover=["extend_from_predecessor"], must_avoid=["sorted_descending"],
        terminal="every cell is filled, so the largest cell is the length of the longest increasing subsequence",
        output_shape="the length of the longest increasing subsequence")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(5, 7)
            arr = rng.sample(range(1, 40), n)
            yield {"array": arr, "_id": f"lis_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return (len(trace.steps) >= 4 and bool(ev.get("fresh_start"))
                and bool(ev.get("extend_from_predecessor")))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        arr = list(example_input["array"])
        n = len(arr)
        dp: list[int] = []
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        for i in range(n):
            v = arr[i]
            best_len, best_j = 0, -1                        # best earlier cell we can extend
            for j in range(i):
                if arr[j] < v and dp[j] > best_len:
                    best_len, best_j = dp[j], j
            dp_i = best_len + 1
            prior = {"array": list(arr), "dp": list(dp), "filled": i}
            dp.append(dp_i)
            after = {"array": list(arr), "dp": list(dp), "filled": i + 1}
            sid = f"s{i + 1}"
            if best_j >= 0:
                reason = (f"dp[{i}] for value {v}: among earlier values smaller than {v}, the longest "
                          f"increasing subsequence ends at {arr[best_j]} with length {best_len}, so extend "
                          f"it — dp[{i}] = {best_len} + 1 = {dp_i}.")
                evr = (f"dp[{i}] = {dp_i} (extend the length {best_len} run ending at {arr[best_j]}); "
                       f"dp so far {dp}.")
                evidence.setdefault("extend_from_predecessor", []).append(sid)
            else:
                reason = (f"dp[{i}] for value {v}: no earlier value is smaller than {v}, so the longest "
                          f"increasing subsequence ending here is just {v} itself — dp[{i}] = 1.")
                evr = f"dp[{i}] = 1 (a fresh start — nothing smaller precedes {v}); dp so far {dp}."
                evidence.setdefault("fresh_start", []).append(sid)
            allowed = sorted(set(arr) | {int(x) for x in re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation="fill_cell", prior_state=prior, state_after=after,
                inputs={"index": i, "value": v, "dp_value": dp_i, "predecessor_index": best_j},
                decision=f"dp[{i}] = {dp_i}", reason=reason,
                visual_state={"kind": "array", "array": list(arr), "dp": list(dp), "active": i},
                visual_delta={"cell": i, "dp_value": dp_i, "predecessor": best_j},
                expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": [fact("dp_value", dp_i)],
                       "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Find the length of the longest strictly increasing subsequence of {arr} "
                     f"using dynamic programming (dp[i] = longest increasing subsequence ending at index i)."),
            conventions=dict(_LIS_CONV), initial_state={"array": list(arr), "dp": [], "filled": 0},
            final_answer={"lis_length": max(dp) if dp else 0}, steps=steps,
            invariants=[dict(x) for x in _LIS_INV], required_cases=list(_LIS_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return (list(a.get("array") or []) == list(b.get("array") or [])
                and list(a.get("dp") or []) == list(b.get("dp") or [])
                and a.get("filled") == b.get("filled"))

    def final_answer_entails(self, state, answer):
        dp = (state or {}).get("dp") or []
        return bool(dp) and max(dp) == (answer or {}).get("lis_length")

    def invariant_holds(self, inv, state):
        if inv.get("id") == "dp_matches_true_lis":
            arr = (state or {}).get("array") or []
            dp = (state or {}).get("dp") or []
            true_dp = _true_lis_dp(list(arr))
            return list(dp) == true_dp[:len(dp)]            # every FILLED cell matches the independent oracle
        return True

    def validate_step_shape(self, step):
        return [] if step.operation == "fill_cell" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        dv = str(step.inputs["dp_value"])
        return [] if dv in prose else [("dp_value_not_stated", dv)]
