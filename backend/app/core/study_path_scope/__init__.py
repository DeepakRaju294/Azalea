"""StudyPathScope — the authoritative path plan (STUDY_PATH_SCOPE_SPEC v3.2).

Phase 1A ships the PLANNING sub-aggregate only (`StudyPathScopePlan`): schema + deterministic identity,
no factual grounding, no lesson changes. Dark behind `AZALEA_STUDY_PATH_SCOPE`. Pure package — importing it
pulls in no app services, so it is safe to import in tests (no .env / route contamination)."""
from __future__ import annotations

from .enums import (
    CardinalityPolicy, CertificationStatus, ConceptRelation, DecompositionMethod, EvidenceStatus, Facet,
    Grammar, MappingHealth, MappingStatus, PlannedGrammarStatus, PlanningStatus, SectionType,
    SelectionMethod, SelectionSourceRole, SelectionStatus, SourceAlignmentMode,
)
from .ids import (
    concept_local_id, record_id, scope_id_for, section_id_for, short_hash, stable_slug, topic_id_for,
)
from .models import (
    Classification, Concept, ConceptIdentity, ConceptSelectionSource, CurriculumGraph, DecompositionRecord,
    Edge, GlossaryTerm, GoalRequirement, LessonSectionPlan, Objective, OrderingConstraints, PlannedGrounding,
    Prereq, RequirementConceptMapping, RequirementPrereqMapping, ScopeIdentity, ScopeIntent, ScopeProvenance,
    SelectionEvidence, SelectionSourceRegistry, StudyPathScopePlan,
)
from .selection import (
    DecompositionCheck, IntegrityIssue, aggregate_concept_selection, apply_selection_status,
    build_concept_mapping, build_prereq_mapping, check_decomposition, check_referential_integrity,
    derive_mapping_status, uncovered_required_requirements,
)
from .construction import (
    DiscoveredFacet, OrderingResult, bridge_insertion_allowed, cardinality_of, consolidate_facets,
    count_hard_edge_violations, hard_edges_from_concepts, resolve_concept_order,
)

__all__ = [
    # enums
    "PlanningStatus", "CertificationStatus", "SourceAlignmentMode", "Facet", "SectionType",
    "CardinalityPolicy", "Grammar", "PlannedGrammarStatus", "SelectionSourceRole", "SelectionStatus",
    "MappingHealth", "SelectionMethod", "ConceptRelation", "EvidenceStatus", "MappingStatus",
    "DecompositionMethod",
    # ids
    "stable_slug", "short_hash", "scope_id_for", "concept_local_id", "topic_id_for", "section_id_for",
    "record_id",
    # models
    "StudyPathScopePlan", "ScopeIdentity", "ScopeIntent", "Classification", "CurriculumGraph",
    "OrderingConstraints", "Edge", "Concept", "ConceptIdentity", "LessonSectionPlan", "Objective",
    "Prereq", "GlossaryTerm", "GoalRequirement", "ConceptSelectionSource", "PlannedGrounding",
    "ScopeProvenance", "SelectionEvidence", "SelectionSourceRegistry", "RequirementConceptMapping",
    "RequirementPrereqMapping", "DecompositionRecord",
    # selection (pure derivation + PR2 exit gate)
    "derive_mapping_status", "build_concept_mapping", "build_prereq_mapping", "aggregate_concept_selection",
    "apply_selection_status", "check_referential_integrity", "uncovered_required_requirements",
    "check_decomposition", "DecompositionCheck", "IntegrityIssue",
    # construction (facets→sections, ordering, bridge guard — PR3)
    "DiscoveredFacet", "consolidate_facets", "resolve_concept_order", "OrderingResult",
    "count_hard_edge_violations", "hard_edges_from_concepts", "bridge_insertion_allowed", "cardinality_of",
]
