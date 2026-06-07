from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

class AlignmentMetricConcept(BaseModel):
    concept_name: str
    topic_id: str
    topic_title: str
    knowledge_state: str
    review_due_at: datetime | None = None
    review_reason: str | None = None


class StudyPathAlignmentMetrics(BaseModel):
    study_path_id: str
    overteaching_score: float
    underteaching_score: float
    time_to_alignment_score: float
    confidence_calibration_score: float
    transfer_success_rate: float
    delayed_recall_success_rate: float
    edge_case_success_rate: float
    repair_success_rate: float
    total_concepts_tracked: int
    stable_or_transferable_concepts: int
    fragile_or_unknown_concepts: int
    total_behavior_events: int
    fast_skip_count: int
    long_dwell_count: int
    revisit_count: int
    hint_count: int
    practice_count: int
    targeted_repair_count: int
    completed_repair_follow_up_count: int
    concepts_needing_support: list[AlignmentMetricConcept]
    concepts_moving_fast: list[AlignmentMetricConcept]
    summary: str


class ClassAlignmentMetricsResponse(BaseModel):
    class_id: str
    overteaching_score: float
    underteaching_score: float
    time_to_alignment_score: float
    confidence_calibration_score: float
    transfer_success_rate: float
    delayed_recall_success_rate: float
    edge_case_success_rate: float
    repair_success_rate: float
    total_concepts_tracked: int
    stable_or_transferable_concepts: int
    fragile_or_unknown_concepts: int
    total_behavior_events: int
    fast_skip_count: int
    long_dwell_count: int
    revisit_count: int
    hint_count: int
    practice_count: int
    targeted_repair_count: int
    completed_repair_follow_up_count: int
    concepts_needing_support: list[AlignmentMetricConcept]
    concepts_moving_fast: list[AlignmentMetricConcept]
    summary: str

class AdaptivePlanTask(BaseModel):
    task_type: str
    title: str
    reason: str
    topic_id: str | None = None
    topic_title: str | None = None
    concept_name: str | None = None
    estimated_minutes: int
    priority: int
    route_mode: str | None = None


class AdaptivePlanResponse(BaseModel):
    study_path_id: str
    recommended_minutes: int
    summary: str
    tasks: list[AdaptivePlanTask]

class ReviewQueueItem(BaseModel):
    concept_state_id: int
    topic_id: str
    topic_title: str
    concept_name: str
    knowledge_state: str
    review_due_at: datetime | None
    review_reason: str | None
    recommended_action: str
    estimated_minutes: int = 3


class ReviewQuestionRequest(BaseModel):
    concept_name: str
    lesson_context: str | None = None
    review_reason: str | None = None


class ReviewQuestionResponse(BaseModel):
    target_concept: str
    question: str
    reason: str
    expected_focus: str


class ReviewAnswerSubmitRequest(BaseModel):
    topic_id: str
    concept_name: str
    question: str
    answer: str
    confidence: int | None = Field(default=None, ge=1, le=5)
    review_reason: str | None = None


class ReviewAnswerSubmitResponse(BaseModel):
    topic_id: str
    concept_name: str
    correctness: float
    reasoning_quality: float
    feedback: str
    next_action: Literal[
        "mark_stable",
        "keep_in_review",
        "targeted_repair",
        "schedule_later",
    ]
    review_due_at: datetime | None = None
    review_reason: str | None = None


KnowledgeState = Literal[
    "unknown",
    "familiar",
    "fragile",
    "stable",
    "transferable",
]

DiagnosticMode = Literal[
    "topic_start",
    "refresh",
    "review",
    "final_review",
]

StartingMode = Literal[
    "full_teach",
    "compressed_refresher",
    "nuance_first",
    "edge_cases",
    "transfer_practice",
]


class SelfReportPayload(BaseModel):
    level: int = Field(ge=0, le=3)
    mode: DiagnosticMode = "topic_start"


class SelfReportResult(BaseModel):
    topic_id: str
    self_report_level: int
    estimated_state: KnowledgeState
    recommended_starting_mode: StartingMode
    explanation_density: str
    should_offer_diagnostic: bool


class DiagnosticQuestion(BaseModel):
    id: str
    type: Literal["recall", "application", "edge_case", "transfer", "confidence"]
    question: str
    concept_name: str | None = None


class StartDiagnosticPayload(BaseModel):
    mode: DiagnosticMode = "topic_start"
    self_report_level: int | None = Field(default=None, ge=0, le=3)


class StartDiagnosticResult(BaseModel):
    diagnostic_id: int
    topic_id: str
    mode: DiagnosticMode
    questions: list[DiagnosticQuestion]


class DiagnosticAnswer(BaseModel):
    question_id: str
    answer: str
    confidence: int | None = Field(default=None, ge=1, le=5)


class SubmitDiagnosticPayload(BaseModel):
    answers: list[DiagnosticAnswer]


class SubmitDiagnosticResult(BaseModel):
    diagnostic_id: int
    topic_id: str
    estimated_state: KnowledgeState
    recommended_starting_mode: StartingMode
    result_summary: str
    concept_states: list[dict[str, Any]]


class LearnerSignalPayload(BaseModel):
    topic_id: str
    concept_name: str
    signal_type: Literal[
        "self_report",
        "diagnostic",
        "practice",
        "lesson_micro_check",
        "question",
        "hint",
        "reread",
        "time_on_slide",
        "confidence",
    ]

    correctness: float | None = Field(default=None, ge=0.0, le=1.0)
    reasoning_quality: float | None = Field(default=None, ge=0.0, le=1.0)
    hint_used: bool = False
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    transfer_success: float | None = Field(default=None, ge=0.0, le=1.0)
    edge_case_success: float | None = Field(default=None, ge=0.0, le=1.0)
    time_seconds: int | None = None
    mistake_type: str | None = None
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearnerConceptStateRead(BaseModel):
    id: int
    topic_id: str
    concept_name: str
    knowledge_state: KnowledgeState

    familiarity_score: float
    conceptual_score: float
    procedural_score: float
    transfer_score: float
    confidence_score: float
    stability_score: float

    total_attempts: int
    correct_attempts: int
    hint_count: int
    misconception_count: int
    recurring_mistakes: list[Any]

    review_due_at: datetime | None
    review_reason: str | None

    class Config:
        from_attributes = True


class AlignmentSummary(BaseModel):
    topic_id: str
    strongest_concepts: list[LearnerConceptStateRead]
    fragile_concepts: list[LearnerConceptStateRead]
    review_queue: list[LearnerConceptStateRead]
    recommended_starting_mode: StartingMode
    adaptation_note: str

class LearnerMemoryConcept(BaseModel):
    concept_name: str
    topic_id: str
    topic_title: str
    knowledge_state: str
    familiarity_score: float
    conceptual_score: float
    procedural_score: float
    transfer_score: float
    confidence_score: float
    stability_score: float
    review_due_at: datetime | None = None
    review_reason: str | None = None


class StudyPathMemorySummary(BaseModel):
    study_path_id: str
    stable_concepts: list[LearnerMemoryConcept]
    fragile_concepts: list[LearnerMemoryConcept]
    transferable_concepts: list[LearnerMemoryConcept]
    unknown_concepts: list[LearnerMemoryConcept]
    concepts_to_skip: list[str]
    concepts_to_briefly_repair: list[str]
    recommended_lesson_guidance: str
    behavior_guidance: str | None = None
    possible_overteaching_signals: list[str] = []
    possible_underteaching_signals: list[str] = []

class ClassAdaptivePlanTask(BaseModel):
    task_type: str
    title: str
    reason: str
    class_id: str | None = None
    study_path_id: str | None = None
    study_path_title: str | None = None
    topic_id: str | None = None
    topic_title: str | None = None
    concept_name: str | None = None
    estimated_minutes: int
    priority: int
    route_mode: str | None = None


class ClassAdaptivePlanResponse(BaseModel):
    class_id: str
    recommended_minutes: int
    summary: str
    tasks: list[ClassAdaptivePlanTask]


class ClassMemorySummary(BaseModel):
    class_id: str
    stable_concepts: list[LearnerMemoryConcept]
    fragile_concepts: list[LearnerMemoryConcept]
    transferable_concepts: list[LearnerMemoryConcept]
    unknown_concepts: list[LearnerMemoryConcept]
    concepts_to_skip: list[str]
    concepts_to_briefly_repair: list[str]
    recommended_guidance: str


class GlobalMemorySummary(BaseModel):
    stable_patterns: list[str]
    fragile_patterns: list[str]
    preferred_learning_patterns: list[str]
    confidence_patterns: list[str]
    recommended_guidance: str

class TransferChallengeRequest(BaseModel):
    concept_name: str
    lesson_context: str | None = None
    prior_context: str | None = None


class TransferChallengeResponse(BaseModel):
    target_concept: str
    challenge: str
    reason: str
    expected_focus: str


class TransferChallengeSubmitRequest(BaseModel):
    topic_id: str
    concept_name: str
    challenge: str
    answer: str
    confidence: int | None = Field(default=None, ge=1, le=5)


class TransferChallengeSubmitResponse(BaseModel):
    target_concept: str
    correctness: float
    reasoning_quality: float
    feedback: str
    next_action: str
