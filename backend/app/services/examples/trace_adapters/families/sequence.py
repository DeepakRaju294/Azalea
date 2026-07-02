"""Indexed-sequence family (WORKED_EXAMPLE_ACCURACY_SPEC §15.3) — the `indexed_sequence` visual family
(arrays/strings with cursors/windows). Members share random-array generation; each owns its reference run.
Members here: binary search, bottom-up merge sort. Future: two-pointer, sliding window, partition, …
"""
from __future__ import annotations

import random
import re
from typing import Any, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase


def fmt_runs(runs: Any) -> str:
    """Humanize a list of merge-sort runs for prose: [[48],[23],[3,5]] -> '[48], [23], [3, 5]' (each run
    bracketed, but no confusing OUTER nesting `[[...],[...]]`)."""
    return ", ".join(str(list(r)) for r in (runs or [])) or "(none)"


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
    label_convention = "ints"             # §2.3 — array indices / values are integers
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
        terminal="the target is found, or the search window becomes empty (target absent)",
        output_shape="the index, or -1")

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
            if decision == "found":
                reason = f"nums[{mid}] = {val} equals the target {target} — found it"
            elif decision == "go_right":
                reason = (f"nums[{mid}] = {val} is less than the target {target}, so discard the left half "
                          f"and search right")
            else:
                reason = (f"nums[{mid}] = {val} is greater than the target {target}, so discard the right half "
                          f"and search left")
            if decision != "found" and after["lo"] > after["hi"]:   # the move empties the window → absent
                reason += " — but that leaves no window to search, so the target is absent"
            steps.append(Step(
                id=sid, operation="probe", prior_state=prior, state_after=after,
                inputs={"mid": mid, "value": val, "target": target},
                decision=decision,
                reason=reason,
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
        required = [fact("probe", f"mid {mid}"), fact("value", val)]
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
        cmp = "<" if decision == "go_right" else ">"
        lo, hi = after["lo"], after["hi"]
        if lo > hi:      # the window just collapsed — nowhere left to look, so the target is absent
            return (f"nums[{mid}] = {val} {cmp} {target} → search {side}, but the window is now empty "
                    f"(low {lo} is past high {hi}) — the target is absent")
        return f"nums[{mid}] = {val} {cmp} {target} → search {side}; window [{lo}, {hi}]"


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
    label_convention = "ints"             # §2.3 — array values are integers
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
            expected_visible_result=f"Initial runs: each element is its own sorted run: {fmt_runs(runs)}.",
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
                expected_visible_result=f"Merge {r1} and {r2} → {merged}; runs now {fmt_runs(runs)}",
                facts={"allowed_values": sorted(set(arr)),
                       "required_facts": [fact("first", merged[0]), fact("last", merged[-1])],
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


# ===================================================================================================
# Insertion sort (grow a sorted prefix: insert each next element into its place) — T8a incremental build
# ===================================================================================================
_INS_CONV = {"algorithm_variant": "insertion_sort", "order": "ascending",
             "invariant": "the prefix a[0..i] is always sorted", "trace_granularity": "one_insertion"}
_INS_REQ = ["shift_insert", "stay_in_place", "completion"]
_INS_INV = [{"id": "prefix_sorted", "scope": "every_step",
             "statement": "the sorted prefix (up to sorted_len) is in ascending order"}]


class InsertionSortAdapter(FamilyAdapterBase):
    slug = "insertion_sort"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(5, 8), value_range=(1, 60), structure=["distinct", "unsorted"]),
        stages={"insert": StageSpec(
            "insert", "insert the next element into its place in the sorted prefix",
            teaching_focus="each element slides left past larger ones until it sits in sorted position",
            contains={"shift_larger": "aggregated_supporting", "place_key": "required"},
            state_effects=["the sorted prefix grows by one; it stays in ascending order"])},
        structure="start_prefix, then insert+ until the whole array is sorted",
        must_exercise=["shift_insert", "stay_in_place", "completion"],
        must_avoid=["already_sorted", "reverse_sorted"],
        terminal="every element is in its sorted position (the array is fully sorted)",
        output_shape="the sorted array")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(5, 8)
            arr = rng.sample(range(1, 60), n)
            yield {"array": arr, "_id": f"insertion_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence          # need BOTH a shift-insert and a stay-in-place (mixed order)
        return len(trace.steps) >= 4 and bool(ev.get("shift_insert")) and bool(ev.get("stay_in_place"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        arr = list(example_input["array"])
        a = list(arr)
        n = len(a)
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        _init = {"array": list(a), "sorted_len": 1}
        steps.append(Step(
            id="s0", operation="insert", prior_state=_init, state_after=_init, inputs={"array": list(a)},
            decision="the first element is a sorted prefix of length 1",
            reason=f"{a[0]} alone is already sorted, so insertion sort starts with it as the sorted prefix",
            visual_state={"kind": "array", "array": list(a), "sorted_len": 1, "active": 0},
            visual_delta={"prefix": 1},
            expected_visible_result=f"Start: {a[0]} alone is a sorted prefix; the rest is still unsorted.",
            facts={"allowed_values": sorted(set(arr) | {1}), "required_facts": [], "forbidden_claims": []}))
        for i in range(1, n):
            sid = f"s{i}"
            key = a[i]
            prior = {"array": list(a), "sorted_len": i}
            j = i - 1
            shifted: list[int] = []
            while j >= 0 and a[j] > key:
                shifted.append(a[j])
                a[j + 1] = a[j]
                j -= 1
            a[j + 1] = key
            pos = j + 1
            after = {"array": list(a), "sorted_len": i + 1}
            if shifted:
                reason = (f"insert {key}: it is smaller than {', '.join(map(str, shifted))}, so slide "
                          f"them right and drop {key} into position {pos}")
                evidence.setdefault("shift_insert", []).append(sid)
            else:
                reason = f"insert {key}: it is already at least as large as the sorted prefix, so it stays put"
                evidence.setdefault("stay_in_place", []).append(sid)
            evr = f"Insert {key} into the sorted prefix; array now {a}."
            allowed = sorted(set(arr) | {int(x) for x in re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation="insert", prior_state=prior, state_after=after,
                inputs={"key": key, "position": pos, "shifted": list(shifted)},
                decision=f"insert {key} into the sorted prefix", reason=reason,
                visual_state={"kind": "array", "array": list(a), "sorted_len": i + 1, "active": pos},
                visual_delta={"inserted": key, "position": pos},
                expected_visible_result=evr,
                facts={"allowed_values": allowed,
                       "required_facts": [fact("key", key)], "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=f"Sort the array {arr} in ascending order using insertion sort.",
            conventions=dict(_INS_CONV), initial_state={"array": list(arr), "sorted_len": 1},
            final_answer={"sorted": sorted(arr)}, steps=steps,
            invariants=[dict(x) for x in _INS_INV], required_cases=list(_INS_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        return (list((a or {}).get("array") or []) == list((b or {}).get("array") or [])
                and (a or {}).get("sorted_len") == (b or {}).get("sorted_len"))

    def final_answer_entails(self, state, answer):
        return list((state or {}).get("array") or []) == list((answer or {}).get("sorted") or [])

    def invariant_holds(self, inv, state):
        if inv.get("id") == "prefix_sorted":
            arr = (state or {}).get("array") or []
            k = (state or {}).get("sorted_len") or 0
            pref = arr[:k]
            return pref == sorted(pref)
        return True

    def validate_step_shape(self, step):
        return [] if step.operation == "insert" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        if "key" not in step.inputs:                       # the setup card (first prefix) has no key to name
            return []
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        key = str(step.inputs["key"])
        return [] if key in prose else [("key_not_stated", key)]


# ===================================================================================================
# Selection sort (repeatedly select the min of the unsorted part and place it) — T8a (2nd pilot => gate)
# ===================================================================================================
_SEL_CONV = {"algorithm_variant": "selection_sort", "order": "ascending",
             "invariant": "a[0..i] holds the i smallest values, sorted", "trace_granularity": "one_selection"}
_SEL_REQ = ["swap_needed", "completion"]
_SEL_INV = [{"id": "prefix_is_sorted_minimums", "scope": "every_step",
             "statement": "the sorted prefix holds the smallest values in ascending order"}]


class SelectionSortAdapter(FamilyAdapterBase):
    slug = "selection_sort"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(5, 8), value_range=(1, 60), structure=["distinct", "unsorted"]),
        stages={"select": StageSpec(
            "select", "select the smallest remaining element and lock it into the front of the unsorted part",
            teaching_focus="each pass finds the minimum of what's left and fixes it in its final position",
            contains={"scan_for_min": "internal", "place_min": "required", "swap": "aggregated_supporting"},
            state_effects=["the sorted prefix grows by one; it always holds the smallest values in order"])},
        structure="select+ until the whole array is sorted",
        must_exercise=["swap_needed", "completion"], must_cover=["swap_needed", "already_min"],
        must_avoid=["already_sorted"],
        terminal="every position holds its final sorted value", output_shape="the sorted array")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(5, 8)
            arr = rng.sample(range(1, 60), n)
            yield {"array": arr, "_id": f"selection_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        return len(trace.steps) >= 4 and bool(trace.case_evidence.get("swap_needed"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        arr = list(example_input["array"])
        a = list(arr)
        n = len(a)
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        for i in range(n - 1):                             # last element is left in place automatically
            sid = f"s{i + 1}"
            suffix = list(a[i:])
            min_idx = i
            for j in range(i + 1, n):
                if a[j] < a[min_idx]:
                    min_idx = j
            min_val = a[min_idx]
            prior = {"array": list(a), "sorted_len": i}
            swapped = min_idx != i
            a[i], a[min_idx] = a[min_idx], a[i]
            after = {"array": list(a), "sorted_len": i + 1}
            if swapped:
                reason = (f"the smallest value in the unsorted part {suffix} is {min_val}, so swap it into "
                          f"position {i}")
                evidence.setdefault("swap_needed", []).append(sid)
            else:
                reason = (f"{min_val} is already the smallest of the unsorted part {suffix}, so it stays in "
                          f"position {i}")
                evidence.setdefault("already_min", []).append(sid)
            evr = f"Select {min_val} (the smallest remaining) into position {i}; array now {a}."
            allowed = sorted(set(arr) | {int(x) for x in re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation="select", prior_state=prior, state_after=after,
                inputs={"min_value": min_val, "position": i, "swapped": swapped},
                decision=f"select {min_val} into position {i}", reason=reason,
                visual_state={"kind": "array", "array": list(a), "sorted_len": i + 1, "active": i},
                visual_delta={"selected": min_val, "position": i},
                expected_visible_result=evr,
                facts={"allowed_values": allowed,
                       "required_facts": [fact("min", min_val)], "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=f"Sort the array {arr} in ascending order using selection sort.",
            conventions=dict(_SEL_CONV), initial_state={"array": list(arr), "sorted_len": 0},
            final_answer={"sorted": sorted(arr)}, steps=steps,
            invariants=[dict(x) for x in _SEL_INV], required_cases=list(_SEL_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        return (list((a or {}).get("array") or []) == list((b or {}).get("array") or [])
                and (a or {}).get("sorted_len") == (b or {}).get("sorted_len"))

    def final_answer_entails(self, state, answer):
        return list((state or {}).get("array") or []) == list((answer or {}).get("sorted") or [])

    def invariant_holds(self, inv, state):
        if inv.get("id") == "prefix_is_sorted_minimums":
            arr = (state or {}).get("array") or []
            k = (state or {}).get("sorted_len") or 0
            pref, rest = arr[:k], arr[k:]
            return pref == sorted(pref) and (not pref or not rest or max(pref) <= min(rest))
        return True

    def validate_step_shape(self, step):
        return [] if step.operation == "select" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        mv = str(step.inputs["min_value"])
        return [] if mv in prose else [("min_not_stated", mv)]


# --- bubble sort (T8a — the 3rd incremental-sort pilot; adjacent compare-swaps grow a sorted SUFFIX of the
#     largest values, and a zero-swap pass exits early. Same "grow a sorted region one pass at a time" shape
#     as selection sort, exercised through a different mechanic + an early-termination case) ----------------
_BUB_CONV = {"algorithm_variant": "bubble_sort", "order": "ascending",
             "invariant": "the sorted suffix a[n-k:] holds the k largest values, sorted",
             "trace_granularity": "one_pass"}
_BUB_REQ = ["swap_needed", "completion"]
_BUB_INV = [{"id": "suffix_is_sorted_maximums", "scope": "every_step",
             "statement": "the sorted suffix holds the largest values in ascending order"}]


class BubbleSortAdapter(FamilyAdapterBase):
    slug = "bubble_sort"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(5, 8), value_range=(1, 60), structure=["distinct", "unsorted"]),
        stages={"pass": StageSpec(
            "pass", "sweep the unsorted part left to right, swapping each adjacent out-of-order pair",
            teaching_focus="each pass floats the largest remaining value to the end; a swap-free pass means done",
            contains={"compare_adjacent": "internal", "swap_adjacent": "aggregated_supporting",
                      "float_max": "required"},
            state_effects=["the sorted suffix grows by one; it always holds the largest values in order"])},
        structure="pass+ until a sweep makes no swaps (or the array is sorted)",
        must_exercise=["swap_needed", "completion"], must_cover=["swap_needed"],
        must_avoid=["already_sorted"],
        terminal="a full pass makes no swaps, so every value is in its final sorted position",
        output_shape="the sorted array")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(5, 8)
            arr = rng.sample(range(1, 60), n)
            yield {"array": arr, "_id": f"bubble_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        return len(trace.steps) >= 3 and bool(trace.case_evidence.get("swap_needed"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        arr = list(example_input["array"])
        a = list(arr)
        n = len(a)
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        sorted_suffix = 0
        p = 0
        while sorted_suffix < n - 1:
            p += 1
            sid = f"s{p}"
            prior_arr = list(a)
            window = list(a[:n - sorted_suffix])           # the unsorted region this pass sweeps
            swaps = 0
            for j in range(0, n - sorted_suffix - 1):
                if a[j] > a[j + 1]:
                    a[j], a[j + 1] = a[j + 1], a[j]
                    swaps += 1
            settled_pos = n - sorted_suffix - 1             # where this pass parks the largest value
            bubbled = a[settled_pos]
            prior = {"array": prior_arr, "sorted_len": sorted_suffix}
            if swaps > 0:
                sorted_suffix += 1
                after = {"array": list(a), "sorted_len": sorted_suffix}
                reason = (f"sweep {window} from left to right, swapping the {swaps} adjacent out-of-order "
                          f"pair(s); the largest value {bubbled} bubbles to position {settled_pos}")
                evr = f"Bubble {bubbled} to position {settled_pos}; array now {a}."
                evidence.setdefault("swap_needed", []).append(sid)
                req = [fact("max", bubbled)]
                inputs = {"bubbled": bubbled, "position": settled_pos, "swaps": swaps}
            else:                                           # a swap-free sweep proves the array is sorted -> stop
                after = {"array": list(a), "sorted_len": n}
                reason = (f"sweep {window} from left to right and find no adjacent pair out of order, so the "
                          f"array is already fully sorted and bubble sort stops early")
                evr = f"No swaps needed; the array {a} is already sorted."
                evidence.setdefault("no_swap_early_exit", []).append(sid)
                req = []
                inputs = {"bubbled": None, "position": settled_pos, "swaps": 0}
            allowed = sorted(set(arr) | {int(x) for x in re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation="pass", prior_state=prior, state_after=after, inputs=inputs,
                decision=(f"bubble {bubbled} to position {settled_pos}" if swaps else "no swaps — already sorted"),
                reason=reason,
                visual_state={"kind": "array", "array": list(a), "sorted_len": after["sorted_len"],
                              "active": settled_pos},
                visual_delta={"bubbled": bubbled, "position": settled_pos, "swaps": swaps},
                expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": req, "forbidden_claims": []}))
            if swaps == 0:
                break
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=f"Sort the array {arr} in ascending order using bubble sort.",
            conventions=dict(_BUB_CONV), initial_state={"array": list(arr), "sorted_len": 0},
            final_answer={"sorted": sorted(arr)}, steps=steps,
            invariants=[dict(x) for x in _BUB_INV], required_cases=list(_BUB_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        return (list((a or {}).get("array") or []) == list((b or {}).get("array") or [])
                and (a or {}).get("sorted_len") == (b or {}).get("sorted_len"))

    def final_answer_entails(self, state, answer):
        return list((state or {}).get("array") or []) == list((answer or {}).get("sorted") or [])

    def invariant_holds(self, inv, state):
        if inv.get("id") == "suffix_is_sorted_maximums":
            arr = (state or {}).get("array") or []
            k = (state or {}).get("sorted_len") or 0
            suffix, prefix = arr[len(arr) - k:], arr[:len(arr) - k]
            return suffix == sorted(suffix) and (not suffix or not prefix or min(suffix) >= max(prefix))
        return True

    def validate_step_shape(self, step):
        return [] if step.operation == "pass" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        if not step.inputs.get("swaps"):                   # early-exit pass states no bubbled value — nothing to check
            return []
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        bv = str(step.inputs["bubbled"])
        return [] if bv in prose else [("bubbled_max_not_stated", bv)]


# --- quicksort (T3 — the 2nd divide-and-conquer pilot after merge sort; a DIFFERENT D&C shape: partition
#     in place around a pivot that lands at its FINAL position, then recurse on the two sides. One card per
#     partition; the placed-pivot invariant is globally verifiable from the array + the set of placed indices) -
_QS_CONV = {"algorithm_variant": "lomuto_quicksort", "order": "ascending", "pivot_rule": "last_element",
            "invariant": "a placed pivot sits at its final sorted index", "trace_granularity": "one_partition"}
_QS_REQ = ["multi_element_partition", "completion"]
_QS_INV = [{"id": "pivots_in_final_position", "scope": "every_step",
            "statement": "every placed pivot is at its final sorted position"}]


class QuickSortAdapter(FamilyAdapterBase):
    slug = "quick_sort"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(6, 8), value_range=(1, 60), structure=["distinct", "unsorted"]),
        stages={"partition": StageSpec(
            "partition", "partition a subarray around its pivot so the pivot reaches its final sorted spot",
            teaching_focus="one partition fixes the pivot forever; recursion then sorts the smaller/larger sides",
            contains={"choose_pivot": "internal", "shift_smaller_left": "aggregated_supporting",
                      "place_pivot": "required"},
            state_effects=["the pivot lands at its final index; everything left is smaller, right is larger"])},
        structure="partition, then recurse on the left and right subarrays",
        must_exercise=["multi_element_partition", "completion"], must_cover=["multi_element_partition"],
        must_avoid=["already_sorted"],
        terminal="every pivot has been placed, so the whole array is sorted", output_shape="the sorted array")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(6, 8)
            arr = rng.sample(range(1, 60), n)
            yield {"array": arr, "_id": f"quick_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        return len(trace.steps) >= 3 and bool(trace.case_evidence.get("multi_element_partition"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        arr = list(example_input["array"])
        a = list(arr)
        n = len(a)
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        placed: list[int] = []
        counter = {"i": 0}

        def do(lo: int, hi: int) -> None:
            if lo >= hi:                                    # 0- or 1-element subarray is already in place
                return
            prior_arr = list(a)
            prior_placed = sorted(placed)
            window = list(a[lo:hi + 1])
            pivot = a[hi]                                   # Lomuto: last element is the pivot
            i = lo
            for j in range(lo, hi):
                if a[j] < pivot:
                    a[i], a[j] = a[j], a[i]
                    i += 1
            a[i], a[hi] = a[hi], a[i]                       # pivot swaps into its final resting index
            placed.append(i)
            counter["i"] += 1
            sid = f"s{counter['i']}"
            reason = (f"partition the subarray {window} around pivot {pivot} (its last element): every value "
                      f"smaller than {pivot} shifts to the left, so {pivot} settles at position {i} — "
                      f"everything left of it is now smaller and everything right is larger")
            evr = f"Pivot {pivot} locked into position {i}; array now {a}."
            if hi - lo >= 2:
                evidence.setdefault("multi_element_partition", []).append(sid)
            allowed = sorted(set(arr) | {int(x) for x in re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation="partition",
                prior_state={"array": prior_arr, "placed": prior_placed},
                state_after={"array": list(a), "placed": sorted(placed)},
                inputs={"pivot": pivot, "position": i, "lo": lo, "hi": hi},
                decision=f"place pivot {pivot} at position {i}", reason=reason,
                visual_state={"kind": "array", "array": list(a), "placed": sorted(placed), "active": i},
                visual_delta={"pivot": pivot, "position": i},
                expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": [fact("pivot", pivot)],
                       "forbidden_claims": []}))
            do(lo, i - 1)                                   # recurse: smaller side, then larger side
            do(i + 1, hi)

        do(0, n - 1)
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Sort the array {arr} in ascending order using quicksort "
                     f"(Lomuto partition, last element as the pivot)."),
            conventions=dict(_QS_CONV), initial_state={"array": list(arr), "placed": []},
            final_answer={"sorted": sorted(arr)}, steps=steps,
            invariants=[dict(x) for x in _QS_INV], required_cases=list(_QS_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        return (list((a or {}).get("array") or []) == list((b or {}).get("array") or [])
                and sorted((a or {}).get("placed") or []) == sorted((b or {}).get("placed") or []))

    def final_answer_entails(self, state, answer):
        return list((state or {}).get("array") or []) == list((answer or {}).get("sorted") or [])

    def invariant_holds(self, inv, state):
        if inv.get("id") == "pivots_in_final_position":
            arr = (state or {}).get("array") or []
            for k in (state or {}).get("placed") or []:
                left, right = arr[:k], arr[k + 1:]
                if left and max(left) > arr[k]:
                    return False
                if right and arr[k] > min(right):
                    return False
        return True

    def validate_step_shape(self, step):
        return [] if step.operation == "partition" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        pv = str(step.inputs["pivot"])
        return [] if pv in prose else [("pivot_not_stated", pv)]


# --- heap sort (T8a — heap-ASSISTED selection: like selection sort it grows a sorted suffix by repeatedly
#     taking the current maximum, but a max-heap finds that maximum in log time instead of a linear scan.
#     Two phases (build the heap, then extract-max repeatedly); one card per sift-down. Both invariants are
#     verifiable from state alone: the sorted-suffix one, and a build-frontier heap-property one that holds
#     through the partial-build phase (nodes from the frontier onward already dominate their children)) ------
_HS_CONV = {"algorithm_variant": "in_place_heap_sort", "order": "ascending", "heap_type": "max_heap",
            "invariant": "the sorted suffix holds the largest values; the heap region is a max-heap",
            "trace_granularity": "one_sift"}
_HS_REQ = ["build_sift", "extract_max", "completion"]
_HS_INV = [{"id": "suffix_is_sorted_maximums", "scope": "every_step",
            "statement": "the sorted suffix holds the largest values in ascending order"},
           {"id": "heap_property_from_frontier", "scope": "every_step",
            "statement": "every node from the build frontier onward dominates its children in the heap region"}]


class HeapSortAdapter(FamilyAdapterBase):
    slug = "heap_sort"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(5, 6), value_range=(1, 60), structure=["distinct", "unsorted"]),
        stages={
            "build_heap": StageSpec(
                "build_heap", "sift each internal node down (last parent first) to build a max-heap",
                teaching_focus="after the build phase the largest value sits at the root",
                contains={"compare_children": "internal", "sift_swap": "aggregated_supporting"},
                state_effects=["each subtree, from the frontier down, becomes a max-heap"]),
            "extract_max": StageSpec(
                "extract_max", "move the root (the max) to its final spot, shrink the heap, and re-sift the root",
                teaching_focus="each extract fixes one more of the largest values in its final sorted position",
                contains={"compare_children": "internal", "sift_swap": "aggregated_supporting",
                          "place_max": "required"},
                state_effects=["the sorted suffix grows by one max; the shrunken heap region stays a max-heap"])},
        structure="build-heap sifts, then extract-max+sift until the heap is empty",
        must_exercise=["build_sift", "extract_max", "completion"], must_cover=["sift_swap"],
        must_avoid=["already_sorted"],
        terminal="every maximum has been extracted to its final position, so the whole array is sorted",
        output_shape="the sorted array")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(5, 6)
            arr = rng.sample(range(1, 60), n)
            yield {"array": arr, "_id": f"heap_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return (len(trace.steps) >= 5 and bool(ev.get("build_sift")) and bool(ev.get("extract_max"))
                and bool(ev.get("sift_swap")))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        arr = list(example_input["array"])
        a = list(arr)
        n = len(a)
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        counter = {"i": 0}

        def state(heap_size: int, frontier: int) -> dict[str, Any]:
            return {"array": list(a), "heap_size": heap_size, "frontier": frontier,
                    "sorted_len": n - heap_size}

        def sift(i: int, size: int):
            """Sift a[i] down within a[0:size]; returns (resting_index, swaps, start_value, first_larger_child)."""
            start_val = a[i]
            first_child = None
            swaps = 0
            while True:
                largest = i
                for c in (2 * i + 1, 2 * i + 2):
                    if c < size and a[c] > a[largest]:
                        largest = c
                if largest == i:
                    break
                if first_child is None:
                    first_child = a[largest]
                a[i], a[largest] = a[largest], a[i]
                swaps += 1
                i = largest
            return i, swaps, start_val, first_child

        def add(op: str, prior, after, inputs, decision, reason, evr, req, active) -> str:
            counter["i"] += 1
            sid = f"s{counter['i']}"
            allowed = sorted(set(arr) | {int(x) for x in re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation=op, prior_state=prior, state_after=after, inputs=inputs,
                decision=decision, reason=reason,
                visual_state={"kind": "array", "array": list(a), "heap_size": after["heap_size"],
                              "sorted_len": after["sorted_len"], "active": active},
                visual_delta=dict(inputs), expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": req, "forbidden_claims": []}))
            return sid

        # phase 1 — build a max-heap: sift each internal node down, last parent first
        for i in range(n // 2 - 1, -1, -1):
            prior = state(n, i + 1)                        # nodes above i are already heap-ordered
            rest, swaps, val, child = sift(i, n)
            after = state(n, i)
            if swaps > 0:
                reason = (f"sift value {val} down from index {i}: it is smaller than its larger child {child}, "
                          f"so it keeps trading places with the larger child until both children are smaller, "
                          f"coming to rest at index {rest}. The subtree rooted at index {i} is now a max-heap.")
                evr = f"Heapify index {i}: {val} sifts down to index {rest}; array now {a}."
            else:
                reason = (f"value {val} at index {i} is already at least as large as both its children, so the "
                          f"subtree rooted at index {i} is already a max-heap.")
                evr = f"Heapify index {i}: {val} already dominates its children; array unchanged {a}."
            sid = add("build_heap", prior, after, {"value": val, "index": i, "resting": rest, "swaps": swaps},
                      f"heapify index {i}", reason, evr, [fact("value", val)], i)
            evidence.setdefault("build_sift", []).append(sid)
            if swaps > 0:
                evidence.setdefault("sift_swap", []).append(sid)

        # phase 2 — repeatedly extract the max (root) to its final position, then re-sift the new root
        for end in range(n - 1, 0, -1):
            prior = state(end + 1, 0)
            maxval = a[0]
            a[0], a[end] = a[end], a[0]                    # the max goes to its final sorted spot
            rest, swaps, newroot, child = sift(0, end)     # newroot is the value promoted from position `end`
            after = state(end, 0)
            tail = (f"The new root {newroot} then sifts down to index {rest} to restore the max-heap."
                    if swaps > 0 else
                    f"The new root {newroot} already dominates its children, so the max-heap still holds.")
            reason = (f"the root {maxval} is the largest value in the heap, so swap it to position {end} — its "
                      f"final sorted position — and shrink the heap to size {end}. {tail}")
            evr = f"Extract max {maxval} to position {end}; array now {a}."
            sid = add("extract_max", prior, after,
                      {"max": maxval, "position": end, "new_root": newroot, "swaps": swaps},
                      f"extract max {maxval} to position {end}", reason, evr, [fact("max", maxval)], end)
            evidence.setdefault("extract_max", []).append(sid)
            if swaps > 0:
                evidence.setdefault("sift_swap", []).append(sid)

        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Sort the array {arr} in ascending order using heap sort "
                     f"(build a max-heap, then repeatedly extract the maximum)."),
            conventions=dict(_HS_CONV),
            initial_state={"array": list(arr), "heap_size": n, "frontier": n // 2, "sorted_len": 0},
            final_answer={"sorted": sorted(arr)}, steps=steps,
            invariants=[dict(x) for x in _HS_INV], required_cases=list(_HS_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return (list(a.get("array") or []) == list(b.get("array") or [])
                and a.get("heap_size") == b.get("heap_size") and a.get("frontier") == b.get("frontier"))

    def final_answer_entails(self, state, answer):
        return list((state or {}).get("array") or []) == list((answer or {}).get("sorted") or [])

    def invariant_holds(self, inv, state):
        state = state or {}
        arr = state.get("array") or []
        if inv.get("id") == "suffix_is_sorted_maximums":
            k = state.get("sorted_len") or 0
            suffix, prefix = arr[len(arr) - k:], arr[:len(arr) - k]
            return suffix == sorted(suffix) and (not suffix or not prefix or min(suffix) >= max(prefix))
        if inv.get("id") == "heap_property_from_frontier":
            size = state.get("heap_size") or 0
            frontier = state.get("frontier") or 0
            for j in range(frontier, size):
                for c in (2 * j + 1, 2 * j + 2):
                    if c < size and arr[j] < arr[c]:
                        return False
            return True
        return True

    def validate_step_shape(self, step):
        return [] if step.operation in ("build_heap", "extract_max") else [
            f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        v = str(step.inputs.get("max", step.inputs.get("value")))
        return [] if v in prose else [("value_not_stated", v)]
