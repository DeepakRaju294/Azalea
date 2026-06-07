from datetime import datetime

from pydantic import BaseModel, Field


class ClassCreate(BaseModel):
    name: str
    description: str | None = None
    deadline: datetime | None = None
    daily_goal_minutes: int | None = Field(default=30, ge=0)
    weekly_goal_minutes: int | None = Field(default=180, ge=0)


class ClassUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    deadline: datetime | None = None
    daily_goal_minutes: int | None = Field(default=None, ge=0)
    weekly_goal_minutes: int | None = Field(default=None, ge=0)


class ClassRead(BaseModel):
    id: str
    user_id: str | None = None
    name: str
    description: str | None
    deadline: datetime | None
    daily_goal_minutes: int | None
    weekly_goal_minutes: int | None
    created_at: datetime

    model_config = {"from_attributes": True}