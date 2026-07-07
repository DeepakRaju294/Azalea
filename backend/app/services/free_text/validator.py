"""Slice orchestration (Q24 §3/§4/§5): segment → route → validate → dispose, in shadow or enforce mode.

Wires claim segmentation, the L2 class-3 transformation check, the BACKEND ownership/requiredness router (§2 —
generator labels discarded), and the backend-`span_requirement`-driven disposition (optional → DELETE, required →
WITHHOLD field, essential → WITHHOLD card). Two modes mirror the rollout ladder:
- `shadow_validate` — compute everything + emit telemetry, but leave the displayed field UNCHANGED.
- `on_enforced`     — apply the disposition (delete/withhold) to the returned field.

There is no fallback or legacy-recovery path — an enforced deletion is gone from the returned text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as _field
from typing import Callable, Dict, List, Optional

from . import binding as bindmod
from . import routing
from . import transformation as xform
from .routing import OPTIONAL, REQUIRED, ESSENTIAL, FREE_TEXT  # re-exported for callers/tests

# claim_class
FACTUAL = "factual"
NON_FACTUAL_FRAMING = "non_factual_framing"
PROMPT = "prompt"
UNCLASSIFIED = "unclassified"

# decisions
SHIP = "ship"
REPAIR = "repair"
SOFTEN = "soften"
WITHHOLD = "withhold"

# span-level actions
ACTION_SHIP = "ship"
ACTION_DELETE = "delete"
ACTION_WITHHOLD_FIELD = "withhold_field"
ACTION_WITHHOLD_CARD = "withhold_card"

# modes
SHADOW_VALIDATE = "shadow_validate"
ON_ENFORCED = "on_enforced"

MAX_REPAIRS = 2


@dataclass(frozen=True)
class ClaimSpan:
    claim_id: str
    text: str
    start: int
    end: int


@dataclass
class SpanResult:
    span: ClaimSpan
    verdict: str
    decision: str                                 # ACTION_*
    content_ownership: str = FREE_TEXT
    span_requirement: str = OPTIONAL
    requirement_source: str = routing.FALLBACK_DEFAULT
    generator_label_discarded: bool = False
    hard_routing_failure: bool = False
    transformation: Optional[xform.TransformationResult] = None
    retry_count: int = 0


@dataclass
class FieldResult:
    field_text_in: str
    field_text_out: str                           # shadow: == field_text_in; enforce: disposition applied
    field_decision: str                           # computed decision (what enforce WOULD do), in both modes
    mode: str
    spans: List[SpanResult] = _field(default_factory=list)

    def telemetry(self, *, topic_id: str = "", card_type: str = "", field: str = "") -> List[dict]:
        """Per-span telemetry rows (§4 telemetry shape) — what shadow_validate logs."""
        rows = []
        for s in self.spans:
            stage = s.transformation.transformation_failure_stage if s.transformation else None
            op = s.transformation.binding.resolved_operation_id if s.transformation else None
            mode = s.transformation.binding.relation_mode if s.transformation else None
            rows.append({
                "topic_id": topic_id, "card_type": card_type, "field": field,
                "claim_id": s.span.claim_id,
                "content_ownership": s.content_ownership,
                "span_requirement": s.span_requirement,
                "requirement_source": s.requirement_source,
                "generator_label_discarded": s.generator_label_discarded,
                "verdict": s.verdict, "action": s.decision, "retry_count": s.retry_count,
                "operation_id": op, "relation_mode": mode,
                "transformation_failure_stage": stage,
                "hard_routing_failure": s.hard_routing_failure,
            })
        return rows


_SENTENCE_RE = re.compile(r"[^.!?]*[.!?]|[^.!?]+$")


def segment(field_text: str) -> List[ClaimSpan]:
    """Ordered, non-overlapping spans covering every non-whitespace character (slice: sentence granularity)."""
    spans: List[ClaimSpan] = []
    for i, m in enumerate(_SENTENCE_RE.finditer(field_text)):
        if not m.group().strip():
            continue
        spans.append(ClaimSpan(claim_id=f"c{i}", text=m.group().strip(), start=m.start(), end=m.end()))
    return spans


def validate_field(
    field_text: str,
    *,
    mode: str = ON_ENFORCED,
    requirements: Optional[Dict[str, str]] = None,          # claim_id → span_requirement (shortcut for a mapping)
    mappings: Optional[Dict[str, routing.RegisteredMapping]] = None,
    generator_labels: Optional[Dict[str, dict]] = None,     # discarded by the router; recorded for telemetry
    backend_bindings: Optional[Dict[str, bindmod.BackendBinding]] = None,
    allow_metadata_backed: Optional[Dict[str, bool]] = None,
    repair_fn: Optional[Callable[[str], Optional[str]]] = None,
) -> FieldResult:
    """Validate a field's transformation spans and compute disposition. In shadow_validate the returned text is
    unchanged; in on_enforced the disposition is applied. `repair_fn` returns a replacement span text or None."""
    requirements = requirements or {}
    mappings = mappings or {}
    generator_labels = generator_labels or {}
    backend_bindings = backend_bindings or {}
    allow_metadata_backed = allow_metadata_backed or {}

    spans = segment(field_text)
    results: List[SpanResult] = []
    deleted_spans: List[ClaimSpan] = []
    withhold_field = False
    withhold_card = False

    for span in spans:
        cid = span.claim_id
        # backend routing: a mapping wins; else the `requirements` shortcut (a card_schema mapping); else unmapped.
        mapping = mappings.get(cid)
        if mapping is None and cid in requirements:
            mapping = routing.RegisteredMapping(
                content_ownership=FREE_TEXT, span_requirement=requirements[cid],
                requirement_source=routing.CARD_SCHEMA)
        routed = routing.route_span(mapping, generator_label=generator_labels.get(cid))

        # hard routing failure → fail closed (withhold), NEVER a free_text downgrade
        if routed.hard_routing_failure:
            if routed.span_requirement == ESSENTIAL:
                withhold_card = True
                action = ACTION_WITHHOLD_CARD
            else:
                withhold_field = True
                action = ACTION_WITHHOLD_FIELD
            results.append(_span_result(span, "hard_routing_failure", action, routed))
            continue

        span_input = bindmod.SpanInput(
            text=span.text,
            backend_binding=backend_bindings.get(cid),
            generator_metadata=generator_labels.get(cid),
            allow_metadata_backed=allow_metadata_backed.get(cid, False),
        )
        tr = xform.validate_transformation(span_input)

        if tr.verdict != xform.VERDICT_REFUTED:
            results.append(_span_result(span, tr.verdict, ACTION_SHIP, routed, transformation=tr))
            continue

        # refuted → repair up to MAX_REPAIRS, then dispose by backend requirement
        retries, repaired_ok, current_text = _attempt_repair(
            span.text, repair_fn, backend_bindings.get(cid), allow_metadata_backed.get(cid, False))

        if repaired_ok:
            fixed = ClaimSpan(cid, current_text, span.start, span.end)
            results.append(_span_result(fixed, xform.VERDICT_PASS, ACTION_SHIP, routed,
                                        transformation=tr, retry_count=retries))
            continue

        req = routed.span_requirement
        if req == OPTIONAL:
            deleted_spans.append(span)
            results.append(_span_result(span, tr.verdict, ACTION_DELETE, routed,
                                        transformation=tr, retry_count=retries))
        elif req == REQUIRED:
            withhold_field = True
            results.append(_span_result(span, tr.verdict, ACTION_WITHHOLD_FIELD, routed,
                                        transformation=tr, retry_count=retries))
        else:
            withhold_card = True
            results.append(_span_result(span, tr.verdict, ACTION_WITHHOLD_CARD, routed,
                                        transformation=tr, retry_count=retries))

    # compute decision (both modes) and the enforced text
    if withhold_card or withhold_field:
        field_decision = WITHHOLD
        enforced_text = ""
    elif deleted_spans:
        field_decision = SOFTEN
        enforced_text = _delete_spans(field_text, deleted_spans)
    else:
        field_decision = SHIP
        enforced_text = field_text

    field_out = field_text if mode == SHADOW_VALIDATE else enforced_text
    return FieldResult(field_text_in=field_text, field_text_out=field_out,
                       field_decision=field_decision, mode=mode, spans=results)


def _span_result(span: ClaimSpan, verdict: str, action: str, routed: routing.RoutedSpan,
                 *, transformation=None, retry_count: int = 0) -> SpanResult:
    return SpanResult(
        span=span, verdict=verdict, decision=action,
        content_ownership=routed.content_ownership, span_requirement=routed.span_requirement,
        requirement_source=routed.requirement_source,
        generator_label_discarded=routed.generator_label_discarded,
        hard_routing_failure=routed.hard_routing_failure,
        transformation=transformation, retry_count=retry_count,
    )


def _attempt_repair(text, repair_fn, backend_binding, allow_metadata):
    retries = 0
    current = text
    while retries < MAX_REPAIRS:
        retries += 1
        new_text = repair_fn(current) if repair_fn else None
        if new_text is None:
            continue
        retry_input = bindmod.SpanInput(text=new_text, backend_binding=backend_binding,
                                        allow_metadata_backed=allow_metadata)
        if xform.validate_transformation(retry_input).verdict != xform.VERDICT_REFUTED:
            return retries, True, new_text
    return retries, False, current


def _delete_spans(field_text: str, deleted: List[ClaimSpan]) -> str:
    out = field_text
    for span in deleted:
        out = out.replace(span.text, "")
    return re.sub(r"\s+", " ", out).strip()
