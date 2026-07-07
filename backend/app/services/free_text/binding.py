"""OperationBinding — bind the learner-visible transformation to a backend-authoritative operation (Q24 §3).

Trust model (the whole point of this module):
- The generator may emit prose. It may NOT choose the operation contract: generator-supplied transformation
  metadata is discarded (retained only as a non-binding hint).
- A binding is created ONLY from (1) deterministic extraction of surfaced learner-visible prose, or (2) a
  registered backend source carrying stable provenance {binding_source_id, binding_source_version, binding_field}.
- Surfaced text and any backend metadata must agree (operation AND source/target relations); a disagreement is a
  hard L2 binding failure.
- A binding failure GATES canonical application: no resolved operation is exposed for an operation-bind failure,
  and `canonical_output_relation` is never produced after any binding failure.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import relations

# conformance values
PASS = "pass"
FAIL = "fail"
METADATA_ONLY = "metadata_only"

# operation_source
SURFACED_TEXT = "surfaced_text"
REGISTERED_METADATA = "registered_metadata"
BOTH = "both"

# binding_provenance.binding_source
SURFACED_EXTRACTION = "surfaced_extraction"
REGISTERED_BACKEND_SOURCE = "registered_backend_source"

# transformation_failure_stage
STAGE_OPERATION_BINDING = "operation_binding"
STAGE_RELATION_BINDING = "relation_binding"
STAGE_TARGET_CONFORMANCE = "target_conformance"
STAGE_RELATION_MODE = "relation_mode"


@dataclass(frozen=True)
class BindingProvenance:
    binding_source: str  # SURFACED_EXTRACTION | REGISTERED_BACKEND_SOURCE
    binding_source_id: Optional[str] = None
    binding_source_version: Optional[str] = None
    binding_field: Optional[str] = None

    def is_valid_backend(self) -> bool:
        return (
            self.binding_source == REGISTERED_BACKEND_SOURCE
            and bool(self.binding_source_id)
            and bool(self.binding_source_version)
        )


@dataclass(frozen=True)
class BackendBinding:
    """A registered backend-source transformation contract (authoritative). Must carry valid provenance."""
    provenance: BindingProvenance
    operation_id: Optional[str] = None
    operation_version: Optional[str] = None
    source_relation: Optional[str] = None
    target_relation: Optional[str] = None
    relation_mode: Optional[str] = None


@dataclass(frozen=True)
class SpanInput:
    """One claim span handed to the transformation validator."""
    text: str
    # authoritative backend metadata (registered source), if any:
    backend_binding: Optional[BackendBinding] = None
    # generator-emitted metadata — NEVER authoritative; kept only so telemetry can show it was discarded:
    generator_metadata: Optional[dict] = None
    # whether the card contract permits a metadata-only (surface-absent) transformation:
    allow_metadata_backed: bool = False


@dataclass(frozen=True)
class OperationBinding:
    """Result of binding — retains BOTH inputs + resolution state (spec §3 result shape)."""
    binding_provenance: Optional[BindingProvenance]
    surfaced_operation_id: Optional[str]
    surfaced_operation_span: Optional[tuple]
    surfaced_source_relation: Optional[relations.Relation]
    surfaced_target_relation: Optional[relations.Relation]
    metadata_operation_id: Optional[str]
    metadata_operation_version: Optional[str]
    metadata_source_relation: Optional[relations.Relation]
    metadata_target_relation: Optional[relations.Relation]
    resolved_operation_id: Optional[str]
    resolved_operation_version: Optional[str]
    resolved_source_relation: Optional[relations.Relation]
    resolved_target_relation: Optional[relations.Relation]
    operation_source: Optional[str]           # SURFACED_TEXT | REGISTERED_METADATA | BOTH | None
    binding_conformance: str                  # PASS | FAIL | METADATA_ONLY
    relation_binding_conformance: str         # PASS | FAIL | METADATA_ONLY
    relation_mode: Optional[str]
    transformation_failure_stage: Optional[str]
    is_transformation: bool                   # False ⇒ not a declared class-3 transformation (→ indeterminate/L4)
    hard_routing_failure: bool = False

    @property
    def canonical_application_permitted(self) -> bool:
        """Canonical op may run ONLY when both binds are pass/metadata_only (§3 gate)."""
        return (
            self.is_transformation
            and not self.hard_routing_failure
            and self.binding_conformance in (PASS, METADATA_ONLY)
            and self.relation_binding_conformance in (PASS, METADATA_ONLY)
        )


def _extract_surfaced(text: str):
    """(operation_id, op_span, source_relation, target_relation) from surfaced prose; ids/relations may be None."""
    phrase = relations.find_operation_phrase(text)
    op_id = None
    op_span = None
    if phrase is not None:
        matched, start, end = phrase
        op_id = relations.normalize_operation_phrase(matched)
        op_span = (start, end)
    rels = relations.find_relations(text)
    source = rels[0][0] if len(rels) >= 1 else None
    target = rels[-1][0] if len(rels) >= 2 else None
    return op_id, op_span, source, target


def build_binding(span: SpanInput) -> OperationBinding:
    """Bind a span's transformation to an authoritative operation. Generator metadata is never consulted here."""
    op_id, op_span, s_source, s_target = _extract_surfaced(span.text)
    surfaced_present = op_id is not None

    backend = span.backend_binding
    m_op = backend.operation_id if backend else None
    m_ver = backend.operation_version if backend else None
    m_source = relations.parse_relation(backend.source_relation) if backend and backend.source_relation else None
    m_target = relations.parse_relation(backend.target_relation) if backend and backend.target_relation else None
    relation_mode = backend.relation_mode if backend else None
    metadata_present = backend is not None and m_op is not None

    # A registered backend binding must carry valid provenance; otherwise it's not authoritative.
    backend_provenance_valid = backend is not None and backend.provenance.is_valid_backend()

    # ── determine operation_source ──
    if surfaced_present and metadata_present:
        operation_source = BOTH
    elif surfaced_present:
        operation_source = SURFACED_TEXT
    elif metadata_present:
        operation_source = REGISTERED_METADATA
    else:
        operation_source = None

    # Not a declared class-3 transformation at all (no surfaced op, no metadata op) → indeterminate → L4.
    # Requires two relations to even be a source→target step.
    if operation_source is None or s_source is None or (s_target is None and m_target is None):
        # If a "since P, we get Q" step has relations but no operation, it's an undeclared transformation.
        return OperationBinding(
            binding_provenance=None,
            surfaced_operation_id=op_id, surfaced_operation_span=op_span,
            surfaced_source_relation=s_source, surfaced_target_relation=s_target,
            metadata_operation_id=m_op, metadata_operation_version=m_ver,
            metadata_source_relation=m_source, metadata_target_relation=m_target,
            resolved_operation_id=None, resolved_operation_version=None,
            resolved_source_relation=None, resolved_target_relation=None,
            operation_source=operation_source,
            binding_conformance=FAIL if operation_source else METADATA_ONLY,
            relation_binding_conformance=FAIL,
            relation_mode=relation_mode,
            transformation_failure_stage=None,
            is_transformation=False,
        )

    # ── metadata-only path (no surfaced operation) ──
    if operation_source == REGISTERED_METADATA:
        if not span.allow_metadata_backed or not backend_provenance_valid:
            # Missing/invalid backend provenance or contract doesn't permit metadata-backed → HARD failure.
            return OperationBinding(
                binding_provenance=(backend.provenance if backend else None),
                surfaced_operation_id=None, surfaced_operation_span=None,
                surfaced_source_relation=s_source, surfaced_target_relation=s_target,
                metadata_operation_id=m_op, metadata_operation_version=m_ver,
                metadata_source_relation=m_source, metadata_target_relation=m_target,
                resolved_operation_id=None, resolved_operation_version=None,
                resolved_source_relation=None, resolved_target_relation=None,
                operation_source=operation_source,
                binding_conformance=FAIL, relation_binding_conformance=FAIL,
                relation_mode=relation_mode,
                transformation_failure_stage=STAGE_OPERATION_BINDING,
                is_transformation=True, hard_routing_failure=True,
            )
        prov = backend.provenance
        return OperationBinding(
            binding_provenance=prov,
            surfaced_operation_id=None, surfaced_operation_span=None,
            surfaced_source_relation=None, surfaced_target_relation=None,
            metadata_operation_id=m_op, metadata_operation_version=m_ver,
            metadata_source_relation=m_source, metadata_target_relation=m_target,
            resolved_operation_id=m_op, resolved_operation_version=m_ver,
            resolved_source_relation=m_source, resolved_target_relation=m_target,
            operation_source=operation_source,
            binding_conformance=METADATA_ONLY, relation_binding_conformance=METADATA_ONLY,
            relation_mode=relation_mode,
            transformation_failure_stage=None,
            is_transformation=True,
        )

    # ── surfaced present (SURFACED_TEXT or BOTH) ──
    prov = BindingProvenance(binding_source=SURFACED_EXTRACTION)

    # operation-binding conformance: when both are present, surfaced normalized id must equal metadata operation_id
    # (surfaced prose carries no version, so version is checked only across registered metadata elsewhere).
    if operation_source == BOTH:
        binding_conf = PASS if op_id == m_op else FAIL
    else:
        binding_conf = PASS

    if binding_conf == FAIL:
        # operation bind failed → NO resolved operation, NO canonical output (typed null state).
        return OperationBinding(
            binding_provenance=prov,
            surfaced_operation_id=op_id, surfaced_operation_span=op_span,
            surfaced_source_relation=s_source, surfaced_target_relation=s_target,
            metadata_operation_id=m_op, metadata_operation_version=m_ver,
            metadata_source_relation=m_source, metadata_target_relation=m_target,
            resolved_operation_id=None, resolved_operation_version=None,
            resolved_source_relation=None, resolved_target_relation=None,
            operation_source=operation_source,
            binding_conformance=FAIL, relation_binding_conformance=FAIL,
            relation_mode=relation_mode,
            transformation_failure_stage=STAGE_OPERATION_BINDING,
            is_transformation=True,
        )

    resolved_op = op_id
    resolved_ver = get_version(op_id)

    # relation-binding conformance: surfaced relations are authoritative; metadata (if any) must match them.
    rel_conf = PASS
    rel_stage = None
    if operation_source == BOTH:
        if m_source is not None and s_source is not None and not relations.relations_equal(m_source, s_source):
            rel_conf, rel_stage = FAIL, STAGE_RELATION_BINDING
        if m_target is not None and s_target is not None and not relations.relations_equal(m_target, s_target):
            rel_conf, rel_stage = FAIL, STAGE_RELATION_BINDING

    if rel_conf == FAIL:
        # relation bind failed AFTER a passing operation bind: resolved op MAY be retained (audit), but
        # canonical output is never produced.
        return OperationBinding(
            binding_provenance=prov,
            surfaced_operation_id=op_id, surfaced_operation_span=op_span,
            surfaced_source_relation=s_source, surfaced_target_relation=s_target,
            metadata_operation_id=m_op, metadata_operation_version=m_ver,
            metadata_source_relation=m_source, metadata_target_relation=m_target,
            resolved_operation_id=resolved_op, resolved_operation_version=resolved_ver,
            resolved_source_relation=None, resolved_target_relation=None,
            operation_source=operation_source,
            binding_conformance=PASS, relation_binding_conformance=FAIL,
            relation_mode=relation_mode,
            transformation_failure_stage=STAGE_RELATION_BINDING,
            is_transformation=True,
        )

    return OperationBinding(
        binding_provenance=prov,
        surfaced_operation_id=op_id, surfaced_operation_span=op_span,
        surfaced_source_relation=s_source, surfaced_target_relation=s_target,
        metadata_operation_id=m_op, metadata_operation_version=m_ver,
        metadata_source_relation=m_source, metadata_target_relation=m_target,
        resolved_operation_id=resolved_op, resolved_operation_version=resolved_ver,
        resolved_source_relation=s_source, resolved_target_relation=s_target,
        operation_source=operation_source,
        binding_conformance=PASS, relation_binding_conformance=rel_conf,
        relation_mode=relation_mode,
        transformation_failure_stage=None,
        is_transformation=True,
    )


def get_version(operation_id: Optional[str]) -> Optional[str]:
    if operation_id is None:
        return None
    op = relations.get_operation(operation_id)
    return op.operation_version if op else None
