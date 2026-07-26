"""Live-path shadow observer for retrieval grounding (§14 Phase-1F / §14.5).

Gated by AZALEA_RETRIEVAL_GROUNDED_EXAMPLES = off | shadow | live (default off). In `shadow` it OBSERVES what
retrieval-grounded verification WOULD conclude about a no-adapter worked example — retrieve an authoritative
answer, compare the solver's produced answer, derive the assurance level — and appends a telemetry record.
It NEVER changes the shipped example in shadow mode; the caller ignores the return value. Fail-closed: any
error is swallowed so generation can never depend on it. `live` is reserved for the delivery cutover (not yet).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

_ENV = "AZALEA_RETRIEVAL_GROUNDED_EXAMPLES"
_PATH_ENV = "AZALEA_RETRIEVAL_SHADOW_PATH"
_DEFAULT_PATH = "logs/retrieval_grounding_shadow.jsonl"


def mode() -> str:
    return os.getenv(_ENV, "off").strip().lower()


def is_observing() -> bool:
    return mode() in {"shadow", "live"}


def _write(record: dict[str, Any]) -> None:
    path = Path(os.getenv(_PATH_ENV, _DEFAULT_PATH))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def observe_grounding(topic: Any, produced_answer: str, *, write: bool = True) -> Optional[dict[str, Any]]:
    """Observe (never substitute) what retrieval grounding would conclude. Returns the telemetry record, or
    None if inactive / no candidate / any failure. Safe to call unconditionally — self-gates on the env flag."""
    if not is_observing():
        return None
    try:
        from app.services.examples.retrieval.cache import VerifiedContractCache
        from app.services.examples.retrieval.pipeline import resolve_and_assure
        # Fresh ephemeral cache: the observer verifies THIS produced answer fresh (never short-circuits to a
        # prior cached verification of the same instance — that cache-first behavior is for the delivery flow).
        report = resolve_and_assure(topic, str(produced_answer or ""), cache=VerifiedContractCache())
        if report is None:
            record = {"ts": time.time(), "outcome": "retrieval_miss",
                      "title": _title(topic), "produced": str(produced_answer or "")[:120]}
        else:
            record = {"ts": time.time(), "outcome": "resolved",
                      "title": _title(topic), "concept_key": report.get("concept_key"),
                      "backend": report.get("backend"), "level": report.get("level"),
                      "reproduction_status": report.get("reproduction_status"),
                      "produced": str(produced_answer or "")[:120],
                      "from_cache": report.get("from_cache")}
        if write:
            _write(record)
        return record
    except Exception:  # noqa: BLE001 — the observer must never break generation
        return None


def _title(topic: Any) -> str:
    get = topic.get if isinstance(topic, dict) else (lambda k, d=None: getattr(topic, k, d))
    return str(get("title", "") or "")
