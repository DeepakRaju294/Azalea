from datetime import datetime
from pydantic import BaseModel


class TextMaterialCreate(BaseModel):
    title: str
    text: str


class LearningMaterialRead(BaseModel):
    id: str
    class_id: str | None = None
    study_path_id: str | None = None
    title: str
    material_type: str
    filename: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
