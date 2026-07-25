"""Best-effort production identity and substrate-shadow telemetry for FormulaSpec executions."""

from __future__ import annotations

import json
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Any

from app.services.examples.runtime_binding.compiler import compile_formula_spec
from app.services.examples.runtime_binding.executor import execute_descriptor
from app.services.examples.trace_adapters.families.formula_engine import _num


_LOG = logging.getLogger(__name__)
_ENV_MODE = "AZALEA_T6_SUBSTRATE_SHADOW"
_ENV_PATH = "AZALEA_T6_SUBSTRATE_SHADOW_PATH"
_ENV_SAMPLE_RATE = "AZALEA_T6_SUBSTRATE_SHADOW_SAMPLE_RATE"
_ENV_SLUGS = "AZALEA_T6_SUBSTRATE_SHADOW_SLUGS"
_ENV_SOURCE = "AZALEA_T6_SUBSTRATE_SHADOW_SOURCE"
_VALID_MODES = {"off", "observe"}


def shadow_mode() -> str:
    mode = os.getenv(_ENV_MODE, "off").strip().lower()
    return mode if mode in _VALID_MODES else "off"


def _sample_rate() -> float:
    try:
        return min(1.0, max(0.0, float(os.getenv(_ENV_SAMPLE_RATE, "1"))))
    except ValueError:
        return 0.0


def _selected_for_comparison(slug: str, candidate_id: str) -> bool:
    allowlist = {
        item.strip() for item in os.getenv(_ENV_SLUGS, "").split(",") if item.strip()
    }
    if allowlist and slug not in allowlist:
        return False
    rate = _sample_rate()
    if rate <= 0:
        return False
    if rate >= 1:
        return True
    digest = hashlib.sha256(f"{slug}|{candidate_id}".encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") / float(2**64)
    return bucket < rate


def shadow_telemetry_path() -> Path:
    configured = os.getenv(_ENV_PATH, "").strip()
    return Path(configured) if configured else (
        Path(__file__).resolve().parents[4] / "logs" / "t6_substrate_shadow.jsonl"
    )


def _exact_inputs(candidate: dict[str, Any]) -> dict[str, int | str]:
    result: dict[str, int | str] = {}
    for name, value in candidate.items():
        if name.startswith("_"):
            continue
        if isinstance(value, bool):
            result[name] = int(value)
        elif isinstance(value, int):
            result[name] = value
        elif isinstance(value, float):
            result[name] = str(value)
        else:
            raise ValueError(f"unsupported candidate input: {name}")
    return result


def _write(event: dict[str, Any]) -> None:
    line = json.dumps(event, sort_keys=True, ensure_ascii=False)
    path = shadow_telemetry_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError as exc:
        _LOG.warning("t6 substrate shadow telemetry write failed: %s", exc)


def observe_formula_execution(
    adapter: Any,
    candidate: dict[str, Any],
    trace: Any,
    *,
    seed: int,
    attempt: int,
) -> None:
    """Record every FormulaSpec execution and compare eligible rows. Never affects the returned trace."""
    if shadow_mode() != "observe":
        return
    spec = getattr(adapter, "_formula_spec", None)
    if spec is None:
        return
    started = time.perf_counter()
    compiled = compile_formula_spec(spec)
    event: dict[str, Any] = {
        "schema_version": 1,
        "ts": time.time(),
        "traffic_source": os.getenv(_ENV_SOURCE, "live_generation").strip() or "live_generation",
        "formula_slug": spec.slug,
        "family": spec.family,
        "candidate_id": str(candidate.get("_id") or ""),
        "seed": seed,
        "attempt": attempt,
        "compile_status": compiled.status,
        "eligible": compiled.status == "compiled",
        "blockers": list(compiled.blockers),
        "legacy_completed": True,
        "comparison_sampled": False,
        "substrate_executed": False,
        "execution_match": None,
        "teaching_match": None,
        "mismatch_kind": None,
        "quarantine_required": False,
    }
    selected = _selected_for_comparison(spec.slug, event["candidate_id"])
    event["comparison_sampled"] = selected
    if compiled.descriptor is not None and selected:
        output = spec.outputs[0]
        try:
            result = execute_descriptor(compiled.descriptor, _exact_inputs(candidate))
            displayed = _num(float(result.value))
            legacy = trace.final_answer.get(output.name)
            event.update(
                substrate_executed=True,
                substrate_displayed_result=displayed,
                legacy_displayed_result=legacy,
                output_unit=result.output_unit,
                execution_match=displayed == legacy,
                teaching_match=displayed == legacy,
            )
            if displayed != legacy:
                event.update(
                    mismatch_kind="displayed_result",
                    quarantine_required=True,
                )
        except Exception as exc:  # noqa: BLE001 - telemetry must retain classified failures
            event.update(
                mismatch_kind=f"substrate_exception:{type(exc).__name__}",
                substrate_exception=str(exc)[:500],
            )
    event["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    _write(event)


def summarize_shadow_events(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    events = []
    if source.exists():
        for line in source.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except (ValueError, TypeError):
                continue
    total = len(events)
    eligible = [event for event in events if event.get("eligible")]
    sampled = [event for event in events if event.get("comparison_sampled")]
    latencies = sorted(
        float(event["latency_ms"]) for event in sampled if isinstance(event.get("latency_ms"), (int, float))
    )
    p95_index = max(0, min(len(latencies) - 1, int(0.95 * len(latencies)))) if latencies else 0
    sources: dict[str, dict[str, Any]] = {}
    for source in sorted({str(event.get("traffic_source") or "unknown") for event in events}):
        selected = [event for event in events if str(event.get("traffic_source") or "unknown") == source]
        source_eligible = [event for event in selected if event.get("eligible")]
        sources[source] = {
            "total": len(selected),
            "eligible": len(source_eligible),
            "eligible_percent": round(100 * len(source_eligible) / len(selected), 2) if selected else None,
            "distinct_slugs": len({event.get("formula_slug") for event in selected}),
            "distinct_eligible_slugs": len({event.get("formula_slug") for event in source_eligible}),
        }
    return {
        "total_formula_executions": total,
        "eligible_formula_executions": len(eligible),
        "eligible_execution_percent": round(100 * len(eligible) / total, 2) if total else None,
        "substrate_executions": sum(bool(event.get("substrate_executed")) for event in events),
        "comparison_samples": len(sampled),
        "execution_mismatches": sum(event.get("execution_match") is False for event in events),
        "substrate_exceptions": sum(
            str(event.get("mismatch_kind") or "").startswith("substrate_exception:")
            for event in events
        ),
        "quarantine_required": sum(bool(event.get("quarantine_required")) for event in events),
        "distinct_formula_slugs": len({event.get("formula_slug") for event in events}),
        "distinct_eligible_formula_slugs": len(
            {event.get("formula_slug") for event in eligible}
        ),
        "comparison_latency_p95_ms": latencies[p95_index] if latencies else None,
        "by_source": sources,
    }
