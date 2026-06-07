from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class LearnerConceptState(Base):
    __tablename__ = "learner_concept_states"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(String, index=True, nullable=False)

    topic_id = Column(String, ForeignKey("topics.id", ondelete="CASCADE"), index=True, nullable=False)

    concept_name = Column(String, index=True, nullable=False)

    knowledge_state = Column(String, default="unknown", nullable=False)
    # unknown, familiar, fragile, stable, transferable

    familiarity_score = Column(Float, default=0.0, nullable=False)
    conceptual_score = Column(Float, default=0.0, nullable=False)
    procedural_score = Column(Float, default=0.0, nullable=False)
    transfer_score = Column(Float, default=0.0, nullable=False)
    confidence_score = Column(Float, default=0.0, nullable=False)
    stability_score = Column(Float, default=0.0, nullable=False)

    total_attempts = Column(Integer, default=0, nullable=False)
    correct_attempts = Column(Integer, default=0, nullable=False)
    hint_count = Column(Integer, default=0, nullable=False)

    misconception_count = Column(Integer, default=0, nullable=False)
    recurring_mistakes = Column(JSONB, default=list, nullable=False)

    last_signal_type = Column(String, nullable=True)
    last_signal_summary = Column(Text, nullable=True)

    review_due_at = Column(DateTime(timezone=True), nullable=True)
    review_reason = Column(String, nullable=True)

    evidence_json = Column(JSONB, default=dict, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    topic = relationship("Topic")
