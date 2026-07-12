from __future__ import annotations

import re
from typing import Any, Iterable

from app.core.topic_assumptions import match_assumption_rules, normalize_assumption_phrase


def normalize_list_field(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,;\n]+", value) if part.strip()]
    if isinstance(value, dict):
        values = [value.get("title"), value.get("name"), value.get("topic")]
        return [str(item).strip() for item in values if str(item).strip()]
    if isinstance(value, Iterable):
        result: list[str] = []
        for item in value:
            result.extend(normalize_list_field(item))
        return result
    return [str(value).strip()] if str(value).strip() else []


def dedupe_keep_order(items: Iterable[Any], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item or "").strip()
        key = normalize_assumption_phrase(text)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
        if limit is not None and len(result) >= limit:
            break
    return result


def build_assumption_ledger(topic: Any, study_path: Any = None) -> dict[str, list[str]]:
    """Build the lesson's source of truth for what may be treated as known."""
    path = study_path or getattr(topic, "study_path", None)
    current_order = int(getattr(topic, "order_index", 0) or 0)
    current_id = str(getattr(topic, "id", "") or "")

    topic_text = " ".join(
        str(value or "")
        for value in (
            getattr(topic, "title", ""),
            getattr(topic, "purpose", ""),
            getattr(topic, "learner_outcome", ""),
            getattr(topic, "practice_target", ""),
            " ".join(normalize_list_field(getattr(topic, "in_scope", None))),
        )
    )
    matched_rules = match_assumption_rules(topic_text)

    rule_prerequisites: list[str] = []
    rule_do_not_reteach: list[str] = []
    rule_ids: list[str] = []
    for rule in matched_rules:
        rule_ids.append(str(rule.get("id") or ""))
        rule_prerequisites.extend(normalize_list_field(rule.get("assumed_prerequisites")))
        rule_do_not_reteach.extend(normalize_list_field(rule.get("do_not_reteach")))

    explicit_prerequisites = normalize_list_field(getattr(topic, "assumed_prerequisites", None))
    explicit_prerequisites.extend(
        normalize_list_field(getattr(topic, "prerequisite_topics", None))
    )

    prior_taught_content = _derive_prior_taught_content(
        topic=topic,
        study_path=path,
        current_id=current_id,
        current_order=current_order,
    )

    assumed_prerequisites = dedupe_keep_order(
        [*explicit_prerequisites, *rule_prerequisites],
        limit=30,
    )
    prior_taught_content = dedupe_keep_order(prior_taught_content, limit=40)
    do_not_reteach = dedupe_keep_order(
        [
            *assumed_prerequisites,
            *prior_taught_content,
            *rule_do_not_reteach,
        ],
        limit=80,
    )

    return {
        "matched_assumption_rules": dedupe_keep_order(rule_ids),
        "assumed_prerequisites": assumed_prerequisites,
        "prior_taught_content": prior_taught_content,
        "do_not_reteach": do_not_reteach,
        "must_explain_before_use": [
            "Any technical term, symbol, state piece, operation, or idea not listed in assumed_prerequisites or prior_taught_content and not introduced earlier in this lesson.",
            "Any current-topic term needed for correctness before it appears in process, worked_example, or practice.",
        ],
        "components_terms_filter": [
            "Before creating components_terms, remove every assumed prerequisite and prior-taught item from the candidate key terms.",
            "Create components_terms only if at least 3 new current-topic terms remain after that filtering.",
        ],
    }


def format_assumption_ledger_for_prompt(ledger: dict[str, list[str]]) -> str:
    if not ledger:
        return ""

    sections = [
        (
            "matched_assumption_rules",
            "Matched assumption rules",
            "Used only to explain why prerequisites were inferred.",
        ),
        (
            "assumed_prerequisites",
            "Assumed prerequisites",
            "The learner is expected to know these before this lesson; use them naturally without reteaching.",
        ),
        (
            "prior_taught_content",
            "Prior taught content",
            "The learner has already seen these earlier in this study path; do not reteach them.",
        ),
        (
            "do_not_reteach",
            "Do not reteach or define as key terms",
            "These may be named briefly when needed, but they should not become components_terms content.",
        ),
        (
            "must_explain_before_use",
            "Must explain before use",
            "These rules define what cannot be assumed.",
        ),
        (
            "components_terms_filter",
            "Components terms filter",
            "Apply this before deciding whether a components_terms card exists.",
        ),
    ]

    lines: list[str] = []
    for key, title, note in sections:
        values = ledger.get(key) or []
        if not values:
            continue
        lines.append(f"{title}: {note}")
        for value in values:
            lines.append(f"- {value}")

    return "\n".join(lines)


def _derive_prior_taught_content(
    topic: Any,
    study_path: Any,
    current_id: str,
    current_order: int,
) -> list[str]:
    topics = list(getattr(study_path, "topics", None) or []) if study_path is not None else []
    if not topics:
        return []

    prior_topics = []
    for item in topics:
        item_id = str(getattr(item, "id", "") or "")
        if current_id and item_id == current_id:
            continue
        item_order = int(getattr(item, "order_index", 0) or 0)
        if item_order < current_order:
            prior_topics.append(item)

    prior_topics.sort(key=lambda item: int(getattr(item, "order_index", 0) or 0))

    content: list[str] = []
    for item in prior_topics:
        title = str(getattr(item, "title", "") or "").strip()
        if title:
            content.append(title)
        content.extend(normalize_list_field(getattr(item, "in_scope", None)))
        outcome = str(getattr(item, "learner_outcome", "") or "").strip()
        if outcome:
            content.append(outcome)
        practice_target = str(getattr(item, "practice_target", "") or "").strip()
        if practice_target:
            content.append(practice_target)
        # The structured fields above rarely name the actual TERMS an earlier topic DEFINED (an intro's in_scope
        # is typically empty), so a later topic re-defines them (e.g. an intro defines Voltage/Current, then the
        # teaching topic defines them again). Harvest the terms from an earlier topic's already-generated
        # key-terms card so they land in do_not_reteach and the dedup rules (prompt §309-310) actually fire.
        # Best-effort — earlier lessons are generated first (intro synchronously), but a missing/lazy one is fine.
        try:
            lesson = getattr(item, "lesson", None)
            lesson_json = getattr(lesson, "lesson_json", None) if lesson is not None else None
            if isinstance(lesson_json, dict):
                content.extend(_defined_terms_from_lesson(lesson_json))
        except Exception:  # noqa: BLE001 — a detached/lazy relationship must never break generation
            pass

    return content


_KEY_TERM_CARD_TYPES = frozenset({"definition", "components_terms", "key_terms"})


def _defined_terms_from_lesson(lesson_json: dict[str, Any]) -> list[str]:
    """The TERM headers an earlier lesson's key-terms card defined. In a key-terms card the term is a MAIN
    bullet ("Voltage") and its meaning is the indented sub-bullet ("  - The potential difference ..."), so the
    defined terms are the short, non-indented points."""
    terms: list[str] = []
    for card in (lesson_json.get("lesson_cards") or []):
        if not isinstance(card, dict):
            continue
        ct = str(card.get("card_type") or card.get("blueprint_key") or "")
        if ct not in _KEY_TERM_CARD_TYPES:
            continue
        for point in (card.get("points") or card.get("bullets") or []):
            s = str(point)
            if not s or s[0].isspace() or s.lstrip().startswith("-"):
                continue  # an indented definition line, not a term header
            term = s.strip().rstrip(":").strip()
            if term and len(term) <= 60:
                terms.append(term)
    return terms
