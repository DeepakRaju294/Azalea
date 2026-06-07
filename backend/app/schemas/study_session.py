from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StudySessionCreate(BaseModel):
    class_id: Optional[str] = None
    study_path_id: Optional[str] = None
    topic_id: Optional[str] = None
    minutes_spent: int = Field(..., ge=0)
    activity_type: str


class StudySessionRead(BaseModel):
    id: int
    class_id: Optional[str] = None
    study_path_id: Optional[str] = None
    topic_id: Optional[str] = None
    minutes_spent: int
    activity_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class StudySessionSummary(BaseModel):
    total_minutes: int
    lesson_minutes: int
    practice_minutes: int
    qa_minutes: int
    review_minutes: int
    regeneration_minutes: int
    session_count: int