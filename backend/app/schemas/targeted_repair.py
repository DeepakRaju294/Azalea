from datetime import datetime

from pydantic import BaseModel


class TargetedRepairRequest(BaseModel):
    concept_name: str
    mistake_type: str | None = None
    question: str | None = None
    user_answer: str | None = None
    lesson_context: str | None = None
    feedback: str | None = None


class TargetedRepairResponse(BaseModel):
    repair_attempt_id: int
    target_concept: str
    repair_explanation: str
    why_this_matters: str
    follow_up_question: str
    next_action: str
    repair_level: str
    prior_repair_count: int


class TargetedRepairFollowUpSubmitRequest(BaseModel):
    answer: str
    confidence: int | None = None


class TargetedRepairFollowUpSubmitResponse(BaseModel):
    repair_attempt_id: int
    is_complete: bool
    correctness: float
    reasoning_quality: float
    feedback: str
    next_action: str
    created_at: datetime | None = None