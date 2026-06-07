from datetime import datetime
from pydantic import BaseModel


class StudyPathCreate(BaseModel):
    title: str
    goal: str | None = None
    estimated_minutes_remaining: int | None = None


class StudyPathRead(BaseModel):
    id: str
    title: str
    goal: str | None
    progress_percent: int
    estimated_minutes_remaining: int | None
    created_at: datetime

    model_config = {"from_attributes": True}