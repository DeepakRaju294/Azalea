from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.lesson_cards import FlexibleLessonJson, LessonCard


LessonJsonPayload = dict[str, Any] | FlexibleLessonJson


class LessonCreate(BaseModel):
    title: str
    lesson_json: LessonJsonPayload

    source_chunk_ids: list[str] | None = None
    source_summary: str | None = None


class LessonRead(BaseModel):
    id: str
    topic_id: str
    title: str
    lesson_json: LessonJsonPayload

    source_chunk_ids: list[str] | None
    source_summary: str | None

    generation_status: str = "ready"

    created_at: datetime

    model_config = {"from_attributes": True}


class LessonSegmentRegenerateRequest(BaseModel):
    lesson_id: str
    current_card_index: int
    completed_card_ids: list[str] = []
    trigger: str
    target_adjustment: str
    learner_evidence: dict[str, Any] = {}


class LessonSegmentRegenerateResponse(BaseModel):
    lesson: LessonRead
    replacement_cards: list[dict[str, Any] | LessonCard]
    adaptation_message: str
