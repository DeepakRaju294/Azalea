import json as _json
from typing import Any

from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.schemas.lesson_generation import GenerateTopicLessonPayload
from app.services.adaptive_lesson_prompt import build_adaptive_lesson_instruction
from app.api.deps import get_current_user, get_db
from app.api.ownership import get_owned_study_path, get_owned_topic
from app.models.content_chunk import ContentChunk
from app.models.learning_material import LearningMaterial
from app.models.lesson import Lesson
from app.models.study_path import StudyPath
from app.models.topic import Topic
from app.services.learner_memory import (
    build_study_path_memory_summary,
    format_memory_summary_for_prompt,
)
from app.services.knowledge_level_service import (
    estimate_knowledge_level_result,
    knowledge_level_to_generation_guidance,
)
from app.services.course_type_classifier import classify_topic_course_type
from app.schemas.lesson import (
    LessonCreate,
    LessonRead,
    LessonSegmentRegenerateRequest,
    LessonSegmentRegenerateResponse,
)
from app.services.lesson_generator import (
    build_lesson_source_metadata,
    extract_prior_concept_states,
    regenerate_future_lesson_cards,
)
from app.services.lean_lesson_generator import (
    build_lean_lesson_from_topic_and_chunks,
    build_lean_lesson_streaming,
    pregenerate_all_study_path_topics,
)
from app.services.legacy_v2_visual_bridge import attach_v2_visuals_to_legacy_lesson

router = APIRouter()


class LessonRegenerateRequest(BaseModel):
    feedback: str | None = None


def get_source_chunks_for_topic(
    topic: Topic,
    db: Session,
    limit: int = 6,
    allow_empty: bool = True,
) -> list[ContentChunk]:
    study_path = topic.study_path

    if not study_path:
        raise HTTPException(status_code=404, detail="Study path not found")

    return get_source_chunks_for_study_path(
        study_path=study_path,
        db=db,
        limit=limit,
        allow_empty=allow_empty,
    )


def get_source_chunks_for_study_path(
    study_path: StudyPath,
    db: Session,
    limit: int = 8,
    allow_empty: bool = True,
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


def create_or_update_lesson_record(
    topic: Topic,
    lesson_json: dict,
    db: Session,
    chunks: list[ContentChunk] | None = None,
    generation_status: str = "ready",
) -> Lesson:
    source_chunk_ids: list[str] | None = None
    source_summary: str | None = None

    if chunks is not None:
        source_chunk_ids, source_summary = build_lesson_source_metadata(chunks)

    existing_lesson = db.query(Lesson).filter(Lesson.topic_id == topic.id).first()

    if existing_lesson:
        existing_lesson.title = topic.title
        existing_lesson.lesson_json = lesson_json
        existing_lesson.source_chunk_ids = source_chunk_ids
        existing_lesson.source_summary = source_summary
        existing_lesson.generation_status = generation_status

        db.commit()
        db.refresh(existing_lesson)

        return existing_lesson

    lesson = Lesson(
        topic_id=topic.id,
        title=topic.title,
        lesson_json=lesson_json,
        source_chunk_ids=source_chunk_ids,
        source_summary=source_summary,
        generation_status=generation_status,
    )

    db.add(lesson)
    db.commit()
    db.refresh(lesson)

    return lesson


def build_legacy_lesson_with_v2_visuals(
    topic: Topic,
    chunks: list[ContentChunk],
    feedback: str | None = None,
) -> dict:
    # Phase 5 (EXAMPLE_SYSTEM_SPEC §6): blueprint skeleton-fill generation — code
    # lays out the cards, the LLM writes only per-card prose. Flag-gated + reversible;
    # the legacy single-call generator is the default. Falls back on any failure.
    from app.services.examples.skeleton_fill import (
        fill_skeleton_lesson,
        llm_slot_filler,
        skeleton_fill_enabled,
    )

    lesson_json = None
    if skeleton_fill_enabled():
        try:
            lesson_json = fill_skeleton_lesson(topic=topic, chunks=chunks, slot_filler=llm_slot_filler)
        except Exception:  # noqa: BLE001 — fall back to the proven generator
            import logging
            logging.getLogger(__name__).exception("skeleton_fill generation failed for topic %s", topic.id)
            lesson_json = None
    if lesson_json is None:
        lesson_json = build_lean_lesson_from_topic_and_chunks(
            topic=topic,
            chunks=chunks,
            feedback=feedback,
        )
    enrich_legacy_lesson_with_v2_visuals(topic=topic, lesson_json=lesson_json)
    return lesson_json


def enrich_legacy_lesson_with_v2_visuals(
    topic: Topic,
    lesson_json: dict,
) -> dict:
    if not isinstance(lesson_json, dict):
        return lesson_json
    attach_v2_visuals_to_legacy_lesson(
        lesson_json,
        topic_id=str(topic.id),
        topic_title=topic.title or "",
        topic_type=str(getattr(topic, "course_type", None) or "concept_intuition"),
        visual_domain=None,
    )

    # Visual System V2 pilot (default-OFF). For a flag-enabled graph-traversal
    # topic, replace the worked-example trace with a simulator-authoritative V2
    # trace. Inert unless AZALEA_VISUAL_V2_MODES is set; failures never break the
    # lesson (the legacy path above already produced a complete lesson).
    try:
        from app.services.examples.handoff import (
            apply_fixture_to_lesson,
            ensure_worked_example_setup,
            validate_and_order_cards,
        )
        from app.services.visual_v2.code_lesson_integration import apply_code_execution_to_lesson

        _v2_topic = {
            "id": str(topic.id),
            "title": topic.title or "",
            "topic_type": str(getattr(topic, "course_type", None) or getattr(topic, "topic_type", "") or ""),
        }
        # Example-ontology path first (EXAMPLE_SYSTEM_SPEC §4.5) — the unified,
        # fixture-driven adapter. The binary-search and graph ad-hoc adapters are
        # RETIRED (spec §7): the fixture path fully covers their topics with richer
        # output. The code adapter remains as the fallback for coding topics whose
        # title has no fixture yet (it traces the lesson's own code).
        if not apply_fixture_to_lesson(lesson_json, _v2_topic):
            apply_code_execution_to_lesson(lesson_json, _v2_topic)

        # Deterministic guarantees, ANY path: a concept worked example always opens
        # with a setup card stating the problem, and the final card set matches the
        # topic type's blueprint keys + order (CardValidator, spec §5.3 #5).
        ensure_worked_example_setup(lesson_json, _v2_topic)
        validate_and_order_cards(lesson_json, _v2_topic)
        # Final shape-agnostic guardrail over EVERY visual (legacy + computed): drop
        # malformed/degenerate diagrams and any diagram slot that points at code.
        from app.services.legacy_v2_visual_bridge import gate_legacy_visuals

        gate_legacy_visuals(lesson_json)

        # Worked-example completion audit (prose-path INV-COMPLETE): a worked example
        # that doesn't reach the final answer is flagged + (when a regenerator is wired)
        # regenerated up to a hard cap; if still incomplete it's logged, never silently
        # shipped. `regenerate=None` for now → audits + logs.
        from app.services.examples.worked_example_audit import audit_worked_examples

        audit_worked_examples(lesson_json, _v2_topic, regenerate=None, max_regenerations=2)
    except Exception:  # noqa: BLE001 — V2 is additive; never let it break legacy
        import logging

        logging.getLogger(__name__).exception("visual_v2 apply failed for topic %s", topic.id)

    return lesson_json


def lesson_json_needs_hybrid_visual_refresh(lesson_json: Any) -> bool:
    # Delegates to the bridge's pure version check (re-enrich cached lessons stamped by
    # an older bridge version, so they pick up the latest fixes).
    from app.services.legacy_v2_visual_bridge import needs_visual_refresh

    return needs_visual_refresh(lesson_json)


def lesson_json_needs_example_ontology_refresh(lesson_json: Any, topic: Topic) -> bool:
    """A cached lesson should be upgraded on read when the example-ontology path
    (EXAMPLE_SYSTEM_SPEC §4.5) applies to this topic but hasn't been applied yet —
    so existing lessons pick up new fixtures without a manual regeneration."""
    if not isinstance(lesson_json, dict) or not isinstance(lesson_json.get("lesson_cards"), list):
        return False
    metadata = lesson_json.get("metadata") or {}
    try:
        from app.services.examples.declaration import declare_example, pick_fixture
        from app.services.examples.handoff import APPLY_VERSION, pipeline_mode, resolve_visual
        from app.services.visual_v2.flags import is_v2_enabled

        applied = metadata.get("visual_v2_example_ontology") if isinstance(metadata, dict) else None

        declared = declare_example({
            "id": str(topic.id),
            "title": topic.title or "",
            "topic_type": str(getattr(topic, "course_type", None) or getattr(topic, "topic_type", "") or ""),
        })
        if declared is None:
            # Stale apply (e.g. an intro that got an example before the blueprint
            # gate existed) → re-enrich so the cleanup pass removes it.
            return isinstance(applied, dict)
        if isinstance(applied, dict) and int(applied.get("version") or 1) >= APPLY_VERSION:
            return False  # already applied at the current quality level
        fixture = pick_fixture(declared)
        if fixture is None:
            return False
        _base, mode = resolve_visual(fixture)
        return is_v2_enabled(pipeline_mode(mode), declared.application)
    except Exception:  # noqa: BLE001 — never block a lesson read
        return False


@router.post("/topics/{topic_id}/lesson", response_model=LessonRead)
def create_or_replace_lesson(
    topic_id: str,
    payload: LessonCreate,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)

    existing_lesson = db.query(Lesson).filter(Lesson.topic_id == topic_id).first()

    if existing_lesson:
        existing_lesson.title = payload.title
        existing_lesson.lesson_json = payload.lesson_json
        existing_lesson.source_chunk_ids = payload.source_chunk_ids
        existing_lesson.source_summary = payload.source_summary

        db.commit()
        db.refresh(existing_lesson)

        return existing_lesson

    lesson = Lesson(
        topic_id=topic_id,
        title=payload.title,
        lesson_json=payload.lesson_json,
        source_chunk_ids=payload.source_chunk_ids,
        source_summary=payload.source_summary,
    )

    db.add(lesson)
    db.commit()
    db.refresh(lesson)

    return lesson


@router.get("/topics/{topic_id}/lesson", response_model=LessonRead)
def get_topic_lesson(
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    topic = get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)

    lesson = db.query(Lesson).filter(Lesson.topic_id == topic_id).first()

    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    # On-read migration: lift cached v2 lessons to the current schema
    # version. Cheap; no-op when the lesson is already at the latest
    # version or is not v2.
    if isinstance(lesson.lesson_json, dict) and lesson.lesson_json.get("lesson_version") == 2:
        try:
            from app.services.v2_lesson_migrations import migrate_stored_lesson
            from sqlalchemy.orm.attributes import flag_modified
            _, changed = migrate_stored_lesson(lesson.lesson_json)
            if changed:
                flag_modified(lesson, "lesson_json")
                db.commit()
        except Exception:  # noqa: BLE001
            # Never let a migration failure block lesson read.
            pass

    if lesson_json_needs_hybrid_visual_refresh(lesson.lesson_json) or lesson_json_needs_example_ontology_refresh(lesson.lesson_json, topic):
        try:
            from sqlalchemy.orm.attributes import flag_modified
            enrich_legacy_lesson_with_v2_visuals(topic=topic, lesson_json=lesson.lesson_json)
            flag_modified(lesson, "lesson_json")
            db.commit()
            db.refresh(lesson)
        except Exception:  # noqa: BLE001
            pass

    return lesson


def _get_prior_concept_states(topic: Topic, db: Session) -> dict[str, str]:
    prev_topic = (
        db.query(Topic)
        .filter(
            Topic.study_path_id == topic.study_path_id,
            Topic.order_index < topic.order_index,
        )
        .order_by(Topic.order_index.desc())
        .first()
    )
    if not prev_topic:
        return {}
    prev_lesson = db.query(Lesson).filter(Lesson.topic_id == prev_topic.id).first()
    if not prev_lesson or not isinstance(prev_lesson.lesson_json, dict):
        return {}
    return extract_prior_concept_states(prev_lesson.lesson_json)


def _pregenerate_pipeline(current_topic_id: str, lookahead: int = 2) -> None:
    """Background task: generate lessons for the next `lookahead` topics in the study path.

    Runs after the user's topic N lesson is returned. Generates N+1, then N+2 sequentially
    so those lessons are ready in the DB before the user reaches them.
    """
    db = SessionLocal()
    try:
        current = db.query(Topic).filter(Topic.id == current_topic_id).first()
        if not current:
            return

        pivot_order = current.order_index

        for _ in range(lookahead):
            next_topic = (
                db.query(Topic)
                .filter(
                    Topic.study_path_id == current.study_path_id,
                    Topic.order_index > pivot_order,
                )
                .order_by(Topic.order_index.asc())
                .first()
            )
            if not next_topic:
                break

            existing = db.query(Lesson).filter(Lesson.topic_id == next_topic.id).first()
            if (
                existing
                and existing.generation_status == "ready"
                and not lesson_json_needs_hybrid_visual_refresh(existing.lesson_json)
            ):
                pivot_order = next_topic.order_index
                continue

            # Mark as generating so the frontend shows a non-404 status.
            if existing:
                existing.generation_status = "generating"
                db.commit()
            else:
                placeholder = Lesson(
                    topic_id=str(next_topic.id),
                    title=next_topic.title,
                    lesson_json={},
                    generation_status="generating",
                )
                db.add(placeholder)
                db.commit()
                db.refresh(placeholder)
                existing = placeholder

            try:
                chunks = get_source_chunks_for_topic(topic=next_topic, db=db)
                lesson_json = build_legacy_lesson_with_v2_visuals(
                    topic=next_topic,
                    chunks=chunks,
                )
                source_chunk_ids, source_summary = build_lesson_source_metadata(chunks)

                if existing.generation_status == "ready" and existing.lesson_json:
                    pivot_order = next_topic.order_index
                    continue

                existing.title = next_topic.title
                existing.lesson_json = lesson_json
                existing.source_chunk_ids = source_chunk_ids
                existing.source_summary = source_summary
                existing.generation_status = "ready"
                db.commit()
            except Exception:
                try:
                    existing.generation_status = "failed"
                    db.commit()
                except Exception:
                    pass
                break

            pivot_order = next_topic.order_index

    finally:
        db.close()


@router.get("/topics/{topic_id}/lesson-status")
def get_lesson_generation_status(
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """Lightweight poll endpoint so the frontend can check if a pre-generated lesson is ready."""
    get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)
    lesson = db.query(Lesson).filter(Lesson.topic_id == topic_id).first()
    if not lesson:
        return {"generation_status": "not_started"}
    return {"generation_status": lesson.generation_status}


@router.get("/topics/{topic_id}/lesson-stream")
def stream_topic_lesson(
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Stream a lesson as newline-delimited JSON so the learner sees early cards
    while later ones generate.

    Events (one JSON object per line):
      {"type":"card","card":{...}}        a raw preview card (pre-post-processing)
      {"type":"complete","lesson":{...}}  the final, fully post-processed lesson
      {"type":"busy"}                     another worker owns generation — poll instead
      {"type":"error","message":"..."}    generation failed — fall back to poll

    The client MUST fall back to the existing poll flow on `busy`/`error`/a dropped
    connection, so streaming is purely additive and never blocks lesson delivery.
    The `complete` lesson is the source of truth — the preview cards are replaced.
    """
    # Validate ownership with the request session before streaming starts.
    topic = get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)
    topic_pk = str(topic.id)

    def _event(obj: dict[str, Any]) -> str:
        return _json.dumps(obj) + "\n"

    def event_stream():
        sdb = SessionLocal()
        try:
            cached = sdb.query(Lesson).filter(Lesson.topic_id == topic_pk).first()
            if cached and cached.generation_status == "ready" and cached.lesson_json:
                # Upgrade a cached lesson on read when the example-ontology path now
                # applies but wasn't recorded at generation time (flag-gated, safe).
                if lesson_json_needs_example_ontology_refresh(cached.lesson_json, topic):
                    try:
                        from sqlalchemy.orm.attributes import flag_modified
                        enrich_legacy_lesson_with_v2_visuals(topic=topic, lesson_json=cached.lesson_json)
                        flag_modified(cached, "lesson_json")
                        sdb.commit()
                        sdb.refresh(cached)
                    except Exception:  # noqa: BLE001 — never block the cached read
                        pass
                yield _event({"type": "complete", "lesson": cached.lesson_json})
                return
            if cached and cached.generation_status in {"generating", "pending"}:
                yield _event({"type": "busy"})
                return
            if cached and cached.generation_status == "failed":
                yield _event({"type": "error", "message": "previous generation failed"})
                return

            t = sdb.query(Topic).filter(Topic.id == topic_pk).first()
            if t is None:
                yield _event({"type": "error", "message": "topic not found"})
                return
            chunks = get_source_chunks_for_topic(topic=t, db=sdb, limit=6)

            # Claim so concurrent opens poll instead of double-generating.
            create_or_update_lesson_record(
                topic=t, lesson_json={}, db=sdb, chunks=chunks, generation_status="generating",
            )

            final: dict[str, Any] | None = None
            needs_enrich = False
            try:
                for kind, payload in build_lean_lesson_streaming(topic=t, chunks=chunks):
                    if kind == "card" and isinstance(payload, dict):
                        yield _event({"type": "card", "card": payload})
                    elif kind == "complete" and isinstance(payload, dict):
                        final = payload
                        needs_enrich = True  # lean->legacy only; bridge runs below
            except Exception:
                # Streaming hiccup: fall back to the blocking builder so the lesson
                # is still produced (it already attaches v2 visuals).
                try:
                    final = build_legacy_lesson_with_v2_visuals(topic=t, chunks=chunks)
                    needs_enrich = False
                except Exception:
                    create_or_update_lesson_record(
                        topic=t, lesson_json={}, db=sdb, chunks=chunks, generation_status="failed",
                    )
                    yield _event({"type": "error", "message": "generation failed"})
                    return

            if final is None:
                create_or_update_lesson_record(
                    topic=t, lesson_json={}, db=sdb, chunks=chunks, generation_status="failed",
                )
                yield _event({"type": "error", "message": "generation failed"})
                return

            if needs_enrich:
                enrich_legacy_lesson_with_v2_visuals(topic=t, lesson_json=final)
            create_or_update_lesson_record(
                topic=t, lesson_json=final, db=sdb, chunks=chunks, generation_status="ready",
            )
            yield _event({"type": "complete", "lesson": final})
        finally:
            sdb.close()

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.post("/topics/{topic_id}/generate-lesson", response_model=LessonRead)
def generate_lesson_for_topic(
    topic_id: str,
    background_tasks: BackgroundTasks,
    payload: GenerateTopicLessonPayload | None = None,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    payload = payload or GenerateTopicLessonPayload()

    topic = get_owned_topic(
        topic_id=topic_id,
        db=db,
        current_user=current_user,
    )

    # If a lesson is already cached for this topic, return it as-is rather
    # than re-running the LLM. This endpoint is hit on EVERY topic open from
    # the frontend; without this cache check we re-pay per-call cost on
    # every navigation. Use POST /regenerate-lesson when a fresh generation
    # is explicitly wanted.
    cached = db.query(Lesson).filter(Lesson.topic_id == topic.id).first()
    if cached and cached.generation_status == "ready" and cached.lesson_json:
        # Reads are PURE: opening a lesson never rewrites the stored copy.
        # Lessons are generated with v2 visuals already attached, so there is
        # nothing to "refresh" on open. The old on-open re-enrich mutated
        # pre-existing lessons under the learner, which surfaced as "content
        # changed when I refreshed". Regenerate explicitly via /regenerate-lesson
        # if a stored lesson needs updating.
        #
        # First-time landing on a ready lesson still kicks off background
        # pre-gen for the rest of the path — pregen short-circuits topics
        # already in "ready" or "failed" status, so repeat opens do no extra
        # LLM work.
        background_tasks.add_task(pregenerate_all_study_path_topics, str(topic.id))
        return cached

    # If a background worker already owns this topic, do not start a second
    # generation from the foreground route. Returning the pending row lets the
    # frontend poll/wait instead of creating a last-writer-wins race where the
    # topic changes after the learner revisits it.
    if cached and cached.generation_status in {"generating", "pending"}:
        return cached

    # ONE-SHOT RULE: if a previous attempt already failed, do NOT auto-retry
    # on this open. Return the failed record so the frontend can show its
    # error/regenerate UI. The user must explicitly hit the regenerate button
    # (which is the /regenerate-lesson endpoint) to try again.
    if cached and cached.generation_status == "failed":
        return cached

    chunks = get_source_chunks_for_topic(topic=topic, db=db, limit=6)

    try:
        lesson_json = build_legacy_lesson_with_v2_visuals(
            topic=topic,
            chunks=chunks,
        )
    except Exception:
        # Persist the failure so the next open doesn't re-run the LLM — the
        # next visit returns the failed record via the ONE-SHOT RULE above.
        create_or_update_lesson_record(
            topic=topic,
            lesson_json={},
            chunks=chunks,
            db=db,
            generation_status="failed",
        )
        raise

    saved_lesson = create_or_update_lesson_record(
        topic=topic,
        lesson_json=lesson_json,
        chunks=chunks,
        db=db,
        generation_status="ready",
    )

    # Pre-generate all remaining topics in parallel while user studies this one.
    background_tasks.add_task(pregenerate_all_study_path_topics, str(topic.id))

    return saved_lesson


@router.post("/topics/{topic_id}/regenerate-lesson", response_model=LessonRead)
def regenerate_lesson_for_topic(
    topic_id: str,
    payload: LessonRegenerateRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    topic = get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)

    chunks = get_source_chunks_for_topic(topic=topic, db=db, limit=6)

    lesson_json = build_legacy_lesson_with_v2_visuals(
        topic=topic,
        chunks=chunks,
        feedback=payload.feedback,
    )

    return create_or_update_lesson_record(
        topic=topic,
        lesson_json=lesson_json,
        chunks=chunks,
        db=db,
    )


@router.post(
    "/topics/{topic_id}/regenerate-lesson-segment",
    response_model=LessonSegmentRegenerateResponse,
)
def regenerate_lesson_segment_for_topic(
    topic_id: str,
    payload: LessonSegmentRegenerateRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    topic = get_owned_topic(topic_id=topic_id, db=db, current_user=current_user)
    lesson = db.query(Lesson).filter(Lesson.id == payload.lesson_id).first()

    if not lesson or str(lesson.topic_id) != str(topic.id):
        raise HTTPException(status_code=404, detail="Lesson not found")

    lesson_cards = lesson.lesson_json.get("lesson_cards")

    if not isinstance(lesson_cards, list) or not lesson_cards:
        raise HTTPException(
            status_code=400,
            detail="Lesson does not have card-based content to adjust.",
        )

    if payload.current_card_index >= len(lesson_cards) - 1:
        return LessonSegmentRegenerateResponse(
            lesson=lesson,
            replacement_cards=[],
            adaptation_message="No future cards were left to adjust.",
        )

    chunks = get_source_chunks_for_topic(topic=topic, db=db, limit=6)
    result = regenerate_future_lesson_cards(
        topic=topic,
        lesson_json=lesson.lesson_json,
        current_card_index=payload.current_card_index,
        completed_card_ids=payload.completed_card_ids,
        trigger=payload.trigger,
        target_adjustment=payload.target_adjustment,
        learner_evidence=payload.learner_evidence,
        chunks=chunks,
    )

    replacement_cards = result["replacement_cards"]

    if replacement_cards:
        kept_cards = lesson_cards[: payload.current_card_index + 1]
        lesson.lesson_json = {
            **lesson.lesson_json,
            "lesson_cards": [*kept_cards, *replacement_cards],
            "segment_adaptation": {
                "trigger": payload.trigger,
                "target_adjustment": payload.target_adjustment,
                "message": result["adaptation_message"],
            },
        }

        db.commit()
        db.refresh(lesson)

    return LessonSegmentRegenerateResponse(
        lesson=lesson,
        replacement_cards=replacement_cards,
        adaptation_message=result["adaptation_message"],
    )


@router.post(
    "/study-paths/{study_path_id}/generate-lessons",
    response_model=list[LessonRead],
)
def generate_lessons_for_study_path(
    study_path_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    study_path = get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )

    topics = study_path.topics

    if not topics:
        raise HTTPException(
            status_code=400,
            detail="No topics found. Generate topics first.",
        )

    chunks = get_source_chunks_for_study_path(
        study_path=study_path,
        db=db,
        limit=8,
        allow_empty=True,
    )

    source_chunk_ids, source_summary = build_lesson_source_metadata(chunks)
    generated_lessons: list[Lesson] = []

    for topic in topics:
        try:
            lesson_json = build_legacy_lesson_with_v2_visuals(topic, chunks)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate lesson for '{topic.title}': {str(exc)}",
            ) from exc

        existing_lesson = db.query(Lesson).filter(Lesson.topic_id == topic.id).first()

        if existing_lesson:
            existing_lesson.title = topic.title
            existing_lesson.lesson_json = lesson_json
            existing_lesson.source_chunk_ids = source_chunk_ids
            existing_lesson.source_summary = source_summary
            generated_lessons.append(existing_lesson)
        else:
            lesson = Lesson(
                topic_id=topic.id,
                title=topic.title,
                lesson_json=lesson_json,
                source_chunk_ids=source_chunk_ids,
                source_summary=source_summary,
            )

            db.add(lesson)
            generated_lessons.append(lesson)

    db.commit()

    for lesson in generated_lessons:
        db.refresh(lesson)

    return generated_lessons
