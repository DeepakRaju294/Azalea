import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.associations import class_study_paths


class AzaleaClass(Base):
    __tablename__ = "classes"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    user_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    deadline: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    daily_goal_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=30,
    )

    weekly_goal_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=180,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    study_paths = relationship(
        "StudyPath",
        secondary=class_study_paths,
        back_populates="classes",
    )

    materials = relationship(
        "LearningMaterial",
        back_populates="azalea_class",
        cascade="all, delete-orphan",
    )
