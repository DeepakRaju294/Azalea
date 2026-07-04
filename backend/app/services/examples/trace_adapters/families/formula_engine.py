"""T6 Formula Engine (SPEC_IMPLEMENTATION_CHECKPOINTS CP12a) — the DECLARATIVE type template for formula
plug-in concepts (given values -> substitute into the governing equation(s) -> result WITH UNITS).

The B-catalog's non-CS domains (statistics, physics mechanics + circuits, chemistry, finance, geometry) are
overwhelmingly this ONE shape. Rather than hand-code a class per concept (KinematicsAdapter ~150 lines), a
concept is now a `FormulaSpec` — a data row of {givens (+units+ranges), outputs (formula+equation+stage),
conventions, optional cases}. `formula_decl(spec)` turns it into an `AdapterDecl` that hydrates into a normal
`FamilyAdapterBase`, so routing / the pipeline / the contract tests consume it unchanged.

The engine computes the REAL arithmetic in `reference()`, so a worked example can never state a wrong number
or unit; its correctness is checked independently by the type gate (`test_formula_engine`), which re-evaluates
each output and compares — the T6 analogue of `test_code_reproduces_trace` (gate-passing != authored-correct).
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

from ...trace_contract import ContractTrace, Step, fact
from ..decl import AdapterDecl
from ..example_spec import ExampleSpec, InstanceShape, StageSpec

# Formulas are AUTHORED by us (never user input), but eval with no builtins + a whitelisted math namespace so a
# typo can't reach the interpreter. Extend as new concepts need functions.
_SAFE_NS = {k: getattr(math, k) for k in
            ("sqrt", "pi", "e", "sin", "cos", "tan", "asin", "acos", "atan", "log", "log10", "exp",
             "floor", "ceil", "fabs", "factorial", "radians", "degrees")}
_SAFE_NS["abs"] = abs


def _eval(expr: str, values: dict[str, Any]) -> float:
    return float(eval(expr, {"__builtins__": {}}, {**_SAFE_NS, **values}))  # noqa: S307 — authored expr, sealed ns


def _num(x: float) -> Any:
    """Integers stay ints; otherwise round to 2 dp (money/science convention). Keeps prose clean."""
    xf = float(x)
    return int(xf) if xf.is_integer() else round(xf, 2)


def _ints(*parts: Any) -> list[int]:
    """Integers appearing in a step's OWN verified prose -> `allowed_values` (faithful card passes; an invented
    number is caught). Same helper the hand-written computation adapters use."""
    found: set[int] = set()
    for m in re.findall(r"-?\d+", " ".join(str(p) for p in parts)):
        found.add(int(m)); found.add(abs(int(m)))
    return sorted(found)


def _substitute(rhs: str, values: dict[str, Any]) -> str:
    """Show the equation with each variable replaced by its value: `u + a*t` -> `5 + 3*2`. Longest names first
    so a substring name can't be partially replaced."""
    out = rhs
    for name in sorted(values, key=len, reverse=True):
        out = re.sub(rf"\b{re.escape(name)}\b", str(_num(values[name])), out)
    return out


@dataclass
class Given:
    name: str                                   # variable symbol used in the formulas
    unit: str = ""                              # display unit ("m/s", "$", "" for dimensionless)
    lo: int = 1
    hi: int = 10
    integer: bool = True                        # sampled as an int (most school formulas); False -> 1-dp float


@dataclass
class Output:
    name: str                                   # symbol for the computed quantity
    equation: str                               # DISPLAY form incl. LHS, human powers: "v = u + a*t", "s = u*t + (a*t^2)/2"
    expr: str                                   # EVAL form of the RHS (Python), "**" powers: "u + a*t", "u*t + (a*t**2)/2"
    unit: str = ""
    stage_id: str = ""                          # Step.operation (defaults to compute_<name>)
    teaching_focus: str = ""
    fact_kind: str = ""                         # required_fact kind (defaults to <name>)

    def stage(self) -> str:
        return self.stage_id or f"compute_{self.name}"


@dataclass
class Case:
    id: str
    when: Callable[[dict[str, Any]], bool]


@dataclass
class FormulaSpec:
    slug: str
    title: str                                  # short concept label ("kinematics with constant acceleration")
    problem_template: str                       # .format(**givens) -> the problem statement
    givens: list[Given]
    outputs: list[Output]
    conventions: dict[str, str] = field(default_factory=dict)
    cases: list[Case] = field(default_factory=list)          # optional coverage cases keyed on the givens
    must_avoid: list[str] = field(default_factory=list)
    n_candidates: int = 80
    label_convention: str = "ints"

    # ------- derived -------------------------------------------------------------------------------
    def compute(self, givens: dict[str, Any]) -> dict[str, Any]:
        """The real arithmetic: each output in order, later outputs may read earlier ones."""
        env = dict(givens)
        for o in self.outputs:
            env[o.name] = _num(_eval(o.expr, env))
        return {o.name: env[o.name] for o in self.outputs}


# --- generic contract methods (bound onto the hydrated adapter; read self._formula_spec) ---------------
def _candidates(self, seed: int) -> Iterable[dict[str, Any]]:
    spec: FormulaSpec = self._formula_spec
    rng = random.Random(seed)
    for i in range(spec.n_candidates):
        row: dict[str, Any] = {}
        for g in spec.givens:
            row[g.name] = rng.randint(g.lo, g.hi) if g.integer else round(rng.uniform(g.lo, g.hi), 1)
        row["_id"] = f"{spec.slug}_v1_case_{i}"
        yield row


def _is_teaching_trace(self, trace: ContractTrace) -> bool:
    spec: FormulaSpec = self._formula_spec
    ev = trace.case_evidence
    return (len(trace.steps) == 1 + len(spec.outputs)
            and all(ev.get(o.stage()) for o in spec.outputs))


def _reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
               attempt: int = 1, seed: int = 0) -> ContractTrace:
    spec: FormulaSpec = self._formula_spec
    givens = {g.name: example_input[g.name] for g in spec.givens}

    knowns_str = ", ".join(f"{g.name} = {_num(givens[g.name])}{(' ' + g.unit) if g.unit else ''}"
                           for g in spec.givens)
    d1 = knowns_str
    r1 = f"the given quantities are {knowns_str}"
    e1 = f"Knowns: {knowns_str}."
    f1 = [fact("known", f"{g.name} = {_num(givens[g.name])}") for g in spec.givens]
    steps = [Step(id="s1", operation="identify_knowns", prior_state={"problem": spec.title},
                  state_after=dict(givens), inputs=dict(givens), decision=d1, reason=r1,
                  visual_state={"kind": "equation", **givens}, expected_visible_result=e1,
                  facts={"allowed_values": _ints(d1, r1, e1), "required_facts": f1, "forbidden_claims": []})]

    env = dict(givens)
    prior = dict(givens)
    answer: dict[str, Any] = {}
    for k, o in enumerate(spec.outputs, start=2):
        val = _num(_eval(o.expr, env))
        env[o.name] = val
        answer[o.name] = val
        rhs = o.equation.split("=", 1)[1].strip()
        subst = _substitute(rhs, {**givens, **{n: env[n] for n in env}})
        unit = (" " + o.unit) if o.unit else ""
        d = f"{o.name} = {val}{unit}"
        r = f"{o.equation} = {subst} = {val}{unit}"
        e = f"{o.teaching_focus or o.name}: {o.equation} = {val}{unit}."
        fk = o.fact_kind or o.name
        after = dict(prior); after[o.name] = val
        steps.append(Step(id=f"s{k}", operation=o.stage(), prior_state=dict(prior), state_after=after,
                          inputs={o.name: val}, decision=d, reason=r,
                          visual_state={"kind": "equation", o.name: val}, expected_visible_result=e,
                          facts={"allowed_values": _ints(d, r, e, *answer.values()),
                                 "required_facts": [fact(fk, f"{o.name} = {val}")], "forbidden_claims": []}))
        prior = after

    # coverage case for this instance (optional)
    case_id = next((c.id for c in spec.cases if c.when(givens)), None)
    required = ["identify_knowns"] + [o.stage() for o in spec.outputs] + ["completion"]
    evidence: dict[str, list[str]] = {"identify_knowns": ["s1"], "completion": [f"s{len(steps)}"]}
    for k, o in enumerate(spec.outputs, start=2):
        evidence[o.stage()] = [f"s{k}"]
    if case_id:
        evidence[case_id] = ["s1"]

    inv = [{"id": f"{spec.slug}_hold", "scope": "final_only",
            "statement": "; ".join(o.equation for o in spec.outputs)}]
    return ContractTrace(
        problem=spec.problem_template.format(**{k: _num(v) for k, v in givens.items()}),
        conventions=dict(spec.conventions), initial_state={"problem": spec.title},
        final_answer=dict(answer), steps=steps, invariants=inv,
        required_cases=list(required), case_evidence=evidence,
        provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                    attempt=attempt))


def _states_equivalent(self, a, b):
    ka, kb = a or {}, b or {}
    return all(str(ka.get(k)) == str(kb.get(k)) for k in (set(ka) | set(kb)))


def _final_answer_entails(self, state, answer):
    st, an = state or {}, answer or {}
    return all(str(st.get(k)) == str(v) for k, v in an.items())


def _invariant_holds(self, inv, state):
    spec: FormulaSpec = self._formula_spec
    if inv.get("id") != f"{spec.slug}_hold":
        return True
    st = state or {}
    if any(st.get(g.name) is None for g in spec.givens):
        return True
    env = {g.name: st[g.name] for g in spec.givens}
    for o in spec.outputs:
        if st.get(o.name) is None:
            return True
        try:
            want = _num(_eval(o.expr, env))            # round the SAME way reference() did before comparing
        except Exception:  # noqa: BLE001
            return True
        if abs(float(st[o.name]) - float(want)) > 1e-6:
            return False
        env[o.name] = st[o.name]
    return True


def _validate_step_shape(self, step):
    spec: FormulaSpec = self._formula_spec
    allowed = {"identify_knowns", *(o.stage() for o in spec.outputs)}
    return [] if step.operation in allowed else [f"unexpected operation {step.operation!r}"]


def _validate_prose_claims(self, card, step):
    prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                      str(card.get("result", ""))]).lower()
    val = (step.inputs or {}).get(step.operation.replace("compute_", ""))
    if step.operation.startswith("compute_") and val is not None:
        return [] if str(val) in prose else [(f"{step.operation}_not_stated", str(val))]
    return []


_METHODS = {
    "candidates": _candidates, "is_teaching_trace": _is_teaching_trace, "reference": _reference,
    "states_equivalent": _states_equivalent, "final_answer_entails": _final_answer_entails,
    "invariant_holds": _invariant_holds, "validate_step_shape": _validate_step_shape,
    "validate_prose_claims": _validate_prose_claims,
}


def build_example_spec(spec: FormulaSpec) -> ExampleSpec:
    stages: dict[str, StageSpec] = {
        "identify_knowns": StageSpec(
            "identify_knowns", "list the given quantities with units", cardinality="exactly_once",
            teaching_focus="separate the knowns from the unknowns",
            contains={"read_quantities": "required"}, state_effects=["the givens are named with units"])}
    for o in spec.outputs:
        stages[o.stage()] = StageSpec(
            o.stage(), f"apply {o.equation}", cardinality="exactly_once",
            teaching_focus=o.teaching_focus or f"the equation for {o.name}",
            contains={"substitute": "required", "evaluate": "required"},
            state_effects=[f"{o.name} is known"])
    structure = " ".join(["identify_knowns", *(o.stage() for o in spec.outputs)])
    return ExampleSpec(
        input=InstanceShape("integers", count=(len(spec.givens), len(spec.givens)),
                            structure=[g.name for g in spec.givens]),
        stages=stages, structure=structure,
        must_exercise=["identify_knowns", *(o.stage() for o in spec.outputs), "completion"],
        must_cover=[c.id for c in spec.cases], must_avoid=list(spec.must_avoid),
        terminal="every requested quantity is stated with units",
        output_shape=", ".join(f"{o.name} ({o.unit})" if o.unit else o.name for o in spec.outputs))


def formula_decl(spec: FormulaSpec, *, routing: Optional[dict[str, Any]] = None) -> AdapterDecl:
    """A formula concept -> a hydratable AdapterDecl. `provides_narration=True` (the step prose is
    learner-quality by construction, so the walkthrough ships from the trace, like the other T6 adapters)."""
    return AdapterDecl(
        slug=spec.slug, type="T6", family=routing.get("family", "formula") if routing else "formula",
        example_spec=build_example_spec(spec), methods=dict(_METHODS),
        label_convention=spec.label_convention, routing=routing or {},
        class_attrs={"_formula_spec": spec, "provides_narration": True})
