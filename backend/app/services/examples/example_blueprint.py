"""Example blueprint — the GENERATION contract and the VALIDATION contract for worked examples.

Kept deliberately separate (generation is strict, validation is diagnostic), and independent of
the retired example-typing/fixture/ontology system.

GENERATION CONTRACT (what the solver emits)
  - SETUP card: the COMPLETE concrete problem — exact inputs + task + answer FORMAT (NOT the
    answer value). Hidden metadata carries expected_final_answer, required_cases, expected_min_steps.
  - STEP card: ONE transition — prior_state -> decision (why) -> action -> resulting_state — plus
    cases_covered (which required_cases this step exercises) and an optional visual_delta.
  - FINAL step: metadata.final_answer is its conclusion; it must reach expected_final_answer.

VALIDATION CONTRACT (audit_example — flags, never raises)
  - structure : every step has a full transition (prior/decision/action/resulting) and is not a
    no-op (prior == resulting).
  - completeness : step count meets the topic's expected_min_steps; the final step reaches the
    expected_final_answer (structured metadata match, blob fallback).
  - coverage : every required_case is covered by some step's cases_covered.
  The result is stamped on the setup card as `example_status` so failures are inspectable.
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
        "contains": "the COMPLETE problem like a test question — exact input values, the task, and "
                    "the expected answer FORMAT (not the value; that is metadata.expected_final_answer)",
        "metadata": "example={role:setup}; expected_final_answer; required_cases; expected_min_steps",
    },
    "step": {
        "role": "step",
        "contains": "ONE transition — prior_state, decision (why), action, resulting_state",
        "metadata": "example={role:step,index,total}; transition={prior_state,decision,action,resulting_state}; "
                    "cases_covered=[...]; visual_delta={...} (optional)",
    },
    "final": {
        "role": "the LAST step",
        "contains": "a step whose resulting_state reaches the expected final answer",
        "metadata": "final_answer=<conclusion>; reaches_final_answer=True (stamped on validation)",
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
- List in `required_cases` the key decisions/cases the example MUST exercise (including the tricky
  / boundary / edge ones), and tag each step's `cases_covered` with the ones it addresses — by the
  end EVERY required_case must be covered. Choose the instance so it genuinely hits them all."""


def _is_worked_example(card: Any) -> bool:
    return (
        isinstance(card, dict)
        and str(card.get("blueprint_key") or card.get("card_type") or "").lower() == "worked_example"
    )


def _is_setup(card: dict[str, Any]) -> bool:
    return bool((card.get("metadata") or {}).get("worked_example_setup"))


def _norm(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _transition(card: dict[str, Any]) -> dict[str, str]:
    return (card.get("metadata") or {}).get("transition") or {}


def _case_covered(required: str, covered: set[str]) -> bool:
    """A required case is covered if a step tagged it (normalized, lenient substring match)."""
    nr = _norm(required)
    return any(nr and (nr in c or c in nr) for c in covered)


def stamp_example_metadata(
    cards: list[Any],
    *,
    expected_final_answer: str = "",
    expected_min_steps: Optional[int] = None,
    required_cases: tuple[str, ...] = (),
    allow_short_example: bool = False,
    enforce_transition_contract: bool = True,
) -> dict[str, Any]:
    """Stamp blueprint metadata on every worked-example card and validate the example, returning
    (and stamping on the setup card) a nested example_status. Failure-safe."""
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

        # --- structure: each step is a FULL transition (prior/decision/action/resulting), no no-op ---
        transition_issues: list[dict[str, Any]] = []
        if enforce_transition_contract or any(_transition(c) for c in steps):
            for index, card in enumerate(steps, start=1):
                tr = _transition(card)
                fields = [tr.get("prior_state"), tr.get("decision"), tr.get("action"), tr.get("resulting_state")]
                if not all(str(x or "").strip() for x in fields):
                    transition_issues.append({"step": index, "issue": "missing_transition"})
                elif _norm(tr.get("prior_state")) == _norm(tr.get("resulting_state")):
                    transition_issues.append({"step": index, "issue": "no_op_step"})

        # --- completeness: reaches the expected final answer (structured metadata, blob fallback) ---
        last = steps[-1] if steps else None
        finished = False
        if last:
            actual_final = str((last.get("metadata") or {}).get("final_answer") or "").strip()
            if not expected_final_answer:
                finished = bool((last.get("metadata") or {}).get("reaches_final_answer") or actual_final)
            else:
                ne = _norm(expected_final_answer)
                if actual_final and (ne in _norm(actual_final) or _norm(actual_final) in ne):
                    finished = True
                else:  # fallback: the answer appears in the last step's text
                    blob = _norm(" ".join(str(p) for p in (last.get("points") or [])))
                    finished = bool(ne) and ne in blob
            if finished:
                last.setdefault("metadata", {})["reaches_final_answer"] = True

        min_steps = expected_min_steps if (expected_min_steps and expected_min_steps > 0) else DEFAULT_MIN_STEPS
        skipped = (not allow_short_example) and total < min_steps

        # --- coverage: every required_case exercised by some step's cases_covered ---
        covered: set[str] = set()
        for card in steps:
            for case in (card.get("metadata") or {}).get("cases_covered") or []:
                if str(case).strip():
                    covered.add(_norm(case))
        missing_cases = [c for c in required_cases if str(c).strip() and not _case_covered(c, covered)]
        coverage_fails = enforce_transition_contract and bool(required_cases) and bool(missing_cases)

        complete = has_setup and finished and not skipped and not transition_issues and not coverage_fails
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
            elif coverage_fails:
                reason = "missing_required_case"

        status = {
            "present": True,
            "complete": complete,
            "structure": {"has_setup": has_setup, "steps": total, "transition_issues": transition_issues},
            "completeness": {
                "expected_min_steps": min_steps, "finished": finished, "skipped": skipped,
                "expected_final_answer_present": bool(expected_final_answer),
            },
            "coverage": {
                "required_cases": list(required_cases),
                "covered_cases": sorted(covered),
                "missing_cases": missing_cases,
            },
            "reason": reason,
        }

        anchor = next((c for c in we if _is_setup(c)), we[0])
        ameta = anchor.setdefault("metadata", {})
        ameta["example_status"] = status
        if expected_final_answer:
            ameta["expected_final_answer"] = expected_final_answer
        if required_cases:
            ameta["required_cases"] = list(required_cases)
        if expected_min_steps is not None:
            ameta["expected_min_steps"] = expected_min_steps

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
