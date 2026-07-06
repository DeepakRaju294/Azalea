"""Phase-1 preference persistence (ONBOARDING_AND_PREFERENCE_CAPTURE_SPEC §3 + D1).

Two records, per the D1 decision:
- `UserPreference` — MUTABLE user-level defaults (depth / language / knowledge). Changing these affects only
  FUTURE generations.
- `StudyPathGeneration` — an IMMUTABLE per-generation snapshot. Every generation writes a new row (incrementing
  `generation_number`); `StudyPath.active_generation_id` points at the active revision. This is what answers
  "why did this path generate Java / working depth?" and "what changed on regenerate?" — a fully-mutable record
  would lose that history. Snapshots are never mutated after write.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base import Base

# Bump when the persisted preference shape changes (both records carry it, §3 "Versioning").
PREFERENCE_SCHEMA_VERSION = 1


class UserPreference(Base):
    """Mutable user-level defaults. One row per user. `precedence: path override > user default > inferred >
    platform default` — this record supplies the *user default* tier (§3)."""

    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, unique=True, nullable=False)

    default_depth_level = Column(String(20), nullable=True)       # intuition | working | deep
    default_language = Column(String(32), nullable=True)          # python | java | cplusplus
    default_knowledge_level = Column(Integer, nullable=True)      # reserved — Phase-2 consumer (§4)

    schema_version = Column(Integer, nullable=False, default=PREFERENCE_SCHEMA_VERSION)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StudyPathGeneration(Base):
    """Immutable per-generation snapshot (D1). Written once per generation; never updated. A regeneration writes a
    NEW row with `generation_number + 1`; `StudyPath.active_generation_id` selects the active revision."""

    __tablename__ = "study_path_generations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    study_path_id = Column(
        String, ForeignKey("study_paths.id", ondelete="CASCADE"), index=True, nullable=False
    )
    generation_number = Column(Integer, nullable=False, default=1)

    # Effective domain routing for this generation (from Phase-0 classification, possibly user-overridden later).
    domain = Column(String(40), nullable=True)
    classification_status = Column(String(20), nullable=True)

    # The three preference views (§3): what the user/path explicitly selected, what actually took effect after
    # precedence + capability resolution, and the per-field provenance (inferred · user_confirmed · user_selected ·
    # saved_default · system_default).
    selected_preferences_json = Column(JSONB, nullable=True)
    effective_preferences_json = Column(JSONB, nullable=True)
    preference_provenance_json = Column(JSONB, nullable=True)

    # Version stamps of every contract that shaped this generation (gate/rewrite/classifier/preference schema) so
    # a snapshot stays explainable even after those contracts evolve.
    contract_versions_json = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
