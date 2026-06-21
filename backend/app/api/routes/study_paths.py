import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

# Max lessons generated concurrently. Each lesson is ~30k-48k tokens, so high
# concurrency multiplies the per-minute token rate and trips the OpenAI account's
# tokens-per-minute (TPM) limit — surfacing as 429s, long retry-backoff waits,
# the occasional topic stuck in "failed", and cache misses (concurrent calls all
# miss the shared prompt cache). 3 keeps the combined rate under a typical tier-1
# TPM while still parallelizing. Tune via AZALEA_LESSON_GEN_CONCURRENCY (raise it
# on higher OpenAI tiers, lower it to 1-2 on a free/low-limit key).
try:
    _LESSON_GEN_CONCURRENCY = max(1, int(os.getenv("AZALEA_LESSON_GEN_CONCURRENCY", "3")))
except ValueError:
    _LESSON_GEN_CONCURRENCY = 3

from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.database import SessionLocal
from app.models.content_chunk import ContentChunk
from app.models.learning_material import LearningMaterial
from app.models.lesson import Lesson
from app.models.practice_attempt import PracticeAttempt
from app.models.study_path import StudyPath
from app.models.study_session import StudySession
from app.models.topic import Topic
from app.schemas.lesson import LessonRead
from app.schemas.study_path import StudyPathCreate, StudyPathRead
from app.schemas.study_path_recommendation import (
    RecommendedTopicRead,
    StudyPathRecommendationRead,
)
from app.services.lesson_generator import (
    build_lesson_source_metadata,
)
from app.services.lean_lesson_generator import build_lean_lesson_from_topic_and_chunks
from app.services.legacy_v2_visual_bridge import attach_v2_visuals_to_legacy_lesson
from app.services.topic_generator import generate_topics_from_chunks
from app.services.llm_client import generate_title

router = APIRouter()


class StudyPathRegenerateRequest(BaseModel):
    feedback: str | None = None
    overwrite_existing: bool = False


class StudyPathInitialGenerationResponse(BaseModel):
    first_topic_id: str
    first_lesson_id: str
    background_generation_started: bool
    message: str
    # Phase 7 cutover scaffolding: 1 = legacy, 2 = v2 pipeline. Frontend
    # uses this to decide whether to redirect to /learn or /learn-v2.
    lesson_version: int = 1


def get_user_id(current_user: dict[str, Any]) -> str:
    return str(current_user["user_id"])


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


def get_chunks_for_study_path(
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


def create_topic_from_generated_data(
    study_path_id: str,
    topic_data: dict[str, Any],
    db: Session,
) -> Topic:
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
        order_index=topic_data["order_index"],
        estimated_minutes=topic_data["estimated_minutes"],
        course_type=topic_data.get("topic_type") or topic_data.get("course_type"),
        secondary_course_types=topic_data.get("secondary_course_types") or [],
        knowledge_level=topic_data.get("knowledge_level"),
        status="not_started",
    )
    db.add(topic)
    return topic


# A topic left in "generating" longer than this is treated as an abandoned
# claim (crashed worker, or a process restart that dropped in-flight background
# tasks) and may be re-claimed. Generous enough to cover a topic waiting its
# turn in the thread pool, so a healthy in-progress topic is never stolen.
_GENERATION_CLAIM_TTL = timedelta(minutes=10)


def _claim_remaining_topic_ids(study_path_id: str, use_v2: bool) -> list[str]:
    """Atomically claim the topics this caller should generate.

    Each topic is moved to "generating" only if it isn't already ready or under
    a fresh "generating" claim by another worker — so the create-flow job and
    the on-open `pregenerate_all_study_path_topics` job stop double-generating
    the same topic (which previously doubled spend and latency). The conditional
    UPDATE + unique(topic_id) constraint make the claim race-safe.
    """
    from app.services.lesson_cache import fresh_on_open

    # fresh-on-open: each topic is regenerated when opened, so pre-warming the rest of the path is
    # wasted LLM work — claim nothing.
    if fresh_on_open():
        return []

    claimed: list[str] = []
    db = SessionLocal()
    try:
        topics = (
            db.query(Topic)
            .filter(Topic.study_path_id == study_path_id)
            .order_by(Topic.order_index.asc())
            .offset(1)  # topic 1 already generated synchronously
            .all()
        )
        for t in topics:
            existing = db.query(Lesson).filter(Lesson.topic_id == t.id).first()
            if existing is None:
                # unique(topic_id) makes exactly one concurrent insert win.
                try:
                    db.add(Lesson(
                        topic_id=str(t.id),
                        title=t.title,
                        lesson_json={},
                        generation_status="generating",
                    ))
                    db.commit()
                    claimed.append(str(t.id))
                except Exception:
                    db.rollback()
                continue

            status = existing.generation_status
            needs_hybrid_refresh = not use_v2 and (
                _is_pure_v2_lesson_json(existing.lesson_json)
                or _needs_hybrid_visual_refresh(existing.lesson_json)
            )
            if status == "ready" and not needs_hybrid_refresh:
                continue
            if (
                status == "generating"
                and existing.created_at is not None
                and datetime.utcnow() - existing.created_at < _GENERATION_CLAIM_TTL
            ):
                continue  # another worker holds a fresh claim

            # Atomically transition from the status we observed; if a concurrent
            # worker moved it first, won == 0 and we skip it.
            won = (
                db.query(Lesson)
                .filter(Lesson.topic_id == t.id, Lesson.generation_status == status)
                .update({Lesson.generation_status: "generating"}, synchronize_session=False)
            )
            db.commit()
            if won == 1:
                claimed.append(str(t.id))
    finally:
        db.close()
    return claimed


def _generate_remaining_lessons_sequentially(
    study_path_id: str,
    use_v2: bool = False,
) -> None:
    """
    Background task: generate lean lessons for all topics after topic 1.

    Topic 1's lesson is already created synchronously before this fires. The
    remaining topics are generated concurrently over a small thread pool (each
    worker gets its own DB session), so an N-topic path finishes in ~ceil(N/6)
    rounds instead of N sequential rounds. Topics are claimed atomically so this
    job and the on-open pre-generation job never generate the same topic twice.

    Hybrid visual cutover: the normal path uses legacy lesson_cards as the
    canonical structure, then attaches v2 visual_models onto supported cards.
    Pass use_v2=True only for the standalone /learn-v2 experiment.
    """
    import logging
    logger = logging.getLogger(__name__)

    topic_ids = _claim_remaining_topic_ids(study_path_id, use_v2)
    if not topic_ids:
        return

    def _generate_one(topic_id: str) -> None:
        tdb = SessionLocal()
        try:
            topic = tdb.query(Topic).filter(Topic.id == topic_id).first()
            if not topic:
                return
            study_path = tdb.query(StudyPath).filter(StudyPath.id == topic.study_path_id).first()
            if not study_path:
                return
            chunks = get_chunks_for_study_path(
                study_path=study_path, db=tdb, limit=6, allow_empty=True
            )
            source_chunk_ids, source_summary = build_lesson_source_metadata(chunks)

            def _persist(lj: dict, *, allow_overwrite: bool) -> None:
                """Upsert the lesson as ready. ``allow_overwrite=False`` is the base/lean commit (skips
                if another job already produced a ready lesson); ``True`` is our own enriched upgrade."""
                lesson = tdb.query(Lesson).filter(Lesson.topic_id == topic_id).first()
                if lesson:
                    if not allow_overwrite and lesson.generation_status == "ready" and lesson.lesson_json:
                        return
                    lesson.lesson_json = lj
                    lesson.source_chunk_ids = source_chunk_ids
                    lesson.source_summary = source_summary
                    lesson.generation_status = "ready"
                else:
                    tdb.add(Lesson(
                        topic_id=topic_id, title=topic.title, lesson_json=lj,
                        source_chunk_ids=source_chunk_ids, source_summary=source_summary,
                        generation_status="ready",
                    ))
                tdb.commit()

            if use_v2:
                lesson_json = _build_v2_lesson_for_topic(topic=topic, chunks=chunks)
                _persist(lesson_json, allow_overwrite=True)
            else:
                # Two-phase: commit the LEAN lesson 'ready' BEFORE the slow enrich (so a coding topic's
                # heavy clean-code + walkthrough + worked-example solve can't leave it unrendered/'failed'
                # on timeout), then upgrade the SAME lesson with the enriched version.
                lesson_json = _build_legacy_lesson_with_v2_visuals(
                    topic=topic, chunks=chunks,
                    on_base_ready=lambda lean: _persist(lean, allow_overwrite=False),
                )
                _persist(lesson_json, allow_overwrite=True)
        except Exception:
            logger.exception("Background lesson generation failed for topic %s", topic_id)
            try:
                tdb.rollback()
                lesson = tdb.query(Lesson).filter(Lesson.topic_id == topic_id).first()
                # Do NOT downgrade a lesson that already committed 'ready' in phase 1 — a failure in
                # the (additive) enrich upgrade must not blank a topic that already renders.
                if lesson and lesson.generation_status != "ready":
                    lesson.generation_status = "failed"
                    tdb.commit()
            except Exception:
                pass
        finally:
            tdb.close()

    max_workers = min(len(topic_ids), _LESSON_GEN_CONCURRENCY)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_generate_one, tid): tid for tid in topic_ids}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                pass


def is_topic_review_due(topic: Topic) -> bool:
    if not topic.review_due_at:
        return False

    return topic.review_due_at <= datetime.utcnow()


def build_recommendation_response(
    topic: Topic,
    message: str,
) -> StudyPathRecommendationRead:
    return StudyPathRecommendationRead(
        message=message,
        topic=RecommendedTopicRead(
            id=str(topic.id),
            title=topic.title,
            status=topic.status,
            estimated_minutes=topic.estimated_minutes,
        ),
        is_complete=False,
    )


def is_attempt_weak_area(attempt: PracticeAttempt) -> bool:
    if attempt.performance_level == "strong":
        return False

    if attempt.is_correct is True and attempt.performance_level not in {
        "fragile",
        "minor_mistake",
        "weak",
    }:
        return False

    return True


def get_topic_weak_area_counts(
    db: Session,
    topic_ids: list[str],
) -> dict[str, dict[str, int]]:
    if not topic_ids:
        return {}

    attempts = (
        db.query(PracticeAttempt)
        .filter(PracticeAttempt.topic_id.in_(topic_ids))
        .order_by(PracticeAttempt.created_at.desc())
        .all()
    )

    weak_area_counts_by_topic: dict[str, dict[str, int]] = {}

    for attempt in attempts:
        if not is_attempt_weak_area(attempt):
            continue

        topic_id = str(attempt.topic_id)
        mistake_type = attempt.mistake_type or "Unclassified mistake"

        if topic_id not in weak_area_counts_by_topic:
            weak_area_counts_by_topic[topic_id] = {}

        if mistake_type not in weak_area_counts_by_topic[topic_id]:
            weak_area_counts_by_topic[topic_id][mistake_type] = 0

        weak_area_counts_by_topic[topic_id][mistake_type] += 1

    return weak_area_counts_by_topic


def get_best_weak_area_for_topic(
    weak_area_counts: dict[str, int],
) -> tuple[str, int] | None:
    if not weak_area_counts:
        return None

    mistake_type, count = max(
        weak_area_counts.items(),
        key=lambda item: item[1],
    )

    return mistake_type, count


def find_topic_with_repeated_weak_area(
    topics: list[Topic],
    weak_area_counts_by_topic: dict[str, dict[str, int]],
) -> tuple[Topic, str, int] | None:
    best_match: tuple[Topic, str, int] | None = None

    for topic in topics:
        topic_weak_area_counts = weak_area_counts_by_topic.get(str(topic.id), {})
        best_weak_area = get_best_weak_area_for_topic(topic_weak_area_counts)

        if not best_weak_area:
            continue

        mistake_type, count = best_weak_area

        if count < 2:
            continue

        if best_match is None or count > best_match[2]:
            best_match = (topic, mistake_type, count)

    return best_match


@router.post("/", response_model=StudyPathRead)
def create_study_path(
    payload: StudyPathCreate,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    title = generate_title(payload.goal or payload.title)

    study_path = StudyPath(
        user_id=get_user_id(current_user),
        title=title,
        goal=payload.goal,
        estimated_minutes_remaining=payload.estimated_minutes_remaining,
    )

    db.add(study_path)
    db.commit()
    db.refresh(study_path)

    return study_path


@router.get("/", response_model=list[StudyPathRead])
def list_study_paths(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    return (
        db.query(StudyPath)
        .filter(StudyPath.user_id == get_user_id(current_user))
        .order_by(StudyPath.created_at.desc())
        .all()
    )


@router.get("/{study_path_id}", response_model=StudyPathRead)
def get_study_path(
    study_path_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    return get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )


@router.post(
    "/{study_path_id}/generate-initial",
    response_model=StudyPathInitialGenerationResponse,
)
def generate_initial_study_path_content(
    study_path_id: str,
    background_tasks: BackgroundTasks,
    use_v2: bool = False,
    regenerate: bool = False,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Generate the first lesson for a study path.

    Hybrid visual cutover (default, 2026-06-04):
      use_v2 defaults to False so the normal learner flow keeps the legacy
      topic/card structure and next-topic navigation. Legacy cards are
      enriched with v2 visual_models where supported. Pass ?use_v2=true only
      for the standalone /learn-v2 experiment.

    Regeneration:
      Pass ?regenerate=true to wipe an existing cached lesson on the
      first topic and re-run generation. Use this when an existing
      lesson was generated under a stale schema and you want it
      re-rolled under the current pipeline.
    """
    _ = background_tasks
    study_path = get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )

    existing_topics = (
        db.query(Topic)
        .filter(Topic.study_path_id == study_path_id)
        .order_by(Topic.order_index.asc())
        .all()
    )

    if existing_topics:
        first_topic = existing_topics[0]
        first_lesson = (
            db.query(Lesson).filter(Lesson.topic_id == first_topic.id).first()
        )

        # ?regenerate=true wipes the existing lesson so the branch below
        # re-runs generation. Cascades nothing else; only the first lesson
        # is regenerated synchronously here. Subsequent lessons get
        # regenerated lazily as the learner visits them (legacy behavior).
        needs_hybrid_refresh = (
            first_lesson is not None
            and not use_v2
            and (
                _is_pure_v2_lesson_json(first_lesson.lesson_json)
                or _needs_hybrid_visual_refresh(first_lesson.lesson_json)
            )
        )
        if (regenerate or needs_hybrid_refresh) and first_lesson is not None:
            db.delete(first_lesson)
            db.commit()
            first_lesson = None

        if not first_lesson:
            chunks = get_chunks_for_study_path(
                study_path=study_path,
                db=db,
                limit=6,
                allow_empty=True,
            )
            source_chunk_ids, source_summary = build_lesson_source_metadata(chunks)
            if use_v2:
                lesson_json = _build_v2_lesson_for_topic(
                    topic=first_topic,
                    chunks=chunks,
                )
            else:
                lesson_json = _build_legacy_lesson_with_v2_visuals(
                    topic=first_topic,
                    chunks=chunks,
                )
            first_lesson = Lesson(
                topic_id=first_topic.id,
                title=first_topic.title,
                lesson_json=lesson_json,
                source_chunk_ids=source_chunk_ids,
                source_summary=source_summary,
                generation_status="ready",
            )
            db.add(first_lesson)
            db.commit()
            db.refresh(first_lesson)

        background_tasks.add_task(
            _generate_remaining_lessons_sequentially, study_path_id, use_v2
        )
        resolved_version = int(
            (first_lesson.lesson_json or {}).get("lesson_version") or 1
        ) if isinstance(first_lesson.lesson_json, dict) else 1
        return StudyPathInitialGenerationResponse(
            first_topic_id=str(first_topic.id),
            first_lesson_id=str(first_lesson.id),
            background_generation_started=True,
            message="Lesson ready. Remaining topics generating in background.",
            lesson_version=resolved_version,
        )

    chunks = get_chunks_for_study_path(
        study_path=study_path,
        db=db,
        limit=8,
        allow_empty=True,
    )
    generated_topic_data = generate_topics_from_chunks(
        chunks=chunks,
        goal=study_path.goal,
    )

    created_topics: list[Topic] = []

    for topic_data in generated_topic_data:
        topic = create_topic_from_generated_data(
            study_path_id=study_path_id,
            topic_data=topic_data,
            db=db,
        )
        created_topics.append(topic)

    db.flush()
    first_topic = created_topics[0]

    source_chunk_ids, source_summary = build_lesson_source_metadata(chunks)
    if use_v2:
        first_lesson_json = _build_v2_lesson_for_topic(
            topic=first_topic,
            chunks=chunks,
        )
    else:
        first_lesson_json = _build_legacy_lesson_with_v2_visuals(
            topic=first_topic,
            chunks=chunks,
        )
    first_lesson = Lesson(
        topic_id=first_topic.id,
        title=first_topic.title,
        lesson_json=first_lesson_json,
        source_chunk_ids=source_chunk_ids,
        source_summary=source_summary,
        generation_status="ready",
    )
    db.add(first_lesson)
    recalculate_study_path_progress(db, study_path_id)
    db.commit()
    db.refresh(first_topic)
    db.refresh(first_lesson)

    background_tasks.add_task(
        _generate_remaining_lessons_sequentially, study_path_id, use_v2
    )
    resolved_version = int(
        (first_lesson.lesson_json or {}).get("lesson_version") or 1
    ) if isinstance(first_lesson.lesson_json, dict) else 1
    return StudyPathInitialGenerationResponse(
        first_topic_id=str(first_topic.id),
        first_lesson_id=str(first_lesson.id),
        background_generation_started=True,
        message="Lesson ready. Remaining topics generating in background.",
        lesson_version=resolved_version,
    )


def _build_v2_lesson_for_topic(
    topic: Topic,
    chunks: list[ContentChunk],
) -> dict[str, Any]:
    """Phase 7 cutover helper: run the v2 pipeline for a topic and return
    the LessonV2 dict. Imports are local so the legacy path doesn't pay
    the import cost.

    On any failure, raises HTTPException(500). Callers may choose to
    catch + fall back to legacy if they want degradation; current callers
    surface the error so misuse is loud rather than silent.

    Emits a v2_telemetry.csv row on completion (success or failure).
    """
    import json as _json

    from app.prompts.lean_lesson_prompt_v2 import (
        SYSTEM_PROMPT_V2,
        build_lesson_v2_prompt,
    )
    from app.services.lean_lesson_generator_v2 import compile_lesson_v2
    from app.services.llm_client import client
    from app.services.llm_schemas_v2 import LESSON_V2_SCHEMA
    from app.services.topic_classifier_v2 import classify_topic_v2
    from app.services.v2_telemetry import record_generation
    from app.services.visual_validators_v2 import validate_lesson_v2

    classification = classify_topic_v2(
        topic_title=topic.title or "",
        topic_summary=getattr(topic, "description", "") or "",
        topic_type=str(getattr(topic, "topic_type", None) or "concept_intuition"),
        knowledge_level=None,
    )

    chunk_excerpts: list[str] = []
    for index, chunk in enumerate(chunks[:6], start=1):
        chunk_excerpts.append(
            f"--- SOURCE CHUNK {index} ---\n"
            f"Material id: {chunk.material_id}\n"
            f"Chunk index: {chunk.chunk_index}\n\n"
            f"{chunk.text}"
        )
    chunks_text = "\n\n".join(chunk_excerpts)

    user_prompt = build_lesson_v2_prompt(
        topic_title=topic.title or "",
        topic_summary=getattr(topic, "description", "") or "",
        topic_type=classification["topic_type"],
        visual_domain=classification["visual_domain"],
        visual_mode_hint=classification["visual_mode_hint"],
        knowledge_level=None,
        chunks_text=chunks_text,
    )

    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "system", "content": SYSTEM_PROMPT_V2},
                {"role": "user", "content": user_prompt},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "lesson_v2",
                    # strict=False: see comment in lessons_v2.generate_lesson_v2.
                    # WorkedExamplePlan.base_state + state_after are polymorphic
                    # (type-specific shape) and use additionalProperties=true,
                    # which strict mode rejects. Backend validators catch
                    # real shape issues.
                    "strict": False,
                    "schema": LESSON_V2_SCHEMA,
                },
            },
        )
        raw_text = response.output_text
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"v2 LLM call failed: {exc}",
        )

    try:
        lesson_v2_raw = _json.loads(raw_text)
    except _json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"v2 LLM returned invalid JSON: {exc}",
        )

    source_chunk_ids = [str(c.id) for c in chunks]
    source_summary = "\n".join(
        f"- chunk {c.chunk_index}"
        for c in chunks
    )

    with record_generation(pipeline="v2", topic_id=str(topic.id)) as telemetry:
        lesson = compile_lesson_v2(
            lesson_v2_raw=lesson_v2_raw,
            topic_id=str(topic.id),
            topic_hint=topic.title or "",
            topic_type=classification["topic_type"],
            visual_domain=classification["visual_domain"],
            source_chunks_excerpt=chunks_text[:2000],
            source_chunk_ids=source_chunk_ids,
            source_summary=source_summary,
        )
        telemetry["lesson"] = lesson
        report = validate_lesson_v2(lesson)
        telemetry["validator_errors"] = len(report.errors())
        telemetry["validator_warnings"] = len(report.warnings())
    return lesson


def _build_legacy_lesson_with_v2_visuals(
    topic: Topic,
    chunks: list[ContentChunk],
    on_base_ready=None,
) -> dict[str, Any]:
    """Build the legacy lesson_cards contract and enrich supported cards
    with v2 VisualModels.

    This is the normal production flow during the visual-system cutover:
    legacy controls instructional structure; v2 controls richer visuals.

    ``on_base_ready(lesson_json)`` (optional) is called with the renderable LEAN lesson BEFORE the
    slow enrich runs — callers use it to mark the topic ``ready`` immediately so a heavy/slow enrich
    (clean code + per-line walkthrough + worked example, on coding topics) can never leave the topic
    unrendered or ``failed`` on timeout. Enrich then upgrades the lesson in place.
    """
    lesson_json = build_lean_lesson_from_topic_and_chunks(
        topic=topic,
        chunks=chunks,
    )
    if not isinstance(lesson_json, dict):
        return lesson_json

    if on_base_ready is not None:
        try:
            on_base_ready(lesson_json)  # render the lean lesson NOW; enrich upgrades it below
        except Exception:  # noqa: BLE001 — an early-commit hiccup must not stop enrich
            import logging
            logging.getLogger(__name__).exception("study-path base-ready callback failed for %s", topic.id)

    # Run the FULL enrich (v2 visuals + clean code + per-line walkthrough + WORKED-EXAMPLE solve +
    # finalize) — the SAME path the single-topic/regen flow runs. Previously this bulk builder only
    # attached visuals, so the worked example was NEVER authored during study-path generation.
    # RESILIENCE: the enrich is the heaviest, slowest, most failure-prone step (especially on coding
    # topics: clean_code + per-line walkthrough + WE solve). If it fails/raises for ANY reason, we keep
    # the already-built LEAN lesson so the topic STILL RENDERS — a coding topic must never come back
    # blank. Lazy import avoids a routes-module import cycle.
    try:
        from app.api.routes.lessons import enrich_legacy_lesson_with_v2_visuals

        enrich_legacy_lesson_with_v2_visuals(topic=topic, lesson_json=lesson_json)
    except Exception:  # noqa: BLE001 — enrich is additive; a failure must not blank the lesson
        import logging
        logging.getLogger(__name__).exception(
            "study-path enrich failed for topic %s (%s) — rendering lean lesson",
            topic.id, getattr(topic, "course_type", None) or getattr(topic, "topic_type", None),
        )
    return lesson_json


def _is_pure_v2_lesson_json(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("render_steps"), list)
        and isinstance(value.get("visual_models"), list)
        and not isinstance(value.get("lesson_cards"), list)
    )


def _needs_hybrid_visual_refresh(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if not isinstance(value.get("lesson_cards"), list):
        return False
    metadata = value.get("metadata") or {}
    return not isinstance(metadata.get("visual_v2_bridge"), dict)


@router.get(
    "/{study_path_id}/recommendation",
    response_model=StudyPathRecommendationRead,
)
def get_study_path_recommendation(
    study_path_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    study_path = get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )

    topics = (
        db.query(Topic)
        .filter(Topic.study_path_id == study_path.id)
        .order_by(Topic.order_index.asc())
        .all()
    )

    if not topics:
        return StudyPathRecommendationRead(
            message="Generate topics first so Azalea can recommend what to study next.",
            topic=None,
            is_complete=False,
        )

    due_review_topic = next(
        (topic for topic in topics if is_topic_review_due(topic)),
        None,
    )

    if due_review_topic:
        return build_recommendation_response(
            topic=due_review_topic,
            message="Review this topic next because it is due for a spaced check.",
        )

    topic_ids = [str(topic.id) for topic in topics]
    weak_area_counts_by_topic = get_topic_weak_area_counts(
        db=db,
        topic_ids=topic_ids,
    )

    repeated_weak_area_topic = find_topic_with_repeated_weak_area(
        topics=topics,
        weak_area_counts_by_topic=weak_area_counts_by_topic,
    )

    if repeated_weak_area_topic:
        topic, mistake_type, count = repeated_weak_area_topic

        return build_recommendation_response(
            topic=topic,
            message=(
                "Retest this topic next because Azalea detected a repeated "
                f"{mistake_type} pattern across {count} practice attempts."
            ),
        )

    needs_review_topic = next(
        (topic for topic in topics if topic.status == "needs_review"),
        None,
    )

    if needs_review_topic:
        return build_recommendation_response(
            topic=needs_review_topic,
            message="Review this topic next because it is marked as needing more work.",
        )

    in_progress_topic = next(
        (topic for topic in topics if topic.status == "in_progress"),
        None,
    )

    if in_progress_topic:
        return build_recommendation_response(
            topic=in_progress_topic,
            message="Continue this topic next because you have already started it.",
        )

    not_started_topic = next(
        (topic for topic in topics if topic.status == "not_started"),
        None,
    )

    if not_started_topic:
        return build_recommendation_response(
            topic=not_started_topic,
            message="Start this topic next because it is the next unfinished topic in the path.",
        )

    incomplete_topic = next(
        (topic for topic in topics if topic.status != "completed"),
        None,
    )

    if incomplete_topic:
        return build_recommendation_response(
            topic=incomplete_topic,
            message="Work on this topic next because it is not completed yet.",
        )

    return StudyPathRecommendationRead(
        message="This study path is complete. You can review previous practice attempts or regenerate topics if you want more practice.",
        topic=None,
        is_complete=True,
    )


@router.post("/{study_path_id}/regenerate", response_model=list[LessonRead])
def regenerate_study_path(
    study_path_id: str,
    payload: StudyPathRegenerateRequest,
    use_v2: bool = False,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    study_path = get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )

    chunks = get_chunks_for_study_path(
        study_path=study_path,
        db=db,
        limit=8,
        allow_empty=True,
    )

    existing_topics = (
        db.query(Topic)
        .filter(Topic.study_path_id == study_path.id)
        .all()
    )

    if existing_topics and not payload.overwrite_existing:
        raise HTTPException(
            status_code=409,
            detail=(
                "This study path already has topics. Send overwrite_existing=true "
                "to regenerate and replace the existing path."
            ),
        )

    for topic in existing_topics:
        detach_and_delete_existing_topic_data(db=db, topic=topic)

    db.flush()

    generated_topic_data = generate_topics_from_chunks(
        chunks=chunks,
        goal=study_path.goal,
        feedback=payload.feedback,
    )

    created_topics: list[Topic] = []

    for topic_data in generated_topic_data:
        topic = Topic(
            study_path_id=study_path.id,
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
            order_index=topic_data["order_index"],
            estimated_minutes=topic_data["estimated_minutes"],
            course_type=topic_data.get("topic_type") or topic_data.get("course_type"),
            secondary_course_types=topic_data.get("secondary_course_types") or [],
            knowledge_level=topic_data.get("knowledge_level"),
            status="not_started",
        )
        db.add(topic)
        created_topics.append(topic)

    db.flush()

    source_chunk_ids, source_summary = build_lesson_source_metadata(chunks)
    generated_lessons: list[Lesson] = []

    topic_lessons: dict[str, dict] = {}
    if use_v2:
        # Standalone /learn-v2 experiment. The normal route uses legacy
        # lesson_cards plus v2 visual attachments.
        for topic in created_topics:
            topic_lessons[topic.id] = _build_v2_lesson_for_topic(
                topic=topic,
                chunks=chunks,
            )
    else:
        def _generate(topic: Topic) -> tuple[Topic, dict]:
            return topic, _build_legacy_lesson_with_v2_visuals(
                topic=topic,
                chunks=chunks,
            )

        max_workers = min(len(created_topics), _LESSON_GEN_CONCURRENCY)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_generate, topic): topic for topic in created_topics}
            for future in as_completed(futures):
                topic = futures[future]
                try:
                    _topic, lesson_json = future.result()
                    topic_lessons[topic.id] = lesson_json
                except Exception:  # noqa: BLE001 — isolate per topic: one failure must not blank others
                    import logging
                    logging.getLogger(__name__).exception(
                        "study-path: lesson build failed for topic %s — lean fallback", topic.id
                    )
                    try:
                        topic_lessons[topic.id] = build_lean_lesson_from_topic_and_chunks(
                            topic=topic, chunks=chunks
                        )
                    except Exception:  # noqa: BLE001 — last resort: a flagged empty lesson, never a KeyError
                        topic_lessons[topic.id] = {
                            "lesson_cards": [],
                            "metadata": {"quality": {"generation_failed": True}},
                        }

    for topic in created_topics:
        lesson_json = topic_lessons[topic.id]
        lesson = Lesson(
            topic_id=topic.id,
            title=topic.title,
            lesson_json=lesson_json,
            source_chunk_ids=source_chunk_ids,
            source_summary=source_summary,
        )
        db.add(lesson)
        generated_lessons.append(lesson)

    recalculate_study_path_progress(db, str(study_path.id))

    db.commit()

    for lesson in generated_lessons:
        db.refresh(lesson)

    return generated_lessons


class OpenStudyPathRequest(BaseModel):
    target: str
    source_study_path_id: str | None = None


class OpenStudyPathResponse(BaseModel):
    study_path_id: str
    title: str
    created: bool


@router.post("/resolve-target", response_model=OpenStudyPathResponse)
def resolve_open_study_path(
    payload: OpenStudyPathRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Find or create a study path for the given target concept (used by open_study_path interactive links)."""
    user_id = get_user_id(current_user)
    target = payload.target.strip()

    if not target:
        raise HTTPException(status_code=400, detail="target cannot be empty")

    target_lower = target.lower()
    existing_paths = (
        db.query(StudyPath)
        .filter(StudyPath.user_id == user_id)
        .order_by(StudyPath.created_at.desc())
        .all()
    )

    for path in existing_paths:
        path_title_lower = (path.title or "").lower()
        path_goal_lower = (path.goal or "").lower()
        if target_lower in path_title_lower or target_lower in path_goal_lower:
            return OpenStudyPathResponse(
                study_path_id=str(path.id),
                title=path.title,
                created=False,
            )

    title = generate_title(target)
    new_path = StudyPath(
        user_id=user_id,
        title=title,
        goal=f"Learn {target}",
    )
    db.add(new_path)
    db.commit()
    db.refresh(new_path)

    return OpenStudyPathResponse(
        study_path_id=str(new_path.id),
        title=new_path.title,
        created=True,
    )
