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

# solver(payload) -> structured solution dict | None. payload carries the built prompt.
SolveFn = Callable[[dict[str, Any]], Optional[dict[str, Any]]]


def solver_enabled() -> bool:
    """Default ON; flip off with AZALEA_WORKED_EXAMPLE_SOLVER=0."""
    return os.getenv("AZALEA_WORKED_EXAMPLE_SOLVER", "1").strip().lower() not in {"0", "false", "off", "no"}


_SYSTEM = (
    "You are a precise, rigorous tutor authoring a WORKED EXAMPLE. "
    "Pose ONE concrete, fully-specified problem for the given topic, then SOLVE IT COMPLETELY "
    "from start to finish, showing every step of the work. Never skip steps and never stop "
    "before the final answer. Each step is ONE clear reasoning move with the concrete "
    "calculation or manipulation shown explicitly. Every number you write must be correct, "
    "and the final answer must follow directly from the steps.\n"
    "Return ONLY a JSON object of exactly this shape:\n"
    '{"problem": "<the concrete problem statement>", '
    '"steps": [{"title": "<short step name>", "detail": ["<one reasoning move / line of work>", ...]}, ...], '
    '"final_answer": "<the final result>"}'
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


def _build_user_prompt(topic: dict[str, Any], existing_problem: str) -> str:
    parts = [f"Topic: {topic.get('title') or ''}"]
    concept = topic.get("concept") or topic.get("learning_goal") or topic.get("main_concept")
    if concept:
        parts.append(f"Concept: {concept}")
    if existing_problem:
        parts.append(f"The lesson frames the example as: {existing_problem}")
    parts.append("Pose a concrete instance of this and solve it fully, step by step.")
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
                {"role": "system", "content": _SYSTEM},
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
    solver: Optional[SolveFn] = None,
) -> Optional[dict[str, Any]]:
    """Run the focused solve. Returns a normalized {problem, steps, final_answer} or None."""
    fn = solver or _default_solver
    payload = {"user": _build_user_prompt(topic, existing_problem), "topic": topic}
    try:
        raw = fn(payload)
    except Exception as exc:  # noqa: BLE001
        _log.warning("worked-example solver: solver raised: %s", exc)
        return None
    if not isinstance(raw, dict):
        return None
    steps = raw.get("steps")
    if not isinstance(steps, list) or not steps:
        return None
    return {
        "problem": str(raw.get("problem") or "").strip(),
        "steps": steps,
        "final_answer": str(raw.get("final_answer") or "").strip(),
    }


def _step_points(step: Any) -> list[str]:
    if not isinstance(step, dict):
        return []
    detail = step.get("detail")
    if isinstance(detail, str):
        detail = [detail]
    elif not isinstance(detail, list):
        detail = []
    return [str(d).strip() for d in detail if str(d).strip()]


def _build_solution_cards(sol: dict[str, Any], topic: dict[str, Any]) -> list[dict[str, Any]]:
    """Structured solution -> worked-example cards: a setup card stating the problem, one
    card per step (the text breakdown), the last stamped reaches_final_answer."""
    tid = str(topic.get("id") or "topic")
    gid = f"we-solver-{tid}"
    problem = sol.get("problem") or _existing_problem_text([]) or "Worked example."
    cards: list[dict[str, Any]] = [{
        "id": f"we-solve-{tid}-setup",
        "blueprint_key": "worked_example",
        "card_type": "worked_example",
        "title": "Worked Example",
        "points": [problem],
        "continuation_group_id": gid,
        "metadata": {"worked_example_setup": True, "worked_example_solver": True},
    }]
    for n, step in enumerate(sol.get("steps") or []):
        points = _step_points(step)
        if not points:
            continue
        cards.append({
            "id": f"we-solve-{tid}-{n}",
            "blueprint_key": "worked_example",
            "card_type": "worked_example",
            "title": str((step or {}).get("title") or f"Step {n + 1}").strip() or f"Step {n + 1}",
            "points": points,
            "continuation_group_id": gid,
            "metadata": {"worked_example_solver": True},
        })
    if len(cards) < 2:
        return []  # need the setup + at least one real step
    last = cards[-1]
    last.setdefault("metadata", {})["reaches_final_answer"] = True
    final = sol.get("final_answer")
    if final:
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


def apply_llm_solved_worked_example(
    lesson_json: dict[str, Any],
    topic: dict[str, Any],
    *,
    solver: Optional[SolveFn] = None,
) -> bool:
    """Replace a non-code topic's worked example with an LLM-solved, start-to-finish text
    breakdown. Returns True iff the lesson was mutated. Failure-safe throughout."""
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

        sol = solve_worked_example(topic, existing_problem=_existing_problem_text(cards), solver=solver)
        if sol is None:
            return False
        step_cards = _build_solution_cards(sol, topic)
        if not step_cards:
            return False
        _replace_worked_example_cards(lesson_json, step_cards)
        lesson_json.setdefault("metadata", {})["worked_example_solver"] = {
            "version": SOLVER_VERSION, "steps": len(step_cards),
        }
        return True
    except Exception as exc:  # noqa: BLE001 — the solver must never break a lesson
        _log.warning("worked-example solver: apply failed for %s: %s", topic.get("id"), exc)
        return False
