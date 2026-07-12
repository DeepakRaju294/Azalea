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
    # is a topic, not a prereq link. So such foundations are excluded from the fold below.
    foundations = [t for t in topics_out
                   if not _is_opener(t) and _role(t) == "foundation" and not _goal_names_topic(t, goal)]
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

    # Name the folded prerequisites on the intro so its prerequisites card mentions them (not taught).
    if dropped_prereqs:
        for t in topics_out:
            if _is_opener(t):
                ap = list(t.get("assumed_prerequisites") or [])
                for p in dropped_prereqs:
                    if p and p not in ap:
                        ap.append(p)
                t["assumed_prerequisites"] = ap
                break

    ordered = sorted(topics_out, key=lambda t: int(t.get("order_index") or 0))
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
