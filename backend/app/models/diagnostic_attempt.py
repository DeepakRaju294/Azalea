from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class DiagnosticAttempt(Base):
    __tablename__ = "diagnostic_attempts"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(String, index=True, nullable=False)

    topic_id = Column(String, ForeignKey("topics.id", ondelete="CASCADE"), index=True, nullable=False)

    mode = Column(String, default="topic_start", nullable=False)
    # topic_start, refresh, review, final_review

    self_report_level = Column(Integer, nullable=True)
    # 0 = completely new
    # 1 = seen before
    # 2 = mostly know it
    # 3 = comfortable

    questions_json = Column(JSONB, default=list, nullable=False)
    answers_json = Column(JSONB, default=list, nullable=False)

    estimated_state = Column(String, default="unknown", nullable=False)
    # unknown, familiar, fragile, stable, transferable

    confidence_score = Column(Float, default=0.0, nullable=False)
    correctness_score = Column(Float, default=0.0, nullable=False)
    transfer_score = Column(Float, default=0.0, nullable=False)
    edge_case_score = Column(Float, default=0.0, nullable=False)

    completed = Column(Boolean, default=False, nullable=False)

    result_summary = Column(Text, nullable=True)
    recommended_starting_mode = Column(String, nullable=True)
    # full_teach, compressed_refresher, nuance_first, edge_cases, transfer_practice

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    topic = relationship("Topic")
