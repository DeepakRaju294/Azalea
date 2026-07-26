"""Delivery boundary (§11, 1B) — shipping policy + eligibility + the fail-closed delivery-scope assertion.

Three policy layers stay separate (spec §5): evidence earns the LEVEL (validate.py); SHIPPING policy decides
learner visibility (here); the delivery-scope assertion checks the evidence actually binds to THIS instance.
`validate_shipping_eligibility` raises ShippingPolicyError (NOT an integrity error) when a valid assurance is
below the bar for its kind+risk — a different job from evidence corruption.

Instance-scope only for 1A: a Mode-A instance ships with `evidence_subject == subject_fingerprint`, so no
relationship/deterministic-execution divergence path applies yet (that arrives with Mode B).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from app.services.examples.retrieval.fingerprints import InstanceFingerprintSet
from app.services.examples.retrieval.model import (
    AssuranceStrength, EvidenceIntegrityError, EvidenceRecord, EvidenceRevocation, InstanceAssuranceDecision,
    ShippingPolicyError,
)
from app.services.examples.retrieval.validate import validate_assurance_decision

DomainRisk = Literal["ordinary", "high"]
ShippingDisposition = Literal["ship_verified", "ship_provisional", "withhold_guided"]


@dataclass(frozen=True)
class ShippingPolicy:
    """Required assurance to ship (§11). Operational policy (user decision 2026-07-25): a UNIFORM bar —
    reproduction-verified is enough in EVERY domain, no elevated high-risk threshold — and producible-but-
    unverified examples SHIP as provisional (badged 'under review'), maximizing coverage. `allow_provisional`
    reflects that stance; going live still requires the frontend badge dependency (§11). `risk` is retained for
    a future per-domain policy but is currently unused."""
    policy_version: str = "shipping/v1-uniform"
    allow_provisional: bool = True

    def required_strength(self, kind: str, risk: DomainRisk) -> AssuranceStrength:
        return AssuranceStrength.REPRODUCED_INSTANCE   # uniform across domains (user decision)


def meets_threshold(decision: InstanceAssuranceDecision, *, kind: str, risk: DomainRisk,
                    policy: ShippingPolicy, review_approved: bool = False) -> bool:
    """automated_strength >= required, OR an approved review covering this artifact (review is orthogonal)."""
    return (decision.profile.automated_strength >= policy.required_strength(kind, risk)) or review_approved


def ship_disposition(decision: InstanceAssuranceDecision, *, kind: str = "computational",
                     risk: DomainRisk = "ordinary", policy: ShippingPolicy = ShippingPolicy(),
                     review_approved: bool = False) -> ShippingDisposition:
    """Resolve what actually reaches the learner. verified/threshold-meeting -> ship_verified; producible-but-
    below-threshold -> ship_provisional (if allowed); otherwise -> withhold_guided (a tracked coverage_gap)."""
    if meets_threshold(decision, kind=kind, risk=risk, policy=policy, review_approved=review_approved):
        return "ship_verified"
    if decision.level == "provisional" and policy.allow_provisional:
        return "ship_provisional"
    return "withhold_guided"


def validate_shipping_eligibility(decision: InstanceAssuranceDecision, *, kind: str = "computational",
                                  risk: DomainRisk = "ordinary", policy: ShippingPolicy = ShippingPolicy(),
                                  review_approved: bool = False) -> ShippingDisposition:
    """Raise ShippingPolicyError only when NOTHING may ship (never on evidence grounds). Otherwise return the
    disposition."""
    disp = ship_disposition(decision, kind=kind, risk=risk, policy=policy, review_approved=review_approved)
    if disp == "withhold_guided" and decision.level != "guided":
        raise ShippingPolicyError(
            f"{decision.level} below required threshold for {kind}/{risk} and provisional not allowed")
    return disp


@dataclass(frozen=True)
class DeliveredInstance:
    fingerprints: InstanceFingerprintSet
    assurance: InstanceAssuranceDecision
    card_payload: Mapping[str, Any]


def assert_delivery_scope(d: DeliveredInstance, evidence_by_id: Mapping[str, EvidenceRecord],
                          revocations: Mapping[str, EvidenceRevocation] | None = None) -> None:
    """Fail-closed delivery integrity (§5). Validates the evidence earns the level (shared authority), then the
    fingerprint-scope rule: an instance-scope delivery MUST have evidence_subject == subject_fingerprint."""
    records: Sequence[EvidenceRecord] = [evidence_by_id[eid] for eid in d.assurance.evidence_ids
                                         if eid in evidence_by_id]
    validate_assurance_decision(d.assurance, records, revocations or {})
    if d.fingerprints.evidence_subject != d.assurance.subject_fingerprint:
        raise EvidenceIntegrityError("evidence/subject fingerprint mismatch (instance scope requires equality)")
