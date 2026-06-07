from datetime import datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.ownership import get_owned_class, get_owned_study_path, get_owned_topic
from app.models.associations import class_study_paths
from app.models.azalea_class import AzaleaClass
from app.models.study_path import StudyPath
from app.models.study_session import StudySession
from app.models.topic import Topic
from app.schemas.study_session import (
    StudySessionCreate,
    StudySessionRead,
    StudySessionSummary,
)

router = APIRouter()

VALID_ACTIVITY_TYPES = {"lesson", "practice", "qa", "review", "regeneration"}


def build_summary(sessions: list[StudySession]) -> StudySessionSummary:
    lesson_minutes = sum(
        session.minutes_spent
        for session in sessions
        if session.activity_type == "lesson"
    )
    practice_minutes = sum(
        session.minutes_spent
        for session in sessions
        if session.activity_type == "practice"
    )
    qa_minutes = sum(
        session.minutes_spent
        for session in sessions
        if session.activity_type == "qa"
    )
    review_minutes = sum(
        session.minutes_spent
        for session in sessions
        if session.activity_type == "review"
    )
    regeneration_minutes = sum(
        session.minutes_spent
        for session in sessions
        if session.activity_type == "regeneration"
    )

    return StudySessionSummary(
        total_minutes=sum(session.minutes_spent for session in sessions),
        lesson_minutes=lesson_minutes,
        practice_minutes=practice_minutes,
        qa_minutes=qa_minutes,
        review_minutes=review_minutes,
        regeneration_minutes=regeneration_minutes,
        session_count=len(sessions),
    )


def study_path_belongs_to_class(study_path: StudyPath, class_id: str) -> bool:
    return any(str(azalea_class.id) == str(class_id) for azalea_class in study_path.classes)


@router.post("/", response_model=StudySessionRead)
def create_study_session(
    payload: StudySessionCreate,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    activity_type = payload.activity_type.strip().lower()

    if activity_type not in VALID_ACTIVITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid activity_type. Must be one of: "
                "lesson, practice, qa, review, regeneration."
            ),
        )

    if (
        payload.class_id is None
        and payload.study_path_id is None
        and payload.topic_id is None
    ):
        raise HTTPException(
            status_code=400,
            detail="At least one of class_id, study_path_id, or topic_id is required.",
        )

    inferred_class_id = payload.class_id
    study_path: StudyPath | None = None
    topic: Topic | None = None

    if payload.class_id is not None:
        get_owned_class(
            class_id=payload.class_id,
            db=db,
            current_user=current_user,
        )

    if payload.study_path_id is not None:
        study_path = get_owned_study_path(
            study_path_id=payload.study_path_id,
            db=db,
            current_user=current_user,
        )

        if inferred_class_id is None:
            class_link = (
                db.query(class_study_paths)
                .join(
                    AzaleaClass,
                    AzaleaClass.id == class_study_paths.c.class_id,
                )
                .filter(class_study_paths.c.study_path_id == payload.study_path_id)
                .filter(AzaleaClass.user_id == study_path.user_id)
                .first()
            )

            if class_link:
                inferred_class_id = class_link.class_id

    if payload.topic_id is not None:
        topic = get_owned_topic(
            topic_id=payload.topic_id,
            db=db,
            current_user=current_user,
        )

        if study_path is not None and str(topic.study_path_id) != str(study_path.id):
            raise HTTPException(
                status_code=400,
                detail="Topic does not belong to the provided study path.",
            )

        if payload.study_path_id is None:
            study_path = topic.study_path

    if inferred_class_id is not None and study_path is not None:
        if not study_path_belongs_to_class(study_path=study_path, class_id=inferred_class_id):
            raise HTTPException(
                status_code=400,
                detail="Study path does not belong to the provided class.",
            )

    session = StudySession(
        class_id=inferred_class_id,
        study_path_id=payload.study_path_id or (str(study_path.id) if study_path else None),
        topic_id=payload.topic_id,
        minutes_spent=payload.minutes_spent,
        activity_type=activity_type,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


@router.get("/study-path/{study_path_id}", response_model=list[StudySessionRead])
def get_study_path_sessions(
    study_path_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )

    return (
        db.query(StudySession)
        .filter(StudySession.study_path_id == study_path_id)
        .order_by(StudySession.created_at.desc())
        .all()
    )


@router.get("/study-path/{study_path_id}/summary", response_model=StudySessionSummary)
def get_study_path_session_summary(
    study_path_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )

    sessions = (
        db.query(StudySession)
        .filter(StudySession.study_path_id == study_path_id)
        .all()
    )

    return build_summary(sessions)


@router.get("/class/{class_id}", response_model=list[StudySessionRead])
def get_class_sessions(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_class(class_id=class_id, db=db, current_user=current_user)

    return (
        db.query(StudySession)
        .filter(StudySession.class_id == class_id)
        .order_by(StudySession.created_at.desc())
        .all()
    )


@router.get("/class/{class_id}/summary", response_model=StudySessionSummary)
def get_class_session_summary(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_class(class_id=class_id, db=db, current_user=current_user)

    sessions = db.query(StudySession).filter(StudySession.class_id == class_id).all()

    return build_summary(sessions)


@router.get("/class/{class_id}/today", response_model=StudySessionSummary)
def get_class_today_session_summary(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_class(class_id=class_id, db=db, current_user=current_user)

    today_start = datetime.combine(datetime.now().date(), time.min)
    today_end = datetime.combine(datetime.now().date(), time.max)

    sessions = (
        db.query(StudySession)
        .filter(StudySession.class_id == class_id)
        .filter(StudySession.created_at >= today_start)
        .filter(StudySession.created_at <= today_end)
        .all()
    )

    return build_summary(sessions)


@router.get("/class/{class_id}/week", response_model=StudySessionSummary)
def get_class_week_session_summary(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_class(class_id=class_id, db=db, current_user=current_user)

    today = datetime.now().date()
    week_start_date = today - timedelta(days=today.weekday())

    week_start = datetime.combine(week_start_date, time.min)
    week_end = datetime.combine(today, time.max)

    sessions = (
        db.query(StudySession)
        .filter(StudySession.class_id == class_id)
        .filter(StudySession.created_at >= week_start)
        .filter(StudySession.created_at <= week_end)
        .all()
    )

    return build_summary(sessions)


@router.get("/topic/{topic_id}", response_model=list[StudySessionRead])
def get_topic_sessions(
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)

    return (
        db.query(StudySession)
        .filter(StudySession.topic_id == topic_id)
        .order_by(StudySession.created_at.desc())
        .all()
    )
