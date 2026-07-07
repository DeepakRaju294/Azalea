"""Backend ownership + requiredness router (Q24 §2/§3).

The last bypass this closes: if the generator could self-label a span `deterministic_carried_elsewhere` or
`optional`, a false claim would dodge establishment / deletion. So ownership and requirement are BACKEND-derived —
generator-supplied labels are discarded here (never read as a routing instruction). A registered mapping that
selects `deterministic_carried_elsewhere` without valid provenance is a HARD routing failure (never a silent
`free_text` downgrade); a span with no backend mapping is `free_text` and must establish normally.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# content_ownership
FREE_TEXT = "free_text"
TRACE_AUTHORITATIVE = "trace_authoritative"
TRACE_DERIVABLE = "trace_derivable"
DETERMINISTIC_CARRIED_ELSEWHERE = "deterministic_carried_elsewhere"

# span_requirement (backend-derived)
OPTIONAL = "optional"
REQUIRED = "required"
ESSENTIAL = "essential"

# requirement_source
NARRATION_CONTRACT = "narration_contract"
CARD_SCHEMA = "card_schema"
REGISTERED_TEMPLATE = "registered_template"
FALLBACK_DEFAULT = "fallback_default"   # no backend mapping — distinguishes a default from a contract-mapped value


@dataclass(frozen=True)
class OwnershipProvenance:
    deterministic_source_id: Optional[str] = None
    source_version: Optional[str] = None
    source_field: Optional[str] = None

    def is_valid(self) -> bool:
        return bool(self.deterministic_source_id) and bool(self.source_version) and bool(self.source_field)


@dataclass(frozen=True)
class RegisteredMapping:
    """What the backend registry knows about a field/slot — the ONLY authority for ownership + requirement."""
    content_ownership: str
    span_requirement: str
    requirement_source: str
    ownership_provenance: Optional[OwnershipProvenance] = None


@dataclass(frozen=True)
class RoutedSpan:
    content_ownership: str
    span_requirement: str
    requirement_source: str
    ownership_provenance: Optional[OwnershipProvenance]
    hard_routing_failure: bool
    generator_label_discarded: bool


def route_span(
    mapping: Optional[RegisteredMapping],
    *,
    generator_label: Optional[dict] = None,   # accepted then DISCARDED — never read as authority
    unclassified: bool = False,
) -> RoutedSpan:
    """Resolve a span's ownership + requirement from the backend registry only.

    `generator_label` is deliberately ignored (its presence is recorded for telemetry so we can prove it was
    discarded). `unclassified` spans inherit the field requirement and default to REQUIRED when unmapped — never
    optional-deletable (a missed clause can't be dropped as "optional")."""
    discarded = generator_label is not None

    if mapping is None:
        # No backend mapping → free_text; must establish normally. Unclassified defaults to required (fail closed).
        req = REQUIRED if unclassified else OPTIONAL
        return RoutedSpan(FREE_TEXT, req, FALLBACK_DEFAULT, None, False, discarded)

    if mapping.content_ownership == DETERMINISTIC_CARRIED_ELSEWHERE:
        prov = mapping.ownership_provenance
        if prov is None or not prov.is_valid():
            # Hard routing failure — fail closed, NEVER downgrade to free_text.
            return RoutedSpan(DETERMINISTIC_CARRIED_ELSEWHERE, mapping.span_requirement,
                              mapping.requirement_source, prov, True, discarded)
        return RoutedSpan(DETERMINISTIC_CARRIED_ELSEWHERE, mapping.span_requirement,
                          mapping.requirement_source, prov, False, discarded)

    # unclassified never becomes optional even under a mapping that says optional
    req = mapping.span_requirement
    if unclassified and req == OPTIONAL:
        req = REQUIRED
    return RoutedSpan(mapping.content_ownership, req, mapping.requirement_source,
                      mapping.ownership_provenance, False, discarded)
