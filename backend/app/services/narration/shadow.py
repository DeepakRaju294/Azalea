"""Phase-2B shadow evaluation (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §9.1 shadow_validate).

Runs the Phase-2 eligibility gate + narration-contract resolution over a finalized card plan and emits telemetry
WITHOUT changing output — the `shadow_validate` mode. STRICT no-op when every card resolves to `off_legacy`
(the default), so wiring this into the live lesson pipeline has zero production impact until a family is enrolled
via AZALEA_DOMAIN_NARRATION_V2. Best-effort: never raises into generation.

Narration domain is derived from the topic type (the card's domain follows its topic type), so this needs no
path-domain threading. `on_enforced` DISPLAY changes are NOT done here — that is the guarded 2B display step.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Optional

from app.services.narration import contracts, fact_source, matrix, rollout

_log = logging.getLogger(__name__)
_LOCK = threading.Lock()
_TELEMETRY_PATH = os.getenv("AZALEA_NARRATION_SHADOW_PATH", os.path.join("logs", "narration_shadow.jsonl"))

# Topic type → coarse narration domain. A card's domain follows its topic type (§3).
TOPIC_TYPE_TO_NARRATION_DOMAIN: dict[str, str] = {
    "algorithm_walkthrough": "coding", "data_structure_operation": "coding", "coding_implementation": "coding",
    "math_formula_method": "math", "proof_reasoning": "math",
    "science_mechanism": "science",
    "concept_intuition": "concept", "terminology_components": "concept", "compare_distinguish": "concept",
    "process_walkthrough": "concept", "problem_solving_application": "concept",
    "study_path_introduction": "concept",
}


# Structural, subject-AGNOSTIC topic types: their narration domain should follow the PATH's subject domain (a math
# path's "process_walkthrough" is a MATH process, not a generic concept), not default to concept. Domain-specific
# topic types (math_formula_method, algorithm_walkthrough, science_mechanism, …) keep their own §3 mapping.
_SUBJECT_AGNOSTIC_TOPIC_TYPES = {
    "process_walkthrough", "problem_solving_application", "study_path_introduction",
    "concept_intuition", "terminology_components", "compare_distinguish",
}


def resolve_narration_domain(topic_type: str | None, path_domain: str | None = None) -> Optional[str]:
    """The card's narration domain. A card's domain follows its topic type (§3), EXCEPT for the subject-agnostic
    structural topic types, which inherit the path's subject domain when that is a gating narration domain — so a
    math path whose topics are typed `process_walkthrough`/`study_path_introduction` still gets the math contract."""
    tt = str(topic_type or "").strip().lower()
    if path_domain and tt in _SUBJECT_AGNOSTIC_TOPIC_TYPES:
        subject = matrix.narration_domain_of(path_domain)
        if subject is not None:
            return subject
    return TOPIC_TYPE_TO_NARRATION_DOMAIN.get(tt)


def narration_domain_for_topic_type(topic_type: str | None) -> Optional[str]:
    return resolve_narration_domain(topic_type)


def _card_key(card: dict[str, Any]) -> str:
    return str(card.get("blueprint_key") or card.get("card_type") or "").strip().lower()


def _optional_cards_for(topic_type: str) -> set[str]:
    try:
        from app.core.course_blueprints import get_topic_blueprint
        bp = get_topic_blueprint(topic_type)
    except Exception:  # noqa: BLE001
        return set()
    return set(bp.get("optional_cards") or []) | set(bp.get("continuation_optional_cards") or [])


def _contract_registered(card_type: str, domain: str) -> bool:
    """Whether a Phase-2 narration contract exists for this (card, domain) — the shadow proxy for 'contract
    written'. Universal/process/worked-example cards use the domain contract; formula_breakdown has its own."""
    if contracts.narration_contract_for(domain) is None:
        return False
    if card_type == "formula_breakdown":
        return contracts.formula_breakdown_framing(domain) is not None
    return True


def _fact_sources_ready(card_type: str, domain: str) -> bool:
    """Static shadow proxy: are this card's REQUIRED fact sources all registered? (Runtime adapter availability
    is the on_enforced check.) A card with no registered required sources is treated as ready (framing-only)."""
    return bool(fact_source.required_sources_for(card_type, domain) is not None)


def evaluate_card_plan(topic_type: str | None, cards: list[dict[str, Any]],
                       path_domain: str | None = None) -> Optional[dict[str, Any]]:
    """Shadow-evaluate a finalized card plan. Returns a telemetry report (and writes it), or None when the plan
    is entirely off_legacy (the default no-op) or the domain is non-gating. NEVER changes `cards`."""
    domain = resolve_narration_domain(topic_type, path_domain)
    if domain is None:
        return None

    # Strict no-op unless at least one card is enrolled beyond off_legacy.
    per_card_modes = {
        _card_key(c): rollout.resolve_mode(domain, _card_key(c), topic_type) for c in cards if _card_key(c)
    }
    if not per_card_modes or all(m == rollout.OFF_LEGACY for m in per_card_modes.values()):
        return None

    optional = _optional_cards_for(str(topic_type or ""))
    decisions: list[dict[str, Any]] = []
    for c in cards:
        ct = _card_key(c)
        if not ct:
            continue
        mode = per_card_modes.get(ct, rollout.OFF_LEGACY)
        if mode == rollout.OFF_LEGACY:
            continue
        decision = matrix.evaluate_card(
            ct, domain, blueprint_optional=(ct in optional),
            contract_registered=_contract_registered(ct, domain),
            fact_sources_ready=_fact_sources_ready(ct, domain),
        )
        decisions.append({
            "card_type": ct, "mode": mode, "action": decision.action,
            "status": decision.status, "reason": decision.reason,
        })

    if not decisions:
        return None
    report = {"topic_type": topic_type, "narration_domain": domain, "decisions": decisions}
    _record(report)
    return report


def _record(report: dict[str, Any]) -> None:
    """Best-effort structured-log + JSONL sink (never raises)."""
    actions = {d["card_type"]: d["action"] for d in report.get("decisions", [])}
    _log.info("narration_shadow domain=%s topic_type=%s decisions=%s",
              report.get("narration_domain"), report.get("topic_type"), actions)
    try:
        directory = os.path.dirname(_TELEMETRY_PATH)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with _LOCK, open(_TELEMETRY_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(report, default=str) + "\n")
    except Exception:  # noqa: BLE001
        pass
