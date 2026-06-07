from datetime import datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.azalea_class import AzaleaClass
from app.models.content_chunk import ContentChunk
from app.models.learning_material import LearningMaterial
from app.models.study_path import StudyPath
from app.models.study_session import StudySession
from app.models.topic import Topic
from app.schemas.azalea_class import ClassCreate, ClassRead, ClassUpdate
from app.schemas.class_daily_plan import ClassDailyPlanRead, ClassDailyPlanTaskRead
from app.schemas.class_qa import ClassQARequest, ClassQAResponse, ClassQASource
from app.schemas.class_recommendation import (
    ClassRecommendationRead,
    ClassRecommendedStudyPathRead,
    ClassRecommendedTopicRead,
)
from app.schemas.study_path import StudyPathRead
from app.services.class_qa import answer_class_question

router = APIRouter()


def get_user_id(current_user: dict[str, Any]) -> str:
    return str(current_user["user_id"])


def get_owned_class(
    class_id: str,
    db: Session,
    current_user: dict[str, Any],
) -> AzaleaClass:
    azalea_class = (
        db.query(AzaleaClass)
        .filter(AzaleaClass.id == class_id)
        .filter(AzaleaClass.user_id == get_user_id(current_user))
        .first()
    )

    if not azalea_class:
        raise HTTPException(status_code=404, detail="Class not found")

    return azalea_class


def get_owned_study_path(
    study_path_id: str,
    db: Session,
    current_user: dict[str, Any],
) -> StudyPath:
    study_path = (
        db.query(StudyPath)
        .filter(StudyPath.id == study_path_id)
        .filter(StudyPath.user_id == get_user_id(current_user))
        .first()
    )

    if not study_path:
        raise HTTPException(status_code=404, detail="Study path not found")

    return study_path


def build_class_pacing_payload(
    azalea_class: AzaleaClass,
    db: Session,
) -> dict:
    today_start = datetime.combine(datetime.now().date(), time.min)
    today_end = datetime.combine(datetime.now().date(), time.max)

    today_sessions = (
        db.query(StudySession)
        .filter(StudySession.class_id == azalea_class.id)
        .filter(StudySession.created_at >= today_start)
        .filter(StudySession.created_at <= today_end)
        .all()
    )

    today_minutes = sum(session.minutes_spent for session in today_sessions)

    today = datetime.now().date()
    week_start_date = today - timedelta(days=today.weekday())
    week_start = datetime.combine(week_start_date, time.min)
    week_end = datetime.combine(today, time.max)

    week_sessions = (
        db.query(StudySession)
        .filter(StudySession.class_id == azalea_class.id)
        .filter(StudySession.created_at >= week_start)
        .filter(StudySession.created_at <= week_end)
        .all()
    )

    week_minutes = sum(session.minutes_spent for session in week_sessions)

    daily_goal_minutes = azalea_class.daily_goal_minutes
    weekly_goal_minutes = azalea_class.weekly_goal_minutes

    remaining_today_minutes = max(
        0,
        (daily_goal_minutes or 0) - today_minutes,
    )

    remaining_week_minutes = max(
        0,
        (weekly_goal_minutes or 0) - week_minutes,
    )

    return {
        "today_minutes": today_minutes,
        "daily_goal_minutes": daily_goal_minutes,
        "remaining_today_minutes": remaining_today_minutes,
        "week_minutes": week_minutes,
        "weekly_goal_minutes": weekly_goal_minutes,
        "remaining_week_minutes": remaining_week_minutes,
        "deadline": azalea_class.deadline,
    }


def build_class_recommendation_response(
    topic: Topic,
    study_path: StudyPath,
    message: str,
    azalea_class: AzaleaClass,
    db: Session,
) -> ClassRecommendationRead:
    pacing_payload = build_class_pacing_payload(azalea_class, db)

    return ClassRecommendationRead(
        message=message,
        topic=ClassRecommendedTopicRead(
            id=str(topic.id),
            title=topic.title,
            status=topic.status,
            estimated_minutes=topic.estimated_minutes,
        ),
        study_path=ClassRecommendedStudyPathRead(
            id=str(study_path.id),
            title=study_path.title,
        ),
        is_complete=False,
        **pacing_payload,
    )


def get_class_topics_with_paths(
    azalea_class: AzaleaClass,
    db: Session,
) -> list[tuple[Topic, StudyPath]]:
    study_paths = azalea_class.study_paths

    if not study_paths:
        return []

    study_path_ids = [study_path.id for study_path in study_paths]

    topics = (
        db.query(Topic)
        .filter(Topic.study_path_id.in_(study_path_ids))
        .order_by(Topic.order_index.asc())
        .all()
    )

    study_path_by_id = {str(study_path.id): study_path for study_path in study_paths}

    topic_pairs: list[tuple[Topic, StudyPath]] = []

    for topic in topics:
        study_path = study_path_by_id.get(str(topic.study_path_id))

        if study_path:
            topic_pairs.append((topic, study_path))

    return topic_pairs


def is_topic_review_due(topic: Topic) -> bool:
    if not topic.review_due_at:
        return False

    return topic.review_due_at <= datetime.now()


def build_daily_plan_tasks(
    topic_pairs: list[tuple[Topic, StudyPath]],
    remaining_today_minutes: int,
) -> list[ClassDailyPlanTaskRead]:
    if remaining_today_minutes <= 0:
        return []

    tasks: list[ClassDailyPlanTaskRead] = []
    planned_minutes = 0

    due_review_pairs = [
        (topic, study_path)
        for topic, study_path in topic_pairs
        if is_topic_review_due(topic)
    ]

    for topic, study_path in due_review_pairs:
        if planned_minutes >= remaining_today_minutes:
            return tasks

        estimated_minutes = min(
            topic.estimated_minutes or 10,
            max(5, remaining_today_minutes - planned_minutes),
        )

        tasks.append(
            ClassDailyPlanTaskRead(
                task_type="review_due",
                title=topic.title,
                reason=topic.review_reason
                or "This topic is due for a spaced review check.",
                study_path_id=str(study_path.id),
                study_path_title=study_path.title,
                topic_id=str(topic.id),
                topic_status=topic.status,
                estimated_minutes=estimated_minutes,
            )
        )

        planned_minutes += estimated_minutes

    priority_groups = [
        (
            "review",
            "needs_review",
            "This topic is marked as needing review.",
        ),
        (
            "continue",
            "in_progress",
            "You already started this topic.",
        ),
        (
            "start",
            "not_started",
            "This is the next unfinished topic.",
        ),
    ]

    due_review_topic_ids = {str(topic.id) for topic, _ in due_review_pairs}

    for task_type, status, reason in priority_groups:
        for topic, study_path in topic_pairs:
            if str(topic.id) in due_review_topic_ids:
                continue

            if topic.status != status:
                continue

            if planned_minutes >= remaining_today_minutes:
                return tasks

            estimated_minutes = topic.estimated_minutes or 10
            minutes_for_task = min(
                estimated_minutes,
                max(5, remaining_today_minutes - planned_minutes),
            )

            tasks.append(
                ClassDailyPlanTaskRead(
                    task_type=task_type,
                    title=topic.title,
                    reason=reason,
                    study_path_id=str(study_path.id),
                    study_path_title=study_path.title,
                    topic_id=str(topic.id),
                    topic_status=topic.status,
                    estimated_minutes=minutes_for_task,
                )
            )

            planned_minutes += minutes_for_task

            if planned_minutes >= remaining_today_minutes:
                return tasks

    return tasks


@router.post("/", response_model=ClassRead)
def create_class(
    payload: ClassCreate,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    azalea_class = AzaleaClass(
        user_id=get_user_id(current_user),
        name=payload.name,
        description=payload.description,
        deadline=payload.deadline,
        daily_goal_minutes=payload.daily_goal_minutes,
        weekly_goal_minutes=payload.weekly_goal_minutes,
    )

    db.add(azalea_class)
    db.commit()
    db.refresh(azalea_class)

    return azalea_class


@router.get("/", response_model=list[ClassRead])
def list_classes(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    return (
        db.query(AzaleaClass)
        .filter(AzaleaClass.user_id == get_user_id(current_user))
        .order_by(AzaleaClass.created_at.desc())
        .all()
    )


@router.get("/{class_id}", response_model=ClassRead)
def get_class(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    return get_owned_class(
        class_id=class_id,
        db=db,
        current_user=current_user,
    )


@router.patch("/{class_id}", response_model=ClassRead)
def update_class(
    class_id: str,
    payload: ClassUpdate,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    azalea_class = get_owned_class(
        class_id=class_id,
        db=db,
        current_user=current_user,
    )

    update_data = payload.model_dump(exclude_unset=True)

    if "name" in update_data:
        if update_data["name"] is not None and not update_data["name"].strip():
            raise HTTPException(status_code=400, detail="Class name cannot be empty")

        azalea_class.name = update_data["name"]

    if "description" in update_data:
        azalea_class.description = update_data["description"]

    if "deadline" in update_data:
        azalea_class.deadline = update_data["deadline"]

    if "daily_goal_minutes" in update_data:
        if (
            update_data["daily_goal_minutes"] is not None
            and update_data["daily_goal_minutes"] < 0
        ):
            raise HTTPException(
                status_code=400,
                detail="daily_goal_minutes cannot be negative",
            )

        azalea_class.daily_goal_minutes = update_data["daily_goal_minutes"]

    if "weekly_goal_minutes" in update_data:
        if (
            update_data["weekly_goal_minutes"] is not None
            and update_data["weekly_goal_minutes"] < 0
        ):
            raise HTTPException(
                status_code=400,
                detail="weekly_goal_minutes cannot be negative",
            )

        azalea_class.weekly_goal_minutes = update_data["weekly_goal_minutes"]

    db.commit()
    db.refresh(azalea_class)

    return azalea_class


@router.get("/{class_id}/recommendation", response_model=ClassRecommendationRead)
def get_class_recommendation(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    azalea_class = get_owned_class(
        class_id=class_id,
        db=db,
        current_user=current_user,
    )

    pacing_payload = build_class_pacing_payload(azalea_class, db)

    study_paths = [
        study_path
        for study_path in azalea_class.study_paths
        if study_path.user_id == get_user_id(current_user)
    ]

    if not study_paths:
        return ClassRecommendationRead(
            message="Create or attach a study path first so Azalea can recommend what to study today.",
            topic=None,
            study_path=None,
            is_complete=False,
            **pacing_payload,
        )

    topic_pairs = get_class_topics_with_paths(azalea_class, db)

    if not topic_pairs:
        return ClassRecommendationRead(
            message="Generate topics in one of this class's study paths so Azalea can recommend what to study today.",
            topic=None,
            study_path=None,
            is_complete=False,
            **pacing_payload,
        )

    due_review_pair = next(
        (
            (topic, study_path)
            for topic, study_path in topic_pairs
            if is_topic_review_due(topic)
        ),
        None,
    )

    if due_review_pair:
        topic, study_path = due_review_pair
        remaining_today = pacing_payload["remaining_today_minutes"]

        if remaining_today > 0:
            message = (
                "Review this topic today because it is due for a spaced check. "
                f"You have {remaining_today} minutes left to hit today's study goal."
            )
        else:
            message = (
                "This topic is due for a spaced review check. "
                "You already hit today's study goal."
            )

        return build_class_recommendation_response(
            topic=topic,
            study_path=study_path,
            message=message,
            azalea_class=azalea_class,
            db=db,
        )

    needs_review_pair = next(
        (
            (topic, study_path)
            for topic, study_path in topic_pairs
            if topic.status == "needs_review"
        ),
        None,
    )

    if needs_review_pair:
        topic, study_path = needs_review_pair
        remaining_today = pacing_payload["remaining_today_minutes"]

        if remaining_today > 0:
            message = (
                "Review this topic today because it needs more work. "
                f"You have {remaining_today} minutes left to hit today's study goal."
            )
        else:
            message = (
                "Review this topic because it needs more work. "
                "You already hit today's study goal."
            )

        return build_class_recommendation_response(
            topic=topic,
            study_path=study_path,
            message=message,
            azalea_class=azalea_class,
            db=db,
        )

    in_progress_pair = next(
        (
            (topic, study_path)
            for topic, study_path in topic_pairs
            if topic.status == "in_progress"
        ),
        None,
    )

    if in_progress_pair:
        topic, study_path = in_progress_pair
        remaining_today = pacing_payload["remaining_today_minutes"]

        if remaining_today > 0:
            message = (
                "Continue this topic today because you have already started it. "
                f"Try to study for {remaining_today} more minutes today."
            )
        else:
            message = (
                "Continue this topic when you are ready. "
                "You already hit today's study goal."
            )

        return build_class_recommendation_response(
            topic=topic,
            study_path=study_path,
            message=message,
            azalea_class=azalea_class,
            db=db,
        )

    not_started_pair = next(
        (
            (topic, study_path)
            for topic, study_path in topic_pairs
            if topic.status == "not_started"
        ),
        None,
    )

    if not_started_pair:
        topic, study_path = not_started_pair
        remaining_today = pacing_payload["remaining_today_minutes"]

        if remaining_today > 0:
            message = (
                "Start this topic today because it is the next unfinished topic in this class. "
                f"Aim for {remaining_today} more minutes today."
            )
        else:
            message = (
                "This is the next unfinished topic in this class. "
                "You already hit today's study goal, so this can be your next topic."
            )

        return build_class_recommendation_response(
            topic=topic,
            study_path=study_path,
            message=message,
            azalea_class=azalea_class,
            db=db,
        )

    incomplete_pair = next(
        (
            (topic, study_path)
            for topic, study_path in topic_pairs
            if topic.status != "completed"
        ),
        None,
    )

    if incomplete_pair:
        topic, study_path = incomplete_pair
        remaining_today = pacing_payload["remaining_today_minutes"]

        if remaining_today > 0:
            message = (
                "Work on this topic today because it is not completed yet. "
                f"You have {remaining_today} minutes left for today's goal."
            )
        else:
            message = (
                "Work on this topic next because it is not completed yet. "
                "You already hit today's study goal."
            )

        return build_class_recommendation_response(
            topic=topic,
            study_path=study_path,
            message=message,
            azalea_class=azalea_class,
            db=db,
        )

    return ClassRecommendationRead(
        message="All study paths in this class look complete. Review past practice attempts or generate more practice if needed.",
        topic=None,
        study_path=None,
        is_complete=True,
        **pacing_payload,
    )


@router.get("/{class_id}/daily-plan", response_model=ClassDailyPlanRead)
def get_class_daily_plan(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    azalea_class = get_owned_class(
        class_id=class_id,
        db=db,
        current_user=current_user,
    )

    pacing_payload = build_class_pacing_payload(azalea_class, db)

    topic_pairs = get_class_topics_with_paths(azalea_class, db)

    tasks = build_daily_plan_tasks(
        topic_pairs=topic_pairs,
        remaining_today_minutes=pacing_payload["remaining_today_minutes"],
    )

    return ClassDailyPlanRead(
        class_id=str(azalea_class.id),
        today_minutes=pacing_payload["today_minutes"],
        daily_goal_minutes=pacing_payload["daily_goal_minutes"],
        remaining_today_minutes=pacing_payload["remaining_today_minutes"],
        tasks=tasks,
    )


@router.post("/{class_id}/study-paths/{study_path_id}", response_model=ClassRead)
def add_study_path_to_class(
    class_id: str,
    study_path_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    azalea_class = get_owned_class(
        class_id=class_id,
        db=db,
        current_user=current_user,
    )

    study_path = get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )

    if study_path not in azalea_class.study_paths:
        azalea_class.study_paths.append(study_path)

    db.commit()
    db.refresh(azalea_class)

    return azalea_class


@router.get("/{class_id}/study-paths", response_model=list[StudyPathRead])
def list_class_study_paths(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    azalea_class = get_owned_class(
        class_id=class_id,
        db=db,
        current_user=current_user,
    )

    return [
        study_path
        for study_path in azalea_class.study_paths
        if study_path.user_id == get_user_id(current_user)
    ]


@router.post("/{class_id}/qa", response_model=ClassQAResponse)
def ask_class_question(
    class_id: str,
    payload: ClassQARequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    azalea_class = get_owned_class(
        class_id=class_id,
        db=db,
        current_user=current_user,
    )

    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    chunks = (
        db.query(ContentChunk)
        .join(ContentChunk.material)
        .filter(ContentChunk.material.has(LearningMaterial.class_id == azalea_class.id))
        .order_by(ContentChunk.chunk_index.asc())
        .limit(8)
        .all()
    )

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No uploaded material chunks found for this class.",
        )

    try:
        result = answer_class_question(
            question=payload.question,
            chunks=chunks,
        )

        used_source_numbers = {
            int(source_number)
            for source_number in result.get("used_chunk_indexes", [])
            if str(source_number).isdigit()
        }

        if used_source_numbers:
            source_chunks = [
                chunk
                for index, chunk in enumerate(chunks, start=1)
                if index in used_source_numbers
            ]
        else:
            source_chunks = chunks[:3]

        sources: list[ClassQASource] = []

        for chunk in source_chunks[:5]:
            material_title = chunk.material.title if chunk.material else "Unknown material"
            material_filename = chunk.material.filename if chunk.material else None
            filename_text = f" ({material_filename})" if material_filename else ""

            sources.append(
                ClassQASource(
                    chunk_id=str(chunk.id),
                    material_id=str(chunk.material_id),
                    material_title=material_title,
                    material_filename=material_filename,
                    chunk_index=chunk.chunk_index,
                    source_label=(
                        f"{material_title}{filename_text}, "
                        f"chunk {chunk.chunk_index}"
                    ),
                    preview=chunk.text[:280],
                )
            )

        return ClassQAResponse(
            answer=result["answer"],
            sources=sources,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to answer class question: {str(exc)}",
        )
