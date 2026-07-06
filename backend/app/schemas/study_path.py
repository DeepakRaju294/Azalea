from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

# The languages we ship verified canonical code for. One per study path, chosen at creation.
CodeLanguage = Literal["python", "cpp", "java"]

# Structural depth level (ONBOARDING_AND_PREFERENCE_CAPTURE_SPEC §4.1). Defined here (the base schema module) so
# the preferences schema can import it without a cycle.
DepthLevel = Literal["intuition", "working", "deep"]

# Coarse domain labels a learner may pick as a per-path override (the wizard's Content-Type step, §2).
OverrideDomain = Literal["coding", "math", "science", "concept"]


class StudyPathCreate(BaseModel):
    title: str
    goal: str | None = None
    estimated_minutes_remaining: int | None = None
    language: CodeLanguage = "python"


class StudyPathLanguageUpdate(BaseModel):
    language: CodeLanguage


class StudyPathPreferenceUpdate(BaseModel):
    """A learner's per-path override (the top precedence tier, §3). All optional — only provided fields are
    applied; an explicit null clears that override. `domain` sets the effective routing domain
    (status → user_selected); `depth_level`/`language` are stored in `StudyPath.selected_preferences`."""

    domain: OverrideDomain | None = None
    depth_level: DepthLevel | None = None
    language: CodeLanguage | None = None


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