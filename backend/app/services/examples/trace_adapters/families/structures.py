"""Data-structure family (WORKED_EXAMPLE_ACCURACY_SPEC §15.3) — the T10 shape: a MUTABLE structure whose
operations must each preserve a structural INVARIANT. The teaching arc is "one card per operation: here is
the operation, here is what it did to the structure, and the invariant still holds."

First member: Union-Find (disjoint-set union, union by size). Correctness is refereed straight from the
`parent` array — the invariant checks the pointers form a valid forest (no cycle, every element reaches a
root), so a corrupt merge can never pass as verified.
"""
from __future__ import annotations

import random
import re
from typing import Any, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase


def _find(parent: list[int], x: int) -> int:
    while parent[x] != x:
        x = parent[x]
    return x


def _groups(parent: list[int]) -> list[list[int]]:
    buckets: dict[int, list[int]] = {}
    for x in range(len(parent)):
        buckets.setdefault(_find(parent, x), []).append(x)
    return sorted(sorted(g) for g in buckets.values())


def _forest_valid(parent: list[int]) -> bool:
    """Every element reaches a self-root without looping (the disjoint-set forest invariant)."""
    for start in range(len(parent)):
        seen = set()
        x = start
        while parent[x] != x:
            if x in seen:
                return False                                # a cycle — not a forest
            seen.add(x)
            x = parent[x]
    return True


_UF_CONV = {"structure": "disjoint_set_union", "union_rule": "by_size",
            "invariant": "parent pointers form a forest; each tree is one set", "trace_granularity": "one_union"}
_UF_REQ = ["merge", "already_connected", "completion"]
_UF_INV = [{"id": "valid_disjoint_forest", "scope": "every_step",
            "statement": "the parent pointers form a valid forest (no cycle; every element reaches a root)"}]


class UnionFindAdapter(FamilyAdapterBase):
    slug = "union_find"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(6, 8), value_range=(0, 7), structure=["disjoint_set"]),
        stages={"union": StageSpec(
            "union", "union two elements: find each root and, if they differ, merge the two trees",
            teaching_focus="each union either joins two sets or is a no-op when they are already together",
            contains={"find_roots": "internal", "merge_trees": "required"},
            state_effects=["two sets become one (or nothing changes); the forest invariant is preserved"])},
        structure="union+ until every operation is processed",
        must_exercise=["merge", "already_connected", "completion"], must_cover=["already_connected"],
        must_avoid=["all_disjoint"],
        terminal="every union is processed; the elements are partitioned into their final groups",
        output_shape="the final groups of connected elements")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(6, 8)
            ops = [tuple(rng.sample(range(n), 2)) for _ in range(n)]   # n unions -> cycles (no-ops) are likely
            yield {"n": n, "ops": ops, "_id": f"union_find_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) >= 4 and bool(ev.get("merge")) and bool(ev.get("already_connected"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        n = int(example_input["n"])
        ops = [tuple(o) for o in example_input["ops"]]
        parent = list(range(n))
        size = [1] * n
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        for idx, (a, b) in enumerate(ops, start=1):
            sid = f"s{idx}"
            ra, rb = _find(parent, a), _find(parent, b)
            prior = {"parent": list(parent), "size": list(size)}
            if ra == rb:
                reason = (f"union({a}, {b}): both {a} and {b} already trace up to root {ra}, so they are in "
                          f"the same group — nothing changes.")
                evr = f"union({a}, {b}): already connected; the groups are unchanged."
                decision = f"union({a}, {b}): already connected — no change"
                evidence.setdefault("already_connected", []).append(sid)
            else:
                larger, smaller = (ra, rb) if size[ra] >= size[rb] else (rb, ra)   # attach smaller under larger
                parent[smaller] = larger
                size[larger] += size[smaller]
                reason = (f"union({a}, {b}): {a}'s root is {ra} and {b}'s root is {rb} — they differ, so merge "
                          f"the two trees by attaching root {smaller} under root {larger}; {a} and {b} now "
                          f"share one group.")
                evr = f"union({a}, {b}): merge — attach root {smaller} under root {larger}."
                decision = f"union({a}, {b}): merge root {smaller} under root {larger}"
                evidence.setdefault("merge", []).append(sid)
            after = {"parent": list(parent), "size": list(size)}
            allowed = sorted(set(range(n)) | {int(x) for x in re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation="union", prior_state=prior, state_after=after,
                inputs={"a": a, "b": b, "root_a": ra, "root_b": rb, "merged": ra != rb},
                decision=decision, reason=reason,
                visual_state={"kind": "forest", "parent": list(parent), "active": [a, b]},
                visual_delta={"a": a, "b": b, "merged": ra != rb},
                expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": [fact("a", a), fact("b", b)],
                       "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Process these unions on elements 0..{n - 1} with union-find (union by size): "
                     f"{', '.join(f'union({a}, {b})' for a, b in ops)}. Give the final groups."),
            conventions=dict(_UF_CONV), initial_state={"parent": list(range(n)), "size": [1] * n},
            final_answer={"groups": _groups(parent)}, steps=steps,
            invariants=[dict(x) for x in _UF_INV], required_cases=list(_UF_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return list(a.get("parent") or []) == list(b.get("parent") or []) and \
            list(a.get("size") or []) == list(b.get("size") or [])

    def final_answer_entails(self, state, answer):
        return _groups(list((state or {}).get("parent") or [])) == list((answer or {}).get("groups") or [])

    def invariant_holds(self, inv, state):
        if inv.get("id") == "valid_disjoint_forest":
            return _forest_valid(list((state or {}).get("parent") or []))
        return True

    def validate_step_shape(self, step):
        return [] if step.operation == "union" else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        a, b = str(step.inputs["a"]), str(step.inputs["b"])
        return [] if a in prose and b in prose else [("pair_not_stated", f"{a},{b}")]
