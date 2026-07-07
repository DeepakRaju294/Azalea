"""L2 class-3 transformation validation (Q24 §3): canonical OUTPUT first, then logical strength.

Consumes a built `OperationBinding`. The order is strict and gated:
1. binding gate — if the operation/relation bind failed, STOP: no canonical output, verdict refuted (or
   indeterminate when there was no declared operation at all).
2. canonical application + target conformance — apply the registered operation to the resolved SOURCE relation;
   the canonical result must equal the declared TARGET, else refuted (even when source & target share a solution
   set — that's exactly the §6 slice).
3. relation-mode conformance — only after target conformance passes, and only when a mode is declared; a
   non-equivalence-preserving operation rendered as an `equivalence` is refuted.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import binding as bindmod
from . import relations

VERDICT_PASS = "pass"
VERDICT_REFUTED = "refuted"
VERDICT_INDETERMINATE = "indeterminate"

# target_conformance / relation_mode_conformance states
CONF_PASS = "pass"
CONF_FAIL = "fail"
CONF_INDETERMINATE = "indeterminate"
CONF_UNEVALUATED = "unevaluated"

EQUIVALENCE = "equivalence"
NECESSARY_CONDITION = "necessary_condition"
CONTRADICTION = "contradiction"
NO_SOLUTION = "no_solution"

_DIRECTIONAL_MARKERS = (
    "necessary condition", "must satisfy", "any solution", "this implies", "therefore a necessary condition",
)


@dataclass(frozen=True)
class TransformationResult:
    binding: bindmod.OperationBinding
    canonical_output_relation: Optional[relations.Relation]
    target_conformance: str
    relation_mode_conformance: str
    verdict: str                              # pass | refuted | indeterminate
    transformation_failure_stage: Optional[str]


def validate_transformation(span: bindmod.SpanInput) -> TransformationResult:
    b = bindmod.build_binding(span)

    # (0) not a declared class-3 transformation → indeterminate → L4 (never inferred)
    if not b.is_transformation:
        return TransformationResult(
            binding=b, canonical_output_relation=None,
            target_conformance=CONF_UNEVALUATED, relation_mode_conformance=CONF_UNEVALUATED,
            verdict=VERDICT_INDETERMINATE, transformation_failure_stage=None,
        )

    # (1) binding gate — a failed bind produces no resolved op / canonical output
    if not b.canonical_application_permitted:
        return TransformationResult(
            binding=b, canonical_output_relation=None,
            target_conformance=CONF_UNEVALUATED, relation_mode_conformance=CONF_UNEVALUATED,
            verdict=VERDICT_REFUTED, transformation_failure_stage=b.transformation_failure_stage,
        )

    op = relations.get_operation(b.resolved_operation_id)
    source = b.resolved_source_relation
    target = b.resolved_target_relation
    if op is None or source is None or target is None:
        # resolved but unrunnable (e.g. metadata-only with no parseable relations) → indeterminate
        return TransformationResult(
            binding=b, canonical_output_relation=None,
            target_conformance=CONF_INDETERMINATE, relation_mode_conformance=CONF_UNEVALUATED,
            verdict=VERDICT_INDETERMINATE, transformation_failure_stage=None,
        )

    # (2) canonical application + target conformance
    canonical = op.apply(source)
    if not relations.relations_equal(canonical, target):
        return TransformationResult(
            binding=b, canonical_output_relation=canonical,
            target_conformance=CONF_FAIL, relation_mode_conformance=CONF_UNEVALUATED,
            verdict=VERDICT_REFUTED, transformation_failure_stage=bindmod.STAGE_TARGET_CONFORMANCE,
        )

    # (3) relation-mode conformance (only when a mode is declared)
    mode = b.relation_mode
    mode_conf = CONF_UNEVALUATED
    if mode == EQUIVALENCE:
        if op.preserves_equivalence:
            mode_conf = CONF_PASS
        else:
            return TransformationResult(
                binding=b, canonical_output_relation=canonical,
                target_conformance=CONF_PASS, relation_mode_conformance=CONF_FAIL,
                verdict=VERDICT_REFUTED, transformation_failure_stage=bindmod.STAGE_RELATION_MODE,
            )
    elif mode == NECESSARY_CONDITION:
        low = span.text.lower()
        if any(marker in low for marker in _DIRECTIONAL_MARKERS):
            mode_conf = CONF_PASS
        else:
            return TransformationResult(
                binding=b, canonical_output_relation=canonical,
                target_conformance=CONF_PASS, relation_mode_conformance=CONF_FAIL,
                verdict=VERDICT_REFUTED, transformation_failure_stage=bindmod.STAGE_RELATION_MODE,
            )

    return TransformationResult(
        binding=b, canonical_output_relation=canonical,
        target_conformance=CONF_PASS, relation_mode_conformance=mode_conf,
        verdict=VERDICT_PASS, transformation_failure_stage=None,
    )
