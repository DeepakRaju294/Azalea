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
from typing import Any, Callable, Optional

_log = logging.getLogger(__name__)

# Bump when the solve contract / card shape changes, so cached lessons re-solve on read.
SOLVER_VERSION = 1

# A multi-step worked example with fewer than this many step cards skipped the work — re-solve
# once with feedback. (Genuine boundary cases that come back short on the retry are shipped.)
_MIN_STEP_CARDS = 5

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

_WORKED_EXAMPLE_RULES = (
    EXAMPLE_PROBLEM_RULES
    + """
- The solution must run MORE THAN 5 steps. If your instance resolves in fewer, pick a richer
  instance. (Only a pure boundary topic — "empty input", "single element" — may be shorter,
  because the boundary itself is the lesson.)

CARD STRUCTURE (follow exactly)"""
    + """
- The example OPENS with the problem (provided separately in `problem`), then proceeds with
  ONE step per card, in order, until the final answer. The LAST card states the final result.
- One step per card: a new state, action, calculation, decision, or result is a NEW card.
  Never split one step across cards; never merge two unrelated steps onto one card.
- Solve COMPLETELY to the TERMINAL STATE (final output / returned value / solved expression /
  completed proof / classified answer). Never stop early and never skip work.

CARD CONTENT
- For a state-transition step, put the prior state, the action taken, and the resulting state
  on the SAME card — e.g. a "Currently:" frame, an "Action:" frame, then a "Now:" frame.
- Each card HANDS OFF from the previous one: it picks up the state the last card ended on.
  Do not repeat bullets already shown on an earlier card.
- Show EVERY meaningful decision, including a check that turns out false or a case that is
  ruled out — the learner must see WHY, not only the path taken.
- NEVER gloss over or hand-wave a step. Do NOT state a sub-result and move on (e.g. NEVER
  write "recursively sort the left half to get [27, 38, 43]" as one step). If a step relies on
  a sub-process such as a recursive call, WALK THROUGH that sub-process step by step — show how
  it actually happens (split the subarray, sort each part, merge them), not just its result.
  The learner must see the FULL mechanism, with nothing assumed or skipped.
- Every number and manipulation must be CORRECT, and the final answer must follow directly
  from the steps shown.

BULLET FORMATTING (the `points` array)
- Each point is a MAIN bullet or a SUBPOINT. A subpoint is the same string prefixed with
  EXACTLY two spaces and "- " (e.g. "  - ...").
- A main bullet is a SHORT frame: 4-10 words (rarely >14). If it introduces subpoints it
  ends with a colon (e.g. "Currently:", "Action:", "Now:", "Why:", "Result:").
- A subpoint carries the detail/answer: ONE cognitive unit, 7-18 words (rarely >24). Put the
  actual calculation, value, reason, or state change in subpoints, not the main bullet.
- At most 3 main bullets and 6 total lines per card; keep fewer when the card is dense.
- Plain language and math notation only — NO programming code (this path is for non-code
  topics).

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
    '{"problem": "<the COMPLETE problem like a TEST QUESTION — exact input values (e.g. the '
    "actual array [38, 27, 43, 3, 9, 82, 10], not the word \\\"array\\\"), the task, and the "
    "expected answer FORMAT. Do NOT reveal the final answer here>\", "
    '"expected_final_answer": "<the actual final answer (kept in metadata, never shown in the problem)>", '
    '"required_cases": ["<a key decision/case the walkthrough MUST exercise>", ...], '
    '"expected_steps": <your integer estimate of the MINIMUM steps a COMPLETE walkthrough needs>, '
    '"problem_visual": "<rich description of the INITIAL figure for the setup>", '
    '"cards": [{"title": "<short step name>", '
    '"prior_state": "<the state BEFORE this step>", '
    '"decision": "<WHY this action is the next move / what rule applies>", '
    '"action": "<the ONE operation or change this step performs>", '
    '"resulting_state": "<the state AFTER this step>", '
    '"cases_covered": ["<which required_cases labels THIS step exercises>", ...], '
    '"visual": "<rich description of what THIS step\'s figure shows>"}, ...]}\n'
    "Each card is exactly ONE state transition and MUST include prior_state, decision, action, "
    "resulting_state, and visual. By the last card, every required_case must have been covered, "
    "and the last card's resulting_state MUST reach the expected_final_answer."
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


# Coding worked examples: the LLM does NOT trace by line. The code is shown to the learner in
# a separate IDE panel; here we explain how it EXECUTES on a concrete input — conceptually,
# never by line number — so the learner understands what each operation does to the data.
_CODING_SYSTEM = (
    "You are authoring a worked example that walks through how a given piece of CODE executes on "
    "a concrete input. The code is shown to the learner in a SEPARATE IDE panel, so:\n"
    "- Do NOT restate the code, and do NOT put raw code in the bullets.\n"
    "- NEVER reference line numbers or say things like 'line 8 executes' or 'line N runs'.\n"
    "Each step must explain HOW THE CODE implements the algorithm at that point — name the code "
    "CONSTRUCT responsible and what it does, in plain English, then the effect on the data. Don't "
    "reduce a step to a vague label like 'Merge arrays': say what the code actually does, e.g. "
    "'the while loop compares the front of each half (left_half[i]=82 vs right_half[j]=10); since "
    "82 < 10 is false, the else branch appends right_half[j]=10 to merged_arr and advances j', or "
    "'the base case len(arr) < 2 is false, so the code splits arr into left_half and right_half "
    "and recurses on each'. Cover the loop conditions, the if/else branches taken, the appends, the "
    "pointer increments, and the recursive calls — so the learner sees HOW the code produces each "
    "result. Pose ONE concrete, representative input and walk the execution to the final returned "
    "result.\n\n"
    "Follow these rules EXACTLY:\n\n"
    f"{_WORKED_EXAMPLE_RULES}\n\n"
    "Return ONLY a JSON object of exactly this shape:\n"
    '{"problem": "<the concrete input the code runs on — the ACTUAL values; do NOT reveal the result>", '
    '"expected_final_answer": "<the value the code returns (kept in metadata)>", '
    '"required_cases": ["<a branch/case the trace MUST exercise, e.g. \'left smaller\', \'leftover tail\'>", ...], '
    '"expected_steps": <integer estimate of the MINIMUM steps a COMPLETE trace needs>, '
    '"problem_visual": "<rich description of the initial data state>", '
    '"cards": [{"title": "<short step name>", '
    '"prior_state": "<the data state BEFORE this step>", '
    '"decision": "<which code construct runs next and WHY (the condition checked / branch taken)>", '
    '"action": "<what that construct does to the data>", '
    '"resulting_state": "<the data state AFTER>", '
    '"cases_covered": ["<which required_cases labels THIS step exercises>", ...], '
    '"visual": "<what the data looks like now>"}, ...]}\n'
    "Each card is ONE step of execution and MUST include prior_state, decision, action, and "
    "resulting_state. By the last card every required_case must be covered and resulting_state "
    "MUST be the returned result. Explain HOW THE CODE does each step; never cite line numbers."
)


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

        response = client.responses.create(
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
    """Run the focused solve. Returns a normalized {problem, cards, final_answer} or None.
    `feedback` is appended on a retry (e.g. "you skipped steps"). When `code` is given (a coding
    worked example), the solve explains the code's EXECUTION conceptually — never by line
    number — and the code is shown separately in an IDE panel."""
    fn = solver or _default_solver
    payload = {
        "user": _build_user_prompt(topic, existing_problem, code, feedback),
        "system": _CODING_SYSTEM if code else _SYSTEM,
        "topic": topic,
        "code": code,
    }
    try:
        raw = fn(payload)
    except Exception as exc:  # noqa: BLE001
        _log.warning("worked-example solver: solver raised: %s", exc)
        return None
    if not isinstance(raw, dict):
        return None
    cards = _normalize_solution_cards(raw)
    if not cards:
        return None
    final = str(raw.get("expected_final_answer") or raw.get("final_answer") or "").strip()
    steps_est = raw.get("expected_steps")
    return {
        "problem": str(raw.get("problem") or "").strip(),
        "problem_visual": str(raw.get("problem_visual") or "").strip(),
        "expected_final_answer": final,
        "required_cases": [str(c).strip() for c in (raw.get("required_cases") or []) if str(c).strip()],
        "expected_steps": int(steps_est) if isinstance(steps_est, (int, float)) else None,
        "cards": cards,
        "final_answer": final,  # backward-compat alias
    }


def _coerce_points(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(p).rstrip() for p in value if str(p).strip()]


def _transition_points(prior: str, decision: str, action: str, resulting: str) -> list[str]:
    """Render a transition into the Currently / Decision / Action / Now bullet frames."""
    pts: list[str] = []
    if prior:
        pts += ["Currently:", f"  - {prior}"]
    if decision:
        pts += ["Decision:", f"  - {decision}"]
    if action:
        pts += ["Action:", f"  - {action}"]
    if resulting:
        pts += ["Now:", f"  - {resulting}"]
    return pts


def _normalize_solution_cards(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize each step to {title, points, visual, transition}. The current contract gives
    prior_state/decision/action/resulting_state (-> Currently/Decision/Action/Now + a transition
    record); older free-form `points` (or `steps`/`detail`) are accepted with an empty transition."""
    out: list[dict[str, Any]] = []
    for card in raw.get("cards") if isinstance(raw.get("cards"), list) else []:
        if not isinstance(card, dict):
            continue
        title = str(card.get("title") or "").strip()
        visual = str(card.get("visual") or "").strip()
        prior = str(card.get("prior_state") or "").strip()
        decision = str(card.get("decision") or "").strip()
        action = str(card.get("action") or "").strip()
        resulting = str(card.get("resulting_state") or "").strip()
        if action and resulting:
            cases = [str(c).strip() for c in (card.get("cases_covered") or []) if str(c).strip()]
            out.append({
                "title": title, "visual": visual,
                "points": _transition_points(prior, decision, action, resulting),
                "transition": {"prior_state": prior, "decision": decision, "action": action,
                               "resulting_state": resulting},
                "cases_covered": cases,
                "visual_delta": card.get("visual_delta") if isinstance(card.get("visual_delta"), dict) else None,
            })
        else:
            points = _coerce_points(card.get("points"))
            if points:
                out.append({"title": title, "visual": visual, "points": points, "transition": {}})
    if out:
        return out
    for step in raw.get("steps") if isinstance(raw.get("steps"), list) else []:
        if not isinstance(step, dict):
            continue
        points = _coerce_points(step.get("detail") if step.get("detail") is not None else step.get("points"))
        if points:
            out.append({
                "title": str(step.get("title") or "").strip(),
                "visual": str(step.get("visual") or "").strip(),
                "points": points, "transition": {},
            })
    return out


def _build_solution_cards(
    sol: dict[str, Any], topic: dict[str, Any], *, code: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Structured solution -> worked-example cards: a setup card stating the problem, one
    card per step (the text breakdown), the last stamped reaches_final_answer. When `code`
    is given, every card carries it as `code_snippet` so the frontend shows it in an IDE
    panel (the ONLY real-rendered visual) alongside the conceptual explanation."""
    tid = str(topic.get("id") or "topic")
    gid = f"we-solver-{tid}"
    norm = sol.get("cards") or []
    problem = sol.get("problem") or "Worked example."

    def _code_fields() -> dict[str, Any]:
        return {"code_snippet": code, "code_language": "python"} if code else {}

    # Always open with an explicit setup card stating the problem; `cards` are the steps.
    # `visual_description` carries the RICH spec of what each step's figure should show — the
    # foundation for Phase-2 visuals (and what the debug view renders in the visual space).
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
            # Hidden generation contract (validation + future use; not shown in the problem text).
            "expected_final_answer": str(sol.get("expected_final_answer") or ""),
            "required_cases": list(sol.get("required_cases") or []),
            "expected_steps": sol.get("expected_steps"),
        },
        **_code_fields(),
    }]
    for n, card in enumerate(norm):
        meta: dict[str, Any] = {"worked_example_solver": True}
        if card.get("transition"):
            meta["transition"] = card["transition"]
        if card.get("cases_covered"):
            meta["cases_covered"] = card["cases_covered"]
        if card.get("visual_delta"):
            meta["visual_delta"] = card["visual_delta"]
        cards.append({
            "id": f"we-solve-{tid}-{n}",
            "blueprint_key": "worked_example",
            "card_type": "worked_example",
            "title": card.get("title") or f"Step {n + 1}",
            "points": card["points"],
            "visual_description": str(card.get("visual") or ""),
            "continuation_group_id": gid,
            "metadata": meta,
            **_code_fields(),
        })
    if len(cards) < 2:
        return []  # need the setup + at least one real step
    last = cards[-1]
    last_meta = last.setdefault("metadata", {})
    # The last step's conclusion = its resulting_state; the blueprint verifies it against the
    # hidden expected_final_answer and stamps reaches_final_answer only when it actually matches.
    last_meta["final_answer"] = str((last_meta.get("transition") or {}).get("resulting_state") or "")
    # Older free-form last step (no transition): surface the answer so it's not missing.
    final = sol.get("expected_final_answer") or sol.get("final_answer")
    if final and not last_meta.get("transition"):
        last_meta["final_answer"] = final
        if not any("final answer" in p.lower() for p in last.get("points") or []):
            last["points"] = list(last.get("points") or []) + [f"Final answer: {final}"]
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
        if not any(
            str(c.get("blueprint_key") or c.get("card_type") or "").lower() == "worked_example"
            for c in cards if isinstance(c, dict)
        ):
            return False  # this topic has no worked-example slot — nothing to solve

        is_coding = str(topic.get("topic_type") or "").lower() == "coding_implementation"
        code = _extract_lesson_code(cards) if is_coding else ""
        code = code or None

        existing = _existing_problem_text(cards)
        sol = solve_worked_example(topic, existing_problem=existing, code=code, solver=solver)
        if sol is None:
            return False
        # Completeness guard: a solution shorter than the solver's OWN expected_steps estimate
        # (or the default floor) skipped the work. Re-solve ONCE with feedback; keep the longer.
        threshold = sol.get("expected_steps") or _MIN_STEP_CARDS
        if len(sol.get("cards") or []) < threshold:
            feedback = (
                f"Your previous attempt had only {len(sol.get('cards') or [])} step(s) and SKIPPED "
                "the work (e.g. jumping from the split straight to the final answer). Produce the "
                "COMPLETE worked example now: walk through EVERY step from start to the final "
                "answer — well over 5 steps — with nothing skipped, summarized, or assumed. Expand "
                "every recursive call / sub-process into its own steps. (Only a genuine boundary "
                "case such as an empty or single-element input may legitimately be shorter.)"
            )
            retry = solve_worked_example(
                topic, existing_problem=existing, code=code, feedback=feedback, solver=solver,
            )
            if retry and len(retry.get("cards") or []) > len(sol.get("cards") or []):
                sol = retry
        step_cards = _build_solution_cards(sol, topic, code=code)
        if not step_cards:
            return False
        _replace_worked_example_cards(lesson_json, step_cards)
        # Stamp the example-blueprint metadata: per-card role + step index/total, and an
        # example_status that flags skipped steps / an unfinished example in the data.
        from app.services.examples.example_blueprint import stamp_example_metadata

        status = stamp_example_metadata(
            lesson_json.get("lesson_cards") or [],
            expected_final_answer=str(sol.get("expected_final_answer") or ""),
            expected_min_steps=sol.get("expected_steps"),
            required_cases=tuple(sol.get("required_cases") or []),
            enforce_transition_contract=True,
        )
        lesson_json.setdefault("metadata", {})["worked_example_solver"] = {
            "version": SOLVER_VERSION, "steps": len(step_cards), "coding": bool(code),
            "complete": status.get("complete"), "reason": status.get("reason"),
        }
        return True
    except Exception as exc:  # noqa: BLE001 — the solver must never break a lesson
        _log.warning("worked-example solver: apply failed for %s: %s", topic.get("id"), exc)
        return False
