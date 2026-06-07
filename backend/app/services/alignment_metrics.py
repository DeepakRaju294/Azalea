from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.models.azalea_class import AzaleaClass
from app.models.learner_concept_state import LearnerConceptState
from app.models.targeted_repair_attempt import TargetedRepairAttempt
from app.models.topic import Topic


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(_clamp(numerator / denominator), 4)


def _extract_events(state: LearnerConceptState) -> list[dict[str, Any]]:
    evidence = state.evidence_json or {}
    events = evidence.get("events", [])
    return events if isinstance(events, list) else []


def _event_labels(events: list[dict[str, Any]]) -> Counter[str]:
    labels: list[str] = []

    for event in events:
        metadata = event.get("metadata") or {}
        behavioral_labels = metadata.get("behavioral_labels") or []

        if isinstance(behavioral_labels, list):
            labels.extend(str(label) for label in behavioral_labels)

    return Counter(labels)


def _count_events(events: list[dict[str, Any]], signal_type: str) -> int:
    return sum(1 for event in events if event.get("signal_type") == signal_type)


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _score_confidence_calibration(events: list[dict[str, Any]]) -> float:
    paired: list[tuple[float, float]] = []

    for event in events:
        confidence = event.get("confidence")
        correctness = event.get("correctness")

        if isinstance(confidence, (int, float)) and isinstance(correctness, (int, float)):
            paired.append((_clamp(float(confidence)), _clamp(float(correctness))))

    if not paired:
        return 0.0

    # Perfect calibration means confidence roughly matches correctness.
    errors = [abs(confidence - correctness) for confidence, correctness in paired]
    return round(_clamp(1.0 - _average(errors)), 4)


def _build_summary(
    overteaching_score: float,
    underteaching_score: float,
    confidence_calibration_score: float,
    repair_success_rate: float,
    fragile_count: int,
) -> str:
    parts: list[str] = []

    if overteaching_score >= 0.6:
        parts.append(
            "Azalea may be explaining more than needed in some places; future related lessons can compress basics when practice stays strong."
        )
    elif overteaching_score >= 0.35:
        parts.append(
            "There are mild overteaching signals, mostly from fast movement through explanation steps."
        )

    if underteaching_score >= 0.6:
        parts.append(
            "Azalea may be moving too quickly through some fragile concepts; future lessons should add slightly more support."
        )
    elif underteaching_score >= 0.35:
        parts.append(
            "There are mild underteaching signals from rereads, slow practice, hints, or fragile concepts."
        )

    if confidence_calibration_score >= 0.75:
        parts.append("Confidence and performance look reasonably aligned.")
    elif confidence_calibration_score > 0:
        parts.append("Confidence calibration is still forming, so Azalea should keep using quick checks.")

    if repair_success_rate >= 0.65:
        parts.append("Targeted repairs appear to be helping close gaps.")
    elif repair_success_rate > 0:
        parts.append("Some repairs still need follow-up checks before treating those concepts as stable.")

    if fragile_count > 0:
        parts.append(f"{fragile_count} concept(s) still look worth reviewing or lightly repairing.")

    if not parts:
        parts.append(
            "Not enough alignment evidence yet. Azalea should keep collecting practice, confidence, and review signals."
        )

    return " ".join(parts)


def build_study_path_alignment_metrics(
    db: Session,
    user_id: str,
    study_path_id: str,
) -> dict[str, Any]:
    rows = (
        db.query(LearnerConceptState, Topic)
        .join(Topic, LearnerConceptState.topic_id == Topic.id)
        .filter(
            LearnerConceptState.user_id == user_id,
            Topic.study_path_id == study_path_id,
        )
        .all()
    )

    states = [state for state, _topic in rows]
    all_events: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()

    for state in states:
        events = _extract_events(state)
        all_events.extend(events)
        label_counts.update(_event_labels(events))

    total_events = max(len(all_events), 1)

    hint_count = _count_events(all_events, "hint")
    question_count = _count_events(all_events, "question")
    practice_count = _count_events(all_events, "practice")
    reread_count = _count_events(all_events, "reread")
    time_signal_count = _count_events(all_events, "time_on_slide")

    strong_practice_events = 0
    weak_practice_events = 0
    minor_or_fragile_events = 0

    transfer_values: list[float] = []
    edge_case_values: list[float] = []
    delayed_recall_values: list[float] = []

    for event in all_events:
        metadata = event.get("metadata") or {}
        performance_level = metadata.get("performance_level")
        next_action = metadata.get("next_action")
        source = metadata.get("source")

        if performance_level == "strong":
            strong_practice_events += 1
        elif performance_level == "weak":
            weak_practice_events += 1
        elif performance_level in {"minor_mistake", "fragile"}:
            minor_or_fragile_events += 1

        transfer_success = event.get("transfer_success")
        edge_case_success = event.get("edge_case_success")
        correctness = event.get("correctness")

        if isinstance(transfer_success, (int, float)):
            transfer_values.append(_clamp(float(transfer_success)))

        if isinstance(edge_case_success, (int, float)):
            edge_case_values.append(_clamp(float(edge_case_success)))

        if source == "spaced_review" and isinstance(correctness, (int, float)):
            delayed_recall_values.append(_clamp(float(correctness)))

        if next_action == "mark_stable" and source == "spaced_review":
            delayed_recall_values.append(1.0)

    fast_skip_count = label_counts["fast_explanation_skip"]
    long_dwell_count = label_counts["long_explanation_dwell"]
    slow_practice_count = label_counts["slow_practice_attempt"]
    fast_practice_count = label_counts["fast_practice_attempt"]
    revisit_count = label_counts["revisit_or_reread"] + reread_count

    overteaching_score = _clamp(
        (fast_skip_count * 0.12)
        + (fast_practice_count * 0.1)
        + (strong_practice_events * 0.08)
        - (hint_count * 0.05)
        - (weak_practice_events * 0.08)
    )

    underteaching_score = _clamp(
        (long_dwell_count * 0.1)
        + (slow_practice_count * 0.12)
        + (revisit_count * 0.08)
        + (hint_count * 0.08)
        + (weak_practice_events * 0.12)
        + (minor_or_fragile_events * 0.08)
        + (question_count * 0.04)
    )

    confidence_calibration_score = _score_confidence_calibration(all_events)
    transfer_success_rate = _average(transfer_values)
    edge_case_success_rate = _average(edge_case_values)
    delayed_recall_success_rate = _average(delayed_recall_values)

    repair_attempts = (
        db.query(TargetedRepairAttempt)
        .join(Topic, TargetedRepairAttempt.topic_id == Topic.id)
        .filter(
            TargetedRepairAttempt.user_id == user_id,
            Topic.study_path_id == study_path_id,
        )
        .all()
    )

    completed_repairs = [attempt for attempt in repair_attempts if attempt.follow_up_completed]
    successful_repairs = [
        attempt
        for attempt in completed_repairs
        if (attempt.follow_up_correctness or 0.0) >= 0.7
        and (attempt.follow_up_reasoning_quality or 0.0) >= 0.6
    ]

    repair_success_rate = _safe_ratio(len(successful_repairs), len(completed_repairs))

    fragile_states = [
        state
        for state in states
        if state.knowledge_state in {"unknown", "familiar", "fragile"}
    ]

    stable_states = [
        state
        for state in states
        if state.knowledge_state in {"stable", "transferable"}
    ]

    time_to_alignment_score = _safe_ratio(len(stable_states), len(states))

    concepts_needing_support = [
        {
            "concept_name": state.concept_name,
            "topic_id": str(topic.id),
            "topic_title": topic.title,
            "knowledge_state": state.knowledge_state,
            "review_due_at": state.review_due_at,
            "review_reason": state.review_reason,
        }
        for state, topic in rows
        if state.knowledge_state in {"unknown", "familiar", "fragile"}
    ][:10]

    concepts_moving_fast = [
        {
            "concept_name": state.concept_name,
            "topic_id": str(topic.id),
            "topic_title": topic.title,
            "knowledge_state": state.knowledge_state,
        }
        for state, topic in rows
        if state.knowledge_state in {"stable", "transferable"}
    ][:10]

    summary = _build_summary(
        overteaching_score=overteaching_score,
        underteaching_score=underteaching_score,
        confidence_calibration_score=confidence_calibration_score,
        repair_success_rate=repair_success_rate,
        fragile_count=len(fragile_states),
    )

    return {
        "study_path_id": study_path_id,
        "overteaching_score": round(overteaching_score, 4),
        "underteaching_score": round(underteaching_score, 4),
        "time_to_alignment_score": round(time_to_alignment_score, 4),
        "confidence_calibration_score": round(confidence_calibration_score, 4),
        "transfer_success_rate": round(transfer_success_rate, 4),
        "delayed_recall_success_rate": round(delayed_recall_success_rate, 4),
        "edge_case_success_rate": round(edge_case_success_rate, 4),
        "repair_success_rate": round(repair_success_rate, 4),
        "total_concepts_tracked": len(states),
        "stable_or_transferable_concepts": len(stable_states),
        "fragile_or_unknown_concepts": len(fragile_states),
        "total_behavior_events": total_events if all_events else 0,
        "fast_skip_count": fast_skip_count,
        "long_dwell_count": long_dwell_count,
        "revisit_count": revisit_count,
        "hint_count": hint_count,
        "practice_count": practice_count,
        "targeted_repair_count": len(repair_attempts),
        "completed_repair_follow_up_count": len(completed_repairs),
        "concepts_needing_support": concepts_needing_support,
        "concepts_moving_fast": concepts_moving_fast,
        "summary": summary,
    }


def build_class_alignment_metrics(
    db: Session,
    user_id: str,
    class_id: str,
) -> dict:
    azalea_class = (
        db.query(AzaleaClass)
        .filter(
            AzaleaClass.id == class_id,
            AzaleaClass.user_id == user_id,
        )
        .first()
    )

    if not azalea_class:
        return {
            "scope_id": class_id,
            "scope_type": "class",
            "overteaching_score": 0.0,
            "underteaching_score": 0.0,
            "confidence_calibration_score": 0.0,
            "transfer_success_rate": 0.0,
            "delayed_recall_success_rate": 0.0,
            "edge_case_success_rate": 0.0,
            "repair_success_rate": 0.0,
            "summary": "Class not found.",
        }

    study_path_ids = [str(path.id) for path in azalea_class.study_paths or []]

    if not study_path_ids:
        return {
            "scope_id": class_id,
            "scope_type": "class",
            "overteaching_score": 0.0,
            "underteaching_score": 0.0,
            "confidence_calibration_score": 0.0,
            "transfer_success_rate": 0.0,
            "delayed_recall_success_rate": 0.0,
            "edge_case_success_rate": 0.0,
            "repair_success_rate": 0.0,
            "summary": "Not enough class activity yet to estimate alignment.",
        }

    states = (
        db.query(LearnerConceptState)
        .join(Topic, LearnerConceptState.topic_id == Topic.id)
        .filter(
            LearnerConceptState.user_id == user_id,
            Topic.study_path_id.in_(study_path_ids),
        )
        .all()
    )

    repairs = (
        db.query(TargetedRepairAttempt)
        .join(Topic, TargetedRepairAttempt.topic_id == Topic.id)
        .filter(
            TargetedRepairAttempt.user_id == user_id,
            Topic.study_path_id.in_(study_path_ids),
        )
        .all()
    )

    if not states:
        return {
            "scope_id": class_id,
            "scope_type": "class",
            "overteaching_score": 0.0,
            "underteaching_score": 0.0,
            "confidence_calibration_score": 0.0,
            "transfer_success_rate": 0.0,
            "delayed_recall_success_rate": 0.0,
            "edge_case_success_rate": 0.0,
            "repair_success_rate": 0.0,
            "summary": "Not enough learner signals yet to estimate alignment.",
        }

    stable_or_transferable = [
        state for state in states
        if state.knowledge_state in {"stable", "transferable"}
    ]

    fragile_or_unknown = [
        state for state in states
        if state.knowledge_state in {"unknown", "familiar", "fragile"}
    ]

    overteaching_score = min(
        1.0,
        len(stable_or_transferable) / max(len(states), 1),
    )

    underteaching_score = min(
        1.0,
        len(fragile_or_unknown) / max(len(states), 1),
    )

    confidence_gap_values = [
        abs((state.confidence_score or 0.0) - (state.stability_score or 0.0))
        for state in states
    ]

    avg_confidence_gap = (
        sum(confidence_gap_values) / len(confidence_gap_values)
        if confidence_gap_values
        else 1.0
    )

    confidence_calibration_score = max(0.0, min(1.0, 1.0 - avg_confidence_gap))

    transfer_values = [state.transfer_score or 0.0 for state in states]
    edge_values = [state.edge_case_score or 0.0 for state in states]

    transfer_success_rate = (
        sum(transfer_values) / len(transfer_values)
        if transfer_values
        else 0.0
    )

    edge_case_success_rate = (
        sum(edge_values) / len(edge_values)
        if edge_values
        else 0.0
    )

    completed_repairs = [
        repair for repair in repairs
        if repair.follow_up_completed and repair.follow_up_correctness is not None
    ]

    repair_success_rate = (
        sum(repair.follow_up_correctness or 0.0 for repair in completed_repairs)
        / len(completed_repairs)
        if completed_repairs
        else 0.0
    )

    delayed_recall_states = [
        state for state in states
        if state.review_due_at is not None
    ]

    delayed_recall_success_rate = (
        sum(state.stability_score or 0.0 for state in delayed_recall_states)
        / len(delayed_recall_states)
        if delayed_recall_states
        else 0.0
    )

    if underteaching_score > 0.55:
        summary = "Azalea may need to give slightly more support across this class."
    elif overteaching_score > 0.75:
        summary = "Azalea can likely compress basics and move faster in parts of this class."
    else:
        summary = "Teaching depth looks reasonably aligned across this class."

    return {
        "scope_id": class_id,
        "scope_type": "class",
        "overteaching_score": overteaching_score,
        "underteaching_score": underteaching_score,
        "confidence_calibration_score": confidence_calibration_score,
        "transfer_success_rate": transfer_success_rate,
        "delayed_recall_success_rate": delayed_recall_success_rate,
        "edge_case_success_rate": edge_case_success_rate,
        "repair_success_rate": repair_success_rate,
        "summary": summary,
    }
    azalea_class = (
        db.query(AzaleaClass)
        .filter(AzaleaClass.id == class_id, AzaleaClass.user_id == user_id)
        .first()
    )

    if not azalea_class:
        return {
            "class_id": class_id,
            "overteaching_score": 0.0,
            "underteaching_score": 0.0,
            "time_to_alignment_score": 0.0,
            "confidence_calibration_score": 0.0,
            "transfer_success_rate": 0.0,
            "delayed_recall_success_rate": 0.0,
            "edge_case_success_rate": 0.0,
            "repair_success_rate": 0.0,
            "total_concepts_tracked": 0,
            "stable_or_transferable_concepts": 0,
            "fragile_or_unknown_concepts": 0,
            "total_behavior_events": 0,
            "fast_skip_count": 0,
            "long_dwell_count": 0,
            "revisit_count": 0,
            "hint_count": 0,
            "practice_count": 0,
            "targeted_repair_count": 0,
            "completed_repair_follow_up_count": 0,
            "concepts_needing_support": [],
            "concepts_moving_fast": [],
            "summary": "Class not found.",
        }

    path_metrics = [
        build_study_path_alignment_metrics(
            db=db,
            user_id=user_id,
            study_path_id=str(study_path.id),
        )
        for study_path in azalea_class.study_paths
    ]

    if not path_metrics:
        return {
            "class_id": class_id,
            "overteaching_score": 0.0,
            "underteaching_score": 0.0,
            "time_to_alignment_score": 0.0,
            "confidence_calibration_score": 0.0,
            "transfer_success_rate": 0.0,
            "delayed_recall_success_rate": 0.0,
            "edge_case_success_rate": 0.0,
            "repair_success_rate": 0.0,
            "total_concepts_tracked": 0,
            "stable_or_transferable_concepts": 0,
            "fragile_or_unknown_concepts": 0,
            "total_behavior_events": 0,
            "fast_skip_count": 0,
            "long_dwell_count": 0,
            "revisit_count": 0,
            "hint_count": 0,
            "practice_count": 0,
            "targeted_repair_count": 0,
            "completed_repair_follow_up_count": 0,
            "concepts_needing_support": [],
            "concepts_moving_fast": [],
            "summary": "No study paths are attached to this class yet.",
        }

    score_fields = [
        "overteaching_score",
        "underteaching_score",
        "time_to_alignment_score",
        "confidence_calibration_score",
        "transfer_success_rate",
        "delayed_recall_success_rate",
        "edge_case_success_rate",
        "repair_success_rate",
    ]
    count_fields = [
        "total_concepts_tracked",
        "stable_or_transferable_concepts",
        "fragile_or_unknown_concepts",
        "total_behavior_events",
        "fast_skip_count",
        "long_dwell_count",
        "revisit_count",
        "hint_count",
        "practice_count",
        "targeted_repair_count",
        "completed_repair_follow_up_count",
    ]

    result: dict[str, Any] = {"class_id": class_id}

    for field in score_fields:
        result[field] = round(
            sum(float(metrics.get(field, 0.0)) for metrics in path_metrics)
            / len(path_metrics),
            4,
        )

    for field in count_fields:
        result[field] = sum(int(metrics.get(field, 0)) for metrics in path_metrics)

    concepts_needing_support: list[dict[str, Any]] = []
    concepts_moving_fast: list[dict[str, Any]] = []

    for metrics in path_metrics:
        concepts_needing_support.extend(metrics.get("concepts_needing_support", []))
        concepts_moving_fast.extend(metrics.get("concepts_moving_fast", []))

    result["concepts_needing_support"] = concepts_needing_support[:10]
    result["concepts_moving_fast"] = concepts_moving_fast[:10]

    fragile_count = result["fragile_or_unknown_concepts"]
    stable_count = result["stable_or_transferable_concepts"]

    if fragile_count:
        result["summary"] = (
            f"{fragile_count} concept(s) across this class still need review or light repair."
        )
    elif stable_count:
        result["summary"] = (
            "Class memory looks stable overall. Azalea can lean into transfer and review checks."
        )
    else:
        result["summary"] = (
            "Not enough class-level alignment evidence yet. Keep using lessons and practice."
        )

    return result
