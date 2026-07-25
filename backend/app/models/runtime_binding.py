"""Milestone C persistence models (GROUNDED_RUNTIME_BINDING_SPEC.md §2.5, §5.9, §5.10, §13.2).

Four insert-only / append-only tables backing the in-memory ledgers built in
`runtime_binding/lifecycle.py` and `runtime_binding/evidence.py`. Created via Alembic (the repo's new
migration mechanism); `Base.metadata.create_all()` is NOT relied on to alter deployed schema.

Discipline:
- `sibling_exercise_claims` — transactional ownership; at most one `active` per (path_plan_version,
  ownership tuple), enforced by a partial unique index.
- `prepared_runtime_bindings` — preparation lifecycle; CAS on `status_version`; at most one non-superseded
  `preparing|ready` per `preparation_identity_digest`, enforced by a partial unique index.
- `evidence_packages` — immutable after `verification_completed_at`; keyed by `evidence_id`/`evidence_digest`.
- `delivery_evidence` — append-only post-sanitization narration/card fidelity bound to an evidence package.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base

RUNTIME_BINDING_SCHEMA_VERSION = 1


def _uuid() -> str:
    return str(uuid.uuid4())


class SiblingExerciseClaim(Base):
    """§2.5 — generic path exercise ownership. Runtime binding is the first consumer."""

    __tablename__ = "sibling_exercise_claims"

    claim_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    claim_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    path_plan_version: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # ownership tuple, stored decomposed so the partial unique index can enforce single-active-owner
    concept_contract_id: Mapped[str] = mapped_column(String, nullable=False)
    variant: Mapped[str] = mapped_column(String, nullable=False)
    grammar_id: Mapped[str] = mapped_column(String, nullable=False)
    lesson_intent_kind: Mapped[str] = mapped_column(String, nullable=False)
    owner_topic_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)          # active | lost | superseded
    superseded_by_claim_id: Mapped[str | None] = mapped_column(String, nullable=True)
    lost_to_topic_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        # at most one ACTIVE claim per (path_plan_version, ownership tuple)
        Index(
            "uq_active_exercise_claim",
            "path_plan_version", "concept_contract_id", "variant", "grammar_id", "lesson_intent_kind",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


class PreparedRuntimeBinding(Base):
    """§13.2 — preparation lifecycle. CAS on status_version; one non-superseded preparing|ready per identity."""

    __tablename__ = "prepared_runtime_bindings"

    preparation_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    topic_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    preparation_identity_digest: Mapped[str] = mapped_column(String, nullable=False, index=True)
    path_plan_version: Mapped[str] = mapped_column(String, nullable=False)
    sibling_claim_id: Mapped[str] = mapped_column(String, nullable=False)
    sibling_claim_version: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_version: Mapped[int] = mapped_column(Integer, nullable=False)
    grammar_version: Mapped[int] = mapped_column(Integer, nullable=False)
    pedagogical_policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_registry_version: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_entry_version: Mapped[int] = mapped_column(Integer, nullable=False)
    binding_digest: Mapped[str] = mapped_column(String, nullable=False)
    execution_environment_digest: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)          # preparing | ready | failed | stale
    status_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    safety_block_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    superseded_by_preparation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    active_evidence_id: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_reason: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "uq_live_preparation_identity",
            "preparation_identity_digest",
            unique=True,
            postgresql_where=text("status IN ('preparing', 'ready')"),
        ),
    )


class EvidencePackageRecord(Base):
    """§5.9 — immutable evidence package. Insert-only once `verification_completed_at` is set."""

    __tablename__ = "evidence_packages"

    evidence_id: Mapped[str] = mapped_column(String, primary_key=True)
    evidence_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evidence_digest: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    binding_digest: Mapped[str] = mapped_column(String, nullable=False)
    instance_digest: Mapped[str] = mapped_column(String, nullable=False)
    resolution_registry_version: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_entry_version: Mapped[int] = mapped_column(Integer, nullable=False)
    pedagogical_policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    contract_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)             # the frozen package (view source)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    verification_completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DeliveryEvidenceRecord(Base):
    """§5.10 — append-only post-sanitization delivery/narration fidelity bound to an evidence package."""

    __tablename__ = "delivery_evidence"

    delivery_evidence_id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence_packages.evidence_id"), nullable=False, index=True)
    evidence_digest: Mapped[str] = mapped_column(String, nullable=False)
    lesson_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    canonical_delivery_payload_digest: Mapped[str] = mapped_column(String, nullable=False)
    canonical_delivery_serialization_version: Mapped[int] = mapped_column(Integer, nullable=False)
    backend_sanitizer_version: Mapped[str] = mapped_column(String, nullable=False)
    structured_renderer_contract_version: Mapped[str] = mapped_column(String, nullable=False)
    narration_validator_version: Mapped[str] = mapped_column(String, nullable=False)
    narration_fidelity: Mapped[str] = mapped_column(String(16), nullable=False)   # passed | failed
    post_sanitization_validation_digest: Mapped[str] = mapped_column(String, nullable=False)
    card_provenance: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("evidence_id", "canonical_delivery_payload_digest", name="uq_delivery_payload"),
    )
