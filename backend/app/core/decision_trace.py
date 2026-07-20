"""Structured decision trace: WHY the pipeline made each choice, not just what it produced.

Every deterministic pass in decomposition/certification/lesson-generation already narrates its own
reasoning as a log line ("dropped duplicate identity...", "certified verified_example=null..."). Those
strings vanish into application logs, keyed by nothing queryable — answering "why does this topic look
like this" means grepping for the right timestamp. This module gives the SAME reasoning a persisted,
structured home: a plain list of {stage, decision, reason, detail} records attached to the thing they
explain, stored alongside data that already ships to the DB (decomposition_metadata / lesson metadata),
so the answer is a read, not a log search.

Two scopes:
  - PATH-level: decisions made before topics exist (curriculum requirements, thin-plan retry, family
    expansion, comparison dedup) — collected on `path_plan["decision_trace"]`, later attached to the
    intro topic's metadata as `path_decision_trace` (mirrors how `goal_requirements` already travels).
  - TOPIC-level: decisions about ONE topic (identity, dedup, scope backfill, adapter claim, retype,
    prereq block) — collected on `topic["_decision_trace"]` (an internal working key), moved into that
    topic's own `decomposition_metadata["decision_trace"]` at persistence time.

Recording is always best-effort: a broken instrumentation call must never break generation. Callers pass
the CONTAINER (topic dict / path_plan dict) they already have in hand — no new threading, no contextvars.
"""
from __future__ import annotations

from typing import Any

_TOPIC_KEY = "_decision_trace"
_PATH_KEY = "decision_trace"


def record_topic_decision(topic: dict[str, Any] | None, stage: str, decision: str, reason: str,
                          **detail: Any) -> None:
    """Append one decision record to a topic dict's working trace. Safe on None/malformed input."""
    if not isinstance(topic, dict):
        return
    try:
        topic.setdefault(_TOPIC_KEY, []).append(_entry(stage, decision, reason, detail))
    except Exception:  # noqa: BLE001 — instrumentation must never break generation
        pass


def record_path_decision(path_plan: dict[str, Any] | None, stage: str, decision: str, reason: str,
                         **detail: Any) -> None:
    """Append one decision record to the path plan's working trace (decisions with no single topic
    subject yet — the curriculum call, the thin-plan retry, family-level backfill)."""
    if not isinstance(path_plan, dict):
        return
    try:
        path_plan.setdefault(_PATH_KEY, []).append(_entry(stage, decision, reason, detail))
    except Exception:  # noqa: BLE001 — instrumentation must never break generation
        pass


def _entry(stage: str, decision: str, reason: str, detail: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {"stage": str(stage), "decision": str(decision), "reason": str(reason)}
    cleaned = {k: v for k, v in detail.items() if v is not None and v != [] and v != ""}
    if cleaned:
        entry["detail"] = cleaned
    return entry


def take_topic_trace(topic: dict[str, Any]) -> list[dict[str, Any]]:
    """Pop the working trace off a topic dict (removing the internal key) for persistence."""
    if not isinstance(topic, dict):
        return []
    try:
        return topic.pop(_TOPIC_KEY, []) or []
    except Exception:  # noqa: BLE001
        return []


def take_path_trace(path_plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Read the path-level trace (non-destructive — several sites read path_plan after this point)."""
    if not isinstance(path_plan, dict):
        return []
    try:
        return list(path_plan.get(_PATH_KEY) or [])
    except Exception:  # noqa: BLE001
        return []


def record_lesson_decision(topic: Any, stage: str, decision: str, reason: str, **detail: Any) -> None:
    """Append one decision record DIRECTLY onto a topic's persisted `decomposition_metadata.decision_trace`
    — for the LESSON-GENERATION layer (card grounding, adapter claim honored/blocked, term/example
    shaping), which runs after decomposition already persisted the topic and works against a `Topic` ORM
    object OR a plain v2_topic dict, never the internal `_decision_trace` working list decomposition uses.

    `decomposition_metadata` is a plain (non-Mutable) JSON column — in-place dict mutation would not be
    detected as dirty by SQLAlchemy's unit of work, so this always REASSIGNS the attribute/key with a new
    dict, which SQLAlchemy (or a plain dict update) always picks up. Best-effort; never raises."""
    try:
        if isinstance(topic, dict):
            meta = dict(topic.get("decomposition_metadata") or {})
            meta["decision_trace"] = list(meta.get("decision_trace") or []) + [_entry(stage, decision, reason, detail)]
            topic["decomposition_metadata"] = meta
        else:
            meta = dict(getattr(topic, "decomposition_metadata", None) or {})
            meta["decision_trace"] = list(meta.get("decision_trace") or []) + [_entry(stage, decision, reason, detail)]
            topic.decomposition_metadata = meta
    except Exception:  # noqa: BLE001 — instrumentation must never break generation
        pass
