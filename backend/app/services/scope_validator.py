from __future__ import annotations

import re
from typing import Any

from app.core.course_stage_rules import STAGE_RULES


def normalize_scope_phrase(value: Any) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", str(value)).lower().strip().split())


GENERIC_FALLBACK_TITLES = {
    "starting point check",
    "why this topic matters",
    "big-picture intuition",
    "core vocabulary / components",
    "how the idea works",
    "step-by-step method",
    "visual or concrete example",
    "common mistakes / edge cases",
    "guided practice",
    "adaptive follow-up",
    "real problem/application",
    "summary / mental model",
    "mastery check",
    "review-later recommendation",
}


def validate_scope_adherence(
    lesson_json: dict[str, Any],
    topic_scope_contract: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    text_only_core_mode = (
        lesson_json.get("generation_mode") == "text_only_core"
        or topic_scope_contract.get("generation_mode") == "text_only_core"
    )

    cards = lesson_json.get("lesson_cards")
    if not isinstance(cards, list):
        cards = []

    practice_questions = lesson_json.get("practice_questions")
    if not isinstance(practice_questions, list):
        practice_questions = []

    allowed_sequence = [
        str(item).strip()
        for item in topic_scope_contract.get("allowed_card_sequence", [])
        if str(item).strip()
    ]
    allowed_set = set(allowed_sequence)
    must_not_teach = [
        str(item).strip().lower()
        for item in topic_scope_contract.get("must_not_teach", [])
        if str(item).strip()
    ]
    out_of_scope = [
        str(item).strip().lower()
        for item in topic_scope_contract.get("out_of_scope_content", [])
        if str(item).strip()
    ]
    popup_only = [
        str(item).strip().lower()
        for item in topic_scope_contract.get("popup_only_prerequisites", [])
        if str(item).strip()
    ]
    assumed_prerequisites = [
        str(item).strip().lower()
        for item in topic_scope_contract.get("assumed_prerequisites", [])
        if str(item).strip()
    ]
    brief_refresh = [
        str(item).strip().lower()
        for item in topic_scope_contract.get("brief_refresh_prerequisites", [])
        if str(item).strip()
    ]
    mini_path_candidates = [
        str(item).strip().lower()
        for item in topic_scope_contract.get("prerequisite_mini_path_candidates", [])
        if str(item).strip()
    ]

    if allowed_set:
        generic_title_count = 0
        generated_blueprint_keys: list[str] = []
        for index, card in enumerate(cards):
            if not isinstance(card, dict):
                continue
            blueprint_key = str(card.get("blueprint_key") or "").strip()
            if blueprint_key and blueprint_key != "review_injection":
                generated_blueprint_keys.append(blueprint_key)
            if blueprint_key and blueprint_key not in allowed_set and blueprint_key != "review_injection":
                issues.append(
                    f"Card {index + 1} uses blueprint_key '{blueprint_key}' outside the scope contract."
                )
            if not blueprint_key:
                issues.append(
                    f"Card {index + 1} has no blueprint_key despite a scoped blueprint sequence existing."
                )
            title = str(card.get("title") or "").strip().lower()
            if title in GENERIC_FALLBACK_TITLES and not blueprint_key:
                generic_title_count += 1
        if generic_title_count >= 3:
            issues.append(
                "Generated lesson used generic fallback cards despite a scoped blueprint sequence existing."
            )
        issues.extend(validate_blueprint_coverage(generated_blueprint_keys, allowed_sequence))
        issues.extend(validate_blueprint_order(generated_blueprint_keys, allowed_sequence))
        if not text_only_core_mode:
            issues.extend(validate_stage_microcheck_requirements(cards, topic_scope_contract))
            issues.extend(validate_stage_support_requirements(cards, topic_scope_contract))

    # "points" is excluded here and checked separately with a ratio heuristic
    # to avoid false positives when out-of-scope phrases appear only in passing.
    searchable_card_fields = (
        "title",
        "main_concept",
        "learning_goal",
        "example",
        "body",
        "bullets",
        "deeper_explanation",
        "what_to_notice",
    )
    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            continue
        text = collect_text(card, searchable_card_fields)
        for phrase in must_not_teach:
            if phrase and phrase in text:
                issues.append(f"Card {index + 1} teaches forbidden content: {phrase}.")
        for phrase in out_of_scope:
            if phrase and phrase in text and is_taught_as_main_content(card, phrase):
                issues.append(f"Card {index + 1} makes out-of-scope content central: {phrase}.")
        for phrase in popup_only:
            if phrase and phrase in text and is_taught_as_main_content(card, phrase):
                issues.append(f"Card {index + 1} turns popup-only prerequisite into full card content: {phrase}.")
            if phrase and phrase in text and not card_has_popup_support(card, phrase):
                issues.append(
                    f"Card {index + 1} mentions popup-only prerequisite without popup/support: {phrase}."
                )
        for phrase in assumed_prerequisites:
            if phrase and phrase in text and is_taught_as_main_content(card, phrase):
                issues.append(
                    f"Card {index + 1} turns assumed prerequisite into a teaching card: {phrase}."
                )
        for phrase in brief_refresh:
            if phrase and phrase in text and is_taught_as_main_content(card, phrase):
                if len(text.split()) > 80:
                    issues.append(f"Card {index + 1} over-expands brief-refresh prerequisite: {phrase}.")
        for phrase in mini_path_candidates:
            if phrase and phrase in text and is_taught_as_main_content(card, phrase):
                issues.append(
                    f"Card {index + 1} teaches prerequisite mini-path candidate inside this lesson: {phrase}."
                )

        # Check card.points with ratio heuristic to avoid false positives.
        # A point fails if the forbidden phrase starts the point OR dominates it (>= 30% word share).
        points_list = card.get("points") or []
        if isinstance(points_list, list):
            for point in points_list:
                normalized_point = normalize_scope_phrase(point)
                point_word_count = len(normalized_point.split())
                for phrase in must_not_teach:
                    normalized_phrase = normalize_scope_phrase(phrase)
                    phrase_word_count = len(normalized_phrase.split())
                    if normalized_phrase and (
                        normalized_point.startswith(normalized_phrase)
                        or (
                            phrase_word_count > 0
                            and point_word_count > 0
                            and phrase_word_count / point_word_count >= 0.30
                        )
                    ):
                        issues.append(
                            f"Card {index + 1} point teaches forbidden content: {phrase}."
                        )
                for phrase in out_of_scope:
                    normalized_phrase = normalize_scope_phrase(phrase)
                    phrase_word_count = len(normalized_phrase.split())
                    if normalized_phrase and (
                        normalized_point.startswith(normalized_phrase)
                        or (
                            phrase_word_count > 0
                            and point_word_count > 0
                            and phrase_word_count / point_word_count >= 0.30
                        )
                    ):
                        issues.append(
                            f"Card {index + 1} point makes out-of-scope content central: {phrase}."
                        )

        main_concept = str(card.get("main_concept") or "").strip().lower()
        for link in card.get("interactive_links") or []:
            if not isinstance(link, dict):
                continue
            link_text = str(link.get("text") or "").strip().lower()
            if main_concept and link_text and link_text == main_concept:
                issues.append(
                    f"Card {index + 1} links its own main_concept as a popup."
                )

    for index, question in enumerate(practice_questions):
        if not isinstance(question, dict):
            continue
        text = collect_text(
            question,
            ("question_text", "skill_target", "concept_tested", "related_section"),
        )
        for phrase in must_not_teach + out_of_scope:
            if phrase and phrase in text:
                issues.append(
                    f"Practice question {index + 1} tests out-of-scope content: {phrase}."
                )

    issues.extend(validate_practice_types(practice_questions, topic_scope_contract))
    if not text_only_core_mode:
        issues.extend(validate_visual_scope(lesson_json, cards, topic_scope_contract))

    report = {
        "passed": not issues,
        "issues": issues,
        "requires_regeneration": bool(issues),
    }
    lesson_json["scope_validation_report"] = report
    return report


def build_scope_retry_feedback(report: dict[str, Any]) -> str:
    issues = report.get("issues")
    if not isinstance(issues, list):
        issues = []
    issue_text = "\n".join(f"- {issue}" for issue in issues[:10])
    return f"""
SCOPE REGENERATION REQUIRED

The previous lesson drifted outside the TopicScopeContract.

Specific issues:
{issue_text or "- Scope validation requested a retry."}

Regenerate with these fixes:
- Teach only the current topic from the TopicScopeContract.
- Remove cards, examples, practice, and visuals about must_not_teach or out_of_scope_content.
- Use only blueprint_keys in allowed_card_sequence.
- Keep prerequisites as assumed, brief refresh, popup-only, or mini-path candidates according to the contract.
- Do not use the generic fallback card sequence when a blueprint sequence exists.
""".strip()


def scope_report_score(report: dict[str, Any]) -> int:
    issues = report.get("issues", [])
    issue_count = len(issues) if isinstance(issues, list) else 0
    score = 100 - issue_count * 15
    if report.get("requires_regeneration"):
        score -= 25
    return score


def collect_text(item: dict[str, Any], fields: tuple[str, ...]) -> str:
    chunks: list[str] = []
    for field in fields:
        value = item.get(field)
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, list):
            chunks.extend(str(part) for part in value)
    return " ".join(chunks).lower()


def collect_any_text(value: Any) -> str:
    chunks: list[str] = []
    if isinstance(value, str):
        chunks.append(value)
    elif isinstance(value, dict):
        for nested in value.values():
            nested_text = collect_any_text(nested)
            if nested_text:
                chunks.append(nested_text)
    elif isinstance(value, list):
        for nested in value:
            nested_text = collect_any_text(nested)
            if nested_text:
                chunks.append(nested_text)
    else:
        return ""
    return " ".join(chunks).lower()


def is_taught_as_main_content(card: dict[str, Any], phrase: str) -> bool:
    central = " ".join(
        str(card.get(field) or "")
        for field in ("title", "main_concept", "learning_goal", "example")
    ).lower()
    return phrase in central


def card_has_popup_support(card: dict[str, Any], phrase: str) -> bool:
    support_text = collect_any_text(card.get("interactive_links") or [])
    support_text += " " + collect_any_text(card.get("concept_support") or [])
    return phrase in support_text


def validate_blueprint_order(
    generated_blueprint_keys: list[str],
    allowed_sequence: list[str],
) -> list[str]:
    issues: list[str] = []
    cursor = 0
    for key in generated_blueprint_keys:
        try:
            next_position = allowed_sequence.index(key, cursor)
        except ValueError:
            try:
                previous_position = allowed_sequence.index(key)
            except ValueError:
                continue
            issues.append(
                f"Blueprint key '{key}' appears out of order; expected sequence is {', '.join(allowed_sequence)}."
            )
            cursor = max(cursor, previous_position + 1)
        else:
            cursor = next_position + 1
    return issues


def validate_blueprint_coverage(
    generated_blueprint_keys: list[str],
    allowed_sequence: list[str],
) -> list[str]:
    issues: list[str] = []
    remaining = list(generated_blueprint_keys)

    for expected_key in allowed_sequence:
        if expected_key in remaining:
            remaining.remove(expected_key)
            continue
        issues.append(f"Missing required blueprint_key from scope sequence: {expected_key}.")

    return issues


def validate_stage_microcheck_requirements(
    cards: list[Any],
    topic_scope_contract: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    course_type = str(topic_scope_contract.get("course_type") or "").strip()
    stage_rules = STAGE_RULES.get(course_type, {})
    if not stage_rules:
        return issues

    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            continue
        blueprint_key = str(card.get("blueprint_key") or "").strip()
        if not blueprint_key or blueprint_key == "review_injection":
            continue
        rule = stage_rules.get(blueprint_key) or {}
        required_microcheck = str(rule.get("microcheck") or "").strip()
        if not required_microcheck:
            continue
        micro_check = card.get("micro_check")
        if not has_non_empty_microcheck(micro_check):
            issues.append(
                f"Card {index + 1} with blueprint_key '{blueprint_key}' is missing required micro_check: {required_microcheck}."
            )

    return issues


def has_non_empty_microcheck(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return any(
        str(value.get(field) or "").strip()
        for field in ("prompt", "question", "answer", "correct_answer", "explanation")
    )


def validate_stage_support_requirements(
    cards: list[Any],
    topic_scope_contract: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    course_type = str(topic_scope_contract.get("course_type") or "").strip()
    stage_rules = STAGE_RULES.get(course_type, {})
    if not stage_rules:
        return issues

    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            continue
        blueprint_key = str(card.get("blueprint_key") or "").strip()
        if not blueprint_key or blueprint_key == "review_injection":
            continue

        rule = stage_rules.get(blueprint_key) or {}
        support = str(rule.get("visual") or "").strip()
        if not support or is_conditional_stage_support(support):
            continue

        if is_styled_stage_support(support):
            if not has_card_styled_support(card):
                issues.append(
                    f"Card {index + 1} with blueprint_key '{blueprint_key}' is missing required styled_elements support: {support}."
                )
            continue

        if not has_card_visual_support(card):
            issues.append(
                f"Card {index + 1} with blueprint_key '{blueprint_key}' is missing required visual support: {support}."
            )

    return issues


def is_conditional_stage_support(value: str) -> bool:
    lower_value = value.lower()
    conditional_markers = (
        " if ",
        "if ",
        "when useful",
        "when helpful",
        "as appropriate",
        "if useful",
        "if helpful",
        "only when",
        "where useful",
        "if the ",
        "if a ",
    )
    return any(marker in lower_value for marker in conditional_markers)


def is_styled_stage_support(value: str) -> bool:
    lower_value = value.lower()
    styled_markers = (
        "styled ui",
        "code block",
        "syntax-highlighted",
        "table",
        "checklist",
        "latex",
        "not a visual_plan",
    )
    return any(marker in lower_value for marker in styled_markers)


def has_card_styled_support(card: dict[str, Any]) -> bool:
    styled_elements = card.get("styled_elements")
    return isinstance(styled_elements, list) and bool(styled_elements)


def has_card_visual_support(card: dict[str, Any]) -> bool:
    visual_index = card.get("visual_index")
    if isinstance(visual_index, int) and visual_index >= 0:
        return True
    visual_plan = card.get("visual_plan")
    if isinstance(visual_plan, dict) and bool(visual_plan):
        return True
    if isinstance(visual_plan, list) and bool(visual_plan):
        return True
    return False


def validate_practice_types(
    practice_questions: list[Any],
    topic_scope_contract: dict[str, Any],
) -> list[str]:
    if not practice_questions:
        return []

    course_type = str(topic_scope_contract.get("course_type") or "").strip()
    expected_types_by_course = {
        "terminology_components": {
            "matching",
            "multiple_choice",
            "short_answer",
            "visual_labeling",
        },
        "process_walkthrough": {
            "short_answer",
            "multiple_choice",
            "ordering",
            "math",
            "math_input",
        },
        "algorithm_walkthrough": {
            "short_answer",
            "multiple_choice",
            "ordering",
            "visual_labeling",
            "trace",
        },
        "coding_implementation": {
            "coding",
            "coding_environment",
            "debugging",
            "short_answer",
        },
        "data_structure_operation": {
            "visual_labeling",
            "short_answer",
            "multiple_choice",
            "coding",
            "coding_environment",
            "trace",
        },
        "math_formula_method": {
            "math",
            "math_input",
            "multiple_choice",
            "short_answer",
        },
        "proof_reasoning": {
            "short_answer",
            "multiple_choice",
            "math",
            "math_input",
            "ordering",
        },
        "compare_distinguish": {
            "multiple_choice",
            "short_answer",
            "decision_scenario",
        },
        "problem_solving_pattern": {
            "short_answer",
            "multiple_choice",
            "coding",
            "coding_environment",
            "trace",
        },
        "problem_solving_application": {
            "short_answer",
            "multiple_choice",
            "coding",
            "coding_environment",
            "debugging",
            "trace",
            "math",
            "math_input",
        },
        "debugging_diagnosis": {
            "debugging",
            "multiple_choice",
            "short_answer",
            "coding",
            "coding_environment",
        },
        "design_decision": {
            "decision_scenario",
            "multiple_choice",
            "short_answer",
        },
        "terminology_vocabulary": {
            "matching",
            "multiple_choice",
            "short_answer",
        },
        "review_refresh": {
            "short_answer",
            "multiple_choice",
            "math",
            "math_input",
            "coding",
            "coding_environment",
        },
    }
    expected = expected_types_by_course.get(course_type)
    if not expected:
        return []

    actual = {
        str(question.get("question_type") or question.get("type") or "").strip()
        for question in practice_questions
        if isinstance(question, dict)
    }
    actual.discard("")
    if not actual:
        return [f"Practice questions for {course_type} do not specify question_type."]
    if actual.isdisjoint(expected):
        return [
            f"Practice question types {sorted(actual)} do not match {course_type}; expected one of {sorted(expected)}."
        ]
    return []


def validate_visual_scope(
    lesson_json: dict[str, Any],
    cards: list[Any],
    topic_scope_contract: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    must_not_teach = [
        str(item).strip().lower()
        for item in topic_scope_contract.get("must_not_teach", [])
        if str(item).strip()
    ]
    out_of_scope = [
        str(item).strip().lower()
        for item in topic_scope_contract.get("out_of_scope_content", [])
        if str(item).strip()
    ]
    visuals: list[tuple[str, Any]] = [
        ("top-level visual_plan", lesson_json.get("visual_plan") or []),
    ]
    for index, card in enumerate(cards):
        if isinstance(card, dict):
            visuals.append((f"card {index + 1} visual_plan", card.get("visual_plan") or {}))
            visuals.append((f"card {index + 1} styled_elements", card.get("styled_elements") or []))

    for label, visual in visuals:
        text = collect_any_text(visual)
        if not text:
            continue
        for phrase in must_not_teach + out_of_scope:
            if phrase and phrase in text:
                issues.append(f"{label} includes out-of-scope visual/styled content: {phrase}.")
    return issues
