from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.course_blueprints import get_course_blueprint

if TYPE_CHECKING:
    from app.models.topic import Topic


SKIP_COURSE_TYPES = {
    "review_refresh",
    "terminology_vocabulary",
}


def maybe_inject_review_card(
    lesson_json: dict[str, Any],
    topic: Topic,
) -> dict[str, Any]:
    cards = lesson_json.get("lesson_cards")
    if not isinstance(cards, list) or not cards:
        report = build_report(False, "lesson_cards was not a list or was empty.")
        lesson_json["review_injection_report"] = report
        return report

    course_type = str(lesson_json.get("course_type") or topic.course_type or "")
    if course_type in SKIP_COURSE_TYPES:
        report = build_report(False, f"Skipped for {course_type}.")
        lesson_json["review_injection_report"] = report
        return report

    prerequisites = parse_prerequisite_topics(getattr(topic, "prerequisite_topics", None))
    if not prerequisites:
        report = build_report(False, "No explicit prerequisite topics found.")
        lesson_json["review_injection_report"] = report
        return report

    if lesson_already_has_review(cards, prerequisites):
        report = build_report(False, "Lesson already includes a prerequisite review card.")
        lesson_json["review_injection_report"] = report
        return report

    review_card = build_review_card(
        topic_title=getattr(topic, "title", None) or "this topic",
        prerequisites=prerequisites,
        insert_index=len(cards),
    )
    insert_index = choose_insert_index(cards)
    cards.insert(insert_index, review_card)
    resequence_card_ids(cards)

    report = build_report(
        True,
        f"Injected quick prerequisite review for: {', '.join(prerequisites[:3])}.",
        prerequisites=prerequisites,
        insert_index=insert_index,
    )
    lesson_json["review_injection_report"] = report
    return report


def parse_prerequisite_topics(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    else:
        text = str(value or "").strip()
        if not text:
            return []
        raw_items = text.replace(";", ",").replace("\n", ",").split(",")

    prerequisites: list[str] = []
    for item in raw_items:
        title = " ".join(str(item or "").strip().split())
        if title and title.lower() not in {"none", "n/a", "no prerequisites"}:
            prerequisites.append(title[:120])

    return list(dict.fromkeys(prerequisites))[:5]


def lesson_already_has_review(cards: list[Any], prerequisites: list[str]) -> bool:
    prerequisite_terms = [item.lower() for item in prerequisites]
    for card in cards:
        if not isinstance(card, dict):
            continue
        title = str(card.get("title") or "").lower()
        blueprint_key = str(card.get("blueprint_key") or "").lower()
        review_concepts = [
            str(item or "").lower()
            for item in card.get("review_concepts", [])
            if isinstance(card.get("review_concepts"), list)
        ]
        if "quick review" in title or blueprint_key == "review_injection":
            return True
        if any(term in " ".join(review_concepts) for term in prerequisite_terms):
            return True
    return False


def get_refresh_bullets_from_blueprint(prerequisite_course_type: str | None) -> list[str]:
    if not prerequisite_course_type:
        return []
    try:
        blueprint = get_course_blueprint(prerequisite_course_type)
        rules = blueprint.get("later_refresh_rules") or []
        return [str(rule).strip() for rule in rules if str(rule).strip()][:3]
    except Exception:
        return []


def build_review_card(
    topic_title: str,
    prerequisites: list[str],
    insert_index: int,
    prerequisite_course_type: str | None = None,
) -> dict[str, Any]:
    primary = prerequisites[0]
    other_prerequisites = prerequisites[1:4]
    prerequisite_text = ", ".join(prerequisites[:4])
    blueprint_refresh_bullets = get_refresh_bullets_from_blueprint(prerequisite_course_type)

    return {
        "id": f"card-{insert_index + 1}",
        "blueprint_key": "review_injection",
        "card_type": "micro_check",
        "title": f"Quick Review: {primary}",
        "body": [
            (
                f"Before {topic_title}, make sure {primary} is available as a working idea. "
                "This is a lightweight refresh, not a full detour."
            )
        ],
        "bullets": blueprint_refresh_bullets or [
            f"Recall the key rule or structure from {primary}.",
            f"Connect it directly to why {topic_title} needs it.",
            "If this feels fuzzy, use the popup or ask before continuing.",
        ],
        "points": blueprint_refresh_bullets or [
            f"Recall the key rule or structure from {primary}.",
            f"Connect it directly to why {topic_title} needs it.",
            "If this feels fuzzy, use the popup or ask before continuing.",
        ],
        "main_concept": f"Prerequisite review for {primary}",
        "new_concepts": [],
        "review_concepts": prerequisites[:5],
        "prerequisite_concepts": prerequisites[:5],
        "related_formulas": [],
        "related_symbols": [],
        "common_misconceptions": [
            "Moving into the new topic while the prerequisite rule is only name-recognized."
        ],
        "concept_support": [
            {
                "concept": primary,
                "state_hint": "fragile",
                "support": "short_reminder",
                "hover_explanation": (
                    f"{primary} is used as a prerequisite for {topic_title}. "
                    "You only need the part that supports the next card."
                ),
            }
        ],
        "interactive_links": [
            {
                "text": primary,
                "explanation": (
                    f"{primary} is a prerequisite idea for this topic. "
                    "If the rule, structure, or notation is not fresh, review it briefly."
                ),
                "why_it_matters_here": f"{topic_title} builds on this earlier idea.",
                "action": "review_earlier_topic",
                "target": primary,
            }
        ],
        "styled_elements": [
            {
                "type": "checklist",
                "title": "Prerequisite check",
                "data": {
                    "items": [
                        {
                            "label": prerequisite,
                            "description": (
                                "Can you state the useful rule or role in one sentence?"
                            ),
                        }
                        for prerequisite in [primary, *other_prerequisites]
                    ]
                },
            }
        ],
        "visual_plan": {},
        "annotations": [],
        "example": "",
        "micro_check": {
            "type": "reveal",
            "prompt": f"What should you remember from {primary} before continuing?",
            "answer": (
                f"Remember the specific rule, structure, or notation from {primary} "
                f"that {topic_title} will use. You do not need a full reteach right now."
            ),
        },
        "deeper_explanation": (
            f"The prerequisite set for this topic is: {prerequisite_text}. "
            "If one of these is unstable, review just that piece rather than restarting the whole path."
        ),
        "what_to_notice": f"This card is here because {topic_title} depends on prior material.",
        "next_transition": "Now use that recalled idea in the new topic.",
        "quality_score": 100,
        "estimated_seconds": 25,
        "transition_text": "Now use that recalled idea in the new topic.",
        "next_card_label": "Continue",
        "practice_question_index": -1,
        "visual_index": -1,
    }


def choose_insert_index(cards: list[Any]) -> int:
    if len(cards) <= 1:
        return len(cards)

    for index, card in enumerate(cards[:4]):
        if not isinstance(card, dict):
            continue
        card_type = str(card.get("card_type") or "")
        if card_type in {"definition", "core_idea", "method_process", "process_step"}:
            return index

    return 1


def resequence_card_ids(cards: list[Any]) -> None:
    for index, card in enumerate(cards):
        if isinstance(card, dict):
            card["id"] = f"card-{index + 1}"


def build_report(
    injected: bool,
    reason: str,
    prerequisites: list[str] | None = None,
    insert_index: int | None = None,
) -> dict[str, Any]:
    return {
        "injected": injected,
        "reason": reason,
        "prerequisites": prerequisites or [],
        "insert_index": insert_index,
    }
