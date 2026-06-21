"""Production cutover — gen_foundation artifact -> legacy worked-example shape (spec §12 step 6).

The legacy renderer consumes ``{problem, cards:[{title, goal, reasoning, work[], result,
teaching_note, cases_covered, prior_state, visual, code_lines}], final_answer}``
(``examples.solver._normalize_solution_cards``). This adapter maps a new single-pass
artifact onto that shape so the shadow path can RENDER through the existing frontend
without any frontend change.

``solve_via_pipeline`` is the flag-gated entry the legacy solver delegates to: it runs the
new pipeline and adapts the result, or returns ``None`` so the caller falls back to legacy.
Default behaviour (flag off) never reaches here.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from . import flags
from .cards import is_coding_card
from .llm import ModelFn, default_auditor, default_repair, default_solver
from .pipeline import run_first_pass

_log = logging.getLogger(__name__)


def _flat_refs_to_ranges(refs: Any) -> Optional[list[list[int]]]:
    """gen_foundation ``code_refs`` (flat 1-based lines) -> legacy ``code_lines`` ([start,end] pairs),
    compressing consecutive lines into ranges."""
    if not isinstance(refs, list):
        return None
    lines = sorted({r for r in refs if isinstance(r, int) and r > 0})
    if not lines:
        return None
    ranges: list[list[int]] = []
    start = prev = lines[0]
    for ln in lines[1:]:
        if ln == prev + 1:
            prev = ln
            continue
        ranges.append([start, prev])
        start = prev = ln
    ranges.append([start, prev])
    return ranges


def card_to_legacy(card: dict[str, Any]) -> dict[str, Any]:
    """Map one gen_foundation card onto the legacy Goal/Reasoning/Work/Result card."""
    coding = is_coding_card(card)
    # Coding cards carry `how`; the legacy `reasoning` field holds the code-construct explanation.
    reasoning = (card.get("how") if coding else card.get("reasoning")) or ""
    return {
        "title": str(card.get("title") or "").strip(),
        "goal": str(card.get("goal") or "").strip(),
        "reasoning": str(reasoning).strip(),
        "work": [str(w) for w in (card.get("work") or [])],
        "result": str(card.get("result") or "").strip(),
        "teaching_note": card.get("teaching_note"),
        "cases_covered": [str(c) for c in (card.get("cases_covered") or [])],
        "prior_state": card.get("prior_state"),
        "visual": "",
        "code_lines": _flat_refs_to_ranges(card.get("code_refs")),
    }


def artifact_to_legacy(artifact: dict[str, Any]) -> dict[str, Any]:
    """Map a full worked-example artifact onto the legacy ``solve_worked_example`` return."""
    cards = [card_to_legacy(c) for c in (artifact.get("cards") or [])]
    final = artifact.get("final_answer")
    return {
        "problem": str(artifact.get("problem") or artifact.get("example_input") or "").strip(),
        "cards": cards,
        "final_answer": final,
        "expected_final_answer": final,  # legacy alias
        "generated_by": "gen_foundation",  # provenance, so a render can be attributed/measured
    }


def solve_via_pipeline(
    topic: dict[str, Any],
    *,
    code: Optional[str] = None,
    solver: Optional[ModelFn] = None,
    auditor: Optional[ModelFn] = None,
    repair: Optional[ModelFn] = None,
) -> Optional[dict[str, Any]]:
    """Flag-gated entry (§12 step 6). Returns a legacy worked-example dict, or ``None`` to fall back.

    Returns ``None`` when: the shadow flag is off; the model is unavailable (offline / no key);
    the pipeline degraded or failed validation. The caller then uses the legacy solver — so a
    flipped flag with no API key safely no-ops to legacy.

    ``solver``/``auditor``/``repair`` may be ``None`` — the production hook forwards
    ``solver=None``, so we coerce to the real adapters here (passing ``None`` straight through made
    ``run_first_pass`` call ``None(payload)`` and the whole pipeline silently fell back to legacy).
    """
    if not flags.is_shadow_enabled():
        return None
    tid = topic.get("id") or topic.get("title") or "?"
    topic_for_run = dict(topic)
    if code is not None:
        topic_for_run.setdefault("code", code)
        topic_for_run.setdefault("coding_implementation", True)
    result = run_first_pass(
        topic_for_run,
        solver=solver or default_solver,
        auditor=auditor or default_auditor,
        repair=repair or default_repair,
    )

    # Provenance: log WHY a topic uses the new path or falls back to legacy, so a missing/
    # legacy-shaped worked example is explainable from the logs instead of guesswork.
    if not result.ok or result.degraded or not result.artifact:
        reason = result.note or ("degraded" if result.degraded else "validation_failed")
        _log.warning(
            "gen_foundation: FELL BACK to legacy for topic %s (reason=%s, calls=%d, errors=%s)",
            tid, reason, result.model_calls, (result.validation_errors or [])[:3],
        )
        return None
    legacy = artifact_to_legacy(result.artifact)
    if not legacy["cards"]:
        _log.warning("gen_foundation: FELL BACK to legacy for topic %s (reason=no_cards_after_adapt)", tid)
        return None
    legacy["_telemetry"] = {
        "model_calls": result.model_calls,
        "audit": result.audit_telemetry,
        "reconciliation": result.reconciliation_telemetry,
    }
    _log.info(
        "gen_foundation: authored worked example for topic %s (cards=%d, calls=%d, recon=%s)",
        tid, len(legacy["cards"]), result.model_calls,
        result.reconciliation_telemetry.get("reconciliation_status", "n/a"),
    )
    return legacy
