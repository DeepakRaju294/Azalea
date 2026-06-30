"""Indexed-sequence family (WORKED_EXAMPLE_ACCURACY_SPEC §15.3) — the `indexed_sequence` visual family
(arrays/strings with cursors/windows). Members share random-array generation; each owns its reference run.
Members here: binary search, bottom-up merge sort. Future: two-pointer, sliding window, partition, …
"""
from __future__ import annotations

import random
from typing import Any, Iterable

from ...trace_contract import ContractTrace, Step
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase


# ===================================================================================================
# Binary search (iterative; window {lo, hi, found}; one probe per step)
# ===================================================================================================
_BS_CONV = {"algorithm_variant": "iterative_binary_search", "array_order": "ascending_sorted",
            "midpoint": "floor((lo+hi)/2)", "bounds_update": "exclusive_of_mid",
            "trace_granularity": "one_probe_per_step"}
_BS_REQ = ["lower_bound_move", "upper_bound_move", "found_or_absent"]
_BS_INV = [{"id": "window_valid", "scope": "every_step", "statement": "lo <= hi + 1"},
           {"id": "answer_in_record", "scope": "final_only", "statement": "found index recorded or window empty"}]


class BinarySearchAdapter(FamilyAdapterBase):
    slug = "binary_search"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(6, 9), value_range=(1, 60),
                            structure=["sorted_ascending", "distinct"]),
        stages={"probe": StageSpec(
            "probe", "compute the midpoint, compare it to the target, and move one bound",
            teaching_focus="use the midpoint comparison to eliminate one half",
            contains={"compute_mid": "required", "compare": "required", "move_one_bound": "required"},
            state_effects=["exactly one of lo/hi moves, OR the target is found"])},
        structure="probe+ until lo>hi (absent) or found",
        must_exercise=["lower_bound_move", "upper_bound_move", "found_or_absent"],
        must_avoid=["found_on_first_probe"],
        terminal="lo>hi (absent) or arr[mid]==target (found)", output_shape="the index, or -1")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(60):
            n = rng.randint(6, 9)
            arr = sorted(rng.sample(range(1, 60), n))
            if rng.random() < 0.7:
                target = arr[rng.randrange(n)]
            else:
                target = rng.choice([x for x in range(1, 60) if x not in arr])
            yield {"nums": arr, "target": target, "_id": f"bs_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return (len(trace.steps) >= 3 and bool(ev.get("lower_bound_move"))
                and bool(ev.get("upper_bound_move")) and bool(ev.get("found_or_absent")))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        nums: list[int] = list(example_input["nums"])
        target: int = int(example_input["target"])
        lo, hi = 0, len(nums) - 1
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        found = -1
        i = 0
        while lo <= hi:
            i += 1
            sid = f"s{i}"
            mid = (lo + hi) // 2
            val = nums[mid]
            prior = {"lo": lo, "hi": hi, "found": None}
            if val == target:
                after = {"lo": lo, "hi": hi, "found": mid}
                decision, vis_delta = "found", {"checked": mid, "result": "found"}
                evidence.setdefault("found_or_absent", []).append(sid)
            elif val < target:
                after = {"lo": mid + 1, "hi": hi, "found": None}
                decision, vis_delta = "go_right", {"checked": mid, "lo": mid + 1}
                evidence.setdefault("lower_bound_move", []).append(sid)
            else:
                after = {"lo": lo, "hi": mid - 1, "found": None}
                decision, vis_delta = "go_left", {"checked": mid, "hi": mid - 1}
                evidence.setdefault("upper_bound_move", []).append(sid)
            steps.append(Step(
                id=sid, operation="probe", prior_state=prior, state_after=after,
                inputs={"mid": mid, "value": val, "target": target},
                decision=decision,
                reason=(f"nums[{mid}]={val} {'==' if decision=='found' else '<' if decision=='go_right' else '>'} "
                        f"{target}"),
                visual_state=self._visual(nums, after, mid),
                visual_delta=vis_delta,
                expected_visible_result=self._visible(mid, val, target, decision, after),
                facts=self._facts(nums, target, mid, val, lo, hi, after, decision),
            ))
            if decision == "found":
                found = mid
                break
            lo, hi = after["lo"], after["hi"]
        if found < 0 and steps:
            evidence.setdefault("found_or_absent", []).append(steps[-1].id)

        return ContractTrace(
            problem=(f"Binary-search the sorted array {nums} for the target {target}. "
                     f"Report the index, or that it is absent."),
            conventions=dict(_BS_CONV),
            initial_state={"lo": 0, "hi": len(nums) - 1, "found": None},
            final_answer={"found_index": found}, steps=steps,
            invariants=[dict(inv) for inv in _BS_INV], required_cases=list(_BS_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input, attempt=attempt),
        )

    @staticmethod
    def _norm(s):
        s = s or {}
        return (s.get("lo"), s.get("hi"), s.get("found"))

    def states_equivalent(self, a, b):
        return self._norm(a) == self._norm(b)

    def final_answer_entails(self, state, answer):
        k = (answer or {}).get("found_index")
        if k is not None and k >= 0:
            return state.get("found") == k
        return state.get("found") is None and state.get("lo", 0) > state.get("hi", -1)

    def invariant_holds(self, inv, state):
        if inv.get("id") == "window_valid":
            return state.get("lo", 0) <= state.get("hi", -1) + 1
        if inv.get("id") == "answer_in_record":
            return state.get("found") is not None or state.get("lo", 0) > state.get("hi", -1)
        return True

    def validate_step_shape(self, step):
        errs: list[str] = []
        if step.operation != "probe":
            errs.append(f"unexpected operation {step.operation!r}")
        if "mid" not in step.inputs:
            errs.append("probe missing inputs.mid")
        for k in ("lo", "hi"):
            if k not in step.prior_state or k not in step.state_after:
                errs.append(f"state missing {k}")
        if step.decision not in ("found", "go_right", "go_left"):
            errs.append(f"bad decision {step.decision!r}")
        return errs

    def _facts(self, nums, target, mid, val, lo, hi, after, decision):
        allowed = set(nums) | set(range(len(nums))) | {target, lo, hi, mid, after["lo"], after["hi"] or 0}
        required = [f"mid {mid}", str(val)]
        forbidden = []
        if decision != "found":
            forbidden.append("target found")
        if decision == "go_right":
            forbidden.append(f"hi {mid - 1}")
        elif decision == "go_left":
            forbidden.append(f"lo {mid + 1}")
        return {"allowed_values": sorted(int(x) for x in allowed if x is not None),
                "required_facts": required, "forbidden_claims": forbidden}

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        out: list[tuple[str, str]] = []
        if str(step.inputs.get("value")) not in prose:
            out.append(("value_not_discussed", f"nums[{step.inputs.get('mid')}]={step.inputs.get('value')}"))
        if step.decision == "found" and "found" not in prose:
            out.append(("decision_mismatch", "step found target but prose doesn't say so"))
        return out

    def _visual(self, nums, state, mid):
        return {"kind": "array_window", "array": list(nums), "lo": state["lo"], "hi": state["hi"],
                "mid": mid, "found": state.get("found")}

    @staticmethod
    def _visible(mid, val, target, decision, after):
        if decision == "found":
            return f"nums[{mid}] = {val} = target → found at index {mid}"
        side = "right" if decision == "go_right" else "left"
        return (f"nums[{mid}] = {val} {'<' if decision == 'go_right' else '>'} {target} → search {side}; "
                f"window [{after['lo']}, {after['hi']}]")


# ===================================================================================================
# Merge sort (bottom-up / queue-based: merge the two front runs, enqueue the result)
# ===================================================================================================
_MS_CONV = {"algorithm_variant": "bottom_up_queue_merge_sort", "order": "ascending",
            "merge": "stable_two_pointer", "trace_granularity": "merge_two_runs"}
_MS_REQ = ["merge_two_runs", "multi_element_merge", "completion"]
_MS_INV = [{"id": "runs_sorted", "scope": "every_step", "statement": "each run is individually sorted"},
           {"id": "single_sorted_run", "scope": "final_only", "statement": "exactly one fully-sorted run"}]


def _merge(a: list[int], b: list[int]) -> list[int]:
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            out.append(a[i]); i += 1
        else:
            out.append(b[j]); j += 1
    out.extend(a[i:]); out.extend(b[j:])
    return out


class MergeSortAdapter(FamilyAdapterBase):
    slug = "merge_sort"
    # NOTE: current behavior merges a whole pair of runs in ONE step (`merge`). The contract's finer
    # merge_select-per-card grain is a planned iteration (keep instances small so a full merge stays safe).
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(5, 8), value_range=(1, 60), structure=["distinct", "unsorted"]),
        stages={
            "init_runs": StageSpec(
                "init_runs", "treat each element as its own sorted run of length 1",
                teaching_focus="bottom-up merge sort starts by viewing every element as an already-sorted run",
                cardinality="exactly_once", contains={"split_into_singletons": "required"},
                state_effects=["the array becomes a list of length-1 runs, each trivially sorted"]),
            "merge": StageSpec(
                "merge", "merge the two front runs into one sorted run",
                teaching_focus="combine two sorted runs by repeatedly taking the smaller head",
                contains={"compare_heads": "aggregated_supporting", "copy_value": "aggregated_supporting",
                          "tail_copy": "aggregated_supporting"},
                state_effects=["two runs replaced by one merged sorted run"]),
        },
        structure="init_runs, then merge+ until a single sorted run remains",
        must_exercise=["merge_two_runs", "multi_element_merge", "completion"],
        must_avoid=["already_sorted"],
        terminal="exactly one sorted run of length N", output_shape="the sorted array")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(5, 8)
            arr = rng.sample(range(1, 60), n)
            yield {"array": arr, "_id": f"merge_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) >= 4 and bool(ev.get("multi_element_merge"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        arr = list(example_input["array"])
        runs: list[list[int]] = [[x] for x in arr]
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        i = 0
        # init_runs stage (multi-stage grammar §0): make bottom-up merge sort's opening explicit.
        _init = {"runs": [list(r) for r in runs]}
        steps.append(Step(
            id="s0", operation="init_runs", prior_state=_init, state_after=_init, inputs={"array": list(arr)},
            decision="split into single-element runs",
            reason="bottom-up merge sort begins by treating every element as its own sorted run.",
            visual_state={"kind": "run_list", "runs": [list(r) for r in runs], "merged": []},
            visual_delta={"runs": [list(r) for r in runs]},
            expected_visible_result=f"Initial runs: each element is its own sorted run: {runs}.",
            facts={"allowed_values": sorted(set(arr)), "required_facts": [], "forbidden_claims": []}))
        while len(runs) > 1:
            i += 1
            sid = f"s{i}"
            r1, r2 = runs[0], runs[1]
            prior = {"runs": [list(r) for r in runs]}
            merged = _merge(r1, r2)
            runs = runs[2:] + [merged]
            after = {"runs": [list(r) for r in runs]}
            evidence.setdefault("merge_two_runs", []).append(sid)
            if len(r1) > 1 or len(r2) > 1:
                evidence.setdefault("multi_element_merge", []).append(sid)
            steps.append(Step(
                id=sid, operation="merge", prior_state=prior, state_after=after,
                inputs={"left": list(r1), "right": list(r2), "merged": list(merged)},
                decision=f"merge {r1} and {r2}",
                reason=f"compare front elements and emit the smaller: {r1} + {r2} → {merged}",
                visual_state={"kind": "run_list", "runs": [list(r) for r in runs], "merged": list(merged)},
                visual_delta={"left": list(r1), "right": list(r2), "result": list(merged)},
                expected_visible_result=f"Merge {r1} and {r2} → {merged}; runs now {runs}",
                facts={"allowed_values": sorted(set(arr)),
                       "required_facts": [str(merged[0]), str(merged[-1])],
                       "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=f"Sort the array {arr} in ascending order using merge sort (bottom-up).",
            conventions=dict(_MS_CONV), initial_state={"runs": [[x] for x in arr]},
            final_answer={"sorted": (runs[0] if runs else arr)}, steps=steps,
            invariants=[dict(x) for x in _MS_INV], required_cases=list(_MS_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input, attempt=attempt))

    def states_equivalent(self, a, b):
        ra = [list(r) for r in (a or {}).get("runs") or []]
        rb = [list(r) for r in (b or {}).get("runs") or []]
        return ra == rb

    def final_answer_entails(self, state, answer):
        runs = [list(r) for r in (state.get("runs") or [])]
        return len(runs) == 1 and runs[0] == list((answer or {}).get("sorted") or [])

    def invariant_holds(self, inv, state):
        runs = state.get("runs") or []
        if inv.get("id") == "runs_sorted":
            return all(list(r) == sorted(r) for r in runs)
        if inv.get("id") == "single_sorted_run":
            return len(runs) == 1 and list(runs[0]) == sorted(runs[0])
        return True

    def validate_step_shape(self, step):
        errs = []
        if step.operation == "init_runs":                # multi-stage: the split-into-singletons step
            if "array" not in step.inputs:
                errs.append("init missing inputs.array")
            return errs
        if step.operation != "merge":
            errs.append(f"unexpected operation {step.operation!r}")
        for k in ("left", "right", "merged"):
            if k not in step.inputs:
                errs.append(f"missing inputs.{k}")
        return errs

    def validate_prose_claims(self, card, step):
        if step.operation == "init_runs":                # presents the singleton runs; no merge to check
            return []
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        merged = step.inputs["merged"]
        if not (str(merged[0]) in prose and str(merged[-1]) in prose):
            return [("merge_result_not_discussed", str(merged))]
        return []
