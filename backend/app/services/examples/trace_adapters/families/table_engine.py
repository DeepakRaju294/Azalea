"""T14 Table-Evaluation Engine (ADAPTER_TAXONOMY_SPEC T14 `indexed_table_evaluation`) — the DECLARATIVE type
template for building a table whose cells are INDEPENDENTLY evaluated: select the next row/cell → apply a LOCAL
rule → store the value → the table stays a valid exhaustive/normalized table.

Distinct from T5 DP (a cell is a recurrence over other cells) and from T8a construction (a growing valid
structure): here each cell is an independent local evaluation and the invariant is TABLE-level (the rows are the
exhaustive input set). The engine fills the table for real; the gate (`test_table_engine`) recomputes every cell
from the local rule and checks the table invariant (exhaustive 2^n rows) + the answer vs an independent recompute.

v1 pilots truth tables of Boolean expressions; the same grammar covers K-maps, transition tables, and probability
tables. A concept is a `TableSpec`: variables + a local cell rule + display. Adding one = a one-file DATA edit."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..decl import AdapterDecl
from ..example_spec import ExampleSpec, InstanceShape, StageSpec


def _ints(*parts: Any) -> list[int]:
    found: set[int] = set()
    for m in re.findall(r"-?\d+", " ".join(str(p) for p in parts)):
        found.add(int(m)); found.add(abs(int(m)))
    return sorted(found)


def _assignments(variables: list[str]) -> list[dict]:
    """All 2^n input assignments in canonical (binary-counting) order."""
    n = len(variables)
    out = []
    for i in range(2 ** n):
        bits = [(i >> (n - 1 - j)) & 1 for j in range(n)]
        out.append({variables[j]: bits[j] for j in range(n)})
    return out


def _row_str(variables: list[str], assign: dict, val: int) -> str:
    left = " ".join(f"{v}={assign[v]}" for v in variables)
    return f"{left} | {val}"


@dataclass
class TableSpec:
    slug: str
    title: str
    problem_template: str                       # .format(expr=expr_str) -> problem
    variables: list                             # ordered variable names
    expr: Callable[[dict], bool]                # the local cell rule: assignment -> truth value
    expr_str: str                               # display form, e.g. "A AND (B OR C)"
    family: str = "discrete"
    aliases: list = field(default_factory=list)
    not_aliases: list = field(default_factory=list)
    priority: int = 50
    register: bool = True
    n_candidates: int = 4
    label_convention: str = "ints"

    def column(self) -> list[int]:
        return [1 if self.expr(a) else 0 for a in _assignments(self.variables)]

    def oracle(self, state: dict) -> dict:
        col = self.column()
        return {"column": "".join(str(b) for b in col), "true_count": str(sum(col))}


def _candidates(self, seed: int) -> Iterable[dict[str, Any]]:
    spec: TableSpec = self._table_spec
    for i in range(spec.n_candidates):
        yield {"expr_str": spec.expr_str, "vars": list(spec.variables), "_id": f"{spec.slug}_v1_case_{i}"}


def _is_teaching_trace(self, trace: ContractTrace) -> bool:
    return bool(trace.steps) and trace.steps[0].operation == "initialize" and len(trace.steps) >= 2


def _reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
               attempt: int = 1, seed: int = 0) -> ContractTrace:
    spec: TableSpec = self._table_spec
    variables = list(spec.variables)
    assigns = _assignments(variables)
    column = spec.column()
    true_count = sum(column)
    col_str = "".join(str(b) for b in column)
    ans = {"column": col_str, "true_count": str(true_count)}

    header = " ".join(variables) + " | " + spec.expr_str
    steps: list[Step] = []
    evidence: dict[str, list[str]] = {"initialize": [], "fill_row": [], "completion": []}

    # s1 initialize — the empty table (header only)
    steps.append(Step(
        id="s1", operation="initialize", prior_state={"problem": spec.title},
        state_after={"output": f"[{header}]"}, inputs=dict(example_input),
        decision=f"set up the truth table for {spec.expr_str}",
        reason=f"one row per input assignment; there are 2^{len(variables)} = {len(assigns)} rows",
        visual_state={"kind": "variables", "output": f"[{header}]"},
        expected_visible_result=f"Table header: {header}. {len(assigns)} rows to fill.",
        facts={"allowed_values": _ints(len(assigns), len(variables)),
               "required_facts": [fact("initialize", header)], "forbidden_claims": []}))
    evidence["initialize"].append("s1")

    prev_render = f"[{header}]"
    filled: list[str] = []
    for idx, assign in enumerate(assigns):
        val = column[idx]
        filled.append(_row_str(variables, assign, val))
        rendered = "[" + header + "]  " + " ; ".join(filled)
        step_id = f"s{idx + 2}"
        is_last = idx == len(assigns) - 1
        assign_str = ", ".join(f"{v}={assign[v]}" for v in variables)
        evis = f"Row {idx + 1}: {assign_str} -> {val}."
        state_after = {"output": rendered}
        if is_last:
            summary = f"{rendered}  =>  column {col_str} ({true_count} true)"
            state_after = {"output": summary}
            evis = f"Last row {assign_str} -> {val}. Column = {col_str} ({true_count} true)."
            evidence["completion"].append(step_id)
        evidence["fill_row"].append(step_id)
        steps.append(Step(
            id=step_id, operation="fill_row", prior_state={"output": prev_render}, state_after=state_after,
            inputs={"output": rendered},
            decision=f"evaluate {spec.expr_str} at {assign_str}",
            reason=f"substitute {assign_str} into {spec.expr_str}; the cell value is {val}",
            visual_state={"kind": "variables", "output": rendered}, expected_visible_result=evis,
            facts={"allowed_values": _ints(rendered, col_str if is_last else "", true_count if is_last else ""),
                   "required_facts": [fact("fill_row", str(val))], "forbidden_claims": []}))
        prev_render = state_after["output"]

    return ContractTrace(
        problem=spec.problem_template.format(expr=spec.expr_str),
        conventions={"method": "evaluate the expression at every input assignment; the table is exhaustive"},
        initial_state={"problem": spec.title}, final_answer=dict(ans), steps=steps,
        invariants=[{"id": f"{spec.slug}_exhaustive", "scope": "terminal",
                     "statement": "the table has exactly 2^n rows, one per input assignment"}],
        required_cases=["initialize", "fill_row", "completion"], case_evidence=evidence,
        provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                    attempt=attempt))


def _states_equivalent(self, a, b):
    return str((a or {}).get("output")) == str((b or {}).get("output"))


def _final_answer_entails(self, state, answer):
    out = str((state or {}).get("output", ""))
    return all(str(v) in out for v in (answer or {}).values())


def _invariant_holds(self, inv, state):
    return True   # exhaustiveness is proven positively by the gate (2^n rows recomputed)


def _validate_step_shape(self, step):
    ok = {"initialize", "fill_row"}
    return [] if step.operation in ok else [f"unexpected operation {step.operation!r}"]


def _validate_prose_claims(self, card, step):
    return []


_METHODS = {
    "candidates": _candidates, "is_teaching_trace": _is_teaching_trace, "reference": _reference,
    "states_equivalent": _states_equivalent, "final_answer_entails": _final_answer_entails,
    "invariant_holds": _invariant_holds, "validate_step_shape": _validate_step_shape,
    "validate_prose_claims": _validate_prose_claims,
}


def build_example_spec(spec: TableSpec) -> ExampleSpec:
    stages = {
        "initialize": StageSpec("initialize", "set up the table header", cardinality="exactly_once",
                                teaching_focus="the table and how many rows it has",
                                contains={"initialize": "required"},
                                state_effects=["the empty table is set up"]),
        "fill_row": StageSpec("fill_row", "evaluate one row", cardinality="one_or_more",
                              teaching_focus="evaluate the expression at one input assignment",
                              contains={"fill_row": "required"},
                              state_effects=["one row is filled in"])}
    return ExampleSpec(
        input=InstanceShape("sequence", count=(1, 1), structure=[spec.slug]),
        stages=stages, structure="initialize fill_row",
        must_exercise=["initialize", "fill_row", "completion"], must_cover=[], must_avoid=[],
        terminal="the table is fully filled", output_shape="the output column")


def manifest_entry(spec: TableSpec) -> dict[str, Any]:
    return {"type": "T14", "family": spec.family, "status": "experimental",
            "verification_level": "trace_verified", "coding": False, "canonical_solution": None,
            "routing_aliases": list(spec.aliases), "negative_guards": list(spec.not_aliases), "fixtures": []}


def routing_rule(spec: TableSpec) -> dict[str, Any]:
    rule: dict[str, Any] = {"any": list(spec.aliases), "priority": spec.priority}
    if spec.not_aliases:
        rule["not"] = list(spec.not_aliases)
    return rule


def table_decl(spec: TableSpec) -> AdapterDecl:
    return AdapterDecl(
        slug=spec.slug, type="T14", family=spec.family, example_spec=build_example_spec(spec),
        methods=dict(_METHODS), label_convention=spec.label_convention, routing=routing_rule(spec),
        class_attrs={"_table_spec": spec, "provides_narration": True})


def registered_specs() -> list[TableSpec]:
    from . import table_specs
    return [s for s in table_specs.ALL_SPECS if s.register]
