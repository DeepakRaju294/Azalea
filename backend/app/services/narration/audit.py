"""Narration-data audit (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §4, §10 Phase-2A deliverable).

"Confirm every required truth-bearing field exists in the authoritative trace/adapter metadata" — and record the
GAPS. This is the audited grounding for `fact_source.py`: it turns the fact-source rules from aspirational into
enforced by (a) registering the real T6 formula-engine + T8b derivation-engine capabilities from the code, and
(b) enumerating the missing authoritative fields so a dependent card behavior is OMITTED/DEFERRED, never
free-generated.

Audited sources:
- `.../trace_adapters/families/formula_specs.py` (T6) — each `Output` is
  `(symbol, equation, expression, units, operation_stage, quantity_label)` + a `conventions` dict.
- `.../trace_adapters/families/derivation_engine.py` (T8b) — each `DerivationStep` carries a named `law` (the
  rule identifier) and an `apply`/`render` producing the transformed expression; the ContractTrace carries a
  typed `final_answer` (the conclusion) and a value-preserved invariant checked at every step by the gate.
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

# The T8b derivation engine (algebraic transforms: completing-the-square, exponent/log laws, equation balancing)
# — what it PROVABLY supplies, read from `derivation_engine._reference`. Each step names an authoritative `law`
# (the rule identifier) and yields a rendered transformed expression; the trace carries a typed `final_answer`
# and a value-preserved invariant re-checked at every step by `test_derivation_engine` (→ verified). It is a
# dimensionless algebraic domain, so it carries no units / dimensional category / sign / reference frame.
DERIVATION_ENGINE_CAPABILITY = AdapterCapability(
    adapter_slug="t8b_derivation_engine",
    supported_domains=("math",),
    supports_verified_worked_example=True,               # gate verifies answer vs oracle + value-preserved/step
    supports_rule_identifier=True,                       # DerivationStep.law → "by the <law>, …" (authoritative)
    supports_units=False,                                # algebraic transforms are dimensionless
    supports_quantity_kind=False,                        # N/A — no physical quantity
    supports_sign_or_direction=False,                    # N/A — no vector/direction
    supports_assumption_metadata=True,                   # conventions{method, conclusion} + invariant statement
    supports_final_result_status=False,                  # no per-step calculation_status field (not needed for math)
    supported_languages=(),
    supported_card_types=("worked_example", "formula_breakdown"),
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
    # NOTE: the math derivation (T8b) audit is now DONE — DERIVATION_ENGINE_CAPABILITY supplies math
    # worked_example.result/reasoning + formula_breakdown.rule/form. formula_breakdown(math) is also now `defined`
    # (matrix §2.1). So the completing-the-square slice is no longer blocked by a missing audit; the only remaining
    # step to display it is the guarded on_enforced display-application (the 2B display step), not more auditing.
)


def register_audited_capabilities() -> None:
    """Register the audited real-adapter capabilities so the fact-source enforcement is grounded in what the code
    actually supplies (call at narration-system init; idempotent)."""
    register_adapter_capability(FORMULA_ENGINE_CAPABILITY)
    register_adapter_capability(DERIVATION_ENGINE_CAPABILITY)


def audit_summary() -> dict[str, object]:
    """Machine-readable audit result (for telemetry / the Phase-2A report)."""
    return {
        "audited_adapters": [FORMULA_ENGINE_CAPABILITY.adapter_slug, DERIVATION_ENGINE_CAPABILITY.adapter_slug],
        "formula_engine_supplies": {
            "result_expression": True, "operation_tag": True, "units": True,
            "quantity_label": True, "assumption_metadata": True,
        },
        "derivation_engine_supplies": {
            "result_expression": True, "rule_identifier": True, "final_answer": True,
            "assumption_metadata": True, "units": False,
        },
        "gaps": [g.field for g in NARRATION_DATA_GAPS],
        "science_interpretation_available": (
            FORMULA_ENGINE_CAPABILITY.supports_units
            and FORMULA_ENGINE_CAPABILITY.supports_quantity_kind
            and FORMULA_ENGINE_CAPABILITY.supports_final_result_status
        ),  # False today — interpretation correctly omitted
    }
