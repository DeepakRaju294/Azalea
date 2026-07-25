"""Read-only T6 FormulaSpec inventory for Grounded Runtime Binding Milestone A.

This module parses reviewed expression strings but never evaluates them. Its output is stable,
machine-readable evidence used to decide the supported Wave-0 substrate before implementation.
"""

from __future__ import annotations

import ast
import inspect
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence

from app.services.examples.trace_adapters.families.formula_engine import FormulaSpec


INVENTORY_SCHEMA_VERSION = 1

_WAVE_1_CALLS = {"len", "max", "median", "min", "sorted", "sum", "zip"}
_WAVE_2_CALLS = {"sqrt"}
_WAVE_3_CALLS = {
    "acos", "asin", "atan", "cos", "degrees", "exp", "log", "log10", "radians", "sin", "tan"
}
_UNPLANNED_CALLS = {"abs", "factorial"}

_ALLOWED_WAVE_0_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.USub,
    ast.UAdd,
)


@dataclass(frozen=True)
class SourceLocation:
    file: str
    line: int


@dataclass(frozen=True)
class OutputInventory:
    name: str
    expression: str
    unit: str
    stage_id: str
    ast_nodes: tuple[str, ...]
    operators: tuple[str, ...]
    calls: tuple[str, ...]
    symbols_read: tuple[str, ...]
    prior_output_dependencies: tuple[str, ...]
    parse_error: str | None


@dataclass(frozen=True)
class GivenInventory:
    name: str
    unit: str
    scalar_type: Literal["integer", "terminating_decimal"]


@dataclass(frozen=True)
class CompileResult:
    status: Literal["compiled", "blocked", "invalid"]
    required_wave: int | None
    unsupported_constructs: tuple[str, ...]
    execution_shape_blockers: tuple[str, ...]
    source_locations: tuple[SourceLocation, ...]


@dataclass(frozen=True)
class FormulaRowInventory:
    row_index: int
    slug: str
    title: str
    family: str
    registered: bool
    input_shape: Literal["scalar", "dataset", "paired_dataset"]
    output_count: int
    givens: tuple[GivenInventory, ...]
    constants: tuple[str, ...]
    conventions: tuple[str, ...]
    has_cases: bool
    has_instance_predicate: bool
    has_interpretation_callback: bool
    outputs: tuple[OutputInventory, ...]
    compile_result: CompileResult


@dataclass(frozen=True)
class InventoryReport:
    schema_version: int
    rows: tuple[FormulaRowInventory, ...]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, ensure_ascii=False)


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    return f"<{type(node.func).__name__}>"


def _formula_source_locations(source_path: Path | None) -> dict[str, SourceLocation]:
    if source_path is None or not source_path.exists():
        return {}
    try:
        app_index = source_path.parts.index("app")
        stable_source_name = "/".join(source_path.parts[app_index:])
    except ValueError:
        stable_source_name = source_path.name
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    locations: dict[str, SourceLocation] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "FormulaSpec":
            continue
        slug = next(
            (
                keyword.value.value
                for keyword in node.keywords
                if keyword.arg == "slug"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ),
            None,
        )
        if slug:
            locations[slug] = SourceLocation(file=stable_source_name, line=node.lineno)
    return locations


def _inspect_output(expression: str, name: str, unit: str, stage_id: str,
                    prior_outputs: set[str]) -> OutputInventory:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        return OutputInventory(
            name=name,
            expression=expression,
            unit=unit,
            stage_id=stage_id,
            ast_nodes=(),
            operators=(),
            calls=(),
            symbols_read=(),
            prior_output_dependencies=(),
            parse_error=f"{exc.msg} at line {exc.lineno}, column {exc.offset}",
        )

    nodes = tuple(sorted({type(node).__name__ for node in ast.walk(tree)}))
    operators = tuple(
        sorted(
            {
                type(node.op).__name__
                for node in ast.walk(tree)
                if isinstance(node, (ast.BinOp, ast.UnaryOp))
            }
        )
    )
    calls = tuple(sorted({_call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)}))
    symbols = tuple(
        sorted(
            {
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name) and node.id not in calls
            }
        )
    )
    dependencies = tuple(sorted(set(symbols) & prior_outputs))
    return OutputInventory(
        name=name,
        expression=expression,
        unit=unit,
        stage_id=stage_id,
        ast_nodes=nodes,
        operators=operators,
        calls=calls,
        symbols_read=symbols,
        prior_output_dependencies=dependencies,
        parse_error=None,
    )


def _classify(spec: FormulaSpec, outputs: Sequence[OutputInventory],
              location: SourceLocation | None) -> CompileResult:
    source_locations = (location,) if location else ()
    if any(output.parse_error for output in outputs):
        return CompileResult(
            status="invalid",
            required_wave=None,
            unsupported_constructs=tuple(
                sorted(output.parse_error for output in outputs if output.parse_error)
            ),
            execution_shape_blockers=(),
            source_locations=source_locations,
        )

    blockers: set[str] = set()
    unsupported: set[str] = set()
    required_wave = 0

    if spec.dataset2 is not None:
        required_wave = max(required_wave, 1)
        blockers.add("paired_dataset_input")
    elif spec.dataset is not None:
        required_wave = max(required_wave, 1)
        blockers.add("dataset_input")

    if len(spec.outputs) != 1:
        blockers.add("multi_output_dependency_shape")
    if spec.instance_ok is not None:
        blockers.add("custom_instance_predicate")
    if spec.interpret is not None:
        blockers.add("custom_interpretation_callback")
    if spec.cases:
        blockers.add("custom_coverage_cases")

    for output in outputs:
        for call in output.calls:
            if call in _WAVE_1_CALLS:
                required_wave = max(required_wave, 1)
            elif call in _WAVE_2_CALLS:
                required_wave = max(required_wave, 2)
            elif call in _WAVE_3_CALLS:
                required_wave = max(required_wave, 3)
            elif call in _UNPLANNED_CALLS:
                unsupported.add(f"unplanned_call:{call}")
            else:
                unsupported.add(f"unknown_call:{call}")

        try:
            tree = ast.parse(output.expression, mode="eval")
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                continue
            if not isinstance(node, _ALLOWED_WAVE_0_NODES):
                unsupported.add(f"unsupported_ast_node:{type(node).__name__}")

    if required_wave > 0:
        blockers.add(f"requires_wave_{required_wave}")

    if unsupported or blockers:
        status: Literal["compiled", "blocked", "invalid"] = "blocked"
    else:
        status = "compiled"
    if unsupported and required_wave == 0:
        required_wave = None

    return CompileResult(
        status=status,
        required_wave=required_wave,
        unsupported_constructs=tuple(sorted(unsupported)),
        execution_shape_blockers=tuple(sorted(blockers)),
        source_locations=source_locations,
    )


def inventory_formula_specs(
    specs: Iterable[FormulaSpec],
    *,
    source_path: str | Path | None = None,
) -> InventoryReport:
    """Inventory specs deterministically without calling compute, reference, or eval."""
    spec_list = list(specs)
    path = Path(source_path).resolve() if source_path is not None else None
    locations = _formula_source_locations(path)
    rows: list[FormulaRowInventory] = []

    for index, spec in enumerate(spec_list):
        prior_outputs: set[str] = set()
        output_rows: list[OutputInventory] = []
        for output in spec.outputs:
            inspected = _inspect_output(
                output.expr,
                output.name,
                output.unit,
                output.stage(),
                prior_outputs,
            )
            output_rows.append(inspected)
            prior_outputs.add(output.name)

        input_shape: Literal["scalar", "dataset", "paired_dataset"] = "scalar"
        if spec.dataset2 is not None:
            input_shape = "paired_dataset"
        elif spec.dataset is not None:
            input_shape = "dataset"

        compile_result = _classify(spec, output_rows, locations.get(spec.slug))
        if not any(output.parse_error for output in output_rows):
            # The typed compiler is the final Wave-0 eligibility authority. Preserve the richer
            # inventory wave/call evidence while ensuring inventory and compiler status cannot diverge.
            from app.services.examples.runtime_binding.compiler import compile_formula_spec

            typed = compile_formula_spec(spec)
            compile_result = CompileResult(
                status=typed.status,
                required_wave=compile_result.required_wave,
                unsupported_constructs=compile_result.unsupported_constructs,
                execution_shape_blockers=tuple(
                    sorted(set(compile_result.execution_shape_blockers) | set(typed.blockers))
                ),
                source_locations=compile_result.source_locations,
            )
        rows.append(
            FormulaRowInventory(
                row_index=index,
                slug=spec.slug,
                title=spec.title,
                family=spec.family,
                registered=bool(spec.register),
                input_shape=input_shape,
                output_count=len(spec.outputs),
                givens=tuple(
                    GivenInventory(
                        name=given.name,
                        unit=given.unit,
                        scalar_type="integer" if given.integer else "terminating_decimal",
                    )
                    for given in spec.givens
                ),
                constants=tuple(sorted(spec.constants)),
                conventions=tuple(sorted(spec.conventions)),
                has_cases=bool(spec.cases),
                has_instance_predicate=spec.instance_ok is not None,
                has_interpretation_callback=spec.interpret is not None,
                outputs=tuple(output_rows),
                compile_result=compile_result,
            )
        )

    status_counts = Counter(row.compile_result.status for row in rows)
    registered_rows = [row for row in rows if row.registered]
    summary: dict[str, Any] = {
        "total_rows": len(rows),
        "registered_rows": len(registered_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "registered_status_counts": dict(
            sorted(Counter(row.compile_result.status for row in registered_rows).items())
        ),
        "input_shape_counts": dict(sorted(Counter(row.input_shape for row in registered_rows).items())),
        "family_counts": dict(sorted(Counter(row.family for row in registered_rows).items())),
        "duplicate_slugs": sorted(
            slug for slug, count in Counter(row.slug for row in rows).items() if count > 1
        ),
    }
    return InventoryReport(
        schema_version=INVENTORY_SCHEMA_VERSION,
        rows=tuple(rows),
        summary=summary,
    )


def inventory_live_catalog() -> InventoryReport:
    """Inventory the live ALL_SPECS catalog with declaration source locations."""
    from app.services.examples.trace_adapters.families import formula_specs

    source_file = inspect.getsourcefile(formula_specs)
    return inventory_formula_specs(formula_specs.ALL_SPECS, source_path=source_file)
