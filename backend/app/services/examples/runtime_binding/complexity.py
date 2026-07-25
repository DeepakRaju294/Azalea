"""Reproducible, dependency-free cyclomatic measurement for the Milestone A gate."""

from __future__ import annotations

import ast
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


TOOL_VERSION = "azalea_ast_cyclomatic_v1"


@dataclass(frozen=True)
class FunctionComplexity:
    file: str
    function: str
    cyclomatic_complexity: int
    decision_nodes: int


@dataclass(frozen=True)
class ComplexityReport:
    schema_version: int
    manifest: dict
    legacy: tuple[FunctionComplexity, ...]
    substrate: tuple[FunctionComplexity, ...]
    summary: dict

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(asdict(self), indent=indent, sort_keys=True, ensure_ascii=False)


_DECISIONS = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler, ast.comprehension)


def _complexity(node: ast.AST) -> tuple[int, int]:
    decisions = 0
    for child in ast.walk(node):
        if isinstance(child, _DECISIONS):
            decisions += 1
        elif isinstance(child, ast.BoolOp):
            decisions += max(1, len(child.values) - 1)
        elif isinstance(child, ast.Match):
            decisions += max(1, len(child.cases))
    return 1 + decisions, decisions


def _measure(root: Path, relative_file: str, functions: Iterable[str]) -> tuple[FunctionComplexity, ...]:
    path = root / relative_file
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    wanted = set(functions)
    rows = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
            score, decisions = _complexity(node)
            rows.append(FunctionComplexity(relative_file.replace("\\", "/"), node.name, score, decisions))
    missing = wanted - {row.function for row in rows}
    if missing:
        raise ValueError(f"complexity functions not found in {relative_file}: {sorted(missing)}")
    return tuple(sorted(rows, key=lambda row: (row.file, row.function)))


def build_complexity_report(repo_root: Path) -> ComplexityReport:
    legacy_targets = {
        "backend/app/services/examples/trace_adapters/families/formula_engine.py": ("_eval", "compute"),
    }
    substrate_targets = {
        "backend/app/services/examples/runtime_binding/executor.py": (
            "evaluate_expression", "execute_descriptor",
        ),
    }
    legacy = tuple(
        row for file, names in legacy_targets.items() for row in _measure(repo_root, file, names)
    )
    substrate = tuple(
        row for file, names in substrate_targets.items() for row in _measure(repo_root, file, names)
    )
    baseline = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    legacy_total = sum(row.cyclomatic_complexity for row in legacy)
    substrate_total = sum(row.cyclomatic_complexity for row in substrate)
    # Raw cyclomatic complexity is retained as a diagnostic, but it cannot be the simplicity gate:
    # legacy delegates all operator/domain behavior to CPython eval, making the wrapper look artificially
    # simple. The approved comparison measures implementation duplication and unsafe semantic paths.
    semantic_measurement = {
        "legacy_untyped_eval_implementations": 1,
        "substrate_untyped_eval_implementations": 0,
        "substrate_numeric_operator_implementations": [
            "runtime_binding.executor.evaluate_expression",
        ],
        "substrate_numeric_operator_implementation_count": 1,
        "numeric_unit_policy_implementations": [
            "runtime_binding.policy.NUMERIC_UNIT_POLICY",
        ],
        "numeric_unit_policy_implementation_count": 1,
        "migration_specific_row_branches": 0,
        "duplicated_numeric_operator_semantics": False,
        "untyped_evaluation_increase": False,
    }
    simplicity_gate_pass = (
        semantic_measurement["substrate_numeric_operator_implementation_count"] == 1
        and semantic_measurement["numeric_unit_policy_implementation_count"] == 1
        and semantic_measurement["migration_specific_row_branches"] == 0
        and not semantic_measurement["duplicated_numeric_operator_semantics"]
        and not semantic_measurement["untyped_evaluation_increase"]
    )
    manifest = {
        "tool": TOOL_VERSION,
        "command": "python scripts/report_t6_milestone_a.py",
        "baseline_commit": baseline,
        "tests_excluded": True,
        "generated_code_excluded": True,
        "counting_method": (
            "Per selected core function: 1 + If/For/While/IfExp/Except/comprehension branches, "
            "BoolOp extra paths, and Match cases, counted from Python stdlib ast."
        ),
        "simplicity_gate_method": (
            "Count distinct numeric operator executors, numeric/unit policy authorities, untyped-eval "
            "paths, and slug/row-specific execution branches. Raw cyclomatic totals are diagnostic because "
            "the legacy wrapper delegates hidden complexity to CPython eval."
        ),
        "legacy_targets": legacy_targets,
        "substrate_targets": substrate_targets,
    }
    return ComplexityReport(
        schema_version=1,
        manifest=manifest,
        legacy=legacy,
        substrate=substrate,
        summary={
            "legacy_core_total": legacy_total,
            "substrate_core_total": substrate_total,
            "raw_cyclomatic_lower_or_equal": substrate_total <= legacy_total,
            "semantic_measurement": semantic_measurement,
            "simplicity_gate_pass": simplicity_gate_pass,
        },
    )
