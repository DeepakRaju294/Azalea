"""Live-route shadow observer for runtime binding (Milestone C, unit 10e — shadow only).

OFF BY DEFAULT and learner-invisible. When `AZALEA_RUNTIME_BINDING_SHADOW=observe`, and only after the
registered-adapter route has genuinely MISSED for a topic, this observes what runtime binding WOULD produce:
resolve the topic's concept against the reviewed contract registry, run the offline bind chain, and append a
telemetry record. It never substitutes a lesson card, changes `we_policy`, or affects the solve result — the
caller ignores its return value. Every failure is contained here so generation can never depend on it.

The reviewed-contract catalog in v1 is the Milestone B fixture set, so on real study-path traffic this records
mostly `unresolved` (no reviewed contract yet) — that is the honest shadow state until a real contract catalog
exists. Its value now is proving the seam fires, resolves, binds, and records without touching output.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

_SHADOW_ENV = "AZALEA_RUNTIME_BINDING_SHADOW"
_PATH_ENV = "AZALEA_RUNTIME_BINDING_SHADOW_PATH"
_DEFAULT_PATH = "logs/runtime_binding_shadow.jsonl"
# spec §0.2 / §13: v1 deterministic binding is sub-100ms; the reviewed per-topic budget is 5s.
_LATENCY_BUDGET_MS = 5000


def _mode() -> str:
    return os.getenv(_SHADOW_ENV, "off").strip().lower()


def is_observing() -> bool:
    return _mode() == "observe"


def _concept_key(topic: dict[str, Any]) -> str:
    get = topic.get if isinstance(topic, dict) else (lambda k, d=None: getattr(topic, k, d))
    return str(get("title", "") or get("concept", "") or "")


def _write(record: dict[str, Any]) -> None:
    path = Path(os.getenv(_PATH_ENV, _DEFAULT_PATH))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


def observe_runtime_binding(
    topic: dict[str, Any],
    *,
    registered_lookup: Optional[Callable[[dict[str, Any]], Optional[object]]] = None,
    seed: int = 0,
    write: bool = True,
) -> Optional[dict[str, Any]]:
    """Observe (never substitute). Returns the telemetry record it wrote, or None if not observing / the
    registered route did not miss. Safe to call unconditionally: it self-gates on the env flag."""
    if not is_observing():
        return None
    try:
        from app.services.examples.runtime_binding.fixtures import (
            MILESTONE_B_CONTRACTS,
            MILESTONE_B_REGISTRY,
        )
        from app.services.examples.runtime_binding.router import bind_offline
        from app.services.examples.trace_pipeline import route_adapter

        lookup = registered_lookup or (lambda t: route_adapter(t))
        owner = lookup(topic)
        if owner is not None:
            return None                                # registered adapter owns it: runtime binding must not run

        concept = _concept_key(topic)
        started = time.perf_counter()
        result = bind_offline(
            concept,
            contracts=MILESTONE_B_CONTRACTS,
            registry=MILESTONE_B_REGISTRY,
            registered_lookup=lambda scope: None,      # already confirmed the registered miss above
            seed=seed,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        record = {
            "concept": concept,
            "decision": result.decision,
            "reason": result.reason,
            "evidence_id": result.evidence.evidence_id if result.evidence else None,
            "trust_level": _trust_level(result),
            "verification_passed": bool(result.verification and result.verification.passed),
            "elapsed_ms": elapsed_ms,
            "within_budget": elapsed_ms <= _LATENCY_BUDGET_MS,
            "learner_visible": False,
        }
        if write:
            _write(record)
        return record
    except Exception as exc:  # noqa: BLE001 — the observer must never break generation
        try:
            if write:
                _write({"concept": _concept_key(topic), "decision": "observer_error", "error": str(exc),
                        "learner_visible": False})
        except Exception:  # noqa: BLE001
            pass
        return None


def _trust_level(result: Any) -> Optional[str]:
    if not (result.evidence and result.verification):
        return None
    from app.services.examples.runtime_binding.delivery import derived_trust_level
    return derived_trust_level("runtime_binding", "reviewed", result.verification)
