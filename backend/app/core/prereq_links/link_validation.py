"""Tier-1 interactive-link validation (PREREQ_LINKS_SPEC v8 §6.3b). Pure — no app imports.

Runs AFTER lesson generation + enrichment, on the links only. Any failure drops the offending link (never the
topic list — that's Tier 2). Operates on `ScannedLink`-shaped items (text/action/target/concept_id); prose
fields are the generator's concern and are not validated here."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import LinkAction
from .scan import ScannedLink

_REQUIRES_CONCEPT = {LinkAction.open_study_path, LinkAction.review_earlier_topic}


class LinkDrop(BaseModel):
    text: str
    action: LinkAction
    reason: str        # anchor_not_verbatim | missing_concept_id | missing_target | over_cap | duplicate


class LinkValidationResult(BaseModel):
    links: list[ScannedLink] = Field(default_factory=list)
    dropped: list[LinkDrop] = Field(default_factory=list)


def validate_links(links: list[ScannedLink], card_text: str, *, per_card_cap: int = 3) -> LinkValidationResult:
    """Drop links that violate the §6.3b contract; the surviving links are returned in input order.

    - `text` must be present VERBATIM (case-sensitive) in the finalized card (§5/§A6);
    - `open_study_path`/`review_earlier_topic` require a non-empty `concept_id` (§1.3);
    - `open_study_path` requires a non-empty `target` (§3);
    - dedupe identical (concept_id, action) — keep the first;
    - enforce the ≤ per_card_cap links-per-card cap (§2.5).
    """
    kept: list[ScannedLink] = []
    dropped: list[LinkDrop] = []
    seen: set[tuple[str, str]] = set()

    for link in links:
        if link.text not in (card_text or ""):
            dropped.append(LinkDrop(text=link.text, action=link.action, reason="anchor_not_verbatim"))
            continue
        if link.action in _REQUIRES_CONCEPT and not link.concept_id:
            dropped.append(LinkDrop(text=link.text, action=link.action, reason="missing_concept_id"))
            continue
        if link.action == LinkAction.open_study_path and not (link.target or "").strip():
            dropped.append(LinkDrop(text=link.text, action=link.action, reason="missing_target"))
            continue
        dedupe_key = (link.concept_id or link.text, link.action.value)
        if dedupe_key in seen:
            dropped.append(LinkDrop(text=link.text, action=link.action, reason="duplicate"))
            continue
        if len(kept) >= per_card_cap:
            dropped.append(LinkDrop(text=link.text, action=link.action, reason="over_cap"))
            continue
        seen.add(dedupe_key)
        kept.append(link)

    return LinkValidationResult(links=kept, dropped=dropped)
