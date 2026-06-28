"""The worked-example verification ladder (WORKED_EXAMPLE_ACCURACY_SPEC §3).

Front door for a topic's worked-example slot when `AZALEA_WORKED_EXAMPLE_ACCURACY_LADDER` is on:

    classify the task  →  route to exactly one treatment
        determinate computation  → Tier 1 (hard, adapter)  ∨  Tier 2 (soft, independent endpoint)  ∨  guided_fallback
        conceptual (resolved)    → None  (defer to the existing non-verified card path; no false rigor)
        unsupported / can't tell → guided_fallback  (never illustrative)

The binding invariant (Phase A1): once enabled, **no computational worked example reaches the learner
through the old self-graded path** — a determinate topic is always (verified trace) ∨ (verified endpoint) ∨
(guided_fallback), never the legacy stub. Offline (no API key) the verified paths defer, so a determinate
topic yields guided_fallback — strictly better than a self-graded stub.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from .guided_explanation import build_guided_explanation
from .task_classifier import WorkedExampleTask, classify_worked_example_task

_log = logging.getLogger(__name__)


def _enabled() -> bool:
    return os.getenv("AZALEA_WORKED_EXAMPLE_ACCURACY_LADDER", "").strip().lower() in {"1", "true", "on", "yes"}


def solve_via_accuracy_ladder(topic: dict[str, Any], *, existing_problem: str = "",
                              code: Optional[str] = None, solver=None,
                              task: Optional[WorkedExampleTask] = None) -> Optional[dict[str, Any]]:
    """Returns a worked-example result, a guided_fallback result, or None (defer to the existing path for
    conceptual topics). For determinate topics it NEVER returns None (→ the self-graded path is unreachable)."""
    task = task or classify_worked_example_task(topic)

    # Conceptual & resolved → illustrative: defer to the existing non-verified card path (no false rigor).
    if task.task_kind in ("conceptual_illustration", "comparison") and task.classification_status == "resolved":
        return None

    # "Don't know whether a computation even exists" → guided, NOT illustrative (§3.2.1).
    if task.classification_status == "unsupported":
        return build_guided_explanation(topic, reason="unsupported")

    # Determinate or ambiguous-computational → the ladder OWNS it: Tier 1 ∨ Tier 2 ∨ guided_fallback.
    r = _try_tier1(topic)
    if r is not None:
        return r
    r = _try_tier2(topic)
    if r is not None:
        return r
    return build_guided_explanation(topic, reason="no_independent_answer_anchor")


def _try_tier1(topic: dict[str, Any]) -> Optional[dict[str, Any]]:
    """HARD: an applicable adapter runs the real algorithm + the verified-trace pipeline. None offline / on
    any failure (a bug-class failure is withheld inside the pipeline; here we just get None and degrade)."""
    try:
        from .trace_pipeline import route_adapter, solve_trace_pipeline
        if route_adapter(topic) is None:
            return None
        r = solve_trace_pipeline(topic)
        if r is not None:
            meta = r.setdefault("metadata", {})
            meta["treatment"] = "hard"
            meta["verification_level"] = "hard_trace"
        return r
    except Exception as exc:  # noqa: BLE001 — the ladder must never raise into generation
        _log.warning("ladder Tier 1 error: %s", exc)
        return None


def _try_tier2(topic: dict[str, Any]) -> Optional[dict[str, Any]]:
    """SOFT: an INDEPENDENT endpoint anchor (reason→extract + verifier). Only runs when explicitly enabled
    (`AZALEA_WORKED_EXAMPLE_REASON_EXTRACT`); the final answer is checked, intermediate steps are not."""
    try:
        from .trace_pipeline import (_reason_extract_enabled, _solve_via_reason_extract, default_format_fn)
        if not _reason_extract_enabled():
            return None
        r = _solve_via_reason_extract(topic, default_format_fn, None, None, None)
        if r is not None:
            r.setdefault("metadata", {}).update(
                treatment="soft", verification_level="soft", confidence="weak_soft",
                verified_dimensions=["final_answer"],
                unverified_dimensions=["intermediate_transition_correctness", "teaching_trace_completeness"])
        return r
    except Exception as exc:  # noqa: BLE001
        _log.warning("ladder Tier 2 error: %s", exc)
        return None
