"""Narration-data audit (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §4, §10 Phase-2A deliverable).

"Confirm every required truth-bearing field exists in the authoritative trace/adapter metadata" — and record the
GAPS. This is the audited grounding for `fact_source.py`: it turns the fact-source rules from aspirational into
enforced by (a) registering the real T6 formula-engine capability from the code, and (b) enumerating the missing
authoritative fields so a dependent card behavior is OMITTED/DEFERRED, never free-generated.

Audited source: `app/services/examples/trace_adapters/families/formula_specs.py` — each `Output` is
`(symbol, equation, expression, units, operation_stage, quantity_label)` and each spec carries a `conventions`
dict (model / law / units assumptions).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.narration.fact_source import AdapterCapability, register_adapter_capability

# The T6 formula engine (physics / chemistry / finance / geometry) — what it PROVABLY supplies, read from the
# Output tuple + conventions. It does NOT carry a dimensional category, sign/direction, reference frame, or an
# explicit final-vs-intermediate status (an Output is a final requested quantity, but that isn't a typed field).
FORMULA_ENGINE_CAPABILITY = AdapterCapability(
    adapter_slug="t6_formula_engine",
    supported_domains=("science", "math", "concept"),   # physics/chem → science; geometry → math; finance → concept
    supports_verified_worked_example=True,               # gate re-evaluates every output → verified
    supports_rule_identifier=True,                       # Output.operation_stage + conventions.law
    supports_units=True,                                 # Output.units
    supports_quantity_kind=False,                        # GAP — no dimensional category
    supports_sign_or_direction=False,                    # GAP — magnitudes only
    supports_assumption_metadata=True,                   # conventions{model|law|units}
    supports_final_result_status=False,                  # GAP — not a typed calculation_status field
    supported_languages=(),
    supported_card_types=("worked_example", "process", "background", "components_terms", "edge_case", "practice"),
)


@dataclass(frozen=True)
class DataGap:
    """A required authoritative field that is NOT present in the audited metadata, and what it blocks."""
    field: str
    needed_by: str            # card behavior that depends on it
    consequence: str          # what happens today (per §4 fallback)


# The enumerated §4 gaps for the science quantitative slice. Each forces the safe fallback (omit/defer), so no
# misleading prose is generated. Recording them here is the audit deliverable; closing them is a SEPARATELY-
# approved adapter/trace change (§4/§11), not implicit narration work.
NARRATION_DATA_GAPS: tuple[DataGap, ...] = (
    DataGap("trace.step.quantity_kind", "science worked_example.interpretation (science_quantity_interpretation_v1)",
            "interpretation OMITTED — value + units still shown"),
    DataGap("trace.step.sign_or_direction", "science interpretation for vector quantities",
            "interpretation OMITTED for direction-bearing quantities"),
    DataGap("trace.step.reference_frame", "science interpretation for frame-dependent quantities",
            "interpretation OMITTED when the quantity_kind needs a frame"),
    DataGap("trace.step.calculation_status", "science interpretation final-vs-intermediate guard",
            "interpretation OMITTED — cannot confirm the value is final"),
    # Math derivation adapters (completing-the-square / algebraic transforms, T8b) are NOT the formula engine and
    # were not audited here; the first math on_enforced slice is independently blocked by formula_breakdown(math)
    # being `deferred` (§2.1), so this gap does not affect the current shadow-only math slice.
    DataGap("math derivation adapter audit", "math worked_example.result / reasoning (completing the square)",
            "PENDING — math slice stays shadow-only until formula_breakdown is defined AND this audit is done"),
)


def register_audited_capabilities() -> None:
    """Register the audited real-adapter capabilities so the fact-source enforcement is grounded in what the code
    actually supplies (call at narration-system init; idempotent)."""
    register_adapter_capability(FORMULA_ENGINE_CAPABILITY)


def audit_summary() -> dict[str, object]:
    """Machine-readable audit result (for telemetry / the Phase-2A report)."""
    return {
        "audited_adapter": FORMULA_ENGINE_CAPABILITY.adapter_slug,
        "supplies": {
            "result_expression": True, "operation_tag": True, "units": True,
            "quantity_label": True, "assumption_metadata": True,
        },
        "gaps": [g.field for g in NARRATION_DATA_GAPS],
        "science_interpretation_available": (
            FORMULA_ENGINE_CAPABILITY.supports_units
            and FORMULA_ENGINE_CAPABILITY.supports_quantity_kind
            and FORMULA_ENGINE_CAPABILITY.supports_final_result_status
        ),  # False today — interpretation correctly omitted
    }
