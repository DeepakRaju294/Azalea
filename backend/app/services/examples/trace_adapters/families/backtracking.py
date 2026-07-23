"""Backtracking family (WORKED_EXAMPLE_ACCURACY_SPEC §15.3) — the T11 shape: search a decision tree by
extending a partial solution, and UNDO the last choice (backtrack) when it leads to a dead end. This is a
control flow no other family has: progress is not monotonic — the trace advances AND retreats.

First member: N-Queens (N=4, the smallest instance that actually backtracks). Correctness is self-evident and
independently checkable — the invariant `no_two_queens_attack` holds on every partial board, verified straight
from the placed coordinates, so a bogus placement can never pass as verified.
"""
from __future__ import annotations

import random
import re
from typing import Any, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase


def _safe(queens: list[int], row: int, col: int) -> bool:
    """A queen at (row, col) is safe against the already-placed queens (one per earlier column)."""
    for c, r in enumerate(queens):
        if r == row or abs(r - row) == abs(c - col):     # same row, or same diagonal
            return False
    return True


def _nqueens_events(n: int) -> tuple[list[int], list[tuple]]:
    """Standard column-by-column backtracking to the FIRST solution. Returns (solution, events) where each
    event is ("place", col, row) or ("backtrack", col, row) — exactly the learner-facing decisions."""
    queens: list[int] = []
    events: list[tuple] = []

    def place(col: int) -> bool:
        if col == n:
            return True
        for row in range(n):
            if _safe(queens, row, col):
                queens.append(row)
                events.append(("place", col, row))
                if place(col + 1):
                    return True
                queens.pop()
                events.append(("backtrack", col, row))   # this choice dead-ended; undo it
        return False

    place(0)
    return list(queens), events


_NQ_CONV = {"problem": "n_queens", "search": "backtracking",
            "rule": "no two queens share a row, column, or diagonal", "trace_granularity": "one_decision"}
_NQ_REQ = ["place", "backtrack", "completion"]
_NQ_INV = [{"id": "no_two_queens_attack", "scope": "every_step",
            "statement": "no two placed queens share a row or a diagonal"}]


class NQueensAdapter(FamilyAdapterBase):
    slug = "n_queens"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("board", count=(4, 4), value_range=(0, 3), structure=["n_queens"]),
        stages={
            "place": StageSpec(
                "place", "place a queen on the first safe row of the current column",
                teaching_focus="extend the partial solution with a choice that breaks no rule so far",
                contains={"check_safe": "internal", "place_queen": "required"},
                state_effects=["one more column holds a queen; the board still has no two queens attacking"]),
            "backtrack": StageSpec(
                "backtrack", "undo the last placement when the current column has no safe row",
                teaching_focus="a dead end means the previous choice was wrong — retreat and try the next option",
                contains={"remove_queen": "required"},
                state_effects=["the last-placed queen is removed; the search resumes from the previous column"])},
        structure="place+ / backtrack until every column holds a queen",
        must_exercise=["place", "backtrack", "completion"], must_cover=["backtrack"],
        must_avoid=["no_backtrack_needed"],
        terminal="every column holds a queen with no two attacking — a valid arrangement",
        output_shape="the row of the queen in each column")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        # N-Queens at N=4 is the canonical smallest instance whose first-solution search actually backtracks.
        for i in range(4):
            yield {"n": 4, "_id": f"nqueens_v1_n4_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) >= 5 and bool(ev.get("place")) and bool(ev.get("backtrack"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        n = int(example_input["n"])
        solution, events = _nqueens_events(n)
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        board: list[int] = []                              # rebuild the board alongside the events
        for idx, ev in enumerate(events, start=1):
            sid = f"s{idx}"
            kind, col, row = ev
            prior = {"queens": list(board), "column": len(board)}
            if kind == "place":
                board.append(row)
                after = {"queens": list(board), "column": len(board)}
                blocked = [r for r in range(row) if not _safe(prior["queens"], r, col)]
                if blocked:
                    reason = (f"in column {col}, row(s) {', '.join(map(str, blocked))} are attacked by an "
                              f"earlier queen, but row {row} shares no row or diagonal with any queen so far — "
                              f"place a queen at (row {row}, column {col}).")
                else:
                    reason = (f"in column {col}, row {row} shares no row or diagonal with any queen placed so "
                              f"far — place a queen at (row {row}, column {col}).")
                evr = f"Place a queen at row {row}, column {col}; queens by column so far {board}."
                decision = f"place a queen at row {row}, column {col}"
                evidence.setdefault("place", []).append(sid)
                op = "place"
            else:                                          # backtrack — the (row, col) choice dead-ended
                board.pop()
                after = {"queens": list(board), "column": len(board)}
                reason = (f"every arrangement of the later columns with a queen at (row {row}, column {col}) "
                          f"hits a conflict — this choice cannot lead to a solution, so remove it and try "
                          f"column {col}'s next option.")
                evr = f"Remove the queen at row {row}, column {col}; queens by column now {board}."
                decision = f"remove the queen at row {row}, column {col}"
                evidence.setdefault("backtrack", []).append(sid)
                op = "backtrack"
            allowed = sorted(set(range(n)) | {int(x) for x in re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation=op, prior_state=prior, state_after=after,
                inputs={"column": col, "row": row, "kind": kind},
                decision=decision, reason=reason,
                visual_state={"kind": "board", "n": n, "queens": list(board), "active_column": col},
                visual_delta={"column": col, "row": row, "action": kind},
                expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": [fact("row", row)], "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Place {n} non-attacking queens on a {n}x{n} board using backtracking "
                     f"(one queen per column, left to right)."),
            conventions=dict(_NQ_CONV), initial_state={"queens": [], "column": 0},
            final_answer={"queen_rows": solution}, steps=steps,
            invariants=[dict(x) for x in _NQ_INV], required_cases=list(_NQ_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return list(a.get("queens") or []) == list(b.get("queens") or []) and a.get("column") == b.get("column")

    def final_answer_entails(self, state, answer):
        # the terminal board is the solution: every column filled, no two queens attacking
        q = list((state or {}).get("queens") or [])
        return q == list((answer or {}).get("queen_rows") or []) and all(
            _safe(q[:c], q[c], c) for c in range(len(q)))

    def invariant_holds(self, inv, state):
        if inv.get("id") == "no_two_queens_attack":
            q = list((state or {}).get("queens") or [])
            return all(_safe(q[:c], q[c], c) for c in range(len(q)))
        return True

    def validate_step_shape(self, step):
        return [] if step.operation in ("place", "backtrack") else [f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        rv = str(step.inputs["row"])
        return [] if rv in prose else [("row_not_stated", rv)]


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
# SUBSETS (power set) via backtracking — ADAPTER_TAXONOMY_SPEC.md §6 T11 backlog. Distinct decision shape from
# N-Queens: at each position the choice is binary (include or exclude the element), not "which of n rows,"
# and there is no constraint to violate — EVERY leaf of the recursion is a valid subset, so backtracking here
# demonstrates exhaustive exploration of a binary decision tree, not constraint-driven pruning.
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
def _subsets_events(elements: list) -> tuple[list[list], list[tuple]]:
    """Backtracking power-set generation: at each position, include the element and recurse, then undo and
    recurse again having excluded it. Returns (all_subsets_in_generation_order, events), where each event is
    ("include", element, position) or ("exclude", element, position) — the "exclude" event both undoes the
    prior include AND represents the second branch, keeping the trace within T11's step budget."""
    n = len(elements)
    current: list = []
    all_subsets: list[list] = []
    events: list[tuple] = []

    def backtrack(pos: int) -> None:
        if pos == n:
            all_subsets.append(list(current))
            return
        current.append(elements[pos])
        events.append(("include", elements[pos], pos))
        backtrack(pos + 1)
        current.pop()
        events.append(("exclude", elements[pos], pos))
        backtrack(pos + 1)

    backtrack(0)
    return all_subsets, events


def _render_subset(xs: list) -> str:
    """Clean, bracket/quote-free rendering of a partial or complete subset — never Python's list repr
    (['A', 'B']), which leaked raw state into learner-facing prose (caught by
    test_state_formatting.py::test_every_adapter_renders_prose_not_repr)."""
    return ", ".join(xs) if xs else "(empty)"


_SUBSETS_CONV = {"problem": "subsets", "search": "backtracking",
                 "rule": "each element is either included or excluded", "trace_granularity": "one_decision"}
_SUBSETS_REQ = ["include", "exclude", "completion"]
_SUBSETS_INV = [{"id": "no_element_used_twice", "scope": "every_step",
                 "statement": "the partial subset never contains a duplicate element"}]


class SubsetsAdapter(FamilyAdapterBase):
    slug = "subsets_backtracking"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("sequence", count=(3, 3), structure=["subsets_backtracking"]),
        stages={
            "include": StageSpec(
                "include", "include the current element and recurse",
                teaching_focus="extend the partial subset with one more element",
                contains={"add_element": "required"},
                state_effects=["the current element joins the partial subset"]),
            "exclude": StageSpec(
                "exclude", "undo the include (if any) and recurse having excluded the element",
                teaching_focus="every element has exactly two branches — included or not — explore both",
                contains={"remove_element": "required"},
                state_effects=["the current element leaves the partial subset (or was never in it)"])},
        structure="include/exclude at every position, recursively, until all positions are decided",
        must_exercise=["include", "exclude", "completion"], must_cover=["exclude"],
        must_avoid=["no_backtrack_needed"],
        terminal="every element has been decided (included or excluded) along every branch — all subsets found",
        output_shape="every subset of the input, in generation order")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        for i in range(4):
            yield {"elements": ["A", "B", "C"], "_id": f"subsets_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) >= 5 and bool(ev.get("include")) and bool(ev.get("exclude"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        elements = list(example_input["elements"])
        all_subsets, events = _subsets_events(elements)
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        current: list = []
        for idx, ev in enumerate(events, start=1):
            sid = f"s{idx}"
            kind, elem, pos = ev
            is_last = idx == len(events)
            # NOTE: "position" is deliberately NOT part of the chained prior/after state (only in `inputs`,
            # as metadata about which decision this step represents) — it does not evolve monotonically the
            # way "subset" does. An include->exclude pair at the SAME position are sibling branches, not a
            # forward step, so a "position: pos+1" field would silently break chain continuity between them
            # (verified live: caused a structural "prior_state != previous state_after" failure).
            prior = {"subset": list(current), "complete": False}
            if kind == "include":
                current.append(elem)
                after = {"subset": list(current), "complete": is_last}
                reason = f"decide element {elem!r} (position {pos}): include it in the current subset"
                evr = f"Include {elem!r}; current partial subset {_render_subset(current)}."
                decision = f"include {elem!r}"
                evidence.setdefault("include", []).append(sid)
            else:                                          # exclude — undoes a prior include, tries the other branch
                if current and current[-1] == elem:
                    current.pop()
                after = {"subset": list(current), "complete": is_last}
                reason = (f"having fully explored the branch where {elem!r} is included, undo that choice and "
                          f"explore the other branch: exclude {elem!r} (position {pos}) instead")
                evr = f"Exclude {elem!r}; current partial subset {_render_subset(current)}."
                decision = f"exclude {elem!r}"
                evidence.setdefault("exclude", []).append(sid)
            if is_last:
                rendered_subsets = "; ".join(_render_subset(s) for s in all_subsets)
                evr += f" Every subset has now been found: {rendered_subsets}."
            op = kind
            # proactively allow 1..len(all_subsets) on every step (not just the last) — the completion clause's
            # eventual "subset 1: ..., subset 2: ..." labels (added later, in _final_answer_text) are numbers
            # this step's own reason/evr never mentions; same defensive pattern union_find uses for its
            # "group N:" labels (allowed_values |= set(range(n))), anticipating a downstream label set.
            allowed = sorted(set(range(1, len(all_subsets) + 1))
                             | {int(x) for x in re.findall(r"\d+", reason + " " + evr)})
            steps.append(Step(
                id=sid, operation=op, prior_state=prior, state_after=after,
                inputs={"position": pos, "element": elem, "kind": kind},
                decision=decision, reason=reason,
                visual_state={"kind": "variables", "elements": elements, "subset": list(current), "position": pos},
                visual_delta={"position": pos, "element": elem, "action": kind},
                expected_visible_result=evr,
                facts={"allowed_values": allowed, "required_facts": [fact("subset", str(current))],
                       "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=f"Generate every subset of the elements {_render_subset(elements)} using backtracking "
                   f"(include/exclude each element).",
            conventions=dict(_SUBSETS_CONV), initial_state={"subset": [], "complete": False},
            final_answer={"subsets": all_subsets}, steps=steps,
            invariants=[dict(x) for x in _SUBSETS_INV], required_cases=list(_SUBSETS_REQ),
            case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return list(a.get("subset") or []) == list(b.get("subset") or [])

    def final_answer_entails(self, state, answer):
        # Structurally different from N-Queens: this problem ENUMERATES every result rather than finding one,
        # so the terminal state (the last branch explored) does not itself hold the complete answer the way a
        # single-solution search's final state does — "subset == []" alone is NOT a unique completion signal
        # either (backtracking passes through the empty partial-subset state at several earlier points too,
        # verified directly against the actual event sequence). `reference()` marks the TRUE last step with an
        # explicit `complete` flag instead of trying to infer completion from subset/position alone. Full
        # correctness of the ENUMERATED answer itself (every element of `answer["subsets"]`, no more, no
        # fewer) is verified separately, against an independent oracle, by the dedicated gate test
        # (test_subsets_backtracking.py) — not by this method.
        return bool((state or {}).get("complete"))

    def invariant_holds(self, inv, state):
        if inv.get("id") == "no_element_used_twice":
            subset = list((state or {}).get("subset") or [])
            return len(subset) == len(set(subset))
        return True

    def validate_step_shape(self, step):
        return [] if step.operation in ("include", "exclude") else [
            f"unexpected operation {step.operation!r}"]

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        ev = str(step.inputs["element"]).lower()
        return [] if ev in prose else [("element_not_stated", ev)]
