from pydantic import BaseModel


class WeakAreaRead(BaseModel):
    mistake_type: str
    count: int
    latest_feedback: str | None = None
    recommended_action: str


class WeakAreaSummaryRead(BaseModel):
    scope_id: str
    scope_type: str
    weak_areas: list[WeakAreaRead]


class WeakAreaQuestionRequest(BaseModel):
    mistake_type: str
    lesson_context: str | None = None


class WeakAreaQuestionResponse(BaseModel):
    question: str
    target_mistake_type: str
    reason: str


class SpacedReviewQuestionRequest(BaseModel):
    lesson_context: str | None = None


class SpacedReviewQuestionResponse(BaseModel):
    question: str
    reason: str
    review_due_at: str | None = None
