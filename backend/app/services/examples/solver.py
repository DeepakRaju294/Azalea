"""LLM worked-example solver — problem-first, solved start-to-finish.

The example-type/ontology/fixture apparatus is bypassed for non-code topics. Instead we
DECLARE one concrete problem and have the LLM solve it completely in a single FOCUSED call,
then render the structured solution as the worked example. The model is reliable at "solve
this one problem and show all work"; isolating that from whole-lesson generation is what
makes the example come out right the first time instead of being audited/regenerated after.

This is Slice 1: the full TEXT breakdown with guaranteed start-to-finish completion (the
last card carries the final answer and is stamped reaches_final_answer). Math verification
and best-effort visuals are separate, later slices.

Design rules:
  - Coding topics are NOT handled here — they keep the machine-authoritative execution
    trace (apply_code_execution_to_lesson). This is the path for everything else.
  - Failure-safe: any problem (no API key, bad JSON, empty solution) leaves the lesson's
    existing worked example untouched — we never empty or break a lesson.
  - The solver function is injectable (tests pass a stub; production uses the real LLM).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable, Optional

_log = logging.getLogger(__name__)

# Bump when the solve contract / card shape changes, so cached lessons re-solve on read.
SOLVER_VERSION = 1

# A multi-step worked example with fewer than this many step cards skipped the work — re-solve
# with feedback. (Genuine boundary cases that come back short on the retry are shipped.)
_MIN_STEP_CARDS = 5

# How many times the example may be RE-SOLVED when it comes back incomplete. A re-solve re-runs the
# WHOLE outline+cards (2-3 more LLM calls, ~40s) and often does NOT improve the result, so it's the
# biggest avoidable cost — default OFF. The outline gate already enforces quality upstream, and
# example_status still flags any residual. Set AZALEA_EXAMPLE_MAX_RESOLVES=1 for stricter quality.
_MAX_RESOLVE_ATTEMPTS = max(0, int(os.getenv("AZALEA_EXAMPLE_MAX_RESOLVES", "0")))

# Per-call timeout (seconds) for the enrich-time LLM calls, so a hung call can't stall the serial
# study-path build. Retries are KEPT (transient rate-limit/5xx must recover, or the worked example is
# silently dropped); the timeout bounds total latency to <= (1 + retries) x timeout.
_ENRICH_TIMEOUT = float(os.getenv("AZALEA_ENRICH_TIMEOUT_SECONDS", "60"))
_ENRICH_MAX_RETRIES = max(0, int(os.getenv("AZALEA_ENRICH_MAX_RETRIES", "2")))

# solver(payload) -> structured solution dict | None. payload carries the built prompt.
SolveFn = Callable[[dict[str, Any]], Optional[dict[str, Any]]]


def solver_enabled() -> bool:
    """Default ON; flip off with AZALEA_WORKED_EXAMPLE_SOLVER=0."""
    return os.getenv("AZALEA_WORKED_EXAMPLE_SOLVER", "1").strip().lower() not in {"0", "false", "off", "no"}


# The platform's worked-example card rules (a faithful distillation of the worked-example
# DEPTH + bullet-shape rules in LEAN_SYSTEM_PROMPT), so a solved example formats and reads
# exactly like the rest of the platform's cards. The example PROBLEM rules are the shared
# EXAMPLE_PROBLEM_RULES (one rule system for how problems are made).
from app.services.examples.example_blueprint import EXAMPLE_PROBLEM_RULES

_ATOMIC_RULES = """

ATOMIC STEP REQUIREMENT — ONE independently-understandable reasoning transition per step/card:
- Each step is ONE primary operation with ONE resulting advancement. A primary operation is one
  decision, comparison, calculation, state update, recursive call, recursive return, merge
  selection, structural transformation, or verification.
- ATOMIC DOES NOT MEAN TINY. A step may show several lines of work when they belong to ONE
  operation — "mid = (0 + 3) // 2 = 1" with its result is one step; "compare the two front values
  and append the smaller, advancing its pointer" is ONE merge-selection step. The test: can the
  work be read as ONE cause-and-effect transition? If yes, keep it; if it is a sequence of
  separately-reasoned transitions, split it.
- SPLIT a step when its work bundles operations that change state separately, need separate
  reasoning, could fail independently, or would be highlighted separately. NEVER bundle a split +
  two recursive calls + a merge into one step.
- FORBIDDEN high-level placeholders — expand them into the ACTUAL operations performed: "sort the
  left half", "recurse on both sides", "merge the results", "process the subtree", "continue the
  algorithm", "solve the smaller problem".
- RECURSION EXPANSION: never treat a recursive call as a completed high-level action. For each
  recursive call show, as separate steps: the input passed in, the descent, the base case reached,
  the returned result, and the resumed parent operation that uses it.
- The example MAY exceed expected_min_steps. Do NOT compress genuine operations to keep it short;
  do NOT over-split one coherent transition into tedious micro-cards either."""

_WORKED_EXAMPLE_RULES = (
    EXAMPLE_PROBLEM_RULES
    + _ATOMIC_RULES
    + """
- The solution must run MORE THAN 5 steps. If your instance resolves in fewer, pick a richer
  instance. (Only a pure boundary topic — "empty input", "single element" — may be shorter,
  because the boundary itself is the lesson.)

CARD STRUCTURE (follow exactly)"""
    + """
- The example OPENS with the problem (provided separately in `problem`), then proceeds with ONE
  step per card, in order, until the final answer. The LAST card reaches and states the result.
- One step = ONE meaningful advancement. A step must NOT merely repeat the previous state, restate
  the problem, describe what happens later, combine several major decisions, skip unexplained work,
  or add commentary without advancing. Solve COMPLETELY to the terminal state — never stop early.
- NEVER gloss over a step. If a step relies on a sub-process (e.g. a recursive call), WALK THROUGH
  that sub-process step by step — show how it happens, not just its result. Every number and
  manipulation must be CORRECT, and the final answer must follow directly from the steps shown.

STEP FIELDS — each step card has four learner-facing fields: `goal`, `reasoning`, `work`, `result`.
- goal: the ONE immediate subproblem this step resolves — an action-oriented FRAGMENT, shorter than
  the rest ("Find the midpoint.", "Choose the next merged value.", "Eliminate one half."). Leave it
  EMPTY when the card title already says it; never pad it into a full sentence.
- reasoning: the SHORTEST sufficient justification — the one decisive fact/rule/comparison/invariant
  that makes the work valid ("27 < 43, so indices 0-3 cannot hold the target."). Leave it EMPTY when
  the work is self-evident. Teach the logic; do not narrate the action or re-explain the whole topic.
- work: REQUIRED. SHOW THE OPERATION THAT PRODUCES THE CHANGE — the actual comparison / calculation /
  swap / slice / append and WHY, not merely the resulting values. The work must demonstrate HOW the
  state transitions, with ACTUAL values, one idea per line. If symbols are awkward, use words.
  - Merge selection — GOOD: "compare 7 and 23 -> 7 < 23 -> append 7". BAD (just the outcome):
    "merged = [7] + [23] => [7, 23]".
  - Split — GOOD: "mid = len([34, 7, 23]) // 2 = 1", "left = arr[:1] = [34]", "right = arr[1:] = [7, 23]".
    BAD (just the outcome): "left_half = [34]", "right_half = [7, 23]".
  - Swap — GOOD: "7 < 32 -> swap arr[0] and arr[1] -> [7, 34, ...]". BAD: "arr = [7, 34, ...]".
  Never a vague placeholder ("apply the formula" / "continue the algorithm" / "update the state"),
  and never collapse a multi-element merge into one concatenation line — show each comparison.
  CORRECTNESS: every line must be arithmetically/logically exact — a merge result is exactly the two
  inputs interleaved (same multiset of elements); a concatenation A + B must literally equal its
  stated result. Do not write a result that the operation could not produce.
- result: REQUIRED. What is now TRUE after the work — the meaningful change / fact established /
  option eliminated — showing only the RELEVANT state, not every tracker. When useful, end by naming
  what the next step must resolve ("Remaining range: indices 4-6. Recompute the midpoint.").
- teaching_note: OPTIONAL, at most one — a single reusable insight as {"type": "key_idea" |
  "invariant" | "watch_for" | "check", "content": "<one concise line>"}. Omit unless it adds
  something reasoning/work/result do not; do NOT put one on every step.
- prior_state: OPTIONAL hidden metadata — the small machine-readable state this step starts from
  (e.g. {"low": 0, "high": 6, "target": 43}). Store ONLY the relevant part; empty is fine.
- cases_covered: the setup `required_cases` THIS step actually demonstrates (zero, one, or a few).

CONCISE STYLE (every field):
- Minimum SUFFICIENT explanation — remove redundancy, never remove necessary reasoning.
- Cut lead-ins: "We can see that", "We now need to", "At this point", "In order to", "This tells us".
- Prefer fragments + symbols/notation over prose: "27 < 43 -> search right", not "Because 27 is less
  than 43, we search the right half".
- State each fact ONCE — do not echo the same statement across goal, reasoning, work, and result.
- Plain language and math notation only — NO programming code (this path is for non-code topics).

VISUAL DESCRIPTION (the `visual` field on every card, and `problem_visual` for the setup)
- This is NOT a one-line summary. Write a RICH, EXPLICIT instruction of exactly what the
  picture for this step should contain — enough that an illustrator could draw the precise
  image from your words alone, with nothing left to guess.
- Describe, concretely:
  - STRUCTURE & LAYOUT: what kind of figure it is and how it is arranged — e.g. "a horizontal
    row of 7 boxes", "a binary tree with root 8 and these children …", "a 2-D table with rows
    R0-R2 and columns C0-C3", "the equation centered with terms aligned".
  - CONTENTS: the CONCRETE values / labels in every element (the actual numbers, names,
    symbols), not placeholders.
  - CURRENT STATE: what is active / highlighted / selected this step — which box, node, cell,
    pointer, range, or term, and the color or emphasis it carries.
  - WHAT CHANGED vs. the previous step: which element moved, was added, recomputed, crossed
    out, or re-colored — so the picture reads as a transition, not a static snapshot.
- `problem_visual` describes the INITIAL figure for the setup card (the starting structure and
  values, nothing highlighted yet)."""
)

_SYSTEM = (
    "You are a precise, rigorous tutor authoring ONE worked example for a learning platform. "
    "Pose ONE concrete, comprehensive, fully-specified problem for the given topic, then "
    "SOLVE IT COMPLETELY from start to finish. The text breakdown must be perfect — complete, "
    "coherent, and correct — because it is the foundation of the lesson. Follow these rules "
    "EXACTLY:\n\n"
    f"{_WORKED_EXAMPLE_RULES}\n\n"
    "Return ONLY a JSON object of exactly this shape:\n"
    '{"problem": "<the COMPLETE problem like a TEST QUESTION — write the ACTUAL concrete input '
    "values you INVENTED for this lesson (a real list of numbers, not the word \\\"array\\\"); "
    "choose fresh, randomized values and never reuse any numbers shown in these instructions. "
    "Give the task and the expected answer FORMAT. Do NOT reveal the final answer here>\", "
    '"expected_final_answer": "<the actual final answer (kept in metadata, never shown in the problem)>", '
    '"required_cases": ["<a key decision/case the walkthrough MUST exercise>", ...], '
    '"expected_steps": <your integer estimate of the MINIMUM steps a COMPLETE walkthrough needs>, '
    '"problem_visual": "<rich description of the INITIAL figure for the setup>", '
    '"cards": [{"title": "<short action-oriented step name>", '
    '"goal": "<the immediate subproblem, a fragment — or empty if the title says it>", '
    '"reasoning": "<one decisive reason the work is valid — or empty if self-evident>", '
    '"work": ["<concrete operation line with actual values>", ...], '
    '"result": "<what is now true after the work — only the relevant state>", '
    '"teaching_note": {"type": "key_idea|invariant|watch_for|check", "content": "<one line>"}, '
    '"cases_covered": ["<which required_cases labels THIS step exercises>", ...], '
    '"prior_state": {"<small machine-readable state this step starts from>": "..."}, '
    '"visual": "<rich description of what THIS step\'s figure shows>"}, ...]}\n'
    "Each card MUST include non-empty `work` (a list of concrete lines) and `result`; `goal`, "
    "`reasoning`, `teaching_note`, and `prior_state` are OPTIONAL (omit or leave empty when they "
    "would only repeat). By the last card every required_case must be covered, and the last "
    "card's `result` MUST reach the expected_final_answer."
)


def _existing_problem_text(cards: list[Any]) -> str:
    """The problem the lesson already frames the example around (kept on-topic), if any."""
    for card in cards or []:
        if not isinstance(card, dict):
            continue
        if str(card.get("blueprint_key") or card.get("card_type") or "").lower() != "worked_example":
            continue
        parts = [str(card.get("title") or "")]
        parts += [str(p) for p in (card.get("points") or [])][:3]
        text = " ".join(p for p in parts if p).strip()
        if text:
            return text[:600]
    return ""


# --- Coding-implementation structural blueprint (see CODING_WORKED_EXAMPLE_SPEC.md) ---
# A coding worked example is divided into the SAME natural structural steps a learner writes by hand
# (per pass / split / recursive call / base case / merge selection / tail copy), and each card
# explains HOW THE CODE performs that step — NOT a runtime line-execution trace (which exploded to
# ~80 cards). The outline plans those structural steps; a hard gate bounds them before the expensive
# cards call. Data tables, gate, and solve path are defined further below (after `_norm`).

_CODING_KIND_GUIDE = """STRUCTURAL STEP KINDS — every plan action declares ONE `kind`:
- pass            : one loop iteration with ONE central decision/update (binary search: mid + compare + adjust).
- split           : one divide (compute mid, slice into two halves).
- recursive_call  : one recursive call that does MEANINGFUL work after entering (it splits/recurses further).
- base_case       : a call that immediately hits the terminating condition and returns — the call AND its return in ONE action.
- merge_selection : one selection phase of a merge (compare fronts, choose, append, advance the pointer).
- merge_tail      : copy a remaining already-sorted tail after one side empties.
- visit           : one traversal visit / dequeue / enqueue cycle.
- return_resume   : a return that ENABLES a new structural action in the parent (only when it unlocks the next move).
- other           : anything not above (rare; include a short `reason`).
A SMALL merge (1-2 comparisons) may be ONE card; a larger merge splits into one card per merge_selection
plus a merge_tail. NEVER one card per assignment / per line-execution, and NEVER collapse a whole
sub-algorithm ('sort the left half') into one card."""

_CODING_OUTLINE_SHAPE = (
    "Return ONLY JSON of this shape:\n"
    '{"problem": "<the concrete input the code runs on — ACTUAL values; do NOT reveal the result>", '
    '"expected_final_answer": "<the value the code returns (kept hidden)>", '
    '"problem_visual": "<rich description of the initial data state>", '
    '"required_cases": ["<case>", ...], '
    '"solution_plan": [{"kind": "<one structural kind>", '
    '"description": "<the ONE structural transition, with concrete values>", '
    '"cases_covered": ["<required_case this action demonstrates>", ...], '
    '"reason": "<ONLY for kind=other: why no other kind fits>"}, ...]}'
)

_CODING_OUTLINE_SYSTEM = (
    "You are PLANNING one CODE-ANCHORED worked example. Divide the example into the SAME natural "
    "structural steps a learner writes BY HAND — one action per pass / split / recursive call / base "
    "case / merge selection / tail copy — NOT one action per code line, and NOT a runtime "
    "line-execution trace. Each action becomes exactly one card later.\n\n"
    f"{_CODING_KIND_GUIDE}\n\n"
    "RULES:\n"
    "- Use a SMALL teaching input: merge sort prefer 4 elements; binary search use enough elements that "
    "the target takes at least 3 passes. Comprehensible, not exhaustive.\n"
    "- Do NOT emit line-level kinds (assignment / condition_check / line_execution).\n"
    "- A single-element recursive call folds its call + base-case return into ONE base_case action; give "
    "a recursive_call its own action only when it does more work after entering.\n"
    "- Map each action's cases_covered to the required_cases you are given; cover them ALL.\n"
    "- Stay within the step budget you are given (its maximum is a CEILING, not a target).\n\n"
    + _CODING_OUTLINE_SHAPE
)

_CODING_CARDS_SHAPE = (
    "Return ONLY a JSON object of this shape:\n"
    '{"problem": "<the concrete input>", "expected_final_answer": "<the returned value>", '
    '"cards": [{"title": "<short step name>", '
    '"goal": "<the structural step, phrased like a normal example — or empty if the title says it>", '
    '"reasoning": "<WHICH code construct implements it and why>", '
    '"work": ["<a code line/trace that runs for THIS step, with actual values>", ...], '
    '"result": "<concrete RUNTIME state after: variables, pointers, frame, branch, return value>", '
    '"code_lines": [[<1-based source line(s) for each work action>], ...], '
    '"cases_covered": ["<required_case this card demonstrates>", ...], '
    '"prior_state": {"<small state before>": "..."}, '
    '"visual": "<what the data looks like now>"}, ...]}'
)

_CODING_CARDS_SYSTEM = (
    "You are authoring a CODE-ANCHORED worked example from an APPROVED structural plan. Produce EXACTLY "
    "ONE Goal/Reasoning/Work/Result card per plan action, in order — do NOT add, remove, merge, split, "
    "or reorder. Each card explains HOW THE CODE performs that structural step, not what happens "
    "conceptually.\n\n"
    "STEP FIELDS:\n"
    "- goal: the structural step ('First pass: examine the middle', 'Merge the two sorted halves'); "
    "empty if the title already says it.\n"
    "- reasoning: WHICH code construct implements it and why (the condition / loop / slice / call / return).\n"
    "- work: REQUIRED list — the code lines that run FOR THIS STEP with their evaluation and ACTUAL "
    "values (code/trace, NOT prose). Several lines are fine; they belong to this ONE transition.\n"
    "- result: REQUIRED — the concrete RUNTIME state after this step (variables, pointers, call stack / "
    "current frame, branch taken, returned value, mutated structure). NOT a vague 'continue searching'.\n"
    "- code_lines: for EACH `work` action, the 1-based line number(s) in the shown code it maps to, as a "
    "list of lists (e.g. [[3],[4],[4],[5]]); use [] for a pure-trace line. Best-effort; one entry per work line.\n"
    "- cases_covered: the required_cases THIS card demonstrates.\n\n"
    "Every card's `work` must contain BOTH a code mechanic (an expression / call / branch / update / "
    "return) AND a concrete runtime value. Never cite a line number in prose — show the code TEXT.\n\n"
    + _CODING_CARDS_SHAPE
)


# How many times the PROBLEM may be regenerated when its cheap outline fails the gate (≥4 full
# steps / coverage). Bounded; the outline is cheap so this rarely costs much.
_MAX_OUTLINE_RETRIES = max(0, int(os.getenv("AZALEA_EXAMPLE_MAX_OUTLINE_RETRIES", "1")))


def _norm(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()

_OUTLINE_RULES = (
    EXAMPLE_PROBLEM_RULES
    + """

OUTLINE THE SOLUTION ACTION BY ACTION (a cheap plan we validate BEFORE writing any cards):
- Identify required_cases: the minimum important behaviors / branches / boundaries / edge cases the
  learner must see to apply the concept correctly. Keep it small; no large case hierarchy.
- Choose ONE realistic, exam-level problem whose NATURAL solution runs through AT LEAST 4 FULL STEPS
  (complete iterations/cycles of the method — e.g. binary search: one full step = compute mid +
  compare + adjust the bounds), exercises every required_case, and reaches a non-obvious answer.
- List the solution ACTION BY ACTION, in order. Each action is ONE atomic move that becomes ONE card
  later ("compute mid", "compare target to arr[mid]", "move low to mid+1"). Tag each action with the
  full_step (iteration/cycle) it belongs to, and the required_cases it demonstrates (often none).
- The plan MUST span ≥4 distinct full_step values, cover every required_case across its actions, and
  contain NO padded, empty, or filler actions (and no single-action step faking a full cycle)."""
    + _ATOMIC_RULES
)


_PLACEHOLDER_PHRASES = (
    "sort the left", "sort the right", "sort both", "sort each", "sort the half", "sort the sub",
    "recursively sort", "recurse on", "recurse left", "recurse right", "recurse into",
    "merge the result", "merge both", "merge the halves", "process the subtree", "process the sub",
    "solve the smaller", "continue the algorithm", "continue the recursion", "do the recursion",
)
_PRIMARY_VERBS = (
    "compute", "compare", "split", "recurse", "merge", "return", "append", "update", "swap",
    "partition", "insert", "pop", "push", "visit", "traverse", "divide", "combine",
)


def _split_action(action: str) -> list[str]:
    """Split a bundled action into its sub-operations on strong list delimiters (`;`, `then`, top-
    level commas — never inside brackets so values like [5, 2, 8] stay intact)."""
    text = re.sub(r"\bthen\b", ";", str(action or ""))
    out, buf, depth = [], [], 0
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if ch in ";," and depth == 0:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return [p.strip(" .-").strip() for p in out if p.strip(" .-").strip()]


def _is_coarse_action(action: str) -> tuple[bool, str]:
    """True (with a reason) when an outline action is too COARSE — a high-level placeholder or a
    bundle of multiple independently-reasoned operations. Lenient: a two-verb atomic move like
    'compare the fronts and append the smaller' is allowed (one cause-and-effect transition)."""
    a = _norm(action)
    if not a:
        return True, "empty action"
    for p in _PLACEHOLDER_PHRASES:
        if p in a:
            return True, f"high-level placeholder ('{p.strip()}')"
    parts = _split_action(action)
    if len(parts) >= 3:
        return True, f"bundles {len(parts)} operations in one step"
    verbs = {v for v in _PRIMARY_VERBS if re.search(rf"\b{v}", a)}
    if len(verbs) >= 3:
        return True, "multiple primary operations (" + ", ".join(sorted(verbs)) + ")"
    return False, ""


def _expand_coarse_actions(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic fallback: a coarse action that lists its sub-operations is split into one
    outline entry per sub-operation (keeping its full_step / cases). Better than shipping a bundled
    card; a contentless placeholder with no delimiters is left as-is (the prompt should prevent it)."""
    out: list[dict[str, Any]] = []
    for a in plan:
        action = str(a.get("action") or "")
        coarse, _ = _is_coarse_action(action)
        subs = _split_action(action) if coarse else []
        if coarse and len(subs) >= 2:
            out.extend({**a, "action": s} for s in subs)
        else:
            out.append(a)
    return out

_OUTLINE_SHAPE = (
    "Return ONLY JSON of this shape:\n"
    '{"problem": "<the COMPLETE problem like a TEST QUESTION — actual invented input values, fresh '
    "and never reused from these instructions; do NOT reveal the answer>\", "
    '"expected_final_answer": "<the answer, kept hidden>", '
    '"problem_visual": "<rich description of the INITIAL figure>", '
    '"required_cases": ["<case>", ...], '
    '"solution_plan": [{"full_step": <int>, "action": "<one atomic action>", '
    '"cases_covered": ["<required_case this action demonstrates>", ...]}, ...]}\n'
    "The solution_plan MUST span ≥4 distinct full_step values and cover every required_case."
)

_OUTLINE_SYSTEM = (
    "You are PLANNING one worked example. Produce the problem and a cheap ACTION-BY-ACTION outline "
    "that we validate before writing any cards. Follow EXACTLY:\n\n"
    f"{_OUTLINE_RULES}\n\n" + _OUTLINE_SHAPE
)

def _gate_outline(outline: dict[str, Any]) -> tuple[bool, str]:
    """Cheap gate on the action outline: ≥4 full steps, every required_case covered, concrete
    actions only. Returns (ok, feedback-for-regenerating-the-problem)."""
    plan = [a for a in (outline.get("solution_plan") or []) if isinstance(a, dict)]
    actions = [a for a in plan if str(a.get("action") or "").strip()]
    full_steps = {a.get("full_step") for a in actions if a.get("full_step") is not None}
    required = [str(c).strip() for c in (outline.get("required_cases") or []) if str(c).strip()]
    covered = {_norm(c) for a in actions for c in (a.get("cases_covered") or []) if str(c).strip()}
    missing = [c for c in required if not any(_norm(c) in cc or cc in _norm(c) for cc in covered if cc)]

    coarse = []
    for i, a in enumerate(actions, start=1):
        is_coarse, reason = _is_coarse_action(str(a.get("action") or ""))
        if is_coarse:
            coarse.append(f"step {i} ({a.get('action')}) — {reason}")

    problems: list[str] = []
    if len(full_steps) < 4:
        problems.append(f"the plan spans only {len(full_steps)} full step(s) — choose a problem whose "
                        "natural solution needs at least 4 full steps (complete iterations/cycles).")
    if len(actions) < len(plan) or len(actions) < 4:
        problems.append("every plan entry must be one concrete atomic action — remove empty/filler entries.")
    if coarse:
        problems.append("these steps are too COARSE — each must be ONE primary operation; expand them "
                        "(including any recursion: input, descent, base case, return, resumed parent) into "
                        "separate atomic steps: " + "; ".join(coarse) + ".")
    if missing:
        problems.append("these required cases are not demonstrated by any action: " + ", ".join(missing) + ".")
    if problems:
        return False, "Revise the PROBLEM and outline so that: " + " ".join(problems)
    return True, ""


# ----------------------------------------------------------------------------------------------
# Coding-implementation structural path (CODING_WORKED_EXAMPLE_SPEC.md v1)
# ----------------------------------------------------------------------------------------------

# v1 flat teaching ranges (input-size-aware ranges are v1.1). `max` is a CEILING, not a target.
CODING_STEP_RANGES: dict[str, tuple[int, int]] = {
    "binary_search": (3, 6),
    "merge_sort": (8, 18),
    "dfs": (5, 12),
    "bfs": (5, 12),
    "linked_list_operation": (4, 10),
    "dynamic_programming": (8, 20),
    "default": (5, 25),
}

# Structural step kinds the outline may use; line-level kinds are a HARD reject.
_CODING_STEP_KINDS = {
    "pass", "split", "recursive_call", "base_case", "merge_selection",
    "merge_tail", "visit", "return_resume", "other",
}
_LINE_LEVEL_KINDS = {"assignment", "condition_check", "line_execution"}

# Required cases keyed by topic slug — supplied deterministically; the model only maps actions to them.
REQUIRED_CASES_BY_TOPIC: dict[str, list[str]] = {
    "binary_search": ["midpoint_calculation", "lower_bound_update", "upper_bound_update", "found_return"],
    "merge_sort": ["split_with_slicing", "immediate_base_case_return",
                   "parent_receives_recursive_result", "merge_selection", "tail_copy"],
    "bfs": ["queue_dequeue", "visited_mark", "neighbor_iteration", "enqueue_unvisited"],
    "dfs": ["stack_or_recursive_visit", "visited_mark", "neighbor_order", "backtrack_or_stack_update"],
}

# Title-keyword fallbacks for resolving a topic to a known slug (slug field -> keyword match -> default).
_CODING_TOPIC_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("binary_search", ("binary search", "binary_search")),
    ("merge_sort", ("merge sort", "merge_sort", "mergesort")),
    ("dfs", ("depth first", "depth-first", "dfs")),
    ("bfs", ("breadth first", "breadth-first", "bfs")),
    ("linked_list_operation", ("linked list", "linked_list")),
    ("dynamic_programming", ("dynamic programming", "dynamic_programming")),
)


def _coding_topic_slug(topic: dict[str, Any]) -> str:
    """Resolve a coding topic to a known slug: explicit slug field, then title-keyword match, then
    'default' — so merge sort never silently falls into the generic range."""
    explicit = _norm(topic.get("slug") or topic.get("topic_slug") or topic.get("algorithm") or "").replace(" ", "_")
    if explicit in CODING_STEP_RANGES or explicit in REQUIRED_CASES_BY_TOPIC:
        return explicit
    hay = _norm(f"{topic.get('title') or ''} {topic.get('concept') or topic.get('main_concept') or ''}")
    for slug, kws in _CODING_TOPIC_KEYWORDS:
        if any(_norm(k) in hay for k in kws):
            return slug
    return "default"


def _coding_step_range(slug: str) -> tuple[int, int]:
    return CODING_STEP_RANGES.get(slug, CODING_STEP_RANGES["default"])


def _gate_coding_outline(
    outline: dict[str, Any], *, step_range: tuple[int, int], required: list[str],
) -> tuple[bool, str, str]:
    """HARD gate on the structural coding outline, BEFORE the expensive cards call. Rejects on:
    too FEW steps (min), line-level kinds, `other` over cap, and missing required-case coverage.
    There is intentionally NO upper bound — the structural plan must run the FULL trace to the final
    result and is never trimmed for length (a trimmed plan ships an incomplete worked example).
    Returns (ok, feedback, fail_reason)."""
    plan = [a for a in (outline.get("solution_plan") or []) if isinstance(a, dict)]
    actions = [a for a in plan if str(a.get("description") or a.get("action") or "").strip()]
    lo, _ = step_range
    problems: list[str] = []
    reason = ""

    if not actions:
        return False, "Produce a structural action plan (one action per pass/split/call/base case/merge).", "empty_plan"

    n = len(actions)
    if n < lo:
        problems.append(f"the plan has only {n} actions — at least {lo} are needed. Show each structural "
                        "step (split / recursive call / base case / merge selection / tail copy).")
        reason = reason or "outline_under_min"

    bad_kinds = sorted({_norm(a.get("kind")).replace(" ", "_") for a in actions
                        if _norm(a.get("kind")).replace(" ", "_") in _LINE_LEVEL_KINDS})
    if bad_kinds:
        problems.append("these actions use line-level kinds (" + ", ".join(bad_kinds) + ") — describe the "
                        "STRUCTURAL transition (pass / split / recursive_call / base_case / merge_selection).")
        reason = reason or "line_level_kind"

    other_count = sum(1 for a in actions if _norm(a.get("kind")).replace(" ", "_") == "other")
    if other_count > max(1, int(0.2 * n)):
        problems.append(f"{other_count} actions are kind=other — assign a specific structural kind; "
                        "`other` is capped.")
        reason = reason or "other_over_cap"

    covered = {_norm(c) for a in actions for c in (a.get("cases_covered") or []) if str(c).strip()}
    missing = [c for c in required if not any(_norm(c) in cc or cc in _norm(c) for cc in covered if cc)]
    if missing:
        problems.append("these required cases are not demonstrated by any action: " + ", ".join(missing) + ".")
        reason = reason or "missing_required_cases"

    if problems:
        return False, "Revise the outline so that: " + " ".join(problems), reason
    return True, "", ""


def _build_coding_outline_user_prompt(
    topic: dict[str, Any], existing_problem: str, code: Optional[str], *,
    required: list[str], step_range: tuple[int, int], feedback: str = "",
) -> str:
    lo, _ = step_range
    parts = [f"Topic: {topic.get('title') or ''}"]
    concept = topic.get("concept") or topic.get("learning_goal") or topic.get("main_concept")
    if concept:
        parts.append(f"Concept: {concept}")
    if existing_problem:
        parts.append(f"The lesson frames the example as: {existing_problem}")
    parts.append("Here is the code (shown to the learner in an IDE panel):\n\n" + str(code or ""))
    if required:
        parts.append("required_cases — use EXACTLY these and map each action's cases_covered to them:\n- "
                     + "\n- ".join(required))
    parts.append(f"Produce AT LEAST {lo} structural actions, and AS MANY AS THE COMPLETE TRACE NEEDS "
                 "— every split, recursive call, base case, merge selection, and tail copy, all the way "
                 "to the final returned result. NEVER stop the trace early or omit steps to save space; "
                 "there is no upper limit.")
    if feedback:
        parts.append(feedback)
    return "\n".join(parts)


def _build_coding_cards_user_prompt(outline: dict[str, Any], code: Optional[str]) -> str:
    plan = [a for a in (outline.get("solution_plan") or []) if isinstance(a, dict)]
    lines = "\n".join(
        f"{i + 1}. [{a.get('kind') or 'other'}] {a.get('description') or a.get('action')}"
        + (f"   [demonstrates: {', '.join(str(c) for c in a.get('cases_covered') or [])}]"
           if a.get("cases_covered") else "")
        for i, a in enumerate(plan)
    )
    return "\n\n".join([
        "Problem — use EXACTLY this, do not change it:\n" + str(outline.get("problem") or ""),
        "Expected final answer (reach this; keep it OUT of the problem text): "
        + str(outline.get("expected_final_answer") or ""),
        "Approved structural plan. Produce EXACTLY ONE code-anchored Goal/Reasoning/Work/Result card "
        "per action below, in order — do NOT add, remove, merge, split, or reorder:\n" + lines,
        "The code below is shown in the IDE panel. Anchor each `work` action to its 1-based line "
        "number(s) via `code_lines`, and explain how the code EXECUTES (never cite a line number in "
        "prose):\n\n" + str(code or ""),
    ])


def _solve_coding_worked_example(
    topic: dict[str, Any], fn: "SolveFn", *, existing_problem: str, code: str, feedback: str = "",
) -> Optional[dict[str, Any]]:
    """Structural coding solve: plan structural steps -> HARD gate (range / kinds / coverage / other)
    -> one code-anchored card per accepted action. On gate failure (within retries) or a cards error,
    return a {coding_fallback_used, reason} marker so the caller keeps the base example and records
    WHY. The old line-execution trace is NOT a fallback."""
    slug = _coding_topic_slug(topic)
    step_range = _coding_step_range(slug)
    required = list(REQUIRED_CASES_BY_TOPIC.get(slug, []))

    def run_outline(fb: str) -> Optional[dict[str, Any]]:
        try:
            raw = fn({
                "user": _build_coding_outline_user_prompt(
                    topic, existing_problem, code, required=required, step_range=step_range, feedback=fb),
                "system": _CODING_OUTLINE_SYSTEM, "topic": topic, "code": code, "phase": "outline",
            })
        except Exception as exc:  # noqa: BLE001
            _log.warning("coding worked-example outline: solver raised: %s", exc)
            return None
        return raw if isinstance(raw, dict) else None

    outline = run_outline(feedback)
    if not outline:
        return None
    if required:  # validate coverage against the canonical cases, not the model's invented ones
        outline["required_cases"] = required
    ok, gate_feedback, fail_reason = _gate_coding_outline(outline, step_range=step_range, required=required)
    for _ in range(_MAX_OUTLINE_RETRIES):
        if ok:
            break
        retry = run_outline(gate_feedback)
        if not retry:
            break
        outline = retry
        if required:
            outline["required_cases"] = required
        ok, gate_feedback, fail_reason = _gate_coding_outline(outline, step_range=step_range, required=required)
    if not ok:
        # lean OMITS the worked example, so abandoning here means NO worked example renders at all.
        # Ship a BEST-EFFORT worked example rather than nothing: an empty plan is the only hard
        # abandon; any other gate failure (too few steps, a missing required case) ships AS-IS and is
        # NEVER trimmed — a complete trace, even if imperfect, beats a cut-short or blank one.
        if fail_reason == "empty_plan":
            return {"coding_fallback_used": True, "reason": "empty_plan"}
        _log.info("coding worked-example: shipping best-effort outline despite gate (reason=%s) for %s",
                  fail_reason, topic.get("id"))

    plan = [a for a in (outline.get("solution_plan") or [])
            if isinstance(a, dict) and str(a.get("description") or a.get("action") or "").strip()]
    if not plan:
        return {"coding_fallback_used": True, "reason": "empty_plan"}
    outline["solution_plan"] = plan

    try:
        cards_raw = fn({
            "user": _build_coding_cards_user_prompt(outline, code),
            "system": _CODING_CARDS_SYSTEM, "topic": topic, "code": code, "phase": "cards",
        })
    except Exception as exc:  # noqa: BLE001
        _log.warning("coding worked-example cards: solver raised: %s", exc)
        return {"coding_fallback_used": True, "reason": "cards_call_error"}
    cards = _normalize_solution_cards(cards_raw) if isinstance(cards_raw, dict) else []
    if not cards:
        return {"coding_fallback_used": True, "reason": "cards_call_error"}

    final = str(outline.get("expected_final_answer") or "").strip()
    return {
        "problem": str(outline.get("problem") or "").strip(),
        "problem_visual": str(outline.get("problem_visual") or "").strip(),
        "expected_final_answer": final,
        "required_cases": [str(c).strip() for c in (outline.get("required_cases") or []) if str(c).strip()],
        "expected_steps": len(cards),
        "full_steps": len(cards),
        "cards": cards,
        "final_answer": final,
        "coding_slug": slug,
    }


def _build_cards_user_prompt(outline: dict[str, Any], code: Optional[str]) -> str:
    """The expensive cards call: expand the APPROVED plan into one card per action."""
    plan = [a for a in (outline.get("solution_plan") or []) if isinstance(a, dict)]
    lines = "\n".join(
        f"{i + 1}. (full_step {a.get('full_step')}) {a.get('action')}"
        + (f"   [demonstrates: {', '.join(str(c) for c in a.get('cases_covered') or [])}]"
           if a.get("cases_covered") else "")
        for i, a in enumerate(plan)
    )
    parts = [
        "Problem — use EXACTLY this, do not change it:\n" + str(outline.get("problem") or ""),
        "Expected final answer (reach this; keep it OUT of the problem text): "
        + str(outline.get("expected_final_answer") or ""),
        "Approved action-by-action plan. Produce EXACTLY ONE Goal/Reasoning/Work/Result card per "
        "action below, in this order — do NOT add, remove, merge, split, or reorder actions:\n" + lines,
    ]
    if code:
        parts.append("The code is shown in an IDE panel; explain how it EXECUTES (never by line "
                     "number):\n\n" + code)
    return "\n\n".join(parts)


def _solve_outline(
    topic: dict[str, Any], fn: "SolveFn", *, existing_problem: str, code: Optional[str], feedback: str = "",
) -> Optional[dict[str, Any]]:
    payload = {
        "user": _build_user_prompt(topic, existing_problem, code, feedback),
        "system": _CODING_OUTLINE_SYSTEM if code else _OUTLINE_SYSTEM,
        "topic": topic, "code": code, "phase": "outline",
    }
    try:
        raw = fn(payload)
    except Exception as exc:  # noqa: BLE001
        _log.warning("worked-example outline: solver raised: %s", exc)
        return None
    return raw if isinstance(raw, dict) else None


def _build_user_prompt(
    topic: dict[str, Any], existing_problem: str, code: Optional[str] = None, feedback: str = "",
) -> str:
    parts = [f"Topic: {topic.get('title') or ''}"]
    concept = topic.get("concept") or topic.get("learning_goal") or topic.get("main_concept")
    if concept:
        parts.append(f"Concept: {concept}")
    if existing_problem:
        parts.append(f"The lesson frames the example as: {existing_problem}")
    if code:
        parts.append("Here is the code (shown to the learner in an IDE panel). Explain how it "
                     "executes on a concrete input — conceptually, never by line number:\n\n" + code)
        parts.append("Walk its execution fully, step by step, to the returned result.")
    else:
        parts.append("Pose a concrete instance of this and solve it fully, step by step.")
    if feedback:
        parts.append(feedback)
    return "\n".join(parts)


def _default_solver(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """The real LLM call. Skips immediately when no usable API key is configured, so the
    test suite / offline enrichment never makes a network call or stalls on retries."""
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip().lower() == "dummy":
        return None
    try:
        from app.services.llm_client import OPENAI_MODEL, client

        # Per-call timeout caps a hung call (so a slow connection can't stall the serial study-path
        # build), but KEEP retries so a transient rate-limit / 5xx recovers instead of silently
        # dropping the worked example. Bounded: <= 3 attempts x timeout. Tune via the env vars.
        response = client.with_options(
            timeout=_ENRICH_TIMEOUT, max_retries=_ENRICH_MAX_RETRIES,
        ).responses.create(
            model=OPENAI_MODEL,
            input=[
                {"role": "system", "content": str(payload.get("system") or _SYSTEM)},
                {"role": "user", "content": str(payload.get("user") or "")},
            ],
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text)
    except Exception as exc:  # noqa: BLE001 — a failed solve is non-fatal; lesson is unchanged
        _log.warning("worked-example solver: LLM call failed: %s", exc)
        return None


def solve_worked_example(
    topic: dict[str, Any],
    *,
    existing_problem: str = "",
    code: Optional[str] = None,
    feedback: str = "",
    solver: Optional[SolveFn] = None,
) -> Optional[dict[str, Any]]:
    """Two-phase solve. (1) A CHEAP action-by-action outline is produced and GATED; on failure the
    PROBLEM is regenerated before we pay for cards. (2) The approved plan is expanded into one
    Goal/Reasoning/Work/Result card per action. Returns a normalized {problem, cards, final_answer,
    ...}, a {coding_fallback_used, reason} marker (coding only), or None. `feedback` is an upstream
    backstop hint (rarely used now that the outline is gated).

    Coding-implementation topics take the STRUCTURAL path (CODING_WORKED_EXAMPLE_SPEC): structural-step
    outline + hard gate + code-anchored cards — NOT the runtime line-execution trace."""
    fn = solver or _default_solver

    if code:
        return _solve_coding_worked_example(
            topic, fn, existing_problem=existing_problem, code=code, feedback=feedback)

    outline = _solve_outline(topic, fn, existing_problem=existing_problem, code=code, feedback=feedback)
    if not outline:
        return None
    for _ in range(_MAX_OUTLINE_RETRIES):
        ok, gate_feedback = _gate_outline(outline)
        if ok:
            break
        retry = _solve_outline(topic, fn, existing_problem=existing_problem, code=code, feedback=gate_feedback)
        if not retry:
            break
        outline = retry

    plan = [a for a in (outline.get("solution_plan") or [])
            if isinstance(a, dict) and str(a.get("action") or "").strip()]
    if not plan:
        return None
    # Deterministic fallback: any action still coarse after the outline retries and that LISTS its
    # sub-operations is split into atomic entries before we pay for cards (a bundled card is worse).
    plan = _expand_coarse_actions(plan)
    outline["solution_plan"] = plan

    cards_raw = None
    try:
        cards_raw = fn({
            "user": _build_cards_user_prompt(outline, code),
            "system": _SYSTEM,
            "topic": topic, "code": code, "phase": "cards",
        })
    except Exception as exc:  # noqa: BLE001
        _log.warning("worked-example cards: solver raised: %s", exc)
        return None
    if not isinstance(cards_raw, dict):
        return None
    cards = _normalize_solution_cards(cards_raw)
    if not cards:
        return None

    final = str(outline.get("expected_final_answer") or "").strip()
    full_steps = len({a.get("full_step") for a in plan if a.get("full_step") is not None})
    return {
        "problem": str(outline.get("problem") or "").strip(),
        "problem_visual": str(outline.get("problem_visual") or "").strip(),
        "expected_final_answer": final,
        "required_cases": [str(c).strip() for c in (outline.get("required_cases") or []) if str(c).strip()],
        "expected_steps": len(plan),
        "full_steps": full_steps,
        "cards": cards,
        "final_answer": final,  # backward-compat alias
    }


def _coerce_points(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(p).rstrip() for p in value if str(p).strip()]


def _coerce_lines(value: Any) -> list[str]:
    """A field that should be a list of short lines — accept a single string too."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(p).rstrip() for p in value if str(p).strip()]


_NOTE_TYPES = {"key_idea", "invariant", "watch_for", "check"}


def _coerce_teaching_note(value: Any) -> Optional[dict[str, str]]:
    if not isinstance(value, dict):
        return None
    content = str(value.get("content") or "").strip()
    if not content:
        return None
    ntype = str(value.get("type") or "key_idea").strip().lower()
    if ntype not in _NOTE_TYPES:
        ntype = "key_idea"
    return {"type": ntype, "content": content}


def _coerce_prior_state(value: Any) -> Any:
    if isinstance(value, dict):
        return value or None
    if isinstance(value, str):
        return value.strip() or None
    return None


def _coerce_code_lines(value: Any) -> Optional[list[list[int]]]:
    """Best-effort per-action code anchor (CODING_WORKED_EXAMPLE_SPEC §5/§9): one entry per `work`
    action, each a list of 1-based source-line numbers ([] when none). Accepts a list of ints (each
    wrapped) or a list of int-lists; anything malformed is dropped (anchors never block rendering)."""
    if not isinstance(value, list):
        return None
    out: list[list[int]] = []
    for entry in value:
        if isinstance(entry, bool):
            out.append([])
        elif isinstance(entry, int):
            out.append([entry])
        elif isinstance(entry, list):
            nums = [int(x) for x in entry if isinstance(x, int) and not isinstance(x, bool)]
            out.append(nums)
        else:
            out.append([])
    return out


def _normalize_solution_cards(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize each step to the Goal/Reasoning/Work/Result contract:
    {title, goal, reasoning, work(list), result, teaching_note, cases_covered, prior_state, visual}.
    Accepts the new shape, the legacy decision/action/resulting_state shape (mapped onto the new
    fields), and free-form `points`/`steps` as a last resort. `work` + `result` are required."""
    out: list[dict[str, Any]] = []
    for card in raw.get("cards") if isinstance(raw.get("cards"), list) else []:
        if not isinstance(card, dict):
            continue
        title = str(card.get("title") or "").strip()
        visual = str(card.get("visual") or "").strip()
        cases = [str(c).strip() for c in (card.get("cases_covered") or []) if str(c).strip()]
        prior_state = _coerce_prior_state(card.get("prior_state"))
        goal = str(card.get("goal") or "").strip()
        reasoning = str(card.get("reasoning") or "").strip()
        work = _coerce_lines(card.get("work"))
        result = str(card.get("result") or "").strip()

        if not (work and result):
            # Legacy shape: decision/action/resulting_state -> reasoning/work/result.
            action = _coerce_lines(card.get("action"))
            resulting = str(card.get("resulting_state") or "").strip()
            if action and resulting:
                work = work or action
                result = result or resulting
                reasoning = reasoning or str(card.get("decision") or "").strip()

        if work and result:
            out.append({
                "title": title, "goal": goal, "reasoning": reasoning, "work": work,
                "result": result, "teaching_note": _coerce_teaching_note(card.get("teaching_note")),
                "cases_covered": cases, "prior_state": prior_state, "visual": visual,
                "code_lines": _coerce_code_lines(card.get("code_lines")),
            })
            continue
        # Last resort: free-form points -> work lines, last as the result.
        pts = _coerce_points(card.get("points"))
        if pts:
            out.append({
                "title": title, "goal": "", "reasoning": "", "work": pts, "result": pts[-1],
                "teaching_note": None, "cases_covered": cases, "prior_state": prior_state, "visual": visual,
            })

    if out:
        return out
    for step in raw.get("steps") if isinstance(raw.get("steps"), list) else []:
        if not isinstance(step, dict):
            continue
        pts = _coerce_points(step.get("detail") if step.get("detail") is not None else step.get("points"))
        if pts:
            out.append({
                "title": str(step.get("title") or "").strip(), "goal": "", "reasoning": "",
                "work": pts, "result": pts[-1], "teaching_note": None, "cases_covered": [],
                "prior_state": None, "visual": str(step.get("visual") or "").strip(),
            })
    return out


def _step_points(
    goal: str, reasoning: str, work: list[str], result: str, note: Optional[dict[str, str]],
) -> list[str]:
    """A bullet-list view of a step, for any consumer that still reads `points` (streaming
    preview, generic renderers, the completeness audit). The structured Goal/Reasoning/Work/
    Result fields on the card are authoritative; the new renderer reads those directly."""
    pts: list[str] = []
    if goal:
        pts.append(f"Goal: {goal}")
    if reasoning:
        pts.append(f"Reasoning: {reasoning}")
    if work:
        pts.append("Work:")
        pts += [f"  - {w}" for w in work]
    if result:
        pts.append(f"Result: {result}")
    if note:
        pts.append(f"{note['type'].replace('_', ' ').title()}: {note['content']}")
    return pts


def _build_solution_cards(
    sol: dict[str, Any], topic: dict[str, Any], *, code: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Structured solution -> worked-example cards: a setup card stating the problem, then one
    card per step carrying the Goal/Reasoning/Work/Result fields, the last stamped with the final
    answer. When `code` is given, every card carries it as `code_snippet` so the frontend shows it
    in an IDE panel alongside the conceptual explanation."""
    tid = str(topic.get("id") or "topic")
    gid = f"we-solver-{tid}"
    norm = sol.get("cards") or []
    total = len(norm)
    problem = sol.get("problem") or "Worked example."

    def _code_fields() -> dict[str, Any]:
        return {"code_snippet": code, "code_language": "python"} if code else {}

    # Always open with an explicit setup card stating the problem; `cards` are the steps.
    cards: list[dict[str, Any]] = [{
        "id": f"we-solve-{tid}-setup",
        "blueprint_key": "worked_example",
        "card_type": "worked_example",
        "title": "Worked Example",
        "points": ["Problem:", f"  - {problem}"],
        "visual_description": str(sol.get("problem_visual") or ""),
        "continuation_group_id": gid,
        "metadata": {
            "worked_example_setup": True, "worked_example_solver": True,
            "example": {"role": "setup"},
            # Hidden generation contract (validation + future use; not shown in the problem text).
            "expected_final_answer": str(sol.get("expected_final_answer") or ""),
            "required_cases": list(sol.get("required_cases") or []),
            "expected_steps": sol.get("expected_steps"),
        },
        **_code_fields(),
    }]
    for n, card in enumerate(norm):
        goal = str(card.get("goal") or "").strip()
        reasoning = str(card.get("reasoning") or "").strip()
        work = [str(w) for w in (card.get("work") or [])]
        result = str(card.get("result") or "").strip()
        note = card.get("teaching_note") if isinstance(card.get("teaching_note"), dict) else None
        meta: dict[str, Any] = {
            "worked_example_solver": True,
            "example": {"role": "step", "index": n + 1, "total": total},
        }
        if card.get("prior_state") is not None:
            meta["prior_state"] = card["prior_state"]
        if card.get("cases_covered"):
            meta["cases_covered"] = card["cases_covered"]
        # Best-effort per-action code anchor — keep ONLY when it matches the work length 1:1
        # (a mismatched/absent anchor is discarded; it never blocks rendering — spec §9).
        code_lines = card.get("code_lines")
        if isinstance(code_lines, list) and len(code_lines) == len(work):
            meta["code_lines"] = code_lines
        cards.append({
            "id": f"we-solve-{tid}-{n}",
            "blueprint_key": "worked_example",
            "card_type": "worked_example",
            "title": card.get("title") or f"Step {n + 1}",
            # Structured, authoritative learner-facing fields (the new renderer reads these).
            "goal": goal,
            "reasoning": reasoning,
            "work": work,
            "result": result,
            **({"teaching_note": note} if note else {}),
            # Backward-compat bullet view for any consumer still reading `points`.
            "points": _step_points(goal, reasoning, work, result, note),
            "visual_description": str(card.get("visual") or ""),
            "continuation_group_id": gid,
            "metadata": meta,
            **_code_fields(),
        })
    if len(cards) < 2:
        return []  # need the setup + at least one real step
    last = cards[-1]
    last_meta = last.setdefault("metadata", {})
    # The final step's conclusion = its `result`; the blueprint verifies it against the hidden
    # expected_final_answer and stamps reaches_final_answer only when it actually matches.
    final = sol.get("expected_final_answer") or sol.get("final_answer")
    last_meta["final_answer"] = str(last.get("result") or final or "")
    return cards


def _replace_worked_example_cards(lesson_json: dict[str, Any], step_cards: list[dict[str, Any]]) -> None:
    """Swap the lesson's worked-example cards for the solved ones, in place."""
    cards = list(lesson_json.get("lesson_cards") or [])
    rebuilt: list[dict[str, Any]] = []
    inserted = False
    for card in cards:
        if str(card.get("blueprint_key") or card.get("card_type") or "").lower() == "worked_example":
            if not inserted:
                rebuilt.extend(step_cards)
                inserted = True
            continue
        rebuilt.append(card)
    if not inserted:
        idx = next((j for j, c in enumerate(rebuilt)
                    if str(c.get("blueprint_key") or "").lower() == "practice"), len(rebuilt))
        rebuilt[idx:idx] = step_cards
    lesson_json["lesson_cards"] = rebuilt


def _extract_lesson_code(cards: list[Any]) -> str:
    """The longest code_snippet the lesson already carries (the LLM's own implementation),
    shown verbatim in the IDE panel — we don't re-generate or trace it."""
    best = ""
    for card in cards or []:
        if not isinstance(card, dict):
            continue
        snippet = str(card.get("code_snippet") or "").strip()
        if len(snippet) > len(best):
            best = snippet
    return best


def _blueprint_wants_worked_example(topic: dict[str, Any]) -> bool:
    """True if this topic type's card blueprint includes a worked_example slot — so we author
    one even when the lesson generation produced none (common on coding topics)."""
    try:
        from app.core.course_blueprints import get_topic_blueprint

        bp = get_topic_blueprint(topic.get("topic_type"))
        seq = list(bp.get("default_card_sequence") or []) + list(bp.get("continuation_card_sequence") or [])
        return "worked_example" in seq
    except Exception:  # noqa: BLE001
        return False


def _feedback_from_status(status: dict[str, Any], sol: dict[str, Any]) -> str:
    """Targeted re-solve feedback derived from the example_status failures, so the retry fixes the
    specific problems (skipped steps / no-op / missing case / cut-short / vague work) — not a blind
    'do it again'."""
    parts = [
        "Your previous worked example was INCOMPLETE. Produce the COMPLETE example again, fixing "
        "EVERY issue below. Keep each step concrete (Work with actual values + a Result) and end by "
        "stating the final answer.",
    ]
    comp = status.get("completeness") or {}
    prog = status.get("progression") or {}
    cov = status.get("coverage") or {}
    field_issues = (status.get("structure") or {}).get("field_issues") or []
    if comp.get("skipped"):
        parts.append(f"- Too few steps: walk through EVERY step (at least {comp.get('expected_min_steps')}), "
                     "expanding each recursive call / sub-process into its own steps; skip nothing.")
    if prog.get("algorithmic_steps"):
        parts.append("- These steps read like an algorithm walkthrough, not code: show the EXACT code "
                     "line/trace in `work` and concrete runtime state (variables, call stack, return) "
                     "in `result` for every step.")
    if prog.get("inconsistent_steps"):
        parts.append("- Fix the arithmetic: a merge/concatenation result must be exactly its inputs "
                     "combined (same elements); recompute the wrong steps.")
    if prog.get("no_op_steps"):
        parts.append("- Remove no-op steps (where nothing changed); every step must advance the solution.")
    if prog.get("repeated_steps"):
        parts.append("- Remove repeated steps that re-state an earlier step without new progress.")
    if prog.get("continuity_issues"):
        parts.append("- Keep continuity: each step must pick up the exact state the previous step ended on.")
    if field_issues:
        parts.append("- Every step needs CONCRETE work (actual values/operations), not vague phrases, and a result.")
    if cov.get("missing"):
        parts.append("- Make sure steps demonstrate these required cases: " + ", ".join(cov["missing"]) + ".")
    if not comp.get("finished"):
        parts.append(f"- It did not reach the final answer ({sol.get('expected_final_answer')}); "
                     "continue until the result is reached.")
    elif not comp.get("visible_conclusion"):
        parts.append(f"- The final step must clearly STATE the answer ({sol.get('expected_final_answer')}) "
                     "in its result.")
    return "\n".join(parts)


def apply_llm_solved_worked_example(
    lesson_json: dict[str, Any],
    topic: dict[str, Any],
    *,
    solver: Optional[SolveFn] = None,
) -> bool:
    """Replace a topic's worked example with an LLM-solved, start-to-finish text breakdown.
    For a coding topic the solve EXPLAINS the code's execution conceptually (never by line
    number) and each card carries the code for the IDE panel. Failure-safe throughout."""
    try:
        if not solver_enabled() or not isinstance(lesson_json, dict):
            return False
        cards = lesson_json.get("lesson_cards")
        if not isinstance(cards, list) or not cards:
            return False
        has_we = any(
            str(c.get("blueprint_key") or c.get("card_type") or "").lower() == "worked_example"
            for c in cards if isinstance(c, dict)
        )
        if not has_we and not _blueprint_wants_worked_example(topic):
            return False  # this topic type has no worked-example slot — nothing to solve
        # If the topic SHOULD have a worked example but the generation produced none, we still
        # solve and INSERT one (the LLM frequently drops it on coding topics). The replace step
        # below splices the solved cards in when there's nothing to replace.

        is_coding = str(topic.get("topic_type") or "").lower() == "coding_implementation"
        code = _extract_lesson_code(cards) if is_coding else ""
        code = code or None

        existing = _existing_problem_text(cards)
        sol = solve_worked_example(topic, existing_problem=existing, code=code, solver=solver)
        if sol is None:
            # Visible diagnostic: the solver path was taken but produced nothing — almost always
            # a missing/dummy OPENAI_API_KEY (the lesson then keeps the weaker lean worked example).
            has_key = bool((os.getenv("OPENAI_API_KEY") or "").strip()) and \
                os.getenv("OPENAI_API_KEY", "").strip().lower() != "dummy"
            lesson_json.setdefault("metadata", {})["worked_example_solver"] = {
                "applied": False, "version": SOLVER_VERSION,
                "reason": "solver_returned_none" + ("" if has_key else "_no_api_key"),
            }
            _log.warning("worked-example solver: produced nothing for %s (api_key=%s) — lean fallback shown",
                         topic.get("id"), has_key)
            return False
        if sol.get("coding_fallback_used"):
            # The structural coding solver could not pass the gate (or the cards call errored). Keep
            # the base example and record WHY — the old line-execution trace is NOT a fallback.
            lesson_json.setdefault("metadata", {})["worked_example_solver"] = {
                "applied": False, "version": SOLVER_VERSION,
                "status": "coding_fallback_used", "reason": sol.get("reason"),
            }
            _log.warning("worked-example solver: coding structural solve failed for %s (reason=%s) — base example kept",
                         topic.get("id"), sol.get("reason"))
            return False
        # Completeness loop: build the cards, evaluate them against the FULL example contract, and
        # re-solve with TARGETED feedback when the example is incomplete (skipped steps, no-op steps,
        # a missing required case, a cut-short trace, vague work). Bounded by _MAX_RESOLVE_ATTEMPTS so
        # we never loop or burn unbounded cost; the last (best) attempt is kept.
        from app.services.examples.example_blueprint import stamp_example_metadata

        step_cards: list[dict[str, Any]] = []
        status: dict[str, Any] = {}
        attempts = 0
        for attempt in range(_MAX_RESOLVE_ATTEMPTS + 1):
            attempts = attempt + 1
            step_cards = _build_solution_cards(sol, topic, code=code)
            if not step_cards:
                return False
            status = stamp_example_metadata(
                step_cards,
                expected_final_answer=str(sol.get("expected_final_answer") or ""),
                expected_min_steps=sol.get("expected_steps"),
                required_cases=tuple(sol.get("required_cases") or []),
                enforce_field_contract=True,
                coding=bool(code),
            )
            if status.get("complete") or attempt == _MAX_RESOLVE_ATTEMPTS:
                break
            _log.info("worked-example solver: re-solving %s (reason=%s, attempt=%d)",
                      topic.get("id"), status.get("reason"), attempts)
            retry = solve_worked_example(
                topic, existing_problem=existing, code=code,
                feedback=_feedback_from_status(status, sol), solver=solver,
            )
            if not retry or retry.get("coding_fallback_used"):
                break  # keep the previous (best) attempt; a marker is not a usable solution
            sol = retry

        # `stamp_example_metadata` already stamped role/index/total + example_status on step_cards.
        _replace_worked_example_cards(lesson_json, step_cards)
        lesson_json.setdefault("metadata", {})["worked_example_solver"] = {
            "version": SOLVER_VERSION, "steps": len(step_cards), "coding": bool(code),
            "complete": status.get("complete"), "reason": status.get("reason"), "attempts": attempts,
        }
        return True
    except Exception as exc:  # noqa: BLE001 — the solver must never break a lesson
        _log.warning("worked-example solver: apply failed for %s: %s", topic.get("id"), exc)
        return False
