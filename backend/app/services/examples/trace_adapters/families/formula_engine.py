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
def _median(xs: list) -> float:
    s = sorted(xs); n = len(s); m = n // 2
    return float(s[m]) if n % 2 else (s[m - 1] + s[m]) / 2


_SAFE_NS = {k: getattr(math, k) for k in
            ("sqrt", "pi", "e", "sin", "cos", "tan", "asin", "acos", "atan", "log", "log10", "exp",
             "floor", "ceil", "fabs", "factorial", "radians", "degrees")}
_SAFE_NS.update({"abs": abs, "sum": sum, "len": len, "min": min, "max": max, "sorted": sorted,
                 "median": _median, "zip": zip})


def _eval(expr: str, values: dict[str, Any]) -> float:
    # Names go in GLOBALS (not locals) so a generator expression's free vars (e.g. `mean` in
    # sum((x-mean)**2 for x in xs)) resolve — a comprehension's inner scope can't read eval's locals dict.
    return float(eval(expr, {"__builtins__": {}, **_SAFE_NS, **values}))  # noqa: S307 — authored expr, sealed ns


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


def _apply_display_names(text: str, names: dict[str, str]) -> str:
    """Render eval identifiers as textbook notation for the learner (`P_A_given_B1` -> `P(A|B1)`). Longest
    first so a shorter name can't clobber part of a longer one. Values (already substituted) are untouched."""
    if not names:
        return text
    for k in sorted(names, key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(k)}\b", names[k], text)
    return text


@dataclass
class Given:
    name: str                                   # variable symbol used in the formulas
    unit: str = ""                              # display unit ("m/s", "$", "" for dimensionless)
    lo: int = 1
    hi: int = 10
    integer: bool = True                        # sampled as an int (most school formulas); False -> 1-dp float


@dataclass
class Dataset:
    """A LIST-valued given (statistics): the concept's input is a dataset, not scalar quantities. Output exprs
    reference it by `name` plus the derived `n` (count), and may use sum/len/min/max/sorted/median."""
    name: str = "xs"
    size_lo: int = 4
    size_hi: int = 7
    val_lo: int = 1
    val_hi: int = 20
    unit: str = ""


@dataclass
class Output:
    name: str                                   # symbol for the computed quantity
    equation: str                               # DISPLAY form incl. LHS, human powers: "v = u + a*t", "s = u*t + (a*t^2)/2"
    expr: str                                   # EVAL form of the RHS (Python), "**" powers: "u + a*t", "u*t + (a*t**2)/2"
    unit: str = ""
    stage_id: str = ""                          # Step.operation (defaults to compute_<name>)
    teaching_focus: str = ""
    fact_kind: str = ""                         # required_fact kind (defaults to <name>)
    # DISPLAY intermediates (list concepts): (token, expr) pairs computed + literal-substituted into `equation`
    # for the "= …" step, so "mean = Σx / n" shows "= 25 / 5". Empty -> scalar var substitution is used instead.
    show: list = field(default_factory=list)

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
    dataset: Optional[Dataset] = None           # set for list-input (statistics) concepts; givens then usually []
    dataset2: Optional[Dataset] = None          # a SECOND aligned list (paired data: weighted mean, covariance)
    constants: dict[str, float] = field(default_factory=dict)   # named constants merged into env (e.g. g=9.8)
    conventions: dict[str, str] = field(default_factory=dict)
    cases: list[Case] = field(default_factory=list)          # optional coverage cases keyed on the givens
    must_avoid: list[str] = field(default_factory=list)
    n_candidates: int = 80
    label_convention: str = "ints"
    # --- registration metadata (so a spec auto-wires its manifest + routing; adding a concept = one edit) ---
    family: str = "formula"                     # manifest family / domain (physics, finance, chemistry, ...)
    aliases: list[str] = field(default_factory=list)         # routing `any` substrings (title -> this adapter)
    not_aliases: list[str] = field(default_factory=list)     # routing `not` guards (blocking substrings)
    priority: int = 50                          # routing precedence (higher wins on overlap)
    register: bool = True                       # False = gate-only (e.g. a migration proof), not a live adapter
    display_names: dict[str, str] = field(default_factory=dict)   # eval id -> textbook label in learner prose

    # ------- derived -------------------------------------------------------------------------------
    def base_env(self, example_input: dict[str, Any]) -> dict[str, Any]:
        """The starting evaluation environment for an instance: scalar givens, or the dataset + its count `n`,
        plus any named constants (g, ...)."""
        if self.dataset is not None:
            data = list(example_input[self.dataset.name])
            env = {self.dataset.name: data, "n": len(data), **self.constants}
            if self.dataset2 is not None:
                env[self.dataset2.name] = list(example_input[self.dataset2.name])
            return env
        return {**{g.name: example_input[g.name] for g in self.givens}, **self.constants}

    def compute(self, example_input: dict[str, Any]) -> dict[str, Any]:
        """The real arithmetic: each output in order, later outputs may read earlier ones."""
        env = self.base_env(example_input)
        for o in self.outputs:
            env[o.name] = _num(_eval(o.expr, env))
        return {o.name: env[o.name] for o in self.outputs}


# --- generic contract methods (bound onto the hydrated adapter; read self._formula_spec) ---------------
def _candidates(self, seed: int) -> Iterable[dict[str, Any]]:
    spec: FormulaSpec = self._formula_spec
    rng = random.Random(seed)
    for i in range(spec.n_candidates):
        row: dict[str, Any] = {}
        if spec.dataset is not None:
            ds = spec.dataset
            size = rng.randint(ds.size_lo, ds.size_hi)
            row[ds.name] = [rng.randint(ds.val_lo, ds.val_hi) for _ in range(size)]
            if spec.dataset2 is not None:                    # a paired list of the SAME length
                d2 = spec.dataset2
                row[d2.name] = [rng.randint(d2.val_lo, d2.val_hi) for _ in range(size)]
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
    env = spec.base_env(example_input)                       # scalar givens OR {dataset, n}
    state0 = dict(env)                                       # the knowns that seed the trace state

    if spec.dataset is not None:
        ds = spec.dataset
        data = env[ds.name]
        du = (" " + ds.unit) if ds.unit else ""
        knowns_str = f"{ds.name} = {data}{du} (n = {env['n']})"
        if spec.dataset2 is not None:
            knowns_str += f", {spec.dataset2.name} = {env[spec.dataset2.name]}"
        f1 = [fact("known", f"{ds.name} has {env['n']} values")]
    else:
        knowns_str = ", ".join(f"{g.name} = {_num(env[g.name])}{(' ' + g.unit) if g.unit else ''}"
                               for g in spec.givens)
        f1 = [fact("known", _apply_display_names(f"{g.name} = {_num(env[g.name])}", spec.display_names))
              for g in spec.givens]
    knowns_str = _apply_display_names(knowns_str, spec.display_names)     # textbook notation for the learner
    d1 = knowns_str
    r1 = f"the given data is {knowns_str}" if spec.dataset is not None else f"the given quantities are {knowns_str}"
    e1 = f"Knowns: {knowns_str}."
    steps = [Step(id="s1", operation="identify_knowns", prior_state={"problem": spec.title},
                  state_after=dict(state0), inputs=dict(state0), decision=d1, reason=r1,
                  visual_state={"kind": "equation", **{k: v for k, v in state0.items() if not isinstance(v, list)}},
                  expected_visible_result=e1,
                  facts={"allowed_values": _ints(d1, r1, e1), "required_facts": f1, "forbidden_claims": []})]

    prior = dict(state0)
    answer: dict[str, Any] = {}
    for k, o in enumerate(spec.outputs, start=2):
        val = _num(_eval(o.expr, env))
        # Build the substituted display BEFORE binding o.name into env, so an output named like a namespace
        # function (e.g. `median`) doesn't shadow that function inside its own show-token exprs.
        rhs = o.equation.split("=", 1)[1].strip()
        if o.show:                                          # list concepts: literal-substitute named intermediates
            subst = rhs
            for tok, expr in o.show:
                subst = subst.replace(tok, str(_num(_eval(expr, env))))
        else:                                               # scalar concepts: substitute the variable values
            subst = _substitute(rhs, {n: env[n] for n in env if not isinstance(env[n], list)})
        env[o.name] = val
        answer[o.name] = val
        unit = (" " + o.unit) if o.unit else ""
        d = _apply_display_names(f"{o.name} = {val}{unit}", spec.display_names)
        r = _apply_display_names(f"{o.equation} = {subst} = {val}{unit}", spec.display_names)
        e = _apply_display_names(f"{o.teaching_focus or o.name}: {o.equation} = {val}{unit}.", spec.display_names)
        fk = o.fact_kind or o.name
        after = dict(prior); after[o.name] = val
        steps.append(Step(id=f"s{k}", operation=o.stage(), prior_state=dict(prior), state_after=after,
                          inputs={o.name: val}, decision=d, reason=r,
                          visual_state={"kind": "equation", o.name: val}, expected_visible_result=e,
                          facts={"allowed_values": _ints(d, r, e, *answer.values()),
                                 "required_facts": [fact(fk, _apply_display_names(f"{o.name} = {val}",
                                                                                 spec.display_names))],
                                 "forbidden_claims": []}))
        prior = after

    # coverage case for this instance (optional; predicate reads the knowns env)
    case_id = next((c.id for c in spec.cases if c.when(state0)), None)
    required = ["identify_knowns"] + [o.stage() for o in spec.outputs] + ["completion"]
    evidence: dict[str, list[str]] = {"identify_knowns": ["s1"], "completion": [f"s{len(steps)}"]}
    for k, o in enumerate(spec.outputs, start=2):
        evidence[o.stage()] = [f"s{k}"]
    if case_id:
        evidence[case_id] = ["s1"]

    inv = [{"id": f"{spec.slug}_hold", "scope": "final_only",
            "statement": "; ".join(o.equation for o in spec.outputs)}]
    fmt_vals = {k: (v if isinstance(v, list) else _num(v)) for k, v in state0.items()}
    return ContractTrace(
        problem=spec.problem_template.format(**fmt_vals),
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
    keys = [spec.dataset.name] if spec.dataset is not None else [g.name for g in spec.givens]
    if any(st.get(k) is None for k in keys):
        return True
    env = {k: st[k] for k in keys}
    if spec.dataset is not None:
        env["n"] = len(st[spec.dataset.name])
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
    if spec.dataset is not None:
        in_shape = InstanceShape("integers", count=(spec.dataset.size_lo, spec.dataset.size_hi),
                                 structure=[spec.dataset.name])
    else:
        in_shape = InstanceShape("integers", count=(len(spec.givens), len(spec.givens)),
                                 structure=[g.name for g in spec.givens])
    return ExampleSpec(
        input=in_shape,
        stages=stages, structure=structure,
        must_exercise=["identify_knowns", *(o.stage() for o in spec.outputs), "completion"],
        must_cover=[c.id for c in spec.cases], must_avoid=list(spec.must_avoid),
        terminal="every requested quantity is stated with units",
        output_shape=", ".join(f"{o.name} ({o.unit})" if o.unit else o.name for o in spec.outputs))


def formula_decl(spec: FormulaSpec, *, routing: Optional[dict[str, Any]] = None) -> AdapterDecl:
    """A formula concept -> a hydratable AdapterDecl. `provides_narration=True` (the step prose is
    learner-quality by construction, so the walkthrough ships from the trace, like the other T6 adapters)."""
    return AdapterDecl(
        slug=spec.slug, type="T6", family=(routing or {}).get("family", spec.family),
        example_spec=build_example_spec(spec), methods=dict(_METHODS),
        label_convention=spec.label_convention, routing=routing or routing_rule(spec),
        class_attrs={"_formula_spec": spec, "provides_narration": True})


# --- auto-registration: a spec carries everything its manifest entry + routing rule need, so the registry,
# manifest, and routing table are all DERIVED from ALL_SPECS (single source of truth; no per-row hand editing) ---
def manifest_entry(spec: FormulaSpec) -> dict[str, Any]:
    return {"type": "T6", "family": spec.family, "status": "experimental",
            "verification_level": "trace_verified", "coding": False, "canonical_solution": None,
            "routing_aliases": list(spec.aliases), "negative_guards": list(spec.not_aliases), "fixtures": []}


def routing_rule(spec: FormulaSpec) -> dict[str, Any]:
    rule: dict[str, Any] = {"any": list(spec.aliases), "priority": spec.priority}
    if spec.not_aliases:
        rule["not"] = list(spec.not_aliases)
    return rule


def registered_specs() -> list[FormulaSpec]:
    """The specs that become LIVE adapters (register=True). Imported lazily by manifest/type modules."""
    from . import formula_specs
    return [s for s in formula_specs.ALL_SPECS if s.register]
