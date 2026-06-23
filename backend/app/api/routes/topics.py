from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.ownership import get_owned_study_path, get_owned_topic
from app.models.content_chunk import ContentChunk
from app.models.learning_material import LearningMaterial
from app.models.confusion_event import ConfusionEvent
from app.models.lesson import Lesson
from app.models.practice_attempt import PracticeAttempt
from app.models.study_path import StudyPath
from app.models.study_session import StudySession
from app.models.topic import Topic
from app.schemas.topic import (
    TopicCreate,
    TopicRead,
    TopicScheduleReview,
    TopicSelfReportKnowledge,
    TopicUpdateStatus,
)
from app.schemas.topic_qa import (
    ConfusionEventRead,
    ConfusionEventUpdate,
    TopicQARequest,
    TopicQAResponse,
    TopicQASource,
)
from app.services.learner_alignment import update_concept_from_signal
from app.services.course_type_classifier import classify_topic_course_type
from app.services.knowledge_level_service import self_report_to_knowledge_level
from app.services.topic_generator import generate_topics_from_chunks
from app.services.topic_qa import answer_topic_question

router = APIRouter()


class GenerateTopicsRequest(BaseModel):
    overwrite_existing: bool = False


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


def apply_status_review_rules(topic: Topic, next_status: str) -> None:
    if next_status == "completed":
        topic.status = "completed"
        topic.review_due_at = datetime.utcnow() + timedelta(days=1)
        topic.review_reason = "Completed topic. Scheduled delayed review."

    elif next_status == "needs_review":
        topic.status = "needs_review"
        topic.review_due_at = None
        topic.review_reason = None

    elif next_status == "not_started":
        topic.status = "not_started"
        topic.review_due_at = None
        topic.review_reason = None

    elif next_status == "in_progress":
        topic.status = "in_progress"

        if topic.review_due_at and topic.review_due_at <= datetime.utcnow():
            topic.review_due_at = None
            topic.review_reason = None


def get_source_chunks_for_topic(
    topic: Topic,
    db: Session,
    limit: int = 8,
) -> list[ContentChunk]:
    study_path = topic.study_path

    if not study_path:
        raise HTTPException(status_code=404, detail="Study path not found")

    direct_chunks = (
        db.query(ContentChunk)
        .join(ContentChunk.material)
        .filter(ContentChunk.material.has(LearningMaterial.study_path_id == study_path.id))
        .order_by(ContentChunk.chunk_index.asc())
        .limit(limit)
        .all()
    )

    if len(direct_chunks) >= limit:
        return direct_chunks

    attached_classes = study_path.classes
    class_chunks: list[ContentChunk] = []

    class_ids = [
        azalea_class.id
        for azalea_class in attached_classes
        if azalea_class.user_id == study_path.user_id
    ]

    if class_ids:
        class_chunks = (
            db.query(ContentChunk)
            .join(ContentChunk.material)
            .filter(ContentChunk.material.has(LearningMaterial.class_id.in_(class_ids)))
            .order_by(ContentChunk.chunk_index.asc())
            .limit(limit - len(direct_chunks))
            .all()
        )

    chunks = direct_chunks + class_chunks

    return chunks


def get_source_chunks_for_study_path(
    study_path: StudyPath,
    db: Session,
    limit: int = 8,
    allow_empty: bool = False,
) -> list[ContentChunk]:
    direct_chunks = (
        db.query(ContentChunk)
        .join(ContentChunk.material)
        .filter(ContentChunk.material.has(LearningMaterial.study_path_id == study_path.id))
        .order_by(ContentChunk.chunk_index.asc())
        .limit(limit)
        .all()
    )

    if len(direct_chunks) >= limit:
        return direct_chunks

    class_ids = [
        azalea_class.id
        for azalea_class in study_path.classes
        if azalea_class.user_id == study_path.user_id
    ]

    class_chunks: list[ContentChunk] = []

    if class_ids:
        class_chunks = (
            db.query(ContentChunk)
            .join(ContentChunk.material)
            .filter(ContentChunk.material.has(LearningMaterial.class_id.in_(class_ids)))
            .order_by(ContentChunk.chunk_index.asc())
            .limit(limit - len(direct_chunks))
            .all()
        )

    chunks = direct_chunks + class_chunks

    if not chunks and not allow_empty:
        raise HTTPException(
            status_code=400,
            detail=(
                "No uploaded material chunks found. Attach a PDF/text file "
                "directly to this study path or attach the path to a class with materials."
            ),
        )

    return chunks


def detach_and_delete_existing_topic_data(db: Session, topic: Topic) -> None:
    existing_lesson = db.query(Lesson).filter(Lesson.topic_id == topic.id).first()

    if existing_lesson:
        db.delete(existing_lesson)

    db.query(PracticeAttempt).filter(
        PracticeAttempt.topic_id == topic.id
    ).delete(synchronize_session=False)

    db.query(StudySession).filter(
        StudySession.topic_id == topic.id
    ).update(
        {StudySession.topic_id: None},
        synchronize_session=False,
    )

    db.delete(topic)


@router.post("/study-paths/{study_path_id}/topics", response_model=TopicRead)
def create_topic(
    study_path_id: str,
    payload: TopicCreate,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )

    classification = None
    payload_topic_type = payload.topic_type or payload.course_type

    if not payload_topic_type:
        classification = classify_topic_course_type(
            user_goal=payload.purpose,
            topic_title=payload.title,
            topic_purpose=payload.purpose,
            source_summary=payload.source_refs,
        )

    course_type = (
        payload_topic_type.value
        if payload_topic_type
        else classification["primary_course_type"]
        if classification
        else None
    )
    secondary_course_types = (
        [course_type.value for course_type in payload.secondary_course_types]
        if payload.secondary_course_types
        else classification["secondary_course_types"]
        if classification
        else []
    )
    knowledge_level = (
        payload.knowledge_level
        if payload.knowledge_level is not None
        else classification["knowledge_level"]
        if classification
        else None
    )

    topic = Topic(
        study_path_id=study_path_id,
        title=payload.title,
        purpose=payload.purpose,
        unit_title=payload.unit_title,
        learner_outcome=payload.learner_outcome,
        prerequisite_topics=payload.prerequisite_topics,
        assumed_prerequisites=payload.assumed_prerequisites,
        source_refs=payload.source_refs,
        in_scope=payload.in_scope,
        out_of_scope=payload.out_of_scope,
        practice_target=payload.practice_target,
        practice_format=payload.practice_format,
        difficulty_focus=payload.difficulty_focus,
        boundary_reason=payload.boundary_reason,
        modifiers=payload.modifiers,
        source_coverage_notes=payload.source_coverage_notes,
        card_blueprint_hint=payload.card_blueprint_hint,
        course_type_reason=payload.topic_type_reason or payload.course_type_reason,
        order_index=payload.order_index,
        estimated_minutes=payload.estimated_minutes,
        course_type=course_type,
        secondary_course_types=secondary_course_types,
        knowledge_level=knowledge_level,
        decomposition_metadata=payload.decomposition_metadata,
    )

    db.add(topic)
    recalculate_study_path_progress(db, study_path_id)

    db.commit()
    db.refresh(topic)

    return topic


@router.get("/study-paths/{study_path_id}/topics", response_model=list[TopicRead])
def list_study_path_topics(
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
        db.query(Topic)
        .filter(Topic.study_path_id == study_path_id)
        .order_by(Topic.order_index.asc())
        .all()
    )


@router.get("/topics/{topic_id}", response_model=TopicRead)
def get_topic(
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    return get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)


@router.patch("/topics/{topic_id}/status", response_model=TopicRead)
def update_topic_status(
    topic_id: str,
    payload: TopicUpdateStatus,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    allowed_statuses = {"not_started", "in_progress", "completed", "needs_review"}

    if payload.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(allowed_statuses))}",
        )

    topic = get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)

    apply_status_review_rules(topic=topic, next_status=payload.status)
    recalculate_study_path_progress(db, str(topic.study_path_id))

    db.commit()
    db.refresh(topic)

    return topic


@router.patch("/topics/{topic_id}/schedule-review", response_model=TopicRead)
def schedule_topic_review(
    topic_id: str,
    payload: TopicScheduleReview,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    topic = get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)

    topic.review_due_at = payload.review_due_at
    topic.review_reason = payload.review_reason

    db.commit()
    db.refresh(topic)

    return topic


@router.patch("/topics/{topic_id}/knowledge-level", response_model=TopicRead)
def set_topic_knowledge_level(
    topic_id: str,
    payload: TopicSelfReportKnowledge,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    topic = get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)

    level = self_report_to_knowledge_level(payload.self_report)
    if level is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid self_report value. Use 1–5 or a text description.",
        )

    topic.knowledge_level = level

    db.commit()
    db.refresh(topic)

    return topic


@router.post("/topics/{topic_id}/qa", response_model=TopicQAResponse)
def ask_topic_question(
    topic_id: str,
    payload: TopicQARequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    topic = get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)
    user_id = str(current_user.get("user_id") or current_user.get("sub") or "")

    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    chunks = get_source_chunks_for_topic(topic=topic, db=db, limit=8)

    try:
        prior_context = None
        if payload.prior_confusion_event_id:
            prior_event = (
                db.query(ConfusionEvent)
                .filter(
                    ConfusionEvent.id == payload.prior_confusion_event_id,
                    ConfusionEvent.user_id == user_id,
                    ConfusionEvent.topic_id == topic_id,
                )
                .first()
            )
            if prior_event:
                prior_context = (
                    f"Previous confusion type: {prior_event.confusion_type}\n"
                    f"Previous question: {prior_event.user_question}\n"
                    f"Previous answer preview: {prior_event.answer_generated[:700]}"
                )

        result = answer_topic_question(
            question=payload.question,
            topic=topic,
            chunks=chunks,
            lesson_context=payload.lesson_context,
            selected_text=payload.highlighted_text or payload.selected_text,
            current_section=payload.current_section,
            clarification_mode=payload.clarification_mode,
            prior_confusion_context=prior_context,
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

        sources: list[TopicQASource] = []

        for chunk in source_chunks[:5]:
            material_title = chunk.material.title if chunk.material else "Unknown material"
            material_filename = chunk.material.filename if chunk.material else None
            filename_text = f" ({material_filename})" if material_filename else ""

            sources.append(
                TopicQASource(
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

        source_chunk_ids = [source.chunk_id for source in sources]
        concept_name = result.get("concept_name") or topic.title or "overall_topic"
        confusion_type = result.get("confusion_type") or "general_question"
        clarification_mode = result.get("clarification_mode") or "direct_answer"

        event = ConfusionEvent(
            user_id=user_id,
            study_path_id=payload.study_path_id,
            topic_id=topic_id,
            lesson_id=payload.lesson_id,
            card_id=payload.card_id,
            card_title=payload.card_title,
            current_section=payload.current_section,
            highlighted_text=payload.highlighted_text or payload.selected_text,
            user_question=payload.question,
            answer_generated=result["answer"],
            confusion_type=confusion_type,
            concept_name=concept_name,
            clarification_mode=clarification_mode,
            source_chunk_ids=source_chunk_ids,
            concepts_involved=result.get("concepts_involved", []),
            suggested_actions=result.get("suggested_actions", []),
            metadata_json={
                "question_length": len(payload.question),
                "has_highlight": bool(payload.highlighted_text or payload.selected_text),
                "prior_confusion_event_id": payload.prior_confusion_event_id,
            },
        )
        db.add(event)
        db.flush()

        update_concept_from_signal(
            db=db,
            user_id=user_id,
            topic_id=topic_id,
            concept_name=concept_name,
            signal_type="question",
            confidence=0.35,
            mistake_type=confusion_type
            if confusion_type in {"misconception", "prerequisite_gap", "skipped_step"}
            else None,
            summary=payload.question,
            metadata={
                "confusion_event_id": event.id,
                "confusion_type": confusion_type,
                "clarification_mode": clarification_mode,
                "card_id": payload.card_id,
                "card_title": payload.card_title,
                "highlighted_text": payload.highlighted_text or payload.selected_text,
            },
        )

        db.commit()
        db.refresh(event)

        return TopicQAResponse(
            answer=result["answer"],
            sources=sources,
            confusion_event_id=event.id,
            confusion_type=confusion_type,
            concept_name=concept_name,
            clarification_mode=clarification_mode,
            suggested_actions=result.get("suggested_actions", []),
            follow_up_prompts=result.get("follow_up_prompts", []),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to answer topic question: {str(exc)}",
        )


@router.get("/topics/{topic_id}/confusion-events", response_model=list[ConfusionEventRead])
def list_topic_confusion_events(
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)
    user_id = str(current_user.get("user_id") or current_user.get("sub") or "")

    events = (
        db.query(ConfusionEvent)
        .filter(
            ConfusionEvent.user_id == user_id,
            ConfusionEvent.topic_id == topic_id,
        )
        .order_by(ConfusionEvent.created_at.desc())
        .limit(50)
        .all()
    )

    return [serialize_confusion_event(event) for event in events]


@router.patch("/confusion-events/{event_id}", response_model=ConfusionEventRead)
def update_confusion_event(
    event_id: str,
    payload: ConfusionEventUpdate,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = str(current_user.get("user_id") or current_user.get("sub") or "")
    event = (
        db.query(ConfusionEvent)
        .filter(ConfusionEvent.id == event_id, ConfusionEvent.user_id == user_id)
        .first()
    )

    if not event:
        raise HTTPException(status_code=404, detail="Confusion event not found")

    get_owned_topic(topic_id=event.topic_id, db=db, current_user=current_user)

    if payload.resolved is not None:
        event.resolved = payload.resolved
    if payload.still_confused:
        event.still_confused_count += 1
        event.resolved = False
    if payload.follow_up:
        event.follow_up_count += 1
    if payload.practice_check_correctness is not None:
        event.practice_check_correctness = payload.practice_check_correctness

    update_concept_from_signal(
        db=db,
        user_id=user_id,
        topic_id=event.topic_id,
        concept_name=event.concept_name,
        signal_type="question",
        correctness=payload.practice_check_correctness,
        confidence=0.8 if payload.resolved else 0.2 if payload.still_confused else None,
        mistake_type=event.confusion_type if payload.still_confused else None,
        summary=(
            "Clarification resolved."
            if payload.resolved
            else "Learner is still confused."
            if payload.still_confused
            else "Clarification follow-up."
        ),
        metadata={
            "confusion_event_id": event.id,
            "resolved": payload.resolved,
            "still_confused": payload.still_confused,
            "follow_up": payload.follow_up,
        },
    )

    db.commit()
    db.refresh(event)
    return serialize_confusion_event(event)


def serialize_confusion_event(event: ConfusionEvent) -> ConfusionEventRead:
    return ConfusionEventRead(
        id=event.id,
        topic_id=event.topic_id,
        study_path_id=event.study_path_id,
        lesson_id=event.lesson_id,
        card_id=event.card_id,
        card_title=event.card_title,
        current_section=event.current_section,
        highlighted_text=event.highlighted_text,
        user_question=event.user_question,
        answer_generated=event.answer_generated,
        confusion_type=event.confusion_type,
        concept_name=event.concept_name,
        clarification_mode=event.clarification_mode,
        resolved=event.resolved,
        still_confused_count=event.still_confused_count,
        follow_up_count=event.follow_up_count,
        suggested_actions=event.suggested_actions or [],
        created_at=event.created_at.isoformat(),
    )


@router.post(
    "/study-paths/{study_path_id}/generate-topics",
    response_model=list[TopicRead],
)
def generate_topics_for_study_path(
    study_path_id: str,
    payload: GenerateTopicsRequest | None = None,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    study_path = get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )

    chunks = get_source_chunks_for_study_path(
        study_path=study_path,
        db=db,
        limit=8,
        allow_empty=True,
    )

    existing_topics = (
        db.query(Topic)
        .filter(Topic.study_path_id == study_path_id)
        .all()
    )

    overwrite_existing = payload.overwrite_existing if payload else False

    if existing_topics and not overwrite_existing:
        generated_topic_data = generate_topics_from_chunks(
            chunks,
            goal=study_path.goal,
        )
        existing_titles = {
            topic.title.strip().lower()
            for topic in existing_topics
            if topic.title
        }
        next_order_index = max(
            (topic.order_index or 0 for topic in existing_topics),
            default=0,
        ) + 1

        for topic_data in generated_topic_data:
            title_key = str(topic_data.get("title", "")).strip().lower()
            if not title_key or title_key in existing_titles:
                continue

            topic = Topic(
                study_path_id=study_path_id,
                title=topic_data["title"],
                purpose=topic_data["purpose"],
                unit_title=topic_data.get("unit_title"),
                learner_outcome=topic_data.get("learner_outcome"),
                prerequisite_topics=topic_data.get("prerequisite_topics"),
                assumed_prerequisites=topic_data.get("assumed_prerequisites") or [],
                source_refs=topic_data.get("source_refs"),
                in_scope=topic_data.get("in_scope") or [],
                out_of_scope=topic_data.get("out_of_scope") or [],
                practice_target=topic_data.get("practice_target"),
                practice_format=topic_data.get("practice_format"),
                difficulty_focus=topic_data.get("difficulty_focus"),
                boundary_reason=topic_data.get("boundary_reason"),
                modifiers=topic_data.get("modifiers") or [],
                source_coverage_notes=topic_data.get("source_coverage_notes"),
                card_blueprint_hint=topic_data.get("card_blueprint_hint") or [],
                course_type_reason=(
                    topic_data.get("topic_type_reason") or topic_data.get("course_type_reason")
                ),
                visual_description=topic_data.get("visual_description"),
                order_index=next_order_index,
                estimated_minutes=topic_data["estimated_minutes"],
                course_type=topic_data.get("topic_type") or topic_data.get("course_type"),
                secondary_course_types=topic_data.get("secondary_course_types") or [],
                knowledge_level=topic_data.get("knowledge_level"),
            )
            db.add(topic)
            existing_topics.append(topic)
            existing_titles.add(title_key)
            next_order_index += 1

        db.flush()
        recalculate_study_path_progress(db, study_path_id)
        db.commit()

        return (
            db.query(Topic)
            .filter(Topic.study_path_id == study_path_id)
            .order_by(Topic.order_index.asc())
            .all()
        )

    for topic in existing_topics:
        detach_and_delete_existing_topic_data(db=db, topic=topic)

    db.flush()

    generated_topic_data = generate_topics_from_chunks(
        chunks,
        goal=study_path.goal,
    )

    created_topics: list[Topic] = []

    for topic_data in generated_topic_data:
        topic = Topic(
            study_path_id=study_path_id,
            title=topic_data["title"],
            purpose=topic_data["purpose"],
            unit_title=topic_data.get("unit_title"),
            learner_outcome=topic_data.get("learner_outcome"),
            prerequisite_topics=topic_data.get("prerequisite_topics"),
            assumed_prerequisites=topic_data.get("assumed_prerequisites") or [],
            source_refs=topic_data.get("source_refs"),
            in_scope=topic_data.get("in_scope") or [],
            out_of_scope=topic_data.get("out_of_scope") or [],
            practice_target=topic_data.get("practice_target"),
            practice_format=topic_data.get("practice_format"),
            difficulty_focus=topic_data.get("difficulty_focus"),
            boundary_reason=topic_data.get("boundary_reason"),
            modifiers=topic_data.get("modifiers") or [],
            source_coverage_notes=topic_data.get("source_coverage_notes"),
            card_blueprint_hint=topic_data.get("card_blueprint_hint") or [],
            course_type_reason=(
                topic_data.get("topic_type_reason") or topic_data.get("course_type_reason")
            ),
            visual_description=topic_data.get("visual_description"),
            order_index=topic_data["order_index"],
            estimated_minutes=topic_data["estimated_minutes"],
            course_type=topic_data.get("topic_type") or topic_data.get("course_type"),
            secondary_course_types=topic_data.get("secondary_course_types") or [],
            knowledge_level=topic_data.get("knowledge_level"),
        )
        db.add(topic)
        created_topics.append(topic)

    db.flush()
    recalculate_study_path_progress(db, study_path_id)

    db.commit()

    for topic in created_topics:
        db.refresh(topic)

    return created_topics


@router.post("/topics/{topic_id}/regenerate-visuals")
def regenerate_topic_visuals(
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    topic = get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)

    lesson = db.query(Lesson).filter(Lesson.topic_id == topic_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="No lesson found for this topic.")
    if lesson.generation_status == "generating":
        raise HTTPException(status_code=409, detail="Lesson is currently being generated.")

    topic_type = str(
        getattr(topic, "topic_type", None)
        or getattr(topic, "course_type", None)
        or ""
    ).strip()
    if not topic_type:
        raise HTTPException(status_code=400, detail="Topic has no topic_type set.")

    from app.services.lean_lesson_generator import patch_lesson_visuals

    updated_json = patch_lesson_visuals(lesson.lesson_json, topic_type)
    lesson.lesson_json = updated_json
    db.commit()

    return {"status": "ok"}
