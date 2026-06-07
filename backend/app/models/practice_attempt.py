import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class PracticeAttempt(Base):
    __tablename__ = "practice_attempts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    study_path_id = Column(
        String,
        ForeignKey("study_paths.id", ondelete="CASCADE"),
        nullable=False,
    )

    topic_id = Column(
        String,
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
    )

    lesson_id = Column(
        String,
        ForeignKey("lessons.id", ondelete="SET NULL"),
        nullable=True,
    )

    question = Column(Text, nullable=False)
    user_answer = Column(Text, nullable=False)

    is_correct = Column(Boolean, nullable=True)

    performance_level = Column(String, nullable=True)
    mistake_type = Column(String, nullable=True)

    feedback = Column(Text, nullable=True)
    hint_used = Column(Boolean, default=False)

    follow_up_question = Column(Text, nullable=True)
    next_action = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    study_path = relationship("StudyPath")
    topic = relationship("Topic")
    lesson = relationship("Lesson")
