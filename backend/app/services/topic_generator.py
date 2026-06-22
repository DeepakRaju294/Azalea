from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from app.prompts.topic_prompt import SYSTEM_PROMPT, build_topic_prompt
from app.services.course_type_classifier import enrich_topic_with_course_type
from app.services.llm_client import generate_structured_topics

if TYPE_CHECKING:
    from app.models.content_chunk import ContentChunk

_log = logging.getLogger(__name__)

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
})


def _subject_tokens(title: str, extra_framing: frozenset[str] = frozenset()) -> tuple[frozenset[str], str]:
    base = [t for t in _re.findall(r"[a-z0-9]+", str(title or "").lower())
            if t not in _SUBJECT_FRAMING_WORDS]
    stripped = [t for t in base if t not in extra_framing]
    # Domain stripping must never EMPTY the subject — in a single-algorithm path the algorithm name
    # itself is path-common (every Quick Sort title has 'quick'/'sort'); falling back to the un-stripped
    # tokens keeps that subject so the same-subject dedup still works.
    tokens = stripped if stripped else base
    return frozenset(tokens), "".join(tokens)


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
        for tok in {x for x in _re.findall(r"[a-z0-9]+", title.lower())
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


_CODE_ABLE_TYPES = frozenset({"algorithm_walkthrough", "data_structure_operation"})
_NO_CODE_GOAL_MARKERS = ("no code", "without code", "no coding", "conceptual only", "concept only",
                         "theory only", "no programming")


def _subject_phrase(title: str) -> str:
    """A readable subject from a title (framing words removed) — e.g. 'Trace Quick Sort Algorithm
    Step by Step' -> 'Quick Sort'. Used to title the synthesized coding topic."""
    words = [w for w in _re.findall(r"[A-Za-z0-9']+", str(title or ""))
             if w.lower() not in _SUBJECT_FRAMING_WORDS]
    return " ".join(words).strip() or str(title or "").strip()


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


def generate_topics_from_chunks(
    chunks: list[ContentChunk],
    goal: str | None = None,
    feedback: str | None = None,
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
        )
        cleaned_topic["topic_type"] = cleaned_topic.get("course_type")

        cleaned_topics.append(cleaned_topic)

        earlier_titles_by_normalized_title[normalized_title] = title

    # Drop auxiliary paradigm/methodology topics (e.g. "Understanding Divide and Conquer" on a
    # merge-sort path) that the concrete algorithm topics already teach by example.
    cleaned_topics = _drop_paradigm_only_topics(cleaned_topics, goal)
    # Backstop the "one walkthrough per algorithm" prompt rule deterministically: drop a second
    # same-type topic for the same subject (e.g. a "Process Overview" walkthrough next to a
    # "Step by Step" walkthrough for quick sort) before it becomes a duplicate lesson.
    cleaned_topics = _drop_same_type_subject_duplicates(cleaned_topics)
    # Guarantee a coding_implementation follow-up exists for each algorithm/data-structure subject
    # (the blueprint rule was prompt-only, so the model often dropped it -> "coding never generated").
    cleaned_topics = _append_missing_coding_topics(cleaned_topics, goal)

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
            )
        )

    for index, topic in enumerate(cleaned_topics, start=1):
        topic["order_index"] = index
        topic["topic_type"] = topic.get("course_type")

    return cleaned_topics
