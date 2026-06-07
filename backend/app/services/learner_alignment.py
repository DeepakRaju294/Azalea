from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.learner_concept_state import LearnerConceptState


SELF_REPORT_TO_STATE = {
    0: "unknown",
    1: "familiar",
    2: "fragile",
    3: "stable",
}

STATE_TO_STARTING_MODE = {
    "unknown": "full_teach",
    "familiar": "compressed_refresher",
    "fragile": "compressed_refresher",
    "stable": "nuance_first",
    "transferable": "transfer_practice",
}


def map_self_report_to_state(level: int) -> str:
    return SELF_REPORT_TO_STATE.get(level, "unknown")


def map_state_to_starting_mode(state: str) -> str:
    return STATE_TO_STARTING_MODE.get(state, "full_teach")


def explanation_density_for_level(level: int) -> str:
    if level == 0:
        return "complete"
    if level == 1:
        return "compressed_with_repairs"
    if level == 2:
        return "nuance_focused"
    return "edge_case_and_transfer_focused"


def should_offer_diagnostic(level: int, mode: str) -> bool:
    if mode in {"refresh", "review", "final_review"}:
        return True

    return level in {1, 2, 3}


def calculate_knowledge_state(
    familiarity_score: float,
    conceptual_score: float,
    procedural_score: float,
    transfer_score: float,
    confidence_score: float,
    stability_score: float,
) -> str:
    average_core = (familiarity_score + conceptual_score + procedural_score) / 3

    if average_core < 0.25:
        return "unknown"

    if average_core < 0.45:
        return "familiar"

    if average_core < 0.7:
        return "fragile"

    if transfer_score >= 0.75 and stability_score >= 0.65:
        return "transferable"

    return "stable"


def schedule_review_for_state(state: str, mistake_type: str | None = None) -> tuple[datetime | None, str | None]:
    now = datetime.now(timezone.utc)

    if state == "unknown":
        return now + timedelta(hours=6), "needs_initial_repair"

    if state == "familiar":
        return now + timedelta(days=1), "needs_foundation_check"

    if state == "fragile":
        return now + timedelta(days=1), "fragile_concept"

    if mistake_type:
        return now + timedelta(days=1), f"mistake_followup:{mistake_type}"

    if state == "stable":
        return now + timedelta(days=3), "delayed_retrieval_check"

    if state == "transferable":
        return now + timedelta(days=7), "long_term_retention_check"

    return None, None


def get_or_create_concept_state(
    db: Session,
    user_id: str,
    topic_id: str,
    concept_name: str,
) -> LearnerConceptState:
    existing = (
        db.query(LearnerConceptState)
        .filter(
            LearnerConceptState.user_id == user_id,
            LearnerConceptState.topic_id == topic_id,
            LearnerConceptState.concept_name == concept_name,
        )
        .first()
    )

    if existing:
        return existing

    state = LearnerConceptState(
        user_id=user_id,
        topic_id=topic_id,
        concept_name=concept_name,
        knowledge_state="unknown",
        familiarity_score=0.0,
        conceptual_score=0.0,
        procedural_score=0.0,
        transfer_score=0.0,
        confidence_score=0.0,
        stability_score=0.0,
        evidence_json={},
        recurring_mistakes=[],
    )

    db.add(state)
    db.flush()

    return state


def apply_self_report(
    db: Session,
    user_id: str,
    topic_id: str,
    level: int,
    concept_name: str = "overall_topic",
) -> LearnerConceptState:
    state = get_or_create_concept_state(
        db=db,
        user_id=user_id,
        topic_id=topic_id,
        concept_name=concept_name,
    )

    mapped_state = map_self_report_to_state(level)

    if level == 0:
        state.familiarity_score = max(state.familiarity_score, 0.05)
    elif level == 1:
        state.familiarity_score = max(state.familiarity_score, 0.35)
    elif level == 2:
        state.familiarity_score = max(state.familiarity_score, 0.65)
        state.conceptual_score = max(state.conceptual_score, 0.45)
    elif level == 3:
        state.familiarity_score = max(state.familiarity_score, 0.8)
        state.conceptual_score = max(state.conceptual_score, 0.65)

    state.knowledge_state = mapped_state
    state.last_signal_type = "self_report"
    state.last_signal_summary = f"User self-reported level {level}."
    state.evidence_json = {
        **(state.evidence_json or {}),
        "self_report_level": level,
    }

    state.review_due_at, state.review_reason = schedule_review_for_state(mapped_state)

    db.add(state)
    db.commit()
    db.refresh(state)

    return state


def update_concept_from_signal(
    db: Session,
    user_id: str,
    topic_id: str,
    concept_name: str,
    signal_type: str,
    correctness: float | None = None,
    reasoning_quality: float | None = None,
    hint_used: bool = False,
    confidence: float | None = None,
    transfer_success: float | None = None,
    edge_case_success: float | None = None,
    time_seconds: int | None = None,
    mistake_type: str | None = None,
    summary: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> LearnerConceptState:
    state = get_or_create_concept_state(
        db=db,
        user_id=user_id,
        topic_id=topic_id,
        concept_name=concept_name,
    )

    metadata = metadata or {}

    if correctness is not None:
        state.total_attempts += 1

        if correctness >= 0.75:
            state.correct_attempts += 1

        state.procedural_score = weighted_update(state.procedural_score, correctness)

    if reasoning_quality is not None:
        state.conceptual_score = weighted_update(state.conceptual_score, reasoning_quality)

    if transfer_success is not None:
        state.transfer_score = weighted_update(state.transfer_score, transfer_success)

    if edge_case_success is not None:
        state.conceptual_score = weighted_update(
            state.conceptual_score,
            max(state.conceptual_score, edge_case_success * 0.9),
        )

    if confidence is not None:
        state.confidence_score = weighted_update(state.confidence_score, confidence)

    if hint_used:
        state.hint_count += 1
        state.stability_score = max(0.0, state.stability_score - 0.08)

    if correctness is not None and correctness >= 0.75 and not hint_used:
        state.stability_score = min(1.0, state.stability_score + 0.08)

    if mistake_type:
        state.misconception_count += 1
        mistakes = list(state.recurring_mistakes or [])
        mistakes.append(
            {
                "mistake_type": mistake_type,
                "summary": summary,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        state.recurring_mistakes = mistakes[-20:]

    state.knowledge_state = calculate_knowledge_state(
        familiarity_score=state.familiarity_score,
        conceptual_score=state.conceptual_score,
        procedural_score=state.procedural_score,
        transfer_score=state.transfer_score,
        confidence_score=state.confidence_score,
        stability_score=state.stability_score,
    )

    if confidence is not None and correctness is not None:
        if confidence >= 0.75 and correctness < 0.5:
            state.review_due_at, state.review_reason = schedule_review_for_state(
                "fragile",
                "high_confidence_wrong",
            )
        elif confidence < 0.45 and correctness >= 0.75:
            state.review_due_at, state.review_reason = schedule_review_for_state(
                "stable",
                "low_confidence_correct",
            )
        else:
            state.review_due_at, state.review_reason = schedule_review_for_state(
                state.knowledge_state,
                mistake_type,
            )
    else:
        state.review_due_at, state.review_reason = schedule_review_for_state(
            state.knowledge_state,
            mistake_type,
        )

    evidence = state.evidence_json or {}
    events = list(evidence.get("events", []))
    events.append(
        {
            "signal_type": signal_type,
            "correctness": correctness,
            "reasoning_quality": reasoning_quality,
            "hint_used": hint_used,
            "confidence": confidence,
            "transfer_success": transfer_success,
            "edge_case_success": edge_case_success,
            "time_seconds": time_seconds,
            "mistake_type": mistake_type,
            "summary": summary,
            "metadata": metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    evidence["events"] = events[-50:]
    state.evidence_json = evidence

    state.last_signal_type = signal_type
    state.last_signal_summary = summary

    db.add(state)
    db.commit()
    db.refresh(state)

    return state


def weighted_update(old_value: float, new_signal: float, signal_weight: float = 0.35) -> float:
    new_signal = max(0.0, min(1.0, new_signal))
    return round((old_value * (1 - signal_weight)) + (new_signal * signal_weight), 4)


def generate_static_diagnostic_questions(topic_title: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "recall_1",
            "type": "recall",
            "question": f"In one sentence, what is the main idea of {topic_title}?",
            "concept_name": "core_idea",
        },
        {
            "id": "application_1",
            "type": "application",
            "question": f"Give a simple example where you would use {topic_title}.",
            "concept_name": "application",
        },
        {
            "id": "edge_case_1",
            "type": "edge_case",
            "question": f"What is one situation where {topic_title} might not work the way someone expects?",
            "concept_name": "edge_cases",
        },
        {
            "id": "transfer_1",
            "type": "transfer",
            "question": f"How could the idea behind {topic_title} apply in a different context?",
            "concept_name": "transfer",
        },
    ]


def estimate_state_from_diagnostic_scores(
    correctness_score: float,
    transfer_score: float,
    edge_case_score: float,
    confidence_score: float,
) -> str:
    core_average = (correctness_score + edge_case_score) / 2

    if core_average < 0.25:
        return "unknown"

    if core_average < 0.5:
        return "familiar"

    if core_average < 0.7:
        return "fragile"

    if transfer_score >= 0.75 and confidence_score >= 0.6:
        return "transferable"

    return "stable"


def get_alignment_note(state: str) -> str:
    if state == "unknown":
        return "Azalea will start from the foundation and avoid assuming prior knowledge."

    if state == "familiar":
        return "Azalea will use a compressed refresher and repair only missing prerequisites."

    if state == "fragile":
        return "Azalea will move quickly but add checks for shaky pieces."

    if state == "stable":
        return "Azalea will skip most basics and focus on nuance, edge cases, and reinforcement."

    return "Azalea will move toward transfer practice and advanced applications."
