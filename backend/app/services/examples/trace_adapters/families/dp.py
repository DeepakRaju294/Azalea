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


# --- coin change (minimum coins) — T5's 2nd DP pilot: a MIN recurrence with a "reach from a-c" dependency
#     (dp[a] = 1 + min over coins c<=a of dp[a-c]), distinct from LIS's max-over-predecessors shape. -----------
def _true_min_coins(coins: list[int], amount: int) -> list[int]:
    """Independent oracle: the correct dp table where dp[a] = fewest coins to make a (a large sentinel if
    unreachable). Recomputed from the coins alone — refereess the trace's table, never echoes it."""
    inf = amount + 1
    dp = [0] + [inf] * amount
    for a in range(1, amount + 1):
        for c in coins:
            if c <= a and dp[a - c] + 1 < dp[a]:
                dp[a] = dp[a - c] + 1
    return dp


_CC_CONV = {"algorithm_variant": "coin_change_min", "recurrence": "dp[a] = 1 + min(dp[a-c] for coin c <= a)",
            "cell_meaning": "dp[a] = fewest coins that sum to a", "trace_granularity": "one_cell"}
_CC_REQ = ["single_coin", "build_from_subproblem", "completion"]
_CC_INV = [{"id": "dp_matches_true_min_coins", "scope": "every_step",
            "statement": "every filled cell equals the true minimum coin count for that amount"}]


class CoinChangeAdapter(FamilyAdapterBase):
    slug = "coin_change"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(3, 3), value_range=(1, 6), structure=["coin_denominations"]),
        stages={"fill_cell": StageSpec(
            "fill_cell", "compute one dp cell — the fewest coins for this amount",
            teaching_focus="each amount reuses the best already-solved smaller amount, plus one coin",
            contains={"try_each_coin": "internal", "take_best_plus_one": "required"},
            state_effects=["dp grows by one amount; each cell is a solved sub-answer larger amounts build on"])},
        structure="fill_cell for amounts 1..A; the answer is dp[A]",
        must_exercise=["single_coin", "build_from_subproblem", "completion"],
        must_cover=["build_from_subproblem"], must_avoid=["single_denomination"],
        terminal="every amount up to the target is solved, so dp[target] is the fewest coins",
        output_shape="the fewest coins that make the target amount")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            coins = sorted({1} | set(rng.sample([2, 3, 4, 5, 6], 2)))   # always include 1 -> every amount reachable
            amount = rng.randint(6, 9)
            yield {"coins": coins, "amount": amount, "_id": f"coin_change_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return (len(trace.steps) >= 4 and bool(ev.get("single_coin"))
                and bool(ev.get("build_from_subproblem")))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        coins = sorted(int(c) for c in example_input["coins"])
        amount = int(example_input["amount"])
        dp = [0]
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        for a in range(1, amount + 1):
            best, best_c = amount + 1, None
            for c in coins:
                if c <= a and dp[a - c] + 1 < best:
                    best, best_c = dp[a - c] + 1, c
            prior = {"dp": list(dp), "filled": a, "coins": coins, "amount": amount}
            dp.append(best)
            after = {"dp": list(dp), "filled": a + 1, "coins": coins, "amount": amount}
            sid = f"s{a}"
            if best_c == a:                                    # a single coin equals the amount exactly
                reason = (f"dp[{a}] (fewest coins for {a}): the coin {a} equals the amount exactly, so one "
                          f"coin suffices — dp[{a}] = 1.")
                evr = f"dp[{a}] = 1 (the single coin {a}); dp so far {dp}."
                evidence.setdefault("single_coin", []).append(sid)
            else:
                reason = (f"dp[{a}] (fewest coins for {a}): the best choice is coin {best_c}, leaving {a - best_c}, "
                          f"which already takes dp[{a - best_c}] = {dp[a - best_c]} coins — so "
                          f"dp[{a}] = {dp[a - best_c]} + 1 = {best}.")
                evr = f"dp[{a}] = {best} (coin {best_c} plus the best way to make {a - best_c}); dp so far {dp}."
                evidence.setdefault("build_from_subproblem", []).append(sid)
            allowed = sorted({int(x) for x in re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation="fill_cell", prior_state=prior, state_after=after,
                inputs={"amount": a, "dp_value": best, "coin": best_c},
                decision=f"dp[{a}] = {best}", reason=reason,
                visual_state={"kind": "array", "array": list(dp), "active": a},
                visual_delta={"cell": a, "dp_value": best, "coin": best_c},
                expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": [fact("dp_value", best)],
                       "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Find the fewest coins from denominations {coins} that sum to {amount}, using dynamic "
                     f"programming (dp[a] = 1 + the smallest dp[a - coin] over coins that fit)."),
            conventions=dict(_CC_CONV),
            initial_state={"dp": [0], "filled": 1, "coins": coins, "amount": amount},
            final_answer={"min_coins": dp[amount]}, steps=steps,
            invariants=[dict(x) for x in _CC_INV], required_cases=list(_CC_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return list(a.get("dp") or []) == list(b.get("dp") or []) and a.get("filled") == b.get("filled")

    def final_answer_entails(self, state, answer):
        dp = (state or {}).get("dp") or []
        return bool(dp) and dp[-1] == (answer or {}).get("min_coins")

    def invariant_holds(self, inv, state):
        if inv.get("id") == "dp_matches_true_min_coins":
            dp = list((state or {}).get("dp") or [])
            coins = list((state or {}).get("coins") or [])
            amount = (state or {}).get("amount") or 0
            true = _true_min_coins(coins, amount)             # independent oracle
            return dp == true[:len(dp)]                        # every FILLED cell matches the true min table
        return True

    def validate_step_shape(self, step):
        return [] if step.operation == "fill_cell" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        dv = str(step.inputs["dp_value"])
        return [] if dv in prose else [("dp_value_not_stated", dv)]


# ======================================================================================================
# HOUSE ROBBER — max non-adjacent sum (a canonical 1-D DP; interview classic)
# ======================================================================================================
def _true_house_robber(nums: list[int]) -> list[int]:
    """Independent oracle: the correct dp table where dp[i] = max loot robbing houses 0..i with no two
    adjacent. Recomputed straight from `nums`, so it referees the trace's table rather than echoing it."""
    dp: list[int] = []
    for i, v in enumerate(nums):
        if i == 0:
            dp.append(v)
        elif i == 1:
            dp.append(max(nums[0], nums[1]))
        else:
            dp.append(max(dp[i - 1], dp[i - 2] + v))
    return dp


_HR_CONV = {"algorithm_variant": "house_robber", "recurrence": "dp[i] = max(dp[i-1], dp[i-2] + nums[i])",
            "cell_meaning": "dp[i] = most money robbing houses 0..i without robbing two adjacent",
            "trace_granularity": "one_cell"}
_HR_REQ = ["skip_house", "rob_house", "completion"]
_HR_INV = [{"id": "dp_matches_true_house_robber", "scope": "every_step",
            "statement": "every filled cell equals the true maximum non-adjacent loot up to that house"}]


class HouseRobberAdapter(FamilyAdapterBase):
    slug = "house_robber"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(5, 5), value_range=(1, 9), structure=["house_values"]),
        stages={"fill_cell": StageSpec(
            "fill_cell", "compute one dp cell — the best loot up to this house",
            teaching_focus="each house either extends the best skipping it, or robs it plus the best two back",
            contains={"compare_rob_vs_skip": "required"},
            state_effects=["dp grows by one house; each cell is the best solved answer later houses build on"])},
        structure="fill_cell for houses 0..n-1; the answer is dp[n-1]",
        must_exercise=["skip_house", "rob_house", "completion"],
        must_cover=["rob_house"], must_avoid=[],
        terminal="every house is solved, so the last cell holds the most money that can be robbed",
        output_shape="the maximum money robbable without robbing two adjacent houses")

    def candidates(self, seed: int):
        rng = random.Random(seed)
        for i in range(80):
            nums = [rng.randint(1, 9) for _ in range(5)]
            yield {"nums": nums, "_id": f"house_robber_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return (len(trace.steps) >= 4 and bool(ev.get("rob_house")) and bool(ev.get("skip_house")))

    def reference(self, example_input, *, candidate_id: str = "", attempt: int = 1, seed: int = 0):
        nums = [int(x) for x in example_input["nums"]]
        dp: list[int] = []
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        for i, v in enumerate(nums):
            prior = {"dp": list(dp), "filled": i, "nums": nums}
            if i == 0:
                best, kind = v, "rob_house"
                reason = f"dp[0] (best up to house 0): only house 0 is available, so rob it — dp[0] = {v}."
                evr = f"dp[0] = {v} (rob house 0); dp so far {dp + [best]}."
            elif i == 1:
                if nums[1] >= nums[0]:
                    best, kind = nums[1], "rob_house"
                    reason = (f"dp[1] (best up to house 1): houses 0 and 1 are adjacent, so take the larger — "
                              f"house 1 has {nums[1]} >= {nums[0]}, dp[1] = {nums[1]}.")
                else:
                    best, kind = nums[0], "skip_house"
                    reason = (f"dp[1] (best up to house 1): houses 0 and 1 are adjacent, so take the larger — "
                              f"house 0 has {nums[0]} > {nums[1]}, dp[1] = {nums[0]}.")
                evr = f"dp[1] = {best} (the larger of houses 0 and 1); dp so far {dp + [best]}."
            else:
                rob = dp[i - 2] + v
                skip = dp[i - 1]
                if rob > skip:
                    best, kind = rob, "rob_house"
                    reason = (f"dp[{i}] (best up to house {i}): robbing house {i} adds {v} to dp[{i - 2}] = "
                              f"{dp[i - 2]}, giving {rob}, which beats skipping it (dp[{i - 1}] = {skip}) — "
                              f"dp[{i}] = {rob}.")
                    evr = f"dp[{i}] = {rob} (rob house {i}: {v} + dp[{i - 2}]); dp so far {dp + [best]}."
                else:
                    best, kind = skip, "skip_house"
                    reason = (f"dp[{i}] (best up to house {i}): skipping house {i} keeps dp[{i - 1}] = {skip}, "
                              f"which is at least robbing it ({v} + dp[{i - 2}] = {rob}) — dp[{i}] = {skip}.")
                    evr = f"dp[{i}] = {skip} (skip house {i}, keep dp[{i - 1}]); dp so far {dp + [best]}."
            dp.append(best)
            after = {"dp": list(dp), "filled": i + 1, "nums": nums}
            sid = f"s{i + 1}"
            evidence.setdefault(kind, []).append(sid)
            allowed = sorted({int(x) for x in re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation="fill_cell", prior_state=prior, state_after=after,
                inputs={"house": i, "dp_value": best},
                decision=f"dp[{i}] = {best}", reason=reason,
                visual_state={"kind": "array", "array": list(dp), "active": i},
                visual_delta={"cell": i, "dp_value": best},
                expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": [fact("dp_value", best)],
                       "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Given house values {nums}, find the most money you can rob without robbing two adjacent "
                     f"houses, using dynamic programming (dp[i] = max(dp[i-1], dp[i-2] + nums[i]))."),
            conventions=dict(_HR_CONV),
            initial_state={"dp": [], "filled": 0, "nums": nums},
            final_answer={"max_loot": dp[-1]}, steps=steps,
            invariants=[dict(x) for x in _HR_INV], required_cases=list(_HR_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return list(a.get("dp") or []) == list(b.get("dp") or []) and a.get("filled") == b.get("filled")

    def final_answer_entails(self, state, answer):
        dp = (state or {}).get("dp") or []
        return bool(dp) and dp[-1] == (answer or {}).get("max_loot")

    def invariant_holds(self, inv, state):
        if inv.get("id") == "dp_matches_true_house_robber":
            dp = list((state or {}).get("dp") or [])
            nums = list((state or {}).get("nums") or [])
            true = _true_house_robber(nums)
            return dp == true[:len(dp)]
        return True

    def validate_step_shape(self, step):
        return [] if step.operation == "fill_cell" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        dv = str(step.inputs["dp_value"])
        return [] if dv in prose else [("dp_value_not_stated", dv)]


# ======================================================================================================
# MAXIMUM SUBARRAY (Kadane) — largest contiguous sum (canonical 1-D DP; the answer is max(dp), not dp[-1])
# ======================================================================================================
def _true_max_subarray(nums: list[int]) -> list[int]:
    """Independent oracle: dp[i] = the largest sum of a contiguous subarray ENDING at i. Recomputed straight
    from `nums`, refereeing the trace's table rather than echoing it. The answer is max(dp)."""
    dp: list[int] = []
    for i, v in enumerate(nums):
        dp.append(v if i == 0 else max(v, dp[i - 1] + v))
    return dp


_MS_CONV = {"algorithm_variant": "kadane", "recurrence": "dp[i] = max(nums[i], dp[i-1] + nums[i])",
            "cell_meaning": "dp[i] = largest contiguous-subarray sum ending at index i",
            "answer": "max over all dp[i]", "trace_granularity": "one_cell"}
_MS_REQ = ["restart", "extend", "completion"]
_MS_INV = [{"id": "dp_matches_true_max_subarray", "scope": "every_step",
            "statement": "every filled cell equals the true best subarray sum ending at that index"}]


class MaxSubarrayAdapter(FamilyAdapterBase):
    slug = "max_subarray"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(5, 5), value_range=(-5, 6), structure=["array_values"]),
        stages={"fill_cell": StageSpec(
            "fill_cell", "compute one dp cell — the best subarray sum ending here",
            teaching_focus="either extend the running sum, or restart at this element when the running sum is negative",
            contains={"extend_or_restart": "required"},
            state_effects=["dp grows by one index; the running best is the max cell so far"])},
        structure="fill_cell for indices 0..n-1; the answer is max(dp)",
        must_exercise=["restart", "extend", "completion"],
        must_cover=["extend"], must_avoid=[],
        terminal="every prefix is solved, so max(dp) is the largest contiguous subarray sum",
        output_shape="the largest sum of any contiguous subarray")

    def candidates(self, seed: int):
        rng = random.Random(seed)
        for i in range(120):
            nums = [rng.randint(-5, 6) for _ in range(5)]
            yield {"nums": nums, "_id": f"max_subarray_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return (len(trace.steps) >= 4 and bool(ev.get("extend")) and bool(ev.get("restart")))

    def reference(self, example_input, *, candidate_id: str = "", attempt: int = 1, seed: int = 0):
        nums = [int(x) for x in example_input["nums"]]
        dp: list[int] = []
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        for i, v in enumerate(nums):
            prior = {"dp": list(dp), "filled": i, "nums": nums}
            if i == 0:
                best, kind = v, "restart"
                reason = f"dp[0] (best subarray ending at 0): start a new subarray at index 0 — dp[0] = {v}."
                evr = f"dp[0] = {v} (start here); dp so far {dp + [best]}."
            else:
                extend = dp[i - 1] + v
                if extend > v:
                    best, kind = extend, "extend"
                    reason = (f"dp[{i}] (best subarray ending at {i}): the running sum dp[{i - 1}] = {dp[i - 1]} "
                              f"is worth extending, so add {v} to get {extend} (better than restarting at {v}) — "
                              f"dp[{i}] = {extend}.")
                    evr = f"dp[{i}] = {extend} (extend: dp[{i - 1}] + {v}); dp so far {dp + [best]}."
                else:
                    best, kind = v, "restart"
                    reason = (f"dp[{i}] (best subarray ending at {i}): the running sum dp[{i - 1}] = {dp[i - 1]} "
                              f"would only drag {v} down, so restart at {v} — dp[{i}] = {v}.")
                    evr = f"dp[{i}] = {v} (restart at index {i}); dp so far {dp + [best]}."
            dp.append(best)
            after = {"dp": list(dp), "filled": i + 1, "nums": nums}
            sid = f"s{i + 1}"
            evidence.setdefault(kind, []).append(sid)
            allowed = sorted({int(x) for x in re.findall(r"-?\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation="fill_cell", prior_state=prior, state_after=after,
                inputs={"index": i, "dp_value": best},
                decision=f"dp[{i}] = {best}", reason=reason,
                visual_state={"kind": "array", "array": list(dp), "active": i},
                visual_delta={"cell": i, "dp_value": best},
                expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": [fact("dp_value", best)],
                       "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Given the array {nums}, find the largest sum of any contiguous subarray using dynamic "
                     f"programming (Kadane: dp[i] = max(nums[i], dp[i-1] + nums[i]); answer = max(dp))."),
            conventions=dict(_MS_CONV),
            initial_state={"dp": [], "filled": 0, "nums": nums},
            final_answer={"max_sum": max(dp)}, steps=steps,
            invariants=[dict(x) for x in _MS_INV], required_cases=list(_MS_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return list(a.get("dp") or []) == list(b.get("dp") or []) and a.get("filled") == b.get("filled")

    def final_answer_entails(self, state, answer):
        dp = (state or {}).get("dp") or []
        return bool(dp) and max(dp) == (answer or {}).get("max_sum")

    def invariant_holds(self, inv, state):
        if inv.get("id") == "dp_matches_true_max_subarray":
            dp = list((state or {}).get("dp") or [])
            nums = list((state or {}).get("nums") or [])
            true = _true_max_subarray(nums)
            return dp == true[:len(dp)]
        return True

    def validate_step_shape(self, step):
        return [] if step.operation == "fill_cell" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        dv = str(step.inputs["dp_value"])
        return [] if dv in prose else [("dp_value_not_stated", dv)]


# ======================================================================================================
# ROD CUTTING — max revenue cutting a rod into priced pieces (1-D DP; max-over-first-cut, like coin change)
# ======================================================================================================
def _true_rod_cutting(prices: list[int], L: int) -> list[int]:
    """Independent oracle: dp[l] = max revenue obtainable from a rod of length l given `prices` (prices[k] =
    value of a piece of length k+1). Recomputed straight from the prices, refereeing the trace's table."""
    dp = [0] * (L + 1)
    for l in range(1, L + 1):
        best = 0
        for c in range(1, min(l, len(prices)) + 1):
            best = max(best, prices[c - 1] + dp[l - c])
        dp[l] = best
    return dp


_RC_CONV = {"algorithm_variant": "rod_cutting", "recurrence": "dp[l] = max(prices[c-1] + dp[l-c] for c in 1..l)",
            "cell_meaning": "dp[l] = most revenue from a rod of length l",
            "trace_granularity": "one_cell"}
_RC_REQ = ["single_piece", "combine_pieces", "completion"]
_RC_INV = [{"id": "dp_matches_true_rod_cutting", "scope": "every_step",
            "statement": "every filled cell equals the true maximum revenue for that rod length"}]


class RodCuttingAdapter(FamilyAdapterBase):
    slug = "rod_cutting"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(4, 4), value_range=(1, 9), structure=["piece_prices"]),
        stages={"fill_cell": StageSpec(
            "fill_cell", "compute one dp cell — the best revenue for this rod length",
            teaching_focus="each length tries every first cut, then reuses the best revenue for the remainder",
            contains={"try_each_first_cut": "internal", "take_best": "required"},
            state_effects=["dp grows by one length; each cell is a solved sub-answer longer rods build on"])},
        structure="fill_cell for lengths 1..L; the answer is dp[L]",
        must_exercise=["single_piece", "combine_pieces", "completion"],
        must_cover=["combine_pieces"], must_avoid=[],
        terminal="every length up to the rod is solved, so dp[L] is the most revenue",
        output_shape="the maximum revenue from cutting the rod")

    def candidates(self, seed: int):
        rng = random.Random(seed)
        for i in range(120):
            L = rng.randint(4, 5)
            prices = [rng.randint(1, 9) for _ in range(L)]
            yield {"prices": prices, "L": L, "_id": f"rod_cutting_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return (len(trace.steps) >= 3 and bool(ev.get("single_piece")) and bool(ev.get("combine_pieces")))

    def reference(self, example_input, *, candidate_id: str = "", attempt: int = 1, seed: int = 0):
        prices = [int(x) for x in example_input["prices"]]
        L = int(example_input["L"])
        dp = [0]
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        for l in range(1, L + 1):
            best, best_c = 0, 0
            for c in range(1, min(l, len(prices)) + 1):
                cand = prices[c - 1] + dp[l - c]
                if cand > best:
                    best, best_c = cand, c
            prior = {"dp": list(dp), "filled": l, "prices": prices, "L": L}
            dp.append(best)
            after = {"dp": list(dp), "filled": l + 1, "prices": prices, "L": L}
            sid = f"s{l}"
            if best_c == l:
                kind = "single_piece"
                reason = (f"dp[{l}] (most revenue from length {l}): the best is one uncut piece of length {l}, "
                          f"worth {prices[l - 1]} — dp[{l}] = {best}.")
                evr = f"dp[{l}] = {best} (one piece of length {l}); dp so far {dp}."
            else:
                kind = "combine_pieces"
                reason = (f"dp[{l}] (most revenue from length {l}): the best first cut is length {best_c} "
                          f"(worth {prices[best_c - 1]}), leaving {l - best_c}, whose best is dp[{l - best_c}] = "
                          f"{dp[l - best_c]} — dp[{l}] = {prices[best_c - 1]} + {dp[l - best_c]} = {best}.")
                evr = (f"dp[{l}] = {best} (cut {best_c} worth {prices[best_c - 1]} plus the best for "
                       f"{l - best_c}); dp so far {dp}.")
            evidence.setdefault(kind, []).append(sid)
            allowed = sorted({int(x) for x in re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation="fill_cell", prior_state=prior, state_after=after,
                inputs={"length": l, "dp_value": best, "first_cut": best_c},
                decision=f"dp[{l}] = {best}", reason=reason,
                visual_state={"kind": "array", "array": list(dp), "active": l},
                visual_delta={"cell": l, "dp_value": best, "first_cut": best_c},
                expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": [fact("dp_value", best)],
                       "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Given piece prices {prices} (price of length k is prices[k-1]) and a rod of length {L}, "
                     f"find the maximum revenue using dynamic programming (dp[l] = max over first cut c of "
                     f"prices[c-1] + dp[l-c])."),
            conventions=dict(_RC_CONV),
            initial_state={"dp": [0], "filled": 1, "prices": prices, "L": L},
            final_answer={"max_revenue": dp[L]}, steps=steps,
            invariants=[dict(x) for x in _RC_INV], required_cases=list(_RC_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return list(a.get("dp") or []) == list(b.get("dp") or []) and a.get("filled") == b.get("filled")

    def final_answer_entails(self, state, answer):
        dp = (state or {}).get("dp") or []
        return bool(dp) and dp[-1] == (answer or {}).get("max_revenue")

    def invariant_holds(self, inv, state):
        if inv.get("id") == "dp_matches_true_rod_cutting":
            dp = list((state or {}).get("dp") or [])
            prices = list((state or {}).get("prices") or [])
            L = (state or {}).get("L") or 0
            true = _true_rod_cutting(prices, L)
            return dp == true[:len(dp)]
        return True

    def validate_step_shape(self, step):
        return [] if step.operation == "fill_cell" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        dv = str(step.inputs["dp_value"])
        return [] if dv in prose else [("dp_value_not_stated", dv)]


# ======================================================================================================
# EDIT DISTANCE (Levenshtein) — the canonical 2-D DP; a GRID table filled cell by cell (match vs. edit)
# ======================================================================================================
def _true_edit_distance(s: str, t: str) -> list[list[int]]:
    """Independent oracle: the full (m+1)x(n+1) Levenshtein table. Recomputed straight from the strings, so it
    referees the trace's grid rather than echoing it. Answer = table[m][n]."""
    m, n = len(s), len(t)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s[i - 1] == t[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp


def _base_grid(m: int, n: int) -> list[list[int]]:
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    return dp


_ED_CONV = {"algorithm_variant": "levenshtein",
            "recurrence": "match: dp[i][j]=dp[i-1][j-1]; else 1+min(delete, insert, replace)",
            "cell_meaning": "dp[i][j] = edit distance between the first i and first j characters",
            "trace_granularity": "one_cell"}
_ED_REQ = ["match", "edit", "completion"]
_ED_INV = [{"id": "grid_matches_true_edit_distance", "scope": "every_step",
            "statement": "every filled cell equals the true Levenshtein distance for that prefix pair"}]


class EditDistanceAdapter(FamilyAdapterBase):
    slug = "edit_distance"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("strings", count=(2, 2), structure=["source_string", "target_string"]),
        stages={"fill_cell": StageSpec(
            "fill_cell", "compute one dp cell — the edit distance for this prefix pair",
            teaching_focus="matching characters copy the diagonal; otherwise take 1 + the cheapest of the three neighbors",
            contains={"match_or_min_of_three": "required"},
            state_effects=["one grid cell is filled; later cells build on the three already-solved neighbors"])},
        structure="fill_cell for inner cells (i,j); the answer is dp[m][n]",
        must_exercise=["match", "edit", "completion"],
        must_cover=["edit"], must_avoid=[],
        terminal="every prefix pair is solved, so dp[m][n] is the edit distance",
        output_shape="the minimum number of edits to turn the source into the target")

    def candidates(self, seed: int):
        rng = random.Random(seed)
        alpha = "abc"
        for i in range(160):
            s = "".join(rng.choice(alpha) for _ in range(3))
            t = "".join(rng.choice(alpha) for _ in range(3))
            yield {"s": s, "t": t, "_id": f"edit_distance_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return (len(trace.steps) >= 4 and bool(ev.get("match")) and bool(ev.get("edit")))

    def reference(self, example_input, *, candidate_id: str = "", attempt: int = 1, seed: int = 0):
        s, t = str(example_input["s"]), str(example_input["t"])
        m, n = len(s), len(t)
        dp = _base_grid(m, n)
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        filled = 0
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                prior = {"dp": [row[:] for row in dp], "filled": filled, "s": s, "t": t}
                if s[i - 1] == t[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                    kind = "match"
                    reason = (f"dp[{i}][{j}]: source '{s[i - 1]}' equals target '{t[j - 1]}', so copy the diagonal "
                              f"dp[{i - 1}][{j - 1}] = {dp[i - 1][j - 1]} — dp[{i}][{j}] = {dp[i][j]}.")
                    evr = f"dp[{i}][{j}] = {dp[i][j]} (match '{s[i - 1]}'; copy the diagonal)."
                else:
                    dele, ins, rep = dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]
                    dp[i][j] = 1 + min(dele, ins, rep)
                    kind = "edit"
                    reason = (f"dp[{i}][{j}]: '{s[i - 1]}' != '{t[j - 1]}', so 1 + the cheapest of delete "
                              f"dp[{i - 1}][{j}] = {dele}, insert dp[{i}][{j - 1}] = {ins}, replace "
                              f"dp[{i - 1}][{j - 1}] = {rep} — dp[{i}][{j}] = {dp[i][j]}.")
                    evr = f"dp[{i}][{j}] = {dp[i][j]} (edit: 1 + min({dele}, {ins}, {rep}))."
                filled += 1
                after = {"dp": [row[:] for row in dp], "filled": filled, "s": s, "t": t}
                sid = f"s{filled}"
                evidence.setdefault(kind, []).append(sid)
                allowed = sorted({int(x) for x in re.findall(r"\d+", reason + " " + evr)})
                steps.append(Step(
                    id=sid, operation="fill_cell", prior_state=prior, state_after=after,
                    inputs={"i": i, "j": j, "dp_value": dp[i][j]},
                    decision=f"dp[{i}][{j}] = {dp[i][j]}", reason=reason,
                    visual_state={"kind": "variables", "grid": [row[:] for row in dp], "active": [i, j]},
                    visual_delta={"cell": [i, j], "dp_value": dp[i][j]},
                    expected_visible_result=evr,
                    facts={"allowed_values": allowed, "required_facts": [fact("dp_value", dp[i][j])],
                           "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Find the edit (Levenshtein) distance between '{s}' and '{t}' using dynamic programming "
                     f"(dp[i][j] = dp[i-1][j-1] on a match, else 1 + min of the three neighbors)."),
            conventions=dict(_ED_CONV),
            initial_state={"dp": _base_grid(m, n), "filled": 0, "s": s, "t": t},
            final_answer={"edit_distance": dp[m][n]}, steps=steps,
            invariants=[dict(x) for x in _ED_INV], required_cases=list(_ED_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return a.get("dp") == b.get("dp") and a.get("filled") == b.get("filled")

    def final_answer_entails(self, state, answer):
        dp = (state or {}).get("dp") or []
        return bool(dp) and dp[-1][-1] == (answer or {}).get("edit_distance")

    def invariant_holds(self, inv, state):
        if inv.get("id") == "grid_matches_true_edit_distance":
            dp = (state or {}).get("dp") or []
            s, t = str((state or {}).get("s") or ""), str((state or {}).get("t") or "")
            m, n = len(s), len(t)
            true = _true_edit_distance(s, t)
            for i in range(m + 1):                       # base column always correct
                if dp[i][0] != true[i][0]:
                    return False
            for j in range(n + 1):                       # base row always correct
                if dp[0][j] != true[0][j]:
                    return False
            k, cnt = (state or {}).get("filled") or 0, 0   # the first k inner cells (row-major) are filled
            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    cnt += 1
                    if cnt <= k and dp[i][j] != true[i][j]:
                        return False
            return True
        return True

    def validate_step_shape(self, step):
        return [] if step.operation == "fill_cell" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        dv = str(step.inputs["dp_value"])
        return [] if dv in prose else [("dp_value_not_stated", dv)]
