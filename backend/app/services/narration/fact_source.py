"""Narration fact-source + adapter-capability registry (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §4).

The machine-checkable bridge that keeps narration truthful: every truth-bearing OUTPUT field of a card contract
maps to exactly one registered SOURCE MODE — `direct` (one authoritative trace/adapter field), `derived` (a named
deterministic template over an enumerated set of authoritative inputs), or `validated_generated` (generated text
accepted only via a companion validator, §12). **Free generation is never a source mode.**

A missing REQUIRED source BLOCKS that card type from the initial rollout; an optional unsupported field is
OMITTED, never free-generated. This registry IS the adapter-capability registry (one artifact): `AdapterCapability`
records what an adapter can actually supply, so the fact-source rules are enforced, not aspirational. The per-
adapter capability rows are produced by the Phase-2A audit; here we ship the shapes + the §4 seed entries.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# --- source modes + fallbacks (§4) ------------------------------------------------------------------------
DIRECT = "direct"
DERIVED = "derived"
VALIDATED_GENERATED = "validated_generated"
SOURCE_MODES = (DIRECT, DERIVED, VALIDATED_GENERATED)

# `required` may be a bool or the sentinel "when_quantitative" (§4 table).
REQUIRED_WHEN_QUANTITATIVE = "when_quantitative"

# Fallback when a source is unavailable.
FALLBACK_BLOCK_CARD = "block_card"
FALLBACK_OMIT = "omit"
FALLBACK_BLOCK_CALC_FRAMING = "block_calculation_framing"
FALLBACK_DEFER_CARD = "defer_card"


@dataclass(frozen=True)
class DerivedSource:
    """A named deterministic template over an enumerated set of authoritative inputs (§4)."""
    template_id: str
    input_field_ids: tuple[str, ...]
    output_schema: str
    validation_rule: Optional[str] = None


@dataclass(frozen=True)
class FactSource:
    """One truth-bearing (card_type, field, domain) → source-mode mapping (§4 data shape)."""
    card_type: str
    field: str
    domain: str
    mode: str                                   # direct | derived | validated_generated
    required: object                            # True | False | "when_quantitative"
    fallback: str                               # block_card | omit | block_calculation_framing | defer_card
    direct_source: Optional[str] = None         # trace/adapter field id (mode == direct)
    derived: Optional[DerivedSource] = None      # (mode == derived)

    def key(self) -> tuple[str, str, str]:
        return (self.card_type, self.field, self.domain)


# Derived-interpretation eligibility (§4): the template runs ONLY when all required semantic inputs are present.
SCIENCE_QUANTITY_INTERPRETATION_V1 = DerivedSource(
    template_id="science_quantity_interpretation_v1",
    input_field_ids=(
        "trace.step.quantity_label", "trace.step.value", "trace.step.units",
        "trace.step.quantity_kind", "trace.step.sign_or_direction", "trace.step.model_assumptions",
        "trace.step.reference_frame", "trace.step.calculation_status",
    ),
    output_schema="one_sentence_interpretation",
    validation_rule="omit_if_any_required_semantic_input_absent",
)

# Seed registry — the §4 table. The full per-domain sweep is the Phase-2A audit deliverable.
_REGISTRY: dict[tuple[str, str, str], FactSource] = {}


def _register(fs: FactSource) -> None:
    _REGISTRY[fs.key()] = fs


for _fs in (
    FactSource("worked_example", "result", "math", DIRECT, True, FALLBACK_BLOCK_CARD,
               direct_source="trace.step.result_expression"),
    FactSource("worked_example", "reasoning", "math", DIRECT, True, FALLBACK_OMIT,
               direct_source="trace.step.operation_tag"),
    FactSource("worked_example", "result_units", "science", DIRECT, REQUIRED_WHEN_QUANTITATIVE,
               FALLBACK_BLOCK_CALC_FRAMING, direct_source="trace.step.units"),
    FactSource("worked_example", "interpretation", "science", DERIVED, False, FALLBACK_OMIT,
               derived=SCIENCE_QUANTITY_INTERPRETATION_V1),
    FactSource("worked_example", "result_state", "coding", DIRECT, True, FALLBACK_BLOCK_CARD,
               direct_source="execution_trace.state_delta"),
    # formula_breakdown(math) — the derivation's rule labels + transformed forms are truth-bearing (§2.1 D2).
    FactSource("formula_breakdown", "rule", "math", DIRECT, True, FALLBACK_BLOCK_CARD,
               direct_source="trace.step.operation_tag"),
    FactSource("formula_breakdown", "form", "math", DIRECT, True, FALLBACK_BLOCK_CARD,
               direct_source="trace.step.result_expression"),
):
    _register(_fs)


def get_fact_source(card_type: str, field: str, domain: str) -> Optional[FactSource]:
    return _REGISTRY.get((card_type, field, domain))


def required_sources_for(card_type: str, domain: str, *, quantitative: bool = False) -> list[FactSource]:
    """The fact sources that are REQUIRED for a (card_type, domain) — `when_quantitative` counts as required only
    when `quantitative` is set. These must all be satisfiable before the card is eligible under `on_enforced`."""
    out: list[FactSource] = []
    for fs in _REGISTRY.values():
        if fs.card_type != card_type or fs.domain != domain:
            continue
        if fs.required is True or (fs.required == REQUIRED_WHEN_QUANTITATIVE and quantitative):
            out.append(fs)
    return out


def all_fact_sources() -> list[FactSource]:
    return list(_REGISTRY.values())


# --- adapter-capability registry (§4 — same artifact) -----------------------------------------------------
@dataclass(frozen=True)
class AdapterCapability:
    """What ONE adapter can actually supply, so the fact-source rules are enforced not aspirational (§4). Keyed by
    adapter slug. The per-adapter rows are the Phase-2A audit; the shape ships now."""
    adapter_slug: str
    supported_domains: tuple[str, ...] = ()
    supports_verified_worked_example: bool = False
    supports_rule_identifier: bool = False
    supports_units: bool = False
    supports_quantity_kind: bool = False
    supports_sign_or_direction: bool = False
    supports_assumption_metadata: bool = False
    supports_final_result_status: bool = False
    supported_languages: tuple[str, ...] = ()
    supported_card_types: tuple[str, ...] = ()


_ADAPTER_CAPABILITIES: dict[str, AdapterCapability] = {}


def register_adapter_capability(cap: AdapterCapability) -> None:
    _ADAPTER_CAPABILITIES[cap.adapter_slug] = cap


def get_adapter_capability(adapter_slug: str) -> Optional[AdapterCapability]:
    return _ADAPTER_CAPABILITIES.get(adapter_slug)


def adapter_can_supply(adapter_slug: str, fs: FactSource, *, quantitative: bool = False) -> bool:
    """Whether the adapter can supply a given fact source. An UNREGISTERED adapter fails closed for any REQUIRED
    source (we cannot assert a verified trace / units / rule tags exist), so the fact-source rules stay enforced
    rather than assumed. Optional sources default to unsupported (→ omit), never invented."""
    cap = _ADAPTER_CAPABILITIES.get(adapter_slug)
    if cap is None:
        return False  # unregistered adapter fails closed — we can't assert a verified trace/units/tags exist
    # Field-specific capability checks for the seed rows; unknown fields fall back to the coarse WE capability.
    if fs.field in ("result", "result_state"):
        return cap.supports_verified_worked_example
    if fs.field == "reasoning":
        return cap.supports_rule_identifier
    if fs.field == "result_units":
        return cap.supports_units
    if fs.field == "interpretation":
        return (cap.supports_units and cap.supports_quantity_kind
                and cap.supports_final_result_status)
    return cap.supports_verified_worked_example
