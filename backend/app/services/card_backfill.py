"""Required-card backfill (#2): regenerate a missing/empty required card instead of shipping without it.

The malformed 2-card Kruskal topic happened because a required card (its worked_example) was silently
dropped. This pass runs AFTER the solver/finalize: it compares the lesson against the topic blueprint's
required cards, and for each one missing or empty it regenerates THAT card specifically — the
worked_example via the existing solver, other cards via a focused single-card LLM call — inserting it at
the blueprint position. Every miss + outcome is logged (#3), so a drop is never invisible again.

Generators are injected, so the orchestration is unit-testable without an API call.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from app.services.card_failure_log import log_card_failure

_log = logging.getLogger(__name__)

WorkedExampleFn = Callable[[dict[str, Any], dict[str, Any]], bool]            # (lesson_json, topic) -> applied?
SingleCardFn = Callable[[str, dict[str, Any], dict[str, Any]], Optional[dict[str, Any]]]  # (key, lesson, topic) -> card


def _card_key(card: dict[str, Any]) -> str:
    return str(card.get("blueprint_key") or card.get("card_type") or "").strip().lower()


def _is_empty(card: dict[str, Any]) -> bool:
    """A card is 'empty' (counts as missing) when it carries no teaching content."""
    if str(card.get("blueprint_key") or "").lower() == "worked_example":
        # a worked example needs steps; a bare setup/title card doesn't count
        pts = card.get("points") or []
        return not any(isinstance(p, (dict, str)) and str(p).strip() for p in pts)
    return not (card.get("points") or card.get("code_snippet") or card.get("body"))


def _required_cards(blueprint: dict[str, Any]) -> list[str]:
    optional = set(blueprint.get("optional_cards") or [])
    return [k for k in (blueprint.get("default_card_sequence") or []) if k not in optional]


def _insert_at_blueprint_position(cards: list[dict[str, Any]], card: dict[str, Any],
                                  key: str, order: list[str]) -> None:
    """Insert `card` so the deck follows the blueprint order as closely as possible.

    `order` must be the blueprint's FULL declared sequence, not just the required-cards subset:
    an existing OPTIONAL card (e.g. prerequisites, itself not being backfilled) has no rank in a
    required-only list and defaults to "last", so a backfilled required card that belongs AFTER it
    (e.g. components_terms, which the sequence places after prerequisites) gets inserted BEFORE it
    instead — live: a study_path_introduction whose model output dropped components_terms had it
    backfilled and spliced ahead of the prerequisites card, contradicting the declared order."""
    rank = {k: i for i, k in enumerate(order)}
    target = rank.get(key, len(order))
    for i, existing in enumerate(cards):
        if rank.get(_card_key(existing), len(order)) > target:
            cards.insert(i, card)
            return
    cards.append(card)


def backfill_missing_required_cards(
    lesson_json: dict[str, Any],
    topic: dict[str, Any],
    *,
    worked_example_fn: Optional[WorkedExampleFn] = None,
    single_card_fn: Optional[SingleCardFn] = None,
) -> list[str]:
    """Regenerate every missing/empty required card. Returns the keys still missing afterward."""
    try:
        from app.core.course_blueprints import IMPLEMENTATION_FOLLOW_UP, get_topic_blueprint
        # An implementation-follow-up coding topic drops the background card, so it must not be REQUIRED here
        # (otherwise backfill re-adds the very card the follow-up strip removed). Derive the relationship from
        # the topic's modifiers so the required set matches the generated blueprint.
        _rel = (IMPLEMENTATION_FOLLOW_UP if IMPLEMENTATION_FOLLOW_UP in (topic.get("modifiers") or [])
                else None)
        blueprint = get_topic_blueprint(topic.get("topic_type"), relationship_to_parent=_rel)
    except Exception:  # noqa: BLE001
        return []
    required = _required_cards(blueprint)
    full_sequence = list(blueprint.get("default_card_sequence") or []) or required
    cards = lesson_json.setdefault("lesson_cards", [])
    present = {_card_key(c) for c in cards if isinstance(c, dict) and not _is_empty(c)}
    missing = [k for k in required if k not in present]
    if not missing:
        return []

    for key in missing:
        action, detail = "dropped", ""
        try:
            if key == "worked_example":
                fn = worked_example_fn or _default_worked_example
                action = "regenerated" if fn(lesson_json, topic) else "dropped"
            else:
                fn = single_card_fn or _default_single_card
                card = fn(key, lesson_json, topic)
                if card:
                    _insert_at_blueprint_position(cards, card, key, full_sequence)
                    action = "regenerated"
        except Exception as exc:  # noqa: BLE001 — backfill must never break a lesson
            detail = repr(exc)
        log_card_failure(topic=topic, card_key=key, stage="backfill",
                         reason="missing_required_card", action=action, detail=detail)

    present = {_card_key(c) for c in cards if isinstance(c, dict) and not _is_empty(c)}
    still = [k for k in required if k not in present]
    # DETERMINISTIC LAST RESORT for practice (product decision): the LLM backfill can fail, and a lesson then
    # shipped `ready` with missing_required_cards=['practice'] recorded and ignored (live). A recall practice
    # built from the lesson's own takeaways is never great but always present — and the stamp keeps it honest.
    if "practice" in still:
        card = _deterministic_practice_card(lesson_json, topic)
        if card:
            _insert_at_blueprint_position(cards, card, "practice", full_sequence)
            log_card_failure(topic=topic, card_key="practice", stage="backfill",
                             reason="missing_required_card", action="synthesized_deterministic", detail="")
            present = {_card_key(c) for c in cards if isinstance(c, dict) and not _is_empty(c)}
            still = [k for k in required if k not in present]
    return still


def _deterministic_practice_card(lesson_json: dict[str, Any], topic: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Last-resort practice card, no LLM: recall/apply prompts from the lesson's own key takeaways (or its
    teaching-card titles when takeaways are absent). Stamped `synthesized: deterministic_backfill` so telemetry
    can count how often the real generator failed."""
    title = str(topic.get("title") or "this topic").strip() or "this topic"
    takeaways = [str(t).strip() for t in (lesson_json.get("key_takeaways") or []) if str(t).strip()]
    if takeaways:
        points = ["In your own words, explain each of the following — and give one concrete example for each:"]
        points += [f"  - {t}" for t in takeaways[:4]]
    else:
        titles = [str(c.get("title") or "").strip() for c in (lesson_json.get("lesson_cards") or [])
                  if isinstance(c, dict) and _card_key(c) not in ("practice", "worked_example")
                  and str(c.get("title") or "").strip()]
        if not titles:
            return None
        points = [f"Explain the following ideas from {title}, with one example each:"]
        points += [f"  - {t}" for t in titles[:4]]
    return {"blueprint_key": "practice", "card_type": "quick_practice",
            "title": f"Practice: {title}", "points": points,
            "metadata": {"synthesized": "deterministic_backfill"}}


def _default_worked_example(lesson_json: dict[str, Any], topic: dict[str, Any]) -> bool:
    from app.services.examples.solver import apply_llm_solved_worked_example
    return bool(apply_llm_solved_worked_example(lesson_json, topic))


def _default_single_card(key: str, lesson_json: dict[str, Any], topic: dict[str, Any]) -> Optional[dict[str, Any]]:
    from app.services.llm_client import generate_single_lesson_card
    return generate_single_lesson_card(key, lesson_json, topic)
