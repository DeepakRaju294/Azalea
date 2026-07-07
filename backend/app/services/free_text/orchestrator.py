"""Q24 field orchestration (§3/§4) — assemble the full ladder into one FreeTextValidationResult.

Per span: segment → backend route (ownership/requirement) → classify_claim → run the applicable rungs
(L1 scope · L2 transformation · L3 sibling · establishment · L4) → decide. Ship rules (§4):
- a `factual` span ships ONLY when the deterministic resolver marks it established (passing checks is NOT a basis);
  otherwise it is unsupported → soften/withhold. A hard fail (L1/L2/L3/L4-refuted) repairs ×2 then disposes.
- `non_factual_framing` / `prompt` / `deterministic_carried_elsewhere` ship when L1 doesn't hard-fail (L4 n/a or
  no_objection); they never need establishment.
Disposition is by backend `span_requirement`: optional → DELETE, required → WITHHOLD field, essential → WITHHOLD
card. `shadow_validate` computes + logs all of this but leaves the displayed field unchanged; `on_enforced` applies
it. No fallback/legacy-recovery path.
"""
from __future__ import annotations

from dataclasses import dataclass, field as _field
from typing import Callable, Dict, List, Optional, Tuple

from . import (binding as bindmod, classify, establishment as est, evidence as ev,
               l1_scope, l3_sibling, l4_verifier, relations, routing, transformation as xform, validator)
from .validator import (FACTUAL, NON_FACTUAL_FRAMING, PROMPT, SHIP, SOFTEN, WITHHOLD,
                        ACTION_SHIP, ACTION_DELETE, ACTION_WITHHOLD_FIELD, ACTION_WITHHOLD_CARD,
                        SHADOW_VALIDATE, ON_ENFORCED, MAX_REPAIRS)
from .routing import OPTIONAL, REQUIRED, ESSENTIAL, FREE_TEXT, DETERMINISTIC_CARRIED_ELSEWHERE


@dataclass
class ClaimResult:
    claim_id: str
    span_text: str
    claim_class: str
    content_ownership: str
    span_requirement: str
    requirement_source: str
    generator_label_discarded: bool
    l1: Optional[l1_scope.L1Result]
    l2: Optional[xform.TransformationResult]
    l3: Optional[l3_sibling.L3Result]
    establishment: est.ClaimEstablishment
    l4: Optional[l4_verifier.L4Result]
    decision: str                       # ACTION_*
    retry_count: int
    failures: Tuple[str, ...]


@dataclass
class FreeTextValidationResult:
    field: str
    field_text_in: str
    field_text_out: str
    field_decision: str
    mode: str
    claims: List[ClaimResult] = _field(default_factory=list)

    def telemetry(self, *, topic_id: str = "", card_type: str = "") -> List[dict]:
        rows = []
        for c in self.claims:
            stage = c.l2.transformation_failure_stage if c.l2 else None
            op = c.l2.binding.resolved_operation_id if c.l2 else None
            rows.append({
                "topic_id": topic_id, "card_type": card_type, "field": self.field,
                "claim_id": c.claim_id, "claim_class": c.claim_class,
                "content_ownership": c.content_ownership, "span_requirement": c.span_requirement,
                "requirement_source": c.requirement_source,
                "generator_label_discarded": c.generator_label_discarded,
                "l1": c.l1.status if c.l1 else None,
                "l2_verdict": c.l2.verdict if c.l2 else None,
                "transformation_failure_stage": stage, "operation_id": op,
                "l3": c.l3.status if c.l3 else None,
                "establishment": c.establishment.status, "establishment_basis": c.establishment.basis,
                "l4": c.l4.verdict if c.l4 else None,
                "unsupported_reason": c.l4.unsupported_reason if c.l4 else None,
                "action": c.decision, "retry_count": c.retry_count,
                "failures": list(c.failures),
            })
        return rows


@dataclass(frozen=True)
class FieldContext:
    """Backend-supplied validation inputs for a field (all authoritative; none generator-authored)."""
    vocab: Optional[l1_scope.TopicVocabulary] = None
    fact_pack: Optional[ev.FactPack] = None
    sibling_facts: Tuple[l3_sibling.SiblingFact, ...] = ()
    verifier_available: bool = True
    mappings: Optional[Dict[str, routing.RegisteredMapping]] = None
    requirements: Optional[Dict[str, str]] = None
    generator_labels: Optional[Dict[str, dict]] = None
    backend_bindings: Optional[Dict[str, bindmod.BackendBinding]] = None
    allow_metadata_backed: Optional[Dict[str, bool]] = None


def validate_field(
    field_name: str,
    field_text: str,
    ctx: Optional[FieldContext] = None,
    *,
    mode: str = ON_ENFORCED,
    repair_fn: Optional[Callable[[str], Optional[str]]] = None,
) -> FreeTextValidationResult:
    ctx = ctx or FieldContext()
    mappings = ctx.mappings or {}
    requirements = ctx.requirements or {}
    generator_labels = ctx.generator_labels or {}
    backend_bindings = ctx.backend_bindings or {}
    allow_metadata_backed = ctx.allow_metadata_backed or {}

    spans = validator.segment(field_text)
    claims: List[ClaimResult] = []
    deleted: List[validator.ClaimSpan] = []
    withhold_field = False
    withhold_card = False

    for span in spans:
        cid = span.claim_id
        claim_class = classify.classify_claim(span.text)

        mapping = mappings.get(cid)
        if mapping is None and cid in requirements:
            mapping = routing.RegisteredMapping(FREE_TEXT, requirements[cid], routing.CARD_SCHEMA)
        routed = routing.route_span(mapping, generator_label=generator_labels.get(cid))

        cr = _validate_span(
            span, claim_class, routed, ctx,
            backend_binding=backend_bindings.get(cid),
            allow_metadata=allow_metadata_backed.get(cid, False),
            repair_fn=repair_fn,
        )
        claims.append(cr)

        if cr.decision == ACTION_DELETE:
            deleted.append(span)
        elif cr.decision == ACTION_WITHHOLD_FIELD:
            withhold_field = True
        elif cr.decision == ACTION_WITHHOLD_CARD:
            withhold_card = True

    if withhold_card or withhold_field:
        field_decision, enforced = WITHHOLD, ""
    elif deleted:
        field_decision, enforced = SOFTEN, validator._delete_spans(field_text, deleted)
    else:
        field_decision, enforced = SHIP, field_text

    field_out = field_text if mode == SHADOW_VALIDATE else enforced
    return FreeTextValidationResult(field_name, field_text, field_out, field_decision, mode, claims)


def _validate_span(span, claim_class, routed, ctx, *, backend_binding, allow_metadata, repair_fn) -> ClaimResult:
    failures: List[str] = []

    # hard routing failure short-circuits everything → fail closed
    if routed.hard_routing_failure:
        action = ACTION_WITHHOLD_CARD if routed.span_requirement == ESSENTIAL else ACTION_WITHHOLD_FIELD
        return _claim(span, claim_class, routed, None, None, None,
                      est.ClaimEstablishment(est.NOT_ESTABLISHED, est.NONE), None, action, 0,
                      ("hard_routing_failure",))

    # L1 scope (deterministic) — applies to every span, including framing
    l1 = l1_scope.check_scope(span.text, ctx.vocab) if ctx.vocab else None
    l1_hard = l1 is not None and l1.status == l1_scope.FAIL
    if l1_hard:
        failures.append(f"l1_out_of_scope:{','.join(l1.out_of_scope_terms)}")

    # L2 transformation (class-3) — only when the span is a declared transformation
    span_input = bindmod.SpanInput(text=span.text, backend_binding=backend_binding,
                                   allow_metadata_backed=allow_metadata)
    tr = xform.validate_transformation(span_input)
    l2 = tr if tr.binding.is_transformation else None
    l2_refuted = l2 is not None and l2.verdict == xform.VERDICT_REFUTED
    if l2_refuted:
        failures.append(f"l2_transformation:{l2.transformation_failure_stage}")
    l2_proven = l2 is not None and l2.verdict == xform.VERDICT_PASS

    # L3 sibling-trace — only when the span references an example fact
    l3 = l3_sibling.check_sibling_consistency(span.text, ctx.sibling_facts) if ctx.sibling_facts else None
    l3_hard = l3 is not None and l3.status == l3_sibling.FAIL
    if l3_hard:
        failures.append(f"l3_sibling:{','.join(l3.conflicting_facts)}")

    trace_owned = routed.content_ownership in (routing.TRACE_AUTHORITATIVE, routing.TRACE_DERIVABLE)
    establishment = est.resolve_establishment(
        span.text, fact_pack=ctx.fact_pack, l2_proven=l2_proven, trace_owned=trace_owned)

    # framing / prompt / deterministic-carried: no establishment needed; ship unless L1 hard-fails
    non_factual = (claim_class in (NON_FACTUAL_FRAMING, PROMPT)
                   or routed.content_ownership == DETERMINISTIC_CARRIED_ELSEWHERE)

    l4 = None
    hard_fail = l1_hard or l2_refuted or l3_hard

    if non_factual:
        l4 = l4_verifier.verify(span.text, claim_class, fact_pack=ctx.fact_pack,
                                content_ownership=routed.content_ownership,
                                verifier_available=ctx.verifier_available)
        if not hard_fail:
            return _claim(span, claim_class, routed, l1, l2, l3, establishment, l4, ACTION_SHIP, 0, ())
        # framing that violates scope still disposes
        action, retries = _dispose_with_repair(span, routed, ctx, backend_binding, allow_metadata, repair_fn)
        return _claim(span, claim_class, routed, l1, l2, l3, establishment, l4, action, retries, tuple(failures))

    # factual span
    if hard_fail:
        action, retries = _dispose_with_repair(span, routed, ctx, backend_binding, allow_metadata, repair_fn)
        return _claim(span, claim_class, routed, l1, l2, l3, establishment, l4, action, retries, tuple(failures))

    if establishment.status == est.ESTABLISHED:
        return _claim(span, claim_class, routed, l1, l2, l3, establishment, l4, ACTION_SHIP, 0, ())

    # not established, no hard fail → consult L4 (reject/downgrade only; can't establish)
    l4 = l4_verifier.verify(span.text, claim_class, fact_pack=ctx.fact_pack,
                            content_ownership=routed.content_ownership,
                            verifier_available=ctx.verifier_available)
    if l4.verdict == l4_verifier.REFUTED:
        failures.append("l4_refuted")
        action, retries = _dispose_with_repair(span, routed, ctx, backend_binding, allow_metadata, repair_fn)
        return _claim(span, claim_class, routed, l1, l2, l3, establishment, l4, action, retries, tuple(failures))

    # unsupported / unavailable factual assertion → NOT a clean pass; dispose by requirement (no repair)
    failures.append(f"unestablished:{l4.verdict}"
                    + (f":{l4.unsupported_reason}" if l4.unsupported_reason else ""))
    action = _dispose(routed.span_requirement)
    return _claim(span, claim_class, routed, l1, l2, l3, establishment, l4, action, 0, tuple(failures))


def _dispose(requirement: str) -> str:
    if requirement == OPTIONAL:
        return ACTION_DELETE
    if requirement == REQUIRED:
        return ACTION_WITHHOLD_FIELD
    return ACTION_WITHHOLD_CARD


def _dispose_with_repair(span, routed, ctx, backend_binding, allow_metadata, repair_fn):
    """Retry a hard-failed/refuted span up to MAX_REPAIRS; a repaired span must pass L2 AND (if factual) establish."""
    retries = 0
    current = span.text
    while retries < MAX_REPAIRS:
        retries += 1
        new_text = repair_fn(current) if repair_fn else None
        if new_text is None:
            continue
        ri = bindmod.SpanInput(text=new_text, backend_binding=backend_binding, allow_metadata_backed=allow_metadata)
        tr = xform.validate_transformation(ri)
        l2_ok = (not tr.binding.is_transformation) or tr.verdict != xform.VERDICT_REFUTED
        l1_ok = (ctx.vocab is None) or l1_scope.check_scope(new_text, ctx.vocab).status != l1_scope.FAIL
        if l2_ok and l1_ok:
            return ACTION_SHIP, retries
    return _dispose(routed.span_requirement), retries


def _claim(span, claim_class, routed, l1, l2, l3, establishment, l4, action, retries, failures) -> ClaimResult:
    return ClaimResult(
        claim_id=span.claim_id, span_text=span.text, claim_class=claim_class,
        content_ownership=routed.content_ownership, span_requirement=routed.span_requirement,
        requirement_source=routed.requirement_source, generator_label_discarded=routed.generator_label_discarded,
        l1=l1, l2=l2, l3=l3, establishment=establishment, l4=l4,
        decision=action, retry_count=retries, failures=failures,
    )
