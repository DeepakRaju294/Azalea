"""Shadow-vs-legacy measurement harness (spec §11, §12 step 5).

Compute the comparison measures the spec calls for — card count, output tokens
(approx), first-pass validity, audit edit rate, reconciliation status — so the shadow
path can be judged against the legacy multi-call solver on real fixtures BEFORE the
production route is replaced (§12 step 6). Pure: token count is an approximation, not a
billing figure.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from .pipeline import RunResult
from .validators import validate_artifact


def approx_tokens(obj: Any) -> int:
    """Rough token estimate (~4 chars/token) for relative comparison only."""
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return max(1, len(text) // 4)


@dataclass
class ShadowMeasure:
    topic_id: str
    card_count: int
    output_tokens: int
    first_pass_valid: bool
    audit_edited: bool
    model_calls: int
    reconciliation_status: str
    degraded: bool

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def measure_run(topic_id: str, result: RunResult) -> ShadowMeasure:
    artifact = result.artifact or {}
    cards = artifact.get("cards") or []
    return ShadowMeasure(
        topic_id=topic_id,
        card_count=len(cards),
        output_tokens=approx_tokens(artifact),
        first_pass_valid=not result.validation_errors,
        audit_edited=result.audit_telemetry.get("audit_status") == "pass_with_edits",
        model_calls=result.model_calls,
        reconciliation_status=result.reconciliation_telemetry.get("reconciliation_status", "n/a"),
        degraded=result.degraded,
    )


@dataclass
class Comparison:
    topic_id: str
    shadow: ShadowMeasure
    legacy_card_count: int
    legacy_output_tokens: int
    legacy_model_calls: int

    @property
    def calls_delta(self) -> int:
        return self.shadow.model_calls - self.legacy_model_calls

    @property
    def tokens_delta(self) -> int:
        return self.shadow.output_tokens - self.legacy_output_tokens

    def as_dict(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "shadow": self.shadow.as_dict(),
            "legacy": {
                "card_count": self.legacy_card_count,
                "output_tokens": self.legacy_output_tokens,
                "model_calls": self.legacy_model_calls,
            },
            "calls_delta": self.calls_delta,
            "tokens_delta": self.tokens_delta,
        }


def compare_to_legacy(
    topic_id: str,
    shadow_result: RunResult,
    legacy_artifact: dict[str, Any],
    legacy_model_calls: int,
) -> Comparison:
    return Comparison(
        topic_id=topic_id,
        shadow=measure_run(topic_id, shadow_result),
        legacy_card_count=len(legacy_artifact.get("cards") or []),
        legacy_output_tokens=approx_tokens(legacy_artifact),
        legacy_model_calls=legacy_model_calls,
    )


def aggregate(comparisons: list[Comparison]) -> dict[str, Any]:
    """Roll up a fixture run into the headline numbers (§12 step 5)."""
    if not comparisons:
        return {"n": 0}
    n = len(comparisons)
    valid = sum(1 for c in comparisons if c.shadow.first_pass_valid)
    edited = sum(1 for c in comparisons if c.shadow.audit_edited)
    return {
        "n": n,
        "first_pass_validity_rate": round(valid / n, 3),
        "audit_edit_rate": round(edited / n, 3),
        "avg_shadow_calls": round(sum(c.shadow.model_calls for c in comparisons) / n, 2),
        "avg_legacy_calls": round(sum(c.legacy_model_calls for c in comparisons) / n, 2),
        "avg_calls_delta": round(sum(c.calls_delta for c in comparisons) / n, 2),
        "avg_tokens_delta": round(sum(c.tokens_delta for c in comparisons) / n, 1),
    }
