"""V2 vs legacy telemetry helper.

Writes a single CSV row per lesson generation so we can compare pipelines
without a metrics infrastructure. Columns:

  timestamp, pipeline, topic_id, base_type_distribution, duration_seconds,
  outcome, validator_errors, validator_warnings, lesson_card_count,
  visual_model_count, render_step_count, error_message

`pipeline` is "v2" or "legacy". `outcome` is "success" or "failure".

Log path: logs/v2_telemetry.csv. The file is created on first write with
a header row. Append-only; never rotated by this module.

Read with `tail -f logs/v2_telemetry.csv` or pandas. For dashboards, copy
the CSV to BigQuery / Snowflake / wherever your metrics stack lives.
"""

from __future__ import annotations

import csv
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


# Alert thresholds for the Phase 8 decom criterion ("v2 error rate <=
# legacy baseline"). When the rolling window of recent rows shows v2
# failing more than the alert ratio, `check_alert_thresholds` returns
# a structured warning. Wired into the /telemetry/summary endpoint
# so an operator dashboard can surface the alert.
ALERT_MIN_SAMPLES = int(os.environ.get("V2_TELEMETRY_ALERT_MIN_SAMPLES", "20"))
ALERT_MAX_V2_ERROR_RATE = float(
    os.environ.get("V2_TELEMETRY_ALERT_MAX_V2_ERROR_RATE", "0.10")
)
ALERT_MAX_V2_OVER_LEGACY_DELTA = float(
    os.environ.get("V2_TELEMETRY_ALERT_MAX_V2_OVER_LEGACY", "0.05")
)

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_PATH = LOG_DIR / "v2_telemetry.csv"
# Rotate when the active log exceeds this size. Default 5 MB; tunable
# via env var V2_TELEMETRY_MAX_BYTES.
MAX_LOG_BYTES = int(os.environ.get("V2_TELEMETRY_MAX_BYTES", str(5 * 1024 * 1024)))
# Keep the most recent N rotated archives; older ones are deleted.
MAX_ARCHIVES = int(os.environ.get("V2_TELEMETRY_MAX_ARCHIVES", "10"))

_FIELDS = (
    "timestamp",
    "pipeline",
    "topic_id",
    "base_type_distribution",
    "duration_seconds",
    "outcome",
    "validator_errors",
    "validator_warnings",
    "lesson_card_count",
    "visual_model_count",
    "render_step_count",
    "error_message",
)

_logger = logging.getLogger(__name__)


def _ensure_header() -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not LOG_PATH.exists():
            with LOG_PATH.open("w", newline="", encoding="utf-8") as fh:
                csv.DictWriter(fh, fieldnames=_FIELDS).writeheader()
    except OSError as exc:
        _logger.warning("v2 telemetry: header init failed: %s", exc)


def _rotate_if_needed() -> None:
    """Size-based rotation: when LOG_PATH exceeds MAX_LOG_BYTES, rename it
    to v2_telemetry.<timestamp>.csv and start a fresh file. Delete the
    oldest archives beyond MAX_ARCHIVES."""
    try:
        if not LOG_PATH.exists():
            return
        if LOG_PATH.stat().st_size < MAX_LOG_BYTES:
            return
        # Rotate
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = LOG_DIR / f"v2_telemetry.{stamp}.csv"
        LOG_PATH.rename(archive)
        _ensure_header()
        # Prune oldest archives
        archives = sorted(
            LOG_DIR.glob("v2_telemetry.*.csv"),
            key=lambda p: p.stat().st_mtime,
        )
        excess = max(0, len(archives) - MAX_ARCHIVES)
        for old in archives[:excess]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError as exc:
        _logger.warning("v2 telemetry: rotation failed: %s", exc)


def _base_type_distribution(lesson_or_raw: dict[str, Any]) -> str:
    """Comma-separated tally of base_types in visual_models. Empty string
    when the input is the legacy `lesson_json` shape (no visual_models)."""
    models = lesson_or_raw.get("visual_models") or []
    if not isinstance(models, list):
        return ""
    counts: dict[str, int] = {}
    for model in models:
        if isinstance(model, dict):
            bt = str(model.get("base_type") or "")
            if bt:
                counts[bt] = counts.get(bt, 0) + 1
    return ";".join(f"{k}:{v}" for k, v in sorted(counts.items()))


def emit_event(
    *,
    pipeline: str,
    topic_id: str,
    duration_seconds: float,
    outcome: str,
    lesson: dict[str, Any] | None = None,
    validator_errors: int = 0,
    validator_warnings: int = 0,
    error_message: str = "",
) -> None:
    """Write one row to logs/v2_telemetry.csv.

    Safe to call from any thread; CSV write uses append mode + a single
    writerow call so partial writes don't corrupt the file.

    Failures here never propagate to the caller — telemetry must not
    break lesson generation.
    """
    try:
        _ensure_header()
        _rotate_if_needed()
        lesson = lesson or {}
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pipeline": pipeline,
            "topic_id": topic_id,
            "base_type_distribution": _base_type_distribution(lesson),
            "duration_seconds": f"{duration_seconds:.3f}",
            "outcome": outcome,
            "validator_errors": validator_errors,
            "validator_warnings": validator_warnings,
            "lesson_card_count": len(lesson.get("lesson_cards") or []),
            "visual_model_count": len(lesson.get("visual_models") or []),
            "render_step_count": len(lesson.get("render_steps") or []),
            "error_message": error_message[:300],
        }
        with LOG_PATH.open("a", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=_FIELDS).writerow(row)
    except Exception as exc:  # noqa: BLE001
        _logger.warning("v2 telemetry: emit failed: %s", exc)


def read_summary(limit_rows: int = 1000) -> dict[str, Any]:
    """Read the telemetry CSV and aggregate the last `limit_rows` rows.

    Returns counts and averages broken down by pipeline. Used by the
    admin `/lessons-v2/telemetry/summary` endpoint and the CI dashboard.
    """
    summary: dict[str, Any] = {
        "rows_read": 0,
        "by_pipeline": {},
        "log_path": str(LOG_PATH),
    }
    if not LOG_PATH.exists():
        summary["error"] = "telemetry file does not exist yet"
        return summary

    try:
        with LOG_PATH.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)[-limit_rows:]
    except OSError as exc:
        summary["error"] = f"read failed: {exc}"
        return summary

    summary["rows_read"] = len(rows)
    per_pipeline: dict[str, dict[str, Any]] = {}
    for row in rows:
        pipeline = row.get("pipeline") or "unknown"
        bucket = per_pipeline.setdefault(pipeline, {
            "count": 0,
            "success": 0,
            "failure": 0,
            "total_duration_seconds": 0.0,
            "total_validator_errors": 0,
            "total_validator_warnings": 0,
            "base_type_counts": {},
        })
        bucket["count"] += 1
        if (row.get("outcome") or "") == "success":
            bucket["success"] += 1
        else:
            bucket["failure"] += 1
        try:
            bucket["total_duration_seconds"] += float(row.get("duration_seconds") or 0.0)
        except ValueError:
            pass
        try:
            bucket["total_validator_errors"] += int(row.get("validator_errors") or 0)
        except ValueError:
            pass
        try:
            bucket["total_validator_warnings"] += int(row.get("validator_warnings") or 0)
        except ValueError:
            pass
        dist = row.get("base_type_distribution") or ""
        for piece in dist.split(";"):
            if ":" in piece:
                bt, _, n = piece.partition(":")
                try:
                    bucket["base_type_counts"][bt] = (
                        bucket["base_type_counts"].get(bt, 0) + int(n)
                    )
                except ValueError:
                    pass

    # Compute averages
    for pipeline, bucket in per_pipeline.items():
        count = max(1, bucket["count"])
        bucket["avg_duration_seconds"] = bucket["total_duration_seconds"] / count
        bucket["error_rate"] = bucket["failure"] / count
        bucket["validator_errors_per_lesson"] = bucket["total_validator_errors"] / count
        bucket["validator_warnings_per_lesson"] = bucket["total_validator_warnings"] / count
    summary["by_pipeline"] = per_pipeline
    summary["alerts"] = check_alert_thresholds(per_pipeline)
    return summary


def check_alert_thresholds(per_pipeline: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute alert objects from the per-pipeline counters.

    Returns a list. Each alert: {code, severity, message, details}.
    Empty list when nothing is over-threshold. Alerts:

      v2_error_rate_high — v2 failure rate > ALERT_MAX_V2_ERROR_RATE
      v2_worse_than_legacy — v2 error rate exceeds legacy by more than
                              ALERT_MAX_V2_OVER_LEGACY_DELTA
    """
    alerts: list[dict[str, Any]] = []
    v2 = per_pipeline.get("v2") or {}
    legacy = per_pipeline.get("legacy") or {}
    v2_count = int(v2.get("count") or 0)
    legacy_count = int(legacy.get("count") or 0)
    v2_rate = float(v2.get("error_rate") or 0.0)
    legacy_rate = float(legacy.get("error_rate") or 0.0)

    if v2_count >= ALERT_MIN_SAMPLES and v2_rate > ALERT_MAX_V2_ERROR_RATE:
        alerts.append({
            "code": "v2_error_rate_high",
            "severity": "warning",
            "message": (
                f"v2 error rate is {v2_rate:.1%}, above threshold "
                f"{ALERT_MAX_V2_ERROR_RATE:.1%} over {v2_count} samples."
            ),
            "details": {
                "v2_error_rate": v2_rate,
                "threshold": ALERT_MAX_V2_ERROR_RATE,
                "v2_samples": v2_count,
            },
        })

    if (
        v2_count >= ALERT_MIN_SAMPLES
        and legacy_count >= ALERT_MIN_SAMPLES
        and (v2_rate - legacy_rate) > ALERT_MAX_V2_OVER_LEGACY_DELTA
    ):
        alerts.append({
            "code": "v2_worse_than_legacy",
            "severity": "warning",
            "message": (
                f"v2 error rate ({v2_rate:.1%}) exceeds legacy "
                f"({legacy_rate:.1%}) by {(v2_rate - legacy_rate):.1%}, "
                f"above threshold {ALERT_MAX_V2_OVER_LEGACY_DELTA:.1%}. "
                "Phase 8 decom criterion #5 is failing."
            ),
            "details": {
                "v2_error_rate": v2_rate,
                "legacy_error_rate": legacy_rate,
                "delta": v2_rate - legacy_rate,
                "threshold": ALERT_MAX_V2_OVER_LEGACY_DELTA,
            },
        })

    return alerts


@contextmanager
def record_generation(
    *,
    pipeline: str,
    topic_id: str,
) -> Iterator[dict[str, Any]]:
    """Context manager that records a generation event with auto-timing.

    Usage:
        with record_generation(pipeline="v2", topic_id=tid) as ctx:
            lesson = generate(...)
            ctx["lesson"] = lesson  # optional — for shape metrics
            ctx["validator_errors"] = N
            ctx["validator_warnings"] = M
    """
    start = time.monotonic()
    ctx: dict[str, Any] = {
        "lesson": None,
        "validator_errors": 0,
        "validator_warnings": 0,
    }
    error_message = ""
    outcome = "success"
    try:
        yield ctx
    except Exception as exc:  # noqa: BLE001
        outcome = "failure"
        error_message = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        duration = time.monotonic() - start
        emit_event(
            pipeline=pipeline,
            topic_id=topic_id,
            duration_seconds=duration,
            outcome=outcome,
            lesson=ctx.get("lesson") or {},
            validator_errors=int(ctx.get("validator_errors") or 0),
            validator_warnings=int(ctx.get("validator_warnings") or 0),
            error_message=error_message,
        )
