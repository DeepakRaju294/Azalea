from collections import Counter
from typing import Any


def extract_behavioral_labels_from_events(events: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []

    for event in events:
        metadata = event.get("metadata") or {}
        event_labels = metadata.get("behavioral_labels") or []

        if isinstance(event_labels, list):
            labels.extend(str(label) for label in event_labels)

    return labels


def summarize_behavior_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    labels = extract_behavioral_labels_from_events(events)
    counts = Counter(labels)

    possible_overteaching = (
        counts["fast_explanation_skip"] >= 3
        or counts["fast_practice_attempt"] >= 2
    )

    possible_underteaching = (
        counts["long_explanation_dwell"] >= 2
        or counts["slow_practice_attempt"] >= 2
        or counts["revisit_or_reread"] >= 2
    )

    fragile_due_to_revisit = counts["revisit_or_reread"] >= 2
    smooth_progression = (
        counts["normal_progression"] >= 3
        and not possible_underteaching
        and not possible_overteaching
    )

    guidance_parts: list[str] = []

    if possible_overteaching:
        guidance_parts.append(
            "The learner moved quickly through several explanation steps. Compress basics for related future lessons unless practice shows weakness."
        )

    if possible_underteaching:
        guidance_parts.append(
            "The learner spent extra time, revisited steps, or moved slowly through practice. Use slightly more support for related concepts."
        )

    if fragile_due_to_revisit:
        guidance_parts.append(
            "The learner revisited this material multiple times, so treat related concepts as potentially fragile until practice confirms stability."
        )

    if smooth_progression:
        guidance_parts.append(
            "The learner progressed smoothly through this material. Future related lessons can keep a steady pace."
        )

    if not guidance_parts:
        guidance_parts.append(
            "No strong behavioral pacing signal is available yet."
        )

    return {
        "label_counts": dict(counts),
        "possible_overteaching": possible_overteaching,
        "possible_underteaching": possible_underteaching,
        "fragile_due_to_revisit": fragile_due_to_revisit,
        "smooth_progression": smooth_progression,
        "behavior_guidance": " ".join(guidance_parts),
    }