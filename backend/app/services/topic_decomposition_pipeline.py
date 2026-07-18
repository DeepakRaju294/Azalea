"""Topic-decomposition generation orchestration (TOPIC_DECOMPOSITION_SPEC.md, the flagged live path).

generate_decomposed_topics(chunks, goal, feedback) does the single-call generation, then runs the pure
deterministic core (normalize -> append coding follow-ups -> validate) and ADAPTS the result into the
legacy topic-dict shape the existing lesson pipeline already consumes — so turning the flag on changes
how topics are *decided* without changing anything downstream. The model call is injectable so the
whole orchestration is unit-testable without an API call.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable, Optional

from app.core.topic_decomposition import (
    canonical_action, normalize_subject_key, resolve_topic_type,
)
from app.core.topic_decomposition_appender import IMPLEMENTATION_FOLLOW_UP, append_coding_follow_ups
from app.core.topic_decomposition_validator import OverlapResolver, validate_topic_decomposition
from app.prompts.topic_decomposition_prompt import SYSTEM_PROMPT, build_decomposition_prompt

_log = logging.getLogger(__name__)

# model_fn: ({"system","user"}) -> parsed {"path_plan", "topics"} (or raw str the pipeline json-loads).
ModelFn = Callable[[dict[str, str]], Any]


def _default_model_fn(payload: dict[str, str]) -> dict[str, Any]:
    from app.services.llm_client import generate_topic_decomposition
    return generate_topic_decomposition(system_prompt=payload["system"], user_prompt=payload["user"])


def _default_resolver() -> Optional[OverlapResolver]:
    """The bounded LLM overlap resolver, only when AZALEA_TOPIC_OVERLAP_RESOLVER is enabled (it costs an
    extra call per genuinely ambiguous pair). Off -> validator flags-and-keeps ambiguous pairs."""
    if os.getenv("AZALEA_TOPIC_OVERLAP_RESOLVER", "") in ("", "0"):
        return None
    from app.services.llm_client import resolve_topic_overlap
    return resolve_topic_overlap


def _coerce(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _normalize_topic(t: dict[str, Any]) -> dict[str, Any]:
    """Format-normalize the model's fields (subject_key, primary_action, topic_type) before validation."""
    t = dict(t)
    t["subject_key"] = normalize_subject_key(t.get("subject_key"))
    if t.get("primary_action"):
        t["primary_action"] = canonical_action(t["primary_action"]) or t["primary_action"]
    if not t.get("topic_type") and t.get("content_role"):
        t["topic_type"] = resolve_topic_type(t["content_role"])
    return t


def _subject_phrase(subject_key: str) -> str:
    return (subject_key or "").replace("_", " ").strip().title() or "the algorithm"


def _cross_topic_foundations(teaching_topics: list[dict[str, Any]], goal: str | None) -> list[str]:
    """A concept named in the in_scope of ≥2 teaching topics but TAUGHT by none (matches no topic's
    subject/title) is a shared assumed foundation — a prerequisite the LLM often forgets to declare. E.g. on a
    Bayes path both 'Law of Total Probability' and 'Bayes Theorem' list 'conditional probability' in_scope, yet
    no topic teaches it → it is a prerequisite, not a key term. Deterministic backstop to the LLM's
    path_plan.assumed_prerequisites. Excludes anything the goal names (that stays in-scope/taught)."""
    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9 ]+", "", str(s or "").replace("_", " ").lower()).strip()

    subjects = {_norm(t.get("subject_key")) for t in teaching_topics} | {_norm(t.get("title")) for t in teaching_topics}
    subjects.discard("")
    counts: dict[str, tuple[str, int]] = {}   # norm -> (display, topic_count)
    for t in teaching_topics:
        for concept in {_norm(c): str(c).strip() for c in (t.get("in_scope") or [])}.items():
            norm, display = concept
            if not norm or norm in subjects:
                continue
            disp, n = counts.get(norm, (display, 0))
            counts[norm] = (disp, n + 1)
    out: list[str] = []
    for norm, (display, n) in counts.items():
        if (n >= 2 and not _goal_names_topic({"title": display, "subject_key": display}, goal)
                and not _is_circular_prereq(display, goal)):
            out.append(display)
    return out


# Prepositions/conjunctions that never legitimately OPEN an educational topic title, so a title starting with
# one is a malformed LLM fragment (e.g. "With Ohm's Law", a truncation of "Calculating With Ohm's Law").
# Deliberately EXCLUDES "for"/"in"/"on" — those DO start real titles ("For Loops", "In-place Sorting").
_LEADING_TITLE_JUNK = frozenset({"with", "of", "by", "to", "from", "at", "and", "or"})


_GOAL_MATCH_GLUE = frozenset({"the", "a", "an", "of", "and", "or", "for", "to", "in", "on", "with", "by", "as"})


def _goal_names_topic(topic: dict[str, Any], goal: str | None) -> bool:
    """True when the learner's goal explicitly names this concept (so it belongs IN scope as a taught topic, not
    demoted to an external prerequisite). Matches when the concept's distinctive title/subject words all appear
    in the goal — e.g. goal '…law of total probability' names the 'Law of Total Probability' topic."""
    goal_words = set(re.findall(r"[a-z]+", str(goal or "").lower()))
    if not goal_words:
        return False
    for field in ("subject_key", "title"):
        raw = str(topic.get(field) or "").replace("_", " ").lower()
        terms = {w for w in re.findall(r"[a-z]+", raw) if len(w) >= 3 and w not in _GOAL_MATCH_GLUE}
        if terms and terms <= goal_words:
            return True
    return False


# Generic wrapper words that carry no subject identity in a prerequisite name ("Combinatorial PRINCIPLES",
# "counting BASICS"). Stripped before deciding whether a prereq is just the goal subject in disguise.
_GENERIC_PREREQ_WORDS = frozenset({
    "principle", "principles", "basic", "basics", "fundamental", "fundamentals", "foundation", "foundations",
    "essential", "essentials", "concept", "concepts", "idea", "ideas", "theory", "introduction", "intro",
    "overview", "notation", "method", "methods", "technique", "techniques", "skill", "skills", "analysis",
})


def _is_circular_prereq(name: str, goal: str | None) -> bool:
    """True when a proposed prerequisite is really THE GOAL SUBJECT wrapped in generic words — e.g. goal
    'learn combinatorial analysis' with prereq 'Combinatorial Principles'. Such a prereq is CIRCULAR (its
    open_study_path link would open a path teaching the very subject the learner asked for) and the concepts
    it hides are this path's own first topics. After dropping generic wrapper words, if every remaining
    distinctive word appears in the goal (light stemming so 'combinatorics'≈'combinatorial'), it's circular.
    A prereq from a DIFFERENT subject ('basic probability', 'binary search trees') keeps a distinctive word
    the goal lacks and passes."""
    goal_words = set(re.findall(r"[a-z]+", str(goal or "").lower()))
    if not goal_words:
        return False

    def _in_goal(w: str) -> bool:
        if w in goal_words:
            return True
        # light stem: shared 6+ char prefix ("combinatorics" ~ "combinatorial")
        return any(len(w) >= 6 and len(g) >= 6 and (g.startswith(w[:6]) or w.startswith(g[:6]))
                   for g in goal_words)

    words = [w for w in re.findall(r"[a-z]+", str(name or "").lower())
             if len(w) >= 3 and w not in _GOAL_MATCH_GLUE and w not in _GENERIC_PREREQ_WORDS]
    # All generic ("basics", "fundamentals") → names no outside subject at all → circular/useless as a prereq.
    if not words:
        return True
    return all(_in_goal(w) for w in words)


# Broad whole-DISCIPLINE names that make poor prerequisites: they restate an entire field rather than the
# specific concept the goal actually needs, and their sub-concepts usually appear as their OWN, tighter prereqs
# (live failure: a z-score path listed BOTH 'Statistics' and 'mean and median', where Statistics' own
# "what to learn" was mean/median/mode — pure redundancy). Dropped only when a more specific prereq remains.
_UMBRELLA_FIELDS = frozenset({
    "statistics", "mathematics", "math", "maths", "programming", "coding", "computer science",
    "computing", "data science", "science", "engineering", "arithmetic",
})


def _drop_umbrella_prereqs(prereqs: list[str]) -> list[str]:
    """Remove a broad umbrella-discipline prerequisite ('Statistics', 'Mathematics') when at least one more
    specific prerequisite remains — the specific one is what the learner actually needs, and the umbrella just
    duplicates it vaguely. If EVERY prereq is an umbrella (nothing more specific), keep them untouched."""
    specific = [p for p in prereqs if _norm_title(p) not in _UMBRELLA_FIELDS]
    if specific and len(specific) < len(prereqs):
        dropped = [p for p in prereqs if _norm_title(p) in _UMBRELLA_FIELDS]
        _log.info("topic_decomposition: dropped umbrella-field prereq(s) %s (kept specific: %s)", dropped, specific)
    return specific if specific else prereqs


def _norm_title(t: str) -> str:
    """Lowercase alnum words of a title, minus glue, for equality/containment checks."""
    return " ".join(w for w in re.findall(r"[a-z0-9]+", str(t or "").lower())
                    if w not in _GOAL_MATCH_GLUE)


# Role verbs for renaming a topic whose bare title collides with the path/goal or another topic. An
# application/synthesis topic BECOMES "Applying <X>"; a review/practice one "Practicing <X>".
_SYNTHESIS_ROLES = {"application": "Applying", "problem_solving_application": "Applying",
                    "synthesis": "Applying", "review": "Reviewing", "practice": "Practicing"}


def _disambiguate_topic_titles(ordered: list[dict[str, Any]], goal: str | None) -> None:
    """Deterministic decomposition validation (naming): a TEACHING topic must not carry the same title as the
    whole path/goal ('Combinatorial Analysis' topic on a Combinatorial-Analysis path) nor duplicate an earlier
    topic's title — both read as 'why is this here?' to a learner. Rename the offender by its ROLE ('Applying
    Combinatorial Analysis' for an application/synthesis topic), else prefix a clarifier. Mutates in place."""
    goal_words = set(_norm_title(goal).split())
    seen: dict[str, int] = {}
    teaching_seen = 0
    for t in ordered:
        if _is_opener(t):
            continue
        title = str(t.get("title") or "").strip()
        words = set(_norm_title(title).split())
        if not words:
            teaching_seen += 1
            continue
        role = str(t.get("content_role") or "").lower()
        ttype = str(t.get("topic_type") or "").lower()
        verb = _SYNTHESIS_ROLES.get(role) or _SYNTHESIS_ROLES.get(ttype)
        # Title IS the whole path subject (all its words in the goal, a substantial >=2-word subject) AND it is a
        # LATE synthesis/application topic — real teaching topics already precede it, so a topic re-titled the
        # whole subject is a redundant synthesis, not the primary lesson. (A single-concept path whose one topic
        # legitimately IS the subject — 'Bayes Theorem' — is left alone: teaching_seen is 0 there.)
        collides_goal = bool(verb) and len(words) >= 2 and words <= goal_words and teaching_seen >= 2
        collides_prev = " ".join(sorted(words)) in seen
        if collides_goal or collides_prev:
            if verb and not title.lower().startswith(verb.lower()):
                t["title"] = f"{verb} {title}"
            elif collides_prev and not title.lower().startswith(("more on", "further")):
                t["title"] = f"More on {title}"
            _log.info("topic_decomposition: disambiguated colliding title %r -> %r "
                      "(goal=%s prev=%s)", title, t.get("title"), collides_goal, collides_prev)
        seen[" ".join(sorted(_norm_title(str(t.get("title") or "")).split()))] = 1
        teaching_seen += 1


# Generic words that, appended to a topic title, do NOT change its subject — so 'X' and 'X Mechanisms' are the
# same lesson. A REAL distinguishing word (e.g. 'Trees' in 'Binary Search Trees') is deliberately NOT here, so
# only filler-only title differences collapse.
_GENERIC_TOPIC_FILLER = frozenset({
    "mechanisms", "mechanism", "overview", "fundamentals", "fundamental", "basics", "basic", "concepts",
    "concept", "process", "processes", "explained", "introduction", "intro", "techniques", "technique",
    "methods", "essentials", "principles", "principle", "walkthrough", "guide", "review", "understanding",
    "working", "details", "detail", "deep", "dive", "explainer", "primer", "explanation", "insights",
})


def _significant_title_words(topic: dict[str, Any]) -> set[str]:
    """Distinctive title words (>=3 chars, minus generic prereq glue) for near-duplicate detection."""
    return {w for w in _norm_title(topic.get("title")).split()
            if len(w) >= 3 and w not in _GENERIC_PREREQ_WORDS}


def _collapse_near_duplicate_topics(topics_out: list[dict[str, Any]]) -> set:
    """Two TEACHING topics of the SAME type whose titles differ only by a GENERIC filler word ('TCP Congestion
    Control' vs 'TCP Congestion Control Mechanisms') are the same lesson — the learner would read it twice (live
    failure: a TCP path shipped both). Keep the earlier topic, merge the later's in_scope into it, drop the later.
    Requires a substantial (>=2 significant) shared subject AND the extra words to be pure filler, so 'Binary
    Search' vs 'Binary Search Trees' (a real distinguishing concept) stays two topics. Mutates topics_out."""
    teaching = [t for t in topics_out if not _is_opener(t)]
    remove_ids: set = set()
    for i, a in enumerate(teaching):
        if id(a) in remove_ids:
            continue
        aw = _significant_title_words(a)
        for b in teaching[i + 1:]:
            if id(b) in remove_ids or str(a.get("topic_type")) != str(b.get("topic_type")):
                continue
            bw = _significant_title_words(b)
            if not aw or not bw:
                continue
            if aw <= bw:
                small, large = aw, bw
            elif bw <= aw:
                small, large = bw, aw
            else:
                continue                                    # neither subsets the other -> distinct subjects
            if len(small) < 2 or not (large - small) <= _GENERIC_TOPIC_FILLER:
                continue
            a_scope = list(a.get("in_scope") or [])          # merge b's scope so no content is lost
            seen = {str(s).lower() for s in a_scope}
            for s in (b.get("in_scope") or []):
                if str(s).lower() not in seen:
                    a_scope.append(s)
                    seen.add(str(s).lower())
            a["in_scope"] = a_scope
            remove_ids.add(id(b))
            _log.info("topic_decomposition: collapsed near-duplicate topic %r into %r (filler-only title diff)",
                      b.get("title"), a.get("title"))
    if remove_ids:
        topics_out[:] = [t for t in topics_out if id(t) not in remove_ids]
    return remove_ids


def _topic_teaches_prereq(topic: dict[str, Any], prereq_names: list[str]) -> bool:
    """True when a topic teaches a concept the path also declared an external PREREQUISITE — i.e. the topic's
    title/subject fully contains a declared prereq's significant words ('Implementing Graph Representation'
    teaches the declared 'Graph Representation' prereq)."""
    tw: set[str] = set()
    for field in ("title", "subject_key"):
        tw |= set(_norm_title(topic.get(field)).split())
    for name in prereq_names:
        pw = {w for w in _norm_title(name).split() if len(w) >= 3}
        if pw and pw <= tw:
            return True
    return False


def _fold_prereq_topics(topics_out: list[dict[str, Any]], prereq_names: list[str], goal: str | None) -> list[str]:
    """A concept is EITHER an external prerequisite OR a taught topic — never both. When the LLM declares a
    concept as a prerequisite AND also emits a standalone topic for it ('Graph Representation' prereq + the
    'Implementing Graph Representation' topic on a Dijkstra path), the learner is assumed to have it, so keep the
    PREREQUISITE (external, linked) and REMOVE the redundant topic. Never removes a goal-named topic (in scope)
    nor the last teaching topic. Mutates topics_out in place; returns the removed titles."""
    if not prereq_names:
        return []
    teaching = [t for t in topics_out if not _is_opener(t)]
    remove_ids, removed = set(), []
    for t in teaching:
        if _goal_names_topic(t, goal):
            continue                                    # the goal names it → it stays a taught topic
        if _topic_teaches_prereq(t, prereq_names):
            remove_ids.add(id(t))
            removed.append(str(t.get("title") or ""))
    if remove_ids and len(remove_ids) < len(teaching):  # never fold away every teaching topic
        topics_out[:] = [t for t in topics_out if id(t) not in remove_ids]
        _log.info("topic_decomposition: folded %d prereq-duplicate topic(s) into prereqs: %s", len(removed), removed)
        return removed
    return []


def _repair_topic_title(title: str, subject_key: str) -> str:
    """Repair a title that begins with a dangling preposition/conjunction (an LLM decomposition artifact) by
    stripping the leading run; if that empties it, fall back to the subject phrase. A clean title is unchanged."""
    tokens = str(title or "").split()
    j = 0
    while j < len(tokens) and tokens[j].lower().strip(",.:;") in _LEADING_TITLE_JUNK:
        j += 1
    if j == 0:
        return title
    rest = tokens[j:]
    if not rest:
        return _subject_phrase(subject_key)
    repaired = " ".join(rest)
    return repaired[0].upper() + repaired[1:]


def _to_legacy(topic: dict[str, Any], title_by_id: dict[str, str], fallback_order: int) -> dict[str, Any]:
    """Adapt one decomposed topic into the legacy topic dict the lesson pipeline consumes, carrying the
    planning fields (incl. relationship_to_parent — the Part C signal) for downstream use/audit."""
    edges = topic.get("topic_relationships") or []
    rel = next((str(e.get("relationship")) for e in edges
                if isinstance(e, dict) and e.get("relationship") == IMPLEMENTATION_FOLLOW_UP), None)
    prereq_titles = [title_by_id.get(str(e.get("parent_topic_id")))
                     for e in edges if isinstance(e, dict)]
    prereq_titles = [p for p in prereq_titles if p]

    subject = str(topic.get("subject_key") or "")
    title = str(topic.get("title") or "").strip()
    if not title:  # synthesized follow-ups have no LLM title
        title = (f"Implementing {_subject_phrase(subject)}"
                 if canonical_action(topic.get("primary_action")) == "implement"
                 else _subject_phrase(subject))
    title = _repair_topic_title(title, subject)
    topic_type = str(topic.get("topic_type") or resolve_topic_type(topic.get("content_role")) or "concept_intuition")

    modifiers = list(topic.get("modifiers") or [])
    if rel == IMPLEMENTATION_FOLLOW_UP and IMPLEMENTATION_FOLLOW_UP not in modifiers:
        modifiers.append(IMPLEMENTATION_FOLLOW_UP)

    _incoming_meta = topic.get("decomposition_metadata")
    _carried_meta: dict[str, Any] = {}
    if isinstance(_incoming_meta, dict):
        # carry the intro's structured prereq maps (gloss = what it is; requirement = what you must know
        # about it for this path) so the lean generator can render the two-line prereq bullets.
        for _k in ("assumed_prerequisite_glosses", "assumed_prerequisite_requirements"):
            if _incoming_meta.get(_k):
                _carried_meta[_k] = _incoming_meta[_k]

    return {
        "title": title[:255],
        "purpose": str(topic.get("purpose") or topic.get("primary_capability") or
                       f"Reach the capability: {topic.get('primary_capability') or title}."),
        "learner_outcome": str(topic.get("learner_outcome") or topic.get("primary_capability") or title),
        "unit_title": str(topic.get("unit_title") or "Core Concepts")[:255],
        "topic_type": topic_type,
        "course_type": topic_type,
        "secondary_course_types": [],
        "prerequisite_topics": ", ".join(prereq_titles),
        "assumed_prerequisites": list(topic.get("assumed_prerequisites") or []),
        "source_refs": ", ".join(str(s) for s in (topic.get("source_refs") or [])),
        "in_scope": list(topic.get("in_scope") or []),
        "out_of_scope": list(topic.get("out_of_scope") or []),
        "practice_target": str(topic.get("practice_target") or ""),
        "practice_format": str(topic.get("practice_format") or ""),
        "estimated_minutes": int(topic.get("estimated_minutes") or 10),
        "order_index": int(topic.get("order_index") or fallback_order),
        "modifiers": modifiers,
        # carried planning fields (Part C signal + audit)
        "subject_key": subject,
        "capability_id": str(topic.get("capability_id") or ""),
        "primary_action": str(topic.get("primary_action") or ""),
        "content_role": str(topic.get("content_role") or ""),
        "practice_evidence_type": str(topic.get("practice_evidence_type") or ""),
        "expected_output": str(topic.get("expected_output") or ""),
        "basis": str(topic.get("basis") or "goal"),
        "policy_reason": topic.get("policy_reason"),
        "relationship_to_parent": rel,
        # persisted audit blob (TOPIC_DECOMPOSITION_SPEC.md step 8)
        "decomposition_metadata": {
            "schema_version": 1,
            "subject_key": subject,
            "capability_id": str(topic.get("capability_id") or ""),
            "primary_action": str(topic.get("primary_action") or ""),
            "content_role": str(topic.get("content_role") or ""),
            "practice_evidence_type": str(topic.get("practice_evidence_type") or ""),
            "expected_output": str(topic.get("expected_output") or ""),
            "basis": str(topic.get("basis") or "goal"),
            "policy_reason": topic.get("policy_reason"),
            "relationship_to_parent": rel,
            # carry the intro's structured prereq glosses (name->one-line "what it is") so the lean generator
            # can render "name — gloss" bullets and thread the gloss into the open_study_path popup.
            **_carried_meta,
        },
    }


def _is_opener(topic: dict[str, Any]) -> bool:
    return (str(topic.get("topic_type") or "") == "study_path_introduction"
            or str(topic.get("content_role") or "").lower() == "orientation")


# capability_ids / subjects a GENUINE orientation topic uses — anything else means the LLM loaded a real
# concept into the intro slot.
_GENERIC_INTRO_IDS = frozenset({"orientation", "study_path_intro", "study_path_introduction",
                                "synth_intro", "overview", "introduction"})


def _is_conflated_intro(topic: dict[str, Any]) -> bool:
    """True when an 'orientation'/study_path_introduction topic is actually a mislabeled CONCEPT — it carries
    a concrete subject + a teaching deliverable (expected_output + a real practice evidence type). The LLM
    sometimes titles the intro after the first concept (e.g. an intro 'Law of Total Probability' that then
    never teaches it), which starves that concept of a worked example and hides that there is no real intro."""
    if not _is_opener(topic):
        return False
    cap = str(topic.get("capability_id") or "").lower()
    subj = str(topic.get("subject_key") or "").lower()
    generic = (not cap) or cap in _GENERIC_INTRO_IDS or subj in _GENERIC_INTRO_IDS
    has_deliverable = (bool(str(topic.get("expected_output") or "").strip())
                       and str(topic.get("practice_evidence_type") or "").strip() not in ("", "none"))
    return (not generic) and has_deliverable


# Leading goal-preamble words stripped when deriving the intro title ("I want to learn about X" -> "X").
_INTRO_FILLER = frozenset({
    "i", "want", "wanna", "would", "like", "wish", "need", "hope", "aim", "trying", "try", "to",
    "learn", "learning", "understand", "understanding", "study", "studying", "know", "knowing",
    "master", "mastering", "explore", "exploring", "review", "reviewing", "about", "more", "get",
})
_TITLE_SMALL_WORDS = frozenset({"and", "or", "of", "the", "a", "an", "to", "for", "in", "on", "with", "by"})


def _intro_title(goal: str | None) -> str:
    """A clean, presentable intro title from a messy goal ('wANT TO LEARN ABOUT bayes...' ->
    'Introduction to Bayes Theorem ...'). Strips leading preamble words and normalizes wild casing."""
    tokens = re.findall(r"[A-Za-z0-9'+#/-]+", str(goal or ""))
    i = 0
    while i < len(tokens) and tokens[i].lower() in _INTRO_FILLER:
        i += 1
    core = tokens[i:]
    if not core:
        return "Introduction & Key Terms"
    titled = " ".join(w.lower() if (j and w.lower() in _TITLE_SMALL_WORDS) else w.capitalize()
                      for j, w in enumerate(core))
    return f"Introduction to {titled}"[:255]


def _path_assumed_prereqs(path_plan: dict[str, Any]) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """Parse path_plan.assumed_prerequisites — the LLM's STRUCTURED external-prerequisite list — into an
    ordered list of clean concept names, a name->gloss map (WHAT IT IS, the one-line refresher), and a
    name->required_knowledge map (what the learner must know about it to follow THIS path). This is the
    source of truth for the intro's prerequisites card and the prerequisite links, replacing prose
    extraction. Tolerates plain strings or {name, gloss, required_knowledge} dicts; dedupes
    case-insensitively; caps at 4 (prereqs are FEW by contract — a flooded list means the model ignored
    the constraint, and the leading entries are the ones it considered most essential)."""
    names: list[str] = []
    glosses: dict[str, str] = {}
    requirements: dict[str, str] = {}
    seen: set[str] = set()
    for item in (path_plan.get("assumed_prerequisites") or []):
        if isinstance(item, str):
            name, gloss, req = item.strip(), "", ""
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("concept") or item.get("title") or "").strip()
            gloss = str(item.get("gloss") or item.get("description") or "").strip()
            req = str(item.get("required_knowledge") or item.get("requirement") or "").strip()
        else:
            continue
        name = name.strip().strip(".").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
        if gloss:
            glosses[name] = gloss
        if req:
            requirements[name] = req
        if len(names) >= 4:
            break
    return names, glosses, requirements


def _synthesize_intro_topic(goal: str | None) -> dict[str, Any]:
    """A lightweight orientation opener (study_path_introduction). Its cards — background, prerequisites
    (named, not taught), shared terms, roadmap — are generated downstream from the blueprint + siblings;
    here we only mint the topic shell so a multi-topic path never starts cold when the LLM omits an intro."""
    return {
        "topic_id": "synth_intro",
        "capability_id": "orientation",
        "title": _intro_title(goal),
        "subject_key": normalize_subject_key(str(goal or "")) or "overview",
        "primary_action": "understand",
        "content_role": "orientation",
        "topic_type": "study_path_introduction",
        "practice_target": "", "practice_format": "", "practice_evidence_type": "", "expected_output": "",
        "in_scope": [], "out_of_scope": [],
        "basis": "goal",
        "estimated_minutes": 8,
        "purpose": ("Orient the learner: frame the area, name the assumed prerequisites (without teaching "
                    "them), define the shared terms, and preview the topics ahead."),
        "topic_relationships": [],
        "provenance": {"synthesized": True, "reason": "intro_guarantee"},
    }


def generate_decomposed_topics(
    goal: str | None,
    chunks_text: str,
    feedback: str | None = None,
    *,
    model_fn: Optional[ModelFn] = None,
    resolve_overlap: Optional[OverlapResolver] = None,
) -> list[dict[str, Any]]:
    """Single-call decompose -> append coding follow-ups -> validate -> adapt to legacy topics.
    Returns [] when the model produced nothing usable (caller falls back to the legacy generator)."""
    payload = {"system": SYSTEM_PROMPT,
               "user": build_decomposition_prompt(goal=goal, chunks_text=chunks_text, feedback=feedback)}
    parsed = _coerce((model_fn or _default_model_fn)(payload))
    raw_topics = [t for t in (parsed.get("topics") or []) if isinstance(t, dict)]
    if not raw_topics:
        return []

    path_plan = parsed.get("path_plan") if isinstance(parsed.get("path_plan"), dict) else {}
    path_plan.setdefault("required_capabilities", [])
    path_plan.setdefault("end_capability_actions", [])

    topics = [_normalize_topic(t) for t in raw_topics]
    path_plan, topics = append_coding_follow_ups(path_plan, topics)
    resolver = resolve_overlap if resolve_overlap is not None else _default_resolver()
    result = validate_topic_decomposition(path_plan, topics, goal or "", resolve_overlap=resolver)
    if not result.ok:
        _log.info("topic_decomposition: validator flagged %d issues: %s",
                  len(result.actions), [a.detail for a in result.actions if a.outcome == "FLAG"][:5])

    # Intro guarantee — a multi-topic path ALWAYS opens with a lightweight orientation topic. The LLM
    # does not reliably emit one (and the validator stays pure), so synthesize it here when missing;
    # order_index 0 puts it ahead of the validated topics before the renumber below.
    topics_out = list(result.topics)
    # De-conflate: an 'orientation' topic the LLM actually loaded with a concrete concept is a mislabeled
    # teaching topic — restore its teaching type so the concept is TAUGHT (worked example + adapter), which
    # also frees the intro slot so a real generic orientation topic is synthesized below.
    for t in topics_out:
        if _is_conflated_intro(t):
            t["topic_type"] = "math_formula_method"       # domain gate remaps for non-math paths
            t["content_role"] = "calculation"
            _log.info("topic_decomposition: de-conflated mislabeled intro %r -> teaching topic", t.get("title"))

    # Prerequisites are NAMED, not taught: a `foundation`-role topic is a building block the learner is
    # assumed to have. When the path also has a real (non-foundation) concept topic, drop the foundation
    # topics and carry them as ASSUMED PREREQUISITES on the intro — mentioned in its prerequisites card,
    # never a standalone teaching topic. If EVERY teaching topic is foundation, keep them (the goal IS that
    # foundation).
    def _role(t: dict[str, Any]) -> str:
        return str(t.get("content_role") or "").lower()

    # A concept the GOAL explicitly names is IN scope — it must stay a taught topic, never be demoted to an
    # external prerequisite (§3.1 rule 1). E.g. goal "…and law of total probability" → Law of Total Probability
    # is a topic, not a prereq link. Same for a CIRCULAR foundation whose title is just the goal subject in
    # generic wrapping ("Combinatorial Principles" on a combinatorial-analysis path) — folding it would turn
    # the path's own first units into a self-referencing prereq link (live failure: the path collapsed to
    # Binomial+Applications with everything else "assumed"). Both stay taught.
    foundations = [t for t in topics_out
                   if not _is_opener(t) and _role(t) == "foundation" and not _goal_names_topic(t, goal)
                   and not _is_circular_prereq(str(t.get("title") or t.get("subject_key") or ""), goal)]
    real_concepts = [t for t in topics_out if not _is_opener(t) and _role(t) != "foundation"]
    dropped_prereqs: list[str] = []
    if foundations and real_concepts:
        dropped_prereqs = [str(t.get("title") or _subject_phrase(str(t.get("subject_key") or ""))).strip()
                           for t in foundations]
        drop_ids = {id(t) for t in foundations}
        topics_out = [t for t in topics_out if id(t) not in drop_ids]
        _log.info("topic_decomposition: folded %d prerequisite topic(s) into the intro: %s",
                  len(dropped_prereqs), dropped_prereqs)

    non_intro = [t for t in topics_out if not _is_opener(t)]
    has_opener = any(_is_opener(t) for t in topics_out)
    # Synthesize an intro for a multi-topic path — OR whenever we folded prerequisites that need a home.
    # (A genuinely single-technique path is intentionally left lean, no intro padding — see the fixture tests.)
    if not has_opener and (len(non_intro) >= 2 or (dropped_prereqs and non_intro)):
        intro = _synthesize_intro_topic(goal)
        intro["order_index"] = 0
        topics_out = [intro, *topics_out]
        _log.info("topic_decomposition: synthesized orientation intro (LLM emitted none)")

    # The intro's prerequisites are the SINGLE structured source of truth for its prerequisites card and the
    # prereq links: the LLM's explicit path_plan.assumed_prerequisites (clean concept names + glosses) plus
    # any foundation topics we folded above. No prose parsing — these names are canonical by construction.
    # Exclude any prereq the GOAL itself names (that concept is in-scope, taught, not an external prereq).
    llm_prereqs, prereq_glosses, prereq_requirements = _path_assumed_prereqs(path_plan)
    # Drop a declared prereq the goal names (in scope, taught) or one that is circular (goal subject in generic
    # wrapping) — those must stay taught topics, never external links.
    llm_prereqs = [p for p in llm_prereqs
                   if not _goal_names_topic({"title": p, "subject_key": p}, goal)
                   and not _is_circular_prereq(p, goal)]
    # Drop a broad umbrella-discipline prereq ('Statistics') when a more specific one remains ('mean and
    # median') — the umbrella just vaguely restates the specific concept, which is the redundancy learners notice.
    llm_prereqs = _drop_umbrella_prereqs(llm_prereqs)
    # A concept is EITHER an external prerequisite OR a topic this path teaches — never both. When the LLM
    # declares a concept as a prereq AND also emits a standalone topic for it (live failure: 'Graph
    # Representation' prereq + the 'Implementing Graph Representation' topic on a Dijkstra path), the learner is
    # ASSUMED to have it — so keep the PREREQUISITE (external, linked) and fold away the redundant topic, rather
    # than padding a Dijkstra path with a full graph-representation lesson. Recompute `teaching` afterward.
    _fold_prereq_topics(topics_out, llm_prereqs, goal)
    teaching = [t for t in topics_out if not _is_opener(t)]
    # Deterministic backstop: concepts shared across ≥2 topics' in_scope but taught by none are prerequisites the
    # LLM tends to omit (e.g. 'conditional probability' on a Bayes path). Their gloss is harvested downstream from
    # the intro's key-terms card if it defines them (and the term is then removed from key-terms — see §overlap).
    auto_prereqs = _cross_topic_foundations(teaching, goal)
    structured_prereqs = [*llm_prereqs, *auto_prereqs, *dropped_prereqs]
    if structured_prereqs:
        for t in topics_out:
            if _is_opener(t):
                ap = list(t.get("assumed_prerequisites") or [])
                have = {a.lower() for a in ap}
                for p in structured_prereqs:
                    if p and p.lower() not in have:
                        ap.append(p)
                        have.add(p.lower())
                t["assumed_prerequisites"] = ap
                if prereq_glosses or prereq_requirements:
                    meta = t.setdefault("decomposition_metadata", {})
                    if prereq_glosses:
                        meta["assumed_prerequisite_glosses"] = {
                            **(meta.get("assumed_prerequisite_glosses") or {}), **prereq_glosses}
                    if prereq_requirements:
                        meta["assumed_prerequisite_requirements"] = {
                            **(meta.get("assumed_prerequisite_requirements") or {}), **prereq_requirements}
                break

    # Collapse near-duplicate teaching topics (filler-only title difference) BEFORE renaming/ordering, so the
    # learner never gets the same lesson twice; the order_index renumber below closes any gap.
    _collapse_near_duplicate_topics(topics_out)
    ordered = sorted(topics_out, key=lambda t: int(t.get("order_index") or 0))
    _disambiguate_topic_titles(ordered, goal)
    title_by_id = {str(t.get("topic_id")): str(t.get("title") or "") for t in ordered if t.get("title")}
    # synthesized follow-ups have no title yet — give title_by_id their adapted title too
    for i, t in enumerate(ordered, start=1):
        if not t.get("title"):
            subject = str(t.get("subject_key") or "")
            title_by_id[str(t.get("topic_id"))] = (
                f"Implementing {_subject_phrase(subject)}"
                if canonical_action(t.get("primary_action")) == "implement" else _subject_phrase(subject))

    legacy = [_to_legacy(t, title_by_id, i) for i, t in enumerate(ordered, start=1)]
    for i, t in enumerate(legacy, start=1):
        t["order_index"] = i
    return legacy
