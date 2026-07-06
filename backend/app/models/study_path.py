import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.associations import class_study_paths


class StudyPath(Base):
    __tablename__ = "study_paths"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Supabase Auth ownership
    user_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Programming language for all coding content on this path (code walkthrough + worked example).
    # Chosen at creation; threaded through generation. One of: python | cpp | java.
    language: Mapped[str] = mapped_column(
        String(32), nullable=False, default="python", server_default="python",
    )

    # Phase-0 domain routing (DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §3). `domain` is the fine classifier label
    # (coding · math · physics · … | mixed | unknown); `domain_provenance` carries gate_family/confidence/scores
    # + classifier_version for audit; `classification_status ∈ pending | classified | ambiguous | failed`
    # (`pending` = pre-classification default). All persisted for analytics; the gate reads `domain` at generation.
    domain: Mapped[str | None] = mapped_column(String(40), nullable=True)
    domain_provenance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    classification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending",
    )

    # Phase-1 (D1): the active immutable StudyPathGeneration revision this path currently reflects. NULL until the
    # first generation writes a snapshot; a regeneration repoints this at the newer revision.
    active_generation_id: Mapped[str | None] = mapped_column(String, nullable=True)

    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_minutes_remaining: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    classes = relationship(
        "AzaleaClass",
        secondary=class_study_paths,
        back_populates="study_paths",
    )

    topics = relationship(
        "Topic",
        back_populates="study_path",
        cascade="all, delete-orphan",
        order_by="Topic.order_index",
    )

    materials = relationship(
        "LearningMaterial",
        back_populates="study_path",
        cascade="all, delete-orphan",
        order_by="LearningMaterial.created_at.desc()",
    )
