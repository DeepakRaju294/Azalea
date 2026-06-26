"""Trace-contract core for the worked-example trace pipeline (WORKED_EXAMPLE_REASONING_SPEC.md v7).

Pure and adapter-driven — NO LLM, NO algorithm knowledge lives here. This module owns:
  * the data model (`Step`, `ContractTrace`) and result types,
  * the structural-invariant gate (§5) run before verification,
  * Stage-4 machine-state fidelity replay (§12),
  * Stage-4b prose fidelity guard (§12b),
all expressed against a `TraceAdapter` (trace_adapters/base.py) so every algorithm-specific decision —
state equivalence, invariants, final-answer entailment, prose facts — is delegated. Adding an algorithm
means adding an adapter, not editing this file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class Step:
    id: str
    operation: str
    prior_state: dict[str, Any]
    state_after: dict[str, Any]
    inputs: dict[str, Any] = field(default_factory=dict)
    decision: str = ""
    reason: str = ""
    visual_state: dict[str, Any] = field(default_factory=dict)
    visual_delta: dict[str, Any] = field(default_factory=dict)
    expected_visible_result: str = ""
    facts: dict[str, Any] = field(default_factory=dict)  # allowed_values / required_facts / forbidden_claims


@dataclass(frozen=True)
class ContractTrace:
    problem: str
    conventions: dict[str, Any]
    initial_state: dict[str, Any]
    final_answer: Any
    steps: list[Step]
    invariants: list[dict[str, Any]] = field(default_factory=list)
    required_cases: list[str] = field(default_factory=list)
    case_evidence: dict[str, list[str]] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    solution_text: str = ""

    def by_id(self, sid: str) -> Optional[Step]:
        return next((s for s in self.steps if s.id == sid), None)


@dataclass
class VerifyResult:
    ok: bool
    illegal_step: Optional[dict[str, Any]] = None   # {id, reason}
    errors: list[str] = field(default_factory=list)


@dataclass
class FidelityResult:
    ok: bool
    code: str = ""
    card_index: int = -1
    trace_step_id: str = ""
    expected_state: Any = None
    observed_state: Any = None


@dataclass(frozen=True)
class ProseViolation:
    code: str          # value_not_allowed | missing_fact | forbidden_claim | adapter-specific
    detail: str
    card_index: int
    trace_step_id: str


# --- §5 structural-invariant gate (pre-verification) --------------------------------------------

def structural_invariants(trace: ContractTrace, adapter) -> list[str]:
    """Generic, family-agnostic checks every ContractTrace must pass before it is verified or formatted.
    Uses only the adapter's equivalence / entailment / invariant / step-shape hooks."""
    errs: list[str] = []
    steps = trace.steps
    if not steps:
        return ["trace has no steps"]
    if not adapter.states_equivalent(steps[0].prior_state, trace.initial_state):
        errs.append(f"{steps[0].id}: prior_state != initial_state")
    for prev, cur in zip(steps, steps[1:]):
        if not adapter.states_equivalent(cur.prior_state, prev.state_after):
            errs.append(f"{cur.id}: prior_state != previous state_after (chain gap)")
    if not adapter.final_answer_entails(steps[-1].state_after, trace.final_answer):
        errs.append(f"{steps[-1].id}: last state_after does not entail final_answer")
    for inv in trace.invariants:
        targets = steps if inv.get("scope") == "every_step" else steps[-1:]
        for s in targets:
            if not adapter.invariant_holds(inv, s.state_after):
                errs.append(f"invariant {inv.get('id')!r} fails at {s.id}")
    for case in trace.required_cases:
        ids = trace.case_evidence.get(case)
        if not ids:
            errs.append(f"required case {case!r} has no evidence step ids")
        elif any(trace.by_id(sid) is None for sid in ids):
            errs.append(f"required case {case!r} cites an unknown step id")
    for s in steps:
        errs += [f"{s.id}: {e}" for e in adapter.validate_step_shape(s)]
    return errs


# --- §12 Stage-4 machine-state fidelity ---------------------------------------------------------

def validate_fidelity(cards: list[dict[str, Any]], trace: ContractTrace, adapter) -> FidelityResult:
    """Every card's backend-attached prior/result state replays the cited step; the chain is gap-free;
    the endpoint entails the final answer; every required-case step is actually rendered."""
    for i, card in enumerate(cards):
        sids = card.get("trace_step_ids") or []
        cited = [trace.by_id(s) for s in sids]
        if not cited or any(s is None for s in cited):
            return FidelityResult(False, "missing_step", i, ",".join(sids))
        if not adapter.states_equivalent(card.get("prior_state"), cited[0].prior_state):
            return FidelityResult(False, "prior_mismatch", i, cited[0].id,
                                  cited[0].prior_state, card.get("prior_state"))
        if not adapter.states_equivalent(card.get("result_state"), cited[-1].state_after):
            return FidelityResult(False, "result_mismatch", i, cited[-1].id,
                                  cited[-1].state_after, card.get("result_state"))
    if cards and not adapter.states_equivalent(cards[0].get("prior_state"), trace.initial_state):
        return FidelityResult(False, "chain_start", 0)
    for i, (a, b) in enumerate(zip(cards, cards[1:])):
        if not adapter.states_equivalent(a.get("result_state"), b.get("prior_state")):
            return FidelityResult(False, "chain_break", i + 1)
    if cards and not adapter.final_answer_entails(cards[-1].get("result_state"), trace.final_answer):
        return FidelityResult(False, "endpoint", len(cards) - 1)
    rendered = {sid for c in cards for sid in (c.get("trace_step_ids") or [])}
    for case, ids in trace.case_evidence.items():
        if not all(sid in rendered for sid in ids):
            return FidelityResult(False, "case_not_rendered", -1, case)
    return FidelityResult(True)


# --- §12b Stage-4b prose fidelity (bounded fact-bundle guard) ------------------------------------

def _prose_of(card: dict[str, Any]) -> str:
    parts = [card.get("title", ""), card.get("goal", ""), card.get("reasoning", ""),
             " ".join(card.get("work") or []), card.get("result", "")]
    return " ".join(str(p) for p in parts).lower()


def _states(prose: str, fact: str) -> bool:
    """Lenient: all significant tokens of `fact` appear in `prose` (order-independent)."""
    toks = [t for t in re.findall(r"[a-z0-9]+", str(fact).lower()) if t]
    return all(t in prose for t in toks)


def validate_prose(cards: list[dict[str, Any]], trace: ContractTrace, adapter) -> list[ProseViolation]:
    """Generic guard: numbers in the prose must be in `allowed_values`, every `required_fact` must be
    stated, no `forbidden_claim` may appear — plus any adapter-specific claim checks. Bounded, not a
    natural-language prover."""
    out: list[ProseViolation] = []
    for i, card in enumerate(cards):
        sids = card.get("trace_step_ids") or []
        step = trace.by_id(sids[0]) if sids else None
        if step is None:
            continue
        prose = _prose_of(card)
        facts = step.facts or {}
        allowed = {str(x) for x in facts.get("allowed_values", [])}
        if allowed:
            for n in set(re.findall(r"-?\d+", prose)):
                if n not in allowed:
                    out.append(ProseViolation("value_not_allowed", n, i, step.id))
        for f in facts.get("required_facts", []):
            if not _states(prose, f):
                out.append(ProseViolation("missing_fact", str(f), i, step.id))
        for c in facts.get("forbidden_claims", []):
            if _states(prose, c):
                out.append(ProseViolation("forbidden_claim", str(c), i, step.id))
        out += [ProseViolation(code, detail, i, step.id)
                for code, detail in adapter.validate_prose_claims(card, step)]
    return out
