"""L4 — bounded risk classifier (Q24 §3), reject/downgrade-only, NEVER certifying.

Returns a RISK CLASS over a supplied evidence package, not a truth certificate. "Supported" is deliberately not a
verdict — L4 can never move a claim to established (that's the deterministic resolver's job). Key guards:
- `no_objection` may be emitted ONLY for non_factual_framing / prompt / deterministic_carried_elsewhere; a factual
  free-text span that nothing contradicts resolves `unsupported`, never `no_objection`.
- `n/a` (no factual assertion) and `unavailable` (couldn't run) are distinct; `unavailable` on a factual assertion
  is soften/withhold, never a clean pass.
- every verdict records its `EvidenceContext`; a `refuted` verdict carries `evidence_ids` and replays identically
  against the same pinned context.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from . import evidence

# verdicts
REFUTED = "refuted"
UNSUPPORTED = "unsupported"
NO_OBJECTION = "no_objection"
NA = "n/a"
UNAVAILABLE = "unavailable"

# unsupported_reason
NO_MATCHING_EVIDENCE = "no_matching_evidence"
INSUFFICIENT_SCOPE = "insufficient_scope"
CONFLICTING_EVIDENCE_WITHOUT_RESOLVED_PRECEDENCE = "conflicting_evidence_without_resolved_precedence"
EVIDENCE_PACK_MISSING_FOR_DOMAIN = "evidence_pack_missing_for_domain"

# claim_class / ownership literals L4 reasons about
FACTUAL = "factual"
NON_FACTUAL_FRAMING = "non_factual_framing"
PROMPT = "prompt"
DETERMINISTIC_CARRIED_ELSEWHERE = "deterministic_carried_elsewhere"


@dataclass(frozen=True)
class L4Result:
    verdict: str
    unsupported_reason: Optional[str]
    evidence_ids: Tuple[str, ...]
    evidence_context: evidence.EvidenceContext
    verifier_available: bool


def verify(
    claim_text: str,
    claim_class: str,
    *,
    fact_pack: Optional[evidence.FactPack] = None,
    content_ownership: str = "free_text",
    verifier_available: bool = True,
    source_excerpt_ids: Tuple[str, ...] = (),
    trace_ids: Tuple[str, ...] = (),
) -> L4Result:
    """Classify risk over the supplied evidence ONLY. Never establishes; only refutes / downgrades / abstains."""
    ctx = (fact_pack.context(source_excerpt_ids=source_excerpt_ids, trace_ids=trace_ids)
           if fact_pack is not None else evidence.EvidenceContext(source_excerpt_ids=tuple(source_excerpt_ids),
                                                                  trace_ids=tuple(trace_ids)))

    if not verifier_available:
        # REQUIRED but couldn't run — distinct from n/a; caller softens/withholds a factual assertion.
        return L4Result(UNAVAILABLE, None, (), ctx, False)

    eligible_no_objection = (
        claim_class in (NON_FACTUAL_FRAMING, PROMPT)
        or content_ownership == DETERMINISTIC_CARRIED_ELSEWHERE
    )

    # pure framing carries no factual assertion → n/a (clean ship), no evidence needed
    if claim_class == NON_FACTUAL_FRAMING:
        return L4Result(NA, None, (), ctx, True)

    if fact_pack is None:
        # no evidence pack for this domain → hold the FAMILY in shadow, don't delete sentences one by one
        return L4Result(UNSUPPORTED, EVIDENCE_PACK_MISSING_FOR_DOMAIN, (), ctx, True)

    norm = evidence.normalize_claim(claim_text)
    denied = fact_pack.denied()
    if norm in denied:
        return L4Result(REFUTED, None, (denied[norm],), ctx, True)

    # nothing contradicts, but L4 cannot establish. no_objection only for the eligible classes.
    if eligible_no_objection:
        return L4Result(NO_OBJECTION, None, (), ctx, True)
    return L4Result(UNSUPPORTED, NO_MATCHING_EVIDENCE, (), ctx, True)
