import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConfusionEvent(Base):
    __tablename__ = "confusion_events"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    study_path_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    topic_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("topics.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    lesson_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("lessons.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    card_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    card_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_section: Mapped[str | None] = mapped_column(String(255), nullable=True)

    highlighted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_question: Mapped[str] = mapped_column(Text, nullable=False)
    answer_generated: Mapped[str] = mapped_column(Text, nullable=False)

    confusion_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    concept_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    clarification_mode: Mapped[str] = mapped_column(String(80), nullable=False)

    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    still_confused_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    follow_up_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    practice_check_correctness: Mapped[float | None] = mapped_column(Float, nullable=True)

    source_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    concepts_involved: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    suggested_actions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
