from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.study_path import StudyPath
from app.models.topic import Topic
from sqlalchemy.orm import Session
from app.schemas.learner_state import (
    AdaptivePlanResponse,
    ClassAdaptivePlanResponse,
    ClassAlignmentMetricsResponse,
    ClassMemorySummary,
    GlobalMemorySummary,
    TransferChallengeRequest,
    TransferChallengeResponse,
    TransferChallengeSubmitRequest,
    TransferChallengeSubmitResponse,
)
from app.services.transfer_challenge import (
    evaluate_transfer_challenge,
    generate_transfer_challenge,
)
from app.services.adaptive_plan import build_class_adaptive_plan
from app.services.learner_memory import (
    build_class_memory_summary,
    build_global_memory_summary,
)
from app.services.alignment_metrics import build_class_alignment_metrics

from app.schemas.targeted_repair import (
    TargetedRepairFollowUpSubmitRequest,
    TargetedRepairFollowUpSubmitResponse,
    TargetedRepairRequest,
    TargetedRepairResponse,
)
from app.services.adaptive_plan import build_study_path_adaptive_plan
from app.services.targeted_repair import (
    evaluate_targeted_repair_follow_up,
    generate_targeted_repair,
)
from app.services.review_question import (
    evaluate_review_answer,
    generate_review_question,
)
from app.models.targeted_repair_attempt import TargetedRepairAttempt
from app.api.ownership import get_owned_class, get_owned_study_path, get_owned_topic
from app.api.deps import get_current_user_id, get_db
from app.models.diagnostic_attempt import DiagnosticAttempt
from app.models.learner_concept_state import LearnerConceptState
from app.services.learner_memory import build_study_path_memory_summary
from app.schemas.learner_state import (
    AlignmentSummary,
    LearnerConceptStateRead,
    LearnerSignalPayload,
    SelfReportPayload,
    SelfReportResult,
    StartDiagnosticPayload,
    StartDiagnosticResult,
    SubmitDiagnosticPayload,
    SubmitDiagnosticResult,
    ReviewAnswerSubmitRequest,
    ReviewAnswerSubmitResponse,
    ReviewQueueItem,
    ReviewQuestionRequest,
    ReviewQuestionResponse,
    StudyPathAlignmentMetrics,
    StudyPathMemorySummary,
)
from app.services.alignment_metrics import build_study_path_alignment_metrics
from app.services.learner_alignment import (
    apply_self_report,
    estimate_state_from_diagnostic_scores,
    explanation_density_for_level,
    generate_static_diagnostic_questions,
    get_alignment_note,
    map_self_report_to_state,
    map_state_to_starting_mode,
    should_offer_diagnostic,
    update_concept_from_signal,
)

router = APIRouter()


@router.post("/topics/{topic_id}/self-report", response_model=SelfReportResult)
def submit_self_report(
    topic_id: str,
    payload: SelfReportPayload,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    get_owned_topic(topic_id, db, {"user_id": user_id})

    state = apply_self_report(
        db=db,
        user_id=user_id,
        topic_id=topic_id,
        level=payload.level,
        concept_name="overall_topic",
    )

    estimated_state = map_self_report_to_state(payload.level)

    return SelfReportResult(
        topic_id=topic_id,
        self_report_level=payload.level,
        estimated_state=estimated_state,
        recommended_starting_mode=map_state_to_starting_mode(estimated_state),
        explanation_density=explanation_density_for_level(payload.level),
        should_offer_diagnostic=should_offer_diagnostic(payload.level, payload.mode),
    )


@router.post("/topics/{topic_id}/diagnostic/start", response_model=StartDiagnosticResult)
def start_diagnostic(
    topic_id: str,
    payload: StartDiagnosticPayload,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    topic = get_owned_topic(topic_id, db, {"user_id": user_id})

    questions = generate_static_diagnostic_questions(topic.title)

    diagnostic = DiagnosticAttempt(
        user_id=user_id,
        topic_id=topic_id,
        mode=payload.mode,
        self_report_level=payload.self_report_level,
        questions_json=questions,
        answers_json=[],
        estimated_state="unknown",
        completed=False,
    )

    db.add(diagnostic)
    db.commit()
    db.refresh(diagnostic)

    return StartDiagnosticResult(
        diagnostic_id=diagnostic.id,
        topic_id=topic_id,
        mode=diagnostic.mode,
        questions=questions,
    )

@router.get(
    "/study-paths/{study_path_id}/memory-summary",
    response_model=StudyPathMemorySummary,
)
def get_study_path_memory_summary(
    study_path_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    get_owned_study_path(study_path_id, db, {"user_id": user_id})

    return build_study_path_memory_summary(
        db=db,
        user_id=user_id,
        study_path_id=study_path_id,
    )

@router.get(
    "/study-paths/{study_path_id}/alignment-metrics",
    response_model=StudyPathAlignmentMetrics,
)
def get_study_path_alignment_metrics(
    study_path_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    get_owned_study_path(study_path_id, db, {"user_id": user_id})

    return build_study_path_alignment_metrics(
        db=db,
        user_id=user_id,
        study_path_id=study_path_id,
    )

@router.get(
    "/study-paths/{study_path_id}/adaptive-plan",
    response_model=AdaptivePlanResponse,
)
def get_study_path_adaptive_plan(
    study_path_id: str,
    target_minutes: int | None = Query(default=None, ge=5, le=120),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    get_owned_study_path(study_path_id, db, {"user_id": user_id})

    return build_study_path_adaptive_plan(
        db=db,
        user_id=user_id,
        study_path_id=study_path_id,
        target_minutes=target_minutes,
    )

@router.get(
    "/classes/{class_id}/adaptive-plan",
    response_model=ClassAdaptivePlanResponse,
)
def get_class_adaptive_plan(
    class_id: str,
    target_minutes: int | None = Query(default=None, ge=5, le=180),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    get_owned_class(class_id, db, {"user_id": user_id})

    return build_class_adaptive_plan(
        db=db,
        user_id=user_id,
        class_id=class_id,
        target_minutes=target_minutes,
    )


@router.get(
    "/classes/{class_id}/memory-summary",
    response_model=ClassMemorySummary,
)
def get_class_memory_summary(
    class_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    get_owned_class(class_id, db, {"user_id": user_id})

    return build_class_memory_summary(
        db=db,
        user_id=user_id,
        class_id=class_id,
    )


@router.get(
    "/classes/{class_id}/alignment-metrics",
    response_model=ClassAlignmentMetricsResponse,
)
def get_class_alignment_metrics(
    class_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    get_owned_class(class_id, db, {"user_id": user_id})

    return build_class_alignment_metrics(
        db=db,
        user_id=user_id,
        class_id=class_id,
    )


@router.get(
    "/global-memory-summary",
    response_model=GlobalMemorySummary,
)
def get_global_memory_summary(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return build_global_memory_summary(
        db=db,
        user_id=user_id,
    )

@router.post(
    "/topics/{topic_id}/transfer-challenge",
    response_model=TransferChallengeResponse,
)
def create_transfer_challenge(
    topic_id: str,
    payload: TransferChallengeRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    topic = get_owned_topic(topic_id, db, {"user_id": user_id})
    concept_name = payload.concept_name.strip() or topic.title

    try:
        result = generate_transfer_challenge(
            concept_name=concept_name,
            lesson_context=payload.lesson_context,
            prior_context=payload.prior_context,
        )

        return TransferChallengeResponse(**result)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate transfer challenge: {str(exc)}",
        )


@router.post(
    "/transfer-challenge/submit",
    response_model=TransferChallengeSubmitResponse,
)
def submit_transfer_challenge_answer(
    payload: TransferChallengeSubmitRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    topic = get_owned_topic(payload.topic_id, db, {"user_id": user_id})

    if not payload.answer.strip():
        raise HTTPException(status_code=400, detail="Answer cannot be empty")

    concept_name = payload.concept_name.strip() or topic.title

    try:
        evaluation = evaluate_transfer_challenge(
            concept_name=concept_name,
            challenge=payload.challenge,
            answer=payload.answer,
            confidence=payload.confidence,
        )

        confidence = (payload.confidence or 3) / 5

        transfer_success = (
            evaluation["correctness"]
            if evaluation["next_action"] == "mark_transferable"
            else max(0.0, evaluation["correctness"] * 0.75)
        )

        update_concept_from_signal(
            db=db,
            user_id=user_id,
            topic_id=payload.topic_id,
            concept_name=concept_name,
            signal_type="practice",
            correctness=evaluation["correctness"],
            reasoning_quality=evaluation["reasoning_quality"],
            confidence=confidence,
            transfer_success=transfer_success,
            hint_used=False,
            mistake_type=None
            if evaluation["next_action"] in {"mark_transferable", "keep_stable"}
            else "transfer_gap",
            summary=evaluation["feedback"],
            metadata={
                "source": "transfer_challenge",
                "challenge": payload.challenge,
                "answer": payload.answer,
                "next_action": evaluation["next_action"],
            },
        )

        return TransferChallengeSubmitResponse(
            target_concept=concept_name,
            correctness=evaluation["correctness"],
            reasoning_quality=evaluation["reasoning_quality"],
            feedback=evaluation["feedback"],
            next_action=evaluation["next_action"],
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit transfer challenge: {str(exc)}",
        )

@router.post("/diagnostic/{diagnostic_id}/submit", response_model=SubmitDiagnosticResult)
def submit_diagnostic(
    diagnostic_id: int,
    payload: SubmitDiagnosticPayload,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    diagnostic = (
        db.query(DiagnosticAttempt)
        .filter(
            DiagnosticAttempt.id == diagnostic_id,
            DiagnosticAttempt.user_id == user_id,
        )
        .first()
    )

    if not diagnostic:
        raise HTTPException(status_code=404, detail="Diagnostic not found")

    if diagnostic.completed:
        raise HTTPException(status_code=400, detail="Diagnostic already completed")

    answers = [answer.model_dump() for answer in payload.answers]

    confidence_values = [
        (answer.confidence or 3) / 5 for answer in payload.answers
    ]

    confidence_score = sum(confidence_values) / len(confidence_values) if confidence_values else 0.5

    # MVP scoring:
    # We are not doing full LLM grading here yet.
    # This is intentionally lightweight and safe.
    non_empty_answers = [answer for answer in payload.answers if answer.answer.strip()]
    completion_score = len(non_empty_answers) / max(len(payload.answers), 1)

    recall_score = score_answer_presence(payload.answers, "recall_1")
    application_score = score_answer_presence(payload.answers, "application_1")
    edge_case_score = score_answer_presence(payload.answers, "edge_case_1")
    transfer_score = score_answer_presence(payload.answers, "transfer_1")

    correctness_score = (recall_score + application_score) / 2

    estimated_state = estimate_state_from_diagnostic_scores(
        correctness_score=correctness_score * completion_score,
        transfer_score=transfer_score,
        edge_case_score=edge_case_score,
        confidence_score=confidence_score,
    )

    diagnostic.answers_json = answers
    diagnostic.estimated_state = estimated_state
    diagnostic.confidence_score = confidence_score
    diagnostic.correctness_score = correctness_score
    diagnostic.transfer_score = transfer_score
    diagnostic.edge_case_score = edge_case_score
    diagnostic.completed = True
    diagnostic.result_summary = get_alignment_note(estimated_state)
    diagnostic.recommended_starting_mode = map_state_to_starting_mode(estimated_state)

    db.add(diagnostic)
    db.commit()
    db.refresh(diagnostic)

    concept_states = []

    for question in diagnostic.questions_json:
        concept_name = question.get("concept_name") or "overall_topic"
        question_id = question.get("id")

        matching_answer = next(
            (answer for answer in payload.answers if answer.question_id == question_id),
            None,
        )

        if not matching_answer:
            continue

        local_confidence = (matching_answer.confidence or 3) / 5

        local_correctness = 1.0 if matching_answer.answer.strip() else 0.0

        if question.get("type") == "transfer":
            transfer_success = local_correctness
        else:
            transfer_success = None

        if question.get("type") == "edge_case":
            edge_case_success = local_correctness
        else:
            edge_case_success = None

        concept_state = update_concept_from_signal(
            db=db,
            user_id=user_id,
            topic_id=diagnostic.topic_id,
            concept_name=concept_name,
            signal_type="diagnostic",
            correctness=local_correctness,
            reasoning_quality=local_correctness,
            confidence=local_confidence,
            transfer_success=transfer_success,
            edge_case_success=edge_case_success,
            summary=f"Diagnostic answer for {question.get('type')} check.",
            metadata={
                "diagnostic_id": diagnostic.id,
                "question_id": question_id,
                "question_type": question.get("type"),
            },
        )

        concept_states.append(
            {
                "concept_name": concept_state.concept_name,
                "knowledge_state": concept_state.knowledge_state,
                "review_due_at": concept_state.review_due_at,
                "review_reason": concept_state.review_reason,
            }
        )

    return SubmitDiagnosticResult(
        diagnostic_id=diagnostic.id,
        topic_id=diagnostic.topic_id,
        estimated_state=diagnostic.estimated_state,
        recommended_starting_mode=diagnostic.recommended_starting_mode,
        result_summary=diagnostic.result_summary or "",
        concept_states=concept_states,
    )


@router.post("/signals")
def submit_learner_signal(
    payload: LearnerSignalPayload,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    get_owned_topic(payload.topic_id, db, {"user_id": user_id})

    state = update_concept_from_signal(
        db=db,
        user_id=user_id,
        topic_id=payload.topic_id,
        concept_name=payload.concept_name,
        signal_type=payload.signal_type,
        correctness=payload.correctness,
        reasoning_quality=payload.reasoning_quality,
        hint_used=payload.hint_used,
        confidence=payload.confidence,
        transfer_success=payload.transfer_success,
        edge_case_success=payload.edge_case_success,
        time_seconds=payload.time_seconds,
        mistake_type=payload.mistake_type,
        summary=payload.summary,
        metadata=payload.metadata,
    )

    return {
        "id": state.id,
        "topic_id": state.topic_id,
        "concept_name": state.concept_name,
        "knowledge_state": state.knowledge_state,
        "review_due_at": state.review_due_at,
        "review_reason": state.review_reason,
    }


@router.get("/topics/{topic_id}", response_model=list[LearnerConceptStateRead])
def get_topic_learner_state(
    topic_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    get_owned_topic(topic_id, db, {"user_id": user_id})

    return (
        db.query(LearnerConceptState)
        .filter(
            LearnerConceptState.user_id == user_id,
            LearnerConceptState.topic_id == topic_id,
        )
        .order_by(LearnerConceptState.updated_at.desc())
        .all()
    )


@router.get("/topics/{topic_id}/alignment", response_model=AlignmentSummary)
def get_topic_alignment_summary(
    topic_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    get_owned_topic(topic_id, db, {"user_id": user_id})

    states = (
        db.query(LearnerConceptState)
        .filter(
            LearnerConceptState.user_id == user_id,
            LearnerConceptState.topic_id == topic_id,
        )
        .all()
    )

    fragile = [
        state for state in states
        if state.knowledge_state in {"unknown", "familiar", "fragile"}
    ]

    strong = [
        state for state in states
        if state.knowledge_state in {"stable", "transferable"}
    ]

    now = datetime.now(timezone.utc)

    review_queue = [
        state for state in states
        if state.review_due_at is not None and state.review_due_at <= now
    ]

    if fragile:
        recommended_state = fragile[0].knowledge_state
    elif strong:
        recommended_state = strong[0].knowledge_state
    else:
        recommended_state = "unknown"

    return AlignmentSummary(
        topic_id=topic_id,
        strongest_concepts=strong,
        fragile_concepts=fragile,
        review_queue=review_queue,
        recommended_starting_mode=map_state_to_starting_mode(recommended_state),
        adaptation_note=get_alignment_note(recommended_state),
    )

@router.get("/review-queue", response_model=list[ReviewQueueItem])
def get_review_queue(
    study_path_id: str | None = Query(default=None),
    topic_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    if topic_id:
        get_owned_topic(topic_id, db, {"user_id": user_id})

    if study_path_id:
        get_owned_study_path(study_path_id, db, {"user_id": user_id})

    now = datetime.now(timezone.utc)

    query = (
        db.query(LearnerConceptState, Topic)
        .join(Topic, LearnerConceptState.topic_id == Topic.id)
        .filter(
            LearnerConceptState.user_id == user_id,
            LearnerConceptState.review_due_at.isnot(None),
            LearnerConceptState.review_due_at <= now,
        )
    )

    if topic_id:
        query = query.filter(LearnerConceptState.topic_id == topic_id)

    if study_path_id:
        query = query.filter(Topic.study_path_id == study_path_id)

    rows = (
        query.order_by(LearnerConceptState.review_due_at.asc())
        .limit(limit)
        .all()
    )

    items: list[ReviewQueueItem] = []

    for state, topic in rows:
        if state.knowledge_state in {"unknown", "familiar"}:
            recommended_action = "quick_refresher"
        elif state.knowledge_state == "fragile":
            recommended_action = "quick_check"
        elif state.knowledge_state == "stable":
            recommended_action = "delayed_retrieval"
        else:
            recommended_action = "transfer_check"

        items.append(
            ReviewQueueItem(
                concept_state_id=state.id,
                topic_id=str(topic.id),
                topic_title=topic.title,
                concept_name=state.concept_name,
                knowledge_state=state.knowledge_state,
                review_due_at=state.review_due_at,
                review_reason=state.review_reason,
                recommended_action=recommended_action,
                estimated_minutes=3,
            )
        )

    return items


@router.post(
    "/topics/{topic_id}/review-question",
    response_model=ReviewQuestionResponse,
)
def create_review_question(
    topic_id: str,
    payload: ReviewQuestionRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    topic = get_owned_topic(topic_id, db, {"user_id": user_id})
    concept_name = payload.concept_name.strip() or topic.title

    try:
        result = generate_review_question(
            concept_name=concept_name,
            lesson_context=payload.lesson_context,
            review_reason=payload.review_reason,
        )

        return ReviewQuestionResponse(**result)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate review question: {str(exc)}",
        )


@router.post(
    "/review-question/submit",
    response_model=ReviewAnswerSubmitResponse,
)
def submit_review_answer(
    payload: ReviewAnswerSubmitRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    topic = get_owned_topic(payload.topic_id, db, {"user_id": user_id})

    if not payload.answer.strip():
        raise HTTPException(status_code=400, detail="Answer cannot be empty")

    concept_name = payload.concept_name.strip() or topic.title

    try:
        evaluation = evaluate_review_answer(
            concept_name=concept_name,
            question=payload.question,
            answer=payload.answer,
            confidence=payload.confidence,
            review_reason=payload.review_reason,
        )

        confidence = (payload.confidence or 3) / 5

        state = update_concept_from_signal(
            db=db,
            user_id=user_id,
            topic_id=payload.topic_id,
            concept_name=concept_name,
            signal_type="practice",
            correctness=evaluation["correctness"],
            reasoning_quality=evaluation["reasoning_quality"],
            confidence=confidence,
            hint_used=False,
            mistake_type=None
            if evaluation["next_action"] in {"mark_stable", "schedule_later"}
            else "review_gap",
            summary=evaluation["feedback"],
            metadata={
                "source": "spaced_review",
                "question": payload.question,
                "answer": payload.answer,
                "next_action": evaluation["next_action"],
                "review_reason": payload.review_reason,
            },
        )

        return ReviewAnswerSubmitResponse(
            topic_id=payload.topic_id,
            concept_name=concept_name,
            correctness=evaluation["correctness"],
            reasoning_quality=evaluation["reasoning_quality"],
            feedback=evaluation["feedback"],
            next_action=evaluation["next_action"],
            review_due_at=state.review_due_at,
            review_reason=state.review_reason,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit review answer: {str(exc)}",
        )

def score_answer_presence(answers, question_id: str) -> float:
    answer = next((item for item in answers if item.question_id == question_id), None)

    if not answer:
        return 0.0

    stripped = answer.answer.strip()

    if not stripped:
        return 0.0

    if len(stripped.split()) < 4:
        return 0.35

    return 1.0


@router.post(
    "/topics/{topic_id}/targeted-repair",
    response_model=TargetedRepairResponse,
)
def create_targeted_repair(
    topic_id: str,
    payload: TargetedRepairRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    topic = get_owned_topic(topic_id, db, {"user_id": user_id})
    concept_name = payload.concept_name.strip() or topic.title

    prior_repair_count = (
        db.query(TargetedRepairAttempt)
        .filter(
            TargetedRepairAttempt.user_id == user_id,
            TargetedRepairAttempt.topic_id == topic_id,
            TargetedRepairAttempt.concept_name == concept_name,
        )
        .count()
    )

    try:
        repair = generate_targeted_repair(
            concept_name=concept_name,
            mistake_type=payload.mistake_type,
            question=payload.question,
            user_answer=payload.user_answer,
            lesson_context=payload.lesson_context,
            feedback=payload.feedback,
            prior_repair_count=prior_repair_count,
        )

        repair_attempt = TargetedRepairAttempt(
            user_id=user_id,
            topic_id=topic_id,
            concept_name=concept_name,
            mistake_type=payload.mistake_type,
            question=payload.question,
            user_answer=payload.user_answer,
            repair_explanation=repair["repair_explanation"],
            why_this_matters=repair["why_this_matters"],
            follow_up_question=repair["follow_up_question"],
            next_action=repair["next_action"],
            repair_level=repair["repair_level"],
            prior_repair_count=prior_repair_count,
        )

        db.add(repair_attempt)
        db.flush()

        update_concept_from_signal(
            db=db,
            user_id=user_id,
            topic_id=topic_id,
            concept_name=concept_name,
            signal_type="practice",
            correctness=0.35,
            reasoning_quality=0.35,
            hint_used=False,
            mistake_type=payload.mistake_type,
            summary=f"Targeted repair generated: {repair.get('repair_explanation', '')}",
            metadata={
                "targeted_repair_attempt_id": repair_attempt.id,
                "repair_level": repair["repair_level"],
                "prior_repair_count": prior_repair_count,
                "repair_explanation": repair.get("repair_explanation"),
                "why_this_matters": repair.get("why_this_matters"),
                "follow_up_question": repair.get("follow_up_question"),
                "next_action": repair.get("next_action"),
                "source": "targeted_repair",
            },
        )

        return TargetedRepairResponse(
            repair_attempt_id=repair_attempt.id,
            target_concept=repair["target_concept"],
            repair_explanation=repair["repair_explanation"],
            why_this_matters=repair["why_this_matters"],
            follow_up_question=repair["follow_up_question"],
            next_action=repair["next_action"],
            repair_level=repair["repair_level"],
            prior_repair_count=prior_repair_count,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate targeted repair: {str(exc)}",
        )

@router.post(
    "/targeted-repair/{repair_attempt_id}/follow-up",
    response_model=TargetedRepairFollowUpSubmitResponse,
)
def submit_targeted_repair_follow_up(
    repair_attempt_id: int,
    payload: TargetedRepairFollowUpSubmitRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repair_attempt = (
        db.query(TargetedRepairAttempt)
        .filter(
            TargetedRepairAttempt.id == repair_attempt_id,
            TargetedRepairAttempt.user_id == user_id,
        )
        .first()
    )

    if not repair_attempt:
        raise HTTPException(status_code=404, detail="Targeted repair not found")

    if repair_attempt.follow_up_completed:
        raise HTTPException(
            status_code=400,
            detail="This targeted repair follow-up was already submitted",
        )

    if not payload.answer.strip():
        raise HTTPException(status_code=400, detail="Answer cannot be empty")

    try:
        evaluation = evaluate_targeted_repair_follow_up(
            target_concept=repair_attempt.concept_name,
            repair_explanation=repair_attempt.repair_explanation,
            follow_up_question=repair_attempt.follow_up_question,
            learner_answer=payload.answer,
        )

        confidence = (payload.confidence or 3) / 5

        repair_attempt.follow_up_answer = payload.answer
        repair_attempt.follow_up_correctness = evaluation["correctness"]
        repair_attempt.follow_up_reasoning_quality = evaluation["reasoning_quality"]
        repair_attempt.follow_up_feedback = evaluation["feedback"]
        repair_attempt.follow_up_completed = True
        repair_attempt.follow_up_confidence = confidence
        repair_attempt.follow_up_completed_at = datetime.now(timezone.utc)

        db.add(repair_attempt)
        db.flush()

        update_concept_from_signal(
            db=db,
            user_id=user_id,
            topic_id=repair_attempt.topic_id,
            concept_name=repair_attempt.concept_name,
            signal_type="practice",
            correctness=evaluation["correctness"],
            reasoning_quality=evaluation["reasoning_quality"],
            confidence=confidence,
            hint_used=False,
            mistake_type=repair_attempt.mistake_type,
            summary=evaluation["feedback"],
            metadata={
                "targeted_repair_attempt_id": repair_attempt.id,
                "source": "targeted_repair_follow_up",
                "next_action": evaluation["next_action"],
                "repair_level": repair_attempt.repair_level,
            },
        )

        return TargetedRepairFollowUpSubmitResponse(
            repair_attempt_id=repair_attempt.id,
            is_complete=True,
            correctness=evaluation["correctness"],
            reasoning_quality=evaluation["reasoning_quality"],
            feedback=evaluation["feedback"],
            next_action=evaluation["next_action"],
            created_at=repair_attempt.follow_up_completed_at,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to evaluate targeted repair follow-up: {str(exc)}",
        )
