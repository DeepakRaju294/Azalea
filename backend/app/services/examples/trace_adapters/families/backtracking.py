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
