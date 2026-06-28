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
    # §12b severity (WORKED_EXAMPLE_REASONING_SPEC v8): only HARD contradictions block in Phase 1;
    # `missing` (a required fact not stated) and `soft` (vague-but-correct) are advisory.
    severity: str = "hard"   # "hard" | "missing" | "soft"


def hard_prose_violations(violations: list[ProseViolation]) -> list[ProseViolation]:
    """The blocking subset (§12b): contradictions only. Missing/soft are logged, not withheld, in Phase 1."""
    return [v for v in violations if v.severity == "hard"]


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

def validate_fidelity(cards: list[dict[str, Any]], trace: ContractTrace, adapter,
                      *, validate_visual_state: bool = False) -> FidelityResult:
    """Every card's backend-attached prior/result state replays the cited step; the chain is gap-free;
    the endpoint entails the final answer; every required-case step is actually rendered.

    `validate_visual_state` (§12, WORKED_EXAMPLE_REASONING_SPEC v8): Phase 1 passes False — `visual_state`
    is carried as METADATA only; enforcing it before the renderer consumes it (Phase 1.5) would raise
    spurious failures on a field nothing reads yet. Phase 1.5 flips this to True."""
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
        # visual-source fidelity — ENFORCED only in Phase 1.5+ (see docstring)
        if validate_visual_state and cited[-1].visual_state and card.get("visual_state") not in (None, {}) \
                and card.get("visual_state") != cited[-1].visual_state:
            return FidelityResult(False, "visual_mismatch", i, cited[-1].id,
                                  cited[-1].visual_state, card.get("visual_state"))
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
    return re.sub(r"\s+", " ", " ".join(str(p) for p in parts).lower()).strip()


def _states(prose: str, fact: str) -> bool:
    """The fact phrase appears CONTIGUOUSLY in the (whitespace-normalized) prose — so 'visit' does not
    match 'visited' and tokens must actually be adjacent, not merely both present somewhere."""
    return re.sub(r"\s+", " ", str(fact).lower()).strip() in prose


# A1 (STUDY_PATH_CONTENT_SPEC §A1) — decision-contradiction guard. Temporary keyword layer; the durable
# plan is a structured decision/claim check. ACCEPT-family and REJECT-family action verbs; a step whose
# verified `decision` is one family but whose Work/Result asserts the other (un-negated) is a hard
# contradiction (the Step-5 "skip vs accept" bug).
_ACCEPT_VERBS = ("accept", "add", "append", "include", "select", "settle")
_REJECT_VERBS = ("skip", "reject", "discard")
_REJECT_PHRASES = ("already connected", "already linked", "already in the same", "forms a cycle",
                   "form a cycle", "would create a cycle", "creates a cycle")
_NEG = re.compile(r"\b(not|no|never|don't|do not|does not|doesn't|cannot|can't|isn't|won't|avoid|"
                  r"without|wouldn't)\b")


def _asserts(text: str, verbs: tuple[str, ...], phrases: tuple[str, ...] = ()) -> bool:
    """True if `text` asserts one of these action verbs/phrases as a positive claim (no negation within
    the ~5 words before it). The suffix group covers inflections incl. doubled forms (skip -> skipped/
    skipping, add -> added)."""
    for pat in [rf"\b{v}(s|es|ed|ped|ping|ing|d)?\b" for v in verbs] + [re.escape(p) for p in phrases]:
        for m in re.finditer(pat, text):
            window = text[max(0, m.start() - 28):m.start()]
            if not _NEG.search(window):
                return True
    return False


def _decision_contradiction(card: dict[str, Any], step, i: int) -> list[ProseViolation]:
    """Flag a HARD contradiction when the verified `decision` is one family (accept/select vs skip/reject)
    but a Work/Result line asserts ONLY the opposite family. Checked PER LINE: a line that mentions BOTH
    (e.g. "add edge X, unlike edge Y which we skipped") is not a contradiction — it states the real action
    and merely references the other. (Temporary keyword layer; the durable plan is a structured check.)"""
    dec = str(getattr(step, "decision", "") or "").strip().lower()
    accept_like = any(dec.startswith(v) for v in _ACCEPT_VERBS)
    reject_like = any(dec.startswith(v) for v in _REJECT_VERBS)
    if not (accept_like or reject_like):
        return []
    for line in [str(w) for w in (card.get("work") or [])] + [str(card.get("result", ""))]:
        t = re.sub(r"\s+", " ", line.lower())
        if accept_like and _asserts(t, _REJECT_VERBS, _REJECT_PHRASES) and not _asserts(t, _ACCEPT_VERBS):
            return [ProseViolation("decision_contradiction", f"decision={dec!r}; line rejects: {line[:48]!r}", i, step.id)]
        if reject_like and _asserts(t, _ACCEPT_VERBS) and not _asserts(t, _REJECT_VERBS, _REJECT_PHRASES):
            return [ProseViolation("decision_contradiction", f"decision={dec!r}; line accepts: {line[:48]!r}", i, step.id)]
    return []


def validate_prose(cards: list[dict[str, Any]], trace: ContractTrace, adapter,
                   *, code_anchored: bool = False) -> list[ProseViolation]:
    """Generic guard: numbers in the prose must be in `allowed_values`, every `required_fact` must be
    stated, no `forbidden_claim` may appear, the prose must not contradict the step's decision — plus any
    adapter-specific claim checks. Bounded, not a natural-language prover.

    `code_anchored` (A3): for a CODE-anchored worked example the numeric allowlist does NOT apply — the
    allowlist encodes the CONCEPTUAL trace vocabulary (edge weights), but code execution legitimately
    surfaces runtime values outside it (heap start cost 0, indices, accumulated totals). required_facts +
    the decision guard + executable validation (A2) carry the guarantees instead."""
    out: list[ProseViolation] = []
    for i, card in enumerate(cards):
        sids = card.get("trace_step_ids") or []
        step = trace.by_id(sids[0]) if sids else None
        if step is None:
            continue
        prose = _prose_of(card)
        facts = step.facts or {}
        allowed = {str(x) for x in facts.get("allowed_values", [])}
        if allowed and not code_anchored:
            for n in set(re.findall(r"-?\d+", prose)):
                if n not in allowed:
                    out.append(ProseViolation("value_not_allowed", n, i, step.id))
        for f in facts.get("required_facts", []):
            if not _states(prose, f):
                # advisory in Phase 1: a paraphrase/omission is not a contradiction (§12b)
                out.append(ProseViolation("missing_fact", str(f), i, step.id, severity="missing"))
        for c in facts.get("forbidden_claims", []):
            if _states(prose, c):
                out.append(ProseViolation("forbidden_claim", str(c), i, step.id))   # hard (default)
        out += _decision_contradiction(card, step, i)                               # A1 (hard)
        # adapter-specific claims are contradictions (wrong node / decision / membership) -> hard
        out += [ProseViolation(code, detail, i, step.id)
                for code, detail in adapter.validate_prose_claims(card, step)]
    return out
