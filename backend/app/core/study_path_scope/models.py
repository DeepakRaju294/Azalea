"""StudyPathScopePlan — the Phase-1A planning aggregate (STUDY_PATH_SCOPE_SPEC v3.2 §1, §12).

This is the SMALLER sub-aggregate the reviewer mandated: it holds only planning fields (identity / intent /
classification / curriculum / provenance). It has NO grounding, verification, notation, or certification
fields, so Phase-1A code physically cannot depend on them. The full `StudyPathScope` will later wrap a
validated plan. Pure — pydantic + stdlib only, no app-service imports (so tests can import it freely)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .enums import (
    AuditStatus, AuditType, CardinalityPolicy, CertificationStatus, ConceptRelation, DecompositionMethod,
    EvidenceStatus, Facet, Grammar, MappingHealth, MappingStatus, PlannedGrammarStatus, PlanningStatus,
    SectionType, SelectionMethod, SelectionSourceRole, SelectionStatus, Severity, SourceAlignmentMode,
    ValidatorKind,
)
from .ids import concept_local_id, record_id, section_id_for, stable_slug, topic_id_for


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
    """A source span that justified a CURRICULUM decision (why-selected). Lives once in the scope-level
    `SelectionSourceRegistry`; `SelectionEvidence.evidence_ref` points at its id — never copied per concept
    (§12)."""
    selection_source_id: str
    source_id: str
    chunk_id: str = ""
    span: str = ""
    role: SelectionSourceRole = SelectionSourceRole.scope

    @classmethod
    def create(cls, *, source_id: str, chunk_id: str = "", span: str = "",
               role: SelectionSourceRole = SelectionSourceRole.scope) -> "ConceptSelectionSource":
        return cls(selection_source_id=record_id("selsrc", source_id, chunk_id, span, role),
                   source_id=source_id, chunk_id=chunk_id, span=span, role=role)


class SelectionSourceRegistry(BaseModel):
    """Scope-level `{selection_source_id → ConceptSelectionSource}` (§12 code-time decision). Single ownership:
    one span can justify several mappings by id, with no duplicated spans."""
    sources: dict[str, ConceptSelectionSource] = Field(default_factory=dict)

    def add(self, source: ConceptSelectionSource) -> str:
        self.sources[source.selection_source_id] = source
        return source.selection_source_id

    def get(self, selection_source_id: str) -> Optional[ConceptSelectionSource]:
        return self.sources.get(selection_source_id)

    def __contains__(self, selection_source_id: str) -> bool:
        return selection_source_id in self.sources


class SelectionEvidence(BaseModel):
    """One evidenced reason a requirement×concept (or requirement×prereq) mapping holds. `evidence_ref` points
    into the `SelectionSourceRegistry` — no duplicated spans (§1.4). `status`/`method` drive the DERIVED
    mapping status (owner: `selection.derive_mapping_status`)."""
    evidence_id: str
    method: SelectionMethod
    evidence_ref: str = ""                 # → ConceptSelectionSource.selection_source_id (may be "" for goal)
    status: EvidenceStatus = EvidenceStatus.supporting
    confidence: float = 0.0

    @classmethod
    def create(cls, *, method: SelectionMethod, requirement_id: str, target_id: str, evidence_ref: str = "",
               status: EvidenceStatus = EvidenceStatus.supporting, confidence: float = 0.0) -> "SelectionEvidence":
        eid = record_id("evidence", requirement_id, target_id, method, evidence_ref, status)
        return cls(evidence_id=eid, method=method, evidence_ref=evidence_ref, status=status,
                   confidence=confidence)


class RequirementConceptMapping(BaseModel):
    """A requirement covered by a concept, via a relation, backed by evidence. `status` is DERIVED from the
    evidence (one owner: `selection.build_concept_mapping`)."""
    mapping_id: str
    requirement_id: str
    concept_id: str
    relation: ConceptRelation = ConceptRelation.direct
    evidence: list[SelectionEvidence] = Field(default_factory=list)
    status: MappingStatus = MappingStatus.ambiguous


class RequirementPrereqMapping(BaseModel):
    """A requirement's prerequisite. Prerequisites map SEPARATELY from concepts — a prereq is never a concept
    (§1.4). `status` derived from evidence (one owner: `selection.build_prereq_mapping`)."""
    mapping_id: str
    requirement_id: str
    prereq_id: str
    evidence: list[SelectionEvidence] = Field(default_factory=list)
    status: MappingStatus = MappingStatus.ambiguous


class DecompositionRecord(BaseModel):
    """The evidenced decomposition: which requirements are covered by which concepts/prereqs, and what stayed
    ambiguous. Coverage is a list of evidenced mappings, not a bare requirement→concept[] map (§1.4)."""
    goal_claims: list[GoalRequirement] = Field(default_factory=list)
    concept_coverage: list[RequirementConceptMapping] = Field(default_factory=list)
    prereq_coverage: list[RequirementPrereqMapping] = Field(default_factory=list)
    decomposition_method: DecompositionMethod = DecompositionMethod.goal_only
    unresolved_ambiguities: list[str] = Field(default_factory=list)


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
    # WHY-selected sources live once in the scope-level SelectionSourceRegistry, referenced by mapping
    # evidence — never copied per concept (§12). So a concept holds no selection_sources list.
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
    decomposition_record: DecompositionRecord = Field(default_factory=DecompositionRecord)   # §1.4 (PR2)


class AuditRecord(BaseModel):
    """One invariant result (§4). `audit_type` says what KIND of check; `severity` says the EFFECT — a
    blocking planning failure rejects the plan, a warning does not."""
    audit_id: str
    invariant: str
    validator: ValidatorKind = ValidatorKind.planning
    audit_type: AuditType = AuditType.structural
    severity: Severity = Severity.blocking
    status: AuditStatus = AuditStatus.passed
    confidence: float = 1.0
    affected_dimension: Optional[str] = None
    fallback_action: Optional[str] = None
    evidence: str = ""


class RepairRecord(BaseModel):
    """A recorded repair (§7). Present for schema completeness; Phase 1A performs no auto-repairs."""
    repair_id: str
    invariant: str
    repair_class: str
    original: str = ""
    repaired: str = ""
    method: str = ""
    severity: Severity = Severity.warning
    requires_review: bool = False
    lifecycle_effect: str = ""
    evidence: str = ""


class ValidationReport(BaseModel):
    invariants: list[AuditRecord] = Field(default_factory=list)
    repair_history: list[RepairRecord] = Field(default_factory=list)


class StudyPathScopePlan(BaseModel):
    """The Phase-1A aggregate. Serializes/deserializes losslessly (round-trip identity is an exit criterion)."""
    schema_version: int = 1
    identity: ScopeIdentity
    intent: ScopeIntent
    classification: Classification
    curriculum: CurriculumGraph = Field(default_factory=CurriculumGraph)
    selection_sources: SelectionSourceRegistry = Field(default_factory=SelectionSourceRegistry)   # §12 (PR2)
    validation: ValidationReport = Field(default_factory=ValidationReport)                         # §4 (PR4)
    provenance: ScopeProvenance = Field(default_factory=ScopeProvenance)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str) -> "StudyPathScopePlan":
        return cls.model_validate_json(raw)
