"""Always-on generation observability (STUDY_PATH_CONTENT_SPEC §M7).

A per-topic causal record of HOW a worked example was produced — which generator ran, what each
returned, and WHY it withheld or fell back — so issues are read from a record instead of inferred from
the output. Persisted to `lesson_json.metadata.generation_report` (travels with the lesson, queryable
from the DB) and appended to `logs/generation_report.jsonl` (cross-path analysis).

Design: a contextvar accumulator so the decision points (in trace_pipeline / solver) can record without
threading a report object through every signature. All record helpers are NO-OPS when no report is
active, so tests and offline paths are unaffected unless a report is explicitly started. Observability
must NEVER break generation — every persist is best-effort.
"""
from __future__ import annotations

import contextvars
import json
import os
import threading
from typing import Any, Optional

_current: contextvars.ContextVar[Optional["GenerationReport"]] = \
    contextvars.ContextVar("azalea_generation_report", default=None)
_lock = threading.Lock()
_JSONL_PATH = os.getenv("AZALEA_GENERATION_REPORT_PATH", os.path.join("logs", "generation_report.jsonl"))


class GenerationReport:
    """Accumulates the worked-example decision tree for one topic generation."""

    def __init__(self, topic: Any):
        get = topic.get if isinstance(topic, dict) else (lambda k, d=None: getattr(topic, k, d))
        self.topic_id = str(get("id", "") or "")
        self.topic_type = str(get("topic_type", None) or get("course_type", None) or "")
        self.title = str(get("title", "") or "")
        self.worked_example: dict[str, Any] = {}
        self.errors: list[str] = []

    def we(self, **kw: Any) -> None:
        self.worked_example.update({k: v for k, v in kw.items() if v is not None})

    def error(self, msg: Any) -> None:
        self.errors.append(str(msg))

    def to_dict(self) -> dict[str, Any]:
        return {"topic_id": self.topic_id, "topic_type": self.topic_type, "title": self.title,
                "worked_example": self.worked_example, "errors": self.errors}


def start(topic: Any) -> GenerationReport:
    report = GenerationReport(topic)
    _current.set(report)
    return report


def current() -> Optional[GenerationReport]:
    return _current.get()


def we(**kw: Any) -> None:
    """Record worked-example facts onto the active report (no-op if none)."""
    r = _current.get()
    if r is not None:
        r.we(**kw)


def error(msg: Any) -> None:
    r = _current.get()
    if r is not None:
        r.error(msg)


def finish_and_persist() -> Optional[dict[str, Any]]:
    """Append the active report to the JSONL log, clear it, and return its dict (for the caller to also
    stash on lesson_json.metadata). Best-effort — never raises."""
    r = _current.get()
    if r is None:
        return None
    payload = r.to_dict()
    try:
        directory = os.path.dirname(_JSONL_PATH)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with _lock, open(_JSONL_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception:  # noqa: BLE001 — observability must never break generation
        pass
    _current.set(None)
    return payload
