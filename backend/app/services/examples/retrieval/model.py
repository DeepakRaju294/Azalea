"""Frozen §5.1 Phase-1A instance-only schemas + evidence/assurance types (RETRIEVAL_GROUNDED_EXAMPLE_SPEC).

These are the [FREEZE FOR 1A] dataclasses. Broad/relationship/catalog types are deliberately NOT here — they
land at their sub-gates. Everything is frozen (immutable) so evidence and identities cannot be mutated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Literal, Mapping, Union

StructuredValue = Union[str, int, float, bool]

# ---- errors (two DIFFERENT jobs — evidence corruption vs policy ineligibility, 5th-review small-point 3) ----
class EvidenceIntegrityError(RuntimeError):
    """Evidence corruption/binding failure — a valid decision references missing/revoked/cross-run/mismatched
    evidence, or the evidence does not earn the level."""


class ShippingPolicyError(RuntimeError):
    """A VALID assurance that the active shipping policy does not permit to ship. Not an integrity failure."""


# ---- verifier / evidence ----
VerifierName = Literal["reproduction_checker", "executor", "comparison_engine", "dimensional_checker",
                       "span_grounder", "trace_validator"]
EvidenceCheck = Literal["source_span_match", "source_independence", "dimensional_balance",
                        "published_answer_reproduction", "deterministic_execution",
                        "independent_endpoint_agreement", "trace_consistency"]


@dataclass(frozen=True)
class VerifierDependency:
    """Binds BOTH the verifier binary AND the meaning of 'confirm' (the check contract)."""
    verifier_version: str
    check_contract_version: str


@dataclass(frozen=True)
class EvidenceRecord:
    """Immutable record of one check over one artifact. Revocation is a SEPARATE record (EvidenceRevocation)."""
    evidence_id: str
    check: EvidenceCheck
    status: Literal["confirm", "refute", "indecisive", "unsupported"]
    subject_fingerprint: str
    verifier_name: VerifierName
    verifier_version: str
    check_contract_version: str
    run_id: str
    evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceRevocation:
    evidence_id: str
    revoked_at: str
    reason: str
    incident_id: str


# ---- assurance (instance-only) ----
class AssuranceStrength(IntEnum):
    GUIDED = 0
    PROVISIONAL = 10
    SOURCE_ATTRIBUTED = 20
    ANSWER_ANCHORED = 25
    CORROBORATED = 30
    REPRODUCED_INSTANCE = 40
    EXECUTION_VERIFIED = 50
    # human review is DELIBERATELY not on this axis (orthogonal, §5)


# minimal for 1A: answer_anchored joins with the legacy fallback; verified_execution with 1B/Mode B.
InstanceAssuranceLevel = Literal["verified_reproduction", "provisional", "guided"]


@dataclass(frozen=True)
class InstanceAssuranceProfile:
    """Instance-only profile — no relationship/review states, so invalid combinations are unrepresentable."""
    automated_strength: AssuranceStrength
    computational_check: Literal["none", "reproduction"]


@dataclass(frozen=True)
class InstanceAssuranceDecision:
    assurance_id: str
    run_id: str
    subject_kind: Literal["published_instance", "generated_instance"]
    level: InstanceAssuranceLevel
    profile: InstanceAssuranceProfile
    subject_fingerprint: str
    assurance_policy_version: str
    verification_dependencies: Mapping[VerifierName, VerifierDependency]
    evidence_ids: tuple[str, ...]


# ---- candidate payload (instance) ----
@dataclass(frozen=True)
class AnswerComparison:
    """Normalized quantity/comparison semantics that travel WITH the answer (not a bare unit string)."""
    kind: Literal["exact_numeric", "relative_tolerance", "absolute_tolerance", "symbolic_equivalence",
                  "unordered_set", "interval", "textual_enum", "vector", "complex", "angle_mod_2pi"]
    quantity_kind: str
    unit_dimension: str
    unit_semantics: Literal["absolute", "difference", "ratio", "dimensionless"]
    allowed_units: tuple[str, ...] = ()
    coordinate_frame: str | None = None
    tolerance: str | None = None          # Decimal-as-str
    rounding_rule: str | None = None      # a REQUIRED rounding rule -> part of answer_semantics identity


@dataclass(frozen=True)
class InstanceAssumption:
    """Frozen minimal AST-shaped assumption (data model only — no extraction/registry/satisfiability yet)."""
    key: str
    value: StructuredValue


@dataclass(frozen=True)
class PublishedInstance:
    problem_statement: str
    inputs: tuple[tuple[str, StructuredValue], ...]   # (name, value) pairs
    target: str                                        # the quantity being solved for
    published_answer: str
    comparison: AnswerComparison
    assumptions: tuple[InstanceAssumption, ...] = ()


# ---- source provenance (curated local corpus — no live egress; §6) ----
@dataclass(frozen=True)
class SourceSnapshot:
    content_hash: str                 # immutable identity of the exact ingested bytes
    retrieved_at: str
    retrieval_method_version: str
    license_policy_version: str


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    publisher_id: str
    corpus_family: str                # independence group (V2 needs 2 distinct; N/A for a single published instance)
    tier: Literal["textbook", "reference", "encyclopedic", "other"]
    reuse_policy: Literal["internal_verification_only", "short_excerpt_allowed",
                          "derived_example_allowed", "full_republication_allowed"]
    snapshot: SourceSnapshot


@dataclass(frozen=True)
class CandidateArtifact:
    """A retrieved candidate. Phase 1B = published_instance only (curated corpus); relationship/illustrative
    kinds arrive at 1D/1C."""
    artifact_id: str
    concept_key: str
    payload: PublishedInstance
    sources: tuple[SourceRef, ...]

    @property
    def kind(self) -> str:
        return "published_instance"
