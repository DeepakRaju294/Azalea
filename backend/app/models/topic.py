import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    study_path_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("study_paths.id"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Milestone 22: better topic generation metadata
    unit_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    learner_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    prerequisite_topics: Mapped[str | None] = mapped_column(Text, nullable=True)
    assumed_prerequisites: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    source_refs: Mapped[str | None] = mapped_column(Text, nullable=True)
    in_scope: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    out_of_scope: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    practice_target: Mapped[str | None] = mapped_column(Text, nullable=True)
    practice_format: Mapped[str | None] = mapped_column(String(80), nullable=True)
    difficulty_focus: Mapped[str | None] = mapped_column(Text, nullable=True)
    boundary_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional topic-planning metadata.
    modifiers: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    source_coverage_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    card_blueprint_hint: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    course_type_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Course-type-aware generation metadata.
    course_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    secondary_course_types: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    knowledge_level: Mapped[int | None] = mapped_column(Integer, nullable=True)

    @property
    def topic_type(self) -> str | None:
        return self.course_type

    @topic_type.setter
    def topic_type(self, value: str | None) -> None:
        self.course_type = value

    @property
    def topic_type_reason(self) -> str | None:
        return self.course_type_reason

    @topic_type_reason.setter
    def topic_type_reason(self, value: str | None) -> None:
        self.course_type_reason = value

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="not_started",
    )

    review_due_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    review_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    study_path = relationship("StudyPath", back_populates="topics")

    lesson = relationship(
        "Lesson",
        back_populates="topic",
        uselist=False,
        cascade="all, delete-orphan",
    )
