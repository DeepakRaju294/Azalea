"""Phase-2B on_enforced DISPLAY step (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §9.1 on_enforced).

The guarded step that shadow.py deliberately does NOT do: when a card's family is enrolled at `on_enforced`, this
actually APPLIES the resolved narration contract to the shipped card — the presentation rules (`terminal_not_narrated`
result lines) plus the per-domain framing bundle attached as additive metadata the renderer can consume.

**v1 scope = math only, presentation-only, dark by default.**
- MATH only: coding/science/concept cards are returned untouched until their slices are audited + spiked. A card's
  narration domain follows its topic type (shadow.TOPIC_TYPE_TO_NARRATION_DOMAIN).
- PRESENTATION only: it never rewrites a truth-bearing value (rule identifiers, transformed forms, the answer come
  from the trace, unchanged). It only strips the robotic narrated-terminal wrapper and records framing.
- DARK by default: `resolve_mode` returns `off_legacy` unless AZALEA_DOMAIN_NARRATION_V2 enrolls the family, so this
  is a strict no-op in production until an operator opts in.

DEFERRED to a later slice (documented, not silently skipped):
- The per-ADAPTER capability check + hard WITHHOLD. Cards do not yet carry a resolvable engine-capability slug
  (trace provenance holds the per-spec slug, not the engine slug), and the frontend has no withheld-card UI (§12).
  Until both exist, a not-ready enrolled card FALLS BACK to its legacy display (logged), never a broken withhold.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.services.narration import contracts, matrix, rollout
from app.services.narration.shadow import (
    _card_key,
    _contract_registered,
    _fact_sources_ready,
    _optional_cards_for,
    narration_domain_for_topic_type,
)

# Register the audited real-adapter capabilities at import so the fact-source enforcement is grounded in
# production (shadow only calls this from tests today). Idempotent.
try:
    from app.services.narration.audit import register_audited_capabilities

    register_audited_capabilities()
except Exception:  # noqa: BLE001 — capability grounding is best-effort; never break import
    pass

_log = logging.getLogger(__name__)

# v1 is scoped to the math slice; widen only when a domain's audit + renderer spike are approved (§9.1).
_ENFORCED_DOMAINS = ("math",)

# The narrated-terminal wrapper produced by trace_pipeline._ensure_completion (and any LLM narration that mimics
# it): "<content>. Complete: <criterion>. Final result: <ans>." / "<content>. Complete — final result: <ans>."
# For math the result line is TERMINAL, not narrated (contracts.RESULT_LINE_RULE) — strip the wrapper, keep the
# content that precedes it (which already shows the answer for a derivation/rewrite).
_NARRATED_TERMINAL_RE = re.compile(r"(?i)\.\s*complete\b\s*[:—-].*$")


def _apply_result_line_rule(text: str) -> str:
    """Drop a robotic narrated-terminal wrapper; keep everything before it. No-op when absent or when stripping
    would empty the line (then the wrapper WAS the only content, so we keep the original)."""
    stripped = _NARRATED_TERMINAL_RE.sub("", str(text or "")).rstrip()
    if not stripped:
        return str(text or "")
    return stripped if stripped.endswith((".", "!", "?")) else stripped + "."


def _enforce_card(card: dict[str, Any], domain: str, contract: contracts.NarrationContract) -> None:
    """Apply the resolved contract's presentation rules to one READY card, in place (§9.1 on_enforced display)."""
    # (1) terminal_not_narrated — clean the result field and any result-bearing points.
    if card.get("result") is not None:
        card["result"] = _apply_result_line_rule(card["result"])
    pts = card.get("points")
    if isinstance(pts, list):
        card["points"] = [_apply_result_line_rule(p) if isinstance(p, str) else p for p in pts]

    # (2) attach the framing bundle as additive metadata for the renderer (never overwrites truth-bearing fields).
    card["narration_mode"] = rollout.ON_ENFORCED
    card["narration"] = {
        "mode": rollout.ON_ENFORCED,
        "domain": domain,
        "worked_example_fields": dict(contract.worked_example_fields),
        "process_scaffold": list(contract.process_scaffold),
        "step_title_rule": contract.step_title_rule,
        "result_line_rule": contract.result_line_rule,
    }


def apply_enforced_narration(topic_type: str | None, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply the on_enforced display contract to an enrolled MATH card plan, in place; return the same list.

    Strict no-op when: the topic's narration domain is not in scope (v1 = math), the resolved contract is absent,
    or no card is enrolled beyond off_legacy. Best-effort — never raises into generation. A not-ready enrolled
    card keeps its legacy display (logged) rather than being withheld (frontend §12 withhold UI is a later slice).
    """
    domain = narration_domain_for_topic_type(topic_type)
    if domain is None or domain not in _ENFORCED_DOMAINS:
        return cards
    contract = contracts.narration_contract_for(domain)
    if contract is None:
        return cards

    optional = _optional_cards_for(str(topic_type or ""))
    applied = 0
    for card in cards:
        ct = _card_key(card)
        if not ct:
            continue
        if rollout.resolve_mode(domain, ct, topic_type) != rollout.ON_ENFORCED:
            continue
        decision = matrix.evaluate_card(
            ct, domain, blueprint_optional=(ct in optional),
            contract_registered=_contract_registered(ct, domain),
            fact_sources_ready=_fact_sources_ready(ct, domain),
        )
        if decision.action == matrix.PROCEED:
            _enforce_card(card, domain, contract)
            applied += 1
        else:
            # DEFERRED withhold: keep legacy display, record why (no frontend withhold UI yet, §12).
            card["narration_mode"] = "legacy_fallback"
            _log.info("narration_enforce fallback card_type=%s domain=%s reason=%s",
                      ct, domain, decision.reason)
    if applied:
        _log.info("narration_enforce applied domain=%s topic_type=%s cards=%d", domain, topic_type, applied)
    return cards
