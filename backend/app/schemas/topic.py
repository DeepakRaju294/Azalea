from datetime import datetime

from pydantic import BaseModel, Field

from app.core.course_types import TopicType


KnowledgeLevel = int


class TopicCreate(BaseModel):
    title: str
    purpose: str | None = None

    # Milestone 22: better topic generation metadata
    unit_title: str | None = None
    learner_outcome: str | None = None
    prerequisite_topics: str | None = None
    assumed_prerequisites: list[str] = Field(default_factory=list)
    source_refs: str | None = None
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    practice_target: str | None = None
    practice_format: str | None = None
    difficulty_focus: str | None = None
    boundary_reason: str | None = None
    modifiers: list[str] = Field(default_factory=list)
    source_coverage_notes: str | None = None
    card_blueprint_hint: list[str] = Field(default_factory=list)
    topic_type_reason: str | None = None
    course_type_reason: str | None = None
    visual_description: str | None = None

    order_index: int = 0
    estimated_minutes: int | None = None
    topic_type: TopicType | None = None
    course_type: TopicType | None = None
    secondary_course_types: list[TopicType] = Field(default_factory=list)
    knowledge_level: KnowledgeLevel | None = None
    decomposition_metadata: dict | None = None


class TopicRead(BaseModel):
    id: str
    study_path_id: str
    title: str
    purpose: str | None

    # Milestone 22: better topic generation metadata
    unit_title: str | None
    learner_outcome: str | None = None
    prerequisite_topics: str | None
    assumed_prerequisites: list[str] | None = None
    source_refs: str | None
    in_scope: list[str] | None = None
    out_of_scope: list[str] | None = None
    practice_target: str | None
    practice_format: str | None = None
    difficulty_focus: str | None = None
    boundary_reason: str | None = None
    modifiers: list[str] | None = None
    source_coverage_notes: str | None = None
    card_blueprint_hint: list[str] | None = None
    topic_type_reason: str | None = None
    course_type_reason: str | None = None
    visual_description: str | None = None

    order_index: int
    estimated_minutes: int | None
    topic_type: TopicType | None = None
    course_type: TopicType | None = None
    secondary_course_types: list[TopicType] | None = None
    knowledge_level: KnowledgeLevel | None = None
    status: str
    review_due_at: datetime | None
    review_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TopicUpdateStatus(BaseModel):
    status: str


class TopicScheduleReview(BaseModel):
    review_due_at: datetime | None
    review_reason: str | None = None


class TopicSelfReportKnowledge(BaseModel):
    self_report: int | str
