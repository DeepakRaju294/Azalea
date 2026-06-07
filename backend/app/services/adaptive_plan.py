from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.azalea_class import AzaleaClass
from app.models.learner_concept_state import LearnerConceptState
from app.models.study_path import StudyPath
from app.models.targeted_repair_attempt import TargetedRepairAttempt
from app.models.topic import Topic


def build_study_path_adaptive_plan(
    db: Session,
    user_id: str,
    study_path_id: str,
    target_minutes: int | None = None,
) -> dict[str, Any]:
    study_path = (
        db.query(StudyPath)
        .filter(
            StudyPath.id == study_path_id,
            StudyPath.user_id == user_id,
        )
        .first()
    )

    if not study_path:
        return {
            "study_path_id": study_path_id,
            "recommended_minutes": target_minutes or 25,
            "summary": "Study path not found.",
            "tasks": [],
        }

    recommended_minutes = target_minutes or 25
    now = datetime.now(timezone.utc)

    topics = (
        db.query(Topic)
        .filter(Topic.study_path_id == study_path_id)
        .order_by(Topic.order_index.asc())
        .all()
    )

    tasks: list[dict[str, Any]] = []
    priority = 1
    remaining_minutes = recommended_minutes

    def add_task(
        task_type: str,
        title: str,
        reason: str,
        estimated_minutes: int,
        topic_id: str | None = None,
        topic_title: str | None = None,
        concept_name: str | None = None,
        route_mode: str | None = None,
    ) -> None:
        nonlocal priority, remaining_minutes

        if remaining_minutes <= 0:
            return

        minutes = min(estimated_minutes, remaining_minutes)

        tasks.append(
            {
                "task_type": task_type,
                "title": title,
                "reason": reason,
                "topic_id": topic_id,
                "topic_title": topic_title,
                "concept_name": concept_name,
                "estimated_minutes": minutes,
                "priority": priority,
                "route_mode": route_mode,
            }
        )

        priority += 1
        remaining_minutes -= minutes

    due_reviews = (
        db.query(LearnerConceptState, Topic)
        .join(Topic, LearnerConceptState.topic_id == Topic.id)
        .filter(
            LearnerConceptState.user_id == user_id,
            Topic.study_path_id == study_path_id,
            LearnerConceptState.review_due_at.isnot(None),
            LearnerConceptState.review_due_at <= now,
        )
        .order_by(LearnerConceptState.review_due_at.asc())
        .limit(5)
        .all()
    )

    for state, topic in due_reviews:
        concept_name = (
            state.concept_name
            if state.concept_name != "overall_topic"
            else topic.title
        )

        add_task(
            task_type="review",
            title=f"Review {concept_name}",
            reason=state.review_reason
            or "This concept is due for a quick delayed check.",
            estimated_minutes=3,
            topic_id=str(topic.id),
            topic_title=topic.title,
            concept_name=concept_name,
            route_mode="review",
        )

    incomplete_repairs = (
        db.query(TargetedRepairAttempt, Topic)
        .join(Topic, TargetedRepairAttempt.topic_id == Topic.id)
        .filter(
            TargetedRepairAttempt.user_id == user_id,
            Topic.study_path_id == study_path_id,
            TargetedRepairAttempt.follow_up_completed == False,  # noqa: E712
        )
        .order_by(TargetedRepairAttempt.created_at.asc())
        .limit(3)
        .all()
    )

    for repair, topic in incomplete_repairs:
        add_task(
            task_type="repair_follow_up",
            title=f"Finish repair check: {repair.concept_name}",
            reason="Azalea gave a targeted repair and one quick follow-up is still open.",
            estimated_minutes=3,
            topic_id=str(topic.id),
            topic_title=topic.title,
            concept_name=repair.concept_name,
            route_mode="practice",
        )

    fragile_rows = (
        db.query(LearnerConceptState, Topic)
        .join(Topic, LearnerConceptState.topic_id == Topic.id)
        .filter(
            LearnerConceptState.user_id == user_id,
            Topic.study_path_id == study_path_id,
            LearnerConceptState.knowledge_state.in_(["fragile", "familiar"]),
        )
        .order_by(LearnerConceptState.updated_at.desc())
        .limit(5)
        .all()
    )

    already_added_concepts = {
        (task.get("topic_id"), task.get("concept_name")) for task in tasks
    }

    for state, topic in fragile_rows:
        concept_name = (
            state.concept_name
            if state.concept_name != "overall_topic"
            else topic.title
        )

        key = (str(topic.id), concept_name)

        if key in already_added_concepts:
            continue

        add_task(
            task_type="fragile_concept_check",
            title=f"Tighten {concept_name}",
            reason="This concept looks close, but not fully stable yet.",
            estimated_minutes=4,
            topic_id=str(topic.id),
            topic_title=topic.title,
            concept_name=concept_name,
            route_mode="review",
        )

    in_progress_topic = next(
        (topic for topic in topics if topic.status == "in_progress"),
        None,
    )

    if in_progress_topic:
        add_task(
            task_type="continue_topic",
            title=f"Continue {in_progress_topic.title}",
            reason="This topic is already in progress, so it is the cleanest next step.",
            estimated_minutes=max(
                5,
                min(in_progress_topic.estimated_minutes or 10, 12),
            ),
            topic_id=str(in_progress_topic.id),
            topic_title=in_progress_topic.title,
            concept_name=None,
            route_mode="learn",
        )

    next_topic = next(
        (topic for topic in topics if topic.status == "not_started"),
        None,
    )

    if next_topic:
        add_task(
            task_type="next_topic",
            title=f"Start {next_topic.title}",
            reason="This is the next topic in your study path sequence.",
            estimated_minutes=max(8, min(next_topic.estimated_minutes or 12, 15)),
            topic_id=str(next_topic.id),
            topic_title=next_topic.title,
            concept_name=None,
            route_mode="learn",
        )

    stable_or_transferable = (
        db.query(LearnerConceptState, Topic)
        .join(Topic, LearnerConceptState.topic_id == Topic.id)
        .filter(
            LearnerConceptState.user_id == user_id,
            Topic.study_path_id == study_path_id,
            LearnerConceptState.knowledge_state.in_(["stable", "transferable"]),
        )
        .order_by(LearnerConceptState.updated_at.desc())
        .first()
    )

    if stable_or_transferable:
        state, topic = stable_or_transferable
        concept_name = (
            state.concept_name
            if state.concept_name != "overall_topic"
            else topic.title
        )

        add_task(
            task_type="transfer_challenge",
            title=f"Try a transfer check on {concept_name}",
            reason="This concept looks stable enough to test in a new context.",
            estimated_minutes=5,
            topic_id=str(topic.id),
            topic_title=topic.title,
            concept_name=concept_name,
            route_mode="practice",
        )

    if tasks:
        summary = build_plan_summary(tasks)
    elif topics:
        summary = "No urgent reviews are due. Continue with the next topic when you are ready."
    else:
        summary = "Generate topics first so Azalea can build a daily plan."

    return {
        "study_path_id": study_path_id,
        "recommended_minutes": recommended_minutes,
        "summary": summary,
        "tasks": tasks,
    }


def build_plan_summary(tasks: list[dict[str, Any]]) -> str:
    review_count = sum(
        1
        for task in tasks
        if task["task_type"] in {"review", "fragile_concept_check"}
    )
    repair_count = sum(
        1 for task in tasks if task["task_type"] == "repair_follow_up"
    )
    lesson_count = sum(
        1
        for task in tasks
        if task["task_type"] in {"continue_topic", "next_topic"}
    )
    transfer_count = sum(
        1 for task in tasks if task["task_type"] == "transfer_challenge"
    )

    parts: list[str] = []

    if review_count:
        parts.append(f"{review_count} review check{'s' if review_count != 1 else ''}")

    if repair_count:
        parts.append(
            f"{repair_count} repair follow-up{'s' if repair_count != 1 else ''}"
        )

    if lesson_count:
        parts.append(f"{lesson_count} lesson step{'s' if lesson_count != 1 else ''}")

    if transfer_count:
        parts.append(
            f"{transfer_count} transfer challenge{'s' if transfer_count != 1 else ''}"
        )

    if not parts:
        return "Azalea did not find any high-priority work."

    return "Recommended today: " + ", ".join(parts) + "."


def build_class_adaptive_plan(
    db: Session,
    user_id: str,
    class_id: str,
    target_minutes: int | None = None,
) -> dict[str, Any]:
    recommended_minutes = target_minutes or 30

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
            "class_id": class_id,
            "recommended_minutes": recommended_minutes,
            "summary": "Class not found.",
            "tasks": [],
        }

    study_paths = list(azalea_class.study_paths or [])

    tasks: list[dict[str, Any]] = []
    priority = 1
    remaining_minutes = recommended_minutes

    def add_task(
        task_type: str,
        title: str,
        reason: str,
        estimated_minutes: int,
        study_path_id: str | None = None,
        study_path_title: str | None = None,
        topic_id: str | None = None,
        topic_title: str | None = None,
        concept_name: str | None = None,
        route_mode: str | None = None,
    ) -> None:
        nonlocal priority, remaining_minutes

        if remaining_minutes <= 0:
            return

        minutes = min(estimated_minutes, remaining_minutes)

        tasks.append(
            {
                "task_type": task_type,
                "title": title,
                "reason": reason,
                "class_id": class_id,
                "study_path_id": study_path_id,
                "study_path_title": study_path_title,
                "topic_id": topic_id,
                "topic_title": topic_title,
                "concept_name": concept_name,
                "estimated_minutes": minutes,
                "priority": priority,
                "route_mode": route_mode,
            }
        )

        priority += 1
        remaining_minutes -= minutes

    now = datetime.now(timezone.utc)
    study_path_ids = [str(path.id) for path in study_paths]

    if not study_path_ids:
        return {
            "class_id": class_id,
            "recommended_minutes": recommended_minutes,
            "summary": "Add or create study paths so Azalea can plan work for this class.",
            "tasks": [],
        }

    # 1. Due reviews across the whole class
    due_reviews = (
        db.query(LearnerConceptState, Topic, StudyPath)
        .join(Topic, LearnerConceptState.topic_id == Topic.id)
        .join(StudyPath, Topic.study_path_id == StudyPath.id)
        .filter(
            LearnerConceptState.user_id == user_id,
            Topic.study_path_id.in_(study_path_ids),
            LearnerConceptState.review_due_at.isnot(None),
            LearnerConceptState.review_due_at <= now,
        )
        .order_by(LearnerConceptState.review_due_at.asc())
        .limit(6)
        .all()
    )

    for state, topic, path in due_reviews:
        concept_name = (
            state.concept_name
            if state.concept_name != "overall_topic"
            else topic.title
        )

        add_task(
            task_type="review",
            title=f"Review {concept_name}",
            reason=state.review_reason
            or "This concept is due for a quick delayed check.",
            estimated_minutes=3,
            study_path_id=str(path.id),
            study_path_title=path.title,
            topic_id=str(topic.id),
            topic_title=topic.title,
            concept_name=concept_name,
            route_mode="review",
        )

    # 2. Open targeted repair follow-ups
    incomplete_repairs = (
        db.query(TargetedRepairAttempt, Topic, StudyPath)
        .join(Topic, TargetedRepairAttempt.topic_id == Topic.id)
        .join(StudyPath, Topic.study_path_id == StudyPath.id)
        .filter(
            TargetedRepairAttempt.user_id == user_id,
            Topic.study_path_id.in_(study_path_ids),
            TargetedRepairAttempt.follow_up_completed == False,  # noqa: E712
        )
        .order_by(TargetedRepairAttempt.created_at.asc())
        .limit(4)
        .all()
    )

    for repair, topic, path in incomplete_repairs:
        add_task(
            task_type="repair_follow_up",
            title=f"Finish repair check: {repair.concept_name}",
            reason="Azalea gave a targeted repair and one quick follow-up is still open.",
            estimated_minutes=3,
            study_path_id=str(path.id),
            study_path_title=path.title,
            topic_id=str(topic.id),
            topic_title=topic.title,
            concept_name=repair.concept_name,
            route_mode="practice",
        )

    # 3. Fragile concepts
    fragile_rows = (
        db.query(LearnerConceptState, Topic, StudyPath)
        .join(Topic, LearnerConceptState.topic_id == Topic.id)
        .join(StudyPath, Topic.study_path_id == StudyPath.id)
        .filter(
            LearnerConceptState.user_id == user_id,
            Topic.study_path_id.in_(study_path_ids),
            LearnerConceptState.knowledge_state.in_(["fragile", "familiar"]),
        )
        .order_by(LearnerConceptState.updated_at.desc())
        .limit(6)
        .all()
    )

    already_added = {
        (task.get("topic_id"), task.get("concept_name")) for task in tasks
    }

    for state, topic, path in fragile_rows:
        concept_name = (
            state.concept_name
            if state.concept_name != "overall_topic"
            else topic.title
        )

        key = (str(topic.id), concept_name)

        if key in already_added:
            continue

        add_task(
            task_type="fragile_concept_check",
            title=f"Tighten {concept_name}",
            reason="This concept looks close, but not fully stable yet.",
            estimated_minutes=4,
            study_path_id=str(path.id),
            study_path_title=path.title,
            topic_id=str(topic.id),
            topic_title=topic.title,
            concept_name=concept_name,
            route_mode="review",
        )

    # 4. In-progress topic across class
    in_progress_topic = (
        db.query(Topic, StudyPath)
        .join(StudyPath, Topic.study_path_id == StudyPath.id)
        .filter(
            Topic.study_path_id.in_(study_path_ids),
            Topic.status == "in_progress",
        )
        .order_by(Topic.created_at.asc())
        .first()
    )

    if in_progress_topic:
        topic, path = in_progress_topic

        add_task(
            task_type="continue_topic",
            title=f"Continue {topic.title}",
            reason=f"This topic is already in progress in {path.title}.",
            estimated_minutes=max(5, min(topic.estimated_minutes or 10, 12)),
            study_path_id=str(path.id),
            study_path_title=path.title,
            topic_id=str(topic.id),
            topic_title=topic.title,
            route_mode="learn",
        )

    # 5. Next not-started topic
    next_topic = (
        db.query(Topic, StudyPath)
        .join(StudyPath, Topic.study_path_id == StudyPath.id)
        .filter(
            Topic.study_path_id.in_(study_path_ids),
            Topic.status == "not_started",
        )
        .order_by(StudyPath.created_at.asc(), Topic.order_index.asc())
        .first()
    )

    if next_topic:
        topic, path = next_topic

        add_task(
            task_type="next_topic",
            title=f"Start {topic.title}",
            reason=f"This is the next untouched topic in {path.title}.",
            estimated_minutes=max(8, min(topic.estimated_minutes or 12, 15)),
            study_path_id=str(path.id),
            study_path_title=path.title,
            topic_id=str(topic.id),
            topic_title=topic.title,
            route_mode="learn",
        )

    # 6. Transfer challenge
    stable_or_transferable = (
        db.query(LearnerConceptState, Topic, StudyPath)
        .join(Topic, LearnerConceptState.topic_id == Topic.id)
        .join(StudyPath, Topic.study_path_id == StudyPath.id)
        .filter(
            LearnerConceptState.user_id == user_id,
            Topic.study_path_id.in_(study_path_ids),
            LearnerConceptState.knowledge_state.in_(["stable", "transferable"]),
        )
        .order_by(LearnerConceptState.updated_at.desc())
        .first()
    )

    if stable_or_transferable:
        state, topic, path = stable_or_transferable

        concept_name = (
            state.concept_name
            if state.concept_name != "overall_topic"
            else topic.title
        )

        add_task(
            task_type="transfer_challenge",
            title=f"Try a transfer check on {concept_name}",
            reason="This concept looks stable enough to test in a new context.",
            estimated_minutes=5,
            study_path_id=str(path.id),
            study_path_title=path.title,
            topic_id=str(topic.id),
            topic_title=topic.title,
            concept_name=concept_name,
            route_mode="practice",
        )

    if tasks:
        summary = build_plan_summary(tasks)
    else:
        summary = "No urgent work is due. Continue with the next topic when ready."

    return {
        "class_id": class_id,
        "recommended_minutes": recommended_minutes,
        "summary": summary,
        "tasks": tasks,
    }
