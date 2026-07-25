"""Measured Wave-0 capability freeze for the live FormulaSpec catalog."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from app.services.examples.runtime_binding.inventory import InventoryReport, inventory_live_catalog
from app.services.examples.runtime_binding.policy import NUMERIC_UNIT_POLICY, numeric_unit_policy_digest
from app.services.examples.runtime_binding.shadow import shadow_telemetry_path, summarize_shadow_events


@dataclass(frozen=True)
class CapabilityReport:
    schema_version: int
    policy: dict[str, Any]
    summary: dict[str, Any]
    eligible_rows: tuple[str, ...]
    blocked_rows: tuple[dict[str, Any], ...]
    invalid_rows: tuple[dict[str, Any], ...]

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(asdict(self), indent=indent, sort_keys=True, ensure_ascii=False)


def build_capability_report(inventory: InventoryReport | None = None) -> CapabilityReport:
    report = inventory or inventory_live_catalog()
    registered = [row for row in report.rows if row.registered]
    eligible = [row for row in registered if row.compile_result.status == "compiled"]
    shape_counts = Counter(
        "+".join(operator for output in row.outputs for operator in output.operators) or "Literal/Name"
        for row in eligible
    )
    families: dict[str, dict[str, int]] = defaultdict(lambda: {"registered": 0, "eligible": 0})
    for row in registered:
        families[row.family]["registered"] += 1
        if row.compile_result.status == "compiled":
            families[row.family]["eligible"] += 1

    def evidence(row) -> dict[str, Any]:
        return {
            "slug": row.slug,
            "family": row.family,
            "required_wave": row.compile_result.required_wave,
            "unsupported_constructs": row.compile_result.unsupported_constructs,
            "execution_shape_blockers": row.compile_result.execution_shape_blockers,
            "required_calls": tuple(sorted({call for output in row.outputs for call in output.calls})),
            "ast_nodes": tuple(sorted({node for output in row.outputs for node in output.ast_nodes})),
        }

    traffic_summary = summarize_shadow_events(shadow_telemetry_path())
    traffic_coverage = (
        {
            "status": "available",
            "source": str(shadow_telemetry_path()),
            **traffic_summary,
        }
        if traffic_summary["total_formula_executions"]
        else {
            "status": "unavailable",
            "reason": "No per-row production FormulaSpec execution-volume source is available.",
        }
    )
    summary = {
        "registered_rows": len(registered),
        "eligible_registered_rows": len(eligible),
        "eligible_registered_percent": round(100 * len(eligible) / len(registered), 2),
        "family_representation": {key: families[key] for key in sorted(families)},
        "eligible_execution_shapes": dict(sorted(shape_counts.items(), key=lambda item: (-item[1], item[0]))),
        "traffic_coverage": traffic_coverage,
        "migration_complexity": {
            "eligible": "mechanical_compile",
            "blocked": "later_wave_or_callback_design",
            "invalid": "authored_row_correction_required",
        },
        "expected_reviewed_runtime_reuse": "exact scalar relationships using the same restricted grammar",
    }
    policy = {
        **NUMERIC_UNIT_POLICY,
        "numeric_unit_policy_digest": numeric_unit_policy_digest(),
        "nodes": ["Literal", "Variable", "Negate", "Add", "Subtract", "Multiply", "Divide", "IntegerPower"],
        "value_types": ["integer", "terminating_decimal", "rational"],
        "unit_type": "multiplicative_dimension_vector",
        "output_policy": "single_output_only",
        "constant_policy": "named_exact_value_with_reviewed_unit",
        "domain_policy": "explicit_nonzero_constraints_from_division",
        "callback_policy": "blocked",
        "trace_policy": "legacy_two-stage_projection_must_match",
    }
    return CapabilityReport(
        schema_version=1,
        policy=policy,
        summary=summary,
        eligible_rows=tuple(row.slug for row in eligible),
        blocked_rows=tuple(evidence(row) for row in registered if row.compile_result.status == "blocked"),
        invalid_rows=tuple(evidence(row) for row in registered if row.compile_result.status == "invalid"),
    )
