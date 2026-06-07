from __future__ import annotations

from typing import Any


ALLOWED_MICROCHECK_TYPES = {
    "reveal",
    "multiple_choice",
    "visual_reveal",
    "short_answer",
    "",
}


def validate_and_repair_microchecks(lesson_json: dict[str, Any]) -> dict[str, Any]:
    cards = lesson_json.get("lesson_cards")
    if not isinstance(cards, list):
        report = build_report(0, 0, ["lesson_cards was not a list."])
        lesson_json["microcheck_report"] = report
        return report

    repaired_count = 0
    removed_count = 0
    issues: list[str] = []

    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            continue

        micro_check = card.get("micro_check")
        if not isinstance(micro_check, dict):
            card["micro_check"] = empty_microcheck()
            repaired_count += 1
            continue

        normalized = normalize_microcheck(micro_check)
        if not normalized["prompt"] and not normalized["answer"]:
            card["micro_check"] = empty_microcheck()
            if micro_check != card["micro_check"]:
                repaired_count += 1
            continue

        if not normalized["prompt"] or not normalized["answer"]:
            card["micro_check"] = empty_microcheck()
            removed_count += 1
            repaired_count += 1
            issues.append(
                f"Removed incomplete microcheck on card {index}: prompt and answer are both required."
            )
            continue

        if len(normalized["prompt"].split()) > 35:
            normalized["prompt"] = shorten_words(normalized["prompt"], 35)
            repaired_count += 1
            issues.append(f"Shortened long microcheck prompt on card {index}.")

        if len(normalized["answer"].split()) > 55:
            normalized["answer"] = shorten_words(normalized["answer"], 55)
            repaired_count += 1
            issues.append(f"Shortened long microcheck answer on card {index}.")

        if normalized["type"] not in ALLOWED_MICROCHECK_TYPES:
            normalized["type"] = "reveal"
            repaired_count += 1
            issues.append(f"Normalized microcheck type on card {index}.")

        if normalized["type"] in {"", "short_answer"}:
            normalized["type"] = "reveal"
            repaired_count += 1

        card["micro_check"] = normalized

    report = build_report(removed_count, repaired_count, issues)
    lesson_json["microcheck_report"] = report
    return report


def normalize_microcheck(value: dict[str, Any]) -> dict[str, str]:
    return {
        "type": clean_text(value.get("type") or "reveal").lower(),
        "prompt": clean_text(value.get("prompt")),
        "answer": clean_text(value.get("answer")),
    }


def empty_microcheck() -> dict[str, str]:
    return {"type": "", "prompt": "", "answer": ""}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def shorten_words(value: str, max_words: int) -> str:
    words = value.split()
    if len(words) <= max_words:
        return value
    return " ".join(words[:max_words]).rstrip(",;:") + "..."


def build_report(
    removed_count: int,
    repaired_card_count: int,
    issues: list[str],
) -> dict[str, Any]:
    return {
        "passed": removed_count == 0,
        "removed_microcheck_count": removed_count,
        "repaired_card_count": repaired_card_count,
        "issues": issues,
    }
