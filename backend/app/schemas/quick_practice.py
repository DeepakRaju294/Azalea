from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class QuickPracticeSessionCreate(BaseModel):
    prompt: str
    exact_problem: bool = False


class QuickPracticeSessionRead(BaseModel):
    id: str
    prompt: str
    title: Optional[str] = None
    source_filename: Optional[str] = None
    current_question: Optional[str] = None
    exact_problem: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class QuickPracticeQuestionRead(BaseModel):
    id: str
    session_id: str
    question_type: str
    topic: Optional[str] = None
    skill_target: Optional[str] = None
    difficulty: Optional[str] = None
    question_text: str
    choices: list[str] = Field(default_factory=list)
    given: list[str] = Field(default_factory=list)
    starter_code: Optional[str] = None
    language: Optional[str] = None
    test_cases: list[dict[str, Any]] = Field(default_factory=list)
    source_reference: Optional[str] = None
    reason: Optional[str] = None
    order_index: int
    created_at: datetime

    @field_validator("choices", "given", "test_cases", mode="before")
    @classmethod
    def default_empty_lists(cls, value):
        return value or []

    class Config:
        from_attributes = True


class QuickPracticeQuestionSetRequest(BaseModel):
    count: int = Field(default=8, ge=1, le=20)
    replace_existing: bool = False


class QuickPracticeHintRequest(BaseModel):
    question_id: Optional[str] = None
    question: Optional[str] = None
    user_partial_answer: Optional[str] = None


class QuickPracticeSubmitRequest(BaseModel):
    question_id: Optional[str] = None
    question: Optional[str] = None
    user_answer: str
    hint_used: bool = False


class QuickPracticeCodeRunRequest(BaseModel):
    question_id: Optional[str] = None
    code: str
    language: Optional[str] = "python"
    test_cases: list[dict[str, Any]] = Field(default_factory=list)


class QuickPracticeSubmitResponse(BaseModel):
    attempt_id: str
    is_correct: bool
    performance_level: str = Field(
        description="One of: strong, fragile, minor_mistake, weak"
    )
    mistake_type: Optional[str] = None
    feedback: str
    follow_up_question: Optional[str] = None
    next_action: str
    adaptive_response: dict = Field(default_factory=dict)
    created_at: datetime


class QuickPracticeAttemptRead(BaseModel):
    id: str
    session_id: str
    question_id: Optional[str] = None
    question: str
    question_type: Optional[str] = None
    user_answer: str
    is_correct: Optional[bool] = None
    performance_level: Optional[str] = None
    mistake_type: Optional[str] = None
    feedback: Optional[str] = None
    hint_used: bool = False
    follow_up_question: Optional[str] = None
    next_action: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
