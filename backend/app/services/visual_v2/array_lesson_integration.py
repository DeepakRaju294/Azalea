"""Wire binary_search into a legacy lesson_json (mirror of code_lesson_integration).

For a flag-enabled binary-search topic: simulate on a canonical sorted array,
compile an indexed_sequence_diagram model the frontend renders, and replace the
worked-example cards with one step card per probe/discard frame. Flag-gated;
failures never break the lesson.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from .compilers.indexed_sequence import compile_from_trace

_log = logging.getLogger(__name__)
from .delta_fold import DeltaFoldEngine
from .example_invariants import validate_example
from .flags import is_v2_enabled
from .profiles import delta_vocabulary, profile_for_mode
from .simulators.registry import get_simulator

_CANONICAL_ARRAY = [3, 7, 9, 12, 18, 21, 30]
_CANONICAL_TARGET = 18


def _is_binary_search_topic(topic: dict[str, Any]) -> bool:
    topic_type = str(topic.get("topic_type") or topic.get("course_type") or "").lower()
    if "coding" in topic_type:
        return False  # the code path handles coding implementations
    text = f"{topic.get('title', '')} {topic_type}".lower()
    return "binary search" in text or bool(re.search(r"\bbinary\b.*\bsearch\b", text))


def _step_cards(model: dict[str, Any], render_steps: list[dict[str, Any]], model_id: str) -> list[dict[str, Any]]:
    cards = []
    for i, frame in enumerate(model["frames"]):
        caption = str((render_steps[i] if i < len(render_steps) else {}).get("caption", ""))
        cards.append({
            "id": f"v2-bs-{model_id}-{i + 1}",
            "blueprint_key": "worked_example",
            "card_type": "worked_example",
            "title": f"Binary Search: Step {i + 1}",
            "points": [caption] if caption else [],
            "body": [],
            "main_concept": caption,
            "visual_type": "indexed_sequence",
            "visual_v2_ref": {"visual_model_id": model_id, "frame_index": i, "source": "v2_binary_search"},
            "estimated_seconds": 30,
        })
    return cards


def apply_binary_search_to_lesson(lesson_json: dict[str, Any], topic: dict[str, Any]) -> bool:
    if not isinstance(lesson_json, dict):
        return False
    if not is_v2_enabled("binary_search_range", "binary_search"):
        return False
    if not _is_binary_search_topic(topic):
        _log.info("visual_v2 binary_search: topic %r not detected as binary search (type=%r)",
                  topic.get("title"), topic.get("topic_type"))
        return False
    _log.info("visual_v2 binary_search: engaging for topic %r", topic.get("title"))

    example = {
        "example_id": f"bs_{topic.get('id', 'topic')}",
        "base_type": "indexed_sequence_diagram",
        "mode": "binary_search_range",
        "algorithm": "binary_search",
        "input": {"target": _CANONICAL_TARGET},
        "base_structure": {"array": list(_CANONICAL_ARRAY)},
    }
    if validate_example(example):
        return False

    array = example["base_structure"]["array"]
    trace = get_simulator("binary_search")(example)
    frames = DeltaFoldEngine().fold(
        trace["initial_state"], trace["steps"], set(range(len(array))), delta_vocabulary("binary_search_range")
    )
    if not frames:
        return False

    model_id = f"v2_bs_{topic.get('id', 'topic')}"
    model, render_steps = compile_from_trace(
        trace=trace, frames=frames, array=array, profile=profile_for_mode("binary_search_range"),
        mode="binary_search_range", model_id=model_id,
    )
    step_cards = _step_cards(model, render_steps, model_id)
    if not step_cards:
        return False

    models = lesson_json.setdefault("visual_models", [])
    models[:] = [m for m in models if m.get("id") != model_id]
    models.append(model)

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
        idx = next((j for j, c in enumerate(rebuilt) if str(c.get("blueprint_key") or "").lower() == "practice"), len(rebuilt))
        rebuilt[idx:idx] = step_cards
    lesson_json["lesson_cards"] = rebuilt
    lesson_json.setdefault("metadata", {})["visual_v2_binary_search"] = {"model_id": model_id, "steps": len(step_cards)}
    return True
