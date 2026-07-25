"""Offline Milestone A compiler coverage and equivalence harnesses.

Nothing in this module changes routing or persists production state. Legacy FormulaSpec execution
remains the comparison oracle while the restricted substrate is evaluated.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Literal, Sequence

from app.services.examples.runtime_binding.compiler import compile_formula_spec
from app.services.examples.runtime_binding.executor import ExecutionError, execute_descriptor
from app.services.examples.runtime_binding.inventory import inventory_live_catalog
from app.services.examples.trace_adapters.decl import hydrate
from app.services.examples.trace_adapters.families.formula_engine import FormulaSpec, _num, formula_decl


EquivalenceStatus = Literal["pass", "accepted_nonsemantic_drift", "blocked", "failed"]


@dataclass(frozen=True)
class EquivalenceIssue:
    candidate_id: str
    dimension: str
    legacy: str
    substrate: str


@dataclass(frozen=True)
class ExecutionEquivalence:
    status: EquivalenceStatus
    candidates_checked: int
    issues: tuple[EquivalenceIssue, ...]


@dataclass(frozen=True)
class TeachingProjectionEquivalence:
    status: EquivalenceStatus
    candidates_checked: int
    issues: tuple[EquivalenceIssue, ...]


@dataclass(frozen=True)
class RowConvergence:
    slug: str
    family: str
    compile_status: Literal["compiled", "blocked", "invalid"]
    compile_blockers: tuple[str, ...]
    execution: ExecutionEquivalence
    teaching: TeachingProjectionEquivalence


@dataclass(frozen=True)
class ConvergenceReport:
    schema_version: int
    rows: tuple[RowConvergence, ...]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, ensure_ascii=False)


def _blocked_equivalence() -> tuple[ExecutionEquivalence, TeachingProjectionEquivalence]:
    return (
        ExecutionEquivalence("blocked", 0, ()),
        TeachingProjectionEquivalence("blocked", 0, ()),
    )


def _candidate_rows(spec: FormulaSpec, *, seeds: Sequence[int], candidates_per_seed: int):
    adapter = hydrate(formula_decl(spec))
    for seed in seeds:
        for index, candidate in enumerate(adapter.candidates(seed)):
            if index >= candidates_per_seed:
                break
            yield adapter, seed, candidate


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
            raise ExecutionError(f"unsupported candidate input for scalar executor: {name}")
    return result


def compare_formula_spec(
    spec: FormulaSpec,
    *,
    seeds: Sequence[int] = (0, 1, 2),
    candidates_per_seed: int = 8,
) -> RowConvergence:
    compiled = compile_formula_spec(spec)
    if compiled.status != "compiled" or compiled.descriptor is None:
        execution, teaching = _blocked_equivalence()
        return RowConvergence(
            slug=spec.slug,
            family=spec.family,
            compile_status=compiled.status,
            compile_blockers=compiled.blockers,
            execution=execution,
            teaching=teaching,
        )

    execution_issues: list[EquivalenceIssue] = []
    teaching_issues: list[EquivalenceIssue] = []
    checked = 0
    output = spec.outputs[0]

    for adapter, seed, candidate in _candidate_rows(
        spec, seeds=seeds, candidates_per_seed=candidates_per_seed
    ):
        candidate_id = str(candidate.get("_id") or f"{spec.slug}:{seed}:{checked}")
        checked += 1
        try:
            legacy_result = spec.compute(candidate)[output.name]
            substrate_result = execute_descriptor(compiled.descriptor, _exact_inputs(candidate))
            substrate_display = _num(float(substrate_result.value))
        except Exception as exc:  # classification evidence; never hide a substrate exception
            execution_issues.append(
                EquivalenceIssue(candidate_id, "execution_exception", "completed", repr(exc))
            )
            continue

        if substrate_display != legacy_result:
            execution_issues.append(
                EquivalenceIssue(
                    candidate_id,
                    "displayed_result",
                    repr(legacy_result),
                    repr(substrate_display),
                )
            )
        if substrate_result.output_unit != output.unit:
            execution_issues.append(
                EquivalenceIssue(candidate_id, "unit", output.unit, substrate_result.output_unit)
            )

        try:
            trace = adapter.reference(candidate, candidate_id=candidate_id, seed=seed)
        except Exception as exc:
            teaching_issues.append(
                EquivalenceIssue(candidate_id, "legacy_trace_exception", "completed", repr(exc))
            )
            continue
        operations = tuple(step.operation for step in trace.steps)
        expected_operations = ("identify_knowns", output.stage())
        if operations != expected_operations:
            teaching_issues.append(
                EquivalenceIssue(
                    candidate_id,
                    "trace_stages",
                    repr(operations),
                    repr(expected_operations),
                )
            )
        if trace.final_answer.get(output.name) != substrate_display:
            teaching_issues.append(
                EquivalenceIssue(
                    candidate_id,
                    "authoritative_result",
                    repr(trace.final_answer.get(output.name)),
                    repr(substrate_display),
                )
            )
        compute_step = trace.steps[-1]
        if output.unit and output.unit not in str(compute_step.reason):
            teaching_issues.append(
                EquivalenceIssue(candidate_id, "rendered_unit", output.unit, str(compute_step.reason))
            )
        if "=" not in str(compute_step.reason):
            teaching_issues.append(
                EquivalenceIssue(candidate_id, "rendered_equation", "contains '='", str(compute_step.reason))
            )

    execution_status: EquivalenceStatus = "failed" if execution_issues else "pass"
    teaching_status: EquivalenceStatus = "failed" if teaching_issues else "pass"
    return RowConvergence(
        slug=spec.slug,
        family=spec.family,
        compile_status="compiled",
        compile_blockers=(),
        execution=ExecutionEquivalence(execution_status, checked, tuple(execution_issues)),
        teaching=TeachingProjectionEquivalence(teaching_status, checked, tuple(teaching_issues)),
    )


def build_offline_convergence_report(
    specs: Sequence[FormulaSpec],
    *,
    seeds: Sequence[int] = (0, 1, 2),
    candidates_per_seed: int = 8,
) -> ConvergenceReport:
    rows = tuple(
        compare_formula_spec(spec, seeds=seeds, candidates_per_seed=candidates_per_seed)
        for spec in specs
    )
    family_coverage: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "compiled": 0})
    for row in rows:
        family_coverage[row.family]["total"] += 1
        if row.compile_status == "compiled":
            family_coverage[row.family]["compiled"] += 1

    summary = {
        "total_rows": len(rows),
        "compile_status_counts": dict(sorted(Counter(row.compile_status for row in rows).items())),
        "execution_status_counts": dict(sorted(Counter(row.execution.status for row in rows).items())),
        "teaching_status_counts": dict(sorted(Counter(row.teaching.status for row in rows).items())),
        "candidates_checked": sum(row.execution.candidates_checked for row in rows),
        "family_coverage": {key: family_coverage[key] for key in sorted(family_coverage)},
        "traffic_coverage": {
            "status": "unavailable",
            "reason": "No per-FormulaSpec production execution-volume source is wired into Milestone A yet.",
        },
    }
    return ConvergenceReport(schema_version=1, rows=rows, summary=summary)


def build_live_offline_convergence_report(
    *,
    seeds: Sequence[int] = (0, 1, 2),
    candidates_per_seed: int = 8,
) -> ConvergenceReport:
    # Load inventory first so catalog/source inconsistencies fail before comparison.
    inventory_live_catalog()
    from app.services.examples.trace_adapters.families.formula_specs import ALL_SPECS

    return build_offline_convergence_report(
        ALL_SPECS, seeds=seeds, candidates_per_seed=candidates_per_seed
    )

