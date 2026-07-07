"""L3 — sibling-trace consistency (Q24 §3, deterministic).

Two parts:
1. BINDING classification (the novel Q24 contribution — never bind by proximity): a general rule/definition must
   NOT be checked against a concrete example's values just because it sits next to it. Only a span that EXPLICITLY
   references an example value/operation/result binds to that sibling fact.
2. The consistency checks themselves reuse trace-to-teaching C1/C2/C4/C5. This module implements the C1 numeric
   containment gate against explicitly-referenced facts; **C2 (forbidden claims), C4 (quantity↔unit) and C5
   (action/method order) are delegated to the shared Q23 check module and are NOT implemented here yet** — L3
   returns `not_applicable` for those until Q23 lands, so it never silently passes an unchecked action claim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

# binding classes
EXPLICIT_EXAMPLE_REFERENCE = "explicit_example_reference"
TOPIC_GENERAL_RULE = "topic_general_rule"
MIXED = "mixed"

# results
PASS = "pass"
FAIL = "fail"
NOT_APPLICABLE = "not_applicable"

_EXAMPLE_MARKERS = ("in this example", "in the example", "our example", "here we", "here the",
                    "above,", "as shown", "in this case")
_GENERAL_MARKERS = ("in general", "for any", "for all", "relates", "is defined as", "in every")


@dataclass(frozen=True)
class SiblingFact:
    trace_id: str
    trace_step_id: str
    output_name: str            # e.g. "net force"
    value: str                  # normalized numeric string, e.g. "20"
    unit: Optional[str] = None  # e.g. "N"


@dataclass(frozen=True)
class L3Result:
    binding_class: str
    c1_values: str              # PASS | FAIL | NOT_APPLICABLE
    c2_forbidden: str           # delegated to Q23 → NOT_APPLICABLE here
    c4_units: str               # delegated to Q23 → NOT_APPLICABLE here
    c5_action: str              # delegated to Q23 → NOT_APPLICABLE here
    conflicting_facts: Tuple[str, ...] = ()

    @property
    def status(self) -> str:
        return FAIL if self.c1_values == FAIL else PASS


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def classify_binding(span_text: str, sibling_facts: Tuple[SiblingFact, ...]) -> str:
    """Decide whether the span binds to example values. Default is topic_general_rule (never bind by proximity)."""
    low = span_text.lower()
    references_example = any(m in low for m in _EXAMPLE_MARKERS)
    # a span that cites an example-specific value (a number matching a sibling fact) also references the example
    span_nums = set(_NUM_RE.findall(span_text))
    references_example = references_example or any(f.value in span_nums for f in sibling_facts)
    is_general = any(m in low for m in _GENERAL_MARKERS)

    if references_example and is_general:
        return MIXED
    if references_example:
        return EXPLICIT_EXAMPLE_REFERENCE
    return TOPIC_GENERAL_RULE


def check_sibling_consistency(span_text: str, sibling_facts: Tuple[SiblingFact, ...]) -> L3Result:
    """Run C1 numeric containment ONLY against facts the span explicitly references (C2/C4/C5 delegated to Q23)."""
    binding = classify_binding(span_text, sibling_facts)

    if binding == TOPIC_GENERAL_RULE:
        # general rule — do NOT run example-value containment (validate via L2/L4 instead)
        return L3Result(binding, NOT_APPLICABLE, NOT_APPLICABLE, NOT_APPLICABLE, NOT_APPLICABLE)

    span_nums = set(_NUM_RE.findall(span_text))
    conflicts = []
    ran_c1 = False
    for f in sibling_facts:
        if f.output_name.lower() not in span_text.lower():
            continue                       # bind only to facts the span actually names
        ran_c1 = True
        if span_nums and f.value not in span_nums:
            conflicts.append(f"{f.trace_id}:{f.trace_step_id}:{f.output_name}")

    c1 = FAIL if conflicts else (PASS if ran_c1 else NOT_APPLICABLE)
    return L3Result(binding, c1, NOT_APPLICABLE, NOT_APPLICABLE, NOT_APPLICABLE, tuple(conflicts))
