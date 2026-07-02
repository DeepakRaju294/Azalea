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
    # §7.0 four-layer model: a VERIFIED SEMANTIC transition may summarize a CONTIGUOUS range of RAW execution
    # events (e.g. a Floyd-Warshall k-layer folds ~V² cell comparisons). When it does, it names that raw range
    # so the chain card -> checkpoint -> semantic step -> raw execution stays fully traceable. None = the step
    # IS one raw event (no summarization).
    raw_event_start: Optional[int] = None
    raw_event_end: Optional[int] = None


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


@dataclass(frozen=True)
class TeachingValidationContract:
    """CP4 / spec §4.0 — the DECLARED hard/soft boundary for teaching validation, in ONE place instead of a
    severity hard-coded at each violation site. A HARD code is a truth contradiction that BLOCKS shipping (a
    wrong selected edge/node/value, a wrong answer, an inverted decision, an invented/absent required step); a
    SOFT/advisory code is imperfect-but-not-wrong (a paraphrased fact, bland wording) and never blocks alone."""
    hard_codes: frozenset[str]
    soft_codes: frozenset[str] = frozenset()

    def is_hard(self, violation: "ProseViolation") -> bool:
        if violation.code in self.hard_codes:
            return True
        if violation.code in self.soft_codes:
            return False
        return violation.severity == "hard"          # fallback for a code the contract doesn't name

    def partition(self, violations: list["ProseViolation"]) -> tuple[list["ProseViolation"], list["ProseViolation"]]:
        hard = [v for v in violations if self.is_hard(v)]
        soft = [v for v in violations if not self.is_hard(v)]
        return hard, soft


# The default teaching-validation contract (CP4 boundary). HARD = contradicts the verified trace; SOFT = merely
# imperfect. Adapters/pipelines can pass a stricter contract; this preserves prior behavior by default.
DEFAULT_TEACHING_VALIDATION = TeachingValidationContract(
    hard_codes=frozenset({
        "value_not_allowed",        # a number not in the verified vocabulary (wrong edge/node/value)
        "decision_contradiction",   # prose asserts the OPPOSITE of the verified decision (accept vs skip)
        "mislabeled_value",         # a named quantity stated with the WRONG value (typed claim ledger, §7)
        "forbidden_claim",          # a claim the adapter declared must never appear
        "wrong_selected", "wrong_final_answer", "invented_transition", "missing_terminal",
    }),
    soft_codes=frozenset({
        "missing_fact",             # a required fact paraphrased/omitted — advisory, not a contradiction
        "bland", "repetitive", "value_in_harmless_context",
    }),
)


def hard_prose_violations(
    violations: list[ProseViolation],
    contract: TeachingValidationContract = DEFAULT_TEACHING_VALIDATION,
) -> list[ProseViolation]:
    """The blocking subset (§12b / CP4): the codes the TeachingValidationContract declares HARD (truth
    contradictions). Advisory codes (missing/soft) are logged, not withheld, in Phase 1. Backward-compatible —
    the default contract maps the previous per-violation severities (value/decision hard, missing_fact soft)."""
    return contract.partition(violations)[0]


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
    # §7.0 raw-provenance: a step that summarizes raw events must name a well-formed range, and the ranges of
    # summarizing steps must be contiguous + ordered (a semantic transition may summarize only a CONTIGUOUS,
    # replayable raw range — never non-contiguous or unrelated behaviour).
    prev_end: Optional[int] = None
    for s in steps:
        rs, re_ = s.raw_event_start, s.raw_event_end
        if (rs is None) != (re_ is None):
            errs.append(f"{s.id}: raw_event range half-declared (need both start and end)")
        elif rs is not None:
            if re_ < rs:
                errs.append(f"{s.id}: raw_event_end < raw_event_start")
            elif prev_end is not None and rs != prev_end + 1:
                errs.append(f"{s.id}: raw_event range not contiguous with previous step")
            prev_end = re_
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


def fact(predicate: str, text: Any, value: Any = None) -> dict[str, Any]:
    """A STRUCTURED required-fact (C1 item 12 / spec §2.2): a predicate + the surface `text` that must appear
    in the prose, optionally the asserted `value`. A JSON-safe dict that replaces a bare string, so a fact is
    checkable structure (predicate/value), not just a substring. `_fact_text` reads its surface form."""
    f: dict[str, Any] = {"predicate": predicate, "text": str(text)}
    if value is not None:
        f["value"] = value
    return f


def _fact_text(f: Any) -> str:
    """The surface phrase of a required-fact — the `text` field of a structured fact, else the value itself
    (back-compatible with the bare-string facts the LLM path still emits)."""
    return f["text"] if isinstance(f, dict) and "text" in f else str(f)


def _states(prose: str, fact: Any) -> bool:
    """The fact phrase appears CONTIGUOUSLY in the (whitespace-normalized) prose — so 'visit' does not
    match 'visited' and tokens must actually be adjacent, not merely both present somewhere."""
    return re.sub(r"\s+", " ", _fact_text(fact).lower()).strip() in prose


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
        # TYPED claim ledger (§7): a named derived/output quantity must be stated with ITS value, not another
        # category's number. Opt-in — only steps that declare `facts["claims"]` (computation adapters).
        ledger = facts.get("claims")
        if isinstance(ledger, dict):
            out += validate_claim_ledger(prose, ledger, i, step.id)
        # adapter-specific claims are contradictions (wrong node / decision / membership) -> hard
        out += [ProseViolation(code, detail, i, step.id)
                for code, detail in adapter.validate_prose_claims(card, step)]
    return out


def claim_ledger(*, inputs: dict[str, Any] | None = None, constants: dict[str, Any] | None = None,
                 derived: dict[str, Any] | None = None, outputs: dict[str, Any] | None = None,
                 units: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """A TYPED claim ledger (ADAPTER_DEVELOPMENT_SPEC §7) — the values a step may state, categorized by ROLE
    (input · formula constant · derived intermediate · expected output · unit). Replaces a flat numeric
    allowlist as the primary truth model for computation adapters: a number is not merely 'allowed', it is
    allowed AS a specific quantity, so a formula constant can't be passed off as the answer."""
    return {"inputs": dict(inputs or {}), "constants": dict(constants or {}),
            "derived": dict(derived or {}), "outputs": dict(outputs or {}), "units": dict(units or {})}


def _claim_value(v: Any) -> str:
    m = re.search(r"-?\d+(?:\.\d+)?", str(v if not isinstance(v, (list, tuple)) else (v[0] if v else "")))
    return m.group() if m else str(v).strip().lower()


def validate_claim_ledger(prose: str, ledger: dict[str, dict[str, Any]], card_index: int,
                          step_id: str) -> list[ProseViolation]:
    """Category-aware guard: a claim that NAMES a derived/output quantity with a copula ('D = 4', 'the roots
    are …') must state THAT quantity's value. Conservative — it only fires on an explicit `name <copula>
    number`, so faithful prose is never flagged; it CATCHES the specific danger a flat allowlist misses
    ('the discriminant is 4' when D is 1 and 4 is only the formula constant)."""
    out: list[ProseViolation] = []
    low = str(prose).lower()
    checkable = {**(ledger.get("derived") or {}), **(ledger.get("outputs") or {})}
    for name, val in checkable.items():
        expected = _claim_value(val)
        pat = re.compile(re.escape(str(name).lower()) + r"\s*(?:is|are|=|equals|:)\s*(-?\d+(?:\.\d+)?)")
        m = pat.search(low)
        if m and m.group(1) != expected:
            out.append(ProseViolation("mislabeled_value",
                                      f"{name} stated as {m.group(1)}, should be {val}", card_index, step_id))
    return out


def coverage_complete(cards: list[dict[str, Any]], trace: ContractTrace, adapter: Any = None, *,
                      checkpoints: Optional[list[Any]] = None,
                      contract: TeachingValidationContract = DEFAULT_TEACHING_VALIDATION) -> tuple[bool, str]:
    """CP3 — is a card set (possibly a DIFFERENT count than the trace's step count) acceptable? True ONLY when
    coverage is complete: every required transition rendered, the terminal transition rendered, no card cites
    an unknown step id, and (when an adapter is given) no HARD prose contradiction. A count != #steps is fine
    iff this holds; a missing required case, an unrendered terminal, a bogus id, or a wrong claim is not.
    Returns (ok, reason). This is the acceptance predicate that lets `count_mismatch` be coverage-based.

    When `checkpoints` is supplied (the adapter's `teaching_checkpoints`), it ALSO enforces the frozen
    checkpoint contract (§CP3): every artifact cites exactly one EXISTING `checkpoint_id`, every REQUIRED
    checkpoint (its source range holds a required transition) is rendered, and the terminal checkpoint is
    rendered. Transition-level checks stay the underlying semantic proof; the checkpoint checks are additive."""
    valid_ids = {s.id for s in trace.steps}
    rendered: set[str] = set()
    for c in cards:
        for sid in (c.get("trace_step_ids") or []):
            if sid not in valid_ids:
                return False, f"unknown_trace_id:{sid}"
            rendered.add(sid)
    evidence = getattr(trace, "case_evidence", {}) or {}
    for rc in getattr(trace, "required_cases", []) or []:
        if not (set(evidence.get(rc, [])) & rendered):
            return False, f"missing_required_transition:{rc}"
    if trace.steps and trace.steps[-1].id not in rendered:
        return False, "terminal_not_rendered"
    if checkpoints is not None:
        cp_ids = {cp.checkpoint_id for cp in checkpoints}
        cited: set[str] = set()
        for c in cards:
            cid = c.get("checkpoint_id")
            if not cid:
                return False, "artifact_without_checkpoint"
            if cid not in cp_ids:
                return False, f"unknown_checkpoint:{cid}"
            cited.add(cid)
        required_steps = {sid for ids in evidence.values() for sid in ids}
        for cp in checkpoints:
            src = set(getattr(cp, "source_step_ids", []) or [])
            if (src & required_steps) and cp.checkpoint_id not in cited:
                return False, f"missing_required_checkpoint:{cp.checkpoint_id}"
        terminal_id = trace.steps[-1].id if trace.steps else None
        terminal_cps = {cp.checkpoint_id for cp in checkpoints
                        if terminal_id in (getattr(cp, "source_step_ids", []) or [])}
        if terminal_cps and not (terminal_cps & cited):
            return False, "terminal_checkpoint_not_rendered"
    if adapter is not None:
        hard = hard_prose_violations(validate_prose(cards, trace, adapter), contract)
        if hard:
            return False, f"hard_prose:{hard[0].code}"
    return True, ""
