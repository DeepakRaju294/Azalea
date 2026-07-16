from __future__ import annotations

from typing import Any


ALLOWED_ACTIONS = {
    "popup_only",
    "open_study_path",
    "review_earlier_topic",
    "ask_question",
}


def validate_and_repair_interactive_links(
    lesson_json: dict[str, Any],
) -> dict[str, Any]:
    from app.services.link_report import attach_link_report, build_link_report

    cards = lesson_json.get("lesson_cards")
    if not isinstance(cards, list):
        return attach_link_report(lesson_json, build_link_report(
            None, source="legacy_validator", issues=["lesson_cards was not a list."]))

    seen_terms: set[str] = set()
    removed_count = 0
    repaired_count = 0
    issues: list[str] = []
    course_type = str(lesson_json.get("course_type") or "")
    is_terminology_course = course_type == "terminology_vocabulary"

    for card_index, card in enumerate(cards):
        if not isinstance(card, dict):
            continue

        raw_links = card.get("interactive_links")
        if not isinstance(raw_links, list):
            card["interactive_links"] = []
            repaired_count += 1
            continue

        current_concept = normalize_term(
            card.get("main_concept")
            or card.get("title")
            or ""
        )
        cleaned_links: list[dict[str, str]] = []
        local_seen: set[str] = set()
        link_cap = 6 if is_terminology_course else 3

        for link in raw_links:
            normalized = normalize_link(link)
            if normalized is None:
                removed_count += 1
                issues.append(f"Removed invalid link on card {card_index}.")
                continue

            term_key = normalize_term(normalized["text"])
            if not term_key:
                removed_count += 1
                issues.append(f"Removed empty link on card {card_index}.")
                continue

            if current_concept and term_key == current_concept:
                removed_count += 1
                issues.append(
                    f"Removed link '{normalized['text']}' on card {card_index}: it matches the current concept."
                )
                continue

            if term_key in local_seen:
                removed_count += 1
                issues.append(
                    f"Removed duplicate local link '{normalized['text']}' on card {card_index}."
                )
                continue

            if term_key in seen_terms and not is_terminology_course:
                removed_count += 1
                issues.append(
                    f"Removed repeated topic link '{normalized['text']}' on card {card_index}."
                )
                continue

            if len(cleaned_links) >= link_cap:
                removed_count += 1
                issues.append(
                    f"Removed extra link '{normalized['text']}' on card {card_index}: link cap is {link_cap}."
                )
                continue

            cleaned_links.append(normalized)
            local_seen.add(term_key)
            seen_terms.add(term_key)

        if cleaned_links != raw_links:
            repaired_count += 1

        card["interactive_links"] = cleaned_links

    report = build_link_report(cards, source="legacy_validator", removed_count=removed_count,
                               repaired_card_count=repaired_count, issues=issues)
    return attach_link_report(lesson_json, report)


def normalize_link(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    text = clean_text(value.get("text"))
    explanation = clean_text(value.get("explanation"))
    why_it_matters_here = clean_text(value.get("why_it_matters_here"))
    action = clean_text(value.get("action")) or "popup_only"
    target = clean_text(value.get("target"))

    if action not in ALLOWED_ACTIONS:
        action = "popup_only"

    # Only popup_only/ask_question RENDER the explanation as their content, so only they require one.
    # Navigation links (open_study_path CTA, review_earlier_topic jump) intentionally allow an empty
    # explanation — removing them here silently destroyed valid nav links during card regeneration.
    if not text:
        return None
    if action in ("popup_only", "ask_question") and not explanation:
        return None

    normalized: dict[str, Any] = {
        "text": text,
        "explanation": explanation,
        "why_it_matters_here": why_it_matters_here,
        "action": action,
        "target": target,
    }
    # Canonical concept identity must survive every normalization (backend dedup/lineage depend on it).
    if value.get("concept_id"):
        normalized["concept_id"] = str(value.get("concept_id"))
    return normalized


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_term(value: Any) -> str:
    text = clean_text(value).lower()
    return " ".join(text.replace("_", " ").replace("-", " ").split())
