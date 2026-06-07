from pydantic import BaseModel


class RecommendedTopicRead(BaseModel):
    id: str
    title: str
    status: str
    estimated_minutes: int | None = None


class StudyPathRecommendationRead(BaseModel):
    message: str
    topic: RecommendedTopicRead | None = None
    is_complete: bool = False