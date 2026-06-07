from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, index=True)

    class_id = Column(String, ForeignKey("classes.id"), nullable=True)
    study_path_id = Column(String, ForeignKey("study_paths.id"), nullable=True)
    topic_id = Column(String, ForeignKey("topics.id"), nullable=True)

    minutes_spent = Column(Integer, nullable=False, default=0)

    # lesson, practice, qa, review, regeneration
    activity_type = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    azalea_class = relationship("AzaleaClass")
    study_path = relationship("StudyPath")
    topic = relationship("Topic")
