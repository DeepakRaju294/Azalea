"""Plan construction — facets→sections, dependency ordering, bridge guard (STUDY_PATH_SCOPE_SPEC §1.6, §6.3,
§11, §12). Pure functions, no app imports.

Two load-bearing pieces:
  * `consolidate_facets` — the ONE place facets become sections (§12): given a canonical key and the facets
    decomposition discovered, produce ONE concept whose sub-facets are SECTIONS (not deleted duplicates,
    not independent concepts), gated by target depth and exclusions.
  * `resolve_concept_order` — the owned derived ordering (§6.3): a stable topological sort with a deterministic
    tie-break; readers consume it, never re-run the sort (§12).
"""
from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from pydantic import BaseModel, Field

from .enums import CardinalityPolicy, Facet, SectionType
from .ids import stable_slug
from .models import Concept, ConceptIdentity, Edge, LessonSectionPlan, Objective

# --- facet → section consolidation (§1.6, §12) ------------------------------------------------------------

# Each identity facet maps to exactly one instructional section role.
_FACET_SECTION: dict[Facet, SectionType] = {
    Facet.core: SectionType.foundation,
    Facet.method: SectionType.walkthrough,
    Facet.derivation: SectionType.derivation,
    Facet.correctness: SectionType.proof,
    Facet.implementation: SectionType.implementation,
    Facet.application: SectionType.application,
}

# The minimum target depth at which a facet is taught. core is always taught; deeper facets need more depth,
# so "quick review" yields an atomic concept and "master X incl. implementation and correctness" a multi_section.
_DEPTH_ORDER = {"overview": 0, "review": 0, "intro": 0, "working": 1, "applied": 1, "mastery": 2, "deep": 2}
_FACET_MIN_DEPTH: dict[Facet, int] = {
    Facet.core: 0, Facet.method: 1, Facet.application: 1,
    Facet.implementation: 2, Facet.derivation: 2, Facet.correctness: 2,
}
# deterministic section ordering within a concept.
_SECTION_ORDER = [
    SectionType.foundation, SectionType.intuition, SectionType.mechanism, SectionType.walkthrough,
    SectionType.derivation, SectionType.proof, SectionType.implementation, SectionType.application,
    SectionType.comparison, SectionType.complexity, SectionType.edge_cases,
]


def _depth_level(depth: str) -> int:
    return _DEPTH_ORDER.get(stable_slug(depth), 1)


def _excluded(section_type: SectionType, facet: Facet, exclusions: Iterable[str]) -> bool:
    """A facet is excluded if any exclusion token matches its facet or section-type name (bidirectional
    substring on slugs, so "proofs" excludes the `proof` section)."""
    names = {stable_slug(section_type.value), stable_slug(facet.value)}
    for raw in exclusions:
        tok = stable_slug(raw)
        if not tok:
            continue
        if any(tok in n or n in tok for n in names):
            return True
    return False


class DiscoveredFacet(BaseModel):
    """A facet of a concept that decomposition surfaced (possibly as its own draft topic, e.g. 'derivation of
    Bayes'). Consolidation decides whether it becomes a section, is depth/exclusion-dropped, or (core) anchors
    the concept identity."""
    facet: Facet = Facet.core
    name: str = ""
    topic_type: str = ""
    objectives: list[Objective] = Field(default_factory=list)
    key_terms: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


def consolidate_facets(canonical_concept_key: str, discovered_facets: Sequence[DiscoveredFacet],
                       target_depth: str = "working",
                       exclusions: Iterable[str] = ()) -> tuple[Concept, list[LessonSectionPlan]]:
    """Collapse the discovered facets of one canonical concept into a SINGLE concept + its section plan (§12).

    Rules: the concept identity is always the `core` facet of the key (a rename or a sub-facet never forks
    identity); each surviving facet becomes one section, depth-gated and exclusion-filtered; a section that
    carries an objective (or is the core foundation) is non-optional so 'every required objective → a
    non-optional section' holds; `split_reason` is set iff >1 section (else null, matching derived cardinality).
    """
    exclusions = list(exclusions)
    level = _depth_level(target_depth)
    by_facet: dict[Facet, DiscoveredFacet] = {}
    for df in discovered_facets:
        by_facet.setdefault(df.facet, df)                      # first wins; stable

    core = by_facet.get(Facet.core)
    anchor = core or (discovered_facets[0] if discovered_facets else DiscoveredFacet())
    aliases = sorted({a for df in discovered_facets for a in df.aliases}
                     | {df.name for df in discovered_facets if df.name and df.name != anchor.name})
    identity = ConceptIdentity.create(name=anchor.name or canonical_concept_key,
                                      topic_type=anchor.topic_type or "concept",
                                      canonical_concept_key=canonical_concept_key, facet=Facet.core,
                                      aliases=aliases)

    sections: list[LessonSectionPlan] = []
    objectives: list[Objective] = []
    key_terms: list[str] = []
    kept_facets: list[Facet] = []
    for facet in sorted(by_facet, key=lambda f: _SECTION_ORDER.index(_FACET_SECTION[f])):
        df = by_facet[facet]
        section_type = _FACET_SECTION[facet]
        if facet != Facet.core and level < _FACET_MIN_DEPTH[facet]:
            continue                                            # depth-gated out
        if _excluded(section_type, facet, exclusions):
            continue                                            # exclusion-filtered
        kept_facets.append(facet)
        objective_ids = [o.objective_id for o in df.objectives]
        # optional iff it owns no objective and isn't the core foundation — pure enrichment.
        optional = facet != Facet.core and not objective_ids
        sections.append(LessonSectionPlan.create(concept_id=identity.concept_id, section_type=section_type,
                                                 order=len(sections) + 1, objective_ids=objective_ids,
                                                 optional=optional))
        objectives.extend(df.objectives)
        key_terms.extend(t for t in df.key_terms if t not in key_terms)

    split_reason = None
    if len(sections) > 1:
        extra = [f.value for f in kept_facets if f != Facet.core]
        split_reason = "concept spans facets: " + ", ".join(extra)

    concept = Concept(identity=identity, key_terms=key_terms, learning_objectives=objectives,
                      section_plan=sections, split_reason=split_reason)
    return concept, sections


# --- dependency ordering — owned derived value (§6.3, §12) -------------------------------------------------

_BIG = 10 ** 9


@dataclass(frozen=True)
class OrderingResult:
    order: list[str] = field(default_factory=list)
    cyclic: list[str] = field(default_factory=list)   # nodes in a cycle — reported, NEVER auto-broken (§4)

    @property
    def acyclic(self) -> bool:
        return not self.cyclic


def hard_edges_from_concepts(concepts: Iterable[Concept]) -> list[Edge]:
    """prerequisite_concept_ids → hard `prereq → concept` edges."""
    edges: list[Edge] = []
    for c in concepts:
        for pre in c.prerequisite_concept_ids:
            edges.append(Edge(from_concept_id=pre, to_concept_id=c.identity.concept_id))
    return edges


def _edge_pairs(edges: Iterable) -> list[tuple[str, str]]:
    out = []
    for e in edges:
        if isinstance(e, Edge):
            out.append((e.from_concept_id, e.to_concept_id))
        else:
            out.append((e[0], e[1]))
    return out


def resolve_concept_order(concept_ids: Sequence[str], edges: Iterable,
                          mention_order: Sequence[str] = (), source_order: Sequence[str] = (),
                          soft_order: Sequence[str] = ()) -> OrderingResult:
    """Stable topological sort (§6.3): honour (1) hard edges, then break ties by (2) goal/mention order,
    (3) source order, (4) soft preferences, (5) stable concept_id. Deterministic and total up to a cycle,
    which is reported (`cyclic`) rather than silently broken."""
    ids = list(concept_ids)
    idset = set(ids)
    pairs = [(f, t) for f, t in _edge_pairs(edges) if f in idset and t in idset]

    indeg = {c: 0 for c in ids}
    adj: dict[str, list[str]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for f, t in pairs:
        if f == t or (f, t) in seen:
            continue
        seen.add((f, t))
        adj[f].append(t)
        indeg[t] += 1

    mi, si, pi = ({v: i for i, v in enumerate(seq)} for seq in (mention_order, source_order, soft_order))

    def key(c: str) -> tuple:
        return (mi.get(c, _BIG), si.get(c, _BIG), pi.get(c, _BIG), c)

    heap = [(key(c), c) for c in ids if indeg[c] == 0]
    heapq.heapify(heap)
    order: list[str] = []
    while heap:
        _, c = heapq.heappop(heap)
        order.append(c)
        for nb in adj[c]:
            indeg[nb] -= 1
            if indeg[nb] == 0:
                heapq.heappush(heap, (key(nb), nb))

    placed = set(order)
    cyclic = sorted((c for c in ids if c not in placed), key=key)
    return OrderingResult(order=order, cyclic=cyclic)


def count_hard_edge_violations(order: Sequence[str], edges: Iterable) -> int:
    """`from` must precede `to`; count edges where it doesn't. The load-bearing shadow signal (§10): a
    `structurally_valid` scope must have zero (§12)."""
    pos = {c: i for i, c in enumerate(order)}
    n = 0
    for f, t in _edge_pairs(edges):
        if f in pos and t in pos and pos[f] > pos[t]:
            n += 1
    return n


# --- bridge insertion guard (§12) -------------------------------------------------------------------------

def bridge_insertion_allowed(*, dependency_evidenced: bool, necessary_for_required: bool,
                             already_prereq: bool, depth_permitted: bool, minimal: bool) -> bool:
    """A bridge concept is added ONLY if all five §12 conditions hold — dependency-evidenced, necessary for a
    required concept, not already a prerequisite, depth-permitted, and minimal vs alternatives. Never merely
    'helpful'."""
    return bool(dependency_evidenced and necessary_for_required and not already_prereq
                and depth_permitted and minimal)


def cardinality_of(concept: Concept) -> CardinalityPolicy:
    """Convenience mirror of the derived policy (owner stays `Concept.cardinality_policy`)."""
    return concept.cardinality_policy
