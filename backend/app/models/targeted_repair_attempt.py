from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class TargetedRepairAttempt(Base):
    __tablename__ = "targeted_repair_attempts"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(String, index=True, nullable=False)
    topic_id = Column(String, ForeignKey("topics.id", ondelete="CASCADE"), index=True, nullable=False)

    concept_name = Column(String, index=True, nullable=False)
    mistake_type = Column(String, nullable=True)

    question = Column(Text, nullable=True)
    user_answer = Column(Text, nullable=True)

    repair_explanation = Column(Text, nullable=False)
    why_this_matters = Column(Text, nullable=False)
    follow_up_question = Column(Text, nullable=False)
    next_action = Column(String, nullable=False)

    repair_level = Column(String, default="targeted_repair", nullable=False)
    prior_repair_count = Column(Integer, default=0, nullable=False)

    follow_up_answer = Column(Text, nullable=True)
    follow_up_correctness = Column(Float, nullable=True)
    follow_up_reasoning_quality = Column(Float, nullable=True)
    follow_up_feedback = Column(Text, nullable=True)
    follow_up_completed = Column(Boolean, default=False, nullable=False)
    follow_up_confidence = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    follow_up_completed_at = Column(DateTime(timezone=True), nullable=True)