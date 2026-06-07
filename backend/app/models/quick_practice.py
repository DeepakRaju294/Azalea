import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class QuickPracticeSession(Base):
    __tablename__ = "quick_practice_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    title = Column(String(255), nullable=True)
    source_text = Column(Text, nullable=True)
    source_filename = Column(String(255), nullable=True)
    current_question = Column(Text, nullable=True)
    exact_problem = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    attempts = relationship(
        "QuickPracticeAttempt",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="QuickPracticeAttempt.created_at.desc()",
    )
    questions = relationship(
        "QuickPracticeQuestion",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="QuickPracticeQuestion.created_at.desc()",
    )


class QuickPracticeQuestion(Base):
    __tablename__ = "quick_practice_questions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String,
        ForeignKey("quick_practice_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    question_type = Column(String, nullable=False, default="short_answer")
    topic = Column(String, nullable=True)
    skill_target = Column(String, nullable=True)
    difficulty = Column(String, nullable=True)
    question_text = Column(Text, nullable=False)
    choices = Column(JSON, nullable=True)
    given = Column(JSON, nullable=True)
    starter_code = Column(Text, nullable=True)
    language = Column(String, nullable=True)
    test_cases = Column(JSON, nullable=True)
    hidden_test_cases = Column(JSON, nullable=True)
    correct_answer = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    source_reference = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("QuickPracticeSession", back_populates="questions")
    attempts = relationship("QuickPracticeAttempt", back_populates="practice_question")


class QuickPracticeAttempt(Base):
    __tablename__ = "quick_practice_attempts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String,
        ForeignKey("quick_practice_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id = Column(
        String,
        ForeignKey("quick_practice_questions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    question = Column(Text, nullable=False)
    question_type = Column(String, nullable=True)
    question_json = Column(JSON, nullable=True)
    user_answer = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=True)
    performance_level = Column(String, nullable=True)
    mistake_type = Column(String, nullable=True)
    feedback = Column(Text, nullable=True)
    hint_used = Column(Boolean, default=False)
    follow_up_question = Column(Text, nullable=True)
    next_action = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("QuickPracticeSession", back_populates="attempts")
    practice_question = relationship("QuickPracticeQuestion", back_populates="attempts")
