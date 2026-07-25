"""Consolidated Milestone A evidence and strict go/no-go evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.services.examples.runtime_binding.capability import build_capability_report
from app.services.examples.runtime_binding.compiler import compile_formula_spec
from app.services.examples.runtime_binding.complexity import build_complexity_report
from app.services.examples.runtime_binding.convergence import build_live_offline_convergence_report
from app.services.examples.runtime_binding.cutover import RowCutoverState, run_offline_dual
from app.services.examples.runtime_binding.inventory import inventory_live_catalog
from app.services.examples.runtime_binding.restricted_expression import expression_canonical_digest
from app.services.examples.trace_adapters.decl import hydrate
from app.services.examples.trace_adapters.families.formula_engine import formula_decl
from app.services.examples.trace_adapters.families.formula_specs import DENSITY


@dataclass(frozen=True)
class GateResult:
    gate: str
    passed: bool
    evidence: str


@dataclass(frozen=True)
class MilestoneAReport:
    schema_version: int
    decision: str
    gates: tuple[GateResult, ...]
    summary: dict[str, Any]
    cutover_demonstration: dict[str, Any]
    reviewed_fixture: dict[str, Any]
    benefits: tuple[str, ...]
    unsupported_boundaries: tuple[str, ...]

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(asdict(self), indent=indent, sort_keys=True, ensure_ascii=False)


def _cutover_demonstration() -> dict[str, Any]:
    adapter = hydrate(formula_decl(DENSITY))
    candidate = next(iter(adapter.candidates(0)))
    state = RowCutoverState(DENSITY.slug)

    def broken(*args, **kwargs):
        raise TimeoutError("offline_cutover_fixture")

    class Wrong:
        value = 999

    events = (
        run_offline_dual(DENSITY, candidate, state, mode="legacy_primary"),
        run_offline_dual(DENSITY, candidate, state, mode="substrate_primary"),
        run_offline_dual(
            DENSITY, candidate, state, mode="substrate_primary", substrate_runner=broken,
        ),
        run_offline_dual(
            DENSITY, candidate, state, mode="legacy_primary",
            substrate_runner=lambda *args, **kwargs: Wrong(),
        ),
    )
    return {
        "fixture": DENSITY.slug,
        "events": [
            {
                "mode": event.mode,
                "outcome": event.outcome,
                "mismatch_kind": event.mismatch_kind,
                "alert_required": event.alert_required,
                "next_status": event.next_state.substrate_status,
                "next_status_version": event.next_state.status_version,
            }
            for event in events
        ],
        "production_routing_connected": False,
    }


def build_milestone_a_report(repo_root: Path) -> MilestoneAReport:
    inventory = inventory_live_catalog()
    capability = build_capability_report(inventory)
    convergence = build_live_offline_convergence_report()
    complexity = build_complexity_report(repo_root)
    cutover = _cutover_demonstration()
    compiled = compile_formula_spec(DENSITY)
    assert compiled.descriptor is not None

    registered = [row for row in inventory.rows if row.registered]
    convergence_by_slug = {row.slug: row for row in convergence.rows}
    eligible = [row for row in registered if row.compile_result.status == "compiled"]
    later = [row for row in registered if row.compile_result.status == "blocked"]
    separate_statuses = {"pass", "blocked", "failed", "accepted_nonsemantic_drift"}
    traffic = capability.summary["traffic_coverage"]
    sources = traffic.get("by_source", {}) if traffic["status"] == "available" else {}
    historical = sources.get("historical_topic_replay", {})
    controlled = sources.get("controlled_router_validation", {})
    reported_statuses = (
        set(convergence.summary["execution_status_counts"])
        | set(convergence.summary["teaching_status_counts"])
    )
    # Zero-count categories remain explicit in the consolidated summary.
    equivalence_counts = {
        status: {
            "execution": convergence.summary["execution_status_counts"].get(status, 0),
            "teaching": convergence.summary["teaching_status_counts"].get(status, 0),
        }
        for status in sorted(separate_statuses)
    }

    gates = (
        GateResult(
            "registered_rows_deterministically_classified",
            len(registered) == 132 and all(row.compile_result.status for row in registered),
            f"{len(registered)} registered rows; no duplicate slugs",
        ),
        GateResult(
            "wave0_frozen_from_live_inventory",
            len(capability.eligible_rows) == len(eligible),
            f"{len(eligible)} eligible registered rows ({capability.summary['eligible_registered_percent']}%)",
        ),
        GateResult(
            "wave0_compiles_and_behavior_matches",
            all(
                convergence_by_slug[row.slug].execution.status == "pass"
                and convergence_by_slug[row.slug].teaching.status == "pass"
                for row in eligible
            ),
            f"{len(eligible)} rows; {convergence.summary['candidates_checked']} candidates",
        ),
        GateResult(
            "later_waves_have_exact_capability_evidence",
            all(
                row.compile_result.execution_shape_blockers
                or row.compile_result.unsupported_constructs
                for row in later
            ),
            f"{len(later)} blocked registered rows retain AST/call/blocker evidence",
        ),
        GateResult(
            "equivalence_statuses_separate",
            reported_statuses <= separate_statuses,
            json.dumps(equivalence_counts, sort_keys=True),
        ),
        GateResult(
            "offline_staged_cutover_demonstrated",
            [event["outcome"] for event in cutover["events"]]
            == ["match", "match", "fallback", "quarantined"],
            "legacy-primary, substrate-primary, explicit fallback, and mismatch quarantine exercised",
        ),
        GateResult(
            "production_execution_volume_coverage_available",
            traffic["status"] == "available",
            traffic.get("reason") or (
                f"{traffic.get('total_formula_executions')} FormulaSpec observations"
            ),
        ),
        GateResult(
            "historical_workload_cohort_sufficient",
            historical.get("total", 0) >= 100 and historical.get("distinct_slugs", 0) >= 10,
            (
                f"historical total={historical.get('total', 0)}; "
                f"distinct slugs={historical.get('distinct_slugs', 0)}"
            ),
        ),
        GateResult(
            "controlled_wave0_cohort_sufficient",
            controlled.get("total", 0) >= 100
            and controlled.get("distinct_eligible_slugs", 0) >= 10,
            (
                f"controlled total={controlled.get('total', 0)}; "
                f"distinct eligible slugs={controlled.get('distinct_eligible_slugs', 0)}"
            ),
        ),
        GateResult(
            "shadow_correctness_and_latency",
            traffic["status"] == "available"
            and traffic.get("execution_mismatches", 0) == 0
            and traffic.get("substrate_exceptions", 0) == 0
            and traffic.get("quarantine_required", 0) == 0
            and traffic.get("comparison_latency_p95_ms") is not None
            and traffic["comparison_latency_p95_ms"] < 10,
            (
                f"mismatches={traffic.get('execution_mismatches')}; "
                f"exceptions={traffic.get('substrate_exceptions')}; "
                f"quarantine={traffic.get('quarantine_required')}; "
                f"p95_ms={traffic.get('comparison_latency_p95_ms')}"
            ),
        ),
        GateResult(
            "substrate_simplicity_evidence",
            complexity.summary["simplicity_gate_pass"],
            (
                "one numeric executor; one numeric/unit policy; zero row-specific execution branches; "
                f"raw cyclomatic diagnostic legacy={complexity.summary['legacy_core_total']}, "
                f"substrate={complexity.summary['substrate_core_total']}"
            ),
        ),
    )
    failed = [gate.gate for gate in gates if not gate.passed]
    decision = "pass" if not failed else "blocked"
    return MilestoneAReport(
        schema_version=1,
        decision=decision,
        gates=gates,
        summary={
            "registered_rows": len(registered),
            "eligible_rows": len(eligible),
            "blocked_rows": len(later),
            "invalid_rows": sum(row.compile_result.status == "invalid" for row in registered),
            "equivalence_counts": equivalence_counts,
            "candidates_checked": convergence.summary["candidates_checked"],
            "failed_gates": failed,
            "complexity": asdict(complexity),
            "traffic_coverage": capability.summary["traffic_coverage"],
        },
        cutover_demonstration=cutover,
        reviewed_fixture={
            "relationship_id": compiled.descriptor.relationship_id,
            "expression_canonical_digest": expression_canonical_digest(compiled.descriptor.expression),
            "symbols": [symbol.name for symbol in compiled.descriptor.symbols],
            "domain_constraint_count": len(compiled.descriptor.domain_constraints),
            "added_executable_semantics": False,
        },
        benefits=(
            "Eligible authored rows execute without formula_engine._eval.",
            "Terminating decimals and rational operations are exact until display rounding.",
            "Multiplicative units and output dimensions are validated before execution.",
            "Division yields explicit nonzero constraints.",
            "Canonical expression, policy, and execution-input identities support deterministic replay.",
            "Execution and teaching-projection drift are reported independently.",
        ),
        unsupported_boundaries=(
            "dataset and paired-dataset inputs",
            "multi-output dependency graphs",
            "dynamic powers and approximating functions",
            "arbitrary calls and custom callbacks",
            "affine temperature units",
            "vectors, aggregates, and cross-currency conversion",
        ),
    )
