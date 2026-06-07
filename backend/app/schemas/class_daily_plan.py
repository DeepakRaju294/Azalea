from pydantic import BaseModel


class ClassDailyPlanTaskRead(BaseModel):
    task_type: str
    title: str
    reason: str
    study_path_id: str
    study_path_title: str
    topic_id: str
    topic_status: str
    estimated_minutes: int


class ClassDailyPlanRead(BaseModel):
    class_id: str
    today_minutes: int
    daily_goal_minutes: int | None
    remaining_today_minutes: int
    tasks: list[ClassDailyPlanTaskRead]