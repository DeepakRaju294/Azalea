"""Slice orchestration (Q24 §3/§4): segment a field → validate each span → disposition (retry → delete/withhold).

This is the vertical slice, not the whole ladder: it wires claim segmentation, the L2 class-3 transformation
check, and the backend-`span_requirement`-driven disposition (optional → DELETE, required → WITHHOLD field,
essential → WITHHOLD card) end to end. `content_ownership`/`span_requirement` are supplied by the BACKEND caller
(a registered mapping), never read off generator payload. There is no fallback or legacy-recovery path — a deleted
span is gone from the returned text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from . import binding as bindmod
from . import transformation as xform

# span_requirement (backend-derived)
OPTIONAL = "optional"
REQUIRED = "required"
ESSENTIAL = "essential"

# content_ownership
FREE_TEXT = "free_text"

# claim_class
FACTUAL = "factual"
NON_FACTUAL_FRAMING = "non_factual_framing"

# decisions
SHIP = "ship"
REPAIR = "repair"
SOFTEN = "soften"
WITHHOLD = "withhold"

MAX_REPAIRS = 2


@dataclass(frozen=True)
class ClaimSpan:
    claim_id: str
    text: str
    start: int
    end: int
    content_ownership: str = FREE_TEXT
    span_requirement: str = OPTIONAL


@dataclass
class SpanResult:
    span: ClaimSpan
    verdict: str                                  # xform verdict or "ship"
    decision: str                                 # ship | delete | withhold_field | withhold_card
    transformation: Optional[xform.TransformationResult] = None
    retry_count: int = 0


@dataclass
class FieldResult:
    field_text_in: str
    field_text_out: str
    field_decision: str                           # ship | soften | withhold
    spans: List[SpanResult] = field(default_factory=list)


_SENTENCE_RE = re.compile(r"[^.!?]*[.!?]|[^.!?]+$")


def segment(field_text: str) -> List[ClaimSpan]:
    """Split a field into ordered, non-overlapping spans covering every non-whitespace character (slice: sentence
    granularity). Requirement/ownership default to free_text/optional and are overridden per-span by the caller."""
    spans: List[ClaimSpan] = []
    idx = 0
    for i, m in enumerate(_SENTENCE_RE.finditer(field_text)):
        chunk = m.group()
        if not chunk.strip():
            continue
        spans.append(ClaimSpan(claim_id=f"c{i}", text=chunk.strip(), start=m.start(), end=m.end()))
        idx += 1
    return spans


def validate_field(
    field_text: str,
    *,
    requirements: Optional[Dict[str, str]] = None,          # claim_id → span_requirement (backend-derived)
    backend_bindings: Optional[Dict[str, bindmod.BackendBinding]] = None,
    generator_metadata: Optional[Dict[str, dict]] = None,
    allow_metadata_backed: Optional[Dict[str, bool]] = None,
    repair_fn: Optional[Callable[[str], Optional[str]]] = None,
) -> FieldResult:
    """Validate a free-text field's transformation spans and apply disposition. `repair_fn` returns a replacement
    span text or None (can't repair); the slice's default treats every claim as unrepairable (repair exhausts)."""
    requirements = requirements or {}
    backend_bindings = backend_bindings or {}
    generator_metadata = generator_metadata or {}
    allow_metadata_backed = allow_metadata_backed or {}

    spans = segment(field_text)
    results: List[SpanResult] = []
    deleted_spans: List[ClaimSpan] = []
    withhold_field = False
    withhold_card = False

    for span in spans:
        requirement = requirements.get(span.claim_id, span.span_requirement)
        span = ClaimSpan(span.claim_id, span.text, span.start, span.end, span.content_ownership, requirement)

        span_input = bindmod.SpanInput(
            text=span.text,
            backend_binding=backend_bindings.get(span.claim_id),
            generator_metadata=generator_metadata.get(span.claim_id),
            allow_metadata_backed=allow_metadata_backed.get(span.claim_id, False),
        )
        tr = xform.validate_transformation(span_input)

        if tr.verdict != xform.VERDICT_REFUTED:
            # not a refuted transformation → ships in this slice (indeterminate → L4 out of slice scope)
            results.append(SpanResult(span=span, verdict=tr.verdict, decision=SHIP, transformation=tr))
            continue

        # refuted → repair up to MAX_REPAIRS, then dispose by backend requirement
        retries = 0
        repaired_ok = False
        current_text = span.text
        while retries < MAX_REPAIRS:
            retries += 1
            new_text = repair_fn(current_text) if repair_fn else None
            if new_text is None:
                continue  # repair unavailable/failed → keep retrying to the cap, then dispose
            retry_input = bindmod.SpanInput(
                text=new_text,
                backend_binding=backend_bindings.get(span.claim_id),
                allow_metadata_backed=allow_metadata_backed.get(span.claim_id, False),
            )
            if xform.validate_transformation(retry_input).verdict != xform.VERDICT_REFUTED:
                repaired_ok = True
                current_text = new_text
                break

        if repaired_ok:
            fixed = ClaimSpan(span.claim_id, current_text, span.start, span.end,
                              span.content_ownership, span.span_requirement)
            results.append(SpanResult(span=fixed, verdict=xform.VERDICT_PASS, decision=SHIP,
                                      transformation=tr, retry_count=retries))
            continue

        # disposition by backend span_requirement — NEVER retain/paraphrase the failed claim
        if requirement == OPTIONAL:
            deleted_spans.append(span)
            results.append(SpanResult(span=span, verdict=tr.verdict, decision="delete",
                                      transformation=tr, retry_count=retries))
        elif requirement == REQUIRED:
            withhold_field = True
            results.append(SpanResult(span=span, verdict=tr.verdict, decision="withhold_field",
                                      transformation=tr, retry_count=retries))
        else:  # ESSENTIAL
            withhold_card = True
            results.append(SpanResult(span=span, verdict=tr.verdict, decision="withhold_card",
                                      transformation=tr, retry_count=retries))

    # compute field text + decision
    if withhold_card or withhold_field:
        field_decision = WITHHOLD
        field_out = ""    # withheld: nothing ships (no placeholder, no fallback)
    elif deleted_spans:
        field_decision = SOFTEN
        field_out = _delete_spans(field_text, deleted_spans)
    else:
        field_decision = SHIP
        field_out = field_text

    return FieldResult(field_text_in=field_text, field_text_out=field_out,
                       field_decision=field_decision, spans=results)


def _delete_spans(field_text: str, deleted: List[ClaimSpan]) -> str:
    """Remove deleted spans by their text (deterministic delete; no replacement prose)."""
    out = field_text
    for span in deleted:
        out = out.replace(span.text, "")
    return re.sub(r"\s+", " ", out).strip()
