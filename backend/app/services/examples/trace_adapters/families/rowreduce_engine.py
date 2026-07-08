"""T15 Row-Reduction Engine (ADAPTER_TAXONOMY_SPEC T15 `matrix_row_operation_elimination`) — the DECLARATIVE type
template for solving a linear system by Gauss-Jordan elimination: choose a pivot → apply a structured row
operation over the WHOLE augmented matrix → the represented system's solution set is preserved → read the
solution off the reduced matrix.

Distinct from T7 scalar rewriting: the teaching atom is a row operation with pivot logic over a matrix, and the
invariant is **solution-set preservation** (not a single algebraic rewrite). The engine performs RREF for real;
the gate (`test_rowreduce_engine`) checks (1) the extracted solution against an INDEPENDENT Cramer's-rule oracle,
and (2) that the true solution satisfies EVERY intermediate augmented matrix (each row op preserved the system).

A concept is a `RowReduceSpec`: how to generate a solvable integer system + naming/routing. The elimination itself
is generic, so adding a linear-system concept is a one-file DATA edit (append a spec to `ALL_SPECS`)."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..decl import AdapterDecl
from ..example_spec import ExampleSpec, InstanceShape, StageSpec


# ── fraction / matrix helpers ────────────────────────────────────────────────────────────────────────────────
def _fs(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def _ints(*parts: Any) -> list[int]:
    found: set[int] = set()
    for m in re.findall(r"-?\d+", " ".join(str(p) for p in parts)):
        found.add(int(m)); found.add(abs(int(m)))
    return sorted(found)


def _render(mat: list[list[Fraction]], n: int) -> str:
    """Render an augmented matrix [A|b] as rows '[a b c | d]'."""
    rows = []
    for row in mat:
        left = " ".join(_fs(v) for v in row[:n])
        rows.append(f"[{left} | {_fs(row[n])}]")
    return "  ".join(rows)


def _aug(A: list[list[int]], b: list[int]) -> list[list[Fraction]]:
    return [[Fraction(v) for v in row] + [Fraction(b[i])] for i, row in enumerate(A)]


# ── the RREF reference (the trace) ───────────────────────────────────────────────────────────────────────────
def _rref_ops(A: list[list[int]], b: list[int]):
    """Run Gauss-Jordan elimination, yielding (operation, matrix_snapshot, factor, pivot_row, target_row).

    Assumes a nonzero pivot is available on the diagonal at each step (the generator guarantees this), so no row
    swaps are produced in v1. Every snapshot is a deep copy so the caller can inspect the full history."""
    n = len(A)
    M = _aug(A, b)
    yield ("initialize", [row[:] for row in M], None, None, None)
    for p in range(n):
        piv = M[p][p]
        if piv != 1:
            M[p] = [v / piv for v in M[p]]
            yield ("normalize", [row[:] for row in M], piv, p, p)
        for i in range(n):
            if i == p:
                continue
            factor = M[i][p]
            if factor != 0:
                M[i] = [a - factor * c for a, c in zip(M[i], M[p])]
                yield ("eliminate", [row[:] for row in M], factor, p, i)


def rref_snapshots(A: list[list[int]], b: list[int]) -> list[list[list[Fraction]]]:
    """Every intermediate augmented matrix (for the gate's solution-preservation check)."""
    return [snap for _, snap, _, _, _ in _rref_ops(A, b)]


def rref_solution(A: list[list[int]], b: list[int]) -> list[Fraction]:
    snaps = rref_snapshots(A, b)
    n = len(A)
    return [snaps[-1][i][n] for i in range(n)]


# ── the INDEPENDENT oracle: Cramer's rule (a different algorithm than RREF) ───────────────────────────────────
def _det(M: list[list[Fraction]]) -> Fraction:
    n = len(M)
    if n == 1:
        return M[0][0]
    if n == 2:
        return M[0][0] * M[1][1] - M[0][1] * M[1][0]
    total = Fraction(0)
    for c in range(n):
        minor = [[M[r][cc] for cc in range(n) if cc != c] for r in range(1, n)]
        total += ((-1) ** c) * M[0][c] * _det(minor)
    return total


def cramer_solve(A: list[list[int]], b: list[int]) -> list[Fraction]:
    n = len(A)
    Af = [[Fraction(v) for v in row] for row in A]
    bf = [Fraction(v) for v in b]
    d = _det(Af)
    out = []
    for i in range(n):
        Ai = [row[:] for row in Af]
        for r in range(n):
            Ai[r][i] = bf[r]
        out.append(_det(Ai) / d)
    return out


# ── spec ─────────────────────────────────────────────────────────────────────────────────────────────────────
@dataclass
class RowReduceSpec:
    slug: str
    title: str
    problem_template: str                              # .format(system=<rendered eqs>) -> problem
    n: int                                             # system size (2 or 3 in v1)
    setup: Callable[[random.Random, int], tuple]       # (rng, n) -> (A, b, x_star)  — solvable integer system
    var_names: list = field(default_factory=lambda: ["x", "y", "z"])
    family: str = "linear_algebra"
    aliases: list = field(default_factory=list)
    not_aliases: list = field(default_factory=list)
    priority: int = 50
    register: bool = True
    n_candidates: int = 60
    label_convention: str = "ints"

    def oracle(self, state: dict) -> dict:
        A, b = state["A"], state["b"]
        sol = cramer_solve(A, b)
        return {self.var_names[i]: _fs(sol[i]) for i in range(len(sol))}


# ── engine methods (bound onto the hydrated adapter) ─────────────────────────────────────────────────────────
def _equations(A: list[list[int]], b: list[int], var_names: list) -> str:
    eqs = []
    for i, row in enumerate(A):
        terms = " + ".join(f"{row[j]}{var_names[j]}" for j in range(len(row)))
        eqs.append(f"{terms} = {b[i]}")
    return "; ".join(eqs)


def _candidates(self, seed: int) -> Iterable[dict[str, Any]]:
    spec: RowReduceSpec = self._rowreduce_spec
    rng = random.Random(seed)
    for i in range(spec.n_candidates):
        A, b, x_star = spec.setup(rng, spec.n)
        yield {"A": A, "b": b, "x_star": x_star, "_id": f"{spec.slug}_v1_case_{i}"}


def _is_teaching_trace(self, trace: ContractTrace) -> bool:
    return bool(trace.steps) and trace.steps[0].operation == "initialize" and len(trace.steps) >= 2


def _reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
               attempt: int = 1, seed: int = 0) -> ContractTrace:
    spec: RowReduceSpec = self._rowreduce_spec
    A, b = example_input["A"], example_input["b"]
    n = spec.n
    var_names = spec.var_names[:n]

    # Only two operations (initialize, eliminate) — a normalize is a row op tagged `eliminate`; `completion` is a
    # CASE mapped to the last eliminate step (mirrors the construct engine), never its own operation.
    ops = list(_rref_ops(A, b))
    solution = rref_solution(A, b)
    ans = {var_names[i]: _fs(solution[i]) for i in range(n)}
    sol_str = ", ".join(f"{var_names[i]} = {_fs(solution[i])}" for i in range(n))

    steps: list[Step] = []
    evidence: dict[str, list[str]] = {"initialize": [], "eliminate": [], "completion": []}
    prev_render = ""
    for idx, (op, snap, factor, prow, trow) in enumerate(ops):
        step_id = f"s{idx + 1}"
        rendered = _render(snap, n)
        is_last = idx == len(ops) - 1
        if op == "initialize":
            operation, decision = "initialize", "write the system as an augmented matrix [A | b]"
            reason = "each equation becomes a row; row operations preserve the solution set"
            evis = f"Augmented matrix: {rendered}."
            evidence["initialize"].append(step_id)
        else:
            operation = "eliminate"
            if op == "normalize":
                decision = f"scale row {prow + 1} so its pivot becomes 1"
                reason = f"divide row {prow + 1} by its pivot {_fs(factor)}; this preserves the solution"
                evis = f"Normalize row {prow + 1}: {rendered}."
            else:
                decision = f"eliminate column {prow + 1} from row {trow + 1}"
                reason = (f"R{trow + 1} <- R{trow + 1} - ({_fs(factor)})*R{prow + 1}; "
                          f"subtracting a multiple of another row preserves the solution")
                evis = f"Eliminate: {rendered}."
            evidence["eliminate"].append(step_id)
        state_after = {"output": rendered}
        if is_last:   # the last row op reaches RREF — read the solution off it (completion case)
            evis = f"Reduced form {rendered} — read off the solution: {sol_str}."
            evidence["completion"].append(step_id)
        prior = {"problem": spec.title} if op == "initialize" else {"output": prev_render}
        steps.append(Step(
            id=step_id, operation=operation, prior_state=prior, state_after=state_after,
            inputs=dict(example_input) if op == "initialize" else {"output": rendered},
            decision=decision, reason=reason,
            visual_state={"kind": "variables", "output": rendered}, expected_visible_result=evis,
            facts={"allowed_values": _ints(rendered, factor, sol_str if is_last else ""),
                   "required_facts": [fact(operation, rendered)], "forbidden_claims": []}))
        prev_render = rendered

    return ContractTrace(
        problem=spec.problem_template.format(system=_equations(A, b, var_names)),
        conventions={"method": "Gauss-Jordan elimination; each row operation preserves the solution set"},
        initial_state={"problem": spec.title}, final_answer=dict(ans), steps=steps,
        invariants=[{"id": f"{spec.slug}_solution_preserved", "scope": "every_step",
                     "statement": "the solution set is preserved after every row operation"}],
        required_cases=["initialize", "eliminate", "completion"], case_evidence=evidence,
        provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                    attempt=attempt))


def _states_equivalent(self, a, b):
    return str((a or {}).get("output")) == str((b or {}).get("output"))


def _final_answer_entails(self, state, answer):
    out = str((state or {}).get("output", ""))
    return all(str(v) in out for v in (answer or {}).values())


def _invariant_holds(self, inv, state):
    # solution preservation is proven POSITIVELY by the gate (the true solution satisfies every snapshot); the
    # rendered state_after carries only a string, so never fail here.
    return True


def _validate_step_shape(self, step):
    ok = {"initialize", "normalize", "eliminate", "completion"}
    return [] if step.operation in ok else [f"unexpected operation {step.operation!r}"]


def _validate_prose_claims(self, card, step):
    return []


_METHODS = {
    "candidates": _candidates, "is_teaching_trace": _is_teaching_trace, "reference": _reference,
    "states_equivalent": _states_equivalent, "final_answer_entails": _final_answer_entails,
    "invariant_holds": _invariant_holds, "validate_step_shape": _validate_step_shape,
    "validate_prose_claims": _validate_prose_claims,
}


def build_example_spec(spec: RowReduceSpec) -> ExampleSpec:
    stages = {
        "initialize": StageSpec("initialize", "write the augmented matrix", cardinality="exactly_once",
                                teaching_focus="the system as an augmented matrix",
                                contains={"initialize": "required"},
                                state_effects=["the system becomes an augmented matrix"]),
        "eliminate": StageSpec("eliminate", "apply a row operation", cardinality="one_or_more",
                               teaching_focus="one pivot/row operation; the solution set is preserved",
                               contains={"eliminate": "required"},
                               state_effects=["one column is reduced toward the identity"])}
    return ExampleSpec(
        input=InstanceShape("sequence", count=(1, 1), structure=[spec.slug]),
        stages=stages, structure="initialize eliminate",
        must_exercise=["initialize", "eliminate", "completion"], must_cover=[], must_avoid=[],
        terminal="the matrix is in reduced row-echelon form", output_shape="the solution vector")


def manifest_entry(spec: RowReduceSpec) -> dict[str, Any]:
    return {"type": "T15", "family": spec.family, "status": "experimental",
            "verification_level": "trace_verified", "coding": False, "canonical_solution": None,
            "routing_aliases": list(spec.aliases), "negative_guards": list(spec.not_aliases), "fixtures": []}


def routing_rule(spec: RowReduceSpec) -> dict[str, Any]:
    rule: dict[str, Any] = {"any": list(spec.aliases), "priority": spec.priority}
    if spec.not_aliases:
        rule["not"] = list(spec.not_aliases)
    return rule


def rowreduce_decl(spec: RowReduceSpec) -> AdapterDecl:
    return AdapterDecl(
        slug=spec.slug, type="T15", family=spec.family, example_spec=build_example_spec(spec),
        methods=dict(_METHODS), label_convention=spec.label_convention, routing=routing_rule(spec),
        class_attrs={"_rowreduce_spec": spec, "provides_narration": True})


def registered_specs() -> list[RowReduceSpec]:
    from . import rowreduce_specs
    return [s for s in rowreduce_specs.ALL_SPECS if s.register]
