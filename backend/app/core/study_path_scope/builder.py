"""Plan builder — decomposition output → a validated StudyPathScopePlan (STUDY_PATH_SCOPE_SPEC §3, §11).

This is the Phase-1A capstone: it wires the PR1–PR4 pieces into one callable. It consumes a lightweight,
app-agnostic `DecompositionInput` (which the live pipeline's Engine-B output maps onto — that mapping lives in
a service module, NOT here, so this package stays import-pure) and returns a `StudyPathScopePlan` that has been
facet-consolidated, ordered, mapping-evidenced, selection-stamped, and planning-validated.

No LLM, no app imports — deterministic from its input, so identical decomposition rebuilds an identical plan.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .construction import DiscoveredFacet, consolidate_facets, hard_edges_from_concepts, resolve_concept_order
from .enums import ConceptRelation, Facet, SelectionMethod
from .ids import scope_id_for
from .models import (
    Classification, Concept, ConceptSelectionSource, CurriculumGraph, DecompositionRecord, GoalRequirement,
    Objective, OrderingConstraints, Prereq, ScopeIdentity, ScopeIntent, SelectionEvidence,
    SelectionSourceRegistry, StudyPathScopePlan,
)
from .selection import apply_selection_status, build_concept_mapping, build_prereq_mapping
from .validation import validate_and_stamp


class ConceptDraft(BaseModel):
    """One decomposed concept (or one facet of a concept — drafts sharing a canonical key are consolidated
    into a single concept with sections). Curriculum-level only; no grounding."""
    canonical_concept_key: str
    name: str
    topic_type: str
    facet: Facet = Facet.core
    aliases: list[str] = Field(default_factory=list)
    objectives: list[Objective] = Field(default_factory=list)
    covers_requirements: list[str] = Field(default_factory=list)     # requirement_ids served DIRECTLY
    bridges_requirements: list[str] = Field(default_factory=list)    # requirement_ids served as a BRIDGE
    prerequisite_keys: list[str] = Field(default_factory=list)       # canonical keys of prerequisite CONCEPTS
    selection_method: SelectionMethod = SelectionMethod.model_consensus
    evidence_ref: str = ""                                           # into the SelectionSourceRegistry


class PrereqDraft(BaseModel):
    id: str
    name: str
    anchor: str = ""
    covers_requirements: list[str] = Field(default_factory=list)
    selection_method: SelectionMethod = SelectionMethod.model_consensus
    evidence_ref: str = ""


class DecompositionInput(BaseModel):
    goal: str
    domain: str
    source_revision: str = ""
    target_depth: str = "working"
    exclusions: list[str] = Field(default_factory=list)
    requirements: list[GoalRequirement] = Field(default_factory=list)
    concepts: list[ConceptDraft] = Field(default_factory=list)
    prereqs: list[PrereqDraft] = Field(default_factory=list)
    selection_sources: list[ConceptSelectionSource] = Field(default_factory=list)
    mention_order: list[str] = Field(default_factory=list)          # canonical keys, goal/user mention order
    source_order: list[str] = Field(default_factory=list)           # canonical keys, source order
    unresolved_ambiguities: list[str] = Field(default_factory=list)  # e.g. "'expected value' discrete|continuous"


def build_plan(inp: DecompositionInput) -> StudyPathScopePlan:
    """Build and validate a plan from decomposition output. The result carries its own `planning_status`
    (structurally_valid or rejected) and a ValidationReport — the caller inspects those; a rejected plan is
    still returned (with its failing audits) rather than raised, so shadow telemetry can record it."""
    registry = SelectionSourceRegistry()
    for src in inp.selection_sources:
        registry.add(src)

    # 1) group drafts by canonical key → one consolidated concept each (facets become sections, §12).
    drafts_by_key: dict[str, list[ConceptDraft]] = {}
    order_seen: list[str] = []
    for d in inp.concepts:
        if d.canonical_concept_key not in drafts_by_key:
            drafts_by_key[d.canonical_concept_key] = []
            order_seen.append(d.canonical_concept_key)
        drafts_by_key[d.canonical_concept_key].append(d)

    concepts: list[Concept] = []
    concept_id_by_key: dict[str, str] = {}
    for key in order_seen:
        drafts = drafts_by_key[key]
        facets = [DiscoveredFacet(facet=d.facet, name=d.name, topic_type=d.topic_type,
                                  objectives=d.objectives, aliases=d.aliases) for d in drafts]
        concept, _sections = consolidate_facets(key, facets, target_depth=inp.target_depth,
                                                exclusions=inp.exclusions)
        concepts.append(concept)
        concept_id_by_key[key] = concept.identity.concept_id

    # 2) prerequisite edges between concepts (alias/facet consolidation already ran, per §12 ordering).
    for key in order_seen:
        pre_ids = [concept_id_by_key[pk] for d in drafts_by_key[key] for pk in d.prerequisite_keys
                   if pk in concept_id_by_key and concept_id_by_key[pk] != concept_id_by_key[key]]
        if pre_ids:
            concept = next(c for c in concepts if c.identity.concept_id == concept_id_by_key[key])
            concept.prerequisite_concept_ids = sorted(set(pre_ids))

    # 3) deterministic ordering — the owned derived value (§6.3); readers consume it, never re-sort.
    edges = hard_edges_from_concepts(concepts)
    mention_ids = [concept_id_by_key[k] for k in inp.mention_order if k in concept_id_by_key]
    source_ids = [concept_id_by_key[k] for k in inp.source_order if k in concept_id_by_key]
    ordering = resolve_concept_order([c.identity.concept_id for c in concepts], edges,
                                     mention_order=mention_ids, source_order=source_ids)

    # 4) evidenced requirement mappings (one owner: selection.build_*_mapping).
    prereqs = [Prereq(id=p.id, name=p.name, anchor=p.anchor) for p in inp.prereqs]
    concept_cov = []
    for key in order_seen:
        cid = concept_id_by_key[key]
        for d in drafts_by_key[key]:
            for rid in d.covers_requirements:
                concept_cov.append(_concept_map(rid, cid, ConceptRelation.direct, d, key))
            for rid in d.bridges_requirements:
                concept_cov.append(_concept_map(rid, cid, ConceptRelation.bridge, d, key))
    prereq_cov = []
    for p in inp.prereqs:
        for rid in p.covers_requirements:
            ev = [SelectionEvidence.create(method=p.selection_method, requirement_id=rid, target_id=p.id,
                                           evidence_ref=p.evidence_ref)]
            prereq_cov.append(build_prereq_mapping(requirement_id=rid, prereq_id=p.id, evidence=ev))

    record = DecompositionRecord(goal_claims=list(inp.requirements), concept_coverage=concept_cov,
                                 prereq_coverage=prereq_cov,
                                 unresolved_ambiguities=list(inp.unresolved_ambiguities))

    plan = StudyPathScopePlan(
        identity=ScopeIdentity(scope_id=scope_id_for(inp.goal, inp.domain, inp.source_revision),
                               source_revision=inp.source_revision),
        intent=ScopeIntent(goal=inp.goal, goal_requirements=list(inp.requirements),
                            target_depth=inp.target_depth, exclusions=list(inp.exclusions)),
        classification=Classification(domain=inp.domain),
        selection_sources=registry,
        curriculum=CurriculumGraph(
            prerequisites=prereqs, concepts=concepts,
            ordering_constraints=OrderingConstraints(hard_edges=edges),
            resolved_concept_order=ordering.order, decomposition_record=record),
    )

    apply_selection_status(plan)                 # write derived selection_status / mapping_health (lone owner)
    validate_and_stamp(plan)                     # run PlanningValidator §4.1–4.9, stamp planning_status
    return plan


def _concept_map(requirement_id: str, concept_id: str, relation: ConceptRelation, draft: ConceptDraft,
                 key: str):
    ev = [SelectionEvidence.create(method=draft.selection_method, requirement_id=requirement_id,
                                   target_id=concept_id, evidence_ref=draft.evidence_ref)]
    return build_concept_mapping(requirement_id=requirement_id, concept_id=concept_id, relation=relation,
                                 evidence=ev)
