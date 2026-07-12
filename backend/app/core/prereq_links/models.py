"""Typed contracts for prerequisite-links (PREREQ_LINKS_SPEC v8 §1). Pure — pydantic + stdlib only.

The two foundational-dependency variants (§1.1a/§1.2) are a discriminated union on `classification`, so
`concept_id`/`canonical_name`/`aliases` have ONE source of truth. `concept_id` is the single identity key
everywhere (there is no separate `prerequisite_id`)."""
from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, Field

from .enums import Classification, Provenance, ScopeRule


class InPathFoundation(BaseModel):            # §1.1a — required AND in scope; may emit a teaching topic
    classification: Classification = Classification.in_path_foundation
    concept_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)      # resolution-only (§2.4)
    topic_id: Optional[str] = None                        # the teaching topic it maps to, once ordered
    scope_rule: ScopeRule                                 # §3.1 — must be an IN_SCOPE_RULES value (§6.3a)
    scope_rationale: str = ""
    provenance: Provenance = Provenance.decomposition


class AssumedPrerequisite(BaseModel):         # §1.2 — required but OUT of scope; delivered by a link
    classification: Classification = Classification.assumed_prerequisite
    concept_id: str                                       # the single identity key (no separate prerequisite_id)
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)      # resolution-only (§2.4)
    display_text: str                                     # learner-facing prereq-card bullet label
    target_goal: str                                      # SCOPED goal for the on-click path (built upstream, §3)
    why_required: Optional[str] = None
    scope_rule: ScopeRule = ScopeRule.recognition_only_fallback   # here always the fallback (§6.3a)
    scope_rationale: str = ""
    provenance: Provenance = Provenance.decomposition


# §1.1a — the discriminated union. (Kept as a plain Union; callers discriminate on `.classification`.)
FoundationalDependency = Union[InPathFoundation, AssumedPrerequisite]


class TopicConceptIdentity(BaseModel):        # §1.1b — identity for every CONCEPT-OWNING teaching topic
    topic_id: str
    topic_index: int                                      # position in topic order → the "taught EARLIER" test
    concept_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)      # resolution-only (§2.4)


class PrerequisitePrioritySignals(BaseModel): # §2.7 — machine-readable inputs to priority_order
    concept_id: str
    is_direct_goal_dependency: bool = False
    dependent_topic_count: int = 0
    first_use_topic_index: int = 0
    provenance: Provenance = Provenance.decomposition


class PrerequisiteScopeWarning(BaseModel):    # §2.7 — structured over-limit warning (internal, v1)
    code: str = "too_many_assumed_prerequisites"
    count: int
    threshold: int
    priority_order: list[str] = Field(default_factory=list)   # concept_ids, most-important-first
    message: str = ""


class DecompositionClassification(BaseModel):
    """The decomposition output this feature validates (§6.0 Tier-2 input). Not the full decomposition —
    just the identity/scope surface the classification validator (§6.3a) reasons over."""
    in_path_foundations: list[InPathFoundation] = Field(default_factory=list)
    assumed_prerequisites: list[AssumedPrerequisite] = Field(default_factory=list)
    topic_identities: list[TopicConceptIdentity] = Field(default_factory=list)   # concept-owning topics only
    # concept_ids referenced by review_earlier_topic candidates (must each resolve to exactly one owner, §6.3a).
    review_referenced_concept_ids: list[str] = Field(default_factory=list)
    scope_warning: Optional[PrerequisiteScopeWarning] = None
