from __future__ import annotations

import copy
import json
import logging
import os
import threading
from typing import TYPE_CHECKING, Any

from app.prompts.topic_prompt import SYSTEM_PROMPT, build_topic_prompt
from app.services.course_type_classifier import enrich_topic_with_course_type
from app.core.decision_trace import record_path_decision, record_topic_decision, take_topic_trace
from app.services.domain_classifier import gate_family_of
from app.services.domain_gate import gate_topic_types_by_domain
from app.services.llm_client import generate_structured_topics

if TYPE_CHECKING:
    from app.models.content_chunk import ContentChunk

_log = logging.getLogger(__name__)

# --- Phase-0 domain routing gate (DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §4/§7) --------------------------------
# AZALEA_DOMAIN_ROUTING_GATE: unset/"0" = SHADOW (compute + log what the gate WOULD change, emit unchanged
# topics — existing behavior byte-for-byte); anything else = ENFORCED (emit the gated topics). The flag is read
# per-call so it can be flipped without a process restart.
_GATE_TELEMETRY_LOCK = threading.Lock()
_GATE_TELEMETRY_PATH = os.getenv(
    "AZALEA_DOMAIN_GATE_TELEMETRY_PATH", os.path.join("logs", "domain_gate.jsonl")
)


def _gate_enforced() -> bool:
    return os.getenv("AZALEA_DOMAIN_ROUTING_GATE", "") not in ("", "0")


def _coding_transforms_enabled(domain: str | None) -> bool:
    """Whether the coding-family canonical backfills (_expand_canonical_family / _append_missing_coding_topics /
    _order_canonical_family) should run. When the gate is ENFORCED and the path is a known NON-coding family,
    skip them so we don't inject coding topics a math/science path would only have to drop. When the flag is off
    (shadow) OR the domain is unknown/mixed/coding, they run exactly as before (§5, D-c)."""
    if not _gate_enforced() or not domain:
        return True
    return gate_family_of(domain) in ("", "coding")


def _record_gate_telemetry(payload: dict[str, Any]) -> None:
    """Best-effort structured-log + JSONL sink for gate decisions (D-d). Never raises — observability must not
    break generation."""
    _log.info(
        "domain_gate[%s] domain=%s family=%s seen=%d rewritten=%d dropped=%d recovered=%s validation=%s",
        payload.get("mode"), payload.get("domain"), payload.get("gate_family"),
        payload.get("topics_seen", 0), payload.get("topics_rewritten", 0), payload.get("topics_dropped", 0),
        payload.get("coverage_recovered"), payload.get("routing_validation"),
    )
    try:
        directory = os.path.dirname(_GATE_TELEMETRY_PATH)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with _GATE_TELEMETRY_LOCK, open(_GATE_TELEMETRY_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception:  # noqa: BLE001 — telemetry is best-effort
        pass


def _apply_domain_gate(topics: list[dict[str, Any]], domain: str | None) -> list[dict[str, Any]]:
    """Run the domain gate over the FINAL topic list and emit telemetry. Returns the gated list when ENFORCED,
    the original (untouched) list in SHADOW mode. The gate mutates dicts in place, so shadow mode runs it on a
    deep copy — the emitted topics stay byte-for-byte identical while telemetry still reflects real decisions."""
    if not domain:
        return topics
    enforced = _gate_enforced()
    working = [copy.deepcopy(t) for t in topics]
    gated, tel = gate_topic_types_by_domain(working, domain)
    tel["mode"] = "enforced" if enforced else "shadow"
    _record_gate_telemetry(tel)
    return gated if enforced else topics


def _ensure_intro_topic(topics: list[dict[str, Any]], goal: str | None) -> list[dict[str, Any]]:
    """Bulletproof backstop: EVERY path opens with a lightweight orientation topic — single-topic paths too
    (product decision; live failure: a 'straight line depreciation' path certified down to one topic and
    shipped with no orientation, no prereq card, no roadmap). The pipeline-level guarantee can be bypassed
    (regeneration, a stale decomposition), so enforce it here at the OUTERMOST point — for both engines.
    Idempotent: skips when an intro already leads the path."""
    if not topics:
        return topics
    if any(str(t.get("course_type") or t.get("topic_type") or "").lower() == "study_path_introduction"
           or str(t.get("content_role") or "").lower() == "orientation" for t in topics):
        return topics
    from app.services.topic_decomposition_pipeline import _intro_title
    intro = {
        "title": _intro_title(goal),
        "purpose": ("Orient the learner: frame the area, name the assumed prerequisites (without teaching "
                    "them), define the shared terms, and preview the topics ahead."),
        "learner_outcome": "Understand what this study path covers and what it assumes you already know.",
        "unit_title": "Introduction",
        "topic_type": "study_path_introduction",
        "course_type": "study_path_introduction",
        "secondary_course_types": [],
        "in_scope": [], "out_of_scope": [],
        "practice_target": "", "practice_format": "",
        "estimated_minutes": 8,
        "content_role": "orientation",
        "basis": "goal",
        "decomposition_metadata": {"schema_version": 1, "capability_id": "orientation",
                                   "content_role": "orientation", "basis": "goal", "synthesized_intro": True},
    }
    out = [intro, *topics]
    for i, t in enumerate(out, start=1):
        t["order_index"] = i
    _log.info("topic_generator: prepended orientation intro (none present on a %d-topic path)", len(topics))
    return out

# Paradigms/methodologies that a concrete algorithm already teaches BY EXAMPLE. A standalone
# "Understanding the X Strategy" / "What is X" topic for one of these — when the path's goal is
# a specific algorithm, not the paradigm itself — is redundant with the algorithm walkthrough
# and gets dropped (see _drop_paradigm_only_topics). Prompt rule alone wasn't enough.
import re as _re

# Canonical form (hyphens / & / underscores → spaces) so "divide-and-conquer" matches
# "divide and conquer".
_PARADIGM_TERMS: tuple[str, ...] = (
    "divide and conquer", "greedy", "dynamic programming", "backtracking",
    "brute force", "two pointer", "sliding window", "memoization",
    "branch and bound", "recursion", "iterative approach",
)


def _canon(text: str) -> str:
    return _re.sub(r"\s+", " ", _re.sub(r"[-&_]", " ", str(text or "").lower())).strip()
_CONCEPT_FRAMING: tuple[str, ...] = (
    "understanding", "what is", "introduction to", "intro to", "overview of",
    "the concept of", "approach", "strategy", "paradigm", "technique", "methodology",
)
_CONCRETE_TYPES: frozenset[str] = frozenset({
    "algorithm_walkthrough", "data_structure_operation", "coding_implementation",
    "math_formula_method", "process_walkthrough",
})


def _is_paradigm_only_topic(topic: dict[str, Any], goal_lower: str) -> bool:
    """A concept topic that merely names a paradigm the path's concrete topics already
    exemplify — not the path's actual subject."""
    title = _canon(topic.get("title"))
    matched = next((term for term in _PARADIGM_TERMS if term in title), None)
    if matched is None:
        return False
    if matched in _canon(goal_lower):
        return False  # the paradigm IS the learner's goal — a real subject, keep it
    if not any(frame in title for frame in _CONCEPT_FRAMING):
        return False  # not framed as an abstract concept (e.g. "Merge Sort", which is concrete)
    ttype = str(topic.get("course_type") or topic.get("topic_type") or "").strip().lower()
    return ttype in ("concept_intuition", "terminology_components", "")


def _drop_paradigm_only_topics(topics: list[dict[str, Any]], goal: str | None) -> list[dict[str, Any]]:
    """Remove auxiliary paradigm/methodology topics, capturing the paradigm in a concrete
    topic's assumed_prerequisites (future just-in-time popup). Never empties the path."""
    goal_lower = str(goal or "").lower()
    concrete = [t for t in topics if str(t.get("course_type") or "").strip().lower() in _CONCRETE_TYPES]
    if not concrete:
        return topics  # nothing concrete teaches the paradigm by example — keep it

    kept: list[dict[str, Any]] = []
    for topic in topics:
        if _is_paradigm_only_topic(topic, goal_lower):
            _log.info("topic_generator: dropping auxiliary paradigm topic %r", topic.get("title"))
            term = next((t for t in _PARADIGM_TERMS if t in _canon(topic.get("title"))), "")
            prereqs = concrete[0].setdefault("assumed_prerequisites", [])
            if isinstance(prereqs, list) and term and not any(term in str(p).lower() for p in prereqs):
                prereqs.append(term)
            continue
        kept.append(topic)
    if not kept:
        return topics  # guard: never drop everything
    dropped_titles = {str(t.get("title") or "").lower() for t in topics} - {str(t.get("title") or "").lower() for t in kept}
    for index, topic in enumerate(kept, start=1):
        topic["order_index"] = index
        # Strip dangling prerequisite references to dropped topics.
        prereq = topic.get("prerequisite_topics")
        if isinstance(prereq, str) and prereq:
            parts = [p.strip() for p in prereq.split(",") if p.strip() and p.strip().lower() not in dropped_titles]
            topic["prerequisite_topics"] = ", ".join(parts)
    return kept


# Topic types where one subject (algorithm / operation) should map to exactly ONE topic.
_ONE_PER_SUBJECT_TYPES: frozenset[str] = frozenset({
    "algorithm_walkthrough", "data_structure_operation", "coding_implementation",
    # A subject gets ONE conceptual-foundation topic too — the generator otherwise emits near-duplicate
    # intros ("Introduction to Quick Sort" + "Understanding Quick Sort Mechanism"). Subject-token
    # equality keeps genuinely distinct concept facets (e.g. "Quick Sort Time Complexity") separate.
    "concept_intuition",
})
# Framing words stripped from a title to find its core SUBJECT, so two differently-worded titles for
# the same subject ("Understanding Quick Sort: Process Overview" vs "Tracing Quick Sort Step by Step")
# reduce to the same key. Approach words (iterative/recursive) are NOT stripped, so genuinely distinct
# implementations stay distinct.
_SUBJECT_FRAMING_WORDS: frozenset[str] = frozenset({
    "understanding", "understand", "tracing", "trace", "exploring", "explore", "introduction",
    "intro", "overview", "review", "process", "step", "steps", "by", "how", "works", "working",
    "basics", "basic", "fundamentals", "fundamental", "deep", "dive", "walkthrough", "guide",
    "lesson", "part", "implementing", "implement", "code", "coding", "the", "a", "an", "to", "of",
    "in", "on", "with", "and", "for", "into",
    # generic "explain how it works" framing (so "...Mechanism" / "...Algorithm Explained" reduce to
    # the bare subject and collapse with a plain intro of the same subject)
    "mechanism", "mechanics", "algorithm", "algorithms", "explained", "explain", "concept", "concepts",
    "what", "is", "are", "key", "terms", "essentials", "primer",
    # study-verb framings the decomposition LLM sprinkles inconsistently ("Analyzing X", "Exploring X").
    # Stripping them keeps the SUBJECT clean so the synthesized coding title is "Implementing Quick Sort"
    # (not "Implementing Analyzing Quick Sort") AND the same-subject dedup collapses the duplicate.
    "analyzing", "analyze", "analysis", "examining", "examine", "learning", "learn", "mastering", "master",
    "discovering", "discover", "investigating", "investigate", "applying",
    # PEDAGOGICAL-ROLE framing: these name a topic's teaching role (worked examples / practice / application),
    # not its subject. Stripping them lets "Completing the Square: Example Problems" reduce to the bare subject
    # so it collapses with the "...Process" walkthrough of the same subject (they generate the same lesson).
    "example", "examples", "problem", "problems", "practice", "exercise", "exercises", "application",
    "applications", "applied", "worked", "solving", "solve", "solution", "solutions",
    # step/understanding/basics framings the LLM pads a single technique with ("Steps to X", "Understanding the
    # Basics of X") — stripping them lets those reduce to the bare subject so the same-subject dedup fires.
    "steps", "step", "understanding", "understand", "basics", "basic", "overview", "fundamentals", "fundamental",
    # goal-phrase intent words ("I want to learn about X") — these reach this vocabulary via the GOAL string in
    # _canonical_concept_key; leaving them in made goal keys like about_cost_opportunity that could never match
    # the taught topic's key, so the goal-core role was silently unreachable for non-adapter subjects.
    "about", "want", "wants", "i", "my", "me",
})


def _stem(tok: str) -> str:
    """Light suffix stemmer so 'complete'/'completing' and 'square'/'squares' key the same (single-concept
    dedup). Conservative: strips a common inflection, then at most one trailing 'e'; leaves short words alone."""
    for suf in ("ing", "edness", "edly", "ed", "es", "s"):
        if tok.endswith(suf) and len(tok) - len(suf) >= 4:
            tok = tok[: -len(suf)]
            break
    if len(tok) >= 5 and tok.endswith("e"):
        tok = tok[:-1]
    return tok


def _subject_tokens(title: str, extra_framing: frozenset[str] = frozenset()) -> tuple[frozenset[str], str]:
    # Framing check on the RAW token, then stem the survivors so inflections collapse (complete/completing).
    base = [_stem(t) for t in _re.findall(r"[a-z0-9]+", str(title or "").lower())
            if t not in _SUBJECT_FRAMING_WORDS]
    stripped = [t for t in base if t not in extra_framing]
    # Domain stripping must never EMPTY the subject — in a single-algorithm path the algorithm name
    # itself is path-common (every Quick Sort title has 'quick'/'sort'); falling back to the un-stripped
    # tokens keeps that subject so the same-subject dedup still works. Sorted key = order-independent.
    tokens = stripped if stripped else base
    return frozenset(tokens), "".join(sorted(tokens))


# One identity vocabulary used by decomposition certification, prerequisites, deduplication, and coding
# follow-ups. Acronyms must resolve to the same global concept as their expanded names; otherwise a goal such
# as "MST algorithms" can incorrectly retain "Minimum Spanning Tree" as its own prerequisite/topic.
_CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    "minimum_spanning_tree": ("mst", "minimum spanning tree", "minimum spanning trees"),
    "binary_search_tree": ("bst", "binary search tree", "binary search trees"),
    "breadth_first_search": ("bfs", "breadth first search"),
    "depth_first_search": ("dfs", "depth first search"),
    # Concept identity is deliberately more specific than adapter routing. A turbulence lesson may USE a
    # Reynolds-number example without BECOMING the Reynolds-number concept.
    "turbulent_energy_cascade": (
        "energy transfer in turbulence", "energy transfer in turbulent flow",
        "energy transfer in turbulent flows", "turbulent energy cascade", "energy cascade",
    ),
    "turbulence_applications": (
        "applications of turbulence", "turbulence applications", "real world effects of turbulence",
        "real world applications of turbulence",
    ),
    "flow_regimes": (
        "flow regime", "flow regimes", "types of fluid flow", "laminar vs turbulent",
        "laminar and turbulent flow", "laminar or turbulent flow",
    ),
    "reynolds_number": ("reynolds number",),
    "fluid_turbulence": ("fluid turbulence",),
}


def _canonical_concept_key(value: Any, topic_type: str = "") -> str:
    """Return the shared semantic identity for a goal, prerequisite, or topic.

    Concept identity is independent of adapter routing. Adapters answer whether a trusted example can support
    a topic; they must never rename a broad topic after one narrow formula (the live failure mapped an entire
    turbulence path to ``reynolds_number``). The alias vocabulary handles acronym/expanded-name equivalence;
    the final token key is deterministic.
    Possessives are normalized before tokenization so ``Kruskal's`` and ``Kruskal`` cannot become two topics.
    """
    raw = _re.sub(r"(?i)\b([a-z0-9]+)['’]s\b", r"\1", str(value or "")).strip()
    lowered = _re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()
    for key, aliases in _CONCEPT_ALIASES.items():
        if any(_re.search(rf"\b{_re.escape(alias)}\b", lowered) for alias in aliases):
            return key
    # Remove intent/role wording after possessive normalization. Keep a stable underscore key for metadata.
    tokens, _ = _subject_tokens(raw)
    return "_".join(sorted(tokens)) or _re.sub(r"\s+", "_", lowered)


def _topic_facet(topic: dict[str, Any]) -> str:
    ttype = str(topic.get("course_type") or topic.get("topic_type") or "").strip().lower()
    return "implementation" if ttype == "coding_implementation" else "core"


def _source_within_prereq(prereq: str, source: str) -> bool:
    """Directional same-concept test for prerequisite blocking.

    A prereq is circular only when a blocking SOURCE (the goal, or a taught topic's subject) names the SAME
    concept the prereq names — source tokens ⊆ prereq tokens (the prereq is the concept plus qualifier noise:
    'Key Laws Governing Turbulence' vs taught 'Laws of Turbulence'), identical despaced tokens, or acronym
    equivalence (BSTs ↔ binary search trees). A source with EXTRA distinctive tokens — goal 'bst traversal'
    vs prereq 'binary search trees' — is a skill ON the prereq's concept, and the structure IS the right
    prerequisite for the skill (user decision; live regression: the greedy 'bst' alias keyed the goal as
    binary_search_tree and key-equality blocked exactly the prereq the user asked for)."""
    pt, pd = _subject_tokens(prereq)
    st, sd = _subject_tokens(source)
    if not pt or not st:
        return False
    if st <= pt or (pd and pd == sd):
        return True
    def _deplural(x: str) -> str:
        return x[:-1] if x.endswith("s") and len(x) > 2 else x

    def _content_words(text: str) -> list[str]:
        # ORDERED framing-stripped words (goal 'Learn MST algorithms' → ['mst']) — raw text polluted the
        # compact/initialism comparison with intent words and never matched.
        return [w for w in _re.findall(r"[a-z0-9]+", str(text).lower())
                if w not in _SUBJECT_FRAMING_WORDS]

    pw, sw = _content_words(prereq), _content_words(source)
    p_compact = _deplural("".join(pw))
    s_compact = _deplural("".join(sw))
    p_init = "".join(w[0] for w in pw)
    s_init = "".join(w[0] for w in sw)
    return (len(s_compact) >= 2 and s_compact == p_init) or (len(p_compact) >= 2 and p_compact == s_init)


def _same_concept_evidence(a: str, b: str) -> bool:
    """Token-level evidence that two subjects sharing a canonical KEY are actually the same concept.

    Adapter-derived keys make this necessary: broad routing aliases give UNRELATED siblings the same key
    ('Defining Fluid Turbulence' / 'Laminar vs Turbulent Flow' / 'Reynolds Number' all route
    reynolds_number), and collapsing on the key alone silently deleted planned topics. Evidence = TWO+ shared
    content tokens (physics of turbulence / turbulence physics) or one-sided containment (turbulence /
    physics of turbulence) — a SINGLE shared generic token ('flow') is not evidence ('Energy Transfer in
    Turbulent Flows' vs 'Flow Regimes and Transition' share only 'flow' and are different lessons) — plus
    identical despaced token strings (quick sort / quicksort) and acronym equivalence (BFS / breadth-first
    search)."""
    ta, da = _subject_tokens(a)
    tb, db = _subject_tokens(b)
    if len(ta & tb) >= 2:
        return True
    if ta and tb and (ta <= tb or tb <= ta):
        return True
    if da and da == db:
        return True
    ca = _re.sub(r"[^a-z0-9]", "", str(a).lower())
    cb = _re.sub(r"[^a-z0-9]", "", str(b).lower())
    ia = "".join(w[0] for w in _re.findall(r"[a-z0-9]+", str(a).lower()))
    ib = "".join(w[0] for w in _re.findall(r"[a-z0-9]+", str(b).lower()))
    return (len(ca) >= 2 and ca == ib) or (len(cb) >= 2 and cb == ia)


# Overview-shaped topic types: fine as supporting topics, but the GOAL's own concept carried only by one of
# these means the path never teaches the goal in depth (depth guard, shadow-stamped in _certify_path_scope).
_OVERVIEW_TOPIC_TYPES = {"concept_intuition", "terminology_components", "compare_distinguish"}


# --- science_shape (science-architecture plan, Phase 2) ---------------------------------------------------
# A small internal planning field on science topics — NOT a new topic type. It selects which lesson grammar a
# science_mechanism topic should get (mechanism: cause-effect chain; regime: classification across a boundary;
# quantitative_relationship: formula + interpretation; model: resolved-vs-approximated tradeoffs). Stamped into
# scope_plan at certification (shadow — consumed by prompt/grammar wiring in a later increment).
_SCIENCE_SHAPE_MODEL_TOKENS = frozenset({
    "model", "models", "modeling", "modelling", "simulation", "simulations", "rans", "les", "dns", "closure",
})
_SCIENCE_SHAPE_REGIME_TOKENS = frozenset({"regime", "regimes", "versus", "vs", "transition"})
_SCIENCE_SHAPE_QUANT_TOKENS = frozenset({
    "number", "equation", "equations", "formula", "formulas", "law", "laws", "coefficient", "ratio",
    "calculate", "calculating", "calculation", "compute", "computing",
})


def _science_shape(topic: dict[str, Any], ttype: str, verified_example: str | None) -> str | None:
    """Classify a science topic's lesson grammar. Deterministic, from the topic's own plan fields.

    Order matters: model beats regime beats quantitative (a 'RANS vs LES' comparison is a MODEL lesson, not a
    regime one; 'Reynolds number' carries a verified formula AND names a quantity → quantitative). A verified
    adapter alone never forces quantitative — a broad mechanism topic may legitimately carry a supporting
    calculation without BEING a formula lesson (Physics of Turbulence + Reynolds calc)."""
    if ttype != "science_mechanism":
        return None
    text = " ".join([str(topic.get("title") or ""), *[str(s) for s in (topic.get("in_scope") or [])]]).lower()
    tokens = set(_re.findall(r"[a-z0-9]+", text))
    if tokens & _SCIENCE_SHAPE_MODEL_TOKENS:
        return "model"
    if (tokens & _SCIENCE_SHAPE_REGIME_TOKENS) or {"laminar", "turbulent"} <= tokens:
        return "regime"
    if verified_example and tokens & _SCIENCE_SHAPE_QUANT_TOKENS:
        return "quantitative_relationship"
    return "mechanism"


def _adapter_fits_owned_scope(adapter_slug: str, topic: dict[str, Any]) -> bool:
    """Return whether a verified adapter directly demonstrates this topic's owned learning delta.

    Routing aliases are intentionally permissive for discovery, so certification applies the stricter scope
    gate. This keeps a supporting calculation from displacing a broader mechanism or application lesson.
    """
    if adapter_slug != "reynolds_number":
        return True
    text = " ".join([
        str(topic.get("title") or ""),
        str(topic.get("subject_key") or ""),
        *[str(item) for item in (topic.get("in_scope") or [])],
        str(topic.get("learner_outcome") or ""),
        str(topic.get("expected_output") or ""),
    ]).lower()
    tokens = set(_re.findall(r"[a-z0-9]+", text))
    return (
        "reynolds" in tokens
        or "regime" in tokens
        or "regimes" in tokens
        or "classification" in tokens
        or "classify" in tokens
        or ({"laminar", "turbulent"} <= tokens)
    )

# Planning-field phrases that carry no content commitment — never worth backfilling into scope_in.
_GENERIC_SCOPE_PREFIXES = ("reach the capability", "general understanding")


def _backfill_scope_commitments(topic: dict[str, Any]) -> list[str]:
    """Deterministic scope_in fallback for a teaching topic whose plan carried no content commitments.

    Derived from the topic's own planning fields (learner_outcome / primary_capability / expected_output) —
    weak but honest commitments, so the lesson generator and validators always see at least one owned item.
    The synthetic 'Reach the capability: …' purpose default is excluded (it commits to nothing)."""
    out: list[str] = []
    title_low = " ".join(str(topic.get("title") or "").split()).strip().rstrip(".").lower()
    seen: set[str] = {title_low}  # a commitment that just restates the title commits to nothing
    for cand in (topic.get("learner_outcome"), topic.get("primary_capability"),
                 topic.get("expected_output"), topic.get("purpose")):
        s = " ".join(str(cand or "").split()).strip().rstrip(".")
        low = s.lower()
        if not s or low in seen or any(low.startswith(p) for p in _GENERIC_SCOPE_PREFIXES):
            continue
        seen.add(low)
        out.append(s)
        if len(out) >= 3:
            break
    return out


def _certify_path_scope(topics: list[dict[str, Any]], goal: str | None) -> list[dict[str, Any]]:
    """Make a single live scope plan authoritative over all topic-list transforms.

    The current lesson architecture represents a concept's walkthrough and implementation as two topic rows,
    so identity is ``canonical_concept_key + facet``. Certification drops duplicate rows with that identity,
    removes every prerequisite that overlaps the goal or a taught concept, and persists the decision into
    decomposition metadata for downstream generation/auditing.
    """
    if not topics:
        return topics
    goal_key = _canonical_concept_key(goal)
    seen: dict[tuple[str, str], list[str]] = {}   # identity -> subject strings kept under it
    seen_topic: dict[tuple[str, str], dict[str, Any]] = {}   # identity -> the FIRST surviving topic under it
    # (a dropped duplicate's own trace never persists — it's not in the output — so its reasoning is
    # recorded on the survivor instead, as "this topic absorbed X")
    # ONE verified exercise per adapter per path: distinct siblings may share an adapter via broad aliases
    # (turbulence trio → reynolds_number), but the learner must not do the identical verified calculation
    # in every lesson. The claim PREFERS the topic whose own subject IS the adapter's concept ('Reynolds
    # Number' beats an alias-matched 'Defining Fluid Turbulence'), else the first routed topic.
    we_claims: dict[str, int] = {}
    we_claim_exact: dict[str, int] = {}   # claim score: 2 exact-subject, 1 quantitative/regime shape, 0 alias
    we_routed: dict[int, str] = {}
    for i, t in enumerate(topics):
        tt = str(t.get("course_type") or t.get("topic_type") or "").strip().lower()
        if tt not in _WE_CENTRIC_TYPES or tt == "coding_implementation":
            continue
        try:
            from app.services.examples.trace_pipeline import route_adapter
            slug = getattr(route_adapter({"title": str(t.get("title") or ""),
                                          "subject_key": str(t.get("subject_key") or ""),
                                          "topic_type": tt, "course_type": tt}), "slug", None)
        except Exception:  # noqa: BLE001 — certification must never break generation
            slug = None
        if not slug:
            continue
        if not _adapter_fits_owned_scope(slug, t):
            _log.info("scope certification: rejected adapter %s for %r because it does not demonstrate "
                      "the topic's owned scope", slug, t.get("title"))
            record_topic_decision(t, "adapter.rejected", f"routing to {slug} rejected",
                                  "the routed adapter's worked example would not demonstrate this "
                                  "topic's own declared scope — routing alone is not enough")
            continue
        we_routed[i] = slug
        # claim preference: 2 = the topic's own subject IS the adapter's concept ('Reynolds Number');
        # 1 = a quantitative/regime-shaped lesson (the calculation is its point); 0 = alias-matched
        # mechanism/overview lesson. Ties keep the earliest topic. (Live: 'Physical Characteristics of
        # Turbulent Flows' — a mechanism lesson — outclaimed 'Flow Regimes and Transition' purely by order.)
        exact = _same_concept_evidence(str(t.get("subject_key") or t.get("title") or ""),
                                       slug.replace("_", " "))
        shape = _science_shape(t, tt, slug)
        score = 2 if exact else (1 if shape in ("quantitative_relationship", "regime") else 0)
        if slug not in we_claims or score > we_claim_exact[slug]:
            we_claims[slug] = i
            we_claim_exact[slug] = score
    certified: list[dict[str, Any]] = []
    taught_keys: set[str] = set()
    identities: list[dict[str, str]] = []
    for topic_idx, topic in enumerate(topics):
        ttype = str(topic.get("course_type") or topic.get("topic_type") or "").strip().lower()
        if ttype == "study_path_introduction":
            certified.append(topic)
            continue
        key = _canonical_concept_key(topic.get("subject_key") or topic.get("title"), ttype)
        facet = _topic_facet(topic)
        identity = (key, facet)
        subject_str = str(topic.get("subject_key") or topic.get("title") or "")
        if key and identity in seen:
            # Same canonical key ≠ same concept: adapter-derived keys collide across UNRELATED siblings via
            # broad routing aliases. Drop only with token-level evidence; otherwise both topics stand (the
            # shared adapter's worked example is deduplicated separately below).
            if any(_same_concept_evidence(subject_str, prev) for prev in seen[identity]):
                _log.info("scope certification: dropped duplicate identity %s/%s (%r)", key, facet,
                          topic.get("title"))
                survivor = seen_topic.get(identity)
                if survivor is not None:
                    # the dropped topic is never persisted, so its reason for being dropped is recorded on
                    # the topic that absorbed it instead — otherwise the decision is unrecoverable
                    record_topic_decision(
                        survivor, "identity.absorbed_duplicate", f"absorbed {topic.get('title')!r}",
                        "the dropped topic shared this topic's canonical key + facet AND showed token "
                        "evidence of being the same concept (not just the same adapter)",
                        canonical_concept_key=key, facet=facet, dropped_topic_type=ttype)
                continue
            _log.info("scope certification: KEPT %r — shares key %s/%s with %r but no token evidence of "
                      "the same concept (adapter-as-identity guard)", topic.get("title"), key, facet,
                      seen[identity][0])
            record_topic_decision(
                topic, "identity.kept_despite_shared_key", f"kept alongside {seen[identity][0]!r}",
                "shares canonical key + facet (usually: routes to the same adapter) with an earlier topic, "
                "but has NO token evidence of being the same concept — broad routing aliases give "
                "unrelated topics the same key, so key equality alone is not proof of duplication",
                canonical_concept_key=key, facet=facet)
            seen[identity].append(subject_str)
        elif key:
            seen[identity] = [subject_str]
            seen_topic[identity] = topic
        if key:
            taught_keys.add(key)
        meta = dict(topic.get("decomposition_metadata") or {})
        meta["canonical_concept_key"] = key
        meta["concept_facet"] = facet
        is_deep_teaching = ttype in (_METHOD_LESSON_TYPES | {"coding_implementation"})
        # EXAMPLE-PLAN certification (scope-plan increment #1): resolve at PLAN time which verified adapter —
        # if any — will back this topic's worked example, and record the policy. A WE-centric topic that
        # resolves NO adapter is stamped withhold_fabricated: the lesson ships honestly qualitative (no
        # essay-shaped pseudo-example) instead of fabricating steps (live failures: turbulence 'worked
        # example' = an essay chopped into steps; Navier-Stokes = unverified PDE prose as Step cards).
        we_centric = ttype in _WE_CENTRIC_TYPES or ttype == "coding_implementation"
        verified_example = None
        we_deduped_shared_adapter = False
        if ttype == "coding_implementation":
            # coding pairs share their adapter with the walkthrough legitimately — no claim contest
            try:
                from app.services.examples.trace_pipeline import route_adapter
                _a = route_adapter({"title": str(topic.get("title") or ""),
                                    "subject_key": str(topic.get("subject_key") or ""),
                                    "topic_type": ttype, "course_type": ttype})
                verified_example = getattr(_a, "slug", None)
            except Exception:  # noqa: BLE001 — certification must never break generation
                verified_example = None
        elif we_centric:
            slug = we_routed.get(topic_idx)
            if slug and we_claims.get(slug) == topic_idx:
                verified_example = slug
            elif slug:
                _log.info("scope certification: %r shares adapter %s with a sibling that claims it — "
                          "worked example withheld (one verified exercise per adapter per path)",
                          topic.get("title"), slug)
                we_deduped_shared_adapter = True
                _claimant = next((t2 for i2, t2 in enumerate(topics) if we_claims.get(slug) == i2), None)
                record_topic_decision(
                    topic, "adapter.claim_lost", f"worked example withheld ({slug})",
                    "another topic's own subject is a closer match for this adapter's concept (or was "
                    "routed first on a tie) — one verified exercise per adapter per path, so this topic "
                    "ships qualitative instead of repeating the identical calculation",
                    adapter=slug, claimed_by=str(_claimant.get("title")) if _claimant else None)
        # SCOPE COMMITMENTS (scope-plan #2 enforcement): an empty scope_in on a teaching topic means the plan
        # carries NO content commitments — the generator can ship a few generic cards and still "satisfy" the
        # blueprint (live: every topic on a thin turbulence path had scope_in=[]). The decomposition prompt now
        # REQUIRES non-empty in_scope; when the model still returns none, backfill deterministically from the
        # topic's own planning fields so downstream always sees at least one commitment. `scope_in_empty` keeps
        # recording the MODEL's behavior (pre-backfill) so telemetry can size prompt compliance.
        scope_in_empty = not (topic.get("in_scope") or [])
        scope_in_backfilled = False
        if scope_in_empty:
            _log.info("scope certification: EMPTY scope_in on teaching topic %r (%s) — no content commitments",
                      topic.get("title"), ttype)
            backfill = _backfill_scope_commitments(topic)
            if backfill:
                topic["in_scope"] = backfill
                scope_in_backfilled = True
                record_topic_decision(
                    topic, "scope.in_backfilled", f"in_scope <- {backfill}",
                    "the decomposition call left in_scope empty (no content commitments to validate the "
                    "lesson against) — backfilled deterministically from the topic's own planning fields "
                    "(learner_outcome / primary_capability / expected_output)")
        role = ("goal_core" if key == goal_key
                else ("application" if facet == "implementation" else "supporting"))
        shape = _science_shape(topic, ttype, verified_example)
        conceptual_mechanism = bool(
            we_centric and not verified_example and ttype == "science_mechanism" and shape == "mechanism"
        )
        meta["scope_plan"] = {
            "scope_in_empty": scope_in_empty,
            "scope_in_backfilled": scope_in_backfilled,
            "scope_in": list(topic.get("in_scope") or []),
            "scope_out": list(topic.get("out_of_scope") or []),
            "role": role,
            "depth": "deep" if key == goal_key or is_deep_teaching else "overview",
            "verified_example": verified_example,
            "we_policy": (
                "verified" if verified_example
                else ("conceptual_mechanism" if conceptual_mechanism
                      else ("withhold_fabricated" if we_centric else "not_applicable"))
            ),
        }
        if we_deduped_shared_adapter:
            meta["scope_plan"]["we_deduped_shared_adapter"] = True
        if shape:
            meta["scope_plan"]["science_shape"] = shape
        record_topic_decision(
            topic, "identity.assigned", f"canonical_concept_key={key!r} role={role}",
            "identity is adapter-routing-first (an adapter slug is the strongest catalog identity), else "
            "alias/token-derived — role is goal_core only when this key matches the GOAL's own key",
            facet=facet, is_goal_core=(role == "goal_core"))
        if verified_example:
            record_topic_decision(
                topic, "adapter.claimed", f"worked example verified via {verified_example}",
                "this topic's own subject is the closest match for the adapter's concept among any "
                "sibling routed to the same adapter (or the only one routed to it)")
        elif we_centric and not verified_example and not we_deduped_shared_adapter:
            record_topic_decision(
                topic, "adapter.none_routed", "we_policy = withhold_fabricated" if not conceptual_mechanism
                else "we_policy = conceptual_mechanism",
                "no adapter routes for this title/type at all — no verified worked example exists to "
                "attach, so the lesson ships honestly qualitative rather than an invented pseudo-example")
        # DEPTH GUARD (shadow): the goal's own concept taught only through an overview-shaped type means the
        # path never goes deep on the thing the learner asked for. Stamp + log; no behavior change yet.
        if role == "goal_core" and ttype in _OVERVIEW_TOPIC_TYPES:
            meta["scope_plan"]["depth_flag"] = "goal_core_overview_type"
            _log.info("scope certification: goal-core topic %r has overview type %s — depth flag stamped",
                      topic.get("title"), ttype)
            record_topic_decision(
                topic, "depth.flagged", "depth_flag = goal_core_overview_type",
                "this topic IS the goal's own concept, but its type only produces an overview-shaped "
                "blueprint (no process card, no worked-example slot) — the path never goes deep on the "
                "thing the learner asked for", topic_type=ttype)
        topic["decomposition_metadata"] = meta
        identities.append({"canonical_concept_key": key, "facet": facet,
                           "title": str(topic.get("title") or "")})
        certified.append(topic)

    # EXACTLY ONE GOAL CORE. Broad goals often decompose into distinct facets whose titles do not equal the
    # goal verbatim ("fluid turbulence" -> flow regimes, energy cascade, applications). In that case choose
    # the central deep mechanism deterministically. Never let several topics become goal_core merely because
    # a shared adapter routed them to the same formula slug.
    teaching_topics = [
        t for t in certified
        if str(t.get("course_type") or t.get("topic_type") or "").strip().lower()
        != "study_path_introduction"
    ]
    selected_goal_core: dict[str, Any] | None = None
    if teaching_topics:
        goal_tokens, _ = _subject_tokens(str(goal or ""))

        def _goal_core_score(item: dict[str, Any]) -> tuple[int, int, int, int]:
            meta = item.get("decomposition_metadata") or {}
            key = str(meta.get("canonical_concept_key") or "")
            ttype = str(item.get("course_type") or item.get("topic_type") or "").strip().lower()
            role = str(meta.get("content_role") or item.get("content_role") or "").strip().lower()
            title_tokens, _ = _subject_tokens(str(item.get("title") or item.get("subject_key") or ""))
            exact_goal = 1 if key and key == goal_key else 0
            mechanism = 2 if ttype == "science_mechanism" else (1 if role == "mechanism" else 0)
            overlap = len(goal_tokens & title_tokens)
            # Earlier topics win a true tie, keeping the result stable across runs.
            order = -int(item.get("order_index") or teaching_topics.index(item))
            return exact_goal, mechanism, overlap, order

        selected_goal_core = max(teaching_topics, key=_goal_core_score)
        _score = _goal_core_score(selected_goal_core)
        record_topic_decision(
            selected_goal_core, "goal_core.selected", "role -> goal_core, depth -> deep",
            "no topic's canonical identity matched the goal's own key exactly, so the central topic is "
            "chosen deterministically: exact-key match, then science_mechanism/mechanism-role type, then "
            "title/goal token overlap, then earliest order — this OVERRIDES whatever role the main "
            "certification pass assigned above" if not _score[0] else
            "this topic's canonical identity matches the goal's own key exactly",
            exact_goal_key_match=bool(_score[0]), mechanism_type_bonus=_score[1], goal_token_overlap=_score[2])
        for item in teaching_topics:
            meta = item.get("decomposition_metadata") or {}
            plan = meta.get("scope_plan") or {}
            item_type = str(item.get("course_type") or item.get("topic_type") or "").strip().lower()
            content_role = str(meta.get("content_role") or item.get("content_role") or "").strip().lower()
            if item is selected_goal_core:
                plan["role"] = "goal_core"
                plan["depth"] = "deep"
            else:
                plan["role"] = (
                    "application"
                    if content_role == "application" or "application" in item_type
                    else "supporting"
                )
                plan["depth"] = "deep" if plan["role"] == "application" else "overview"
            meta["scope_plan"] = plan
            item["decomposition_metadata"] = meta

    # SCOPE_OUT backfill (scope-plan #2, sibling boundaries): every scope_out came back empty live, so no
    # topic ever excluded its siblings' content and lessons overlapped freely (two turbulence topics both
    # taught fluctuations/vortices/Reynolds). Deterministic: a teaching topic with NO model-provided
    # out_of_scope inherits its siblings' scope_in commitments as explicit exclusions (its own commitments
    # excepted). Flows into the lean prompt's "Out of scope:" line; stamped for telemetry.
    for topic in certified:
        ttype = str(topic.get("course_type") or topic.get("topic_type") or "").strip().lower()
        if ttype == "study_path_introduction" or (topic.get("out_of_scope") or []):
            continue
        own = {" ".join(str(s).lower().split()) for s in (topic.get("in_scope") or [])}
        # token view of the topic's OWN content, so a sibling commitment that merely REPHRASES it is never
        # copied in as an exclusion (live: a topic's scope_out contained a sentence-level restatement of its
        # own scope_in — the lesson was told its own subject was out of scope)
        own_tokens: set[str] = set()
        for s in [str(topic.get("title") or ""), *[str(x) for x in (topic.get("in_scope") or [])]]:
            own_tokens |= _subject_tokens(s)[0]
        sibling_scope: list[str] = []
        for other in certified:
            if other is topic:
                continue
            for item in other.get("in_scope") or []:
                norm = " ".join(str(item).lower().split())
                if not norm or norm in own or norm in {" ".join(s.lower().split()) for s in sibling_scope}:
                    continue
                item_tokens = _subject_tokens(str(item))[0]
                overlap = len(item_tokens & own_tokens)
                if item_tokens and overlap >= max(2, (len(item_tokens) + 1) // 2):
                    continue                               # semantically the topic's own content
                sibling_scope.append(str(item).strip())
        if sibling_scope:
            topic["out_of_scope"] = sibling_scope[:6]
            plan = ((topic.get("decomposition_metadata") or {}).get("scope_plan") or {})
            if plan:
                plan["scope_out"] = list(topic["out_of_scope"])
                plan["scope_out_backfilled"] = True
            record_topic_decision(
                topic, "scope.out_backfilled", f"out_of_scope <- {topic['out_of_scope']}",
                "the model left out_of_scope empty — inherited siblings' scope_in commitments as explicit "
                "exclusions (own content, detected by token overlap, is never copied in) so sibling "
                "lessons don't silently overlap")

    blocked_prereq_keys = taught_keys | ({goal_key} if goal_key else set())
    # SOURCE strings for directional blocking: raw key equality over-blocked (the greedy 'bst' alias keyed
    # goal 'bst traversal' as binary_search_tree, deleting the 'binary search trees' prereq the user asked
    # for) and raw key-token superset under-described the sources. A prereq is dropped only when the GOAL or
    # a TAUGHT SUBJECT is within it per _source_within_prereq — a source with extra distinctive tokens is a
    # skill ON the prereq's concept and never blocks it.
    block_sources = [str(goal or "")] + [i["title"] for i in identities if i.get("title")]
    for topic in certified:
        ttype = str(topic.get("course_type") or topic.get("topic_type") or "").strip().lower()
        prereqs: list[Any] = []
        seen_prereq_keys: set[str] = set()
        for prereq in topic.get("assumed_prerequisites") or []:
            prereq_key = _canonical_concept_key(prereq)
            if not prereq_key or prereq_key in seen_prereq_keys:
                continue
            blocker = next((s for s in block_sources if _source_within_prereq(str(prereq), s)), None)
            if blocker is not None:
                _log.info("scope certification: dropped prereq %r — same concept as %r (goal/taught)",
                          prereq, blocker)
                record_topic_decision(
                    topic, "prerequisite.blocked", f"dropped {prereq!r}",
                    f"{blocker!r} (the goal or a taught topic) IS this prerequisite's concept, not just a "
                    "skill applied to it — directional check: a source with EXTRA distinctive tokens "
                    "('bst traversal' vs prereq 'binary search trees') is a skill ON the concept and would "
                    "never block it", blocked_by=blocker)
                continue
            prereqs.append(prereq)
            seen_prereq_keys.add(prereq_key)
        topic["assumed_prerequisites"] = prereqs
        if ttype != "study_path_introduction":
            continue
        meta = dict(topic.get("decomposition_metadata") or {})
        meta["brief_refresh_prerequisites"] = [
            p for p in (meta.get("brief_refresh_prerequisites") or [])
            if _canonical_concept_key(p) not in blocked_prereq_keys
        ]
        meta["path_scope_plan"] = {
            "goal_canonical_concept_key": goal_key,
            "concept_identities": identities,
            "prerequisite_keys": [
                _canonical_concept_key(p) for p in topic.get("assumed_prerequisites", [])
            ],
        }
        topic["decomposition_metadata"] = meta

    # Consolidate every decision recorded onto ANY certified topic across this whole function — including
    # decisions recorded on a topic from a LATER loop iteration processing a DIFFERENT topic (e.g. an
    # absorbed duplicate's note lands on the survivor, which may already be past its own decomposition_
    # metadata assignment) — into the SAME decision_trace list decomposition already started. One pass at
    # the very end catches every case correctly regardless of which loop above recorded it.
    for topic in certified:
        trace = take_topic_trace(topic)
        if trace:
            meta = dict(topic.get("decomposition_metadata") or {})
            meta["decision_trace"] = list(meta.get("decision_trace") or []) + trace
            topic["decomposition_metadata"] = meta

    for i, topic in enumerate(certified, 1):
        topic["order_index"] = i
    return certified


def _path_domain_tokens(topics: list[dict[str, Any]]) -> frozenset[str]:
    """The path's DOMAIN words — qualifiers that don't distinguish one algorithm from another, so the
    SAME algorithm normalizes to ONE subject whether or not a given title includes the domain word
    ('Implementing Prim's MST' and 'Implementing Prim's Algorithm in Code' both -> 'prim'). Two signals:
    (1) an all-caps ACRONYM (MST/BST/DFS) — a domain abbreviation inconsistently sprinkled into titles;
    (2) a token appearing in a MAJORITY of titles. `_subject_tokens` falls back to the un-stripped
    tokens if stripping would EMPTY a subject, so a path whose only subject IS the acronym (DFS vs BFS)
    or word (Quick Sort) is unharmed."""
    n = len(topics)
    acronyms: set[str] = set()
    counts: dict[str, int] = {}
    for t in topics:
        title = str(t.get("title") or "")
        for ac in _re.findall(r"\b[A-Z]{2,}\b", title):
            acronyms.add(ac.lower())
        for tok in {_stem(x) for x in _re.findall(r"[a-z0-9]+", title.lower())
                    if x not in _SUBJECT_FRAMING_WORDS}:
            counts[tok] = counts.get(tok, 0) + 1
    common: set[str] = set()
    if n >= 3:
        threshold = max(3, (n + 1) // 2)
        common = {tok for tok, c in counts.items() if c >= threshold}
    return frozenset(acronyms | common)


def _drop_same_type_subject_duplicates(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Backstop for the topic-prompt rule: never keep two topics of the same one-per-subject type
    (algorithm_walkthrough / data_structure_operation / coding_implementation) that cover the SAME
    subject. Keeps the first occurrence, drops later duplicates — e.g. a '...Process Overview'
    walkthrough alongside a '...Step by Step' walkthrough for the same algorithm. Equality-based so
    distinct subjects (binary search vs binary search tree) and distinct approaches (iterative vs
    recursive) are preserved. Never empties the path."""
    domain = _path_domain_tokens(topics)
    seen: list[tuple[str, frozenset[str], str]] = []  # (topic_type, token_set, despaced)
    kept: list[dict[str, Any]] = []
    for topic in topics:
        ttype = str(topic.get("course_type") or topic.get("topic_type") or "").strip().lower()
        if ttype in _ONE_PER_SUBJECT_TYPES:
            tset, despaced = _subject_tokens(topic.get("title"), domain)
            if despaced and any(
                st == ttype and (ts == tset or ds == despaced) for (st, ts, ds) in seen
            ):
                _log.info("topic_generator: dropping same-subject duplicate %r (%s)",
                          topic.get("title"), ttype)
                survivor = next((k for k in kept
                                 if str(k.get("course_type") or k.get("topic_type") or "").strip().lower()
                                 == ttype and _subject_tokens(k.get("title"), domain)[1] == despaced), None)
                if survivor is not None:
                    record_topic_decision(
                        survivor, "dedup.same_subject_same_type_collapsed",
                        f"absorbed {topic.get('title')!r}",
                        f"another {ttype} topic covered the identical subject (e.g. '...Process Overview' "
                        "beside '...Step by Step' for the same algorithm) — first occurrence kept")
                continue
            if despaced:
                seen.append((ttype, tset, despaced))
        kept.append(topic)
    return kept or topics  # never drop everything


# Full "method lesson" types — each independently emits a background + process + worked-example + practice
# lesson. Two of these for the SAME subject duplicate each other: a process_walkthrough AND a
# problem_solving_application of "completing the square" produce the same steps AND the same worked example, so
# the learner reads the lesson twice ("topics other than intro feel very similar"). coding_implementation
# (a legit teach-then-code follow-up) and concept_intuition (intuition before mechanics) are deliberately NOT
# in this set — those are valid same-subject companions, not duplicates.
_METHOD_LESSON_TYPES = frozenset({
    "process_walkthrough", "algorithm_walkthrough", "data_structure_operation", "problem_solving_application",
    # math/science full-method lessons — each emits its own background + method + worked-example + practice, so
    # two of the same subject duplicate (and the domain gate REMAPS math method topics TO math_formula_method,
    # so a math path's duplicated method + application pair only both count once this is here).
    "math_formula_method", "proof_reasoning", "science_mechanism",
})
# When several method lessons share a subject, keep the one that TEACHES the method (a walkthrough) over one
# that merely applies/examples it; ties keep the earlier topic.
_METHOD_LESSON_PRIORITY = {
    "algorithm_walkthrough": 3, "data_structure_operation": 3, "process_walkthrough": 3,
    "math_formula_method": 3, "proof_reasoning": 3, "science_mechanism": 3,
    "problem_solving_application": 1,
}


def _collapse_same_subject_method_topics(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A single simple procedure often gets decomposed into TWO full method lessons of DIFFERENT types (e.g. a
    process_walkthrough AND a problem_solving_application of the same subject). Both regenerate the same
    background, steps, and worked example — pure duplication. Keep the method-teaching topic per subject
    (walkthrough > application; ties keep the earlier), drop the same-subject duplicates. Complements
    _drop_same_type_subject_duplicates, which only collapses SAME-type pairs. Never empties the path."""
    domain = _path_domain_tokens(topics)

    def _tt(t: dict[str, Any]) -> str:
        return str(t.get("course_type") or t.get("topic_type") or "").strip().lower()

    winner_by_subject: dict[str, int] = {}  # subject-key -> index of the topic kept so far
    drop_idx: set[int] = set()
    for idx, t in enumerate(topics):
        if _tt(t) not in _METHOD_LESSON_TYPES:
            continue
        _, subj = _subject_tokens(t.get("title"), domain)
        if not subj:
            continue
        prev = winner_by_subject.get(subj)
        if prev is None:
            winner_by_subject[subj] = idx
            continue
        cur_pri = _METHOD_LESSON_PRIORITY.get(_tt(t), 2)
        prev_pri = _METHOD_LESSON_PRIORITY.get(_tt(topics[prev]), 2)
        loser, keeper = (prev, idx) if cur_pri > prev_pri else (idx, prev)
        drop_idx.add(loser)
        winner_by_subject[subj] = keeper
        _log.info("topic_generator: collapsed same-subject method topic %r (kept %r)",
                  topics[loser].get("title"), topics[keeper].get("title"))
        record_topic_decision(
            topics[keeper], "dedup.same_subject_method_collapsed",
            f"absorbed {topics[loser].get('title')!r} ({_tt(topics[loser])})",
            "two full 'method lesson' types (walkthrough / application / mechanism) shared a subject and "
            "would have regenerated the same background, steps, and worked example — the method-TEACHING "
            "type wins over one that merely applies/exemplifies it")
    if not drop_idx:
        return topics
    kept = [t for i, t in enumerate(topics) if i not in drop_idx]
    return kept or topics


_CODE_ABLE_TYPES = frozenset({"algorithm_walkthrough", "data_structure_operation"})
_NO_CODE_GOAL_MARKERS = ("no code", "without code", "no coding", "conceptual only", "concept only",
                         "theory only", "no programming")

# Topic types that concretely TEACH a subject (so its concept is a target of the path, not a prerequisite).
_TEACHING_TYPES = frozenset({"algorithm_walkthrough", "data_structure_operation", "coding_implementation",
                             "process_walkthrough", "worked_example"})
# Prerequisite classification (intro consolidation). A prereq is ASSUMED (a whole skill/topic — silent now,
# linked to its own study path later) or GLOSSED (a single statement — a fact/definition/notation/formula —
# stated in one intro line). The test is STRUCTURAL ("is P a statement or a skill/topic?"), not a fuzzy guess
# about what the learner knows. `_ASSUMED_FOUNDATIONS` = broad upstream skills we always assume; a title naming
# a specific form/notation/theorem is a STATEMENT -> gloss; the safe default is gloss.
_ASSUMED_FOUNDATIONS = frozenset({
    "arithmetic", "algebra", "algebraic", "quadratic", "quadratics", "factoring", "factorization",
    "exponent", "exponents", "fraction", "fractions", "polynomial", "polynomials", "function", "functions",
    "variable", "variables", "equation", "equations", "expression", "expressions", "inequality", "inequalities",
    "integer", "integers", "ratio", "ratios", "proportion", "proportions", "logarithm", "logarithms",
    "trigonometry", "geometry", "coordinate", "coordinates", "vector", "vectors", "matrix", "matrices",
    "probability", "statistics", "graph", "graphs", "array", "arrays", "loop", "loops", "recursion",
})
_STATEMENT_MARKERS = ("form", "formula", "notation", "convention", "theorem", "identity", "coefficient",
                      "property", " rule", "definition of", "law of")


def _stem(tok: str) -> str:
    """Light stemmer so "completing"/"complete" and "equations"/"equation" collapse to one subject key."""
    for suf in ("ing", "ed", "es"):
        if len(tok) > len(suf) + 2 and tok.endswith(suf):
            tok = tok[: -len(suf)]
            break
    if len(tok) > 3 and tok.endswith("s"):
        tok = tok[:-1]
    if len(tok) > 3 and tok.endswith("e"):
        tok = tok[:-1]
    return tok


def _stem_subject_set(title: str, domain: frozenset[str]) -> frozenset[str]:
    return frozenset(_stem(t) for t in _subject_tokens(title, domain)[0])


def _classify_prerequisite(title: str) -> str:
    """ASSUME (a whole skill/topic) vs GLOSS (a single statement). Structural, not a knowledge guess: a title
    naming a specific form / notation / theorem / coefficient convention is a statement -> gloss; a broad
    foundation skill -> assume; default gloss (a stray line never hurts; a wrongly-assumed skill strands a
    learner, and assumed skills are linked out anyway)."""
    t = str(title or "").lower()
    if any(m in t for m in _STATEMENT_MARKERS):
        return "gloss"
    words = set(_re.findall(r"[a-z]+", t))
    return "assume" if (words & _ASSUMED_FOUNDATIONS) else "gloss"


def _subject_phrase(title: str) -> str:
    """A readable subject from a title (framing words removed) — e.g. 'Trace Quick Sort Algorithm
    Step by Step' -> 'Quick Sort'. Used to title the synthesized coding topic.

    Hyphenated compounds are ONE token: splitting "In-Order Traversal" made the leading "In" hit the
    framing stopword "in", titling the coding topic "Implementing Order Traversal" (live bug — which
    then also failed adapter routing, so the topic shipped unverified LLM code). A hyphenated token is
    dropped only when EVERY part is a framing word ("Step-by-Step" goes; "In-Order" stays). The space
    form "In Order Traversal" fuses to the compound too (never prepositional "in order to")."""
    fused = _re.sub(r"\b([Ii]n)[ _]([Oo]rder)\b(?!\s+[Tt]o\b)", r"\1-\2", str(title or ""))
    words = []
    for w in _re.findall(r"[A-Za-z0-9']+(?:-[A-Za-z0-9']+)*", fused):
        if all(part in _SUBJECT_FRAMING_WORDS for part in w.lower().split("-")):
            continue
        words.append(w)
    return " ".join(words).strip() or str(title or "").strip()


# Canonical member sets for common SURVEY/FAMILY goals. The decomposition LLM under-generates these (it
# folds "another sort" as a redundant delta), and the rest of the pipeline is SUBTRACTIVE — nothing backfills
# a missing member. This table + _expand_canonical_family inject them deterministically, exactly like
# _append_missing_coding_topics backfills coding topics. Every listed member has a VERIFIED adapter, so an
# injected topic ships verified content. (title = the injected walkthrough subject; slug = its adapter.)
_CANONICAL_FAMILIES: dict[str, dict[str, Any]] = {
    "sorting": {
        "goal_markers": ("sorting algorithm", "sorting algorithms", "learn sorting", "sorting method",
                         "sorting technique", "comparison-based sorting", "comparison based sorting",
                         "how sorting works"),
        "members": [("Bubble Sort", "bubble_sort"), ("Selection Sort", "selection_sort"),
                    ("Insertion Sort", "insertion_sort"), ("Merge Sort", "merge_sort"),
                    ("Quicksort", "quick_sort")],
        "display": "Sorting Algorithms",
    },
    "graph_traversal": {
        "goal_markers": ("graph traversal", "graph traversals", "traverse a graph", "traversing a graph"),
        "members": [("Breadth-First Search", "bfs"), ("Depth-First Search", "dfs_iter")],
        "display": "Graph Traversals",
    },
    # Live failure: a "bst traversal" path shipped only in/post/pre-order — the model under-generates and
    # nothing backfilled Level-Order. Every member routes to a verified tree adapter with canonical code.
    "tree_traversal": {
        "goal_markers": ("bst traversal", "binary search tree traversal", "tree traversal", "tree traversals",
                         "binary tree traversal", "traversing a tree", "traversing a bst", "traverse a bst"),
        "members": [("In-Order Traversal", "tree_inorder"), ("Pre-Order Traversal", "tree_preorder"),
                    ("Post-Order Traversal", "tree_postorder"), ("Level-Order Traversal", "tree_levelorder")],
        "display": "Tree Traversal Orders",
    },
    # Live gap: an "mst algorithms" path had no registered family, so no WT→impl pairing/consolidation ran
    # (Implementing Kruskal at [4], Comparing wedged at [5], Implementing Prim at [6]).
    "mst": {
        "goal_markers": ("mst algorithm", "mst algorithms", "minimum spanning tree", "minimum spanning trees",
                         "spanning tree algorithm", "spanning tree algorithms"),
        "members": [("Kruskal's Algorithm", "kruskal"), ("Prim's Algorithm", "prim")],
        "display": "MST Algorithms",
    },
}

# A member counts as already TAUGHT only by a walkthrough or coding topic — NOT a compare/concept topic that
# merely NAMES it in its title. ("Comparing Quick Sort and Merge Sort" routes to merge_sort but does not
# teach it; counting it as present made the expansion skip the real merge-sort walkthrough.)
_MEMBER_TEACHING_TYPES = frozenset({"algorithm_walkthrough", "data_structure_operation",
                                    "coding_implementation"})


def _expand_canonical_family(topics: list[dict[str, Any]], goal: str | None) -> list[dict[str, Any]]:
    """Deterministically ensure a FAMILY SURVEY covers its canonical members. When the goal surveys a known
    family (sorting, graph traversal), the decomposition LLM emits only 1-2 members and the subtractive
    pipeline can't backfill the rest — so this injects the missing canonical members as walkthrough topics
    (each then gets a coding follow-up + routes to its verified adapter). Mirrors _append_missing_coding_topics.
    Presence is detected by ROUTING each title to an adapter slug (robust to title variants). GUARDED: only
    expands a family the path ALREADY teaches >=1 member of, so it never injects into an unrelated path.
    Off via AZALEA_CANONICAL_FAMILY_EXPANSION=0."""
    if os.getenv("AZALEA_CANONICAL_FAMILY_EXPANSION", "1") == "0":
        return topics
    g = (goal or "").lower()
    fam = next((f for f in _CANONICAL_FAMILIES.values() if any(m in g for m in f["goal_markers"])), None)
    if not fam:
        return topics
    try:
        from app.services.examples.trace_pipeline import route_adapter
    except Exception:  # noqa: BLE001 — expansion must never break topic generation
        return topics

    def _ttype(t: dict[str, Any]) -> str:
        return str(t.get("course_type") or t.get("topic_type") or "").strip().lower()

    def _slug(t: dict[str, Any]) -> Optional[str]:
        a = route_adapter({"title": str(t.get("title") or ""), "subject_key": str(t.get("subject_key") or ""),
                           "topic_type": _ttype(t)})
        return a.slug if a else None

    present = {slug for t in topics if _ttype(t) in _MEMBER_TEACHING_TYPES
               for slug in [_slug(t)] if slug}
    member_slugs = {slug for _, slug in fam["members"]}
    template = next((t for t in topics if _ttype(t) == "algorithm_walkthrough"), None)
    result = list(topics)
    if not (present & member_slugs):
        # ZERO members (requirements-first live regression): the model folded the WHOLE family into one
        # umbrella topic ("BST Traversal Methods" + "Implementing BST Traversal"), so the old >=1-member
        # guard blocked injection exactly when it mattered most. The goal already names the family (markers
        # matched); require an in-path UMBRELLA topic as evidence, inject the full canonical set, and drop
        # the umbrella walkthrough/coding topics (each member now owns its slice of their content).
        fam_words = {w for name, _ in fam["members"] for w in name.lower().replace("-", " ").split()
                     if len(w) >= 4}
        fam_words |= {w for w in str(fam.get("display") or "").lower().split() if len(w) >= 4}

        def _is_umbrella(t: dict[str, Any]) -> bool:
            title_words = set(str(t.get("title") or "").lower().replace("-", " ").split())
            return (_ttype(t) in _MEMBER_TEACHING_TYPES and bool(fam_words & title_words)
                    and _slug(t) is None)

        umbrellas = [t for t in result if _is_umbrella(t)]
        if not umbrellas:
            return topics                       # no in-path evidence of the family — do not inject
        template = next((t for t in umbrellas if _ttype(t) == "algorithm_walkthrough"), template)
        drop = {id(t) for t in umbrellas}
        result = [t for t in result if id(t) not in drop]
        _log.info("canonical-family expansion: zero members — dropped %d umbrella topic(s) %s and "
                  "injecting the full canonical set", len(umbrellas),
                  [str(t.get("title")) for t in umbrellas])
        _dropped_umbrella_titles = [str(t.get("title")) for t in umbrellas]
    else:
        _dropped_umbrella_titles = None
    for member_title, slug in fam["members"]:
        if slug in present:
            continue
        new = dict(template) if template else {}
        new.pop("topic_id", None)
        new.pop("id", None)
        new.pop("_decision_trace", None)   # a fresh injected topic gets its OWN trace, not the template's
        new.update({
            # BARE canonical name — matches how model-emitted siblings are titled ("Inorder Traversal"); the
            # old " Algorithm Walkthrough" suffix made injected members read inconsistently (live complaint).
            "title": member_title,
            "course_type": "algorithm_walkthrough", "topic_type": "algorithm_walkthrough",
            # OWN unit — cloning the template's unit filed the injected Level-Order under the In-Order unit,
            # so the UI (which groups by unit) rendered it "grouped in with inorder" (live complaint).
            "subject_key": slug, "secondary_course_types": [],
            "unit_title": member_title,
            "learner_outcome": f"The learner can trace {member_title} step by step on a concrete input.",
            "purpose": f"Trace {member_title} on a concrete input to see how the algorithm works.",
            "in_scope": [f"Tracing {member_title} on a concrete input"],
            "out_of_scope": [], "prerequisite_topics": [], "source_refs": [],
        })
        result.append(new)
        present.add(slug)
        _log.info("canonical-family expansion: injected %r (survey backfill for goal %r)",
                  new["title"], goal)
        record_topic_decision(
            new, "family.member_injected", f"synthesized {member_title!r}",
            (f"the model folded the whole family survey into umbrella topic(s) {_dropped_umbrella_titles} "
             "(now removed) — every canonical member is injected fresh so each owns its own slice"
             if _dropped_umbrella_titles else
             "the goal names a registered family survey and this canonical member was missing from the "
             "model's plan — the deterministic backfill fills the gap so the survey stays complete"),
            family=fam.get("display"), adapter=slug)
    return result


def _order_canonical_family(topics: list[dict[str, Any]], goal: str | None) -> list[dict[str, Any]]:
    """Group a family survey's topics into CANONICAL ORDER, each walkthrough immediately followed by its
    coding follow-up (bubble WT, bubble code, selection WT, selection code, ...). The expansion + coding
    backfill append injected members out of order (the observed scramble: insertion's code stranded at the
    end); this consolidates the family into a coherent sequence. Non-family topics (intro) keep their order."""
    if os.getenv("AZALEA_CANONICAL_FAMILY_EXPANSION", "1") == "0":
        return topics
    g = (goal or "").lower()
    fam = next((f for f in _CANONICAL_FAMILIES.values() if any(m in g for m in f["goal_markers"])), None)
    if not fam:
        return topics
    try:
        from app.services.examples.trace_pipeline import route_adapter
    except Exception:  # noqa: BLE001
        return topics
    order = {slug: i for i, (_, slug) in enumerate(fam["members"])}

    def _ttype(t: dict[str, Any]) -> str:
        return str(t.get("course_type") or t.get("topic_type") or "").strip().lower()

    def _slug(t: dict[str, Any]) -> Optional[str]:
        a = route_adapter({"title": str(t.get("title") or ""), "subject_key": str(t.get("subject_key") or ""),
                           "topic_type": _ttype(t)})
        return a.slug if a else None

    canon = {slug: name for name, slug in fam["members"]}
    # ORPHAN-IMPLEMENTATION REPAIR: a coding follow-up whose subject key was mangled upstream routes to NO
    # adapter and strands outside the family block, while its walkthrough sits partnerless (live: topic 2
    # 'In-Order Traversal' with no implementation + topic 9 'Implementing Order Traversal' with we=None,
    # dumped after the family). One orphan + one partnerless walkthrough = an unambiguous pair: retitle the
    # orphan to the canonical 'Implementing <name>' so it routes, orders, and inherits the pair's unit.
    wt_slugs = {_slug(t) for t in topics if _ttype(t) == "algorithm_walkthrough"} & set(order)
    impl_slugs = {_slug(t) for t in topics if _ttype(t) == "coding_implementation"} & set(order)
    partnerless = wt_slugs - impl_slugs
    orphans = [t for t in topics
               if _ttype(t) == "coding_implementation" and _slug(t) is None
               and str(t.get("title") or "").lower().startswith("implementing")]
    if len(partnerless) == 1 and len(orphans) == 1:
        slug = next(iter(partnerless))
        _orphan_old_title = orphans[0].get("title")
        orphans[0]["title"] = f"Implementing {canon[slug]}"
        orphans[0]["unit_title"] = canon[slug]
        _log.info("topic_generator: paired orphan implementation with partnerless walkthrough %s -> %r",
                  slug, orphans[0]["title"])
        record_topic_decision(
            orphans[0], "family.orphan_paired", f"title -> {orphans[0]['title']!r}",
            "this coding topic's subject key was mangled upstream so it routed to NO adapter and sat "
            "outside the family block, while exactly one walkthrough had no implementation partner — an "
            "unambiguous pair; retitled to the canonical form so it now routes and orders correctly",
            original_title=_orphan_old_title, paired_with=canon[slug])

    fam_positions = [i for i, t in enumerate(topics)
                     if _ttype(t) in _MEMBER_TEACHING_TYPES and _slug(t) in order]
    if len(fam_positions) < 2:
        return topics
    fam_block = sorted((topics[i] for i in fam_positions),
                       key=lambda t: (order.get(_slug(t), 99), 0 if _ttype(t) != "coding_implementation" else 1))
    # Consistent titles across the family (deterministic backstop for the decomposition prompt): every
    # walkthrough member reads the SAME way — the BARE canonical name ("In-Order Traversal", "Merge Sort") —
    # so a study-verb the LLM sprinkled on one ("Analyzing Quick Sort") or an injected suffix ("Level-Order
    # Traversal Algorithm Walkthrough" beside "Inorder Traversal" — live inconsistency) never survives.
    for t in fam_block:
        s = _slug(t)
        if s not in canon:
            continue
        if _ttype(t) == "algorithm_walkthrough":
            t["title"] = canon[s]
            # The pair's UNIT is the CONCEPT name — the model sometimes names the unit after the follow-up
            # ("Implementing Kruskal's Algorithm"), filing the conceptual walkthrough under an
            # "Implementing…" header (live). The implementation inherits this below (pair coherence).
            t["unit_title"] = canon[s]
        elif _ttype(t) == "coding_implementation":
            t["title"] = f"Implementing {canon[s]}"     # consistent — never "…in Code" on some, bare on others
    # UNIT coherence per pair: an implementation shares its WALKTHROUGH partner's unit (the coding backfill
    # files synthesized topics under the first coding unit it finds, which put "Implementing Level-Order
    # Traversal" inside the Inorder unit — the UI groups by unit, so the pair rendered under the wrong header).
    last_wt_unit: str | None = None
    for t in fam_block:
        if _ttype(t) == "algorithm_walkthrough":
            last_wt_unit = str(t.get("unit_title") or "").strip() or None
        elif _ttype(t) == "coding_implementation" and last_wt_unit:
            t["unit_title"] = last_wt_unit
    first, famset = fam_positions[0], set(fam_positions)
    result: list[dict[str, Any]] = []
    for i, t in enumerate(topics):
        if i in famset:
            if i == first:
                result.extend(fam_block)      # drop the whole ordered family block in at the first slot
        else:
            result.append(t)
    for i, t in enumerate(result, 1):
        t["order_index"] = i
    return result


def _fix_intro_prefixed_units(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A TEACHING topic filed under an 'Introduction to X' unit header reads backwards (live: the intro sat
    under 'Core Concepts' while the main 'Fluid Turbulence' lesson sat under 'Introduction to Fluid
    Turbulence'). A non-intro topic whose unit starts with an intro prefix takes its own title as the unit."""
    for t in topics:
        ttype = str(t.get("course_type") or t.get("topic_type") or "").strip().lower()
        if ttype == "study_path_introduction":
            continue
        unit = str(t.get("unit_title") or "").strip()
        if unit.lower().startswith(("introduction to ", "intro to ")):
            t["unit_title"] = str(t.get("title") or "").strip() or unit
    return topics


# Types whose lesson is BUILT AROUND a worked example — only these can be "the identical exercise twice".
# concept_intuition/terminology/compare topics have NO worked-example slot in their blueprints: they must never
# claim an adapter slug here (live regression: 'Turbulence and Its Definitions' (concept_intuition) routed via
# the broad 'turbulence' alias, claimed reynolds_number FIRST, and shadowed the mechanism/formula topics — the
# path shipped with NO worked example at all).
_WE_CENTRIC_TYPES = frozenset({
    "math_formula_method", "process_walkthrough", "problem_solving_application",
    "algorithm_walkthrough", "data_structure_operation", "science_mechanism", "proof_reasoning",
})


def _drop_same_adapter_duplicate_topics(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Two WORKED-EXAMPLE-CENTRIC, non-coding topics that route to the SAME adapter generate the same KIND of
    verified worked example — the learner does the identical exercise twice with different numbers (live: a
    depreciation path's 'Straight-Line Depreciation Formula' AND 'Applying Straight-Line Depreciation' both
    routed to depreciation_schedule and both built a book-value schedule). Keep the FIRST, drop the repeats.
    Exempt: coding topics (teach-then-code pairs share an adapter legitimately) and every non-WE-centric type
    (no worked-example slot -> can neither duplicate an exercise nor claim the slug)."""
    try:
        from app.services.examples.trace_pipeline import route_adapter
    except Exception:  # noqa: BLE001 — never break topic generation
        return topics

    def _ttype(t: dict[str, Any]) -> str:
        return str(t.get("course_type") or t.get("topic_type") or "").strip().lower()

    seen: dict[str, str] = {}
    kept: list[dict[str, Any]] = []
    for t in topics:
        ttype = _ttype(t)
        if ttype not in _WE_CENTRIC_TYPES or ttype == "coding_implementation":
            kept.append(t)
            continue
        a = route_adapter({"title": str(t.get("title") or ""), "subject_key": str(t.get("subject_key") or ""),
                           "topic_type": ttype, "course_type": ttype})
        slug = getattr(a, "slug", None)
        title = str(t.get("title") or "")
        # Drop only with token evidence the topics are the SAME concept — broad aliases give unrelated
        # siblings one adapter (turbulence trio → reynolds_number), and those must all survive; the
        # certifier separately withholds the repeated verified exercise on the later ones.
        if slug and slug in seen and _same_concept_evidence(title, seen[slug]):
            _log.info("topic_generator: dropped %r — same adapter (%s) as %r, identical worked-example kind",
                      t.get("title"), slug, seen[slug])
            survivor = next((k for k in kept if str(k.get("title")) == seen[slug]), None)
            if survivor is not None:
                record_topic_decision(
                    survivor, "dedup.same_adapter_worked_example_collapsed", f"absorbed {t.get('title')!r}",
                    f"routes to the SAME adapter ({slug}) with token evidence of being the same concept — "
                    "the learner would do the identical exercise twice with different numbers")
            continue
        if slug and slug not in seen:
            seen[slug] = title
        kept.append(t)
    return kept


def _ensure_family_comparison_topic(topics: list[dict[str, Any]], goal: str | None) -> list[dict[str, Any]]:
    """Deterministic COMPARISON topic for a family survey (user-endorsed: 'Comparing MST Algorithms' — but it
    only appeared when the decomposition model chose to emit one; the prompt has no comparison guidance, so
    sibling surveys like bst-traversal never got theirs). When the goal surveys a registered family AND the
    path teaches >=2 distinct members AND no compare_distinguish topic exists, append one LAST — a comparison
    is only teachable after every alternative has been taught. `compare_distinguish` is a UNIVERSAL type
    (allowed on every domain), so this never fights the domain gate."""
    if os.getenv("AZALEA_CANONICAL_FAMILY_EXPANSION", "1") == "0":
        return topics
    g = (goal or "").lower()
    fam = next((f for f in _CANONICAL_FAMILIES.values() if any(m in g for m in f["goal_markers"])), None)
    if not fam:
        return topics

    def _ttype(t: dict[str, Any]) -> str:
        return str(t.get("course_type") or t.get("topic_type") or "").strip().lower()

    # ONE comparison per family survey: the model sometimes emits a comparison AND an analysis-framed
    # sibling that normalization retypes to compare_distinguish ('Evaluating Traversal Complexity') —
    # keep the first, drop the rest (their content is the comparison topic's job).
    comps = [t for t in topics if _ttype(t) == "compare_distinguish"]
    if len(comps) > 1:
        drop_ids = {id(t) for t in comps[1:]}
        topics = [t for t in topics if id(t) not in drop_ids]
        _log.info("topic_generator: dropped %d extra comparison topic(s) for the family survey: %s",
                  len(comps) - 1, [str(t.get("title")) for t in comps[1:]])
        record_topic_decision(
            comps[0], "family.extra_comparisons_dropped",
            f"absorbed {[str(t.get('title')) for t in comps[1:]]}",
            "a family survey gets exactly ONE comparison topic (often duplicated by an analysis-framed "
            "sibling retyped to compare_distinguish during normalization) — first kept, rest dropped")
    if any(_ttype(t) == "compare_distinguish" for t in topics):
        return topics                                       # the model already emitted one — never duplicate
    try:
        from app.services.examples.trace_pipeline import route_adapter
    except Exception:  # noqa: BLE001 — never break topic generation
        return topics
    member_slugs = {slug for _, slug in fam["members"]}
    taught = {getattr(route_adapter({"title": str(t.get("title") or ""),
                                     "subject_key": str(t.get("subject_key") or ""),
                                     "topic_type": _ttype(t)}), "slug", None)
              for t in topics if _ttype(t) in _MEMBER_TEACHING_TYPES}
    taught &= member_slugs
    if len(taught) < 2:
        return topics                                       # one alternative — nothing to compare
    display = str(fam.get("display") or "the alternatives")
    names = [name for name, slug in fam["members"] if slug in taught]
    title = f"Comparing {display}"
    comparison = {
        "title": title,
        "course_type": "compare_distinguish", "topic_type": "compare_distinguish",
        "unit_title": title,
        "description": f"When to choose each of: {', '.join(names)}.",
        "purpose": f"Choose the right approach: compare {', '.join(names)} on how they work, cost, and fit.",
        "learner_outcome": f"The learner can pick between {display.lower()} for a given situation and say why.",
        "in_scope": [f"{a} vs {b}" for a, b in zip(names, names[1:])] or names,
        "out_of_scope": [], "prerequisite_topics": [], "source_refs": [],
        "order_index": max((int(t.get("order_index") or 0) for t in topics), default=0) + 1,
        # create_topic_from_generated_data reads this with a HARD key lookup; every model-emitted topic gets
        # it via normalization, but this injected dict skipped it — KeyError the first time the injector
        # actually fired live (model emitted no comparison of its own).
        "estimated_minutes": 10,
    }
    _log.info("topic_generator: injected deterministic family comparison topic %r", title)
    record_topic_decision(
        comparison, "family.comparison_injected", f"synthesized {title!r}",
        "the goal surveys a registered family, the path teaches >=2 distinct members, and the model "
        "emitted no comparison of its own — a comparison is only teachable once every alternative has "
        "been taught, so it is appended last", compared=names)
    return [*topics, comparison]


def _fix_noncoding_coding_topics(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A coding_implementation topic whose SUBJECT routes to a NON-coding adapter (a math/derivation/formula/
    stateful concept — manifest `coding: False`) is a decomposition slip: the model applied the generic
    'algorithm -> walkthrough + coding' pattern to a concept you do NOT implement in code (e.g. 'Implementing
    Completing the Square', which just dressed the derivation up as fake code). If a real walkthrough already
    covers that concept (same adapter), DROP the coding twin; if it is the ONLY topic for the concept, relabel
    it to a process_walkthrough (stripping the 'Implementing' framing) so the derivation is still taught."""
    try:
        from app.services.examples.trace_adapters.manifest import MANIFEST, match_routing_slug
    except Exception:  # noqa: BLE001 — never break generation on an import hiccup
        return topics

    def _tt(t: dict[str, Any]) -> str:
        return str(t.get("course_type") or t.get("topic_type") or "").strip().lower()

    def _slug(t: dict[str, Any]):
        return match_routing_slug(str(t.get("title") or "").lower())

    covered = {_slug(t) for t in topics if _tt(t) != "coding_implementation"}   # concepts a walkthrough teaches
    out: list[dict[str, Any]] = []
    for t in topics:
        if _tt(t) == "coding_implementation":
            slug = _slug(t)
            if slug and MANIFEST.get(slug, {}).get("coding") is False:
                if slug in covered:                     # a real walkthrough already teaches it -> drop the twin
                    _log.info("topic_generator: dropped non-coding coding_implementation %r (adapter %s is "
                              "coding:False; a walkthrough already covers it)", t.get("title"), slug)
                    twin = next((w for w in topics if _tt(w) != "coding_implementation" and _slug(w) == slug),
                                None)
                    if twin is not None:
                        record_topic_decision(
                            twin, "coding.non_coding_twin_dropped", f"dropped {t.get('title')!r}",
                            f"the adapter ({slug}) is declared coding:False — the concept is a "
                            "derivation/formula dressed up as fake code, and this walkthrough already "
                            "teaches it, so the redundant 'Implementing' twin is removed")
                    continue
                title = str(t.get("title") or "")       # sole topic -> keep it, but as a walkthrough
                t["course_type"] = t["topic_type"] = "process_walkthrough"
                t["practice_format"] = ""
                if title.lower().startswith("implementing "):
                    t["title"] = title[len("implementing "):].strip()
                _log.info("topic_generator: relabeled lone non-coding coding_implementation %r -> "
                          "process_walkthrough (adapter %s is coding:False)", title, slug)
                record_topic_decision(
                    t, "coding.relabeled_non_coding", "course_type -> process_walkthrough",
                    f"the adapter ({slug}) is declared coding:False — the concept is a derivation/formula, "
                    "not something implemented in code — and this is the ONLY topic covering it, so it's "
                    "kept but re-typed rather than dropped", original_title=title)
        out.append(t)
    return out


def _fold_prereqs_into_intro(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prereqs live in the INTRO; every other topic teaches ONLY its own concept. A `concept_intuition` whose
    subject is NOT taught on the path (no walkthrough/process/coding of it) is a prerequisite, not the target —
    remove it from the body and record it on the intro: ASSUMED foundations are listed (linked to their own path
    later), GLOSSED statements get a one-line mention. Every body topic is annotated with `assumed_prerequisites`
    so its generation does not re-explain prereq material. Off via AZALEA_FOLD_PREREQS=0."""
    if os.getenv("AZALEA_FOLD_PREREQS", "1") == "0":
        return topics

    def _tt(t: dict[str, Any]) -> str:
        return str(t.get("course_type") or t.get("topic_type") or "").strip().lower()

    intro = next((t for t in topics if _tt(t) == "study_path_introduction"), None)
    if intro is None:
        return topics  # nowhere to fold prereqs -> leave the path unchanged

    domain = _path_domain_tokens(topics)
    taught_sets = [_stem_subject_set(t.get("title"), domain) for t in topics if _tt(t) in _TEACHING_TYPES]

    def _is_taught(concept: frozenset[str]) -> bool:
        # taught if a majority of the concept's (stemmed) subject tokens appear in some taught topic's subject
        return bool(concept) and any(len(concept & ts) / len(concept) >= 0.5 for ts in taught_sets)

    kept: list[dict[str, Any]] = []
    assumed: list[str] = []
    glossed: list[dict[str, str]] = []
    for t in topics:
        if _tt(t) == "concept_intuition":
            subj = _stem_subject_set(t.get("title"), domain)
            if subj and not _is_taught(subj):                    # a prerequisite, not a taught target concept
                cls = _classify_prerequisite(t.get("title"))
                phrase = _subject_phrase(t.get("title"))
                if cls == "assume":
                    assumed.append(phrase)
                else:
                    glossed.append({"concept": phrase, "purpose": str(t.get("purpose") or "")})
                _log.info("topic_generator: folded prerequisite %r into intro (%s)", t.get("title"), cls)
                record_topic_decision(
                    intro, "prerequisite.folded_from_body", f"absorbed {t.get('title')!r} ({cls})",
                    "a concept_intuition topic whose subject is NOT taught anywhere else on the path is a "
                    "prerequisite the learner is assumed to have, not a teaching target — removed from the "
                    "body and recorded on the intro instead")
                continue
        kept.append(t)

    if not (assumed or glossed):
        return topics
    if not any(_tt(t) not in ("study_path_introduction",) for t in kept):
        return topics  # never leave a path with only the intro

    # The intro carries the prereqs. ASSUMED ones go on `assumed_prerequisites` (a first-class Topic field the
    # assumption ledger reads to build `do_not_reteach`). GLOSSED ones go on the intro's
    # `brief_refresh_prerequisites`, which the scope contract feeds to the prompt as a 1-3 line refresh; since the
    # Topic model has no such column, they ride along in the persisted `decomposition_metadata` blob (read back in
    # topic_scope_service.build_topic_scope_contract). MERGE everywhere (never clobber existing values).
    def _merge_assumed(t: dict[str, Any], names: list[str]) -> None:
        merged = list(dict.fromkeys([*(t.get("assumed_prerequisites") or []), *names]))
        t["assumed_prerequisites"] = merged

    gloss_names = [g["concept"] for g in glossed]
    if gloss_names:
        meta = intro.get("decomposition_metadata")
        meta = dict(meta) if isinstance(meta, dict) else {}
        existing = meta.get("brief_refresh_prerequisites") or []
        meta["brief_refresh_prerequisites"] = list(dict.fromkeys([*existing, *gloss_names]))
        intro["decomposition_metadata"] = meta
    _merge_assumed(intro, assumed)                                # intro assumes the foundational ones silently
    all_names = [*assumed, *gloss_names]
    for t in kept:
        if _tt(t) != "study_path_introduction":
            _merge_assumed(t, all_names)                          # body: assume ALL of them; do not re-explain
    return kept


def _append_missing_coding_topics(topics: list[dict[str, Any]], goal: str) -> list[dict[str, Any]]:
    """Deterministically guarantee the blueprint's 'append a coding_implementation after the
    walkthrough' rule (course_blueprints §combination_rules) — the rule was prompt-only, so the model
    frequently DROPPED it and the coding topic never existed. For every algorithm_walkthrough /
    data_structure_operation whose subject has no coding_implementation, synthesize one and insert it
    right after. Skipped when the goal explicitly asks for no code. Off via AZALEA_AUTO_CODING_FOLLOWUP=0.
    """
    if os.getenv("AZALEA_AUTO_CODING_FOLLOWUP", "1") == "0":
        return topics
    if any(m in (goal or "").lower() for m in _NO_CODE_GOAL_MARKERS):
        return topics

    def _ttype(t: dict[str, Any]) -> str:
        return str(t.get("course_type") or t.get("topic_type") or "").strip().lower()

    # Domain-normalized subjects so a coding topic is recognized as covering an algorithm even when the
    # titles differ only by a domain qualifier ('Implementing Prim's MST' vs '...Prim's Algorithm in Code').
    have_coding = {
        _canonical_concept_key(t.get("subject_key") or t.get("title"), _ttype(t))
        for t in topics if _ttype(t) == "coding_implementation"
    }
    # Put any synthesized coding topic in the coding section, not the walkthrough's unit it was derived
    # from (dict(t) would otherwise inherit the walkthrough's unit_title and mis-file it).
    coding_unit = next(
        (str(t.get("unit_title")) for t in topics
         if _ttype(t) == "coding_implementation" and str(t.get("unit_title") or "").strip()),
        "Coding Implementation",
    )
    result: list[dict[str, Any]] = []
    for t in topics:
        result.append(t)
        if _ttype(t) in _CODE_ABLE_TYPES:
            subject = _canonical_concept_key(t.get("subject_key") or t.get("title"), _ttype(t))
            if subject and subject not in have_coding:
                have_coding.add(subject)
                phrase = _subject_phrase(t.get("title"))
                coding = dict(t)  # inherit every field/key the downstream expects
                coding.pop("_decision_trace", None)   # a fresh follow-up gets its OWN trace, not the WT's
                coding.update({
                    "title": f"Implementing {phrase}",
                    "course_type": "coding_implementation",
                    "topic_type": "coding_implementation",
                    "unit_title": coding_unit,
                    "secondary_course_types": [],
                    "purpose": f"Translate the {phrase} algorithm into working, runnable code.",
                    "in_scope": [f"Writing the {phrase} implementation in code",
                                 "Reading the code and tracing it on a concrete input"],
                    "prerequisite_topics": list(t.get("prerequisite_topics") or []) + [t.get("title")],
                    "practice_format": "coding",
                })
                result.append(coding)
                _log.info("topic_generator: appended coding_implementation %r after %r",
                          coding["title"], t.get("title"))
                record_topic_decision(
                    coding, "coding.follow_up_appended", f"synthesized {coding['title']!r}",
                    "coding-family paths always give every algorithm_walkthrough / data_structure_operation "
                    "topic an implementation follow-up (this domain gates coding_follow_ups=True) — the "
                    "model didn't emit one for this subject, so it's appended deterministically",
                    walkthrough=str(t.get("title")))
    for i, t in enumerate(result, 1):
        t["order_index"] = i
    return result


def clean_text_field(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback

    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())

    return str(value).strip() or fallback


def clean_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [normalize_spacing(str(item)) for item in value if normalize_spacing(str(item))]
    if isinstance(value, str):
        separators = [";", "|", "\n"]
        normalized = value
        for separator in separators:
            normalized = normalized.replace(separator, ",")
        return [normalize_spacing(item) for item in normalized.split(",") if normalize_spacing(item)]
    return [normalize_spacing(str(value))] if normalize_spacing(str(value)) else []


def clean_source_refs(value: Any, fallback: str = "") -> str:
    refs = clean_string_list(value)
    if refs:
        return "; ".join(refs)
    return fallback


def normalize_spacing(value: str) -> str:
    return " ".join(value.split())


def normalize_estimated_minutes(value: Any) -> int:
    try:
        estimated_minutes = int(value)
    except (TypeError, ValueError):
        estimated_minutes = 10

    return max(5, min(25, estimated_minutes))


def normalize_knowledge_level(value: Any) -> int | None:
    try:
        level = int(value)
    except (TypeError, ValueError):
        return None
    return max(1, min(5, level))


def build_chunk_source_label(chunk: ContentChunk, source_number: int) -> str:
    material_title = "Uploaded material"
    material_filename = ""

    if getattr(chunk, "material", None) is not None:
        material_title = chunk.material.title or chunk.material.filename or "Uploaded material"
        material_filename = chunk.material.filename or ""

    filename_text = f", {material_filename}" if material_filename else ""
    return (
        f"SOURCE CHUNK {source_number}: {material_title}{filename_text}, "
        f"chunk {chunk.chunk_index}"
    )


_CODING_TITLE_MARKERS = ("implementing", "implement", "code", "coding", "in code")


def _is_coding_title(normalized_title: str) -> bool:
    """Heuristic: title looks like a coding_implementation topic title.
    Generated topics typically prefix with 'Implementing ', 'Code ', etc."""
    return any(marker in normalized_title.split() for marker in ("implementing", "implement", "coding"))


def is_probably_duplicate(
    title: str,
    existing_titles: set[str],
    topic_type: str | None = None,
) -> bool:
    normalized_title = normalize_spacing(title.lower())

    if normalized_title in existing_titles:
        return True

    title_words = set(normalized_title.split())
    is_coding_topic = (topic_type == "coding_implementation") or _is_coding_title(normalized_title)

    for existing_title in existing_titles:
        existing_words = set(existing_title.split())

        if not title_words or not existing_words:
            continue

        # Skip dedup when one title looks like a coding_implementation follow-up
        # and the other looks like its parent walkthrough — they share the
        # algorithm/structure name by design (e.g. "Implementing Inorder
        # Traversal of a BST" vs "Inorder Traversal of a BST"). Treating them
        # as duplicates silently kills the auto-generated coding follow-ups.
        existing_is_coding = _is_coding_title(existing_title)
        if is_coding_topic != existing_is_coding:
            continue

        overlap = len(title_words.intersection(existing_words))
        smaller_size = min(len(title_words), len(existing_words))

        if smaller_size > 0 and overlap / smaller_size >= 0.85:
            return True

    return False


def parse_prerequisite_titles(value: str) -> list[str]:
    separators = [";", "|", "\n"]

    normalized = value
    for separator in separators:
        normalized = normalized.replace(separator, ",")

    return [
        normalize_spacing(item)
        for item in normalized.split(",")
        if normalize_spacing(item)
    ]


def normalize_prerequisites(
    prerequisite_topics: Any,
    earlier_titles_by_normalized_title: dict[str, str],
) -> str:
    prerequisite_titles = clean_string_list(prerequisite_topics)
    if not prerequisite_titles:
        return ""

    cleaned_prerequisites: list[str] = []
    seen: set[str] = set()

    for prerequisite_title in prerequisite_titles:
        normalized_title = normalize_spacing(prerequisite_title.lower())
        matched_title = earlier_titles_by_normalized_title.get(normalized_title)

        if not matched_title:
            continue

        if normalized_title in seen:
            continue

        cleaned_prerequisites.append(matched_title)
        seen.add(normalized_title)

    return ", ".join(cleaned_prerequisites)


_FOLLOW_UP_STOPWORDS = {"implementing", "implement", "implementation", "the", "a", "an", "of", "for", "in",
                        "algorithm", "algorithms", "and", "to", "with", "using", "code", "coding"}
_WALKTHROUGH_TYPES = {"algorithm_walkthrough", "operation_walkthrough"}


def _followup_subject_tokens(title: Any) -> set[str]:
    return {w for w in _re.split(r"[^a-z0-9]+", str(title or "").lower())
            if w and len(w) > 2 and w not in _FOLLOW_UP_STOPWORDS}


def _mark_coding_follow_ups(topics: list[dict[str, Any]]) -> None:
    """A coding_implementation topic that FOLLOWS a walkthrough on the SAME subject re-teaches nothing new
    conceptually, so tag it with the implementation_follow_up modifier — generation then drops the redundant
    `background` card (the walkthrough already framed the algorithm). Deterministic: the preceding topic is a
    walkthrough AND they share a significant title token. Applied on first generation AND regeneration, so the
    structure is stable across regen without re-typing the topic (coding detection stays intact)."""
    from app.core.course_blueprints import IMPLEMENTATION_FOLLOW_UP

    for i in range(1, len(topics)):
        cur, prev = topics[i], topics[i - 1]
        cur_type = str(cur.get("topic_type") or cur.get("course_type") or "").lower()
        prev_type = str(prev.get("topic_type") or prev.get("course_type") or "").lower()
        same_concept = (
            _canonical_concept_key(cur.get("subject_key") or cur.get("title"), cur_type)
            == _canonical_concept_key(prev.get("subject_key") or prev.get("title"), prev_type)
        )
        if cur_type == "coding_implementation" and prev_type in _WALKTHROUGH_TYPES and same_concept:
            mods = cur.setdefault("modifiers", [])
            if isinstance(mods, list) and IMPLEMENTATION_FOLLOW_UP not in mods:
                mods.append(IMPLEMENTATION_FOLLOW_UP)


def generate_topics_from_chunks(
    chunks: list[ContentChunk],
    goal: str | None = None,
    feedback: str | None = None,
    domain: str | None = None,
) -> list[dict[str, Any]]:
    chunk_sections: list[str] = []

    source_labels: list[str] = []

    for index, chunk in enumerate(chunks[:10]):
        source_label = build_chunk_source_label(chunk=chunk, source_number=index + 1)
        source_labels.append(source_label)

        chunk_sections.append(
            f"""
--- SOURCE CHUNK {index + 1} ---
Source label: {source_label}
Material id: {chunk.material_id}
Chunk id: {chunk.id}
Chunk index: {chunk.chunk_index}

{chunk.text}
""".strip()
        )

    chunks_text = "\n\n".join(chunk_sections)

    if not chunks_text:
        chunks_text = (
            "No uploaded source material was provided. Build the study path "
            "from the learner goal only. Leave source_refs empty."
        )

    # Capability-graph decomposition path (TOPIC_DECOMPOSITION_SPEC.md), flag-gated. Produces the same
    # legacy topic-dict shape, so the rest of the pipeline is unchanged. Falls back to the legacy
    # generator below if it yields nothing.
    if os.getenv("AZALEA_TOPIC_DECOMPOSITION", "") not in ("", "0"):
        try:
            from app.services.topic_decomposition_pipeline import generate_decomposed_topics

            # Coding follow-ups (append an "Implementing X" topic after each walkthrough) are for the CODING
            # family ONLY — no other domain (CS, science, math, …) ever gets an implementation topic (live
            # failure: a TCP congestion-control path grew an "Implementing TCP Congestion Control" coding topic).
            decomposed = generate_decomposed_topics(
                goal=goal, chunks_text=chunks_text, feedback=feedback,
                coding_follow_ups=(gate_family_of(domain) == "coding"))
            if decomposed:
                _log.info("topic_generator: used capability-graph decomposition (%d topics)", len(decomposed))
                # Gate BEFORE marking follow-ups so the marking reflects the final (possibly remapped) types.
                decomposed = _apply_domain_gate(decomposed, domain)
                # One authoritative identity/scope decision BEFORE additive policy. This prevents the coding
                # backfill from manufacturing a second implementation for a spelling/possessive variant.
                decomposed = _certify_path_scope(decomposed, goal)
                # FAMILY-SURVEY backfill for the decomposed path too (was legacy-only — live gap: a "bst
                # traversal" path shipped without Level-Order). Injected walkthroughs then get their coding
                # follow-ups from the same backfill, and the family is consolidated into canonical order
                # (each walkthrough immediately followed by its implementation — the observed scramble left
                # an implementation stranded between other members).
                if _coding_transforms_enabled(domain):
                    decomposed = _expand_canonical_family(decomposed, goal)
                    decomposed = _append_missing_coding_topics(decomposed, goal)
                    decomposed = _order_canonical_family(decomposed, goal)
                    decomposed = _ensure_family_comparison_topic(decomposed, goal)
                # Same-adapter duplicates produce the identical exercise twice — all domains, not just coding.
                decomposed = _drop_same_adapter_duplicate_topics(decomposed)
                decomposed = _fix_intro_prefixed_units(decomposed)
                # Certify again because family/coding policy may have added rows. The second pass records their
                # identities and guarantees policy cannot reintroduce an overlap or duplicate.
                decomposed = _certify_path_scope(decomposed, goal)
                _mark_coding_follow_ups(decomposed)
                return _ensure_intro_topic(decomposed, goal)
            _log.warning("topic_generator: decomposition produced nothing — falling back to legacy")
        except Exception as exc:  # noqa: BLE001 — never block generation; fall back to legacy
            _log.warning("topic_generator: decomposition failed (%s) — falling back to legacy", exc)

    user_prompt = build_topic_prompt(
        goal=goal,
        chunks_text=chunks_text,
        feedback=feedback,
    )

    topics = generate_structured_topics(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    cleaned_topics: list[dict[str, Any]] = []
    existing_titles: set[str] = set()
    earlier_titles_by_normalized_title: dict[str, str] = {}
    fallback_source_refs = "; ".join(source_labels[:3])

    for topic in topics[:10]:
        raw_title = clean_text_field(topic.get("title"))
        title = normalize_spacing(raw_title)[:255].strip()

        if not title:
            title = f"Generated Topic {len(cleaned_topics) + 1}"

        raw_topic_type = str(topic.get("topic_type") or topic.get("course_type") or "").strip().lower()
        if is_probably_duplicate(title, existing_titles, topic_type=raw_topic_type):
            continue

        normalized_title = normalize_spacing(title.lower())
        existing_titles.add(normalized_title)

        purpose = clean_text_field(
            topic.get("purpose"),
            fallback=(
                "Understand and apply the key idea from this study goal."
            ),
        )
        learner_outcome = clean_text_field(
            topic.get("learner_outcome"),
            fallback=purpose,
        )

        unit_title = normalize_spacing(
            clean_text_field(
                topic.get("unit_title"),
                fallback="Core Concepts",
            )
        )[:255]

        prerequisite_topics = normalize_prerequisites(
            prerequisite_topics=topic.get("prerequisite_topics"),
            earlier_titles_by_normalized_title=earlier_titles_by_normalized_title,
        )

        source_refs = clean_source_refs(
            topic.get("source_refs"),
            fallback=fallback_source_refs,
        )

        if not source_refs:
            source_refs = fallback_source_refs

        estimated_minutes = normalize_estimated_minutes(
            topic.get("estimated_minutes", 10)
        )

        cleaned_topic = enrich_topic_with_course_type(
            {
                "title": title,
                "learner_outcome": learner_outcome,
                "purpose": purpose,
                "unit_title": unit_title,
                "prerequisite_topics": prerequisite_topics,
                "assumed_prerequisites": clean_string_list(topic.get("assumed_prerequisites")),
                "source_refs": source_refs,
                "in_scope": clean_string_list(topic.get("in_scope")),
                "out_of_scope": clean_string_list(topic.get("out_of_scope")),
                "course_type": clean_text_field(topic.get("topic_type") or topic.get("course_type"), ""),
                "secondary_course_types": clean_string_list(
                    topic.get("secondary_topic_types")
                    or topic.get("secondary_course_types")
                ),
                "knowledge_level": normalize_knowledge_level(topic.get("knowledge_level")),
                "practice_format": clean_text_field(topic.get("practice_format"), ""),
                "modifiers": clean_string_list(topic.get("modifiers")),
                "practice_target": clean_text_field(topic.get("practice_target"), ""),
                "order_index": len(cleaned_topics) + 1,
                "estimated_minutes": estimated_minutes,
            },
            user_goal=goal,
            previous_topics=[topic["title"] for topic in cleaned_topics],
            source_summary=source_refs,
            domain=domain if _gate_enforced() else None,   # constrain the type to the path's domain at the source
        )
        cleaned_topic["topic_type"] = cleaned_topic.get("course_type")

        cleaned_topics.append(cleaned_topic)

        earlier_titles_by_normalized_title[normalized_title] = title

    # Drop auxiliary paradigm/methodology topics (e.g. "Understanding Divide and Conquer" on a
    # merge-sort path) that the concrete algorithm topics already teach by example.
    cleaned_topics = _drop_paradigm_only_topics(cleaned_topics, goal)
    # A coding_implementation for a pure-math/derivation concept (routes to a coding:False adapter) is a
    # decomposition slip — drop the twin if a walkthrough covers it, else relabel it to a walkthrough.
    cleaned_topics = _fix_noncoding_coding_topics(cleaned_topics)
    # Backstop the "one walkthrough per algorithm" prompt rule deterministically: drop a second
    # same-type topic for the same subject (e.g. a "Process Overview" walkthrough next to a
    # "Step by Step" walkthrough for quick sort) before it becomes a duplicate lesson.
    cleaned_topics = _drop_same_type_subject_duplicates(cleaned_topics)
    # Also collapse DIFFERENT-type method lessons of the same subject (e.g. a process_walkthrough AND a
    # problem_solving_application of "completing the square") — both regenerate the same steps + worked example,
    # so keep the teaching walkthrough and drop the duplicate application.
    cleaned_topics = _collapse_same_subject_method_topics(cleaned_topics)
    cleaned_topics = _certify_path_scope(cleaned_topics, goal)
    # Deterministically fill in a FAMILY SURVEY's canonical members (e.g. sorting -> all five sorts) that the
    # decomposition LLM under-generated. The pipeline is otherwise subtractive, so this is the only place the
    # canonical set is guaranteed. Runs BEFORE the coding backfill so injected walkthroughs get coding topics.
    # These are coding-family backfills — skipped when the gate is ENFORCED on a non-coding path (§5, D-c).
    if _coding_transforms_enabled(domain):
        cleaned_topics = _expand_canonical_family(cleaned_topics, goal)
        # Guarantee a coding_implementation follow-up exists for each algorithm/data-structure subject
        # (the blueprint rule was prompt-only, so the model often dropped it -> "coding never generated").
        cleaned_topics = _append_missing_coding_topics(cleaned_topics, goal)
    # Prereqs live in the intro; every other topic teaches only its own concept. Fold prerequisite
    # concept_intuition topics (subject not taught on the path) into the intro (assume vs gloss), and mark body
    # topics with the prereqs to assume — runs after the teaching topics are finalized, before ordering.
    cleaned_topics = _fold_prereqs_into_intro(cleaned_topics)
    # Consolidate a family survey into canonical order, each walkthrough next to its coding follow-up
    # (runs AFTER the coding backfill so both halves of each member are present to group).
    if _coding_transforms_enabled(domain):
        cleaned_topics = _order_canonical_family(cleaned_topics, goal)
        cleaned_topics = _ensure_family_comparison_topic(cleaned_topics, goal)
    cleaned_topics = _certify_path_scope(cleaned_topics, goal)

    if not cleaned_topics:
        cleaned_topics.append(
            enrich_topic_with_course_type(
                {
                    "title": "Core Ideas For This Goal",
                    "unit_title": "Core Concepts",
                    "learner_outcome": "The learner can explain and apply the main idea from this study goal.",
                    "purpose": (
                        "Understand the main ideas for this study goal and prepare "
                        "for examples and practice."
                    ),
                    "in_scope": ["main idea", "core vocabulary", "basic application"],
                    "out_of_scope": [],
                    "prerequisite_topics": "",
                    "assumed_prerequisites": [],
                    "source_refs": fallback_source_refs,
                    "practice_target": "Apply the main idea to a simple example.",
                    "practice_format": "short_answer",
                    "order_index": 1,
                    "estimated_minutes": 10,
                },
                user_goal=goal,
                source_summary=fallback_source_refs,
                domain=domain if _gate_enforced() else None,
            )
        )

    # Domain gate — the final authority over topic types (§4). Shadow mode (flag off) leaves the list untouched
    # and only records what it WOULD change; enforced mode returns the remapped/dropped list. Runs before the
    # order-index/topic_type sync so re-numbering reflects any drops.
    cleaned_topics = _apply_domain_gate(cleaned_topics, domain)

    for index, topic in enumerate(cleaned_topics, start=1):
        topic["order_index"] = index
        topic["topic_type"] = topic.get("course_type")

    _mark_coding_follow_ups(cleaned_topics)
    return _ensure_intro_topic(cleaned_topics, goal)
