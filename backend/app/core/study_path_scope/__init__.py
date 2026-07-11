"""StudyPathScope — the authoritative path plan (STUDY_PATH_SCOPE_SPEC v3.2).

Phase 1A ships the PLANNING sub-aggregate only (`StudyPathScopePlan`): schema + deterministic identity,
no factual grounding, no lesson changes. Dark behind `AZALEA_STUDY_PATH_SCOPE`. Pure package — importing it
pulls in no app services, so it is safe to import in tests (no .env / route contamination)."""
from __future__ import annotations

from .enums import (
    CardinalityPolicy, CertificationStatus, Facet, Grammar, MappingHealth, PlannedGrammarStatus,
    PlanningStatus, SectionType, SelectionSourceRole, SelectionStatus, SourceAlignmentMode,
)
from .ids import (
    concept_local_id, record_id, scope_id_for, section_id_for, short_hash, stable_slug, topic_id_for,
)
from .models import (
    Classification, Concept, ConceptIdentity, ConceptSelectionSource, CurriculumGraph, Edge, GlossaryTerm,
    GoalRequirement, LessonSectionPlan, Objective, OrderingConstraints, PlannedGrounding, Prereq,
    ScopeIdentity, ScopeIntent, ScopeProvenance, StudyPathScopePlan,
)

__all__ = [
    # enums
    "PlanningStatus", "CertificationStatus", "SourceAlignmentMode", "Facet", "SectionType",
    "CardinalityPolicy", "Grammar", "PlannedGrammarStatus", "SelectionSourceRole", "SelectionStatus",
    "MappingHealth",
    # ids
    "stable_slug", "short_hash", "scope_id_for", "concept_local_id", "topic_id_for", "section_id_for",
    "record_id",
    # models
    "StudyPathScopePlan", "ScopeIdentity", "ScopeIntent", "Classification", "CurriculumGraph",
    "OrderingConstraints", "Edge", "Concept", "ConceptIdentity", "LessonSectionPlan", "Objective",
    "Prereq", "GlossaryTerm", "GoalRequirement", "ConceptSelectionSource", "PlannedGrounding",
    "ScopeProvenance",
]
