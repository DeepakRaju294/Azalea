"""Telemetry aggregation + widening gates (VISUAL_SYSTEM_SPEC §7.2, §8.1).

Records the outcome of each V2 build so rollout decisions are measured, not
eyeballed: coverage, rejection rate, repair rate, and the failure breakdown by
stage. `widening_gates` turns those into the §8.1 go/no-go for expanding V2 to the
next mode. In-memory + process-local; a real deployment would also ship snapshots
to a metrics backend (the snapshot dict is the wire format).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

# §8.1 widening thresholds (tune the numbers, keep the gates).
COVERAGE_FLOOR = 0.95
REJECTION_CEIL = 0.05
REPAIR_CEIL = 0.20
MIN_SAMPLES = 20


@dataclass
class VisualMetrics:
    total: int = 0
    validated: int = 0
    repaired: int = 0
    failures_by_stage: Counter = field(default_factory=Counter)
    by_mode: Counter = field(default_factory=Counter)

    def record(self, result: dict[str, Any]) -> None:
        """Record one build result (from build_v2_visual / run_for_registered)."""
        self.total += 1
        example = result.get("example") or {}
        if example.get("mode"):
            self.by_mode[example["mode"]] += 1
        if result.get("status") == "validated":
            self.validated += 1
            if result.get("prose_repaired"):
                self.repaired += 1
        else:
            self.failures_by_stage[result.get("stage") or "unknown"] += 1

    @property
    def coverage(self) -> float:
        return self.validated / self.total if self.total else 0.0

    @property
    def rejection_rate(self) -> float:
        return (self.total - self.validated) / self.total if self.total else 0.0

    @property
    def repair_rate(self) -> float:
        return self.repaired / self.validated if self.validated else 0.0

    def snapshot(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "validated": self.validated,
            "repaired": self.repaired,
            "coverage": round(self.coverage, 4),
            "rejection_rate": round(self.rejection_rate, 4),
            "repair_rate": round(self.repair_rate, 4),
            "failures_by_stage": dict(self.failures_by_stage),
            "by_mode": dict(self.by_mode),
        }

    def reset(self) -> None:
        self.total = self.validated = self.repaired = 0
        self.failures_by_stage.clear()
        self.by_mode.clear()


def widening_gates(
    metrics: VisualMetrics,
    *,
    known_bad_failures: int = 0,
    min_samples: int = MIN_SAMPLES,
) -> dict[str, Any]:
    """§8.1 go/no-go for widening V2 to the next mode. `pass` is True only when
    every gate holds. `reasons` lists each failing gate (empty when passing)."""
    reasons: list[str] = []
    if metrics.total < min_samples:
        reasons.append(f"insufficient samples ({metrics.total} < {min_samples})")
    if metrics.coverage < COVERAGE_FLOOR:
        reasons.append(f"coverage {metrics.coverage:.0%} < {COVERAGE_FLOOR:.0%}")
    if metrics.rejection_rate > REJECTION_CEIL:
        reasons.append(f"rejection {metrics.rejection_rate:.0%} > {REJECTION_CEIL:.0%}")
    if metrics.repair_rate > REPAIR_CEIL:
        reasons.append(f"repair {metrics.repair_rate:.0%} > {REPAIR_CEIL:.0%}")
    if known_bad_failures > 0:
        reasons.append(f"{known_bad_failures} known-bad regression failure(s)")
    return {"pass": not reasons, "reasons": reasons, **metrics.snapshot()}


# Process-local accumulator the build path records into.
GLOBAL = VisualMetrics()
