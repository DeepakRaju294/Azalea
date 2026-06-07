import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
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
