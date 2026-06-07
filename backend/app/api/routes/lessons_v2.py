"""V2 lesson API route.

Endpoint: POST /lessons-v2/topics/{topic_id}/generate

Wires the v2 pipeline:
  1. Load the topic + its source chunks
  2. Classify visual_domain (topic_classifier_v2)
  3. Call the LLM with prompt_v2 + LESSON_V2_SCHEMA
  4. Compile via lean_lesson_generator_v2.compile_lesson_v2
  5. Return the LessonV2 contract directly (no legacy lesson_json conversion)

Coexists with the legacy /lessons routes. Nothing here modifies legacy.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.ownership import get_owned_topic
from app.models.content_chunk import ContentChunk
from app.models.lesson import Lesson
from app.models.topic import Topic
from app.prompts.lean_lesson_prompt_v2 import (
    SYSTEM_PROMPT_V2,
    build_lesson_v2_prompt,
)
from app.services.lean_lesson_generator_v2 import compile_lesson_v2
from app.services.llm_schemas_v2 import LESSON_V2_SCHEMA
from app.services.topic_classifier_v2 import classify_topic_v2
from app.services.v2_rate_limit import (
    enforce_practice_submit_rate_limit,
    enforce_visual_qa_rate_limit,
)
from app.services.v2_telemetry import read_summary as read_telemetry_summary
from app.services.visual_context_formatter import format_visual_context

router = APIRouter()


def _get_topic_chunks(topic: Topic, db: Session, limit: int = 8) -> list[ContentChunk]:
    """Pull up to `limit` content chunks for a topic. Falls back to study
    path's chunks if the topic itself has none."""
    study_path = topic.study_path
    if study_path is None:
        return []

    # Topic-specific chunks (linked through topic_chunk_links or similar).
    # The simplest path: pull from the study path's material chunks.
    material_ids = [
        material.id
        for material in (study_path.materials or [])
    ]
    if not material_ids:
        return []

    chunks = (
        db.query(ContentChunk)
        .filter(ContentChunk.material_id.in_(material_ids))
        .order_by(ContentChunk.material_id, ContentChunk.chunk_index)
        .limit(limit)
        .all()
    )
    return chunks


def _chunks_to_text(chunks: list[ContentChunk]) -> str:
    if not chunks:
        return ""
    parts = []
    for index, chunk in enumerate(chunks, start=1):
        parts.append(
            f"--- SOURCE CHUNK {index} ---\n"
            f"Material id: {chunk.material_id}\n"
            f"Chunk index: {chunk.chunk_index}\n\n"
            f"{chunk.text}"
        )
    return "\n\n".join(parts)


@router.post("/lessons-v2/topics/{topic_id}/generate")
def generate_lesson_v2(
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate a v2 lesson for a topic. Returns the LessonV2 contract."""
    topic = get_owned_topic(
        topic_id=topic_id,
        db=db,
        current_user=current_user,
    )

    classification = classify_topic_v2(
        topic_title=topic.title or "",
        topic_summary=getattr(topic, "description", "") or "",
        topic_type=str(getattr(topic, "topic_type", None) or "concept_intuition"),
        knowledge_level=None,
    )

    chunks = _get_topic_chunks(topic, db, limit=8)
    chunks_text = _chunks_to_text(chunks)

    user_prompt = build_lesson_v2_prompt(
        topic_title=topic.title or "",
        topic_summary=getattr(topic, "description", "") or "",
        topic_type=classification["topic_type"],
        visual_domain=classification["visual_domain"],
        visual_mode_hint=classification["visual_mode_hint"],
        knowledge_level=classification["knowledge_level"],
        chunks_text=chunks_text,
    )

    # Call the LLM. We import here to avoid circular imports at module load.
    try:
        from app.services.llm_client import client
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"LLM client unavailable: {exc}",
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
                    # strict=False: WorkedExamplePlan.base_state and
                    # WorkedExampleStep.state_after are intentionally
                    # polymorphic (shape varies by base_type) and use
                    # additionalProperties=true. OpenAI strict mode
                    # rejects that. Our backend validators
                    # (validate_lesson_v2) catch real shape issues.
                    "strict": False,
                    "schema": LESSON_V2_SCHEMA,
                },
            },
        )
        raw_text = response.output_text
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"LLM call failed: {exc}",
        )

    import json
    try:
        lesson_v2_raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"LLM returned invalid JSON: {exc}",
        )

    # Source metadata
    source_chunk_ids = [str(c.id) for c in chunks]
    source_summary_parts = []
    for chunk in chunks:
        material_title = (
            chunk.material.title
            if getattr(chunk, "material", None) is not None
            else "Uploaded material"
        )
        source_summary_parts.append(f"- {material_title} (chunk {chunk.chunk_index})")
    source_summary = "\n".join(source_summary_parts)

    compiled = compile_lesson_v2(
        lesson_v2_raw=lesson_v2_raw,
        topic_id=str(topic.id),
        topic_hint=topic.title or "",
        topic_type=classification["topic_type"],
        visual_domain=classification["visual_domain"],
        source_chunks_excerpt=chunks_text[:2000],
        source_chunk_ids=source_chunk_ids,
        source_summary=source_summary,
    )

    existing_lesson = db.query(Lesson).filter(Lesson.topic_id == topic.id).first()
    if existing_lesson:
        existing_lesson.title = topic.title or ""
        existing_lesson.lesson_json = compiled
        existing_lesson.source_chunk_ids = source_chunk_ids
        existing_lesson.source_summary = source_summary
        existing_lesson.generation_status = "ready"
        db.commit()
        db.refresh(existing_lesson)
    else:
        db.add(
            Lesson(
                topic_id=str(topic.id),
                title=topic.title or "",
                lesson_json=compiled,
                source_chunk_ids=source_chunk_ids,
                source_summary=source_summary,
                generation_status="ready",
            )
        )
        db.commit()

    return {
        "topic_id": str(topic.id),
        "classification": classification,
        "lesson": compiled,
    }


@router.get("/lessons-v2/topics/{topic_id}/classify")
def classify_topic_v2_endpoint(
    topic_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Diagnostic: return the v2 classification for a topic without
    generating the lesson. Useful for debugging visual_domain inference."""
    topic = get_owned_topic(
        topic_id=topic_id,
        db=db,
        current_user=current_user,
    )
    return classify_topic_v2(
        topic_title=topic.title or "",
        topic_summary=getattr(topic, "description", "") or "",
        topic_type=str(getattr(topic, "topic_type", None) or "concept_intuition"),
        knowledge_level=None,
    )


@router.post("/lessons-v2/visual-qa")
def visual_qa_v2(
    request: Request,
    body: dict[str, Any],
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Click-to-ask backend.

    Body: { question: str, visual_context: VisualContextPayload }
    Returns: { answer: str, visual_context_summary: str }

    Rate-limited at 30 requests / 60 seconds per identity (user or IP).
    """
    enforce_visual_qa_rate_limit(request, current_user)
    question = str(body.get("question") or "").strip()
    visual_context = body.get("visual_context") or {}
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    if not visual_context:
        raise HTTPException(status_code=400, detail="visual_context is required")

    context_summary = format_visual_context(visual_context)

    try:
        from app.services.llm_client import client
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"LLM client unavailable: {exc}",
        )

    system_prompt = (
        "You are a tutor explaining a specific element of an interactive "
        "lesson visual. Be concrete. Reference the element's current state. "
        "Keep your answer to 2-4 sentences unless the learner asks for more."
    )
    user_prompt = f"{context_summary}\n\nLearner's question: {question}"

    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        answer = response.output_text
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"LLM call failed: {exc}",
        )

    return {
        "answer": answer,
        "visual_context_summary": context_summary,
    }


@router.post("/lessons-v2/practice/submit")
def submit_practice_attempt_v2(
    request: Request,
    body: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Persist a v2 practice attempt.

    Body:
      {
        topic_id: str,
        lesson_id: str (optional),
        practice_question_id: str,
        question: str,
        user_answer: str,
        is_correct: bool,
        self_rating: "got_it" | "needs_review" (optional)
      }

    Reuses the existing `practice_attempts` table. Returns the row id +
    minimal correctness summary so the frontend can confirm persistence.
    """
    enforce_practice_submit_rate_limit(request, current_user)
    from app.models.practice_attempt import PracticeAttempt

    topic_id = str(body.get("topic_id") or "").strip()
    if not topic_id:
        raise HTTPException(status_code=400, detail="topic_id is required")
    question = str(body.get("question") or "").strip()
    user_answer = str(body.get("user_answer") or "").strip()
    if not question or not user_answer:
        raise HTTPException(
            status_code=400, detail="question and user_answer are required",
        )

    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if topic is None:
        raise HTTPException(status_code=404, detail="topic not found")
    study_path_id = str(topic.study_path_id or "")

    self_rating = str(body.get("self_rating") or "").strip().lower()
    performance_level = ""
    if self_rating == "got_it":
        performance_level = "strong"
    elif self_rating == "needs_review":
        performance_level = "weak"

    attempt = PracticeAttempt(
        study_path_id=study_path_id,
        topic_id=topic_id,
        lesson_id=str(body.get("lesson_id") or "") or None,
        question=question,
        user_answer=user_answer,
        is_correct=bool(body.get("is_correct")),
        performance_level=performance_level or None,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return {
        "attempt_id": str(attempt.id),
        "is_correct": bool(attempt.is_correct),
        "performance_level": attempt.performance_level,
    }


@router.get("/lessons-v2/telemetry/summary")
def telemetry_summary(
    limit_rows: int = 1000,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Aggregated telemetry from logs/v2_telemetry.csv.

    Auth-gated; no per-user scoping (all rows aggregated). Intended for
    the operator dashboard during Phase 7 cutover monitoring.

    Returns:
        {
          rows_read: N,
          by_pipeline: {
            "v2": { count, success, failure, avg_duration_seconds,
                    error_rate, validator_errors_per_lesson,
                    validator_warnings_per_lesson, base_type_counts },
            "legacy": { ... }
          },
          log_path: str
        }
    """
    _ = current_user
    return read_telemetry_summary(limit_rows=limit_rows)
