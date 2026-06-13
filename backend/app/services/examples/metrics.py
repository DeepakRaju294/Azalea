"""Example-ontology telemetry (EXAMPLE_SYSTEM_SPEC §9.1).

Records every `apply_fixture_to_lesson` outcome so the one question that matters —
is the ontology path more accurate/cheaper than the free-form path? — is measured,
not eyeballed. Mirrors `visual_v2/metrics.py`: in-memory + process-local; the
snapshot dict is the wire format.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

# Closed enum (§9.1) so dashboards can bucket failures. Anything not in this set is
# normalised to its nearest bucket at record time.
FALLBACK_REASONS = (
    "no_application_match",
    "no_fixture_for_role",
    "fixture_validation_failed",
    "visual_pipeline_failed",
    "prose_validation_failed",
    "card_validation_failed",
    "feature_flag_disabled",
    "unsupported_example_type",
    "unsupported_visual_mode",
)


def normalize_reason(reason: str) -> str:
    """Map a raw reason (possibly suffixed, e.g. `visual_pipeline_failed:stage`) to
    the closed enum."""
    head = str(reason or "").split(":", 1)[0]
    return head if head in FALLBACK_REASONS else "visual_pipeline_failed"


@dataclass
class ExampleMetrics:
    total: int = 0
    applied: int = 0
    fallbacks: Counter = field(default_factory=Counter)
    by_application: Counter = field(default_factory=Counter)
    by_fixture: Counter = field(default_factory=Counter)
    by_lens: Counter = field(default_factory=Counter)
    time_to_apply_ms_sum: float = 0.0

    def record_applied(
        self,
        *,
        application: str,
        resolved_example_type: str,
        pattern: str,
        fixture_id: str,
        fixture_source: str,
        variant: Optional[str],
        raw_frame_count: int,
        milestone_count: int,
        elapsed_ms: float,
    ) -> None:
        self.total += 1
        self.applied += 1
        self.by_application[application] += 1
        self.by_fixture[fixture_id] += 1
        self.by_lens[resolved_example_type] += 1
        self.time_to_apply_ms_sum += float(elapsed_ms)
        self._last = {
            "application": application,
            "resolved_example_type": resolved_example_type,
            "pattern": pattern,
            "fixture_id": fixture_id,
            "fixture_source": fixture_source,
            "variant": variant,
            "raw_frame_count": raw_frame_count,
            "milestone_count": milestone_count,
            "time_to_apply_ms": round(float(elapsed_ms), 1),
        }

    def record_fallback(self, reason: str, application: Optional[str] = None) -> None:
        self.total += 1
        self.fallbacks[normalize_reason(reason)] += 1
        if application:
            self.by_application[f"{application} (fallback)"] += 1

    @property
    def apply_rate(self) -> float:
        return self.applied / self.total if self.total else 0.0

    def snapshot(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "applied": self.applied,
            "apply_rate": round(self.apply_rate, 4),
            "fallbacks": dict(self.fallbacks),
            "by_application": dict(self.by_application),
            "by_fixture": dict(self.by_fixture),
            "by_lens": dict(self.by_lens),
            "avg_time_to_apply_ms": round(self.time_to_apply_ms_sum / self.applied, 1) if self.applied else 0.0,
        }

    def reset(self) -> None:
        self.total = self.applied = 0
        self.time_to_apply_ms_sum = 0.0
        self.fallbacks.clear()
        self.by_application.clear()
        self.by_fixture.clear()
        self.by_lens.clear()


# Process-local accumulator the apply path records into.
GLOBAL = ExampleMetrics()
