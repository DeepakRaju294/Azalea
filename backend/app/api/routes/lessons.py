import concurrent.futures
import json as _json
import os
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
from app.services.lesson_cache import fresh_on_open
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


def _build_study_path_topic_lesson(topic_id: str) -> tuple[str, dict | None, str | None]:
    """Worker for PARALLEL study-path generation. Each topic's build is LLM-bound (mostly network
    I/O, GIL released), so the topics run concurrently in a thread pool. SQLAlchemy sessions are NOT
    thread-safe, so each worker opens its OWN session and loads its own topic + chunks; the request
    thread writes the results sequentially. Returns (topic_id, lesson_json, error)."""
    wdb = SessionLocal()
    try:
        topic = wdb.query(Topic).filter(Topic.id == topic_id).first()
        if topic is None:
            return topic_id, None, "topic not found"
        chunks = get_source_chunks_for_study_path(
            study_path=topic.study_path, db=wdb, limit=8, allow_empty=True,
        )
        lesson_json = build_legacy_lesson_with_v2_visuals(topic, chunks)
        return topic_id, lesson_json, None
    except Exception as exc:  # noqa: BLE001 — surfaced to the request thread, which decides
        return topic_id, None, str(exc)
    finally:
        wdb.close()


def _defer_worked_example() -> bool:
    """Defer the worked-example solve on the single-topic STREAM path (default OFF). When ON, the
    stream completes the lesson WITHOUT the worked example (so it renders fast), then generates and
    patches it in via a follow-up `worked_example` event. Bulk generation always solves inline."""
    return os.getenv("AZALEA_DEFER_WORKED_EXAMPLE", "0") == "1"


def _finalize_lesson_cards(lesson_json: dict, v2_topic: dict) -> None:
    """Deterministic post-solve guarantees: the worked-example setup card, blueprint card order,
    visual gating, and the completeness audit. Safe to run more than once — used by both the inline
    enrich path and the deferred worked-example path."""
    from app.services.examples.handoff import ensure_worked_example_setup, validate_and_order_cards
    from app.services.examples.worked_example_audit import audit_worked_examples
    from app.services.legacy_v2_visual_bridge import gate_legacy_visuals

    ensure_worked_example_setup(lesson_json, v2_topic)
    validate_and_order_cards(lesson_json, v2_topic)
    gate_legacy_visuals(lesson_json)
    audit_worked_examples(lesson_json, v2_topic, regenerate=None, max_regenerations=2)
    _audit_required_cards(lesson_json, v2_topic)


def _audit_required_cards(lesson_json: dict, v2_topic: dict) -> None:
    """Re-stamp `metadata.quality.missing_required_cards` on the FINAL lesson (after the solver), so
    the signal is accurate rather than the misleading lean-time value (which always flags
    worked_example because lean omits it). A genuinely-missing required card — e.g. the solver failed
    to produce a worked_example — is then visible and logged loudly instead of silently shipped."""
    try:
        from app.services.card_backfill import backfill_missing_required_cards

        # #2: regenerate missing/empty required cards specifically (worked_example via the solver,
        # others via a focused single-card call) instead of just flagging them. Returns what is STILL
        # missing after backfill — that's the honest signal to stamp.
        still_missing = backfill_missing_required_cards(lesson_json, v2_topic)
        meta = lesson_json.setdefault("metadata", {})
        if isinstance(meta, dict):
            quality = meta.setdefault("quality", {})
            if isinstance(quality, dict):
                quality["missing_required_cards"] = still_missing
        if still_missing:
            import logging
            logging.getLogger(__name__).warning(
                "lesson for topic %s STILL missing required cards after backfill: %s",
                v2_topic.get("id"), still_missing,
            )

        # B (#5 across paths): a CODING worked example must TRACE concrete values, not re-define the
        # code. The gen_foundation gate handles its own path; this also catches the legacy-solver path.
        if str(v2_topic.get("topic_type") or "").lower() == "coding_implementation":
            from app.services.gen_foundation.trace_quality import walkthrough_mode_violations
            we_cards = [c for c in (lesson_json.get("lesson_cards") or [])
                        if isinstance(c, dict) and str(c.get("blueprint_key") or "").lower() == "worked_example"]
            we_violations = walkthrough_mode_violations(we_cards)
            if we_violations:
                from app.services.card_failure_log import log_card_failure
                log_card_failure(topic=v2_topic, card_key="worked_example", stage="trace_quality",
                                 reason="walkthrough_instead_of_trace", action="flagged",
                                 detail="; ".join(we_violations[:3]))
                meta = lesson_json.setdefault("metadata", {})
                if isinstance(meta, dict):
                    q = meta.setdefault("quality", {})
                    if isinstance(q, dict):
                        q["worked_example_trace_violations"] = we_violations
    except Exception:  # noqa: BLE001 — auditing must never break a lesson
        pass


def apply_deferred_worked_example(topic: Topic, lesson_json: dict) -> bool:
    """Generate the worked example the stream deferred, patch it into an already-completed lesson,
    and re-run the deterministic finalize. Failure-safe; returns whether the solver applied."""
    if not isinstance(lesson_json, dict):
        return False
    try:
        from app.services.examples.solver import apply_llm_solved_worked_example

        v2_topic = {
            "id": str(topic.id),
            "title": topic.title or "",
            "topic_type": str(getattr(topic, "course_type", None) or getattr(topic, "topic_type", "") or ""),
        }
        applied = apply_llm_solved_worked_example(lesson_json, v2_topic)
        _finalize_lesson_cards(lesson_json, v2_topic)
        return bool(applied)
    except Exception:  # noqa: BLE001 — never break a delivered lesson
        import logging
        logging.getLogger(__name__).exception("deferred worked-example apply failed for topic %s", topic.id)
        return False


def enrich_legacy_lesson_with_v2_visuals(
    topic: Topic,
    lesson_json: dict,
    defer_worked_example: bool = False,
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
        _v2_topic = {
            "id": str(topic.id),
            "title": topic.title or "",
            "topic_type": str(getattr(topic, "course_type", None) or getattr(topic, "topic_type", "") or ""),
        }
        # Worked-example authoring: a single focused LLM solve for EVERY topic. For a coding
        # topic the solve explains how the code EXECUTES on a concrete input — conceptually,
        # never by line number — and the code is shown in an IDE panel (not a frame-by-frame
        # trace visual). The line-by-line execution-trace path is retired (it gated example
        # completeness on a successful trace and produced "line N executes" cards); the
        # example-type/fixture/ontology apparatus stays bypassed. Both remain in the tree.
        from app.services.examples.code_repair import apply_clean_code_to_lesson
        from app.services.examples.code_walkthrough import apply_line_explained_walkthrough
        from app.services.examples.solver import apply_llm_solved_worked_example

        # If a coding topic's code is broken (the incremental walkthrough transforms can ship
        # code with undefined variables), replace it with one clean, validated LLM regeneration
        # BEFORE the solver runs, so the worked-example IDE panel shows correct code.
        apply_clean_code_to_lesson(lesson_json, _v2_topic)
        # Rebuild the code_walkthrough as a per-LINE, one-step-at-a-time walkthrough off the now-
        # authoritative code (the general prompt summarizes code and the merge pass collapses it,
        # so the learner never gets a line-by-line walk). Structure is deterministic; the model
        # only supplies one explanation per line.
        apply_line_explained_walkthrough(lesson_json, _v2_topic)
        # The worked-example solve is the heaviest enrich step (2-3 LLM calls). On the single-topic
        # STREAM path it can be DEFERRED: the lesson completes/renders without it, then it is solved
        # and patched in afterward (apply_deferred_worked_example). Bulk generation solves inline.
        if not defer_worked_example:
            apply_llm_solved_worked_example(lesson_json, _v2_topic)

        # Deterministic guarantees, ANY path: a concept worked example always opens with a setup
        # card, the card set matches the topic type's blueprint order, visuals are gated, and the
        # completeness audit runs. (When deferred, this runs again after the worked example lands.)
        _finalize_lesson_cards(lesson_json, _v2_topic)
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
    """RETIRED. Worked examples are no longer authored by the example-ontology/fixture path
    (that apparatus is dormant — see enrich_legacy_lesson_with_v2_visuals); cache upgrades
    are driven solely by the bridge VERSION via lesson_json_needs_hybrid_visual_refresh.

    Kept (returns False) so the two read-path call sites stay valid without churn. It must
    NOT use declare_example/pick_fixture: those would report "needs ontology apply" forever
    now that apply_fixture_to_lesson never runs, re-enriching (and re-solving) on every read."""
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

    # Caching is ON: serve the saved lesson. This is the reliable fallback when a long streaming
    # generation drops before `complete` — it returns the lesson the stream just saved (fresh, in
    # fresh-on-open mode) instead of regenerating it again.
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

    if lesson_json_needs_hybrid_visual_refresh(lesson.lesson_json):
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
            # fresh-on-open: the streaming open regenerates from scratch so each open shows fresh
            # content; other reads (the fallback) still serve the saved copy. When fresh-on-open is
            # off, serve the cached lesson here too.
            if not fresh_on_open():
                if cached and cached.generation_status == "ready" and cached.lesson_json:
                    # Upgrade a cached lesson on read when the bridge VERSION advanced (so it
                    # picks up the latest solver/code/visual fixes). The example-typing/ontology
                    # refresh is retired — version is the only upgrade trigger now.
                    if lesson_json_needs_hybrid_visual_refresh(cached.lesson_json):
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

            defer_we = _defer_worked_example() and needs_enrich
            if needs_enrich:
                enrich_legacy_lesson_with_v2_visuals(topic=t, lesson_json=final, defer_worked_example=defer_we)
            create_or_update_lesson_record(
                topic=t, lesson_json=final, db=sdb, chunks=chunks, generation_status="ready",
            )
            # Complete WITHOUT the worked example (renders immediately) when deferring; otherwise the
            # full lesson is already assembled.
            yield _event({"type": "complete", "lesson": final})

            if defer_we:
                # Solve the deferred worked example, patch it into the (already-delivered) lesson,
                # persist it so it's never lost, then emit it so the client can patch it in live.
                if apply_deferred_worked_example(t, final):
                    create_or_update_lesson_record(
                        topic=t, lesson_json=final, db=sdb, chunks=chunks, generation_status="ready",
                    )
                yield _event({"type": "worked_example", "lesson": final})
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
    # Caching is ON: serve the saved lesson rather than re-running the LLM on every open (the
    # streaming open is what regenerates fresh in fresh-on-open mode; this is the cheap fallback).
    if cached and cached.generation_status == "ready" and cached.lesson_json:
        background_tasks.add_task(pregenerate_all_study_path_topics, str(topic.id))
        return cached

    # If a background worker already owns this topic, do not start a second generation from the
    # foreground route — let the frontend poll/wait instead of a last-writer-wins race.
    if cached and cached.generation_status in {"generating", "pending"}:
        return cached

    # ONE-SHOT RULE: a previous failed attempt is returned as-is so the frontend can show its
    # error/regenerate UI; the user must explicitly regenerate to retry.
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

    # Build every topic's lesson CONCURRENTLY — each build is LLM-bound (network I/O), so a thread
    # pool turns an N-topic serial wait into ~N/workers. Each worker uses its own DB session; this
    # request thread writes the results sequentially afterward (one session, no cross-thread sharing).
    topic_order = [str(t.id) for t in topics]
    max_workers = max(1, min(len(topic_order), int(os.getenv("AZALEA_LESSON_PARALLELISM", "4"))))
    built: dict[str, dict] = {}
    errors: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for tid, lesson_json, err in executor.map(_build_study_path_topic_lesson, topic_order):
            if err is not None:
                errors[tid] = err
            elif lesson_json is not None:
                built[tid] = lesson_json
    if errors:
        first_tid, first_err = next(iter(errors.items()))
        title = next((t.title for t in topics if str(t.id) == first_tid), first_tid)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate lesson for '{title}': {first_err}",
        )

    for topic in topics:
        lesson_json = built.get(str(topic.id))
        if lesson_json is None:
            continue
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
