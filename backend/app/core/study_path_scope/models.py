"""StudyPathScopePlan — the Phase-1A planning aggregate (STUDY_PATH_SCOPE_SPEC v3.2 §1, §12).

This is the SMALLER sub-aggregate the reviewer mandated: it holds only planning fields (identity / intent /
classification / curriculum / provenance). It has NO grounding, verification, notation, or certification
fields, so Phase-1A code physically cannot depend on them. The full `StudyPathScope` will later wrap a
validated plan. Pure — pydantic + stdlib only, no app-service imports (so tests can import it freely)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .enums import (
    CardinalityPolicy, CertificationStatus, Facet, Grammar, MappingHealth, PlannedGrammarStatus,
    PlanningStatus, SectionType, SelectionSourceRole, SelectionStatus, SourceAlignmentMode,
)
from .ids import concept_local_id, section_id_for, stable_slug, topic_id_for


class ScopeIdentity(BaseModel):
    scope_id: str
    scope_version: int = 1
    input_hash: str = ""
    source_revision: str = ""
    builder_version: str = "0.1.0"
    validator_version: str = "0.1.0"
    planning_status: PlanningStatus = PlanningStatus.draft
    certification_status: CertificationStatus = CertificationStatus.not_started   # always in Phase 1A
    source_alignment_mode: SourceAlignmentMode = SourceAlignmentMode.course_faithful


class ScopeProvenance(BaseModel):
    emitted_by: str = "scope_builder"
    model_ref: str = ""


class Classification(BaseModel):
    domain: str
    domain_provenance: str = ""


class GoalRequirement(BaseModel):
    requirement_id: str
    description: str
    source: str = "goal"
    required: bool = True
    priority: int = 0
    depth: str = "working"


class ScopeIntent(BaseModel):
    goal: str
    goal_requirements: list[GoalRequirement] = Field(default_factory=list)
    target_depth: str = "working"
    exclusions: list[str] = Field(default_factory=list)


class Prereq(BaseModel):
    id: str
    name: str
    anchor: str = ""
    future_path_ref: Optional[str] = None


class GlossaryTerm(BaseModel):
    term: str
    gloss: str
    owner: str = "intro"


class Objective(BaseModel):
    objective_id: str
    statement: str
    target_depth: str = "working"
    excluded_depth: Optional[str] = None
    # objectives are COMMITMENTS (required by default, §12); enrichment lives in optional sections/mappings.


class ConceptSelectionSource(BaseModel):
    selection_source_id: str
    source_id: str
    chunk_id: str = ""
    span: str = ""
    role: SelectionSourceRole = SelectionSourceRole.scope


class PlannedGrounding(BaseModel):
    """Phase 1A plans WHICH trace grammar a concept will use; it does not create facts (§1.3, §12). The
    grounding *content* stays null until Phase 1B — an empty variant would falsely imply confident content."""
    grammar: Grammar
    selection_method: str = "model"
    confidence: float = 0.0
    status: PlannedGrammarStatus = PlannedGrammarStatus.proposed
    grounding_status: str = "not_started"


class ConceptIdentity(BaseModel):
    concept_id: str
    topic_id: str
    name: str
    topic_type: str
    canonical_concept_key: str          # GLOBAL semantic identity — the id basis, NOT the display name
    facet: Facet = Facet.core
    parent_concept_key: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)

    @classmethod
    def create(cls, *, name: str, topic_type: str, canonical_concept_key: Optional[str] = None,
               facet: Facet = Facet.core, parent_concept_key: Optional[str] = None,
               aliases: Optional[list[str]] = None) -> "ConceptIdentity":
        """Derive scope-local ids from the CANONICAL KEY (+facet), never the mutable name — so a rename is a
        no-op and identical inputs rebuild identical ids. The key falls back to a slug of the name only when no
        adapter slug / catalog id is supplied."""
        key = canonical_concept_key or stable_slug(name)
        cid = concept_local_id(key, facet)
        return cls(concept_id=cid, topic_id=topic_id_for(cid), name=name, topic_type=topic_type,
                   canonical_concept_key=key, facet=facet, parent_concept_key=parent_concept_key,
                   aliases=list(aliases or []))


class LessonSectionPlan(BaseModel):
    section_id: str
    section_type: SectionType
    objective_ids: list[str] = Field(default_factory=list)
    required_grounding_artifact_ids: list[str] = Field(default_factory=list)
    optional: bool = False
    order: int = 0

    @classmethod
    def create(cls, *, concept_id: str, section_type: SectionType, order: int,
               objective_ids: Optional[list[str]] = None, optional: bool = False) -> "LessonSectionPlan":
        return cls(section_id=section_id_for(concept_id, section_type, order), section_type=section_type,
                   order=order, objective_ids=list(objective_ids or []), optional=optional)


class Concept(BaseModel):
    identity: ConceptIdentity
    prerequisite_concept_ids: list[str] = Field(default_factory=list)
    key_terms: list[str] = Field(default_factory=list)
    learning_objectives: list[Objective] = Field(default_factory=list)
    section_plan: list[LessonSectionPlan] = Field(default_factory=list)
    selection_sources: list[ConceptSelectionSource] = Field(default_factory=list)
    planned_grounding: Optional[PlannedGrounding] = None
    split_reason: Optional[str] = None                 # authored; cardinality.policy is DERIVED from below
    # derived (one owner — read, don't recompute elsewhere):
    selection_status: SelectionStatus = SelectionStatus.supported
    mapping_health: MappingHealth = MappingHealth.clean

    @property
    def cardinality_policy(self) -> CardinalityPolicy:
        return CardinalityPolicy.atomic if len(self.section_plan) <= 1 else CardinalityPolicy.multi_section


class Edge(BaseModel):
    from_concept_id: str
    to_concept_id: str


class OrderingConstraints(BaseModel):
    hard_edges: list[Edge] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)


class CurriculumGraph(BaseModel):
    prerequisites: list[Prereq] = Field(default_factory=list)
    concepts: list[Concept] = Field(default_factory=list)
    ordering_constraints: OrderingConstraints = Field(default_factory=OrderingConstraints)
    glossary: list[GlossaryTerm] = Field(default_factory=list)
    resolved_concept_order: list[str] = Field(default_factory=list)   # owned derived value (§11); readers consume it
    # decomposition_record (mappings) is PR2 — intentionally absent from the PR1 schema.


class StudyPathScopePlan(BaseModel):
    """The Phase-1A aggregate. Serializes/deserializes losslessly (round-trip identity is an exit criterion)."""
    schema_version: int = 1
    identity: ScopeIdentity
    intent: ScopeIntent
    classification: Classification
    curriculum: CurriculumGraph = Field(default_factory=CurriculumGraph)
    provenance: ScopeProvenance = Field(default_factory=ScopeProvenance)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str) -> "StudyPathScopePlan":
        return cls.model_validate_json(raw)
