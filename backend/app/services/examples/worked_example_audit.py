"""Post-generation worked-example completion audit (the prose-path equivalent of
INV-COMPLETE).

A trace-backed worked example is already guaranteed to reach the final answer. But a
prose-only worked example (a non-traceable / conceptual topic, or a coding topic whose
input couldn't be extracted) is just the cards the LLM wrote — and the LLM often stops
after a couple. This audit catches that:

  1. detect a worked example that doesn't reach a final answer / verification,
  2. regenerate it — but at most `max_regenerations` times (a hard cap, so we never
     loop or burn cost),
  3. if it's STILL incomplete after the cap, LOG it + record telemetry rather than
     silently shipping the cut-short example.

`regenerate` is injectable (the real one re-runs lesson generation; tests pass a stub).
With no regenerator wired, the audit still flags + logs incomplete worked examples.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

_log = logging.getLogger(__name__)

# A worked example "reaches the answer" when a card signals completion — either the
# computed `reaches_final_answer` stamp (trace path) or a concluding phrase (prose path).
_FINAL_ANSWER_HINTS = (
    "final answer", "final result", "the answer is", "the result is", "the output is",
    "in conclusion", "therefore", "we get", "is complete", "completes the", "done.",
    "fully sorted", "fully visited", "all nodes", "traversal order", "we have visited all",
)


def _worked_example_groups(cards: list[Any]) -> list[list[dict[str, Any]]]:
    """Group worked-example cards (by continuation group, else one group)."""
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for card in cards or []:
        if not isinstance(card, dict):
            continue
        if str(card.get("blueprint_key") or card.get("card_type") or "").lower() != "worked_example":
            continue
        gid = str(card.get("continuation_group_id") or "_we")
        if gid not in groups:
            groups[gid] = []
            order.append(gid)
        groups[gid].append(card)
    return [groups[g] for g in order]


def _reaches_final_answer(group: list[dict[str, Any]]) -> bool:
    if not group:
        return True  # nothing claimed → nothing to audit
    for card in group:
        if (card.get("metadata") or {}).get("reaches_final_answer"):
            return True
    last = group[-1]
    text = " ".join([
        *(str(p) for p in (last.get("points") or [])),
        str(last.get("main_concept") or ""),
        str(last.get("title") or ""),
        str(last.get("content") or ""),
    ]).lower()
    return any(hint in text for hint in _FINAL_ANSWER_HINTS)


def _incomplete_groups(lesson_json: dict[str, Any]) -> list[list[dict[str, Any]]]:
    return [g for g in _worked_example_groups(lesson_json.get("lesson_cards") or []) if not _reaches_final_answer(g)]


def audit_worked_examples(
    lesson_json: dict[str, Any],
    topic: dict[str, Any],
    *,
    regenerate: Optional[Callable[[dict[str, Any], dict[str, Any]], None]] = None,
    max_regenerations: int = 2,
) -> dict[str, Any]:
    """Audit + bounded-regenerate worked examples. Returns a small report. Failure-safe:
    never raises, never empties a lesson."""
    try:
        if not isinstance(lesson_json, dict):
            return {"status": "skipped"}

        regens = 0
        while True:
            incomplete = _incomplete_groups(lesson_json)
            if not incomplete:
                return {"status": "complete", "regenerations": regens}

            # Out of budget (or no regenerator wired) → log + record, ship as-is.
            if regenerate is None or regens >= max_regenerations:
                from app.services.visual_v2.invariant_metrics import GLOBAL as INV

                _log.warning(
                    "worked-example audit: topic %s still has %d incomplete worked example(s) "
                    "after %d regeneration(s) (cap %d); shipping as-is",
                    topic.get("id"), len(incomplete), regens, max_regenerations,
                )
                INV.record_incomplete_worked_example(regenerations=regens)
                return {
                    "status": "incomplete_after_cap",
                    "regenerations": regens,
                    "incomplete_count": len(incomplete),
                }

            # Spend one regeneration attempt.
            try:
                regenerate(lesson_json, topic)
            except Exception as exc:  # noqa: BLE001 — a failed regen counts as an attempt
                _log.warning("worked-example audit: regenerate raised for %s: %s", topic.get("id"), exc)
            regens += 1
    except Exception as exc:  # noqa: BLE001 — the audit must never break a lesson
        _log.warning("worked-example audit failed for %s: %s", topic.get("id"), exc)
        return {"status": "error"}
