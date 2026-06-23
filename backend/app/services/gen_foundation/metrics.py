"""Shadow-vs-legacy measurement harness (spec §11, §12 step 5).

Compute the comparison measures the spec calls for — card count, output tokens
(approx), first-pass validity, audit edit rate, reconciliation status — so the shadow
path can be judged against the legacy multi-call solver on real fixtures BEFORE the
production route is replaced (§12 step 6). Pure: token count is an approximation, not a
billing figure.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from .pipeline import RunResult
from .validators import validate_artifact

_log = logging.getLogger(__name__)


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
    # Layer 1/3 execution signals (the oracle-gap measures) — defaults keep older callers working.
    blocked: bool = False                          # would this run have been withheld from the learner?
    executed: bool = False                         # did the executor actually run the code?
    execution_skip_reason: Optional[str] = None    # why not (execution_disabled / unsafe / no_entry / ...)
    final_answer_agreement: Optional[bool] = None  # executed answer vs the model's claim (None = uncheckable)
    property_violations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def measure_run(topic_id: str, result: RunResult) -> ShadowMeasure:
    artifact = result.artifact or {}
    cards = artifact.get("cards") or []
    execution = result.reconciliation_telemetry.get("execution") or {}
    return ShadowMeasure(
        topic_id=topic_id,
        card_count=len(cards),
        output_tokens=approx_tokens(artifact),
        first_pass_valid=not result.validation_errors,
        audit_edited=result.audit_telemetry.get("audit_status") == "pass_with_edits",
        model_calls=result.model_calls,
        reconciliation_status=result.reconciliation_telemetry.get("reconciliation_status", "n/a"),
        degraded=result.degraded,
        blocked=bool(result.degraded or not result.ok or not result.artifact),
        executed=bool(execution.get("executed")),
        execution_skip_reason=execution.get("skip_reason"),
        final_answer_agreement=execution.get("final_answer_agreement"),
        property_violations=list(execution.get("property_violations") or []),
    )


def record_run_telemetry(topic_id: str, result: RunResult, *, path: Optional[str] = None) -> None:
    """Durably append one shadow run's measures as a JSON line so the oracle-gap rates (executed %,
    skip reasons, answer-agreement, property violations, blocked %) are actually queryable. Sink is
    ``AZALEA_GEN_FOUNDATION_TELEMETRY_PATH``; with none set we still structured-log it. Best-effort —
    telemetry must never break generation."""
    line = json.dumps(measure_run(topic_id, result).as_dict(), ensure_ascii=False)
    sink = path or os.getenv("AZALEA_GEN_FOUNDATION_TELEMETRY_PATH")
    if not sink:
        _log.info("gen_foundation.telemetry %s", line)
        return
    try:
        with open(sink, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:  # noqa: BLE001
        _log.warning("gen_foundation: telemetry write to %s failed (%s)", sink, exc)


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
