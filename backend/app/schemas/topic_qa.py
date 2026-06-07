from pydantic import BaseModel, Field


class TopicQARequest(BaseModel):
    question: str
    study_path_id: str | None = None
    lesson_id: str | None = None
    current_section: str | None = None
    lesson_context: str | None = None
    selected_text: str | None = None
    highlighted_text: str | None = None
    card_id: str | None = None
    card_title: str | None = None
    clarification_mode: str | None = None
    prior_confusion_event_id: str | None = None


class TopicQASource(BaseModel):
    chunk_id: str
    material_id: str
    material_title: str
    material_filename: str | None = None
    chunk_index: int
    source_label: str
    preview: str


class TopicQAResponse(BaseModel):
    answer: str
    sources: list[TopicQASource]
    confusion_event_id: str | None = None
    confusion_type: str = "general_question"
    concept_name: str = "overall_topic"
    clarification_mode: str = "direct_answer"
    suggested_actions: list[str] = Field(default_factory=list)
    follow_up_prompts: list[str] = Field(default_factory=list)


class ConfusionEventRead(BaseModel):
    id: str
    topic_id: str
    study_path_id: str | None = None
    lesson_id: str | None = None
    card_id: str | None = None
    card_title: str | None = None
    current_section: str | None = None
    highlighted_text: str | None = None
    user_question: str
    answer_generated: str
    confusion_type: str
    concept_name: str
    clarification_mode: str
    resolved: bool
    still_confused_count: int
    follow_up_count: int
    suggested_actions: list[str] = Field(default_factory=list)
    created_at: str


class ConfusionEventUpdate(BaseModel):
    resolved: bool | None = None
    still_confused: bool = False
    follow_up: bool = False
    practice_check_correctness: float | None = None
