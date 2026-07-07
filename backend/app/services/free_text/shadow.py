"""Free-text shadow evaluation (Q24 §5) — run the ladder over a finalized card plan, log, change nothing.

Mirrors `narration/shadow.py`: gated by the SAME `AZALEA_DOMAIN_NARRATION_V2` ladder + per-family overrides (the
spec integrates with that flag, no separate one), STRICT no-op when every card is `off_legacy`, best-effort (never
raises into generation). This hook ONLY ever shadow-logs — it never alters display, even for a family at
`on_enforced` (enforced display is the separate guarded step). It measures a family's free-text false-claim /
unestablished rate before that flip.

Evidence (fact-pack + vocabulary) is looked up per domain from a registry seeded EMPTY here: an empty pack yields
the honest raw measurement (every factual span is unestablished → L4 `evidence_pack_missing_for_domain`, and L2
transformation refutations still surface). Populating the packs is content work tracked separately.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

from app.services.free_text import orchestrator, validator
from app.services.free_text.orchestrator import FieldContext
from app.services.narration import rollout
from app.services.narration.shadow import narration_domain_for_topic_type

_log = logging.getLogger(__name__)
_LOCK = threading.Lock()
_TELEMETRY_PATH = os.getenv("AZALEA_FREE_TEXT_SHADOW_PATH", os.path.join("logs", "free_text_shadow.jsonl"))

# Card fields that TYPICALLY carry free-text spans (Q24 §2). Trace-backed worked-example fields are Q23's, excluded.
_STRING_FIELDS = ("background", "explanation", "main_concept", "learning_goal", "intuition",
                  "why_it_matters", "what_to_notice", "summary")
_LIST_FIELDS = ("body", "points")

# Per-domain evidence registry (seeded empty; populated by content work, not the model).
_FACT_PACKS: Dict[str, Any] = {}
_VOCAB: Dict[str, Any] = {}


def register_fact_pack(domain: str, fact_pack: Any) -> None:
    _FACT_PACKS[domain] = fact_pack


def register_vocabulary(domain: str, vocab: Any) -> None:
    _VOCAB[domain] = vocab


def _card_key(card: Dict[str, Any]) -> str:
    return str(card.get("blueprint_key") or card.get("card_type") or "").strip().lower()


def _free_text_fields(card: Dict[str, Any]) -> List[Tuple[str, str]]:
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


def _summarize(claims) -> Dict[str, int]:
    s = {"spans": len(claims), "l2_refuted": 0, "l4_unsupported": 0, "established": 0,
         "withheld": 0, "deleted": 0}
    for c in claims:
        if c.l2 is not None and c.l2.verdict == "refuted":
            s["l2_refuted"] += 1
        if c.l4 is not None and c.l4.verdict == "unsupported":
            s["l4_unsupported"] += 1
        if c.establishment.status == "established":
            s["established"] += 1
        if c.decision == validator.ACTION_DELETE:
            s["deleted"] += 1
        elif c.decision in (validator.ACTION_WITHHOLD_FIELD, validator.ACTION_WITHHOLD_CARD):
            s["withheld"] += 1
    return s


def evaluate_card_plan(topic_type: Optional[str], cards: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Shadow-evaluate the free-text fields of a finalized card plan. Returns a telemetry report (and writes it),
    or None when the domain is non-gating or every enrolled card is off_legacy. NEVER changes `cards`."""
    domain = narration_domain_for_topic_type(topic_type)
    if domain is None:
        return None

    ctx = FieldContext(fact_pack=_FACT_PACKS.get(domain), vocab=_VOCAB.get(domain))
    field_reports: List[Dict[str, Any]] = []

    for card in cards:
        ct = _card_key(card)
        if not ct:
            continue
        if rollout.resolve_mode(domain, ct, topic_type) == rollout.OFF_LEGACY:
            continue  # strict no-op unless this family is enrolled
        for field_name, text in _free_text_fields(card):
            # ALWAYS shadow mode here — display is never changed from this hook.
            result = orchestrator.validate_field(field_name, text, ctx, mode=validator.SHADOW_VALIDATE)
            field_reports.append({
                "card_type": ct, "field": field_name,
                "field_decision": result.field_decision,
                "summary": _summarize(result.claims),
                "claims": result.telemetry(topic_id=str(topic_type or ""), card_type=ct),
            })

    if not field_reports:
        return None
    report = {"topic_type": topic_type, "domain": domain, "fields": field_reports}
    _record(report)
    return report


def _record(report: Dict[str, Any]) -> None:
    totals = {"l2_refuted": 0, "l4_unsupported": 0, "withheld": 0, "deleted": 0, "spans": 0}
    for fr in report.get("fields", []):
        for k in totals:
            totals[k] += fr.get("summary", {}).get(k, 0)
    _log.info("free_text_shadow domain=%s topic_type=%s totals=%s",
              report.get("domain"), report.get("topic_type"), totals)
    try:
        directory = os.path.dirname(_TELEMETRY_PATH)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with _LOCK, open(_TELEMETRY_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(report, default=str) + "\n")
    except Exception:  # noqa: BLE001
        pass
