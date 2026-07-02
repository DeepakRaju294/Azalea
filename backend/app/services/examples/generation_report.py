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
        self.language = str(get("language", None) or "python").lower()   # the path's requested code language
        self.worked_example: dict[str, Any] = {}
        self.errors: list[str] = []

    def we(self, **kw: Any) -> None:
        self.worked_example.update({k: v for k, v in kw.items() if v is not None})

    def error(self, msg: Any) -> None:
        self.errors.append(str(msg))

    def to_dict(self) -> dict[str, Any]:
        return {"topic_id": self.topic_id, "topic_type": self.topic_type, "title": self.title,
                "language": self.language,
                "worked_example": self.worked_example, "errors": self.errors}


# ADAPTER_AND_GENERATION_SYSTEM_SPEC §1.2 — sources that mean "from-scratch LLM derivation".
# The three enumerated below are the ones solver.py emits today; the prefix guard in is_from_scratch_source
# also catches any FUTURE `legacy_*`/`gen_*` variant, so a new source can't silently slip the invariant.
_FROM_SCRATCH_SOURCES = {"gen_foundation", "legacy_coding", "legacy_outline"}


def is_from_scratch_source(source: Optional[str]) -> bool:
    """True iff `source` is a from-scratch LLM derivation (§1.2). Operational, not a literal set membership: the
    enumerated set + any `legacy` / `legacy_*` variant (that prefix reliably means the old re-derivation path).
    Deliberately NOT a `gen_*` prefix — that would misclassify a legitimate future adapter-backed source like
    `gen_trace_pipeline`; `gen_foundation` is already enumerated. (Eventual hardening: a full source trust-class
    map with fail-closed on unknown adapter-supported sources — see CP6b.)"""
    s = source or ""
    return s in _FROM_SCRATCH_SOURCES or s == "legacy" or s.startswith("legacy_")


def invariant_violations(report: dict[str, Any]) -> list[str]:
    """The SPEC §1.2 hard invariant (Checkpoints CP1/CP6): an adapter-supported topic's worked example must
    descend from the adapter trace — it may NEVER ship from a from-scratch generator. Returns the list of
    violations (empty = conformant). Pure; usable as a standing test and in batch audits over the JSONL log."""
    we = (report or {}).get("worked_example") or {}
    adapter, src = we.get("adapter"), we.get("final_source")
    out: list[str] = []
    if adapter and is_from_scratch_source(src):
        out.append(f"§1.2: adapter-supported topic '{adapter}' shipped from from-scratch source '{src}' "
                   f"(title={(report or {}).get('title')!r})")
    if adapter and we.get("tp_shipped") and we.get("verification_level") not in (None, "trace_verified"):
        out.append(f"§1.2: adapter-supported ship has verification_level="
                   f"{we.get('verification_level')!r} (expected trace_verified)")
    # CP6 coverage invariants — only assert when the fields are present (instrumented ships)
    if adapter and we.get("tp_shipped"):
        if we.get("missing_required_transition_ids"):
            out.append(f"CP6: adapter '{adapter}' shipped missing required transitions "
                       f"{we.get('missing_required_transition_ids')}")
        if we.get("terminal_rendered") is False:
            out.append(f"CP6: adapter '{adapter}' shipped without a rendered terminal/completion step")
        if we.get("missing_required_checkpoint_ids"):          # CP6b — checkpoint-level coverage
            out.append(f"CP6b: adapter '{adapter}' shipped missing required checkpoints "
                       f"{we.get('missing_required_checkpoint_ids')}")
    return out


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
