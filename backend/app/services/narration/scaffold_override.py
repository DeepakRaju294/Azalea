"""Phase-3 card-level scaffold overrides / mixed-domain (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §5,
DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §47).

A genuinely-mixed topic (e.g. a math lesson with one code card) may eventually let a single card borrow another
domain's scaffold. Uncontrolled, this recreates the Phase-0 problem locally, so the mechanism is tightly bounded:

  1. only an explicitly WHITELISTED card type may override;
  2. the override is chosen by DETERMINISTIC metadata / an approved adapter flag — never free LLM choice;
  3. it must NOT bypass Phase-0 topic-type / card-safety rules (the borrowed scaffold's card must not be
     `not_applicable` in the scaffold domain);
  4. the card declares BOTH `topic_domain` and `scaffold_domain`;
  5. every override is logged for review.

**v1 ships with the allow-list EMPTY** — the data shape + resolver exist, but no card type may override until a
concrete fixture proves the need. So `resolve_scaffold` is an identity (scaffold_domain == topic_domain) by
default; enabling a card type is a deliberate `register_override_allowed(...)` call backed by a fixture.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.services.narration.matrix import NARRATION_DOMAINS, NOT_APPLICABLE, card_status, narration_domain_of

_log = logging.getLogger(__name__)

# §5 rule 1: EMPTY in v1. Add a card type only when a fixture proves the need.
_OVERRIDE_ALLOWED_CARD_TYPES: set[str] = set()

# §5 rule 2: only deterministic provenance may drive an override — never "llm"/free choice.
_DETERMINISTIC_SOURCE_PREFIXES = ("adapter_flag:", "metadata:")


@dataclass(frozen=True)
class ScaffoldResolution:
    topic_domain: str
    scaffold_domain: str        # effective scaffold domain (== topic_domain unless a valid override applied)
    overridden: bool
    reason: str                 # machine-readable outcome/rejection code


def register_override_allowed(card_type: str) -> None:
    """Whitelist a card type for scaffold override (backed by an approved fixture, §5 rule 1)."""
    _OVERRIDE_ALLOWED_CARD_TYPES.add(str(card_type or "").strip().lower())


def clear_override_allowlist() -> None:
    """Reset to the v1 empty allow-list (test/rollback helper)."""
    _OVERRIDE_ALLOWED_CARD_TYPES.clear()


def is_override_allowed(card_type: str) -> bool:
    return str(card_type or "").strip().lower() in _OVERRIDE_ALLOWED_CARD_TYPES


def _is_deterministic_source(source: Optional[str]) -> bool:
    return bool(source) and any(str(source).startswith(p) for p in _DETERMINISTIC_SOURCE_PREFIXES)


def resolve_scaffold(
    card_type: str,
    topic_domain: str,
    *,
    requested_scaffold_domain: Optional[str] = None,
    source: Optional[str] = None,
) -> ScaffoldResolution:
    """Resolve the effective scaffold domain for one card. Identity (no override) unless ALL §5 conditions hold.
    Every applied override is logged. Rejections carry a reason but never raise — the card simply keeps its own
    topic-domain scaffold (the safe default)."""
    td = narration_domain_of(topic_domain) or topic_domain
    sd = narration_domain_of(requested_scaffold_domain) if requested_scaffold_domain else None

    # No override requested → identity.
    if not requested_scaffold_domain or sd == td:
        return ScaffoldResolution(td, td, False, "no_override")

    # Rule 1 — card type must be whitelisted (empty in v1 ⇒ always rejected here).
    if not is_override_allowed(card_type):
        return ScaffoldResolution(td, td, False, "card_type_not_whitelisted")
    # Rule 2 — deterministic source only.
    if not _is_deterministic_source(source):
        return ScaffoldResolution(td, td, False, "non_deterministic_source")
    # Valid target domain.
    if sd not in NARRATION_DOMAINS:
        return ScaffoldResolution(td, td, False, "invalid_scaffold_domain")
    # Rule 3 — must not bypass card-safety: the borrowed scaffold's card must be applicable in that domain.
    if card_status(card_type, sd) == NOT_APPLICABLE:
        return ScaffoldResolution(td, td, False, "would_bypass_card_safety")

    # Rule 5 — log every applied override.
    _log.info("scaffold_override applied card_type=%s topic_domain=%s scaffold_domain=%s source=%s",
              card_type, td, sd, source)
    return ScaffoldResolution(td, sd, True, f"override_applied:{source}")
