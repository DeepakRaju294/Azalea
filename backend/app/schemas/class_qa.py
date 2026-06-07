from pydantic import BaseModel


class ClassQARequest(BaseModel):
    question: str


class ClassQASource(BaseModel):
    chunk_id: str
    material_id: str
    material_title: str
    material_filename: str | None = None
    chunk_index: int
    source_label: str
    preview: str


class ClassQAResponse(BaseModel):
    answer: str
    sources: list[ClassQASource]
