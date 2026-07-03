"""Worked-example trace pipeline — orchestration (WORKED_EXAMPLE_REASONING_SPEC.md v7, Phase 1).

Additive and flag-gated (`AZALEA_WORKED_EXAMPLE_TRACE_PIPELINE`, default OFF). Stages:
  0 select teaching instance  ·  1 produce trace (adapter-owned reference)  ·  2 verify (structural gate)
  ·  3 format cards (LLM writes PROSE ONLY; backend attaches state)  ·  4 fidelity  ·  4b prose fidelity.
Returns a legacy-shaped worked-example dict, or `None` to defer to the existing systems. The formatter is
injectable, so the whole pipeline is testable offline.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any, Callable, Optional

from .trace_adapters import ADAPTERS
from .trace_contract import (ContractTrace, Step, hard_prose_violations, structural_invariants,
                             validate_fidelity, validate_prose)

_log = logging.getLogger(__name__)

FormatFn = Callable[[dict[str, str]], Optional[Any]]   # {"system","user"} -> {"cards":[...]} | None
_MAX_FORMAT_ATTEMPTS = max(1, int(os.getenv("AZALEA_TRACE_PIPELINE_MAX_FORMAT_ATTEMPTS", "3")))


def _enabled() -> bool:
    return os.getenv("AZALEA_WORKED_EXAMPLE_TRACE_PIPELINE", "").strip().lower() in {"1", "true", "on", "yes"}


# --- routing (explicit, non-fuzzy, §17) ----------------------------------------------------------

# Routing SAFETY: a topic whose title is ABOUT a concept (an intro/overview/comparison), rather than a solvable
# INSTANCE of it, must not be handed a computational adapter even if it names the algorithm — it would ship a
# worked example the topic never asked for. Such topics defer (None) and degrade honestly.
_META_TITLE_MARKERS = ("introduction to", "history of", "applications of", "application of", "when to use",
                       "advantages of", "disadvantages of", "real-world", "real world", "comparison of",
                       "pros and cons", "why use", "why do we use", "big picture", "big-picture")
_NON_ROUTING_TYPES = ("study_path_introduction", "conceptual_overview", "topic_overview")


def route_adapter(topic: dict[str, Any]):
    """Explicit (non-fuzzy) routing: a topic enters the pipeline only when its slug/metadata or a tight
    title alias names one of the supported algorithms — AND it is a topic that actually wants a worked
    INSTANCE (not an intro/overview). Anything else returns None and defers to the existing systems.

    C2 Part 1 (no canonical code): coding-implementation topics now ALSO route to the adapter — they get the
    same VERIFIED conceptual trace as the walkthrough (correct), without per-step code-line highlighting
    (canonical code is Part 2, deferred). The code-walkthrough card still shows the code separately."""
    slug = str(topic.get("slug") or topic.get("topic_family") or topic.get("family") or "").lower()
    text = (slug + " " + str(topic.get("title") or topic.get("name") or "")).lower()
    # SAFETY: never route an intro/overview/meta topic to a computational adapter.
    ttype = str(topic.get("topic_type") or topic.get("course_type") or "").lower()
    if ttype in _NON_ROUTING_TYPES or any(m in text for m in _META_TITLE_MARKERS):
        return None
    return _match_adapter(text, slug)


def _match_adapter(text: str, slug: str):
    """The tight alias matcher (kept separate so the routing-safety guards wrap it cleanly)."""
    # Covered TREE + ALGEBRA concepts route explicitly (checked before the tree-defer guard below). Only
    # inorder BST traversal has a tree adapter today; other tree/BST topics still defer.
    if "inorder" in text or "in-order" in text:
        return ADAPTERS["tree_inorder"]
    if "preorder" in text or "pre-order" in text:
        return ADAPTERS["tree_preorder"]
    if "postorder" in text or "post-order" in text:
        return ADAPTERS["tree_postorder"]
    if "level order" in text or "level-order" in text or "levelorder" in text:
        return ADAPTERS["tree_levelorder"]
    # A BST *search* is a tree probe (not array binary search); but "binary search tree" also names
    # INSERTION/DELETION/TRAVERSAL topics — so strip the structure name, then require the search OPERATION.
    _bst_op = text.replace("binary search tree", " ").replace("binary-search tree", " ")
    if ("bst" in text or "binary search tree" in text) and "search" in _bst_op:
        return ADAPTERS["bst_search"]
    if "quadratic" in text:
        return ADAPTERS["quadratic"]
    if "kinematic" in text or "constant acceleration" in text or "uniform acceleration" in text:
        return ADAPTERS["kinematics"]
    # Tree traversal is a DIFFERENT algorithm from graph BFS/DFS (no visited-set / cycle handling; a
    # parent/child structure; pre/in/post/level order) — and a binary-search TREE is not array binary search.
    # These graph/array adapters do NOT cover trees, so a tree topic must NOT route here; it defers (None)
    # and degrades honestly per the coverage ladder rather than shipping a confidently-wrong trace.
    is_tree = any(k in text for k in ("tree", "bst", "inorder", "preorder", "postorder", "level order",
                                      "level-order", "subtree", "leaf"))
    if ("binary_search" in slug or "binary search" in text) and not is_tree:
        return ADAPTERS["binary_search"]
    if "kruskal" in text:
        return ADAPTERS["kruskal"]
    if "prim" in text:
        return ADAPTERS["prim"]
    if "merge sort" in text or "merge_sort" in text:
        return ADAPTERS["merge_sort"]
    if "quicksort" in text or "quick sort" in text or "quick_sort" in text:
        return ADAPTERS["quick_sort"]
    if "insertion sort" in text or "insertion_sort" in text:
        return ADAPTERS["insertion_sort"]
    if "selection sort" in text or "selection_sort" in text:
        return ADAPTERS["selection_sort"]
    if "bubble sort" in text or "bubble_sort" in text:
        return ADAPTERS["bubble_sort"]
    if "heapsort" in text or "heap sort" in text or "heap_sort" in text:
        return ADAPTERS["heap_sort"]
    if not is_tree and ("breadth-first" in text or "breadth first" in text or " bfs" in f" {text}"):
        return ADAPTERS["bfs"]
    if not is_tree and ("depth-first" in text or "depth first" in text or " dfs" in f" {text}"):
        return ADAPTERS["dfs_iter"]
    if "n-queens" in text or "n queens" in text or "nqueens" in text or "eight queens" in text or "queens problem" in text:
        return ADAPTERS["n_queens"]
    if "induction" in text or "prove that" in text or "proof by induction" in text or "mathematical induction" in text:
        return ADAPTERS["induction_proof"]
    if "euclid" in text or "euclidean" in text or "gcd" in text or "greatest common divisor" in text:
        return ADAPTERS["euclid_gcd"]
    if "union-find" in text or "union find" in text or "disjoint set" in text or "disjoint-set" in text or "union_find" in text:
        return ADAPTERS["union_find"]
    if "increasing subsequence" in text or "longest_increasing_subsequence" in text:
        return ADAPTERS["longest_increasing_subsequence"]
    if "order of operations" in text or "evaluate expression" in text or "arithmetic expression" in text:
        return ADAPTERS["arithmetic_eval"]
    if "bellman-ford" in text or "bellman ford" in text or "bellman_ford" in text or "bellmanford" in text:
        return ADAPTERS["bellman_ford"]
    if "dijkstra" in text or "shortest path" in text or "shortest-path" in text:
        return ADAPTERS["dijkstra"]
    return None


def _seed_for(topic: dict[str, Any]) -> int:
    tid = str(topic.get("id") or "").strip()
    if tid:
        key = tid                                          # a real topic id -> stable, reproducible instance
    else:
        # No id: salt with study-path + position so two SAME-TITLED topics (e.g. in different paths) do not
        # collapse to the identical instance. Falls back to the title alone when nothing else is present, so
        # title-only callers (tests) are unchanged.
        salt = "|".join(str(topic.get(k)) for k in ("study_path_id", "path_id", "order_index")
                        if topic.get(k) not in (None, ""))
        title = str(topic.get("title") or topic.get("name") or "x")
        key = f"{salt}|{title}" if salt else title
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % 1_000_000


# --- Stage 0 + 1: select a teaching instance and build its trace --------------------------------

def select_instance(adapter, seed: int) -> Optional[ContractTrace]:
    for attempt, cand in enumerate(adapter.candidates(seed), start=1):
        trace = adapter.reference(cand, candidate_id=str(cand.get("_id", "")), attempt=attempt, seed=seed)
        if adapter.is_teaching_trace(trace):
            return trace
    return None


# --- Stage 3: prose-only formatter + backend state attach ---------------------------------------

# Coding worked-example field contract (carried over from solver._CODING_CARDS_SYSTEM, §ADAPTER): the
# trace is the verified source of truth; the formatter's only job is to MAP each verified step onto the
# code the learner is shown — Work = the literal code line(s), Result = the runtime state. This is what
# makes the per-bullet active-line highlight precise (each Work bullet anchors to one source line).
_CODING_FORMAT_SYSTEM = (
    "You format an ALREADY-CORRECT, verified execution trace into CODE-ANCHORED worked-example cards — "
    "EXACTLY one card per step, in order. The trace is the source of truth: use ONLY each step's "
    "operation/decision/facts; never invent or alter a value, never add, remove, or reorder steps.\n"
    "FIELDS per card:\n"
    "- title: a SHORT, DISTINCT name for THIS step that NAMES the entity it acts on, in THIS algorithm's own "
    "terms (e.g. 'Add edge (A,B,7)', 'Compare arr[3] with the target', 'Merge two sorted runs') — NEVER the "
    "raw operation id like 'select_edge' (that repeats every step), and never borrow another algorithm's nouns.\n"
    "- goal: leave EMPTY — the card title already states the structural step (do not restate it).\n"
    "- reasoning: WHICH code construct implements it and why (the condition / loop / call / branch).\n"
    "- work: REQUIRED list. Each line BEGINS with the LITERAL code line from the CODE below, quoted "
    "VERBATIM with its variable names, THEN — REQUIRED on every line — ` // <plain-English of what this line "
    "does NOW, naming the concrete value(s) from this step>` (e.g. `lo = mid + 1  // move the lower bound "
    "past index 4`). Do NOT substitute the values into the code itself — put them in the // part. A line "
    "with no ` // ` is INVALID. Follow STAGE_GUIDANCE: show the `required` operation's code line as the "
    "DECISION, COMBINE `aggregated_supporting` lines into ONE summary line, and OMIT `internal` lines — aim for "
    "2–3 work lines, NOT every executed line. When a step RE-RUNS a loop body already shown in an earlier card, "
    "list ONLY the decision line + one `// the rest of the loop runs as shown above`; never re-list the "
    "unchanged machinery.\n"
    "- result: leave it BRIEF — it is REPLACED downstream by the step's verified state description, so it is "
    "only a fallback; focus your effort on reasoning + work. Never output a raw dict/JSON.\n"
    "- code_lines: for EACH work action, the 1-based line number(s) in the CODE it maps to, as a list of "
    "lists (e.g. [[18],[19],[20]]); use [] for a pure-narration line. One entry per work line.\n"
    'Return ONLY JSON: {"cards":[{"title","goal","reasoning","work":[...],"result","code_lines":[...]}, ...]}'
)


def _retry_feedback(reason: str, detail: list[str], n_steps: int) -> str:
    """Targeted feedback for the NEXT format attempt (the dominant withholds — prose_fail/count_mismatch
    — were retried with the SAME payload, so they never improved). Evidence from M7."""
    if reason == "count_mismatch":
        return (f"Your previous output had the WRONG number of cards. Produce EXACTLY {n_steps} cards — "
                "ONE per verified step, in order. Do not split a step into several cards or merge steps.")
    if reason == "prose_fail":
        return ("Your previous output failed these checks: " + "; ".join(detail) + ". "
                "Fix each: every step must NAME the exact entity/values it acts on (e.g. the edge and its "
                "weight) AND explicitly state its decision in words (accept/add vs skip/reject-as-cycle).")
    if reason == "work_too_long":
        return ("HARD LIMIT: each step's `work` MUST have AT MOST 2 lines. " + "; ".join(detail) + ". "
                "Line 1 = the single decision (the required op, naming the entity/values). Line 2 (only if "
                "needed) = ALL supporting operations combined into ONE phrase. Drop internal machinery "
                "entirely. Do NOT emit a separate work line per operation.")
    return ""


# §1a (STUDY_PATH_CONTENT_SPEC) — the instructional grammar the formatter was flying blind without.
_STAGE_GRAMMAR_RULE = (
    "\nINSTRUCTIONAL GRAMMAR — use STAGE_GUIDANCE below (keyed by each step's `operation`):\n"
    "- Lead the `reasoning` with THIS step's SPECIFIC decision — take the step's own `reason`/`decision` and "
    "say WHY this exact entity got this exact outcome (e.g. 'D and E are already connected, so adding this edge "
    "would form a cycle — skip it'). The stage's `teaching_focus` is the theme, NOT the sentence: NEVER repeat "
    "the teaching_focus verbatim across cards — each card's reasoning must differ by naming this step's entity "
    "and outcome. A card whose reasoning is generic (identical to a sibling card) is INVALID.\n"
    "- In `work`: surface the `required` operation as the step's single DECISION line; combine ALL "
    "`aggregated_supporting` operations into ONE summary line; OMIT `internal` operations unless the "
    "teaching_focus needs them. Aim for ~1-2 work lines — surface the decision, do not narrate machinery."
)


def _humanize_op(op: str) -> str:
    """Op identifiers in `contains` are internal snake_case tags (e.g. `emit_node`, `place_pivot`). They are
    surfaced to the formatter as the operations to state, and a lazy formatter can echo them VERBATIM into
    learner text ("emit_node 20" shipped in a real BST path). Convert to plain words at this boundary so the
    worst case is still readable English — one fix covers every adapter, current and future."""
    return op.replace("_", " ").strip()


def _stage_guidance(adapter: Any) -> dict[str, Any]:
    """Per-operation instructional grammar from the adapter's example_spec: teaching_focus + the role of
    each contained operation (required / aggregated_supporting / internal). Op names are humanized so no raw
    machine token can leak into a card. Empty if not declared."""
    spec = getattr(adapter, "example_spec", None)
    stages = getattr(spec, "stages", None) if spec is not None else None
    if not stages:
        return {}
    out: dict[str, Any] = {}
    for sid, st in stages.items():
        contains = getattr(st, "contains", None) or {}
        out[sid] = {
            "teaching_focus": getattr(st, "teaching_focus", "") or "",
            "required": [_humanize_op(op) for op, r in contains.items() if r == "required"],
            "aggregated_supporting": [_humanize_op(op) for op, r in contains.items() if r == "aggregated_supporting"],
            "internal": [_humanize_op(op) for op, r in contains.items() if r == "internal"],
        }
    return out


def build_format_payload(trace: ContractTrace, code: Optional[str] = None,
                         feedback: str = "", adapter: Any = None) -> dict[str, str]:
    steps = [{
        "id": s.id, "operation": s.operation, "inputs": s.inputs,
        "prior_state": s.prior_state, "state_after": s.state_after,
        "decision": s.decision, "reason": s.reason,        # the VERIFIED, step-specific "why" (C1/E4)
        "expected_visible_result": s.expected_visible_result, "facts": s.facts,
    } for s in trace.steps]
    fb = f"\n\nFIX FROM THE PREVIOUS ATTEMPT (address ALL of this):\n{feedback}" if feedback else ""
    guidance = _stage_guidance(adapter)
    g_rule = _STAGE_GRAMMAR_RULE if guidance else ""
    g_text = f"\n\nSTAGE_GUIDANCE (per step.operation):\n{json.dumps(guidance, default=str)}" if guidance else ""
    if code:                                                   # coding topic — anchor Work to the shown code
        numbered = "\n".join(f"{i:>3}  {ln}" for i, ln in enumerate(code.split("\n"), start=1))
        user = (f"PROBLEM: {trace.problem}\n\nCODE (1-based line numbers — anchor every work line and "
                f"code_lines entry to THESE lines):\n{numbered}{g_text}{fb}\n\nProduce EXACTLY {len(steps)} "
                f"cards — one per step below, in order; do NOT merge or split steps.\n\nSTEPS (verified, "
                f"describe faithfully):\n{json.dumps(steps, default=str)}")
        return {"system": _CODING_FORMAT_SYSTEM + g_rule, "user": user}
    system = (
        "You format an ALREADY-CORRECT, verified solution into learner-facing step cards. Write EXACTLY "
        "one card per step, in order (do NOT split or merge steps). For each card write only: title, goal, "
        "reasoning, work (list), result. Use ONLY the step's facts — state EVERY required_fact, use only "
        "allowed_values, never make a forbidden_claim. "
        "EACH card MUST (a) NAME the exact entity and values the step acts on — taken from THIS step's facts "
        "(e.g. an edge '(A,C,13)', a probe 'arr[3]=21', a merge of '[3] and [5]') — and (b) STATE the "
        "decision in words, in THIS algorithm's own terms (e.g. 'add it / accept'; 'move the lower bound to "
        "6'; 'copy 3 to the output'; 'skip it — it would form a cycle'). Use this algorithm's nouns, never "
        "another's. A step that omits the entity/values or the decision is INVALID. "
        "Do NOT invent or alter any value, and do NOT output any machine-state/JSON-state fields. "
        'Return ONLY JSON: {"cards":[{"title","goal","reasoning","work":[...],"result"}, ...]}'
    ) + g_rule
    user = (f"PROBLEM: {trace.problem}{g_text}{fb}\nProduce EXACTLY {len(steps)} cards — one per step below, "
            f"in order; do NOT merge or split steps.\nSTEPS (verified, describe faithfully):\n"
            f"{json.dumps(steps, default=str)}")
    return {"system": system, "user": user}


def _collapse_repeated_coding_work(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """§5.4 / study-path review — an iterative algorithm's coding cards re-run the SAME loop body every step, so
    re-listing all its lines on cards 2..N is a wall of near-identical code (Prim: 6 lines × 4 selects). Once a
    step's code lines were ALL taught in an earlier card, keep this card's decision line(s) and elide the
    already-shown machinery — the learner saw the full loop on its first appearance. Truth is untouched (the
    result is the verified EVR; the decision + entity stay in the kept lines and the result)."""
    shown: set[str] = set()
    for c in cards:
        if "code_lines" not in c:                              # coding cards only
            continue
        work = c.get("work") or []
        codeparts = [str(w).split("//", 1)[0].strip() for w in work]
        new = [cp for cp in codeparts if cp and cp not in shown]
        if not new and work:                                   # nothing new here — a repeated body (loop OR recursion)
            if len(work) > 2:                                  # a multi-line loop body: keep the decision, elide the rest
                c["work"] = work[:2] + ["…the rest of the loop body runs exactly as shown above."]
                cl = c.get("code_lines") or []
                if cl:
                    c["code_lines"] = cl[:2] + [[]]
            else:                                              # a repeated 1-2 line body (e.g. a recursion's return
                c["work"] = ["…the same code runs, producing this step's value (see the result)."]  # line): don't reprint
                c["code_lines"] = [[]]
        else:
            shown.update(cp for cp in codeparts if cp)
    return cards


def _norm_txt(s: str) -> str:
    """Loose text key for 'is this reasoning just the generic stage line?' — lowercase, collapse whitespace,
    drop trailing punctuation."""
    return re.sub(r"\s+", " ", str(s or "").strip().lower()).rstrip(".!;: ")


def _normalize_and_attach(raw: Any, trace: ContractTrace,
                          adapter: Any = None) -> Optional[list[dict[str, Any]]]:
    cards = raw.get("cards") if isinstance(raw, dict) else raw
    if not isinstance(cards, list) or len(cards) != len(trace.steps):   # v1: one card per step
        return None
    guidance = _stage_guidance(adapter) if adapter is not None else {}
    terminal = str(getattr(getattr(adapter, "example_spec", None), "terminal", "") or "")
    out: list[dict[str, Any]] = []
    for card, step in zip(cards, trace.steps):
        if not isinstance(card, dict):
            return None
        # C7 / anti-hardcoding: the learner-facing `result` is ALWAYS the step's VERIFIED prose
        # (expected_visible_result) — never the LLM's. This makes it correct by construction (no raw-dict, no
        # cross-algorithm wording leak — the model can't write "all vertices connected" on a sort because it
        # doesn't write the result at all) and removes the truth-bearing field from the LLM. The model still
        # writes reasoning/work. Falls back to the LLM result only if the adapter gives no EVR for this step.
        evr = str(getattr(step, "expected_visible_result", "") or "").strip()
        result = evr or str(card.get("result", "")).strip()
        # C1/E4 backstop: if the model left reasoning empty OR just echoed the stage's generic teaching_focus
        # (the #1 observed coding bug — 7 identical "add an edge only when..." cards, incl. on the SKIP card),
        # fall back to THIS step's VERIFIED reason, which names the exact entity + decision (e.g. "D and E are
        # already connected — skip (would form a cycle)"). The verified reason beats a generic repeated line.
        reasoning = str(card.get("reasoning", "")).strip()
        focus = str((guidance.get(step.operation) or {}).get("teaching_focus", "")).strip()
        step_reason = str(getattr(step, "reason", "") or "").strip()
        if step_reason and (not reasoning or _norm_txt(reasoning) == _norm_txt(focus)):
            reasoning = step_reason
        c: dict[str, Any] = {
            "title": str(card.get("title", "")).strip(),
            "goal": str(card.get("goal", "")).strip(),
            "reasoning": reasoning,
            "work": [str(w) for w in (card.get("work") or [])],
            "result": result,
        }
        if isinstance(card.get("code_lines"), list):           # coding path: per-action anchors (validated downstream)
            c["code_lines"] = card["code_lines"]
        # backend attaches the truth-bearing fields deterministically (§11) — the model never produced them
        c["trace_step_ids"] = [step.id]
        c["prior_state"] = step.prior_state
        c["result_state"] = step.state_after
        c["visual_state"] = step.visual_state
        c["visual_delta"] = step.visual_delta
        if not c["work"] or not c["result"]:
            return None
        out.append(c)
    _collapse_repeated_coding_work(out)                         # §5.4: elide a re-run loop body on later cards
    _ensure_completion(out, trace, terminal)                    # C4: completion + stopping criterion
    return out


def _final_answer_text(trace: ContractTrace) -> str:
    fa = trace.final_answer
    if isinstance(fa, dict):
        if "found_index" in fa:
            k = fa["found_index"]
            return f"found at index {k}" if isinstance(k, int) and k >= 0 else "target is absent (index -1)"
        if "visit_order" in fa:
            return "visit order: " + ", ".join(map(str, fa["visit_order"]))
        if "mst_edges" in fa:
            from .trace_adapters.families.graph import fmt_edges
            return f"MST edges: {fmt_edges(fa['mst_edges'])} (total weight {fa.get('total_weight')})"
        if "sorted" in fa:
            return "sorted: " + ", ".join(map(str, fa["sorted"]))
        if "roots" in fa:                                          # quadratic
            rs = fa["roots"]
            return "x = " + " and x = ".join(map(str, rs)) if rs else "no real roots"
        if "found_at" in fa:                                       # BST search
            return f"found at node {fa['found_at']}" if fa.get("found") else "the target is absent"
        if "lis_length" in fa:                                     # longest increasing subsequence (DP)
            return f"longest increasing subsequence length = {fa['lis_length']}"
        if "queen_rows" in fa:                                     # N-Queens (backtracking)
            rows = fa["queen_rows"]
            return "queens on rows " + ", ".join(map(str, rows)) + " (one per column, left to right)"
        if "groups" in fa:                                         # union-find (disjoint sets) — no braces (guard)
            return "; ".join(f"group {i + 1}: {', '.join(map(str, g))}"
                             for i, g in enumerate(fa["groups"]))
        if "gcd" in fa:                                            # Euclid GCD (program execution)
            return f"gcd = {fa['gcd']}"
        if "claim" in fa:                                          # induction proof (formal derivation)
            return f"proved by induction: {fa['claim']}"
        if "value" in fa:
            return f"= {fa['value']}"
        if "dist" in fa:
            return "shortest distances: " + ", ".join(f"{k} = {v}" for k, v in fa["dist"].items())
        # generic clean fallback — NEVER a raw dict/list repr (kinematics {v,s}, a stray sequence key, etc.):
        # scalars render "v = 2"; a list renders comma-joined ("7, 21, 23") so brackets never leak to a learner.
        def _fmt(v: Any) -> str:
            return ", ".join(map(str, v)) if isinstance(v, (list, tuple)) else str(v)
        return ", ".join(f"{k} = {_fmt(v)}" for k, v in fa.items())
    return str(fa)


_COMPLETE_RE = re.compile(r"complete|all (?:nodes|vertices|elements)|finished|\bdone\b|\bfinal\b", re.I)


def _ensure_completion(cards: list[dict[str, Any]], trace: ContractTrace, terminal: str = "") -> None:
    """C4/C7: the trace ran to its terminal, so the LAST card must state completion. If its result doesn't
    already say so, append a deterministic, verified completion clause that states BOTH the stopping CRITERION
    (why the algorithm is done — e.g. 'V−1 edges accepted (a spanning tree)') and the final answer. The
    criterion is the adapter's declared `terminal`; a learner who is uncertain needs to know WHY it stopped, not
    just the result. Works for every adapter and both the LLM and trace-preserving paths."""
    if not cards:
        return
    last = cards[-1]
    res = str(last.get("result") or "").rstrip()
    if _COMPLETE_RE.search(res):
        return
    ans = _final_answer_text(trace)
    crit = str(terminal or "").strip().rstrip(".")
    tail = f"Complete: {crit}. Final result: {ans}." if crit else f"Complete — final result: {ans}."
    last["result"] = (res.rstrip(".") + ". " + tail).lstrip(". ")


def _coverage_fields(trace: ContractTrace, cards: list[dict[str, Any]]) -> dict[str, Any]:
    """CP6 report invariants: which verified transitions the shipped cards actually rendered, whether every
    required case is covered, and whether the terminal/completion is stated. Lets an audit (and the standing
    invariant check) catch a missing required transition or a missing completion without eyeballing."""
    rendered = [sid for c in cards for sid in (c.get("trace_step_ids") or [])]
    rendered_set = set(rendered)
    required = list(getattr(trace, "required_cases", []) or [])
    evidence = getattr(trace, "case_evidence", {}) or {}
    missing = [rc for rc in required if not (set(evidence.get(rc, [])) & rendered_set)]
    last_result = str(cards[-1].get("result", "")) if cards else ""
    terminal_rendered = bool(_COMPLETE_RE.search(last_result)) and bool(
        trace.steps and trace.steps[-1].id in rendered_set)
    return {"trace_ids_rendered": rendered, "required_transition_ids": required,
            "missing_required_transition_ids": missing, "terminal_rendered": terminal_rendered}


def _attach_checkpoints(cards: list[dict[str, Any]], trace: ContractTrace, adapter: Any) -> list[Any]:
    """CP3a — attach the adapter's default (identity) TeachingCheckpoint provenance to each shipped card so every
    learner-facing artifact cites exactly one `checkpoint_id` (spec §2.5.2 / §7.3). Identity projection: one
    checkpoint per trace transition, so a card for step X cites the checkpoint whose source range covers X.
    Returns the checkpoint list for report coverage. ADDITIVE — provenance never blocks a verified ship."""
    try:
        checkpoints = list(adapter.teaching_checkpoints(trace) or [])
    except Exception:  # noqa: BLE001 — provenance is best-effort; a verified trace still ships without it
        return []
    by_step: dict[str, Any] = {}
    for cp in checkpoints:
        for sid in getattr(cp, "source_step_ids", []) or []:
            by_step.setdefault(sid, cp)
    for c in cards:
        cp = next((by_step[s] for s in (c.get("trace_step_ids") or []) if s in by_step), None)
        if cp is None:
            continue
        ids = list(getattr(cp, "source_step_ids", []) or [])
        c["checkpoint_id"] = cp.checkpoint_id
        c["source_transition_start"] = cp.source_step_start or (ids[0] if ids else "")
        c["source_transition_end"] = cp.source_step_end or (ids[-1] if ids else "")
    return checkpoints


def _checkpoint_coverage_fields(trace: ContractTrace, cards: list[dict[str, Any]],
                                checkpoints: list[Any]) -> dict[str, Any]:
    """CP6b — checkpoint-level audit provenance: which checkpoints the cards rendered, which are REQUIRED (their
    source range holds a required transition, spec §CP3a derivation), and which required ones are missing."""
    rendered = [c.get("checkpoint_id") for c in cards if c.get("checkpoint_id")]
    rendered_set = set(rendered)
    evidence = getattr(trace, "case_evidence", {}) or {}
    required_steps = {sid for ids in evidence.values() for sid in ids}
    required_cp = [cp.checkpoint_id for cp in checkpoints
                   if set(getattr(cp, "source_step_ids", []) or []) & required_steps]
    missing = [cid for cid in required_cp if cid not in rendered_set]
    return {"checkpoint_ids_rendered": rendered, "required_checkpoint_ids": required_cp,
            "missing_required_checkpoint_ids": missing}


def _prose_validation_field(prose: Any) -> dict[str, Any]:
    """CP6b — the structured `prose_validation` report object: the contract-partitioned prose result split into
    `hard_failures` (would block) + `soft_warnings` (advisory, never block). Replaces the flat prose recording so
    an audit can see exactly what fired. A shipped adapter example should carry NO hard failures (§4.0 Truth is
    the only withhold; a hard NARRATION failure retries → deterministic narration)."""
    items = list(prose or [])
    hard = hard_prose_violations(items)
    hard_ids = {id(v) for v in hard}

    def _v(x: Any) -> dict[str, Any]:
        return {"code": getattr(x, "code", ""), "detail": getattr(x, "detail", ""),
                "trace_step_id": getattr(x, "trace_step_id", "")}
    return {"prose_validation": {
        "hard_failures": [_v(v) for v in hard],
        "soft_warnings": [_v(v) for v in items if id(v) not in hard_ids]}}


def _to_solve_result(trace: ContractTrace, cards: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "problem": trace.problem,
        "cards": cards,
        "final_answer": _final_answer_text(trace),
        "expected_final_answer": _final_answer_text(trace),
        "generated_by": "trace_pipeline",
        "trace_first": True,
        "metadata": {"worked_example_source": "trace_pipeline", "provenance": trace.provenance},
    }


def _det_step_title(step: Step, i: int) -> str:
    # prefer the visible result (it names the entity: "Edge (A,C,1) accept") over the bare decision verb
    src = str(getattr(step, "expected_visible_result", "") or getattr(step, "decision", "")
              or getattr(step, "operation", "") or "").strip()
    head = re.split(r"[;:.\n]", src, maxsplit=1)[0].strip()[:60].strip()
    return f"Step {i + 1}: {head}" if head else f"Step {i + 1}"


def _deterministic_narration(trace: ContractTrace, adapter: Any = None) -> list[dict[str, Any]]:
    """ADAPTER_AND_GENERATION_SYSTEM_SPEC §4.3.1 step 2 — build cards DIRECTLY from the verified trace (no
    LLM), trace-preserving by construction. Used when the LLM narration fails its gate: per §1.2 we never
    discard the verified trace to a from-scratch fallback, so we ship a terse-but-correct narration of the
    SAME trace. Each card's truth-bearing fields are the step's own (prior/after state, decision, result)."""
    terminal = str(getattr(getattr(adapter, "example_spec", None), "terminal", "") or "")
    out: list[dict[str, Any]] = []
    for i, step in enumerate(trace.steps):
        evr = str(getattr(step, "expected_visible_result", "") or "").strip()
        decision = str(getattr(step, "decision", "") or "").strip()
        reason = str(getattr(step, "reason", "") or "").strip()
        out.append({
            "title": _det_step_title(step, i),
            "goal": "",
            "reasoning": reason,
            "work": [decision] if decision else ([evr] if evr else ["state update"]),
            "result": evr or decision or "state updated",
            "trace_step_ids": [step.id],
            "prior_state": step.prior_state,
            "result_state": step.state_after,
            "visual_state": step.visual_state,
            "visual_delta": step.visual_delta,
        })
    _ensure_completion(out, trace, terminal)                    # C4: completion + stopping criterion
    return out


# --- top-level orchestration --------------------------------------------------------------------

def _reason_extract_enabled() -> bool:
    return os.getenv("AZALEA_WORKED_EXAMPLE_REASON_EXTRACT", "").strip().lower() in {"1", "true", "on", "yes"}


def solve_trace_pipeline(topic: dict[str, Any], *, format_fn: Optional[FormatFn] = None,
                         reason_fn: Optional[FormatFn] = None, extract_fn: Optional[FormatFn] = None,
                         critic_fn: Optional[FormatFn] = None, seed: Optional[int] = None,
                         code: Optional[str] = None
                         ) -> Optional[dict[str, Any]]:
    from . import generation_report as _gr
    fmt = format_fn or default_format_fn
    title = str(topic.get("title") or topic.get("name") or topic.get("id") or "?")
    ctype = str(topic.get("topic_type") or topic.get("course_type") or "?")
    adapter = route_adapter(topic)
    if adapter is not None:                                        # deterministic path (HARD guarantee)
        _log.info("WORKED-EXAMPLE ADAPTER: topic=%r type=%s -> adapter=%s (verified trace path)",
                  title, ctype, adapter.slug)
        _gr.we(adapter=adapter.slug, tp_attempted=True)
        seed = seed if seed is not None else _seed_for(topic)
        trace = select_instance(adapter, seed)                     # Stage 0 + 1
        if trace is None or structural_invariants(trace, adapter):  # §5 gate (Stage 2 is ground truth)
            _log.warning("WORKED-EXAMPLE ADAPTER: topic=%r adapter=%s -> WITHHELD (no teaching trace) — defer",
                         title, adapter.slug)
            _gr.we(tp_shipped=False, tp_reason="no_teaching_trace")
            return None
        result = _format_validate_ship(topic, trace, adapter, fmt, code=code)
        _log.info("WORKED-EXAMPLE ADAPTER: topic=%r adapter=%s -> %s",
                  title, adapter.slug, "SHIPPED (verified)" if result is not None else "withheld (defer)")
        return result
    _guard = " [BLOCKED by coding_implementation guard - needs C2]" if ctype == "coding_implementation" else ""
    _log.info("WORKED-EXAMPLE ADAPTER: topic=%r type=%s -> NO adapter%s (deferring to gen_foundation/legacy)",
              title, ctype, _guard)
    _gr.we(adapter=None, tp_attempted=False, tp_reason="no_adapter")
    if _reason_extract_enabled():                                  # non-deterministic path (SOFT) — opt-in
        return _solve_via_reason_extract(topic, fmt, reason_fn, extract_fn, critic_fn)
    return None                                                    # defer to existing systems


def _format_validate_ship(topic, trace, adapter, fmt, *, code: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Stage 3 + 4 + 4b (WORKED_EXAMPLE_REASONING_SPEC v8 §13): prose-only format, backend state-attach,
    then SPLIT BY FAILURE SOURCE — a fidelity failure is a backend/trace defect a formatter retry cannot
    fix (withhold + log immediately); only a HARD prose contradiction is worth re-formatting; missing/soft
    prose is advisory in Phase 1 (logged, not blocking). `validate_visual_state=False` in Phase 1."""
    from . import generation_report as _gr
    last_raw, last_cards, last_prose = None, None, None
    reason, detail, attempts, feedback = "formatter_none", [], 0, ""
    n_steps = len(trace.steps)
    for _ in range(_MAX_FORMAT_ATTEMPTS):
        attempts += 1
        raw = fmt(build_format_payload(trace, code=code, feedback=feedback, adapter=adapter))   # §1a + M7 retry
        cards = _normalize_and_attach(raw, trace, adapter)
        last_raw, last_cards = raw, cards
        if cards is None:                                          # formatter produced nothing usable -> retry
            n_raw = len(raw["cards"]) if isinstance(raw, dict) and isinstance(raw.get("cards"), list) else None
            reason = "count_mismatch" if (n_raw is not None and n_raw != n_steps) else "formatter_none"
            detail = [f"formatter cards={n_raw} vs verified steps={n_steps}"] if reason == "count_mismatch" else ["formatter returned no usable cards"]
            feedback = _retry_feedback(reason, detail, n_steps)
            continue
        fid = validate_fidelity(cards, trace, adapter, validate_visual_state=False)
        if not fid.ok:                                             # BACKEND/TRACE defect — retry can't fix it
            _log.error("trace_pipeline: %s fidelity failure %r (backend/trace defect) — withholding",
                       getattr(adapter, "slug", "?"), fid.code)
            _retain_debug(topic, trace, raw, cards, fid, [], shipped=False)
            _gr.we(tp_shipped=False, tp_reason="fidelity_fail", tp_detail=[str(fid.code)],
                   verified_steps=n_steps, formatter_cards=len(cards), tp_attempts=attempts)
            return None
        prose = validate_prose(cards, trace, adapter, code_anchored=bool(code))
        last_prose = prose
        hard = hard_prose_violations(prose)
        advisory = [v for v in prose if v.severity != "hard"]
        if advisory:
            _log.info("trace_pipeline: %s advisory prose (missing/soft) x%d", adapter.slug, len(advisory))
        if not hard:                                               # contradictions are the only blocker
            # M6 quality gate (§1a aggregation): a WALKTHROUGH step should be ~1-2 work lines. Retry to
            # enforce it, but NEVER withhold over shape — ship on the final attempt even if still verbose.
            from .content_shape import _MAX_WORK_LINES
            over = sum(1 for c in cards if len(c.get("work") or []) > _MAX_WORK_LINES)
            if not code and over and attempts < _MAX_FORMAT_ATTEMPTS:
                reason = "work_too_long"
                detail = [f"{over} step(s) have > {_MAX_WORK_LINES} work lines"]
                feedback = _retry_feedback(reason, detail, n_steps)
                continue
            checkpoints = _attach_checkpoints(cards, trace, adapter)   # CP3a: one checkpoint_id per card
            _retain_debug(topic, trace, raw, cards, fid, prose, shipped=True)
            _gr.we(tp_shipped=True, tp_reason="shipped", verified_steps=n_steps,
                   formatter_cards=len(cards), tp_attempts=attempts, work_over_cap=over or None)
            _gr.we(**_coverage_fields(trace, cards))           # CP6 coverage/terminal instrumentation
            _gr.we(**_checkpoint_coverage_fields(trace, cards, checkpoints))   # CP6b checkpoint provenance
            _gr.we(**_prose_validation_field(prose))           # CP6b structured prose_validation
            return _to_solve_result(trace, cards)
        reason = "prose_fail"                                      # a hard contradiction -> re-format
        detail = [f"{v.code} {v.detail} ({v.trace_step_id})" for v in hard][:6]
        feedback = _retry_feedback(reason, detail, n_steps)        # targeted: tell it exactly what to fix
    # §1.2 / §4.3.1 step 2 — the LLM narration failed its gate after every retry, but the trace is GROUND
    # TRUTH. We never discard it to a from-scratch fallback: ship a trace-preserving deterministic narration
    # of the SAME verified trace. (A fidelity failure already returned None above — that's a trace defect,
    # not a narration one.) `narration_failed_reason` records WHY the LLM path was abandoned, for M7.
    det_cards = _deterministic_narration(trace, adapter)
    checkpoints = _attach_checkpoints(det_cards, trace, adapter)   # CP3a: one checkpoint_id per card
    det_prose = validate_prose(det_cards, trace, adapter, code_anchored=bool(code))   # what actually shipped
    _retain_debug(topic, trace, last_raw, last_cards, None, last_prose, shipped=True)
    _gr.we(tp_shipped=True, tp_reason="trace_preserving_narration", narration="deterministic",
           narration_failed_reason=reason, tp_detail=detail, verified_steps=n_steps,
           formatter_cards=len(det_cards), tp_attempts=attempts)
    _gr.we(**_coverage_fields(trace, det_cards))               # CP6 coverage/terminal instrumentation
    _gr.we(**_checkpoint_coverage_fields(trace, det_cards, checkpoints))   # CP6b checkpoint provenance
    _gr.we(**_prose_validation_field(det_prose))               # CP6b structured prose_validation
    return _to_solve_result(trace, det_cards)


def _solve_via_reason_extract(topic, fmt, reason_fn, extract_fn, critic_fn) -> Optional[dict[str, Any]]:
    """SOFT path: the model reasons in prose then a trace is extracted; a critic verifies it (Stage 2);
    then the same format + fidelity + prose machinery applies. Offline / on any miss -> None (defer)."""
    from .reason_extract import produce_via_reason_extract
    from .verifiers import verify_via_critic
    from .trace_adapters.generic import GenericAdapter
    trace = produce_via_reason_extract(
        topic, topic.get("example_input") or {},
        reason_fn=reason_fn or _default_reason_fn, extract_fn=extract_fn or _default_extract_fn)
    if trace is None:
        return None
    adapter = GenericAdapter()
    if structural_invariants(trace, adapter):
        return None
    if verify_via_critic(trace, critic_fn=critic_fn or _default_critic_fn).illegal_step:
        return None                                               # critic rejected -> withhold
    return _format_validate_ship(topic, trace, adapter, fmt)


def _retain_debug(topic: dict[str, Any], trace: ContractTrace, raw: Any, cards: Any,
                  fid: Any, prose: Any, *, shipped: bool) -> None:
    """Internal-only debug payload (§18): input, conventions, trace, formatter raw, cards, results — so a
    failure reads as 'reference correct -> formatter prose drifted at card N'. Off unless a path is set."""
    path = os.getenv("AZALEA_TRACE_PIPELINE_DEBUG_PATH")
    if not path:
        return
    try:
        from dataclasses import asdict
        payload = {
            "topic": {k: topic.get(k) for k in ("id", "title", "slug")},
            "shipped": shipped, "provenance": trace.provenance, "conventions": trace.conventions,
            "problem": trace.problem, "final_answer": trace.final_answer,
            "steps": [asdict(s) for s in trace.steps],
            "formatter_raw": raw, "normalized_cards": cards,
            "fidelity": (asdict(fid) if fid else None),
            "prose_violations": [asdict(p) for p in (prose or [])],
        }
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception as exc:  # noqa: BLE001 — debug retention must never affect generation
        _log.debug("trace_pipeline debug retain failed: %s", exc)


def _llm_call(payload: dict[str, str], label: str, *, json_mode: bool = True) -> Optional[Any]:
    """Shared LLM seam (None offline / on failure). json_mode=True parses a JSON object; False returns text."""
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip().lower() == "dummy":
        return None
    try:
        from app.services.llm_client import OPENAI_MODEL, client, llm_call
        kwargs: dict[str, Any] = {
            "model": OPENAI_MODEL,
            "input": [{"role": "system", "content": payload.get("system", "")},
                      {"role": "user", "content": payload.get("user", "")}],
        }
        if json_mode:
            kwargs["text"] = {"format": {"type": "json_object"}}
        with llm_call(label):
            response = client.with_options(
                timeout=float(os.getenv("AZALEA_ENRICH_TIMEOUT_SECONDS", "60")),
                max_retries=max(0, int(os.getenv("AZALEA_ENRICH_MAX_RETRIES", "2"))),
            ).responses.create(**kwargs)
        return json.loads(response.output_text) if json_mode else response.output_text
    except Exception as exc:  # noqa: BLE001
        _log.warning("trace_pipeline %s call failed: %s", label, exc)
        return None


def default_format_fn(payload: dict[str, str]) -> Optional[Any]:
    return _llm_call(payload, "we_trace_format", json_mode=True)


def _default_reason_fn(payload: dict[str, str]) -> Optional[Any]:
    return _llm_call(payload, "we_trace_reason", json_mode=False)


def _default_extract_fn(payload: dict[str, str]) -> Optional[Any]:
    return _llm_call(payload, "we_trace_extract", json_mode=True)


def _default_critic_fn(payload: dict[str, str]) -> Optional[Any]:
    return _llm_call(payload, "we_trace_critic", json_mode=True)
