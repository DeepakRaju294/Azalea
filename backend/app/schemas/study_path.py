from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# The languages we ship verified canonical code for. One per study path, chosen at creation.
CodeLanguage = Literal["python", "cpp", "java"]


class StudyPathCreate(BaseModel):
    title: str
    goal: str | None = None
    estimated_minutes_remaining: int | None = None
    language: CodeLanguage = "python"


class StudyPathRead(BaseModel):
    id: str
    title: str
    goal: str | None
    progress_percent: int
    estimated_minutes_remaining: int | None
    language: str
    created_at: datetime

    model_config = {"from_attributes": True}