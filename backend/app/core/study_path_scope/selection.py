"""Selection derivation — the ONE owner of mapping/selection status (STUDY_PATH_SCOPE_SPEC §1.4, §11, §12).

Pure functions, no app imports. Everything derived from evidence is computed here exactly once so validators
and serializers never re-derive it independently (§12 "ONE pure, table-tested function"):

    SelectionEvidence[]           → RequirementConceptMapping.status   (derive_mapping_status)
    RequirementConceptMapping[]   → Concept.selection_status + mapping_health   (aggregate_concept_selection)

Plus the PR2 exit gate: referential integrity (evidence_ref / concept_id / prereq_id / requirement_id all
resolve) and full requirement coverage (every required GoalRequirement is covered by a real concept mapping).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .enums import (
    ConceptRelation, EvidenceStatus, MappingHealth, MappingStatus, SelectionMethod, SelectionStatus,
)
from .ids import record_id
from .models import (
    Concept, DecompositionRecord, RequirementConceptMapping, RequirementPrereqMapping, SelectionEvidence,
    SelectionSourceRegistry, StudyPathScopePlan,
)

# Ranked strength (§1.4): explicitly named in goal / user-confirmed > source structure > trusted
# curriculum/catalog > model inference. model_consensus is the weakest — a SIGNAL, never "verified".
_METHOD_RANK: dict[SelectionMethod, int] = {
    SelectionMethod.explicit_goal: 5,
    SelectionMethod.user_confirmed: 5,
    SelectionMethod.source_heading: 4,
    SelectionMethod.source_span: 4,
    SelectionMethod.curriculum_graph: 3,
    SelectionMethod.concept_catalog: 3,
    SelectionMethod.model_consensus: 1,
}


# --- evidence[] → one mapping's status --------------------------------------------------------------------

def derive_mapping_status(evidence: Iterable[SelectionEvidence]) -> MappingStatus:
    """A single mapping's status from its evidence. A conflict dominates (blocking); otherwise the strongest
    SUPPORTING method decides. Empty/only-weak evidence is `ambiguous`, never silently confirmed."""
    evidence = list(evidence)
    if any(e.status == EvidenceStatus.conflicting for e in evidence):
        return MappingStatus.conflicting
    supporting = [e for e in evidence if e.status == EvidenceStatus.supporting]
    strongest = max((_METHOD_RANK.get(e.method, 0) for e in supporting), default=0)
    if strongest >= 5:
        return MappingStatus.confirmed
    if strongest >= 3:
        return MappingStatus.supported
    return MappingStatus.ambiguous          # only model inference, equivocal, or no support


# --- mapping builders (compute id + derived status in one place) ------------------------------------------

def build_concept_mapping(*, requirement_id: str, concept_id: str,
                          relation: ConceptRelation = ConceptRelation.direct,
                          evidence: Iterable[SelectionEvidence] = ()) -> RequirementConceptMapping:
    evidence = list(evidence)
    return RequirementConceptMapping(
        mapping_id=record_id("mapping", requirement_id, "concept", concept_id, relation),
        requirement_id=requirement_id, concept_id=concept_id, relation=relation,
        evidence=evidence, status=derive_mapping_status(evidence))


def build_prereq_mapping(*, requirement_id: str, prereq_id: str,
                         evidence: Iterable[SelectionEvidence] = ()) -> RequirementPrereqMapping:
    evidence = list(evidence)
    return RequirementPrereqMapping(
        mapping_id=record_id("mapping", requirement_id, "prereq", prereq_id),
        requirement_id=requirement_id, prereq_id=prereq_id,
        evidence=evidence, status=derive_mapping_status(evidence))


# --- mappings[] → one concept's (selection_status, mapping_health) ----------------------------------------

# existence justification: the STRONGEST inclusion mapping wins.
_SELECTION_RANK = {MappingStatus.confirmed: 3, MappingStatus.supported: 2, MappingStatus.ambiguous: 1}
_RANK_TO_STATUS = {3: SelectionStatus.confirmed, 2: SelectionStatus.supported, 1: SelectionStatus.ambiguous}


def aggregate_concept_selection(
        mappings: Iterable[RequirementConceptMapping]) -> tuple[SelectionStatus, MappingHealth]:
    """Concept-level aggregate (§1.4). Two orthogonal signals from the SAME mappings, exposed together:
      - selection_status: the strongest inclusion mapping justifies existence (a conflict alone justifies none).
      - mapping_health: any conflict → blocking; any ambiguous → warning — a conflict "still counts" even when
        another mapping confirms existence.
    """
    mappings = list(mappings)
    best = max((_SELECTION_RANK.get(m.status, 0) for m in mappings), default=0)
    selection_status = _RANK_TO_STATUS.get(best, SelectionStatus.unsupported)

    if any(m.status == MappingStatus.conflicting for m in mappings):
        health = MappingHealth.contains_blocking
    elif any(m.status == MappingStatus.ambiguous for m in mappings):
        health = MappingHealth.contains_warning
    else:
        health = MappingHealth.clean
    return selection_status, health


def apply_selection_status(plan: StudyPathScopePlan) -> StudyPathScopePlan:
    """Write each concept's derived `selection_status`/`mapping_health` from its concept mappings. Mutates in
    place (and returns the plan). The lone owner of those two fields (§11) — readers never recompute them."""
    by_concept: dict[str, list[RequirementConceptMapping]] = {}
    for m in plan.curriculum.decomposition_record.concept_coverage:
        by_concept.setdefault(m.concept_id, []).append(m)
    for concept in plan.curriculum.concepts:
        status, health = aggregate_concept_selection(by_concept.get(concept.identity.concept_id, []))
        concept.selection_status = status
        concept.mapping_health = health
    return plan


# --- PR2 exit gate: referential integrity + full requirement coverage -------------------------------------

@dataclass(frozen=True)
class IntegrityIssue:
    kind: str        # dangling_evidence_ref | missing_concept | missing_prereq | missing_requirement
    detail: str


def check_referential_integrity(record: DecompositionRecord, registry: SelectionSourceRegistry,
                                concept_ids: Iterable[str], prereq_ids: Iterable[str]) -> list[IntegrityIssue]:
    """Every mapping must target a real requirement/concept/prereq, and every evidence_ref must resolve to a
    registered source (§12). Deleting a selection source therefore surfaces as a dangling_evidence_ref."""
    concept_ids, prereq_ids = set(concept_ids), set(prereq_ids)
    requirement_ids = {r.requirement_id for r in record.goal_claims}
    issues: list[IntegrityIssue] = []

    def _check_evidence(evidence: list[SelectionEvidence], where: str) -> None:
        for e in evidence:
            if e.evidence_ref and e.evidence_ref not in registry:
                issues.append(IntegrityIssue("dangling_evidence_ref",
                                             f"{where}: evidence {e.evidence_id} → {e.evidence_ref}"))

    for m in record.concept_coverage:
        if m.requirement_id not in requirement_ids:
            issues.append(IntegrityIssue("missing_requirement", f"concept mapping {m.mapping_id} → {m.requirement_id}"))
        if m.concept_id not in concept_ids:
            issues.append(IntegrityIssue("missing_concept", f"mapping {m.mapping_id} → {m.concept_id}"))
        _check_evidence(m.evidence, f"concept mapping {m.mapping_id}")
    for m in record.prereq_coverage:
        if m.requirement_id not in requirement_ids:
            issues.append(IntegrityIssue("missing_requirement", f"prereq mapping {m.mapping_id} → {m.requirement_id}"))
        if m.prereq_id not in prereq_ids:
            issues.append(IntegrityIssue("missing_prereq", f"mapping {m.mapping_id} → {m.prereq_id}"))
        _check_evidence(m.evidence, f"prereq mapping {m.mapping_id}")
    return issues


# a requirement is "covered" only by a non-conflicting DIRECT/BRIDGE concept mapping or a prereq mapping;
# enrichment is extra depth and never discharges a required goal (§1.4).
_COVERING_RELATIONS = {ConceptRelation.direct, ConceptRelation.bridge}


def uncovered_required_requirements(record: DecompositionRecord) -> list[str]:
    covered: set[str] = set()
    for m in record.concept_coverage:
        if m.relation in _COVERING_RELATIONS and m.status != MappingStatus.conflicting:
            covered.add(m.requirement_id)
    for m in record.prereq_coverage:
        if m.status != MappingStatus.conflicting:
            covered.add(m.requirement_id)
    return [r.requirement_id for r in record.goal_claims if r.required and r.requirement_id not in covered]


@dataclass(frozen=True)
class DecompositionCheck:
    integrity_issues: list[IntegrityIssue]
    uncovered_requirements: list[str]

    @property
    def ok(self) -> bool:
        return not self.integrity_issues and not self.uncovered_requirements


def check_decomposition(plan: StudyPathScopePlan) -> DecompositionCheck:
    """The PR2 exit gate over a whole plan: referential integrity + full required-requirement coverage."""
    record = plan.curriculum.decomposition_record
    concept_ids = [c.identity.concept_id for c in plan.curriculum.concepts]
    prereq_ids = [p.id for p in plan.curriculum.prerequisites]
    return DecompositionCheck(
        integrity_issues=check_referential_integrity(record, plan.selection_sources, concept_ids, prereq_ids),
        uncovered_requirements=uncovered_required_requirements(record))
