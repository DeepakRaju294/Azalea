"""Shadow telemetry — neutral counts/distances between a scope plan and the current pipeline's output
(STUDY_PATH_SCOPE_SPEC §10). Pure, no app imports.

Phase 1A emits the plan in SHADOW and diffs it against today's output. The current pipeline is what the scope
exists to fix, so differences are NOT automatically regressions — metrics are neutral counts, and each diff is
CLASSIFIED (`same | scope_improvement | scope_regression | needs_review`), never assumed a regression.
`precision/recall` need a gold reference, so they are reserved for the labelled fixtures — not computed here.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .construction import count_hard_edge_violations, hard_edges_from_concepts
from .enums import DiffClass
from .models import StudyPathScopePlan


class ShadowBaseline(BaseModel):
    """The current pipeline's output, expressed in the scope's canonical vocabulary (the harness maps today's
    topics → canonical keys). Kept minimal — only what the neutral metrics compare."""
    concept_keys: list[str] = Field(default_factory=list)
    prereq_ids: list[str] = Field(default_factory=list)
    concept_order: list[str] = Field(default_factory=list)          # canonical keys, in taught order
    topic_types: dict[str, str] = Field(default_factory=dict)       # canonical key → topic_type


class ShadowMetrics(BaseModel):
    concept_added_count: int = 0
    concept_removed_count: int = 0
    concept_overlap_ratio: float = 1.0
    prereq_added_count: int = 0
    prereq_removed_count: int = 0
    order_exact_match: bool = True
    order_pairwise_distance: int = 0
    hard_edge_violation_count: int = 0                              # load-bearing signal (§10, §12)
    topic_type_diff_count: int = 0
    orphan_concept_count: int = 0
    unresolved_ambiguity_count: int = 0
    semantic_repair_count: int = 0
    diff_class: DiffClass = DiffClass.same


def _pairwise_distance(a: list[str], b: list[str]) -> int:
    """Discordant ordered pairs over the shared items — how far apart the two orderings are, independent of
    which items each contains."""
    shared = [x for x in a if x in set(b)]
    pos_b = {x: i for i, x in enumerate(b)}
    discordant = 0
    for i in range(len(shared)):
        for j in range(i + 1, len(shared)):
            if pos_b[shared[i]] > pos_b[shared[j]]:
                discordant += 1
    return discordant


def shadow_diff(plan: StudyPathScopePlan, baseline: ShadowBaseline) -> ShadowMetrics:
    cur = plan.curriculum
    concepts = cur.concepts
    by_id = {c.identity.concept_id: c for c in concepts}
    scope_keys = [c.identity.canonical_concept_key for c in concepts]
    scope_set, base_set = set(scope_keys), set(baseline.concept_keys)
    union = scope_set | base_set

    # scope order → canonical keys, honouring resolved_concept_order when present.
    ordered_ids = cur.resolved_concept_order or [c.identity.concept_id for c in concepts]
    scope_order_keys = [by_id[i].identity.canonical_concept_key for i in ordered_ids if i in by_id]

    scope_prereqs = {p.id for p in cur.prerequisites}
    base_prereqs = set(baseline.prereq_ids)

    scope_types = {c.identity.canonical_concept_key: c.identity.topic_type for c in concepts}
    type_diffs = sum(1 for k in scope_set & base_set
                     if baseline.topic_types.get(k) and scope_types.get(k) != baseline.topic_types[k])

    mapped = {m.concept_id for m in cur.decomposition_record.concept_coverage}
    orphans = sum(1 for cid in by_id if cur.decomposition_record.concept_coverage and cid not in mapped)

    edges = hard_edges_from_concepts(concepts)
    hard_violations = count_hard_edge_violations(ordered_ids, edges)

    m = ShadowMetrics(
        concept_added_count=len(scope_set - base_set),
        concept_removed_count=len(base_set - scope_set),
        concept_overlap_ratio=(len(scope_set & base_set) / len(union)) if union else 1.0,
        prereq_added_count=len(scope_prereqs - base_prereqs),
        prereq_removed_count=len(base_prereqs - scope_prereqs),
        order_exact_match=(scope_order_keys == baseline.concept_order) if baseline.concept_order else True,
        order_pairwise_distance=_pairwise_distance(scope_order_keys, baseline.concept_order),
        hard_edge_violation_count=hard_violations,
        topic_type_diff_count=type_diffs,
        orphan_concept_count=orphans,
        unresolved_ambiguity_count=len(cur.decomposition_record.unresolved_ambiguities),
        semantic_repair_count=sum(1 for r in plan.validation.repair_history if r.repair_class == "semantic"),
    )
    m.diff_class = classify_shadow_diff(m)
    return m


def classify_shadow_diff(m: ShadowMetrics) -> DiffClass:
    """Coarse, conservative classification. A hard-edge violation or an orphan/ambiguity is the one thing that
    is unambiguously worse (a broken plan); pure set/order differences are `needs_review`, because the current
    pipeline is not ground truth. Identical structure is `same`."""
    if m.hard_edge_violation_count > 0 or m.orphan_concept_count > 0 or m.unresolved_ambiguity_count > 0:
        return DiffClass.scope_regression
    if (m.concept_added_count == 0 and m.concept_removed_count == 0 and m.prereq_added_count == 0
            and m.prereq_removed_count == 0 and m.topic_type_diff_count == 0 and m.order_exact_match):
        return DiffClass.same
    return DiffClass.needs_review
