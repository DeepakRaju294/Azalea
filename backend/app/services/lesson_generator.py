from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.course_blueprints import get_course_blueprint
from app.core.course_stage_rules import STAGE_RULES
from app.prompts.lesson_prompt import (
    CARD_BLUEPRINT_MAP,
    SYSTEM_PROMPT,
    build_course_blueprint_instruction,
    build_lesson_user_prompt,
)
from app.services.interactive_link_validation import validate_and_repair_interactive_links
from app.services.course_type_classifier import classify_topic_course_type
from app.services.knowledge_level_service import estimate_knowledge_level
from app.services.llm_client import generate_lesson_segment, generate_structured_lesson
from app.services.microcheck_validation import validate_and_repair_microchecks
from app.services.practice_quality import validate_and_repair_practice
from app.services.review_injection_service import maybe_inject_review_card
from app.services.scope_validator import (
    build_scope_retry_feedback,
    scope_report_score,
    validate_scope_adherence,
)
from app.services.topic_quality_validator import (
    build_quality_retry_feedback,
    quality_report_score,
    validate_generated_topic,
)
from app.services.topic_scope_service import build_topic_scope_contract
from app.services.visual_validation import validate_and_repair_lesson_visuals

if TYPE_CHECKING:
    from app.models.content_chunk import ContentChunk
    from app.models.topic import Topic


CORE_TEXT_ONLY_GENERATION_MODE = "text_only_core"


def build_source_chunk_ids(chunks: list[ContentChunk]) -> list[str]:
    return [str(chunk.id) for chunk in chunks]


def build_source_summary(chunks: list[ContentChunk]) -> str:
    if not chunks:
        return "No source chunks were used."

    summary_parts: list[str] = []

    for index, chunk in enumerate(chunks[:5]):
        material_title = "Uploaded material"
        material_filename = None

        if getattr(chunk, "material", None) is not None:
            material_title = (
                chunk.material.title
                or chunk.material.filename
                or "Uploaded material"
            )
            material_filename = chunk.material.filename

        filename_text = f" ({material_filename})" if material_filename else ""

        summary_parts.append(
            (
                f"Source {index + 1}: {material_title}{filename_text}, "
                f"chunk {chunk.chunk_index}, chunk_id {chunk.id}"
            )
        )

    return "\n".join(summary_parts)


def extract_prior_concept_states(lesson_json: dict[str, Any]) -> dict[str, str]:
    states: dict[str, str] = {}
    cards = lesson_json.get("lesson_cards")
    if not isinstance(cards, list):
        return states
    for card in cards:
        if not isinstance(card, dict):
            continue
        for support_item in card.get("concept_support") or []:
            if not isinstance(support_item, dict):
                continue
            concept = str(support_item.get("concept") or "").strip()
            state_hint = str(support_item.get("state_hint") or "").strip()
            if concept and state_hint:
                states.setdefault(concept, state_hint)
    return states


def build_lesson_from_topic_and_chunks(
    topic: Topic,
    chunks: list[ContentChunk],
    feedback: str | None = None,
    prior_concept_states: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    LLM-based Azalea lesson generator.

    Input:
    - Topic
    - Relevant chunks from uploaded class material
    - Optional adaptive instructions or regeneration feedback
    - Optional prior_concept_states: {concept: state_hint} from previous lesson cards

    Output:
    - lesson_json matching the frontend lesson renderer.
    """

    lesson_json = generate_and_finalize_lesson(
        topic=topic,
        chunks=chunks,
        feedback=feedback,
        prior_concept_states=prior_concept_states,
    )

    # Collect all validation failures from the initial generation and address
    # them in a single combined retry instead of three separate generation calls.
    retry_feedbacks: list[str] = []

    scope_report = lesson_json.get("scope_validation_report", {})
    if scope_report.get("requires_regeneration"):
        retry_feedbacks.append(build_scope_retry_feedback(scope_report))

    visual_report = lesson_json.get("visual_validation_report", {})
    if visual_report.get("requires_regeneration"):
        retry_feedbacks.append(build_visual_retry_feedback(visual_report))

    quality_report = lesson_json.get("topic_quality_report", {})
    if quality_report.get("requires_regeneration"):
        retry_feedbacks.append(build_quality_retry_feedback(quality_report))

    if retry_feedbacks:
        combined_retry_feedback = "\n\n---\n\n".join(retry_feedbacks)
        retry_lesson_json = generate_and_finalize_lesson(
            topic=topic,
            chunks=chunks,
            feedback=merge_feedback(feedback, combined_retry_feedback),
            prior_concept_states=prior_concept_states,
        )
        lesson_json = choose_best_overall_lesson(
            original_lesson=lesson_json,
            retry_lesson=retry_lesson_json,
        )

    if "adaptation_metadata" not in lesson_json:
        lesson_json["adaptation_metadata"] = {
            "starting_mode": "default",
            "estimated_state": "not_provided",
            "adaptation_summary": (
                "Azalea used the default lesson style for this topic."
            ),
            "teaching_strategy": "default",
        }

    sync_validation_report(lesson_json)
    return lesson_json


def generate_and_finalize_lesson(
    topic: Topic,
    chunks: list[ContentChunk],
    feedback: str | None = None,
    prior_concept_states: dict[str, str] | None = None,
) -> dict[str, Any]:
    ensure_topic_generation_metadata(topic=topic)
    topic_scope_contract = build_topic_scope_contract(topic=topic)
    topic_scope_contract["generation_mode"] = CORE_TEXT_ONLY_GENERATION_MODE
    apply_scope_contract_to_topic(topic=topic, topic_scope_contract=topic_scope_contract)

    user_prompt = build_lesson_user_prompt(
        topic=topic,
        chunks=chunks,
        feedback=feedback,
        prior_concept_states=prior_concept_states,
        topic_scope_contract=topic_scope_contract,
    )

    lesson_json = generate_structured_lesson(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    lesson_json["source_chunk_ids"] = build_source_chunk_ids(chunks)
    lesson_json["source_summary"] = build_source_summary(chunks)
    lesson_json["topic_scope_contract"] = topic_scope_contract
    lesson_json["generation_mode"] = CORE_TEXT_ONLY_GENERATION_MODE
    ensure_course_blueprint_metadata(lesson_json=lesson_json, topic=topic)

    ensure_lesson_orientation(lesson_json=lesson_json, topic=topic)
    ensure_lesson_cards(lesson_json=lesson_json, topic=topic)
    maybe_inject_review_card(lesson_json=lesson_json, topic=topic)
    strip_rich_card_interactions(lesson_json)
    validate_and_repair_practice(
        lesson_json=lesson_json,
        course_type=topic.course_type,
    )
    repair_practice_question_index_references(lesson_json)
    validate_generated_topic(
        lesson_json=lesson_json,
        course_type=topic.course_type,
    )
    validate_scope_adherence(
        lesson_json=lesson_json,
        topic_scope_contract=topic_scope_contract,
    )

    sync_validation_report(lesson_json)
    return lesson_json


def strip_rich_card_interactions(lesson_json: dict[str, Any]) -> None:
    """Keep generation in the text-only core mode while preserving schema shape."""

    lesson_json["visual_plan"] = []
    lesson_json["visual_validation_report"] = {
        "is_valid": True,
        "requires_regeneration": False,
        "issues": [],
        "mode": CORE_TEXT_ONLY_GENERATION_MODE,
    }
    lesson_json["microcheck_validation_report"] = {
        "is_valid": True,
        "requires_regeneration": False,
        "issues": [],
        "mode": CORE_TEXT_ONLY_GENERATION_MODE,
    }
    lesson_json["interactive_link_validation_report"] = {
        "is_valid": True,
        "requires_regeneration": False,
        "issues": [],
        "mode": CORE_TEXT_ONLY_GENERATION_MODE,
    }

    cards = lesson_json.get("lesson_cards")
    if not isinstance(cards, list):
        return

    for card in cards:
        if not isinstance(card, dict):
            continue
        card["interactive_links"] = []
        card["concept_support"] = []
        card["annotations"] = []
        card["visual_plan"] = normalize_card_visual_plan({})
        card["visual_index"] = -1
        card["micro_check"] = {"type": "", "prompt": "", "answer": ""}


def apply_scope_contract_to_topic(
    topic: Topic,
    topic_scope_contract: dict[str, Any],
) -> None:
    """Let a strict scope contract correct stale/broad topic metadata."""

    contract_course_type = str(topic_scope_contract.get("course_type") or "").strip()
    if contract_course_type:
        try:
            topic.course_type = contract_course_type
        except Exception:
            pass

    contract_secondary = topic_scope_contract.get("secondary_course_types")
    if isinstance(contract_secondary, list):
        try:
            topic.secondary_course_types = [
                str(item).strip()
                for item in contract_secondary
                if str(item).strip()
            ]
        except Exception:
            pass


def ensure_topic_generation_metadata(topic: Topic) -> None:
    """Fill missing topic metadata before selecting scope and blueprint."""

    needs_classification = (
        not getattr(topic, "course_type", None)
        or not isinstance(getattr(topic, "secondary_course_types", None), list)
    )

    classification: dict[str, Any] = {}
    if needs_classification:
        classification = classify_topic_course_type(
            user_goal=getattr(topic, "purpose", None) or getattr(topic, "title", None),
            topic_title=str(getattr(topic, "title", "") or ""),
            topic_purpose=getattr(topic, "purpose", None),
            source_summary=getattr(topic, "source_refs", None),
        )

    if not getattr(topic, "course_type", None):
        try:
            topic.course_type = classification.get("primary_course_type") or "concept_intuition"
        except Exception:
            pass

    if not isinstance(getattr(topic, "secondary_course_types", None), list):
        try:
            topic.secondary_course_types = list(classification.get("secondary_course_types") or [])
        except Exception:
            pass

    if not getattr(topic, "knowledge_level", None):
        try:
            topic.knowledge_level = int(
                classification.get("knowledge_level")
                or estimate_knowledge_level(
                    user_goal=getattr(topic, "purpose", None) or getattr(topic, "title", None),
                    topic_title=getattr(topic, "title", None),
                )
            )
        except Exception:
            pass


def merge_feedback(
    original_feedback: str | None,
    retry_feedback: str,
) -> str:
    if original_feedback and original_feedback.strip():
        return f"{original_feedback.strip()}\n\n{retry_feedback.strip()}"
    return retry_feedback.strip()


def sync_validation_report(lesson_json: dict[str, Any]) -> None:
    """Expose one stable validation summary while preserving detailed reports."""

    report_names = (
        "scope_validation_report",
        "visual_validation_report",
        "topic_quality_report",
    )
    reports = {
        name: lesson_json.get(name)
        for name in report_names
        if isinstance(lesson_json.get(name), dict)
    }

    issues: list[dict[str, Any]] = []
    requires_regeneration = False
    passed = True

    for report_name, report in reports.items():
        if report.get("requires_regeneration"):
            requires_regeneration = True
        if report.get("passed") is False:
            passed = False

        raw_issues = report.get("issues")
        if not isinstance(raw_issues, list):
            continue
        for issue in raw_issues:
            issues.append(normalize_validation_issue(report_name, issue))

    if issues:
        passed = False

    lesson_json["validation_reports"] = reports
    lesson_json["validation_report"] = {
        "passed": passed,
        "issues": issues,
        "auto_fix_suggestions": build_validation_suggestions(reports),
        "requires_regeneration": requires_regeneration,
    }


def normalize_validation_issue(
    report_name: str,
    issue: Any,
) -> dict[str, Any]:
    source_code = report_name.replace("_validation_report", "")
    if isinstance(issue, dict):
        message = str(issue.get("message") or issue.get("code") or issue).strip()
        severity = str(issue.get("severity") or "warning").strip()
        code = str(issue.get("code") or source_code).strip()
        return {
            "severity": severity if severity in {"info", "warning", "error"} else "warning",
            "code": code,
            "message": message,
            "card_id": issue.get("card_id"),
            "auto_fixable": bool(issue.get("auto_fixable", False)),
        }

    return {
        "severity": "warning",
        "code": source_code,
        "message": str(issue).strip(),
        "card_id": None,
        "auto_fixable": False,
    }


def build_validation_suggestions(
    reports: dict[str, dict[str, Any]],
) -> list[str]:
    suggestions: list[str] = []
    if reports.get("scope_validation_report", {}).get("issues"):
        suggestions.append("Regenerate inside the TopicScopeContract.")
    if reports.get("visual_validation_report", {}).get("issues"):
        suggestions.append("Repair blank or unsupported visual/styled elements.")
    if reports.get("topic_quality_report", {}).get("issues"):
        suggestions.append("Regenerate missing blueprint, microcheck, or practice coverage.")
    return suggestions


def build_visual_retry_feedback(validation_report: dict[str, Any]) -> str:
    issues = validation_report.get("issues")
    if not isinstance(issues, list):
        issues = []

    issue_text = "\n".join(f"- {issue}" for issue in issues[:8])

    return f"""
VISUAL REGENERATION REQUIRED

The previous generated lesson had visual objects that would render blank or violate Azalea's visual rules.

Specific issues:
{issue_text or "- Visual validation requested a retry."}

Regenerate the lesson with these fixes:
- If using a graph visual, include at least 10 concrete data_points as [x, y] pairs and meaningful axis labels.
- If using a node_link_diagram, include concrete nodes with id, label, x, y and edges with from/to.
- If using a circuit_diagram, include concrete components and wires.
- Do not put formulas, equations, tables, comparison grids, concept maps, or checklist content in visual_plan.
- Put equations in LaTeX inside lesson card text.
- If you cannot create a complete renderable visual, remove that visual and teach with a concrete example or styled lesson card instead.
- Do not emit visual placeholders that only contain title, type, purpose, or empty arrays.
""".strip()


def choose_best_overall_lesson(
    original_lesson: dict[str, Any],
    retry_lesson: dict[str, Any],
) -> dict[str, Any]:
    original_score = (
        scope_report_score(original_lesson.get("scope_validation_report", {}))
        + visual_report_score(original_lesson.get("visual_validation_report", {}))
        + quality_report_score(original_lesson.get("topic_quality_report", {}))
    )
    retry_score = (
        scope_report_score(retry_lesson.get("scope_validation_report", {}))
        + visual_report_score(retry_lesson.get("visual_validation_report", {}))
        + quality_report_score(retry_lesson.get("topic_quality_report", {}))
    )
    selected = retry_lesson if retry_score >= original_score else original_lesson
    for report_key in ("scope_validation_report", "visual_validation_report", "topic_quality_report"):
        report = selected.get(report_key)
        if isinstance(report, dict):
            report["retry_attempted"] = True
            report["retry_selected"] = selected is retry_lesson
    return selected


def choose_best_visual_lesson(
    original_lesson: dict[str, Any],
    retry_lesson: dict[str, Any],
) -> dict[str, Any]:
    original_report = original_lesson.get("visual_validation_report", {})
    retry_report = retry_lesson.get("visual_validation_report", {})

    original_score = visual_report_score(original_report)
    retry_score = visual_report_score(retry_report)

    selected = retry_lesson if retry_score >= original_score else original_lesson
    selected_report = selected.get("visual_validation_report")
    if isinstance(selected_report, dict):
        selected_report["retry_attempted"] = True
        selected_report["retry_selected"] = selected is retry_lesson
        selected_report["original_issue_count"] = len(
            original_report.get("issues", [])
            if isinstance(original_report.get("issues"), list)
            else []
        )
        selected_report["retry_issue_count"] = len(
            retry_report.get("issues", [])
            if isinstance(retry_report.get("issues"), list)
            else []
        )

    return selected


def choose_best_quality_lesson(
    original_lesson: dict[str, Any],
    retry_lesson: dict[str, Any],
) -> dict[str, Any]:
    original_report = original_lesson.get("topic_quality_report", {})
    retry_report = retry_lesson.get("topic_quality_report", {})

    original_score = quality_report_score(original_report)
    retry_score = quality_report_score(retry_report)

    selected = retry_lesson if retry_score >= original_score else original_lesson
    selected_report = selected.get("topic_quality_report")
    if isinstance(selected_report, dict):
        selected_report["retry_attempted"] = True
        selected_report["retry_selected"] = selected is retry_lesson
        selected_report["original_score"] = original_score
        selected_report["retry_score"] = retry_score

    return selected


def choose_best_scope_lesson(
    original_lesson: dict[str, Any],
    retry_lesson: dict[str, Any],
) -> dict[str, Any]:
    original_report = original_lesson.get("scope_validation_report", {})
    retry_report = retry_lesson.get("scope_validation_report", {})

    original_score = scope_report_score(original_report)
    retry_score = scope_report_score(retry_report)

    selected = retry_lesson if retry_score >= original_score else original_lesson
    selected_report = selected.get("scope_validation_report")
    if isinstance(selected_report, dict):
        selected_report["retry_attempted"] = True
        selected_report["retry_selected"] = selected is retry_lesson
        selected_report["original_score"] = original_score
        selected_report["retry_score"] = retry_score

    return selected


def visual_report_score(report: dict[str, Any]) -> int:
    issues = report.get("issues", [])
    issue_count = len(issues) if isinstance(issues, list) else 0
    removed_count = int(report.get("removed_visual_count") or 0)
    repaired_count = int(report.get("repaired_card_count") or 0)
    requires_regeneration = bool(report.get("requires_regeneration"))

    score = 100
    score -= issue_count * 8
    score -= removed_count * 12
    score -= repaired_count * 4
    if requires_regeneration:
        score -= 30
    return score


def repair_practice_question_index_references(lesson_json: dict[str, Any]) -> None:
    cards = lesson_json.get("lesson_cards")
    questions = lesson_json.get("practice_questions")
    if not isinstance(cards, list) or not isinstance(questions, list):
        return

    valid_count = len(questions)
    for card in cards:
        if not isinstance(card, dict):
            continue
        index = card.get("practice_question_index")
        if isinstance(index, int) and index >= valid_count:
            card["practice_question_index"] = -1


def ensure_course_blueprint_metadata(lesson_json: dict[str, Any], topic: Topic) -> None:
    course_type = topic.course_type or "concept_intuition"
    secondary_course_types = topic.secondary_course_types or []
    knowledge_level = topic.knowledge_level
    blueprint = get_course_blueprint(course_type)

    lesson_json["course_type"] = course_type
    lesson_json["secondary_course_types"] = secondary_course_types
    lesson_json["knowledge_level"] = knowledge_level
    lesson_json["blueprint_card_sequence"] = get_lesson_blueprint_card_sequence(
        lesson_json=lesson_json,
        blueprint=blueprint,
    )

    adaptation_metadata = lesson_json.get("adaptation_metadata")
    if not isinstance(adaptation_metadata, dict):
        adaptation_metadata = {}

    teaching_strategy = adaptation_metadata.get("teaching_strategy")
    if not teaching_strategy or teaching_strategy == "default":
        adaptation_metadata["teaching_strategy"] = (
            f"{blueprint.get('name', course_type)}; "
            f"Level {knowledge_level or 'not resolved'}"
        )

    adaptation_metadata.setdefault("starting_mode", "default")
    adaptation_metadata.setdefault("estimated_state", "not_provided")
    adaptation_metadata.setdefault(
        "adaptation_summary",
        "Azalea selected the lesson structure from the topic's course type and knowledge level.",
    )

    lesson_json["adaptation_metadata"] = adaptation_metadata


def get_lesson_blueprint_card_sequence(
    lesson_json: dict[str, Any],
    blueprint: dict[str, Any],
) -> list[str]:
    scope_contract = lesson_json.get("topic_scope_contract")
    if isinstance(scope_contract, dict):
        allowed_sequence = [
            str(item).strip()
            for item in scope_contract.get("allowed_card_sequence", [])
            if str(item).strip()
        ]
        if allowed_sequence:
            return allowed_sequence

    return list(blueprint.get("default_card_sequence") or [])


def ensure_lesson_orientation(lesson_json: dict[str, Any], topic: Topic) -> None:
    topic_title = topic.title or "this topic"
    topic_purpose = topic.purpose or f"Understand why {topic_title} matters in this study path."

    lesson_json["intro"] = clean_orientation_text(
        lesson_json.get("intro"),
        f"You are learning {topic_title}.",
    )
    lesson_json["purpose"] = clean_orientation_text(
        lesson_json.get("purpose"),
        topic_purpose,
    )
    lesson_json["context"] = clean_orientation_text(
        lesson_json.get("context"),
        build_fallback_context(topic),
    )
    lesson_json["learning_objective"] = clean_orientation_text(
        lesson_json.get("learning_objective"),
        f"By the end, you should be able to explain and apply {topic_title}.",
    )

    if not isinstance(lesson_json.get("key_takeaways"), list) or not lesson_json["key_takeaways"]:
        lesson_json["key_takeaways"] = [
            f"{topic_title} matters because: {topic_purpose}",
            lesson_json["learning_objective"],
        ]

    lesson_json["concepts"] = normalize_string_list(
        lesson_json.get("concepts") or lesson_json.get("components")
    )[:20]

    practice_questions = lesson_json.get("practice_questions")
    if isinstance(practice_questions, list):
        for question in practice_questions:
            if not isinstance(question, dict):
                continue

            question_text = clean_orientation_text(
                question.get("question_text"),
                f"Explain the main idea of {topic_title}.",
            )
            concept_tested = clean_orientation_text(
                question.get("concept_tested"),
                question.get("skill_target") or topic_title,
            )
            related_section = clean_orientation_text(
                question.get("related_section"),
                infer_related_section(question),
            )

            question["question_text"] = question_text
            question["concept_tested"] = concept_tested
            question["related_section"] = related_section
            question["why_this_matters"] = clean_orientation_text(
                question.get("why_this_matters"),
                f"This checks whether you can use {concept_tested} while learning {topic_title}.",
            )


def ensure_lesson_cards(lesson_json: dict[str, Any], topic: Topic) -> None:
    cards = lesson_json.get("lesson_cards")

    if isinstance(cards, list) and cards:
        normalized_cards: list[dict[str, Any]] = []

        for index, card in enumerate(cards):
            if not isinstance(card, dict):
                continue

            normalized_cards.append(normalize_lesson_card(card, index, topic))

        if normalized_cards:
            lesson_json["lesson_cards"] = split_dense_cards(normalized_cards, topic)
            return

    lesson_json["lesson_cards"] = split_dense_cards(
        build_fallback_lesson_cards(lesson_json, topic),
        topic,
    )


def normalize_lesson_card(
    card: dict[str, Any],
    index: int,
    topic: Topic,
) -> dict[str, Any]:
    topic_title = topic.title or "this topic"
    card_type = clean_orientation_text(card.get("card_type"), "core_idea")
    points = normalize_card_points(
        card.get("points")
        or card.get("bullets")
        or card.get("body")
    )
    visual_plan = normalize_card_visual_plan(card.get("visual_plan"))
    annotations = normalize_annotations(card.get("annotations"))
    example = clean_orientation_text(card.get("example"), "")
    micro_check = normalize_micro_check(card.get("micro_check"))
    deeper_explanation = clean_orientation_text(card.get("deeper_explanation"), "")
    what_to_notice = clean_orientation_text(
        card.get("what_to_notice"),
        build_default_notice(card_type, points),
    )
    next_transition = clean_orientation_text(
        card.get("next_transition") or card.get("transition_text"),
        build_default_transition(card_type),
    )

    normalized = {
        "id": clean_orientation_text(card.get("id"), f"card-{index + 1}"),
        "blueprint_key": clean_orientation_text(card.get("blueprint_key"), ""),
        "card_type": card_type,
        "title": clean_orientation_text(card.get("title"), topic_title),
        "body": normalize_string_list(card.get("body"))[:2],
        "bullets": normalize_string_list(card.get("bullets"))[:4],
        "points": points,
        "main_concept": clean_orientation_text(
            card.get("main_concept"),
            infer_card_main_concept(card, topic_title),
        ),
        "new_concepts": normalize_string_list(card.get("new_concepts"))[:8],
        "review_concepts": normalize_string_list(card.get("review_concepts"))[:8],
        "prerequisite_concepts": normalize_string_list(
            card.get("prerequisite_concepts")
        )[:8],
        "related_formulas": normalize_string_list(card.get("related_formulas"))[:6],
        "related_symbols": normalize_string_list(card.get("related_symbols"))[:12],
        "common_misconceptions": normalize_string_list(
            card.get("common_misconceptions")
        )[:6],
        "concept_support": normalize_concept_support(card.get("concept_support")),
        "interactive_links": normalize_interactive_links(card.get("interactive_links")),
        "styled_elements": normalize_styled_elements(card.get("styled_elements")),
        "visual_plan": visual_plan,
        "annotations": annotations,
        "example": example,
        "micro_check": micro_check,
        "deeper_explanation": deeper_explanation,
        "what_to_notice": what_to_notice,
        "next_transition": next_transition,
        "estimated_seconds": clamp_card_seconds(card.get("estimated_seconds")),
        "transition_text": clean_orientation_text(
            card.get("transition_text"),
            next_transition,
        ),
        "next_card_label": clean_orientation_text(
            card.get("next_card_label"),
            build_default_next_label(card_type),
        ),
        "practice_question_index": normalize_index(card.get("practice_question_index")),
        "visual_index": normalize_index(card.get("visual_index")),
    }
    normalized["quality_score"] = score_card_quality(normalized)
    return normalized


def build_fallback_lesson_cards(
    lesson_json: dict[str, Any],
    topic: Topic,
) -> list[dict[str, Any]]:
    scope_contract = lesson_json.get("topic_scope_contract")
    if isinstance(scope_contract, dict):
        allowed_sequence = [
            str(item).strip()
            for item in scope_contract.get("allowed_card_sequence", [])
            if str(item).strip()
        ]
        if allowed_sequence:
            return build_blueprint_fallback_lesson_cards(
                allowed_sequence=allowed_sequence,
                topic=topic,
            )

    topic_title = topic.title or "this topic"
    cards: list[dict[str, Any]] = []

    cards.append(
        build_lesson_card(
            index=len(cards),
            card_type="micro_check",
            title="Starting point check",
            body=[
                clean_orientation_text(
                    lesson_json.get("intro"),
                    f"You are learning {topic_title}.",
                )
            ],
            bullets=[],
            transition_text="Now that the starting point is clear, the next step is why it matters.",
            next_card_label="Show why it matters",
        )
    )

    cards.append(
        build_lesson_card(
            index=len(cards),
            card_type="purpose_context",
            title="Why this topic matters",
            body=[
                clean_orientation_text(
                    lesson_json.get("purpose"),
                    topic.purpose or f"Understand why {topic_title} matters.",
                ),
                clean_orientation_text(
                    lesson_json.get("context"),
                    build_fallback_context(topic),
                ),
            ],
            bullets=[
                clean_orientation_text(
                    lesson_json.get("learning_objective"),
                    f"By the end, you should be able to explain and apply {topic_title}.",
                )
            ],
            transition_text="This gives the reason; now we need the pieces.",
            next_card_label="Show me the pieces",
        )
    )

    cards.append(
        build_lesson_card(
            index=len(cards),
            card_type="intuition",
            title="Big-picture intuition",
            body=[
                clean_orientation_text(
                    lesson_json.get("learning_objective"),
                    f"Build a working mental model for {topic_title} before details.",
                )
            ],
            bullets=[],
            transition_text="The intuition gives the shape; now name the components.",
            next_card_label="Show the vocabulary",
        )
    )

    add_list_cards(
        cards=cards,
        items=normalize_string_list(lesson_json.get("components")),
        card_type="definition",
        title="Core vocabulary / components",
        transition_text="Once the pieces are clear, the method becomes easier to follow.",
        next_card_label="Show me the method",
    )

    add_list_cards(
        cards=cards,
        items=normalize_string_list(lesson_json.get("process")),
        card_type="method_process",
        title="How the idea works",
        transition_text="You have the steps; now it helps to see them in action.",
        next_card_label="Try an example",
    )

    worked_examples = lesson_json.get("worked_examples")
    if isinstance(worked_examples, list):
        for example in worked_examples:
            if not isinstance(example, dict):
                continue

            cards.append(
                build_lesson_card(
                    index=len(cards),
                    card_type="worked_example",
                    title=clean_orientation_text(
                        example.get("title"),
                        "Visual or concrete example",
                    ),
                    body=normalize_string_list(example.get("steps"))[:3],
                    bullets=normalize_string_list(example.get("steps"))[3:],
                    transition_text="You have seen the normal case; now look for the tricky part.",
                    next_card_label="Show the tricky case",
                )
            )

    add_list_cards(
        cards=cards,
        items=normalize_string_list(lesson_json.get("edge_cases"))
        or normalize_string_list(lesson_json.get("limitations")),
        card_type="edge_case",
        title="Common mistakes / edge cases",
        transition_text="That is the main trap; now do a quick check.",
        next_card_label="Do a quick check",
    )

    practice_questions = lesson_json.get("practice_questions")
    if isinstance(practice_questions, list):
        for index, question in enumerate(practice_questions[:3]):
            if not isinstance(question, dict):
                continue

            cards.append(
                build_lesson_card(
                    index=len(cards),
                    card_type="quick_practice",
                    title="Guided practice" if index == 0 else "Real problem/application",
                    body=[
                        clean_orientation_text(
                            question.get("why_this_matters"),
                            "This checks the idea before you move on.",
                        )
                    ],
                    bullets=[],
                    estimated_seconds=35,
                    transition_text="Use this check to confirm the idea, then keep moving.",
                    next_card_label="Check my answer",
                    practice_question_index=index,
                )
            )

            if index == 0:
                cards.append(
                    build_lesson_card(
                        index=len(cards),
                        card_type="micro_check",
                        title="Adaptive follow-up",
                        body=[
                            "If the last check felt shaky, revisit the edge case before continuing."
                        ],
                        bullets=[],
                        estimated_seconds=25,
                        transition_text="Use that signal to choose whether you need one more application.",
                        next_card_label="Try the application",
                    )
                )

    if not any(card.get("title") == "Guided practice" for card in cards):
        cards.append(
            build_lesson_card(
                index=len(cards),
                card_type="quick_practice",
                title="Guided practice",
                body=[f"Apply the central rule of {topic_title} to a concrete case."],
                bullets=[],
                estimated_seconds=35,
                transition_text="Use this check to confirm the idea, then adapt if needed.",
                next_card_label="Check my answer",
            )
        )
        cards.append(
            build_lesson_card(
                index=len(cards),
                card_type="micro_check",
                title="Adaptive follow-up",
                body=["If the guided practice felt shaky, review the weakest component first."],
                bullets=[],
                estimated_seconds=25,
                transition_text="Now apply the idea in a more realistic setting.",
                next_card_label="Try the application",
            )
        )
        cards.append(
            build_lesson_card(
                index=len(cards),
                card_type="example",
                title="Real problem/application",
                body=[f"Use {topic_title} in a realistic application and check the edge case."],
                bullets=[],
                transition_text="The application gives context; now compress the mental model.",
                next_card_label="Summarize the model",
            )
        )

    add_list_cards(
        cards=cards,
        items=normalize_string_list(lesson_json.get("key_takeaways")),
        card_type="summary",
        title="Summary / mental model",
        transition_text="The mental model is in place; finish by deciding what to review later.",
        next_card_label="Show review recommendation",
    )

    cards.append(
        build_lesson_card(
            index=len(cards),
            card_type="micro_check",
            title="Mastery check",
            body=[
                f"Explain when {topic_title} works well and when its assumptions break."
            ],
            bullets=[],
            estimated_seconds=30,
            transition_text="This checks whether the mental model transfers.",
            next_card_label="Show review recommendation",
        )
    )

    cards.append(
        build_lesson_card(
            index=len(cards),
            card_type="bridge_to_next_topic",
            title="Review-later recommendation",
            body=[
                f"Review {topic_title} later by redoing the hardest edge case without notes."
            ],
            bullets=[],
            transition_text="This closes the topic and prepares the next one.",
            next_card_label="Continue to next topic",
        )
    )

    return cards


def build_blueprint_fallback_lesson_cards(
    allowed_sequence: list[str],
    topic: Topic,
) -> list[dict[str, Any]]:
    topic_title = topic.title or "this topic"
    course_type = topic.course_type or "concept_intuition"
    stage_rules = STAGE_RULES.get(course_type, {})
    cards: list[dict[str, Any]] = []

    for card_key in allowed_sequence:
        title, card_type = CARD_BLUEPRINT_MAP.get(
            card_key,
            (card_key.replace("_", " ").title(), "core_idea"),
        )
        rule = stage_rules.get(card_key, {})
        content_items = list(rule.get("content") or [])
        body = [
            f"This card focuses on {title.lower()} for {topic_title}."
        ]
        bullets = [
            item if len(item.split()) >= 6 else f"Use this to understand {item}."
            for item in content_items[:3]
        ]
        card = build_lesson_card(
            index=len(cards),
            card_type=card_type,
            title=title,
            body=body,
            bullets=bullets,
            transition_text=f"Next, continue through the scoped {topic_title} sequence.",
            next_card_label="Continue",
            practice_question_index=(0 if card_key == "practice" else -1),
        )
        card["blueprint_key"] = card_key
        card["main_concept"] = f"{title} for {topic_title}"
        card["new_concepts"] = [topic_title] if len(cards) == 0 else []
        cards.append(card)

    return cards


def build_lesson_card(
    index: int,
    card_type: str,
    title: str,
    body: list[str],
    bullets: list[str],
    transition_text: str,
    next_card_label: str,
    estimated_seconds: int = 45,
    practice_question_index: int = -1,
    visual_index: int = -1,
) -> dict[str, Any]:
    return {
        "id": f"card-{index + 1}",
        "card_type": card_type,
        "title": title,
        "body": body[:3],
        "bullets": bullets[:5],
        "points": normalize_card_points([*body, *bullets]),
        "main_concept": title,
        "new_concepts": [title] if card_type in {"core_idea", "definition", "formula"} else [],
        "review_concepts": [],
        "prerequisite_concepts": [],
        "related_formulas": [],
        "related_symbols": [],
        "common_misconceptions": [],
        "concept_support": [],
        "interactive_links": [],
        "styled_elements": [],
        "visual_plan": {},
        "annotations": [],
        "example": "",
        "micro_check": {
            "type": "short_answer" if card_type == "quick_practice" else "",
            "prompt": body[0] if card_type == "quick_practice" and body else "",
            "answer": "",
        },
        "deeper_explanation": "",
        "what_to_notice": build_default_notice(card_type, [*body, *bullets]),
        "next_transition": transition_text,
        "quality_score": 0,
        "estimated_seconds": estimated_seconds,
        "transition_text": transition_text,
        "next_card_label": next_card_label,
        "practice_question_index": practice_question_index,
        "visual_index": visual_index,
    }


def add_list_cards(
    cards: list[dict[str, Any]],
    items: list[str],
    card_type: str,
    title: str,
    transition_text: str,
    next_card_label: str,
) -> None:
    for index in range(0, len(items), 3):
        chunk = items[index : index + 3]

        cards.append(
            build_lesson_card(
                index=len(cards),
                card_type=card_type,
                title=title if index == 0 else f"{title}, continued",
                body=[chunk[0]] if chunk else [],
                bullets=chunk[1:],
                transition_text=transition_text,
                next_card_label=next_card_label,
            )
        )


def normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str) and value.strip():
        return [value.strip()]

    return []


def normalize_concept_support(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    allowed_states = {"unknown", "familiar", "fragile", "stable", "transferable"}
    allowed_support = {
        "main_explain",
        "short_reminder",
        "repair",
        "hover_only",
        "skip",
    }
    normalized: list[dict[str, str]] = []

    for item in value:
        if not isinstance(item, dict):
            continue

        concept = clean_orientation_text(item.get("concept"), "")
        if not concept:
            continue

        state_hint = clean_orientation_text(item.get("state_hint"), "unknown").lower()
        support = clean_orientation_text(item.get("support"), "main_explain").lower()

        normalized.append(
            {
                "concept": concept[:120],
                "state_hint": state_hint if state_hint in allowed_states else "unknown",
                "support": support if support in allowed_support else "main_explain",
                "hover_explanation": clean_orientation_text(
                    item.get("hover_explanation"),
                    f"{concept} matters for this card.",
                )[:500],
            }
        )

    return normalized[:10]


def normalize_interactive_links(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    allowed_actions = {
        "popup_only",
        "open_study_path",
        "review_earlier_topic",
        "ask_question",
    }
    normalized: list[dict[str, str]] = []

    for item in value:
        if not isinstance(item, dict):
            continue

        text = clean_orientation_text(item.get("text"), "")
        explanation = clean_orientation_text(item.get("explanation"), "")
        if not text or not explanation:
            continue

        action = clean_orientation_text(item.get("action"), "popup_only")
        normalized.append(
            {
                "text": text[:120],
                "explanation": explanation[:500],
                "why_it_matters_here": clean_orientation_text(
                    item.get("why_it_matters_here"),
                    "",
                )[:400],
                "action": action if action in allowed_actions else "popup_only",
                "target": clean_orientation_text(item.get("target"), "")[:180],
            }
        )

    return normalized[:6]


def normalize_styled_elements(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    allowed_types = {
        "table",
        "comparison",
        "comparison_table",
        "checklist",
        "timeline",
        "formula_steps",
        "proof_skeleton",
        "decision_matrix",
        "workflow_map",
        "glossary_table",
        "input_output_table",
        "stage_map",
        "term_map",
        "code_trace",
    }
    normalized: list[dict[str, Any]] = []

    for item in value:
        if not isinstance(item, dict):
            continue

        element_type = clean_orientation_text(item.get("type"), "").lower()
        if element_type == "code_block":
            element_type = "code_trace"
        if element_type not in allowed_types:
            continue

        data = item.get("data")
        if not isinstance(data, dict):
            data = {}

        normalized.append(
            {
                "type": element_type,
                "title": clean_orientation_text(item.get("title"), "")[:160],
                "data": normalize_styled_element_data(data),
            }
        )

    return normalized[:4]


def normalize_styled_element_data(data: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}

    for key, value in data.items():
        safe_key = clean_orientation_text(key, "")[:80]
        if not safe_key:
            continue

        if isinstance(value, str):
            normalized[safe_key] = value[:4000]
        elif isinstance(value, (int, float, bool)) or value is None:
            normalized[safe_key] = value
        elif isinstance(value, list):
            normalized[safe_key] = normalize_styled_element_list(value)
        elif isinstance(value, dict):
            nested: dict[str, Any] = {}
            for nested_key, nested_value in list(value.items())[:20]:
                safe_nested_key = clean_orientation_text(nested_key, "")[:80]
                if not safe_nested_key:
                    continue
                if isinstance(nested_value, str):
                    nested[safe_nested_key] = nested_value[:1000]
                elif isinstance(nested_value, (int, float, bool)) or nested_value is None:
                    nested[safe_nested_key] = nested_value
            normalized[safe_key] = nested

    return normalized


def normalize_styled_element_list(value: list[Any]) -> list[Any]:
    normalized: list[Any] = []
    for item in value[:30]:
        if isinstance(item, str):
            normalized.append(item[:1000])
        elif isinstance(item, (int, float, bool)) or item is None:
            normalized.append(item)
        elif isinstance(item, list):
            normalized.append([str(cell)[:500] for cell in item[:12]])
        elif isinstance(item, dict):
            row: dict[str, Any] = {}
            for key, nested_value in list(item.items())[:12]:
                safe_key = clean_orientation_text(key, "")[:80]
                if safe_key:
                    row[safe_key] = str(nested_value)[:1000]
            normalized.append(row)
    return normalized


def infer_card_main_concept(card: dict[str, Any], topic_title: str) -> str:
    for key in ("title", "card_type"):
        value = clean_orientation_text(card.get(key), "")
        if value:
            return value
    return topic_title


def normalize_card_points(value: Any) -> list[str]:
    points = normalize_string_list(value)
    cleaned: list[str] = []

    for point in points:
        sentences = [
            part.strip()
            for part in point.replace(";", ".").split(".")
            if part.strip()
        ]
        cleaned.extend(sentences or [point])

    return [shorten_point(point) for point in cleaned[:4]]


def shorten_point(point: str) -> str:
    words = point.split()

    if len(words) <= 16:
        return point

    return " ".join(words[:16]).rstrip(",;:") + "..."


def normalize_annotations(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    annotations: list[dict[str, str]] = []

    for item in value[:4]:
        if not isinstance(item, dict):
            continue

        label = clean_orientation_text(item.get("label"), "")
        explanation = clean_orientation_text(item.get("explanation"), "")

        if label or explanation:
            annotations.append({"label": label, "explanation": explanation})

    return annotations


def normalize_micro_check(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"type": "", "prompt": "", "answer": ""}

    return {
        "type": clean_orientation_text(value.get("type"), ""),
        "prompt": clean_orientation_text(value.get("prompt"), ""),
        "answer": clean_orientation_text(value.get("answer"), ""),
    }


def normalize_card_visual_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    kind = clean_orientation_text(value.get("kind") or value.get("type"), "")
    visual_type = clean_orientation_text(value.get("type") or value.get("kind"), "")
    title = clean_orientation_text(value.get("title"), "")
    description = clean_orientation_text(
        value.get("description") or value.get("purpose"),
        "",
    )
    elements = normalize_string_list(value.get("elements"))[:8]
    highlight = clean_orientation_text(value.get("highlight"), "")
    purpose = clean_orientation_text(value.get("purpose") or description, "")
    placement = clean_orientation_text(value.get("placement"), "")
    columns = normalize_string_list(value.get("columns"))[:8]
    rows = normalize_table_rows(value.get("rows"))[:12]
    steps = normalize_visual_steps(value.get("steps"))[:10]
    formula = clean_orientation_text(value.get("formula"), "")
    symbols = normalize_visual_symbols(value.get("symbols"))[:12]
    when_to_use = clean_orientation_text(value.get("when_to_use"), "")
    common_mistake = clean_orientation_text(value.get("common_mistake"), "")
    center = clean_orientation_text(value.get("center"), "")
    nodes = normalize_visual_nodes(value.get("nodes"))[:9]
    edges = normalize_visual_edges(value.get("edges"))[:16]
    traversal_path = normalize_string_list(value.get("traversal_path"))[:16]
    components = normalize_visual_components(value.get("components"))[:12]
    wires = normalize_visual_edges(value.get("wires"))[:16]
    x_label = clean_orientation_text(value.get("x_label"), "")
    y_label = clean_orientation_text(value.get("y_label"), "")
    data_points = normalize_graph_points(value.get("data_points"))[:24]
    key_points = normalize_key_points(value.get("key_points"))[:8]
    what_to_notice = clean_orientation_text(value.get("what_to_notice"), "")
    code = clean_orientation_text(value.get("code"), "")
    language = clean_orientation_text(value.get("language"), "")
    highlight_row = normalize_index(value.get("highlight_row"))
    wrong = clean_orientation_text(value.get("wrong"), "")
    correct = clean_orientation_text(value.get("correct"), "")
    wrong_label = clean_orientation_text(value.get("wrong_label"), "")
    correct_label = clean_orientation_text(value.get("correct_label"), "")
    why = clean_orientation_text(value.get("why"), "")
    counterexample = clean_orientation_text(value.get("counterexample"), "")
    # interactive_change fields
    interactive_parameter = normalize_interactive_parameter(value.get("interactive_parameter"))
    # spatial_geometric fields
    spatial_diagram = normalize_spatial_diagram(value.get("spatial_diagram"))
    labels = []

    if isinstance(value.get("labels"), list):
        for item in value["labels"][:4]:
            if not isinstance(item, dict):
                continue

            target = clean_orientation_text(item.get("target"), "")
            text = clean_orientation_text(
                item.get("text") or item.get("explanation"),
                "",
            )

            if target or text:
                labels.append({"target": target, "text": text})

    # Suppress complex visual stubs: the AI emits required-but-empty arrays for complex
    # visual types (node_link_diagram, graph, circuit_diagram) when the real data lives in
    # the top-level visual_plan[] and the card is supposed to reference it via visual_index.
    # Returning {} here prevents a VisualFallbackCard (title + purpose text) from rendering
    # in place of the actual diagram. The card's visual_index path still works correctly.
    type_lower = visual_type.lower()
    node_link_type = any(x in type_lower for x in (
        "node_link", "tree_diagram", "binary_tree", "bst_diagram",
        "graph_diagram", "linked_node", "traversal_diagram",
    ))
    graph_type = type_lower in ("graph", "chart") or any(x in type_lower for x in (
        "graph_chart", "line_graph", "scatter", "bar_chart", "histogram",
        "distribution", "curve", "plot", "growth_rate", "area_under_curve",
        "runtime_growth", "loss_curve", "supply_demand",
    ))
    circuit_type = any(x in type_lower for x in (
        "circuit", "logic_gate", "digital_logic", "hardware_diagram", "schematic",
    ))
    if node_link_type and not nodes:
        return {}
    if graph_type and not data_points:
        return {}
    if circuit_type and not components and not wires:
        return {}

    if not any([
        kind,
        visual_type,
        title,
        description,
        purpose,
        placement,
        elements,
        highlight,
        labels,
        columns,
        rows,
        steps,
        formula,
        symbols,
        when_to_use,
        common_mistake,
        center,
        nodes,
        edges,
        traversal_path,
        components,
        wires,
        x_label,
        y_label,
        data_points,
        key_points,
        what_to_notice,
        code,
        language,
        wrong,
        correct,
        wrong_label,
        correct_label,
        why,
        counterexample,
        interactive_parameter,
        spatial_diagram,
    ]):
        return {}

    return {
        "kind": kind,
        "type": visual_type,
        "title": title,
        "description": description,
        "purpose": purpose,
        "placement": placement,
        "elements": elements,
        "highlight": highlight,
        "labels": labels,
        "columns": columns,
        "rows": rows,
        "steps": steps,
        "formula": formula,
        "symbols": symbols,
        "when_to_use": when_to_use,
        "common_mistake": common_mistake,
        "center": center,
        "nodes": nodes,
        "edges": edges,
        "traversal_path": traversal_path,
        "components": components,
        "wires": wires,
        "x_label": x_label,
        "y_label": y_label,
        "data_points": data_points,
        "key_points": key_points,
        "what_to_notice": what_to_notice,
        "code": code,
        "language": language,
        "highlight_row": highlight_row,
        "wrong": wrong,
        "correct": correct,
        "wrong_label": wrong_label,
        "correct_label": correct_label,
        "why": why,
        "counterexample": counterexample,
        "interactive_parameter": interactive_parameter,
        "spatial_diagram": spatial_diagram,
    }


def normalize_interactive_parameter(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    name = clean_orientation_text(value.get("name"), "")
    description = clean_orientation_text(value.get("description"), "")
    if not name and not description:
        return {}
    return {
        "name": name,
        "description": description,
        "min": coerce_float(value.get("min")),
        "max": coerce_float(value.get("max")),
        "steps": normalize_string_list(value.get("steps"))[:20],
        "unit": clean_orientation_text(value.get("unit"), ""),
    }


def normalize_spatial_diagram(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    coordinate_system = clean_orientation_text(value.get("coordinate_system"), "")
    description = clean_orientation_text(value.get("description"), "")
    if not coordinate_system and not description:
        return {}
    labeled_points: list[dict[str, Any]] = []
    for item in (value.get("labeled_points") or [])[:12]:
        if not isinstance(item, dict):
            continue
        x = coerce_float(item.get("x"))
        y = coerce_float(item.get("y"))
        label = clean_orientation_text(item.get("label"), "")
        if x is not None and y is not None:
            labeled_points.append({"x": x, "y": y, "label": label})
    vectors: list[dict[str, Any]] = []
    for item in (value.get("vectors") or [])[:8]:
        if not isinstance(item, dict):
            continue
        vectors.append({
            "from": [coerce_float(v) for v in (item.get("from") or [0, 0])[:2]],
            "to": [coerce_float(v) for v in (item.get("to") or [0, 0])[:2]],
            "label": clean_orientation_text(item.get("label"), ""),
        })
    return {
        "coordinate_system": coordinate_system,
        "description": description,
        "labeled_points": labeled_points,
        "vectors": vectors,
        "annotations": normalize_string_list(value.get("annotations"))[:6],
    }


def normalize_table_rows(value: Any) -> list[list[str]]:
    if not isinstance(value, list):
        return []

    rows: list[list[str]] = []

    for row in value:
        if isinstance(row, list):
            cells = [str(cell).strip() for cell in row if str(cell).strip()]
            if cells:
                rows.append(cells)

    return rows


def normalize_visual_steps(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    steps: list[dict[str, str]] = []

    for item in value:
        if not isinstance(item, dict):
            continue

        label = clean_orientation_text(item.get("label"), "")
        description = clean_orientation_text(item.get("description"), "")

        if label or description:
            steps.append({"label": label, "description": description})

    return steps


def normalize_visual_symbols(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    symbols: list[dict[str, str]] = []

    for item in value:
        if not isinstance(item, dict):
            continue

        symbol = clean_orientation_text(item.get("symbol"), "")
        meaning = clean_orientation_text(item.get("meaning"), "")

        if symbol or meaning:
            symbols.append({"symbol": symbol, "meaning": meaning})

    return symbols


def normalize_visual_nodes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    nodes: list[dict[str, Any]] = []

    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue

        node_id = clean_orientation_text(item.get("id"), f"node-{index + 1}")
        label = clean_orientation_text(item.get("label"), "")
        relation = clean_orientation_text(item.get("relation"), "")
        description = clean_orientation_text(item.get("description"), "")
        x = coerce_float(item.get("x"))
        y = coerce_float(item.get("y"))

        if node_id or label or relation or description:
            nodes.append({
                "id": node_id,
                "label": label or node_id,
                "relation": relation,
                "description": description,
                "x": x if x is not None else default_node_x(index),
                "y": y if y is not None else default_node_y(index),
            })

    return nodes


def normalize_visual_edges(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    edges: list[dict[str, str]] = []

    for item in value:
        if not isinstance(item, dict):
            continue

        source = clean_orientation_text(item.get("from"), "")
        target = clean_orientation_text(item.get("to"), "")
        label = clean_orientation_text(item.get("label"), "")
        style = clean_orientation_text(item.get("style"), "")

        if source and target:
            edges.append({
                "from": source,
                "to": target,
                "label": label,
                "style": style,
            })

    return edges


def normalize_visual_components(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    components: list[dict[str, Any]] = []

    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue

        component_id = clean_orientation_text(
            item.get("id"),
            f"component-{index + 1}",
        )
        component_type = clean_orientation_text(item.get("type"), "component")
        label = clean_orientation_text(item.get("label"), component_id)
        value_text = clean_orientation_text(item.get("value"), "")
        x = coerce_float(item.get("x"))
        y = coerce_float(item.get("y"))

        components.append({
            "id": component_id,
            "type": component_type,
            "label": label,
            "value": value_text,
            "x": x if x is not None else default_node_x(index),
            "y": y if y is not None else default_node_y(index),
        })

    return components


def default_node_x(index: int) -> float:
    columns = [50, 30, 70, 20, 40, 60, 80, 15, 85]
    return float(columns[index % len(columns)])


def default_node_y(index: int) -> float:
    row = index // 3
    return float(16 + row * 22)


def normalize_graph_points(value: Any) -> list[list[float]]:
    if not isinstance(value, list):
        return []

    points: list[list[float]] = []

    for item in value:
        if not isinstance(item, list) or len(item) < 2:
            continue

        x = coerce_float(item[0])
        y = coerce_float(item[1])

        if x is None or y is None:
            continue

        points.append([x, y])

    return sorted(points, key=lambda point: point[0])


def normalize_key_points(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    key_points: list[dict[str, Any]] = []

    for item in value:
        if not isinstance(item, dict):
            continue

        x = coerce_float(item.get("x"))
        y = coerce_float(item.get("y"))
        label = clean_orientation_text(item.get("label"), "")

        if x is None or y is None:
            continue

        key_points.append({"x": x, "y": y, "label": label})

    return key_points


def coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_index(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def clamp_card_seconds(value: Any) -> int:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return 45

    return max(10, min(seconds, 120))


def split_dense_cards(cards: list[dict[str, Any]], topic: Topic) -> list[dict[str, Any]]:
    split_cards: list[dict[str, Any]] = []

    for card in cards:
        points = normalize_card_points(card.get("points"))

        if len(points) <= 4:
            card["points"] = points
            card["quality_score"] = score_card_quality(card)
            split_cards.append(card)
            continue

        for index in range(0, len(points), 4):
            split_card = {
                **card,
                "id": f"{card.get('id', 'card')}-{(index // 4) + 1}",
                "title": card.get("title") if index == 0 else f"{card.get('title')} continued",
                "points": points[index : index + 4],
                "body": [],
                "bullets": points[index : index + 4],
                "visual_plan": card.get("visual_plan") if index == 0 else {},
                "annotations": card.get("annotations") if index == 0 else [],
            }
            split_card["quality_score"] = score_card_quality(split_card)
            split_cards.append(split_card)

    for index, card in enumerate(split_cards):
        card["id"] = clean_orientation_text(card.get("id"), f"card-{index + 1}")

    return split_cards


def score_card_quality(card: dict[str, Any]) -> int:
    score = 100
    points = normalize_string_list(card.get("points"))
    title = clean_orientation_text(card.get("title"), "")
    has_visual = bool(card.get("visual_plan"))
    has_annotations = bool(card.get("annotations"))
    has_example = bool(card.get("example"))
    has_notice = bool(card.get("what_to_notice"))
    has_main_concept = bool(clean_orientation_text(card.get("main_concept"), ""))
    has_support = bool(card.get("concept_support")) or bool(card.get("styled_elements"))

    if not title:
        score -= 15
    if not has_main_concept:
        score -= 12
    if len(points) == 0:
        score -= 25
    if len(points) > 4:
        score -= 20
    if any(0 < len(point.split()) < 5 for point in points):
        score -= 8
    if any(len(point.split()) > 16 for point in points):
        score -= 15
    if has_visual and not has_annotations:
        score -= 10
    if not has_visual and not has_example and card.get("card_type") in {
        "formula",
        "method_process",
        "process_step",
        "worked_example",
        "example",
        "visual",
    }:
        score -= 10
    if not has_notice:
        score -= 8
    if not has_support and card.get("card_type") not in {"intro", "summary", "bridge_to_next_topic"}:
        score -= 6

    return max(0, min(score, 100))


def build_default_notice(card_type: str, points: list[str]) -> str:
    if card_type in {"edge_case", "common_mistake"}:
        return "Notice what changes from the normal case."

    if card_type in {"method_process", "process_step"}:
        return "Notice which step changes the state."

    if card_type in {"quick_practice", "micro_check"}:
        return "Notice whether the idea works by itself."

    if points:
        return f"Notice: {points[0]}"

    return "Notice the one idea this card adds."


def build_default_transition(card_type: str) -> str:
    if card_type == "intro":
        return "Now that you know the topic, the next step is why it matters."
    if card_type in {"purpose", "purpose_context"}:
        return "This gives the reason; now we need the core idea."
    if card_type in {"method_process", "process_step"}:
        return "You have the steps; now try them in context."
    if card_type in {"worked_example", "example"}:
        return "You have seen the normal case; now look for the tricky part."
    if card_type == "edge_case":
        return "This is the trap to watch for; now do a quick check."
    if card_type in {"quick_practice", "micro_check"}:
        return "Use this check to confirm the idea, then keep moving."

    return "This sets up the next idea."


def build_default_next_label(card_type: str) -> str:
    if card_type == "intro":
        return "Show why it matters"
    if card_type in {"purpose", "purpose_context"}:
        return "Show me the idea"
    if card_type in {"core_idea", "definition", "intuition", "visual", "formula", "comparison"}:
        return "Show me the method"
    if card_type in {"method_process", "process_step"}:
        return "Try an example"
    if card_type in {"worked_example", "example"}:
        return "Show the tricky case"
    if card_type in {"edge_case", "common_mistake"}:
        return "Do a quick check"
    if card_type in {"quick_practice", "micro_check"}:
        return "Continue"

    return "Continue"


def clean_orientation_text(value: Any, fallback: str) -> str:
    if value is None:
        return fallback

    text = str(value).strip()
    return text or fallback


def build_fallback_context(topic: Topic) -> str:
    previous = topic.prerequisite_topics or "the earlier ideas in this path"
    unit = topic.unit_title or "this unit"

    return (
        f"This topic sits in {unit}. It builds on {previous} and prepares you "
        "for the later topics that rely on this idea."
    )


def infer_related_section(question: dict[str, Any]) -> str:
    question_type = str(question.get("question_type") or "").lower()

    if question_type in {"coding", "math"}:
        return "Process / Method"

    if question_type == "multiple_choice":
        return "Components / Definitions"

    return "Practice"


def build_lesson_source_metadata(
    chunks: list[ContentChunk],
) -> tuple[list[str], str]:
    return build_source_chunk_ids(chunks), build_source_summary(chunks)


SEGMENT_SYSTEM_PROMPT = """
You are Azalea, an adaptive learning system.

You rewrite only the future cards in a lesson after a level shift.

Rules:
- Do not rewrite completed cards.
- Do not rewrite the current card.
- Preserve the same learning objective and topic scope.
- Return only replacement cards for positions after current_card_index.
- Keep cards tiny: one idea per card, 20 to 90 seconds.
- If the user is struggling, insert a small repair card immediately.
- If the user is moving fast, compress upcoming definitions and move toward examples/checks.
- Keep practice_question_index stable when reusing existing practice questions.
- Use -1 for practice_question_index or visual_index when not used.
- Return valid JSON only.
"""


def regenerate_future_lesson_cards(
    topic: Topic,
    lesson_json: dict[str, Any],
    current_card_index: int,
    completed_card_ids: list[str],
    trigger: str,
    target_adjustment: str,
    learner_evidence: dict[str, Any],
    chunks: list[ContentChunk],
) -> dict[str, Any]:
    lesson_cards = lesson_json.get("lesson_cards")

    if not isinstance(lesson_cards, list) or not lesson_cards:
        ensure_lesson_cards(lesson_json=lesson_json, topic=topic)
        lesson_cards = lesson_json.get("lesson_cards", [])

    safe_current_index = max(0, min(current_card_index, len(lesson_cards) - 1))
    completed_cards = lesson_cards[: safe_current_index + 1]
    future_cards = lesson_cards[safe_current_index + 1 :]

    if not future_cards:
        return {
            "adaptation_message": "No future cards were left to adjust.",
            "replacement_cards": [],
        }

    source_preview = "\n\n".join(chunk.text[:1200] for chunk in chunks[:4])
    blueprint_instruction = build_course_blueprint_instruction(topic)

    user_prompt = f"""
Topic:
{topic.title}

Topic purpose:
{topic.purpose or "No purpose provided."}

{blueprint_instruction}

Trigger:
{trigger}

Target adjustment:
{target_adjustment}

Learner evidence:
{learner_evidence}

Completed card ids:
{completed_card_ids}

Current card index:
{safe_current_index}

Completed/current cards to preserve:
{completed_cards}

Future cards to replace:
{future_cards}

Existing practice questions:
{lesson_json.get("practice_questions", [])}

Existing visuals:
{lesson_json.get("visual_plan", [])}

Lesson objective:
{lesson_json.get("learning_objective", "")}

Source material preview:
{source_preview or "No source preview available."}

Return:
- adaptation_message: one short learner-facing sentence.
- replacement_cards: the complete replacement sequence for all future cards. Each card must preserve or set blueprint_key when it corresponds to a blueprint stage; use "" only for extra non-blueprint cards.
"""

    result = generate_lesson_segment(
        system_prompt=SEGMENT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    replacement_cards = result.get("replacement_cards", [])
    normalized_cards: list[dict[str, Any]] = []

    for index, card in enumerate(replacement_cards):
        if isinstance(card, dict):
            normalized_cards.append(
                normalize_lesson_card(
                    card,
                    safe_current_index + index + 1,
                    topic,
                )
            )

    temporary_lesson = {
        "course_type": lesson_json.get("course_type"),
        "lesson_cards": normalized_cards,
    }
    validate_and_repair_interactive_links(temporary_lesson)
    validate_and_repair_microchecks(temporary_lesson)
    normalized_cards = temporary_lesson["lesson_cards"]

    return {
        "adaptation_message": clean_orientation_text(
            result.get("adaptation_message"),
            "Azalea adjusted the next few cards based on your recent work.",
        ),
        "replacement_cards": normalized_cards,
    }
