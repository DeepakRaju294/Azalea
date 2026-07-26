"""Escalation state machine (§1.6, §12, §2.5) — maps outcomes to the learner output + offline acquisition,
encoding the hard completeness invariant: 'no adapter' is NEVER a reason a wanting topic lacks an example.

Online resolution returns a ResolutionResult (a learner output NOW + optional acquisition metadata); the
offline worker advances acquisition. A rejection (refute) discards the candidate and escalates — never ships
wrong, never silently blocks. The learner-level outcome is always exhaustive: a delivered example OR a tracked
guided coverage_gap — never 'blocked because no adapter'.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

FailureClass = Literal["transient_infrastructure", "source_not_found", "source_conflict",
                       "transcription_invalid", "verification_refuted", "verification_indecisive",
                       "policy_blocked"]

EscalationAction = Literal["retry_or_queue", "broaden_retrieval", "human_review", "discard_candidate",
                           "stronger_verifier_or_review", "guided_or_provisional_per_policy"]

# §12 table — a transient failure is NEVER a semantic refutation.
_NEXT_STATE: dict[FailureClass, EscalationAction] = {
    "transient_infrastructure": "retry_or_queue",
    "source_not_found": "broaden_retrieval",
    "source_conflict": "human_review",
    "transcription_invalid": "discard_candidate",
    "verification_refuted": "discard_candidate",
    "verification_indecisive": "stronger_verifier_or_review",
    "policy_blocked": "guided_or_provisional_per_policy",
}


def next_state(failure: FailureClass) -> EscalationAction:
    return _NEXT_STATE[failure]


AcquisitionState = Literal["retrieval_pending", "verification_pending", "review_pending",
                           "approved", "corrected", "rejected"]
LearnerOutput = Literal["delivered", "provisional", "guided"]


@dataclass(frozen=True)
class ResolutionResult:
    """The online result. `learner_output` is always present (completeness); `acquisition_state` is metadata a
    background worker advances. `coverage_gap` marks a guided floor (a tracked, converging defect, never a
    resting 'blocked'). `blocked_no_adapter` is ALWAYS False — lacking an adapter never blocks."""
    learner_output: LearnerOutput
    acquisition_state: Optional[AcquisitionState]
    coverage_gap: bool
    blocked_no_adapter: bool = False   # invariant: never True (hard completeness, §1.7)


def route_disposition(disposition: str) -> ResolutionResult:
    """Map a shipping disposition (delivery.ship_disposition) to a resolution outcome."""
    if disposition == "ship_verified":
        return ResolutionResult("delivered", "approved", coverage_gap=False)
    if disposition == "ship_provisional":
        return ResolutionResult("provisional", "review_pending", coverage_gap=False)
    # withhold_guided: refuted/empty candidate -> transitional guided floor, enqueued, tracked.
    return ResolutionResult("guided", "review_pending", coverage_gap=True)


def route_retrieval_miss() -> ResolutionResult:
    """No candidate found. Still NOT blocked: guided floor now + offline acquisition keeps trying (broaden)."""
    return ResolutionResult("guided", "retrieval_pending", coverage_gap=True)
