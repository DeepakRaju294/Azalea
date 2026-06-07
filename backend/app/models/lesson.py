import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    topic_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("topics.id"),
        nullable=False,
        unique=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    lesson_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Milestone 23: source grounding / citations
    source_chunk_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    source_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Progressive pre-generation pipeline status.
    # "pending"    — placeholder created, generation not started yet
    # "generating" — background task is running
    # "ready"      — lesson is complete and renderable
    # "failed"     — background generation failed; user can manually regenerate
    generation_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ready",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    topic = relationship("Topic", back_populates="lesson")