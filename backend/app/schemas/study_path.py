from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

# The languages we ship verified canonical code for. One per study path, chosen at creation.
CodeLanguage = Literal["python", "cpp", "java"]


class StudyPathCreate(BaseModel):
    title: str
    goal: str | None = None
    estimated_minutes_remaining: int | None = None
    language: CodeLanguage = "python"


class StudyPathLanguageUpdate(BaseModel):
    language: CodeLanguage


class StudyPathRead(BaseModel):
    id: str
    title: str
    goal: str | None
    progress_percent: int
    estimated_minutes_remaining: int | None
    language: str
    created_at: datetime

    # Phase-0/1: the inferred domain + classifier status, and the effective preferences the active generation
    # ran under (from the immutable snapshot). `effective_preferences` is None until the first generation.
    domain: str | None = None
    classification_status: str | None = None
    effective_preferences: dict[str, Any] | None = None
    preference_provenance: dict[str, Any] | None = None

    model_config = {"from_attributes": True}