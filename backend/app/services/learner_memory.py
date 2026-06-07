from sqlalchemy.orm import Session

from app.models.azalea_class import AzaleaClass
from app.models.learner_concept_state import LearnerConceptState
from app.models.topic import Topic
from app.services.behavior_interpreter import summarize_behavior_from_events


def build_study_path_memory_summary(
    db: Session,
    user_id: str,
    study_path_id: str,
    exclude_topic_id: str | None = None,
) -> dict:
    query = (
        db.query(LearnerConceptState, Topic)
        .join(Topic, LearnerConceptState.topic_id == Topic.id)
        .filter(
            LearnerConceptState.user_id == user_id,
            Topic.study_path_id == study_path_id,
        )
    )

    if exclude_topic_id:
        query = query.filter(Topic.id != exclude_topic_id)

    rows = query.order_by(LearnerConceptState.updated_at.desc()).all()

    stable_concepts = []
    fragile_concepts = []
    transferable_concepts = []
    unknown_concepts = []

    all_behavior_events: list[dict] = []
    overteaching_signals: list[str] = []
    underteaching_signals: list[str] = []

    for state, topic in rows:
        evidence = state.evidence_json or {}
        events = evidence.get("events", [])

        if isinstance(events, list):
            all_behavior_events.extend(events)

        behavior_summary = summarize_behavior_from_events(
            events if isinstance(events, list) else []
        )

        if behavior_summary["possible_overteaching"]:
            overteaching_signals.append(
                f"{state.concept_name} in {topic.title}"
            )

        if behavior_summary["possible_underteaching"]:
            underteaching_signals.append(
                f"{state.concept_name} in {topic.title}"
            )

        item = {
            "concept_name": state.concept_name,
            "topic_id": str(topic.id),
            "topic_title": topic.title,
            "knowledge_state": state.knowledge_state,
            "familiarity_score": state.familiarity_score,
            "conceptual_score": state.conceptual_score,
            "procedural_score": state.procedural_score,
            "transfer_score": state.transfer_score,
            "confidence_score": state.confidence_score,
            "stability_score": state.stability_score,
            "review_due_at": state.review_due_at,
            "review_reason": state.review_reason,
        }

        if state.knowledge_state == "transferable":
            transferable_concepts.append(item)
        elif state.knowledge_state == "stable":
            stable_concepts.append(item)
        elif state.knowledge_state in {"fragile", "familiar"}:
            fragile_concepts.append(item)
        else:
            unknown_concepts.append(item)

    concepts_to_skip = [
        item["concept_name"]
        for item in transferable_concepts[:8] + stable_concepts[:8]
        if item["concept_name"] != "overall_topic"
    ]

    concepts_to_briefly_repair = [
        item["concept_name"]
        for item in fragile_concepts[:10]
        if item["concept_name"] != "overall_topic"
    ]

    overall_behavior_summary = summarize_behavior_from_events(all_behavior_events)

    guidance_parts = []

    if concepts_to_skip:
        guidance_parts.append(
            "Avoid reteaching stable/transferable concepts unless they are necessary anchors: "
            + ", ".join(concepts_to_skip[:8])
            + "."
        )

    if concepts_to_briefly_repair:
        guidance_parts.append(
            "Briefly repair fragile concepts only if they are needed for the current topic: "
            + ", ".join(concepts_to_briefly_repair[:8])
            + "."
        )

    if transferable_concepts:
        guidance_parts.append(
            "Prefer transfer/application when building from transferable concepts."
        )

    if overall_behavior_summary["possible_overteaching"]:
        guidance_parts.append(
            "Behavior suggests the learner may be moving quickly through some explanations, so compress obvious basics when related concepts are already stable."
        )

    if overall_behavior_summary["possible_underteaching"]:
        guidance_parts.append(
            "Behavior suggests some explanations may be too compressed, so add support when related concepts are fragile or repeatedly revisited."
        )

    if not guidance_parts:
        guidance_parts.append(
            "No strong prior learner memory is available yet. Use the current calibration and topic context."
        )

    return {
        "study_path_id": study_path_id,
        "stable_concepts": stable_concepts[:20],
        "fragile_concepts": fragile_concepts[:20],
        "transferable_concepts": transferable_concepts[:20],
        "unknown_concepts": unknown_concepts[:20],
        "concepts_to_skip": concepts_to_skip[:12],
        "concepts_to_briefly_repair": concepts_to_briefly_repair[:12],
        "recommended_lesson_guidance": " ".join(guidance_parts),
        "behavior_guidance": overall_behavior_summary["behavior_guidance"],
        "possible_overteaching_signals": overteaching_signals[:12],
        "possible_underteaching_signals": underteaching_signals[:12],
    }


def format_memory_summary_for_prompt(memory_summary: dict | None) -> str:
    if not memory_summary:
        return "No cross-topic learner memory was provided."

    stable = memory_summary.get("stable_concepts", [])
    fragile = memory_summary.get("fragile_concepts", [])
    transferable = memory_summary.get("transferable_concepts", [])
    concepts_to_skip = memory_summary.get("concepts_to_skip", [])
    concepts_to_repair = memory_summary.get("concepts_to_briefly_repair", [])
    overteaching = memory_summary.get("possible_overteaching_signals", [])
    underteaching = memory_summary.get("possible_underteaching_signals", [])

    def format_items(items: list[dict], limit: int = 8) -> str:
        if not items:
            return "- none"

        return "\n".join(
            f"- {item.get('concept_name')} "
            f"({item.get('knowledge_state')} from {item.get('topic_title')})"
            for item in items[:limit]
        )

    def format_strings(items: list[str], limit: int = 8) -> str:
        if not items:
            return "- none"

        return "\n".join(f"- {item}" for item in items[:limit])

    skip_text = format_strings(concepts_to_skip)
    repair_text = format_strings(concepts_to_repair)

    return f"""
CROSS-TOPIC LEARNER MEMORY

Transferable concepts:
{format_items(transferable)}

Stable concepts:
{format_items(stable)}

Fragile concepts:
{format_items(fragile)}

Concepts to avoid reteaching unless needed:
{skip_text}

Concepts to briefly repair only if needed:
{repair_text}

Behavior guidance:
{memory_summary.get("behavior_guidance", "No behavior guidance available.")}

Possible overteaching signals:
{format_strings(overteaching)}

Possible underteaching signals:
{format_strings(underteaching)}

Recommended guidance:
{memory_summary.get("recommended_lesson_guidance", "No guidance provided.")}
""".strip()


def build_class_memory_summary(
    db: Session,
    user_id: str,
    class_id: str,
) -> dict:
    azalea_class = (
        db.query(AzaleaClass)
        .filter(AzaleaClass.id == class_id, AzaleaClass.user_id == user_id)
        .first()
    )

    if not azalea_class:
        return {
            "class_id": class_id,
            "stable_concepts": [],
            "fragile_concepts": [],
            "transferable_concepts": [],
            "unknown_concepts": [],
            "concepts_to_skip": [],
            "concepts_to_briefly_repair": [],
            "recommended_guidance": "Class not found.",
        }

    stable_concepts: list[dict] = []
    fragile_concepts: list[dict] = []
    transferable_concepts: list[dict] = []
    unknown_concepts: list[dict] = []
    concepts_to_skip: list[str] = []
    concepts_to_briefly_repair: list[str] = []

    for study_path in azalea_class.study_paths:
        summary = build_study_path_memory_summary(
            db=db,
            user_id=user_id,
            study_path_id=str(study_path.id),
        )

        stable_concepts.extend(summary.get("stable_concepts", []))
        fragile_concepts.extend(summary.get("fragile_concepts", []))
        transferable_concepts.extend(summary.get("transferable_concepts", []))
        unknown_concepts.extend(summary.get("unknown_concepts", []))
        concepts_to_skip.extend(summary.get("concepts_to_skip", []))
        concepts_to_briefly_repair.extend(
            summary.get("concepts_to_briefly_repair", [])
        )

    concepts_to_skip = list(dict.fromkeys(concepts_to_skip))[:12]
    concepts_to_briefly_repair = list(dict.fromkeys(concepts_to_briefly_repair))[:12]

    guidance_parts: list[str] = []

    if concepts_to_skip:
        guidance_parts.append(
            "Avoid reteaching stable concepts across this class unless needed: "
            + ", ".join(concepts_to_skip[:8])
            + "."
        )

    if concepts_to_briefly_repair:
        guidance_parts.append(
            "Briefly repair fragile class concepts when they appear again: "
            + ", ".join(concepts_to_briefly_repair[:8])
            + "."
        )

    if not guidance_parts:
        guidance_parts.append(
            "Not enough class-level learner memory yet. Azalea will build this from practice, review, and confidence signals."
        )

    return {
        "class_id": class_id,
        "stable_concepts": stable_concepts[:20],
        "fragile_concepts": fragile_concepts[:20],
        "transferable_concepts": transferable_concepts[:20],
        "unknown_concepts": unknown_concepts[:20],
        "concepts_to_skip": concepts_to_skip,
        "concepts_to_briefly_repair": concepts_to_briefly_repair,
        "recommended_guidance": " ".join(guidance_parts),
    }


def build_global_memory_summary(
    db: Session,
    user_id: str,
) -> dict:
    rows = (
        db.query(LearnerConceptState, Topic)
        .join(Topic, LearnerConceptState.topic_id == Topic.id)
        .filter(LearnerConceptState.user_id == user_id)
        .order_by(LearnerConceptState.updated_at.desc())
        .all()
    )

    stable_patterns: list[str] = []
    fragile_patterns: list[str] = []
    preferred_learning_patterns: list[str] = []
    confidence_patterns: list[str] = []

    for state, topic in rows:
        label = f"{state.concept_name} ({topic.title})"

        if state.knowledge_state in {"stable", "transferable"}:
            stable_patterns.append(label)

        if state.knowledge_state in {"unknown", "familiar", "fragile"}:
            fragile_patterns.append(label)

        if state.confidence_score >= 0.7 and state.procedural_score >= 0.7:
            confidence_patterns.append(f"Well calibrated on {label}")
        elif state.confidence_score >= 0.7 and state.procedural_score < 0.5:
            confidence_patterns.append(f"High confidence gap on {label}")

        evidence = state.evidence_json or {}
        events = evidence.get("events", [])
        if isinstance(events, list):
            behavior_summary = summarize_behavior_from_events(events)
            guidance = behavior_summary.get("behavior_guidance")
            if guidance:
                preferred_learning_patterns.append(guidance)

    stable_patterns = list(dict.fromkeys(stable_patterns))[:10]
    fragile_patterns = list(dict.fromkeys(fragile_patterns))[:10]
    preferred_learning_patterns = list(dict.fromkeys(preferred_learning_patterns))[:6]
    confidence_patterns = list(dict.fromkeys(confidence_patterns))[:8]

    guidance_parts: list[str] = []

    if stable_patterns:
        guidance_parts.append(
            "The learner often benefits from faster movement on stable areas."
        )

    if fragile_patterns:
        guidance_parts.append(
            "The learner still needs quick checks and light repair on fragile areas."
        )

    if confidence_patterns:
        guidance_parts.append(
            "Use confidence checks because calibration patterns are emerging."
        )

    if not guidance_parts:
        guidance_parts.append(
            "No strong global learner memory yet. Continue collecting practice and review signals."
        )

    return {
        "stable_patterns": stable_patterns,
        "fragile_patterns": fragile_patterns,
        "preferred_learning_patterns": preferred_learning_patterns,
        "confidence_patterns": confidence_patterns,
        "recommended_guidance": " ".join(guidance_parts),
    }
