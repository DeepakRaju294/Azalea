from datetime import datetime, timedelta
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.ownership import (
    get_owned_class,
    get_owned_lesson,
    get_owned_study_path,
    get_owned_topic,
)
from app.models.practice_attempt import PracticeAttempt
from app.models.study_path import StudyPath
from app.models.topic import Topic
from app.schemas.practice import (
    CodeRunRequest,
    CodeRunResponse,
    PracticeAttemptRead,
    PracticeHintRequest,
    PracticeHintResponse,
    PracticeSubmitRequest,
    PracticeSubmitResponse,
)
from app.schemas.weak_area import (
    SpacedReviewQuestionRequest,
    SpacedReviewQuestionResponse,
    WeakAreaQuestionRequest,
    WeakAreaQuestionResponse,
    WeakAreaRead,
    WeakAreaSummaryRead,
)
from app.services.code_runner import run_code_against_tests
from app.services.practice_evaluator import (
    evaluate_practice_answer,
    generate_practice_hint,
    generate_spaced_review_question,
    generate_weak_area_question,
)

router = APIRouter(prefix="/practice", tags=["Practice"])


@router.post("/run-code", response_model=CodeRunResponse)
def run_practice_code(
    payload: CodeRunRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    if not payload.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty.")

    return run_code_against_tests(
        code=payload.code,
        language=payload.language,
        test_cases=[test_case.model_dump() for test_case in payload.test_cases],
    )


def recalculate_study_path_progress(db: Session, study_path_id: str) -> None:
    topics = db.query(Topic).filter(Topic.study_path_id == study_path_id).all()
    study_path = db.query(StudyPath).filter(StudyPath.id == study_path_id).first()

    if not study_path:
        return

    if not topics:
        study_path.progress_percent = 0
        study_path.estimated_minutes_remaining = None
        return

    completed_count = sum(1 for topic in topics if topic.status == "completed")

    study_path.progress_percent = round((completed_count / len(topics)) * 100)

    study_path.estimated_minutes_remaining = sum(
        topic.estimated_minutes or 0
        for topic in topics
        if topic.status != "completed"
    )


def apply_practice_result_to_topic(topic: Topic, performance_level: str) -> None:
    now = datetime.utcnow()

    if performance_level == "strong":
        topic.status = "completed"
        topic.review_due_at = now + timedelta(days=1)
        topic.review_reason = "Strong answer. Scheduled delayed check."

    elif performance_level == "fragile":
        topic.status = "in_progress"
        topic.review_due_at = now + timedelta(hours=12)
        topic.review_reason = "Fragile answer. Scheduled quick variation check."

    elif performance_level == "minor_mistake":
        topic.status = "in_progress"

    elif performance_level == "weak":
        topic.status = "needs_review"

    else:
        topic.status = "in_progress"


def build_adaptive_practice_response(
    evaluation: dict[str, Any],
    topic: Topic,
) -> dict[str, Any]:
    performance_level = evaluation.get("performance_level") or "weak"
    next_action = evaluation.get("next_action") or "minimal_repair"
    concept_to_review = evaluation.get("mistake_type") or getattr(topic, "title", None)

    if performance_level == "strong":
        message = "You can move on. Azalea will schedule a later check so the idea stays durable."
        should_continue = True
        should_generate_repair = False
        suggested_mode = "continue"
    elif performance_level == "fragile":
        message = "You have the idea, but it is still a little fragile. Do one edge-case variation before moving on."
        should_continue = False
        should_generate_repair = False
        suggested_mode = "edge_case_check"
    elif performance_level == "minor_mistake":
        message = "Small miss. Fix the specific detail, then retry a nearby version."
        should_continue = False
        should_generate_repair = True
        suggested_mode = "targeted_follow_up"
    else:
        message = "This looks like a weak spot. Do a minimal repair before more practice."
        should_continue = False
        should_generate_repair = True
        suggested_mode = "minimal_repair"

    return {
        "message": message,
        "performance_level": performance_level,
        "next_action": next_action,
        "suggested_mode": suggested_mode,
        "should_continue": should_continue,
        "should_generate_repair": should_generate_repair,
        "concept_to_review": concept_to_review,
        "follow_up_question": evaluation.get("follow_up_question"),
        "review_scheduled_at": (
            topic.review_due_at.isoformat() if topic.review_due_at else None
        ),
        "review_reason": topic.review_reason,
        "topic_status": topic.status,
    }


def get_recommended_action_for_mistake(mistake_type: str, count: int) -> str:
    normalized_mistake = mistake_type.lower()

    if count >= 3:
        return (
            "This mistake has repeated several times. Do a focused repair "
            "lesson, then one targeted practice problem."
        )

    if "boundary" in normalized_mistake or "edge" in normalized_mistake:
        return "Do one targeted edge-case problem focused on this mistake."

    if "setup" in normalized_mistake or "formula" in normalized_mistake:
        return (
            "Review the setup pattern, then try one similar problem with "
            "different numbers."
        )

    if "assumption" in normalized_mistake:
        return (
            "Identify the assumption that failed, then test one variation "
            "where that assumption changes."
        )

    if "calculation" in normalized_mistake or "arithmetic" in normalized_mistake:
        return (
            "Redo the computation slowly and compare each step against the "
            "correct reasoning."
        )

    return "Do one targeted follow-up problem focused only on this mistake type."


def build_weak_area_summary(
    attempts: list[PracticeAttempt],
    scope_id: str,
    scope_type: str,
) -> WeakAreaSummaryRead:
    grouped_attempts: dict[str, list[PracticeAttempt]] = {}

    for attempt in attempts:
        if attempt.performance_level == "strong":
            continue

        if attempt.is_correct is True and attempt.performance_level not in {
            "fragile",
            "minor_mistake",
            "weak",
        }:
            continue

        mistake_type = attempt.mistake_type or "Unclassified mistake"

        if mistake_type not in grouped_attempts:
            grouped_attempts[mistake_type] = []

        grouped_attempts[mistake_type].append(attempt)

    weak_areas: list[WeakAreaRead] = []

    for mistake_type, mistake_attempts in grouped_attempts.items():
        sorted_attempts = sorted(
            mistake_attempts,
            key=lambda attempt: attempt.created_at,
            reverse=True,
        )
        latest_attempt = sorted_attempts[0]

        weak_areas.append(
            WeakAreaRead(
                mistake_type=mistake_type,
                count=len(mistake_attempts),
                latest_feedback=latest_attempt.feedback,
                recommended_action=get_recommended_action_for_mistake(
                    mistake_type=mistake_type,
                    count=len(mistake_attempts),
                ),
            )
        )

    weak_areas.sort(key=lambda area: area.count, reverse=True)

    return WeakAreaSummaryRead(
        scope_id=scope_id,
        scope_type=scope_type,
        weak_areas=weak_areas,
    )


def validate_owned_practice_scope(
    study_path_id: str,
    topic_id: str,
    db: Session,
    current_user: dict[str, Any],
) -> tuple[StudyPath, Topic]:
    study_path = get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )
    topic = get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)

    if str(topic.study_path_id) != str(study_path.id):
        raise HTTPException(
            status_code=400,
            detail="Topic does not belong to the provided study path.",
        )

    return study_path, topic


def build_oriented_practice_context(
    lesson_context: str | None,
    current_section: str | None = None,
    concept_tested: str | None = None,
    related_section: str | None = None,
) -> str | None:
    context_parts: list[str] = []

    if lesson_context:
        context_parts.append(lesson_context)

    orientation_parts = []

    if current_section:
        orientation_parts.append(f"Current section: {current_section}")

    if concept_tested:
        orientation_parts.append(f"Concept tested: {concept_tested}")

    if related_section:
        orientation_parts.append(f"Related lesson section: {related_section}")

    if orientation_parts:
        context_parts.append(
            "Practice orientation:\n" + "\n".join(orientation_parts)
        )

    if not context_parts:
        return None

    return "\n\n".join(context_parts)


@router.post("/hint", response_model=PracticeHintResponse)
def get_practice_hint(
    payload: PracticeHintRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    validate_owned_practice_scope(
        study_path_id=str(payload.study_path_id),
        topic_id=str(payload.topic_id),
        db=db,
        current_user=current_user,
    )

    try:
        result = generate_practice_hint(
            question=payload.question,
            user_partial_answer=payload.user_partial_answer,
            lesson_context=build_oriented_practice_context(
                lesson_context=payload.lesson_context,
                current_section=payload.current_section,
            ),
        )

        return result

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate practice hint: {str(exc)}",
        )


@router.post("/submit", response_model=PracticeSubmitResponse)
def submit_practice_answer(
    payload: PracticeSubmitRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        study_path_id = str(payload.study_path_id)
        topic_id = str(payload.topic_id)
        lesson_id = str(payload.lesson_id) if payload.lesson_id else None

        _, topic = validate_owned_practice_scope(
            study_path_id=study_path_id,
            topic_id=topic_id,
            db=db,
            current_user=current_user,
        )

        if lesson_id is not None:
            lesson = get_owned_lesson(
                lesson_id=lesson_id,
                db=db,
                current_user=current_user,
            )

            if str(lesson.topic_id) != topic_id:
                raise HTTPException(
                    status_code=400,
                    detail="Lesson does not belong to the provided topic.",
                )

        evaluation = evaluate_practice_answer(
            question=payload.question,
            user_answer=payload.user_answer,
            lesson_context=build_oriented_practice_context(
                lesson_context=payload.lesson_context,
                current_section=payload.current_section,
                concept_tested=payload.concept_tested,
                related_section=payload.related_section,
            ),
            hint_used=payload.hint_used,
        )

        attempt = PracticeAttempt(
            study_path_id=study_path_id,
            topic_id=topic_id,
            lesson_id=lesson_id,
            question=payload.question,
            user_answer=payload.user_answer,
            is_correct=evaluation["is_correct"],
            performance_level=evaluation["performance_level"],
            mistake_type=evaluation["mistake_type"],
            feedback=evaluation["feedback"],
            hint_used=payload.hint_used,
            follow_up_question=evaluation["follow_up_question"],
            next_action=evaluation["next_action"],
        )

        db.add(attempt)

        apply_practice_result_to_topic(
            topic=topic,
            performance_level=evaluation["performance_level"],
        )
        adaptive_response = build_adaptive_practice_response(
            evaluation=evaluation,
            topic=topic,
        )

        recalculate_study_path_progress(db, study_path_id)

        db.commit()
        db.refresh(attempt)

        return PracticeSubmitResponse(
            attempt_id=attempt.id,
            is_correct=attempt.is_correct,
            performance_level=attempt.performance_level,
            mistake_type=attempt.mistake_type,
            feedback=attempt.feedback,
            follow_up_question=attempt.follow_up_question,
            next_action=attempt.next_action,
            adaptive_response=adaptive_response,
            created_at=attempt.created_at,
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit practice answer: {str(exc)}",
        )


@router.get(
    "/study-path/{study_path_id}/attempts",
    response_model=List[PracticeAttemptRead],
)
def get_study_path_practice_attempts(
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
        db.query(PracticeAttempt)
        .filter(PracticeAttempt.study_path_id == study_path_id)
        .order_by(PracticeAttempt.created_at.desc())
        .limit(20)
        .all()
    )


@router.get(
    "/topic/{topic_id}/attempts",
    response_model=List[PracticeAttemptRead],
)
def get_topic_practice_attempts(
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)

    return (
        db.query(PracticeAttempt)
        .filter(PracticeAttempt.topic_id == topic_id)
        .order_by(PracticeAttempt.created_at.desc())
        .limit(20)
        .all()
    )


@router.get(
    "/topic/{topic_id}/weak-areas",
    response_model=WeakAreaSummaryRead,
)
def get_topic_weak_areas(
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)

    attempts = (
        db.query(PracticeAttempt)
        .filter(PracticeAttempt.topic_id == topic_id)
        .order_by(PracticeAttempt.created_at.desc())
        .all()
    )

    return build_weak_area_summary(
        attempts=attempts,
        scope_id=topic_id,
        scope_type="topic",
    )


@router.get(
    "/study-path/{study_path_id}/weak-areas",
    response_model=WeakAreaSummaryRead,
)
def get_study_path_weak_areas(
    study_path_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )

    attempts = (
        db.query(PracticeAttempt)
        .filter(PracticeAttempt.study_path_id == study_path_id)
        .order_by(PracticeAttempt.created_at.desc())
        .all()
    )

    return build_weak_area_summary(
        attempts=attempts,
        scope_id=study_path_id,
        scope_type="study_path",
    )


@router.post(
    "/topic/{topic_id}/weak-area-question",
    response_model=WeakAreaQuestionResponse,
)
def create_weak_area_question(
    topic_id: str,
    payload: WeakAreaQuestionRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)

    if not payload.mistake_type.strip():
        raise HTTPException(status_code=400, detail="Mistake type cannot be empty.")

    try:
        result = generate_weak_area_question(
            mistake_type=payload.mistake_type,
            lesson_context=payload.lesson_context,
        )

        return WeakAreaQuestionResponse(
            question=result["question"],
            target_mistake_type=result["target_mistake_type"],
            reason=result["reason"],
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate weak-area question: {str(exc)}",
        )


@router.post(
    "/topic/{topic_id}/review-question",
    response_model=SpacedReviewQuestionResponse,
)
def create_spaced_review_question(
    topic_id: str,
    payload: SpacedReviewQuestionRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    topic = get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)

    if not topic.review_due_at:
        raise HTTPException(
            status_code=400,
            detail="This topic does not have a scheduled review.",
        )

    if topic.review_due_at > datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="This topic is not due for review yet.",
        )

    try:
        result = generate_spaced_review_question(
            topic_title=topic.title,
            topic_purpose=topic.purpose,
            review_reason=topic.review_reason,
            lesson_context=payload.lesson_context,
        )

        return SpacedReviewQuestionResponse(
            question=result["question"],
            reason=result["reason"],
            review_due_at=topic.review_due_at.isoformat(),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate spaced review question: {str(exc)}",
        )


@router.get(
    "/class/{class_id}/weak-areas",
    response_model=WeakAreaSummaryRead,
)
def get_class_weak_areas(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    azalea_class = get_owned_class(
        class_id=class_id,
        db=db,
        current_user=current_user,
    )

    study_path_ids = [str(study_path.id) for study_path in azalea_class.study_paths]

    if not study_path_ids:
        return WeakAreaSummaryRead(
            scope_id=class_id,
            scope_type="class",
            weak_areas=[],
        )

    attempts = (
        db.query(PracticeAttempt)
        .filter(PracticeAttempt.study_path_id.in_(study_path_ids))
        .order_by(PracticeAttempt.created_at.desc())
        .all()
    )

    return build_weak_area_summary(
        attempts=attempts,
        scope_id=class_id,
        scope_type="class",
    )
