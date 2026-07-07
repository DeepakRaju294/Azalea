"""Claim-establishment resolver (Q24 §4) — DETERMINISTIC, never L4.

Passing L1/L2/L3 is NOT establishment. A `factual` free-text span ships only when this resolver marks it
`established` via a concrete basis: a registered definition, a fact-pack rule, a deterministic L2 proof / registered
transformation, or authoritative trace ownership. It runs before/alongside L4 and returns {status, basis,
evidence_ids}; it NEVER uses an LLM verdict as establishment (otherwise L4 quietly becomes a certifier).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from . import evidence

ESTABLISHED = "established"
NOT_ESTABLISHED = "not_established"

# basis
TRACE_AUTHORITATIVE = "trace_authoritative"
DETERMINISTIC_GROUND_RELATION = "deterministic_ground_relation"
DETERMINISTIC_SYMBOLIC_TRANSFORMATION = "deterministic_symbolic_transformation"
REGISTERED_DEFINITION = "registered_definition"
FACT_PACK_RULE = "fact_pack_rule"
SUPPLIED_SOURCE_EXCERPT = "supplied_source_excerpt"
NONE = "none"


@dataclass(frozen=True)
class ClaimEstablishment:
    status: str
    basis: str
    evidence_ids: Tuple[str, ...] = ()


def resolve_establishment(
    claim_text: str,
    *,
    fact_pack: Optional[evidence.FactPack] = None,
    l2_proven: bool = False,
    ground_relation_proven: bool = False,
    trace_owned: bool = False,
) -> ClaimEstablishment:
    """Mark a factual span established ONLY via a deterministic basis. Order: trace ownership → deterministic
    proof → registered definition/fact-pack rule. No match ⇒ not_established (→ L4, which cannot establish)."""
    if trace_owned:
        return ClaimEstablishment(ESTABLISHED, TRACE_AUTHORITATIVE)
    if ground_relation_proven:
        return ClaimEstablishment(ESTABLISHED, DETERMINISTIC_GROUND_RELATION)
    if l2_proven:
        return ClaimEstablishment(ESTABLISHED, DETERMINISTIC_SYMBOLIC_TRANSFORMATION)
    if fact_pack is not None:
        norm = evidence.normalize_claim(claim_text)
        asserted = fact_pack.asserted()
        if norm in asserted:
            eid, kind = asserted[norm]
            basis = REGISTERED_DEFINITION if kind == "definition" else FACT_PACK_RULE
            return ClaimEstablishment(ESTABLISHED, basis, (eid,))
    return ClaimEstablishment(NOT_ESTABLISHED, NONE)
