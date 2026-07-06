"""Phase-1 user-preference API schemas (ONBOARDING_AND_PREFERENCE_CAPTURE_SPEC §3)."""
from typing import Literal

from pydantic import BaseModel

from app.schemas.study_path import CodeLanguage

DepthLevel = Literal["intuition", "working", "deep"]


class UserPreferenceRead(BaseModel):
    """The user's mutable defaults. All fields optional — an unset default means 'fall through to the next
    precedence tier' (inferred / platform), not a stored value."""

    default_depth_level: str | None = None
    default_language: str | None = None
    default_knowledge_level: int | None = None
    schema_version: int

    model_config = {"from_attributes": True}


class UserPreferenceUpdate(BaseModel):
    """Partial upsert — only provided fields are written (unset fields are left unchanged; an explicit null
    clears that default). `default_knowledge_level` is stored but has no live consumer until Phase 2."""

    default_depth_level: DepthLevel | None = None
    default_language: CodeLanguage | None = None
    default_knowledge_level: int | None = None
