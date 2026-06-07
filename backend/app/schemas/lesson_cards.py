from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.course_types import TopicType


ContentBlockType = Literal[
    "paragraph",
    "bullet_list",
    "latex",
    "code",
    "callout",
]

StyledElementType = Literal[
    "table",
    "comparison",
    "comparison_table",
    "checklist",
    "timeline",
    "formula_steps",
    "proof_skeleton",
    "decision_matrix",
    "workflow_map",
    "glossary_table",
    "input_output_table",
    "stage_map",
    "term_map",
    "code_trace",
]

VisualRenderMode = Literal[
    "actual_visual",
    "styled_ui",
    "latex",
    "code",
    "table",
    "none",
]

MicrocheckType = Literal[
    "reveal",
    "multiple_choice",
    "visual_reveal",
]

InteractiveLinkAction = Literal[
    "popup_only",
    "open_study_path",
    "review_earlier_topic",
    "ask_question",
]

PracticeQuestionType = Literal[
    "short_answer",
    "multiple_choice",
    "select_all",
    "math",
    "math_input",
    "coding",
    "coding_environment",
    "visual_labeling",
    "ordering",
    "debugging",
    "debugging_scenario",
    "decision_scenario",
]

PracticeDifficulty = Literal[
    "intro",
    "standard",
    "high_level",
    "edge_case",
    "transfer",
]


class ContentBlock(BaseModel):
    type: ContentBlockType
    content: Any


class StyledElement(BaseModel):
    type: StyledElementType
    title: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class VisualPlan(BaseModel):
    render_mode: VisualRenderMode = "none"
    visual_type: str | None = None
    description: str | None = None
    reason: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class MicrocheckOption(BaseModel):
    id: str | None = None
    label: str
    value: str | None = None


class Microcheck(BaseModel):
    type: MicrocheckType = "reveal"
    question: str
    options: list[MicrocheckOption] = Field(default_factory=list)
    correct_answer: str
    explanation: str
    visual_feedback_plan: VisualPlan | None = None


class InteractiveLink(BaseModel):
    text: str
    explanation: str
    why_it_matters_here: str | None = None
    action: InteractiveLinkAction = "popup_only"
    target: str | None = None


class LessonCard(BaseModel):
    id: str | None = None
    blueprint_key: str | None = None
    card_type: str
    title: str
    main_concept: str = ""
    learning_goal: str = ""
    example_type: str = "none"
    visual_type: str = "none"
    points: list[str] = Field(default_factory=list)
    body: str | list[str] = ""
    bullets: list[str] = Field(default_factory=list)
    new_concepts: list[str] = Field(default_factory=list)
    review_concepts: list[str] = Field(default_factory=list)
    prerequisite_concepts: list[str] = Field(default_factory=list)
    concept_support: list[dict[str, Any]] = Field(default_factory=list)
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    styled_elements: list[StyledElement] = Field(default_factory=list)
    visual_plan: VisualPlan | dict[str, Any] | None = None
    visual_description: str = ""
    visual_index: int = -1
    annotations: list[str] = Field(default_factory=list)
    example: str = ""
    code_snippet: str = ""
    code_language: str = "python"
    highlight_lines_per_step: list[list[int]] = Field(default_factory=list)
    idea_refs: list[dict[str, Any]] = Field(default_factory=list)
    continuation_group_id: str = ""
    continuation_index: int = 0
    continuation_total: int = 0
    continuation_reason: str = ""
    continues_from_previous: bool = False
    visual_focus: dict[str, Any] | None = None
    execution_trace: dict[str, Any] | None = None
    micro_check: dict[str, Any] = Field(default_factory=dict)
    microcheck: Microcheck | None = None
    interactive_links: list[InteractiveLink] = Field(default_factory=list)
    deeper_explanation: str = ""
    what_to_notice: str = ""
    estimated_seconds: int = 45
    transition_text: str = ""
    next_card_label: str = ""
    practice_question_index: int = -1
    quality_score: int = 0


class TopicScopeContract(BaseModel):
    current_topic: str
    user_goal: str = ""
    topic_type: str = "concept_intuition"
    course_type: str = "concept_intuition"
    secondary_course_types: list[str] = Field(default_factory=list)
    primary_learning_goal: str = ""
    target_skill: str = ""
    assumed_prerequisites: list[str] = Field(default_factory=list)
    brief_refresh_prerequisites: list[str] = Field(default_factory=list)
    popup_only_prerequisites: list[str] = Field(default_factory=list)
    prerequisite_mini_path_candidates: list[str] = Field(default_factory=list)
    in_scope_content: list[str] = Field(default_factory=list)
    out_of_scope_content: list[str] = Field(default_factory=list)
    must_not_teach: list[str] = Field(default_factory=list)
    allowed_card_sequence: list[str] = Field(default_factory=list)
    depth_notes: list[str] = Field(default_factory=list)


class PracticeItem(BaseModel):
    id: str | None = None
    question_type: PracticeQuestionType
    skill_target: str = ""
    prompt: str = ""
    question_text: str = ""
    concept_tested: str = ""
    related_section: str = ""
    why_this_matters: str = ""
    expected_answer: Any = None
    correct_answer: Any = None
    explanation: str = ""
    rubric: dict[str, Any] = Field(default_factory=dict)
    given: dict[str, Any] = Field(default_factory=dict)
    choices: list[dict[str, Any] | str] = Field(default_factory=list)
    options: list[dict[str, Any]] = Field(default_factory=list)
    starter_code: str = ""
    language: str = ""
    test_cases: list[dict[str, Any]] = Field(default_factory=list)
    visual_feedback_plan: VisualPlan | None = None
    difficulty: PracticeDifficulty | str | None = None
    edge_cases_tested: list[str] = Field(default_factory=list)
    misconceptions_tested: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TopicValidationIssue(BaseModel):
    severity: Literal["info", "warning", "error"] = "warning"
    code: str | None = None
    message: str
    card_id: str | None = None
    auto_fixable: bool = False


class TopicValidationReport(BaseModel):
    passed: bool = True
    issues: list[TopicValidationIssue] = Field(default_factory=list)
    auto_fix_suggestions: list[str] = Field(default_factory=list)
    requires_regeneration: bool = False


class FlexibleLessonJson(BaseModel):
    topic_type: TopicType | None = None
    course_type: TopicType | None = None
    secondary_course_types: list[TopicType] = Field(default_factory=list)
    knowledge_level: int | None = Field(default=None, ge=1, le=5)
    topic_scope_contract: TopicScopeContract | None = None
    blueprint_card_sequence: list[str] = Field(default_factory=list)
    intro: str = ""
    purpose: str = ""
    context: str = ""
    learning_objective: str = ""
    components: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    process: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    worked_examples: list[Any] = Field(default_factory=list)
    example_plan: dict[str, Any] = Field(default_factory=dict)
    edge_cases: list[Any] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    lesson_cards: list[LessonCard] = Field(default_factory=list)
    cards: list[LessonCard] = Field(default_factory=list)
    practice_questions: list[PracticeItem] = Field(default_factory=list)
    practice: list[PracticeItem] = Field(default_factory=list)
    visual_plan: list[dict[str, Any]] = Field(default_factory=list)
    source_preview: str = ""
    source_chunk_ids: list[str] = Field(default_factory=list)
    source_summary: str = ""
    adaptation_metadata: dict[str, Any] = Field(default_factory=dict)
    scope_validation_report: dict[str, Any] = Field(default_factory=dict)
    visual_validation_report: dict[str, Any] = Field(default_factory=dict)
    topic_quality_report: dict[str, Any] = Field(default_factory=dict)
    validation_report: TopicValidationReport = Field(
        default_factory=TopicValidationReport
    )
    validation_reports: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}


LessonJson = FlexibleLessonJson
