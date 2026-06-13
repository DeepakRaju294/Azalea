"""Phase 5 — blueprint skeleton-fill generation (EXAMPLE_SYSTEM_SPEC §6).

Inverts lesson generation: instead of one mega LLM call that authors the whole
lesson, code lays out the card skeleton from the topic type's blueprint and fills
each slot with a focused, narrow task. Example/walkthrough/edge/practice slots are
left as placeholders for the existing fixture handoff to swap (one source of truth).

The per-slot filler is INJECTABLE: the default is deterministic (no LLM — fully
unit-testable and always safe), and a real LLM filler can be plugged in when the
flag is on. Flag-gated (`AZALEA_SKELETON_FILL`), additive, reversible — the legacy
generator stays the default.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.core.course_blueprints import get_topic_blueprint, normalize_topic_type_key

_log = logging.getLogger(__name__)

# Slots the fixture handoff fills (it owns the verified example/practice content).
_HANDOFF_SLOTS = {"worked_example", "code_walkthrough", "edge_case", "practice"}


def skeleton_fill_enabled() -> bool:
    return os.getenv("AZALEA_SKELETON_FILL", "").strip().lower() in {"1", "true", "all", "on"}


@dataclass(frozen=True)
class Slot:
    blueprint_key: str
    optional: bool


def build_card_skeleton(topic: Any) -> list[Slot]:
    """The ordered card slots for this topic type, straight from the blueprint
    (spec §6 step 1). Deterministic — the LLM never chooses the structure."""
    topic_type = normalize_topic_type_key(_topic_attr(topic, "topic_type") or _topic_attr(topic, "course_type"))
    blueprint = get_topic_blueprint(topic_type)
    sequence = list(blueprint.get("default_card_sequence") or [])
    optional = set(blueprint.get("optional_cards") or [])
    return [Slot(blueprint_key=key, optional=key in optional) for key in sequence]


def _topic_attr(topic: Any, name: str) -> Any:
    if isinstance(topic, dict):
        return topic.get(name)
    return getattr(topic, name, None)


def _humanize(key: str) -> str:
    return key.replace("_", " ").title()


# --- the deterministic default filler (testable, never an LLM) -------------------

# What each non-example card is FOR — drives both the deterministic stub and the
# focused LLM prompt (the LLM gets exactly this instruction + source, nothing else).
SLOT_INTENT: dict[str, str] = {
    "background": "Frame why this topic matters and what problem it solves, in 2-3 sentences.",
    "components_terms": "Define the key terms/parts the learner needs, one per bullet.",
    "process": "List the repeatable steps of the procedure in order, one per bullet.",
    "formula_breakdown": "Break the formula into its symbols and what each one means.",
    "comparison": "Contrast the related ideas on the dimensions that distinguish them.",
    "proof_plan": "Outline the proof strategy before the steps.",
    "roadmap": "Preview the upcoming subtopics and how they connect.",
}


def _deterministic_slot(slot: Slot, topic: Any, chunks: list[Any]) -> Optional[dict[str, Any]]:
    """A safe, content-free placeholder so the structure is always valid without an
    LLM. Real prose arrives when an LLM filler is injected."""
    title = _topic_attr(topic, "title") or "Topic"
    intent = SLOT_INTENT.get(slot.blueprint_key, "")
    return {
        "title": f"{_humanize(slot.blueprint_key)}: {title}",
        "points": [intent] if intent else [f"{_humanize(slot.blueprint_key)} for {title}."],
    }


# A filler maps (slot, topic, chunks) -> {title, points} or None (omit an optional slot).
SlotFiller = Callable[[Slot, Any, list[Any]], Optional[dict[str, Any]]]


def _card_from_slot(slot: Slot, filled: dict[str, Any], index: int) -> dict[str, Any]:
    points = [p for p in (filled.get("points") or []) if str(p).strip()]
    return {
        "id": f"sk-{slot.blueprint_key}-{index}",
        "blueprint_key": slot.blueprint_key,
        "card_type": "quick_practice" if slot.blueprint_key == "practice" else slot.blueprint_key,
        "title": str(filled.get("title") or _humanize(slot.blueprint_key)),
        "points": points or [f"{_humanize(slot.blueprint_key)}."],
        "body": [],
        "main_concept": points[0] if points else "",
        "visual_type": "none",
        "estimated_seconds": 30,
    }


def _example_placeholder(slot: Slot, index: int) -> dict[str, Any]:
    """A minimal example/walkthrough/practice card the fixture handoff will replace
    (or, for non-fixture topics, the legacy enrichment fills). Never blank."""
    return {
        "id": f"sk-{slot.blueprint_key}-{index}",
        "blueprint_key": slot.blueprint_key,
        "card_type": "quick_practice" if slot.blueprint_key == "practice" else slot.blueprint_key,
        "title": _humanize(slot.blueprint_key),
        "points": [],
        "body": [],
        "visual_type": "none",
        "estimated_seconds": 30,
    }


def fill_skeleton_lesson(
    topic: Any,
    chunks: Optional[list[Any]] = None,
    *,
    slot_filler: Optional[SlotFiller] = None,
) -> dict[str, Any]:
    """Assemble a lesson_json from the blueprint skeleton (spec §6). Non-example
    slots are filled by `slot_filler` (default: deterministic). Example slots are
    placeholders for the fixture handoff. Optional slots whose filler returns None
    are omitted (never emitted empty)."""
    chunks = chunks or []
    filler = slot_filler or _deterministic_slot
    skeleton = build_card_skeleton(topic)

    cards: list[dict[str, Any]] = []
    for i, slot in enumerate(skeleton):
        if slot.blueprint_key in _HANDOFF_SLOTS:
            cards.append(_example_placeholder(slot, i))
            continue
        try:
            filled = filler(slot, topic, chunks)
        except Exception as exc:  # noqa: BLE001 — a slot failure must not break the lesson
            _log.warning("skeleton_fill: slot %s failed: %s", slot.blueprint_key, exc)
            filled = None
        if filled is None:
            if slot.optional:
                continue  # spec §6.4: omit an optional slot with no content (never empty)
            filled = _deterministic_slot(slot, topic, chunks)
        cards.append(_card_from_slot(slot, filled, i))

    return {
        "lesson_cards": cards,
        "practice_questions": [],
        "visual_models": [],
        "metadata": {"generation": "skeleton_fill"},
    }


# --- the real LLM filler (one focused call per slot; §8.1) ----------------------

_SLOT_SYSTEM = (
    "You write ONE card of a lesson. You are given the card's role and the source "
    "material. Write only that card's content as JSON {title, points}. Each point is "
    "one short, concrete sentence. Use ONLY facts from the source. Do not write other "
    "cards, code, or worked examples — only this card's prose."
)


def _chunk_text(chunks: list[Any], limit: int = 6000) -> str:
    parts: list[str] = []
    for c in chunks or []:
        t = c.get("text") if isinstance(c, dict) else getattr(c, "text", None) or getattr(c, "content", None)
        if t:
            parts.append(str(t))
    return ("\n\n".join(parts))[:limit]


def llm_slot_filler(slot: Slot, topic: Any, chunks: list[Any]) -> Optional[dict[str, Any]]:
    """Fill one card slot with a focused LLM call; falls back to the deterministic
    stub on any error so a lesson is never blocked by one slot."""
    try:
        from app.services.llm_client import generate_card_slot

        title = _topic_attr(topic, "title") or "this topic"
        intent = SLOT_INTENT.get(slot.blueprint_key, f"Write the {_humanize(slot.blueprint_key)} card.")
        user = (
            f"Topic: {title}\nCard role: {slot.blueprint_key}\nInstruction: {intent}\n\n"
            f"Source material:\n{_chunk_text(chunks)}"
        )
        result = generate_card_slot(_SLOT_SYSTEM, user)
        points = [p for p in (result.get("points") or []) if str(p).strip()]
        if not points:
            return None
        return {"title": str(result.get("title") or _humanize(slot.blueprint_key)), "points": points}
    except Exception as exc:  # noqa: BLE001
        _log.warning("skeleton_fill: LLM slot %s failed, using deterministic: %s", slot.blueprint_key, exc)
        return _deterministic_slot(slot, topic, chunks)
