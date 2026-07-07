"""Trace-to-teaching shadow evaluation (Q23 §14 shadow_validate) — run C1–C6 over trace-bound cards, log, change
nothing.

Shadow-PARALLEL to the shipped `examples/trace_contract.validate_prose`: it runs the generalized C1–C6 gate over
the same trace-bound cards and logs its verdicts, so we can measure the new gate against the shipped one WITHOUT
touching shipped behaviour. Gated by the same `AZALEA_DOMAIN_NARRATION_V2` ladder, STRICT no-op by default,
best-effort (never raises into generation), NEVER mutates cards. Only ever shadow-logs.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

from app.services.narration import rollout
from app.services.trace_teaching import checks, grammar
from app.services.trace_teaching import validator as ttv

_log = logging.getLogger(__name__)
_LOCK = threading.Lock()
_TELEMETRY_PATH = os.getenv("AZALEA_TRACE_TEACHING_SHADOW_PATH",
                            os.path.join("logs", "trace_teaching_shadow.jsonl"))

# Prose-bearing card fields (§10.1) — connective prose only. `work`/code lines are authoritative/coding-validated,
# not token-scanned here.
_STRING_FIELDS = ("main_concept", "reasoning", "goal", "why", "transformation")
_LIST_FIELDS = ("points", "body", "parts")


def _prose_fields(card: Dict[str, Any]) -> List[Tuple[str, str]]:
    fields: List[Tuple[str, str]] = []
    for f in _STRING_FIELDS:
        v = card.get(f)
        if isinstance(v, str) and v.strip():
            fields.append((f, v.strip()))
    for f in _LIST_FIELDS:
        v = card.get(f)
        if isinstance(v, list):
            joined = ". ".join(str(x).strip() for x in v if str(x).strip())
            if joined:
                fields.append((f, joined))
    return fields


def _summarize(results: List[ttv.TraceTeachingValidationResult]) -> Dict[str, int]:
    s = {"fields": len(results), "c1_fail": 0, "c4_fail": 0, "withhold": 0, "retry": 0}
    for r in results:
        for f in r.failures:
            if f.check == "C1":
                s["c1_fail"] += 1
            elif f.check == "C4":
                s["c4_fail"] += 1
        if r.decision == ttv.WITHHOLD:
            s["withhold"] += 1
        elif r.decision == ttv.RETRY:
            s["retry"] += 1
    return s


def evaluate(
    cards: List[Dict[str, Any]],
    steps_by_id: Dict[str, grammar.Step],
    *,
    gate_domain: str = "coding",
    gate_card_type: str = "worked_example",
    topic_id: str = "",
) -> Optional[Dict[str, Any]]:
    """Shadow-evaluate trace-bound cards. Returns a telemetry report (and writes it), or None when not enrolled or
    no card carries a resolvable trace-step binding. NEVER mutates `cards`."""
    if rollout.resolve_mode(gate_domain, gate_card_type, None) == rollout.OFF_LEGACY:
        return None
    if not steps_by_id:
        return None

    field_reports: List[Dict[str, Any]] = []
    results: List[ttv.TraceTeachingValidationResult] = []
    for i, card in enumerate(cards):
        sids = card.get("trace_step_ids") or []
        step = steps_by_id.get(str(sids[0])) if sids else None
        if step is None:
            continue
        for field_name, text in _prose_fields(card):
            r = ttv.run_checks(text, step, field_name=field_name, prose_bearing=True,
                               action_bearing=False, run_c6=False, trace_id=topic_id)
            results.append(r)
            field_reports.append({
                "card_index": i, "trace_step_id": step.id, "field": field_name,
                "decision": r.decision, "failures": [f.check for f in r.failures],
                "telemetry": r.telemetry,
            })

    if not field_reports:
        return None
    report = {"topic_id": topic_id, "domain": gate_domain,
              "summary": _summarize(results), "fields": field_reports}
    _record(report)
    return report


def _record(report: Dict[str, Any]) -> None:
    _log.info("trace_teaching_shadow topic=%s domain=%s summary=%s",
              report.get("topic_id"), report.get("domain"), report.get("summary"))
    try:
        directory = os.path.dirname(_TELEMETRY_PATH)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with _LOCK, open(_TELEMETRY_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(report, default=str) + "\n")
    except Exception:  # noqa: BLE001
        pass
