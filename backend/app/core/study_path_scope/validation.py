"""PlanningValidator — the Phase-1A invariants §4.1–4.9 + dual-status derivation (STUDY_PATH_SCOPE_SPEC §4,
§7). Pure, no app imports.

Only PLANNING invariants run here (over the ungrounded plan); grounding-minimum / notation / assertion-honesty
are CERTIFICATION invariants and are `not_applicable` until Phase 1B, so they are not emitted at all in 1A.
Every planning invariant is blocking: a single failure → `planning_status = rejected`; otherwise the plan is
`structurally_valid`. certification_status stays `not_started`.
"""
from __future__ import annotations

from typing import Iterable, Optional

from .construction import _excluded, resolve_concept_order, count_hard_edge_violations, hard_edges_from_concepts
from .enums import AuditStatus, AuditType, PlanningStatus, Severity, ValidatorKind
from .ids import record_id, stable_slug
from .models import AuditRecord, StudyPathScopePlan, ValidationReport
from .selection import apply_selection_status

# Minimal domain→topic-type legality (§4.6). Non-CS quantitative domains must not carry coding topics; unknown
# domains permit everything (the validator never invents illegality). The shadow harness can supply a fuller
# table later; the rule that matters now is "no coding topic in a math path".
_CODING_PREFIXES = ("coding", "truncated_coding")
_NON_CODING_DOMAINS = {"math", "mathematics", "physics", "chemistry", "finance", "statistics", "economics"}


def _topic_type_legal(domain: str, topic_type: str) -> bool:
    d = stable_slug(domain)
    tt = stable_slug(topic_type)
    if d in _NON_CODING_DOMAINS and tt.startswith(_CODING_PREFIXES):
        return False
    return True


def _audit(invariant: str, ok: bool, evidence: str = "", *, audit_type: AuditType = AuditType.structural,
           severity: Severity = Severity.blocking, affected_dimension: Optional[str] = None) -> AuditRecord:
    return AuditRecord(
        audit_id=record_id("audit", invariant, evidence or "ok"), invariant=invariant,
        validator=ValidatorKind.planning, audit_type=audit_type, severity=severity,
        status=AuditStatus.passed if ok else AuditStatus.failed, affected_dimension=affected_dimension,
        evidence=evidence)


def run_planning_validator(plan: StudyPathScopePlan) -> ValidationReport:
    """Evaluate §4.1–4.9 and return the report. Applies the derived selection status first (its lone owner)
    so §4.9 reads consistent values. Does not mutate `plan.validation` — see `validate_and_stamp`."""
    apply_selection_status(plan)
    cur = plan.curriculum
    concepts = cur.concepts
    record = cur.decomposition_record
    audits: list[AuditRecord] = []

    concept_ids = {c.identity.concept_id for c in concepts}
    concept_keys = [c.identity.canonical_concept_key for c in concepts]

    # §4.1 coverage: every required requirement covered; no orphan concept.
    from .selection import uncovered_required_requirements
    uncovered = uncovered_required_requirements(record)
    audits.append(_audit("coverage", not uncovered,
                         "" if not uncovered else f"uncovered required requirements: {uncovered}"))
    mapped = {m.concept_id for m in record.concept_coverage}
    orphans = [cid for cid in concept_ids if record.concept_coverage and cid not in mapped]
    audits.append(_audit("no_orphan_concept", not orphans,
                         "" if not orphans else f"orphan concepts: {orphans}"))

    # §4.2 no duplication over (canonical_concept_key, facet) — not a string.
    seen: set[tuple[str, str]] = set()
    dups: list[str] = []
    for c in concepts:
        key = (c.identity.canonical_concept_key, c.identity.facet.value)
        if key in seen:
            dups.append(f"{key}")
        seen.add(key)
    audits.append(_audit("no_duplication", not dups, "" if not dups else f"duplicate (key,facet): {dups}"))

    # §4.3 prereq/concept disjoint; prereqs untaught.
    prereq_keys = {stable_slug(p.id) for p in cur.prerequisites} | {stable_slug(p.name) for p in cur.prerequisites}
    taught = {stable_slug(k) for k in concept_keys}
    overlap = sorted(prereq_keys & taught)
    audits.append(_audit("prereq_concept_disjoint", not overlap,
                         "" if not overlap else f"prereq also taught as a concept: {overlap}"))

    # §4.4 order acyclic (a cycle is reported, never auto-broken); stored order honours hard edges.
    edges = hard_edges_from_concepts(concepts)
    order_result = resolve_concept_order([c.identity.concept_id for c in concepts], edges)
    audits.append(_audit("order_acyclic", order_result.acyclic,
                         "" if order_result.acyclic else f"cycle among: {order_result.cyclic}"))
    stored = cur.resolved_concept_order or order_result.order
    violations = count_hard_edge_violations(stored, edges)
    audits.append(_audit("order_honours_hard_edges", violations == 0,
                         "" if not violations else f"{violations} hard-edge violation(s) in resolved order"))

    # §4.5 glossary ownership: each term once; key_terms disjoint from glossary.
    gterms = [stable_slug(g.term) for g in cur.glossary]
    gdup = sorted({t for t in gterms if gterms.count(t) > 1})
    audits.append(_audit("glossary_unique", not gdup, "" if not gdup else f"glossary term defined twice: {gdup}"))
    gset = set(gterms)
    clash = sorted({stable_slug(t) for c in concepts for t in c.key_terms} & gset)
    audits.append(_audit("glossary_keyterm_disjoint", not clash,
                         "" if not clash else f"key_term also a glossary term: {clash}"))

    # §4.6 domain legality.
    illegal = [f"{c.identity.name}:{c.identity.topic_type}" for c in concepts
               if not _topic_type_legal(plan.classification.domain, c.identity.topic_type)]
    audits.append(_audit("domain_legality", not illegal,
                         "" if not illegal else f"illegal topic_type for {plan.classification.domain}: {illegal}"))

    # §4.7 section structure: split_reason iff multi-section; every objective owned by a non-optional section.
    struct_problems: list[str] = []
    for c in concepts:
        multi = len(c.section_plan) > 1
        if multi and not c.split_reason:
            struct_problems.append(f"{c.identity.name}: multi-section without split_reason")
        if not multi and c.split_reason:
            struct_problems.append(f"{c.identity.name}: split_reason on an atomic concept")
        owning = {oid: s for s in c.section_plan for oid in s.objective_ids}
        for obj in c.learning_objectives:
            s = owning.get(obj.objective_id)
            if s is None:
                struct_problems.append(f"{c.identity.name}: objective {obj.objective_id} maps to no section")
            elif s.optional:
                struct_problems.append(f"{c.identity.name}: objective {obj.objective_id} only in an optional section")
    audits.append(_audit("section_structure", not struct_problems,
                         "" if not struct_problems else "; ".join(struct_problems)))

    # §4.8 exclusions honoured: no rendered section matches an exclusion.
    excl = plan.intent.exclusions
    violated = [f"{c.identity.name}:{s.section_type.value}" for c in concepts for s in c.section_plan
                if _excluded(s.section_type, c.identity.facet, excl)]
    audits.append(_audit("exclusions_honoured", not violated,
                         "" if not violated else f"section violates exclusions {excl}: {violated}"))

    # §4.9 selection honesty: no unresolved ambiguity; no blocking mapping conflict in a consumable plan.
    ambig = record.unresolved_ambiguities
    blocking_health = [c.identity.name for c in concepts if c.mapping_health.value == "contains_blocking"]
    problem = bool(ambig) or bool(blocking_health)
    audits.append(_audit("selection_honesty", not problem,
                         "" if not problem else f"unresolved ambiguities: {ambig}; blocking mappings: {blocking_health}"))

    return ValidationReport(invariants=audits)


def derive_planning_status(report: ValidationReport) -> PlanningStatus:
    """Any blocking failure → rejected; otherwise structurally_valid. (Phase 1A has no `draft` output — the
    plan is either sound or rejected once validated.)"""
    for a in report.invariants:
        if a.status == AuditStatus.failed and a.severity == Severity.blocking:
            return PlanningStatus.rejected
    return PlanningStatus.structurally_valid


def validate_and_stamp(plan: StudyPathScopePlan) -> StudyPathScopePlan:
    """Run the validator, attach the report, and stamp `planning_status`. certification_status stays
    `not_started` in Phase 1A. Mutates and returns the plan."""
    report = run_planning_validator(plan)
    plan.validation = report
    plan.identity.planning_status = derive_planning_status(report)
    return plan


def failed_invariants(report: ValidationReport) -> list[str]:
    return [a.invariant for a in report.invariants if a.status == AuditStatus.failed]
