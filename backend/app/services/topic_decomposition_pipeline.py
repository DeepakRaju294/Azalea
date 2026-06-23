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

    ordered = sorted(result.topics, key=lambda t: int(t.get("order_index") or 0))
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
