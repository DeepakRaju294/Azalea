from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.prompts.topic_prompt import SYSTEM_PROMPT, build_topic_prompt
from app.services.course_type_classifier import enrich_topic_with_course_type
from app.services.llm_client import generate_structured_topics

if TYPE_CHECKING:
    from app.models.content_chunk import ContentChunk


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
