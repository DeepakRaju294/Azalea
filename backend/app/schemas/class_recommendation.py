from datetime import datetime

from pydantic import BaseModel


class ClassRecommendedTopicRead(BaseModel):
    id: str
    title: str
    status: str
    estimated_minutes: int | None = None


class ClassRecommendedStudyPathRead(BaseModel):
    id: str
    title: str


class ClassRecommendationRead(BaseModel):
    message: str
    topic: ClassRecommendedTopicRead | None = None
    study_path: ClassRecommendedStudyPathRead | None = None
    is_complete: bool = False

    today_minutes: int = 0
    daily_goal_minutes: int | None = None
    remaining_today_minutes: int = 0

    week_minutes: int = 0
    weekly_goal_minutes: int | None = None
    remaining_week_minutes: int = 0

    deadline: datetime | None = None