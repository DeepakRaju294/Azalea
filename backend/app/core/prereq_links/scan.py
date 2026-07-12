"""Deterministic candidate scan + action assignment (PREREQ_LINKS_SPEC v8 §2/§2.3/§2.5a/§5). Pure.

Given a card's plain-text projection (§2.2) + the decomposition-emitted identities for this path, emit the
NAVIGATION link skeletons (`review_earlier_topic` / `open_study_path`, plus glossary-seeded `popup_only`) by
exact deterministic scanning — never depending on the model *noticing* a term (§A26). Prose (explanation /
why_it_matters_here) is filled later by the generator; this module only decides action/target/concept_id/anchor."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .enums import LinkAction
from .models import AssumedPrerequisite, TopicConceptIdentity
from .projection import find_token_matches
from .validation import normalize_identity


class GlossaryIdentity(BaseModel):
    concept_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)


class ScanContext(BaseModel):
    current_topic_index: int
    topic_identities: list[TopicConceptIdentity] = Field(default_factory=list)   # owners; index<current → review
    assumed_prerequisites: list[AssumedPrerequisite] = Field(default_factory=list)
    glossary_identities: list[GlossaryIdentity] = Field(default_factory=list)
    suppressed_concept_ids: set[str] = Field(default_factory=set)                # cycle suppression (§4.1)
    already_linked_concept_ids: set[str] = Field(default_factory=set)            # linked earlier this topic (§2.5a)
    per_card_cap: int = 3


class ScannedLink(BaseModel):
    text: str
    action: LinkAction
    target: Optional[str] = None
    concept_id: Optional[str] = None


class DroppedCandidate(BaseModel):
    concept_id: Optional[str] = None
    surface: str
    reason: str        # ambiguous_navigation_identity | overlap | over_cap | glossary_shadowed_by_navigation


class ScanResult(BaseModel):
    links: list[ScannedLink] = Field(default_factory=list)
    dropped: list[DroppedCandidate] = Field(default_factory=list)


class _Candidate:
    __slots__ = ("start", "end", "surface", "concept_id", "action", "target", "origin")

    def __init__(self, start, end, surface, concept_id, action, target, origin):
        self.start, self.end, self.surface = start, end, surface
        self.concept_id, self.action, self.target, self.origin = concept_id, action, target, origin

    @property
    def length(self) -> int:
        return self.end - self.start


# origin → §2.5a priority tier (lower = higher priority). Computed from ORIGIN, not action, so a cycle-suppressed
# prerequisite (action popup_only) still ranks as a knowledge-gap, not an incidental gloss.
_TIER_NEW_PREREQ = 0        # assumed-prereq not yet linked in this topic
_TIER_EARLIER = 1           # earlier-topic review
_TIER_SEEN_PREREQ = 2       # assumed-prereq already linked in this topic
_TIER_GLOSSARY = 3          # popup-only glossary seed


def scan_card(card_text: str, ctx: ScanContext) -> ScanResult:
    """Scan one card's plain-text projection; return the ordered, capped navigation links (§2/§2.5a/§5)."""
    dropped: list[DroppedCandidate] = []

    # ── 1. build the navigation surface index (normalized surface → concept action) ───────────────────────
    nav: dict[str, list[tuple[str, LinkAction, Optional[str]]]] = {}   # surface → [(concept_id, action, target)]

    def _add_nav(surfaces, concept_id, action, target):
        for surface in surfaces:
            key = normalize_identity(surface)
            if key:
                nav.setdefault(key, []).append((concept_id, action, target))

    for t in ctx.topic_identities:
        if t.topic_index < ctx.current_topic_index:            # taught EARLIER only (§A36)
            _add_nav((t.canonical_name, *t.aliases), t.concept_id, LinkAction.review_earlier_topic, t.topic_id)
    for p in ctx.assumed_prerequisites:
        if p.concept_id in ctx.suppressed_concept_ids:         # cycle-suppressed → popup, target dropped (§4.1)
            _add_nav((p.canonical_name, *p.aliases), p.concept_id, LinkAction.popup_only, None)
        else:
            _add_nav((p.canonical_name, *p.aliases), p.concept_id, LinkAction.open_study_path, p.target_goal)

    # ambiguity: one normalized surface → >1 distinct concept_id ⇒ no deterministic action (§2.3/§A19).
    nav_resolved: dict[str, tuple[str, LinkAction, Optional[str]]] = {}
    for key, entries in nav.items():
        concepts = {c for c, _, _ in entries}
        if len(concepts) > 1:
            dropped.append(DroppedCandidate(surface=key, reason="ambiguous_navigation_identity"))
            continue
        nav_resolved[key] = entries[0]

    # glossary index (popup seed); navigation OUTRANKS glossary on a shared surface (§2.3/§A38).
    glossary: dict[str, str] = {}
    for g in ctx.glossary_identities:
        for surface in (g.canonical_name, *g.aliases):
            key = normalize_identity(surface)
            if not key:
                continue
            if key in nav_resolved:
                dropped.append(DroppedCandidate(concept_id=g.concept_id, surface=key,
                                                reason="glossary_shadowed_by_navigation"))
                continue
            glossary[key] = g.concept_id

    # ── 2. scan the card text for every surface → raw candidates ──────────────────────────────────────────
    cands: list[_Candidate] = []
    for key, (concept_id, action, target) in nav_resolved.items():
        origin = (_TIER_EARLIER if action == LinkAction.review_earlier_topic
                  else (_TIER_NEW_PREREQ if concept_id not in ctx.already_linked_concept_ids else _TIER_SEEN_PREREQ))
        for start, end, surface in find_token_matches(card_text, key):
            cands.append(_Candidate(start, end, surface, concept_id, action, target, origin))
    for key, concept_id in glossary.items():
        for start, end, surface in find_token_matches(card_text, key):
            cands.append(_Candidate(start, end, surface, concept_id, LinkAction.popup_only, None, _TIER_GLOSSARY))

    # ── 3. anchor resolution (§5): longest wins, first eligible per concept, reject overlaps ──────────────
    selected = _resolve_overlaps(cands, dropped)

    # ── 4. priority + per-card cap (§2.5a) ────────────────────────────────────────────────────────────────
    selected.sort(key=lambda c: (c.origin, c.start, -c.length, c.concept_id or ""))
    kept = selected[: ctx.per_card_cap]
    for c in selected[ctx.per_card_cap:]:
        dropped.append(DroppedCandidate(concept_id=c.concept_id, surface=c.surface, reason="over_cap"))

    kept.sort(key=lambda c: c.start)   # emit in reading order
    links = [ScannedLink(text=c.surface, action=c.action, target=c.target, concept_id=c.concept_id) for c in kept]
    return ScanResult(links=links, dropped=dropped)


def _resolve_overlaps(cands: list[_Candidate], dropped: list[DroppedCandidate]) -> list[_Candidate]:
    """§5: prefer the longest phrase on overlap, reject overlapping links, first eligible occurrence per concept."""
    # longest-first, then earliest, gives "electric field" precedence over "field" (§A13).
    ordered = sorted(cands, key=lambda c: (-c.length, c.start, c.concept_id or ""))
    occupied: list[tuple[int, int]] = []
    seen_concepts: set[str] = set()
    selected: list[_Candidate] = []
    for c in ordered:
        if c.concept_id in seen_concepts:                     # first eligible occurrence per concept (§A12)
            dropped.append(DroppedCandidate(concept_id=c.concept_id, surface=c.surface, reason="overlap"))
            continue
        if any(not (c.end <= s or c.start >= e) for s, e in occupied):   # overlaps a taken span → reject (§5)
            dropped.append(DroppedCandidate(concept_id=c.concept_id, surface=c.surface, reason="overlap"))
            continue
        occupied.append((c.start, c.end))
        if c.concept_id:
            seen_concepts.add(c.concept_id)
        selected.append(c)
    return selected
