from pydantic import BaseModel
from typing import Optional


class HomeRecommendationRead(BaseModel):
    type: str
    title: str
    reason: str

    class_id: Optional[str] = None
    class_name: Optional[str] = None

    study_path_id: Optional[str] = None
    study_path_title: Optional[str] = None

    topic_id: Optional[str] = None
    topic_title: Optional[str] = None

    review_due_at: Optional[str] = None
    review_reason: Optional[str] = None

    minutes_estimate: Optional[int] = None