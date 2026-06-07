from typing import Literal

from pydantic import BaseModel, Field


StartingMode = Literal[
    "full_teach",
    "compressed_refresher",
    "nuance_first",
    "edge_cases",
    "transfer_practice",
]

KnowledgeState = Literal[
    "unknown",
    "familiar",
    "fragile",
    "stable",
    "transferable",
]


class GenerateTopicLessonPayload(BaseModel):
    starting_mode: StartingMode | None = "full_teach"
    explanation_density: str | None = None
    estimated_state: KnowledgeState | None = None
    knowledge_level: int | None = Field(default=None, ge=1, le=5)
    adaptation_note: str | None = None
    fragile_concepts: list[str] = Field(default_factory=list)
    review_concepts: list[str] = Field(default_factory=list)

    # Milestone G: cross-topic learner memory
    stable_concepts: list[str] = Field(default_factory=list)
    transferable_concepts: list[str] = Field(default_factory=list)
    concepts_to_skip: list[str] = Field(default_factory=list)
    concepts_to_briefly_repair: list[str] = Field(default_factory=list)
    memory_guidance: str | None = None
