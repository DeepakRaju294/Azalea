"""Shadow-vs-legacy fixture measurement (spec §12 step 5).

    python -m app.services.gen_foundation.fixture_run

* No ``OPENAI_API_KEY`` (or a ``dummy`` one): runs the pipeline on **canned** artifacts so
  you can see the harness + comparison format end-to-end. These are NOT live model
  numbers — every row is tagged ``offline``.
* With a real key: runs the real single-pass pipeline per topic (``default_solver``) and
  reports live metrics. The new path must WIN here (fewer calls/tokens, high first-pass
  validity) before flipping ``AZALEA_GEN_FOUNDATION_SHADOW`` in production (§12 step 6).

Pure measurement — does not modify production or require the flag to be set.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from .llm import default_solver
from .metrics import aggregate, compare_to_legacy
from .pipeline import RunResult, run_first_pass


def _load_env() -> None:
    """Load backend/.env so a standalone run sees OPENAI_API_KEY (the app loads it via
    llm_client at import, but that happens too late for the ``_live()`` check)."""
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    except Exception:
        pass


# --- representative topics + their canned (offline) artifacts ------------------

def _coding_artifact(n: int) -> dict:
    return {
        "problem": "merge [2,4] and [3,7]",
        "code": "def merge(a, b):\n    return sorted(a + b)\n",
        "cards": [
            {"title": f"Step {i+1}", "goal": "combine fronts", "how": "the while loop appends the smaller front",
             "work": [f"compare, append {i}"], "result": "merged grows", "state_relevance": "stateful",
             "state_delta": {"ops": [{"op": "push", "path": "merged", "value": i}]},
             "primary_kind": "merge", "explanation_mode": "implementation_how",
             "code_refs": [2], "cases_covered": [f"case_{i}"]}
            for i in range(n)
        ],
        "initial_resolved_state": {"merged": []},
        "final_answer": "[2,3,4,7]",
    }


def _bsearch_artifact(n: int) -> dict:
    return {
        "problem": "search 7 in [1..7]",
        "code": "def bsearch(nums, t):\n    lo, hi = 0, len(nums) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if nums[mid] == t:\n            return mid\n        lo = mid + 1\n    return -1\n",
        "cards": [
            {"title": f"Step {i+1}", "goal": "halve the range", "how": "compute mid, compare, drop a half",
             "work": [f"mid={i}"], "result": "range halved", "state_relevance": "stateful",
             "state_delta": {"ops": [{"op": "set", "path": "mid", "value": i}]},
             "primary_kind": "compare", "explanation_mode": "implementation_how",
             "code_refs": [4], "cases_covered": [f"case_{i}"]}
            for i in range(n)
        ],
        "initial_resolved_state": {"nums": [1, 2, 3, 4, 5, 6, 7], "low": 0, "high": 6},
        "final_answer": "6",
    }


def _concept_artifact(n: int) -> dict:
    return {
        "problem": "classify the example",
        "cards": [
            {"title": f"Step {i+1}", "goal": "advance the argument", "reasoning": "the decisive reason",
             "work": ["apply the rule"], "result": "now established", "state_relevance": "none",
             "state_delta": None, "cases_covered": [f"case_{i}"]}
            for i in range(n)
        ],
        "final_answer": "classified",
    }


def _canned(n: int, coding: bool = False) -> dict:
    """A schema-agnostic, stateless valid artifact for the OFFLINE harness check only."""
    cards = []
    for i in range(n):
        c = {"title": f"Step {i+1}", "goal": f"resolve step {i}", "work": [f"action {i} with values"],
             "result": f"state after step {i}", "state_relevance": "none", "state_delta": None,
             "cases_covered": [f"case_{i}"]}
        if coding:
            c["how"] = "the relevant construct performs this step"
            c["explanation_mode"] = "implementation_how"
        else:
            c["reasoning"] = "the decisive reason"
        cards.append(c)
    return {"problem": "a concrete input", "cards": cards, "final_answer": "the result"}


def _topic(id, ttype, family, title, summary) -> dict:
    return {"id": id, "topic_type": ttype, "topic_family": family, "title": title, "summary": summary}


# (topic, offline-canned artifact, legacy baseline, legacy_calls). The canned artifact +
# baseline are only used OFFLINE; LIVE runs the real model on the topic. Legacy baseline
# approximates the old multi-call solver (~4-5 calls coding, ~3 non-coding) for the delta.
_C = "coding_implementation"
FIXTURES = [
    # --- sorting / searching ---
    (_topic("merge_sort", _C, "array_sort", "Merge sort",
            "Sort an array by recursive split then merge of sorted halves."),
     _coding_artifact(7), {"cards": [{} for _ in range(11)]}, 5),
    (_topic("binary_search", _C, "binary_search", "Binary search",
            "Find a target in a sorted array by halving the range."),
     _bsearch_artifact(7), {"cards": [{} for _ in range(9)]}, 5),
    (_topic("quicksort", _C, "recursive_divide_and_conquer", "Quicksort",
            "Sort by partitioning around a pivot and recursing on each side."),
     _canned(7, True), {"cards": [{} for _ in range(11)]}, 5),
    (_topic("bubble_sort", _C, "array_sort", "Bubble sort",
            "Sort by repeatedly swapping adjacent out-of-order elements."),
     _canned(7, True), {"cards": [{} for _ in range(9)]}, 5),
    # --- graphs ---
    (_topic("bfs", _C, "graph_traversal", "Breadth-first search",
            "Traverse a graph level by level using a queue."),
     _canned(7, True), {"cards": [{} for _ in range(10)]}, 5),
    (_topic("dfs", _C, "graph_traversal", "Depth-first search",
            "Traverse a graph by going as deep as possible using a stack/recursion."),
     _canned(7, True), {"cards": [{} for _ in range(10)]}, 5),
    # --- linked lists ---
    (_topic("linked_list_reversal", _C, "", "Reverse a linked list",
            "Reverse the pointers of a singly linked list in one pass."),
     _canned(6, True), {"cards": [{} for _ in range(8)]}, 5),
    (_topic("linked_list_insert", _C, "", "Insert into a sorted linked list",
            "Insert a node into a sorted singly linked list."),
     _canned(6, True), {"cards": [{} for _ in range(8)]}, 5),
    # --- dynamic programming ---
    (_topic("knapsack_dp", _C, "dynamic_programming", "0/1 knapsack (DP)",
            "Fill a DP table of best value per capacity to solve 0/1 knapsack."),
     _canned(8, True), {"cards": [{} for _ in range(12)]}, 5),
    (_topic("lcs_dp", _C, "dynamic_programming", "Longest common subsequence (DP)",
            "Fill a 2-D DP table comparing two strings to find the LCS length."),
     _canned(8, True), {"cards": [{} for _ in range(12)]}, 5),
    # --- recursion ---
    (_topic("fibonacci_memo", _C, "recursion", "Memoized Fibonacci",
            "Compute Fibonacci with recursion + a memo table."),
     _canned(7, True), {"cards": [{} for _ in range(9)]}, 5),
    (_topic("tower_of_hanoi", _C, "recursion", "Tower of Hanoi",
            "Move a stack of disks between pegs via recursive subproblems."),
     _canned(7, True), {"cards": [{} for _ in range(10)]}, 5),
    # --- math / concept ---
    (_topic("quadratic_formula", "formula", "", "Quadratic formula",
            "Solve ax^2+bx+c=0 by substituting into the quadratic formula."),
     _canned(5), {"cards": [{} for _ in range(6)]}, 3),
    (_topic("set_operations", "concept", "", "Set operations",
            "Compute union, intersection, and difference of two sets."),
     _canned(5), {"cards": [{} for _ in range(6)]}, 3),
    (_topic("induction_proof", "proof", "", "Proof by induction",
            "Prove a summation identity by mathematical induction."),
     _concept_artifact(5), {"cards": [{} for _ in range(6)]}, 3),
    (_topic("big_o_concept", "concept", "", "Big-O of a loop",
            "Determine the time complexity of a nested loop."),
     _concept_artifact(5), {"cards": [{} for _ in range(7)]}, 3),
]


def _fake(artifact):
    return lambda payload: copy.deepcopy(artifact)


def _none(payload):
    return None


def _live() -> bool:
    key = os.getenv("OPENAI_API_KEY")
    return bool(key) and key.strip().lower() != "dummy"


def run() -> dict:
    _load_env()
    live = _live()
    mode = "LIVE" if live else "OFFLINE (canned artifacts - NOT live model output)"
    print(f"\n=== gen_foundation fixture measurement - {mode} ===\n")
    header = f"{'topic':<18}{'cards':>6}{'tokens':>8}{'calls':>7}{'valid':>7}{'audit':>7}{'recon':>12}  vs legacy"
    print(header)
    print("-" * len(header))

    comparisons = []
    diagnostics: list[tuple[str, RunResult]] = []
    for topic, canned, legacy_artifact, legacy_calls in FIXTURES:
        tid = topic["id"]
        if live:
            result: RunResult = run_first_pass(topic, solver=default_solver)
        else:
            result = run_first_pass(topic, solver=_fake(canned), auditor=_none)
        comp = compare_to_legacy(tid, result, legacy_artifact, legacy_calls)
        comparisons.append(comp)
        if live and (not result.ok or result.degraded or result.note):
            diagnostics.append((tid, result))
        s = comp.shadow
        print(
            f"{tid:<18}{s.card_count:>6}{s.output_tokens:>8}{s.model_calls:>7}"
            f"{('Y' if s.first_pass_valid else 'N'):>7}{('Y' if s.audit_edited else '-'):>7}"
            f"{s.reconciliation_status:>12}"
            f"  d_calls {comp.calls_delta:+d}  d_tok {comp.tokens_delta:+d}"
        )

    if diagnostics:
        print("\n--- diagnostics (for prompt tuning) ---")
        for tid, r in diagnostics:
            print(f"\n[{tid}] note={r.note or '-'}  degraded={r.degraded}")
            for e in (r.validation_errors or [])[:8]:
                print(f"   - {e}")

    agg = aggregate(comparisons)
    print("\n--- aggregate ---")
    print(json.dumps(agg, indent=2))
    if not _live():
        print("\n(OFFLINE: these prove the harness + validators run end-to-end. Set OPENAI_API_KEY "
              "in backend/.env and re-run for live numbers.)")
    return agg


if __name__ == "__main__":
    run()
