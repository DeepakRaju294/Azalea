"""Example blueprint — the EXPLICIT structure of a worked example + completeness metadata.

This is the deterministic contract every worked example follows, independent of the retired
example-typing/fixture/ontology system. It pins down (1) exactly what each example card
contains, (2) the rules for how the example PROBLEM is posed, and (3) per-card metadata that
makes a SKIPPED step or an UNFINISHED example visible in the data rather than silent.

  EXAMPLE STRUCTURE
    - SETUP card  : states the COMPLETE problem (exact input values + task + expected answer).
    - STEP cards  : each is ONE state transition (prior state -> action -> resulting state),
                    carrying its position via metadata.example = {role:"step", index, total}.
    - FINAL step  : reaches the final answer (metadata.reaches_final_answer = True).

  COMPLETENESS METADATA (stamped on the setup card's metadata.example_status)
    - skipped  : True when the example has too few steps (the work was skipped over).
    - finished : True when the last step reaches the stated final answer.
    - complete : setup present AND finished AND not skipped.
    - reason   : "" | "missing_setup" | "steps_skipped" | "did_not_finish".
"""
from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

# A multi-step example with fewer than this many STEP cards skipped the work.
MIN_STEPS = 5

# The blueprint, as reference data (what each card role contains).
EXAMPLE_CARD_BLUEPRINT: dict[str, dict[str, str]] = {
    "setup": {
        "role": "setup",
        "contains": "the COMPLETE problem stated like a test question — exact input values, "
                    "the task, and the expected answer form, solvable from the statement alone",
        "points": "['Problem:', '  - <the full concrete problem>']",
    },
    "step": {
        "role": "step",
        "contains": "ONE state transition — prior state, the action taken, the resulting state",
        "points": "['Currently:', '  - <state>', 'Action:', '  - <what happens>', 'Now:', '  - <new state>']",
        "metadata": "example = {role:'step', index, total}; visual_description set",
    },
    "final": {
        "role": "the LAST step",
        "contains": "the final answer; metadata.reaches_final_answer = True",
    },
}

# The rule system for HOW the example problem is made (shared by the solver prompt).
EXAMPLE_PROBLEM_RULES = """\
HOW TO MAKE THE EXAMPLE PROBLEM:
- Pick ONE concrete, COMPREHENSIVE, canonical instance of the topic — the kind of problem a
  learner must master, NOT a trivial warm-up. It must be rich enough to need several genuine
  decisions and to reach a non-trivial answer.
- State the COMPLETE problem like a TEST QUESTION: the exact input VALUES (e.g. the actual array
  [38, 27, 43, 3, 9, 82, 10], never the word "array" or a placeholder), the task, and the
  expected answer form — so the learner could solve it from the statement alone.
- Choose the instance so the walkthrough EXERCISES the concept's key cases and decision branches,
  including the tricky / boundary / edge ones — not a path that avoids them."""


def _is_worked_example(card: Any) -> bool:
    return (
        isinstance(card, dict)
        and str(card.get("blueprint_key") or card.get("card_type") or "").lower() == "worked_example"
    )


def _is_setup(card: dict[str, Any]) -> bool:
    return bool((card.get("metadata") or {}).get("worked_example_setup"))


def stamp_example_metadata(
    cards: list[Any], *, final_answer: str = "", boundary: bool = False,
) -> dict[str, Any]:
    """Stamp role + step index/total on every worked-example card and an example_status that
    flags SKIPPED steps / an UNFINISHED example. Returns the status. Failure-safe."""
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
            card.setdefault("metadata", {})["example"] = {
                "role": "step", "index": index, "total": total,
            }

        last = steps[-1] if steps else None
        finished = bool(last and (last.get("metadata") or {}).get("reaches_final_answer"))
        if last and final_answer and not finished:
            text = " ".join(str(p) for p in (last.get("points") or [])).lower()
            finished = final_answer.strip().lower() in text
        skipped = (not boundary) and total < MIN_STEPS
        complete = has_setup and finished and not skipped
        reason = ""
        if not complete:
            reason = "missing_setup" if not has_setup else "steps_skipped" if skipped else "did_not_finish"

        status = {
            "present": True, "complete": complete, "steps": total,
            "has_setup": has_setup, "finished": finished, "skipped": skipped, "reason": reason,
        }
        anchor = next((c for c in we if _is_setup(c)), we[0])
        anchor.setdefault("metadata", {})["example_status"] = status

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
