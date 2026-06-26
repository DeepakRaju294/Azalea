"""Binary-search trace adapter — the first Phase-1 vertical slice (WORKED_EXAMPLE_REASONING_SPEC.md v7).

Adapter-owned reference implementation (so the HARD guarantee holds: the trace is faithful to a *known*
variant under declared conventions). State is the search window `{lo, hi, found}`; one canonical
transition = one probe (midpoint → compare → update bounds). Everything algorithm-specific is here.
"""
from __future__ import annotations

import random
from typing import Any, Iterable

from ..trace_contract import ContractTrace, Step

_CONVENTIONS = {
    "algorithm_variant": "iterative_binary_search",
    "array_order": "ascending_sorted",
    "midpoint": "floor((lo+hi)/2)",
    "bounds_update": "exclusive_of_mid",      # lo=mid+1 / hi=mid-1
    "trace_granularity": "one_probe_per_step",
}
_REQUIRED_CASES = ["lower_bound_move", "upper_bound_move", "found_or_absent"]
_INVARIANTS = [
    {"id": "window_valid", "scope": "every_step", "statement": "lo <= hi + 1"},
    {"id": "answer_in_record", "scope": "final_only", "statement": "found index recorded or window empty"},
]


class BinarySearchAdapter:
    slug = "binary_search"
    version = 1

    # --- Stage 0: deterministic candidate inputs ------------------------------------------------
    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(60):
            n = rng.randint(6, 9)
            arr = sorted(rng.sample(range(1, 60), n))
            if rng.random() < 0.7:
                target = arr[rng.randrange(n)]                       # present
            else:
                target = rng.choice([x for x in range(1, 60) if x not in arr])  # absent
            yield {"nums": arr, "target": target, "_id": f"bs_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return (len(trace.steps) >= 3 and bool(ev.get("lower_bound_move"))
                and bool(ev.get("upper_bound_move")) and bool(ev.get("found_or_absent")))

    # --- Stage 1: the adapter-owned reference run, lifted into a ContractTrace -------------------
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
        if found < 0 and steps:                                      # absent: window collapsed
            evidence.setdefault("found_or_absent", []).append(steps[-1].id)

        return ContractTrace(
            problem=(f"Binary-search the sorted array {nums} for the target {target}. "
                     f"Report the index, or that it is absent."),
            conventions=dict(_CONVENTIONS),
            initial_state={"lo": 0, "hi": len(nums) - 1, "found": None},
            final_answer={"found_index": found},
            steps=steps,
            invariants=[dict(inv) for inv in _INVARIANTS],
            required_cases=list(_REQUIRED_CASES),
            case_evidence=evidence,
            provenance={"source": "adapter_reference", "adapter": self.slug, "adapter_version": self.version,
                        "verification_level": "hard", "candidate_seed": seed,
                        "candidate_id": candidate_id or example_input.get("_id", ""),
                        "selection_attempt": attempt},
        )

    # --- equivalence / entailment / invariants / shape ------------------------------------------
    @staticmethod
    def _norm(s: dict[str, Any] | None) -> tuple:
        s = s or {}
        return (s.get("lo"), s.get("hi"), s.get("found"))

    def states_equivalent(self, a: dict[str, Any], b: dict[str, Any]) -> bool:
        return self._norm(a) == self._norm(b)

    def final_answer_entails(self, state: dict[str, Any], answer: Any) -> bool:
        k = (answer or {}).get("found_index")
        if k is not None and k >= 0:
            return state.get("found") == k
        return state.get("found") is None and state.get("lo", 0) > state.get("hi", -1)

    def invariant_holds(self, inv: dict[str, Any], state: dict[str, Any]) -> bool:
        if inv.get("id") == "window_valid":
            return state.get("lo", 0) <= state.get("hi", -1) + 1
        if inv.get("id") == "answer_in_record":
            return state.get("found") is not None or state.get("lo", 0) > state.get("hi", -1)
        return True

    def validate_step_shape(self, step: Step) -> list[str]:
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

    # --- prose facts + adapter-specific prose claim check ---------------------------------------
    def _facts(self, nums, target, mid, val, lo, hi, after, decision) -> dict[str, Any]:
        allowed = set(nums) | set(range(len(nums))) | {target, lo, hi, mid, after["lo"], after["hi"] or 0}
        required = [f"mid {mid}", str(val)]
        forbidden = []
        if decision != "found":
            forbidden.append("target found")
        # forbid claiming the opposite bound move
        if decision == "go_right":
            forbidden.append(f"hi {mid - 1}")
        elif decision == "go_left":
            forbidden.append(f"lo {mid + 1}")
        return {"allowed_values": sorted(int(x) for x in allowed if x is not None),
                "required_facts": required, "forbidden_claims": forbidden}

    def validate_prose_claims(self, card: dict[str, Any], step: Step) -> list[tuple[str, str]]:
        # Targeted (robust) check: the probed value must be discussed; the recorded decision must match.
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        out: list[tuple[str, str]] = []
        if str(step.inputs.get("value")) not in prose:
            out.append(("value_not_discussed", f"nums[{step.inputs.get('mid')}]={step.inputs.get('value')}"))
        if step.decision == "found" and "found" not in prose:
            out.append(("decision_mismatch", "step found target but prose doesn't say so"))
        return out

    # --- visuals (carried as metadata in Phase 1; enforced in 1.5) ------------------------------
    def _visual(self, nums, state, mid) -> dict[str, Any]:
        return {"kind": "array_window", "array": list(nums), "lo": state["lo"], "hi": state["hi"],
                "mid": mid, "found": state.get("found")}

    @staticmethod
    def _visible(mid, val, target, decision, after) -> str:
        if decision == "found":
            return f"nums[{mid}] = {val} = target → found at index {mid}"
        side = "right" if decision == "go_right" else "left"
        return (f"nums[{mid}] = {val} {'<' if decision == 'go_right' else '>'} {target} → search {side}; "
                f"window [{after['lo']}, {after['hi']}]")
