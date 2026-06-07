from datetime import datetime
from pydantic import BaseModel


class ContentChunkRead(BaseModel):
    id: str
    material_id: str
    chunk_index: int
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}