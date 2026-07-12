"""Tier-2 classification validation (PREREQ_LINKS_SPEC v8 §6.3a). Pure — no app imports.

Runs at the §6.0 Tier-2 decision point, BEFORE lesson generation, on decomposition output only. Any failure →
the caller discards the gated decomposition and uses the legacy plan (§6.6 Tier 2), stamping the structured
`fallback_reason`. This module owns NO lesson/link/frontend concerns (PR1 stays narrowly structural)."""
from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict

from pydantic import BaseModel, Field

from .enums import IN_SCOPE_RULES, Classification, FallbackReason, ScopeRule
from .models import DecompositionClassification


# ── §2.2 resolution normalization (identity resolution only; NOT anchoring) ────────────────────────────────
_APOSTROPHES = {"’": "'", "‘": "'", "`": "'", "´": "'"}   # ’ ‘ ` ´ → '


def normalize_identity(text: str) -> str:
    """Unicode NFC → lowercase → normalize apostrophe variants → collapse whitespace; preserve hyphens (§2.2).

    Used for identity RESOLUTION and for the navigation-set alias-uniqueness check. Deliberately NOT fuzzy:
    hyphens are preserved, so "potential-difference" != "potential difference" unless both are listed aliases."""
    s = unicodedata.normalize("NFC", text or "")
    s = "".join(_APOSTROPHES.get(ch, ch) for ch in s)
    s = s.lower()
    return " ".join(s.split())


class ClassificationFailure(BaseModel):
    reason: FallbackReason
    detail: str = ""


class ClassificationValidationResult(BaseModel):
    ok: bool
    failures: list[ClassificationFailure] = Field(default_factory=list)

    @property
    def fallback_reason(self) -> FallbackReason | None:
        """The primary Tier-2 fallback reason (first failure), for telemetry stamping (§6.7)."""
        return self.failures[0].reason if self.failures else None


def validate_classification(dc: DecompositionClassification) -> ClassificationValidationResult:
    """Run the §6.3a checks over decomposition output. Returns all failures (empty ⇒ the gated plan is usable)."""
    failures: list[ClassificationFailure] = []

    foundation_ids = {f.concept_id for f in dc.in_path_foundations}
    owner_ids = {t.concept_id for t in dc.topic_identities}
    taught_ids = foundation_ids | owner_ids

    # 1. disjointness — a prereq concept_id must not also be a foundation / taught-topic owner (§A11).
    overlap = sorted({p.concept_id for p in dc.assumed_prerequisites} & taught_ids)
    for cid in overlap:
        failures.append(ClassificationFailure(
            reason=FallbackReason.prerequisite_topic_overlap,
            detail=f"concept_id {cid!r} is both an assumed_prerequisite and a taught concept"))

    # 2. every assumed_prerequisite has a non-empty target_goal (§A15).
    for p in dc.assumed_prerequisites:
        if not (p.target_goal or "").strip():
            failures.append(ClassificationFailure(
                reason=FallbackReason.missing_target_goal,
                detail=f"assumed_prerequisite {p.concept_id!r} has an empty target_goal"))

    # 3. uniqueness (§1.1b): topic_id unique; two owners for one concept_id → duplicate_concept_ownership (§A37);
    #    AssumedPrerequisite.concept_id / InPathFoundation.concept_id unique → duplicate_identity_key.
    for topic_id, n in Counter(t.topic_id for t in dc.topic_identities).items():
        if n > 1:
            failures.append(ClassificationFailure(
                reason=FallbackReason.duplicate_identity_key,
                detail=f"topic_id {topic_id!r} appears in {n} TopicConceptIdentity records"))
    for cid, n in Counter(t.concept_id for t in dc.topic_identities).items():
        if n > 1:
            failures.append(ClassificationFailure(
                reason=FallbackReason.duplicate_concept_ownership,
                detail=f"concept_id {cid!r} is owned by {n} teaching topics"))
    for label, ids in (("assumed_prerequisite", [p.concept_id for p in dc.assumed_prerequisites]),
                       ("in_path_foundation", [f.concept_id for f in dc.in_path_foundations])):
        for cid, n in Counter(ids).items():
            if n > 1:
                failures.append(ClassificationFailure(
                    reason=FallbackReason.duplicate_identity_key,
                    detail=f"{label} concept_id {cid!r} appears {n} times"))

    # 4. owner resolvability — every review_earlier_topic reference resolves to EXACTLY ONE owner (§A41: a
    #    non-owning synthesis/review topic having no identity is fine; the failure is 0 or >1 owners).
    owner_count = Counter(t.concept_id for t in dc.topic_identities)
    for cid in dc.review_referenced_concept_ids:
        if owner_count.get(cid, 0) != 1:
            failures.append(ClassificationFailure(
                reason=FallbackReason.missing_owner_for_review,
                detail=f"review reference {cid!r} resolves to {owner_count.get(cid, 0)} owners (need exactly 1)"))

    # 5. navigation-set normalized-alias uniqueness — one normalized surface must map to ≤1 navigation concept_id
    #    (glossary overlap is allowed; navigation wins, §2.3). Same concept under multiple surfaces is fine.
    surface_to_concepts: dict[str, set[str]] = defaultdict(set)
    for t in dc.topic_identities:
        for surface in (t.canonical_name, *t.aliases):
            surface_to_concepts[normalize_identity(surface)].add(t.concept_id)
    for p in dc.assumed_prerequisites:
        for surface in (p.canonical_name, *p.aliases):
            surface_to_concepts[normalize_identity(surface)].add(p.concept_id)
    for surface, cids in surface_to_concepts.items():
        if len(cids) > 1:
            failures.append(ClassificationFailure(
                reason=FallbackReason.ambiguous_navigation_identity,
                detail=f"normalized surface {surface!r} maps to {len(cids)} navigation concept_ids: {sorted(cids)}"))

    # 6. scope_rule validity per variant (§6.3a).
    for p in dc.assumed_prerequisites:
        if p.scope_rule != ScopeRule.recognition_only_fallback:
            failures.append(ClassificationFailure(
                reason=FallbackReason.invalid_scope_rule,
                detail=f"assumed_prerequisite {p.concept_id!r} scope_rule {p.scope_rule.value!r} "
                       f"!= recognition_only_fallback"))
    for f in dc.in_path_foundations:
        if f.scope_rule not in IN_SCOPE_RULES:
            failures.append(ClassificationFailure(
                reason=FallbackReason.invalid_scope_rule,
                detail=f"in_path_foundation {f.concept_id!r} scope_rule {f.scope_rule.value!r} is not an in-scope rule"))

    return ClassificationValidationResult(ok=not failures, failures=failures)
