"""Enums for the StudyPathScope (STUDY_PATH_SCOPE_SPEC v3.2, Phase 1A). Pure — no app imports."""
from __future__ import annotations

from enum import Enum


class PlanningStatus(str, Enum):          # §7 — gates the plan
    draft = "draft"
    structurally_valid = "structurally_valid"
    rejected = "rejected"


class CertificationStatus(str, Enum):     # §7 — gates the facts (always not_started in Phase 1A)
    not_started = "not_started"
    partial = "partial"
    complete = "complete"
    complete_with_degradation = "complete_with_degradation"
    failed = "failed"


class SourceAlignmentMode(str, Enum):     # §6.4
    canonical_truth = "canonical_truth"
    course_faithful = "course_faithful"
    compare_and_correct = "compare_and_correct"


class Facet(str, Enum):                   # §1.4 — identity facet; dedup reasons over (canonical_key, facet)
    core = "core"
    method = "method"
    derivation = "derivation"
    correctness = "correctness"
    implementation = "implementation"
    application = "application"


class SectionType(str, Enum):             # §1.6 — instructional role, aligned to the card charter
    foundation = "foundation"
    intuition = "intuition"
    mechanism = "mechanism"
    walkthrough = "walkthrough"
    derivation = "derivation"
    proof = "proof"
    implementation = "implementation"
    application = "application"
    comparison = "comparison"
    complexity = "complexity"
    edge_cases = "edge_cases"


class CardinalityPolicy(str, Enum):       # §1.6 — DERIVED from section_plan length, never authored
    atomic = "atomic"
    multi_section = "multi_section"


class Grammar(str, Enum):                 # §1.3 — trace-grammar variant (planned in 1A, grounded in 1B)
    formula = "formula"
    derivation = "derivation"
    algorithm = "algorithm"
    operation = "operation"
    proof = "proof"
    mechanism = "mechanism"
    numerical = "numerical"
    table = "table"
    comparison = "comparison"
    general = "general"


class PlannedGrammarStatus(str, Enum):    # §12 code-time — a Phase-1A grammar is provisional, not verified
    proposed = "proposed"
    catalog_supported = "catalog_supported"
    confirmed = "confirmed"                # "planning classification confirmed", NOT "grounding verified"


class SelectionSourceRole(str, Enum):     # §1.4 — why a source justified a curriculum decision
    scope = "scope"
    prerequisite = "prerequisite"
    dependency_selection = "dependency_selection"


class SelectionStatus(str, Enum):         # §1.4 — derived per concept
    confirmed = "confirmed"
    supported = "supported"
    ambiguous = "ambiguous"
    unsupported = "unsupported"


class MappingHealth(str, Enum):           # §1.4 — derived per concept (parallel to selection_status)
    clean = "clean"
    contains_warning = "contains_warning"
    contains_blocking = "contains_blocking"
