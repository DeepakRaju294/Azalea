"""Invariant & projector telemetry (PROJECTOR_SYSTEM_SPEC §6.2, §14).

The guardrail's whole point is observability: "renders empty silently" becomes
"caught and counted." This records invariant failures, empty-legacy fallbacks, and
(later) per-tier + inference outcomes, so projector work is data-driven — telemetry
says where the system bleeds, and that prioritizes the next fix.

In-memory + process-local, mirroring `metrics.py`; the snapshot dict is the wire
format surfaced via /v2-metrics.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

# Verbatim invariant names (§18 rule 9) — used as telemetry keys, validator error
# prefixes, and test names alike.
INVARIANTS = ("INV-RENDER", "INV-COMPLETE", "INV-DUAL-SLOT", "INV-PROSE-SYNC")

# Legacy fallback reasons distinct from a *failed* projection (§6.2, §10.1).
FALLBACK_REASONS = ("empty_node_state", "unsupported_projector_shape")


@dataclass
class InvariantMetrics:
    invariant_failures: Counter = field(default_factory=Counter)   # code -> count
    fallbacks: Counter = field(default_factory=Counter)            # reason -> count
    by_tier: Counter = field(default_factory=Counter)             # "T1".."T5" -> count
    empty_by_application: Counter = field(default_factory=Counter)
    inference: Counter = field(default_factory=Counter)           # accepted:<band> | rejected
    confidence_bands: Counter = field(default_factory=Counter)    # high|medium|low
    worked_example_regens: Counter = field(default_factory=Counter)  # regen-count -> times hit limit

    def record_invariant_failure(self, code: str, *, application: Optional[str] = None) -> None:
        self.invariant_failures[code] += 1

    def record_empty_node_state(self, *, application: Optional[str] = None) -> None:
        self.fallbacks["empty_node_state"] += 1
        if application:
            self.empty_by_application[application] += 1

    def record_unsupported_shape(self, shape: str) -> None:
        self.fallbacks["unsupported_projector_shape"] += 1

    def record_tier(self, tier: str) -> None:
        self.by_tier[tier] += 1

    def record_inference(self, *, accepted: bool, confidence_band: Optional[str] = None) -> None:
        if accepted:
            self.inference["accepted"] += 1
            if confidence_band:
                self.confidence_bands[confidence_band] += 1
        else:
            self.inference["rejected"] += 1

    def record_incomplete_worked_example(self, *, regenerations: int) -> None:
        """A worked example that's still incomplete after the regeneration cap shipped."""
        self.fallbacks["incomplete_worked_example"] += 1
        self.worked_example_regens[str(regenerations)] += 1

    def record_code_drop(self, reason: str) -> None:
        """A coding worked example fell to legacy instead of the traced one — WHY
        (no_code | no_input | trace_failed | no_milestones). Makes the gap measurable."""
        self.fallbacks[f"code_execution_drop:{reason}"] += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "invariant_failures": dict(self.invariant_failures),
            "fallbacks": dict(self.fallbacks),
            "by_tier": dict(self.by_tier),
            "empty_by_application": dict(self.empty_by_application),
            "inference": dict(self.inference),
            "confidence_bands": dict(self.confidence_bands),
            "worked_example_regens": dict(self.worked_example_regens),
        }

    def reset(self) -> None:
        for counter in (self.invariant_failures, self.fallbacks, self.by_tier,
                        self.empty_by_application, self.inference, self.confidence_bands,
                        self.worked_example_regens):
            counter.clear()


# Process-local accumulator.
GLOBAL = InvariantMetrics()
