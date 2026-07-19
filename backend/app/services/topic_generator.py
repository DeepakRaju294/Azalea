from __future__ import annotations

import copy
import json
import logging
import os
import threading
from typing import TYPE_CHECKING, Any

from app.prompts.topic_prompt import SYSTEM_PROMPT, build_topic_prompt
from app.services.course_type_classifier import enrich_topic_with_course_type
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
    """Bulletproof backstop: a multi-topic path ALWAYS opens with a lightweight orientation topic. The
    pipeline-level guarantee can be bypassed (regeneration, a stale decomposition), so enforce it here at
    the OUTERMOST point — for both engines. Idempotent: skips when an intro already leads the path, and
    leaves a single-topic path untouched (it self-orients)."""
    if not topics or len(topics) < 2:
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
    },
    "graph_traversal": {
        "goal_markers": ("graph traversal", "graph traversals", "traverse a graph", "traversing a graph"),
        "members": [("Breadth-First Search", "bfs"), ("Depth-First Search", "dfs_iter")],
    },
    # Live failure: a "bst traversal" path shipped only in/post/pre-order — the model under-generates and
    # nothing backfilled Level-Order. Every member routes to a verified tree adapter with canonical code.
    "tree_traversal": {
        "goal_markers": ("bst traversal", "binary search tree traversal", "tree traversal", "tree traversals",
                         "binary tree traversal", "traversing a tree", "traversing a bst", "traverse a bst"),
        "members": [("In-Order Traversal", "tree_inorder"), ("Pre-Order Traversal", "tree_preorder"),
                    ("Post-Order Traversal", "tree_postorder"), ("Level-Order Traversal", "tree_levelorder")],
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

    def _slug(title: Any, ttype: str) -> Optional[str]:
        a = route_adapter({"title": str(title or ""), "topic_type": ttype})
        return a.slug if a else None

    present = {slug for t in topics if _ttype(t) in _MEMBER_TEACHING_TYPES
               for slug in [_slug(t.get("title"), _ttype(t))] if slug}
    member_slugs = {slug for _, slug in fam["members"]}
    if not (present & member_slugs):            # path teaches no member of this family -> do not inject
        return topics
    template = next((t for t in topics if _ttype(t) == "algorithm_walkthrough"), None)
    result = list(topics)
    for member_title, slug in fam["members"]:
        if slug in present:
            continue
        new = dict(template) if template else {}
        new.pop("topic_id", None)
        new.pop("id", None)
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
        a = route_adapter({"title": str(t.get("title") or ""), "topic_type": _ttype(t)})
        return a.slug if a else None

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
    canon = {slug: name for name, slug in fam["members"]}
    for t in fam_block:
        s = _slug(t)
        if s not in canon:
            continue
        if _ttype(t) == "algorithm_walkthrough":
            t["title"] = canon[s]
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
                    continue
                title = str(t.get("title") or "")       # sole topic -> keep it, but as a walkthrough
                t["course_type"] = t["topic_type"] = "process_walkthrough"
                t["practice_format"] = ""
                if title.lower().startswith("implementing "):
                    t["title"] = title[len("implementing "):].strip()
                _log.info("topic_generator: relabeled lone non-coding coding_implementation %r -> "
                          "process_walkthrough (adapter %s is coding:False)", title, slug)
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
    domain = _path_domain_tokens(topics)
    have_coding = {
        _subject_tokens(t.get("title"), domain)[1]
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
            _, subject = _subject_tokens(t.get("title"), domain)
            if subject and subject not in have_coding:
                have_coding.add(subject)
                phrase = _subject_phrase(t.get("title"))
                coding = dict(t)  # inherit every field/key the downstream expects
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
        if (cur_type == "coding_implementation" and prev_type in _WALKTHROUGH_TYPES
                and (_followup_subject_tokens(cur.get("title")) & _followup_subject_tokens(prev.get("title")))):
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
                # FAMILY-SURVEY backfill for the decomposed path too (was legacy-only — live gap: a "bst
                # traversal" path shipped without Level-Order). Injected walkthroughs then get their coding
                # follow-ups from the same backfill, and the family is consolidated into canonical order
                # (each walkthrough immediately followed by its implementation — the observed scramble left
                # an implementation stranded between other members).
                if _coding_transforms_enabled(domain):
                    decomposed = _expand_canonical_family(decomposed, goal)
                    decomposed = _append_missing_coding_topics(decomposed, goal)
                    decomposed = _order_canonical_family(decomposed, goal)
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
