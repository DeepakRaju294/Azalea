"""Example blueprint — the GENERATION contract and the VALIDATION contract for worked examples.

Kept deliberately separate (generation is strict, validation is diagnostic), and independent of
the retired example-typing/fixture/ontology system.

GENERATION CONTRACT (what the solver emits)
  - SETUP card: the COMPLETE concrete problem — exact inputs + task + answer FORMAT (NOT the
    answer value). Hidden metadata carries the real expected_final_answer, required_cases, and
    expected_steps so we can validate against them without spoiling the answer.
  - STEP card: ONE state transition — prior_state -> decision (why this action) -> action ->
    resulting_state.
  - FINAL step: its resulting_state reaches the expected_final_answer.

VALIDATION CONTRACT (what audit_example checks — flags, never raises)
  - structure : setup present; each step carries a transition (prior/action/resulting), and no
    step is a no-op (prior == resulting).
  - completeness : step count within the expected range; the last step reaches the expected
    final answer.
  - The result is stamped on the setup card as `example_status` so failures are inspectable
    (skipped / did_not_finish / missing_transition / no_op_step / missing_setup).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

_log = logging.getLogger(__name__)

# Fallback minimum when the solver did not estimate an expected step count.
DEFAULT_MIN_STEPS = 5

# Reference data: exactly what each card role contains (the generation contract).
EXAMPLE_CARD_BLUEPRINT: dict[str, dict[str, str]] = {
    "setup": {
        "role": "setup",
        "contains": "the COMPLETE problem like a test question — exact input values, the task, "
                    "and the expected answer FORMAT (not the answer value, which is hidden in "
                    "metadata.expected_final_answer)",
        "metadata": "example={role:setup}; expected_final_answer; required_cases; expected_steps",
    },
    "step": {
        "role": "step",
        "contains": "ONE state transition — prior_state, decision (why this action), action, resulting_state",
        "metadata": "example={role:step, index, total}; transition={prior_state, action, resulting_state}",
    },
    "final": {
        "role": "the LAST step",
        "contains": "a step whose resulting_state reaches the expected final answer",
        "metadata": "reaches_final_answer=True",
    },
}

# The one rule system for HOW the example problem is posed (shared by the solver prompt).
EXAMPLE_PROBLEM_RULES = """\
HOW TO MAKE THE EXAMPLE PROBLEM:
- Pick ONE concrete, COMPREHENSIVE, canonical instance of the topic — the kind of problem a
  learner must master, NOT a trivial warm-up. It must be rich enough to need several genuine
  decisions and to reach a non-trivial answer.
- State the COMPLETE problem like a TEST QUESTION: the exact input VALUES (e.g. the actual array
  [38, 27, 43, 3, 9, 82, 10], never the word "array" or a placeholder), the task, and the
  expected answer FORMAT — so the learner could solve it from the statement alone. Do NOT reveal
  the final answer in the problem text; that goes in `expected_final_answer`.
- Choose the instance so the walkthrough EXERCISES the concept's key cases/decisions (list them
  in `required_cases`), including the tricky / boundary / edge ones — not a path that avoids them."""


def _is_worked_example(card: Any) -> bool:
    return (
        isinstance(card, dict)
        and str(card.get("blueprint_key") or card.get("card_type") or "").lower() == "worked_example"
    )


def _is_setup(card: dict[str, Any]) -> bool:
    return bool((card.get("metadata") or {}).get("worked_example_setup"))


def _norm(text: Any) -> str:
    """Normalize a state string for comparison (lowercase, collapse non-alphanumerics)."""
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _transition(card: dict[str, Any]) -> dict[str, str]:
    return (card.get("metadata") or {}).get("transition") or {}


def stamp_example_metadata(
    cards: list[Any],
    *,
    expected_final_answer: str = "",
    expected_steps: Optional[int] = None,
    required_cases: tuple[str, ...] = (),
    allow_short_example: bool = False,
) -> dict[str, Any]:
    """Stamp blueprint metadata on every worked-example card and validate the example, returning
    (and stamping on the setup card) an example_status that flags incompleteness. Failure-safe."""
    try:
        we = [c for c in cards if _is_worked_example(c)]
        if not we:
            return {"present": False}

        steps = [c for c in we if not _is_setup(c)]
        total = len(steps)
        has_setup = any(_is_setup(c) for c in we)

        for card in we:
            meta = card.setdefault("metadata", {})
            if _is_setup(card):
                meta["example"] = {"role": "setup"}
        for index, card in enumerate(steps, start=1):
            card.setdefault("metadata", {})["example"] = {"role": "step", "index": index, "total": total}

        # --- structure: each step is a real transition (prior/action/resulting), no no-ops ---
        # Only enforced when the example uses the transition contract (older free-form cards skip it).
        transition_issues: list[dict[str, Any]] = []
        if any(_transition(c) for c in steps):
            for index, card in enumerate(steps, start=1):
                tr = _transition(card)
                prior, action, resulting = tr.get("prior_state"), tr.get("action"), tr.get("resulting_state")
                if not (str(action or "").strip() and str(resulting or "").strip()):
                    transition_issues.append({"step": index, "issue": "missing_transition"})
                elif prior and _norm(prior) == _norm(resulting):
                    transition_issues.append({"step": index, "issue": "no_op_step"})  # state didn't change

        # --- completeness ---
        last = steps[-1] if steps else None
        finished = bool(last and (last.get("metadata") or {}).get("reaches_final_answer"))
        if last and expected_final_answer and not finished:
            blob = _norm(_transition(last).get("resulting_state")) + " " + _norm(
                " ".join(str(p) for p in (last.get("points") or []))
            )
            finished = _norm(expected_final_answer) in blob

        min_steps = max(1, expected_steps or DEFAULT_MIN_STEPS) if expected_steps else DEFAULT_MIN_STEPS
        skipped = (not allow_short_example) and total < min_steps

        complete = has_setup and finished and not skipped and not transition_issues
        reason = ""
        if not complete:
            if not has_setup:
                reason = "missing_setup"
            elif transition_issues:
                reason = transition_issues[0]["issue"]
            elif skipped:
                reason = "steps_skipped"
            elif not finished:
                reason = "did_not_finish"

        status = {
            "present": True, "complete": complete, "steps": total, "expected_steps": expected_steps,
            "has_setup": has_setup, "finished": finished, "skipped": skipped,
            "transition_issues": transition_issues, "required_cases": list(required_cases), "reason": reason,
        }
        anchor = next((c for c in we if _is_setup(c)), we[0])
        anchor.setdefault("metadata", {})["example_status"] = status
        if expected_final_answer:
            anchor["metadata"]["expected_final_answer"] = expected_final_answer

        if not complete:
            _log.warning("example_blueprint: incomplete worked example (%s, steps=%d)", reason, total)
            try:
                from app.services.visual_v2.invariant_metrics import GLOBAL as INV

                INV.record_incomplete_worked_example(regenerations=0)
            except Exception:  # noqa: BLE001 — telemetry is best-effort
                pass
        return status
    except Exception as exc:  # noqa: BLE001 — metadata stamping must never break a lesson
        _log.warning("example_blueprint: stamp failed: %s", exc)
        return {"present": False, "error": True}
