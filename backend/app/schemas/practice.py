from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PracticeHintRequest(BaseModel):
    study_path_id: str
    topic_id: str
    lesson_id: Optional[str] = None

    question: str
    user_partial_answer: Optional[str] = None
    lesson_context: Optional[str] = None
    current_section: Optional[str] = None


class PracticeHintResponse(BaseModel):
    hint: str
    guiding_question: str
    concept_to_review: Optional[str] = None


class PracticeSubmitRequest(BaseModel):
    study_path_id: str
    topic_id: str
    lesson_id: Optional[str] = None

    question: str
    user_answer: str
    lesson_context: Optional[str] = None
    current_section: Optional[str] = None
    concept_tested: Optional[str] = None
    related_section: Optional[str] = None
    hint_used: bool = False


class PracticeSubmitResponse(BaseModel):
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


class PracticeAttemptRead(BaseModel):
    id: str

    study_path_id: str
    topic_id: str
    lesson_id: Optional[str] = None

    question: str
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


class CodeRunTestCase(BaseModel):
    input: str = ""
    expected: str = ""


class CodeRunRequest(BaseModel):
    code: str
    language: Optional[str] = "python"
    test_cases: list[CodeRunTestCase] = Field(default_factory=list)


class CodeRunCaseResult(BaseModel):
    case_number: int
    input: str
    expected: str
    actual: str
    stderr: str
    passed: bool
    status: str


class CodeRunResponse(BaseModel):
    language: str
    passed: int
    total: int
    all_passed: bool
    error: Optional[str] = None
    hidden_passed: int = 0
    hidden_total: int = 0
    cases: list[CodeRunCaseResult] = Field(default_factory=list)
