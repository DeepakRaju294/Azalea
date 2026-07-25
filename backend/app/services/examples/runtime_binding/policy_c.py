"""Milestone C runtime policy: latency budget + route-aware certification decision (spec §13, §2.4, §9).

Decisions taken by the owner: per-topic latency budget = 5000 ms; runtime binding ships reviewed contracts
under `reviewed_contract_runtime_binding`. These are pure helpers — the flags that ACT on them
(`AZALEA_RUNTIME_BINDING_SHADOW`, and a future enforce flag) live at the call sites and default off.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Optional

# §13 / §19 item 5 — the owner-chosen per-topic budget. v1 deterministic binding is sub-100ms; this is the
# ceiling that triggers automatic degradation to the next route tier, not an expected cost.
LATENCY_BUDGET_MS = 5000

WePolicy = Literal["runtime_binding_eligible", "withhold_fabricated", "verified"]


def within_budget(elapsed_ms: float, budget_ms: int = LATENCY_BUDGET_MS) -> bool:
    return elapsed_ms <= budget_ms


@dataclass(frozen=True)
class CertificationDecision:
    """§2.4 — the route-aware certification stamp for one topic. `we_policy='runtime_binding_eligible'` only
    when the topic misses registered routing, resolves a reviewed contract at `reviewed_match`, and wins its
    ownership claim. Eligibility authorizes PREPARATION, never shipping (§13.2): only a frozen passing
    evidence package authorizes shipping."""

    topic_id: str
    we_policy: WePolicy
    reason: str
    resolved_contract_id: Optional[str] = None
    resolution_registry_version: Optional[int] = None
    claim_id: Optional[str] = None


def certify_runtime_binding_eligibility(
    topic_id: str,
    *,
    registered_owner: Optional[object],
    resolution_status: str,
    resolution_validity: str,
    resolved_contract_id: Optional[str],
    resolution_registry_version: Optional[int],
    claim_status: str,
    claim_id: Optional[str],
) -> CertificationDecision:
    """Pure decision function (spec §2.4, §2.5). Wired into `_certify_path_scope` behind an enforce flag; on
    its own it changes nothing. A topic that fails any gate keeps the existing withhold behavior."""
    if registered_owner is not None:
        return CertificationDecision(topic_id, "withhold_fabricated", "registered adapter owns the topic")
    if resolution_status != "resolved" or resolution_validity != "reviewed_match":
        return CertificationDecision(topic_id, "withhold_fabricated",
                                     f"resolution {resolution_status}/{resolution_validity}")
    if claim_status != "active":
        return CertificationDecision(topic_id, "withhold_fabricated",
                                     f"lost or non-active ownership claim ({claim_status})")
    return CertificationDecision(
        topic_id, "runtime_binding_eligible",
        "reviewed-contract runtime binding eligible; awaiting prepared+verified evidence",
        resolved_contract_id=resolved_contract_id,
        resolution_registry_version=resolution_registry_version,
        claim_id=claim_id,
    )


def runtime_binding_enforced() -> bool:
    """The enforce flag (default off). Shipping runtime-binding cards to learners requires this AND a passing
    shadow slice; until then everything stays shadow/observe."""
    return os.getenv("AZALEA_RUNTIME_BINDING_ENFORCE", "off").strip().lower() in {"1", "true", "on", "enforce"}
