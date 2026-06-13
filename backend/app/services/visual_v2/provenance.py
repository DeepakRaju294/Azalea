"""Visual-model provenance (PROJECTOR_SYSTEM_SPEC §10.1, §18 rule 1).

Every visual model declares where its per-step state came from, so a bad visual is
diagnosable without guesswork — if a visual is wrong AND its tier is "T5", the fix is
to move the topic up the ladder (build a projector / contract), not to tweak the
renderer. Provenance is also what lets telemetry (§14) and feedback (§11) attribute a
problem to the right layer.

This module is pure data + a stamping helper; it has no dependency on the pipeline or
the projector, so it can ship first (build-order step 1) and everything downstream
becomes attributable from day one.
"""
from __future__ import annotations

from typing import Any, Optional

# Bumped when the respective logic changes, so a regenerated old lesson knows it is
# upgrading rather than just re-running (§4.2, §10.1).
PROJECTOR_VERSION = "0.1.0"
INFERENCE_VERSION = "0.1.0"

# The five tiers' state sources (§10) — verbatim names, reused everywhere (§18 rule 9).
STATE_SOURCES = (
    "registered_simulator",      # T1
    "authored_projection",       # T2
    "inferred_projection",       # T3
    "llm_validated_projection",  # T4
    "legacy_raw",                # T5
)
TIERS = ("T1", "T2", "T3", "T4", "T5")
SHAPE_PROJECTOR_STATUS = ("implemented", "planned", "unsupported")

_TIER_BY_SOURCE: dict[str, str] = {
    "registered_simulator": "T1",
    "authored_projection": "T2",
    "inferred_projection": "T3",
    "llm_validated_projection": "T4",
    "legacy_raw": "T5",
}


def tier_for(state_source: str) -> str:
    """The ladder tier that owns this state source (§10)."""
    return _TIER_BY_SOURCE.get(state_source, "T5")


def make_provenance(
    state_source: str,
    *,
    shape_projector_status: str = "implemented",
    projection_source: Optional[str] = None,   # "authored" | "inferred" | "llm_authored"
    projection_contract: Optional[dict[str, Any]] = None,
    projector_version: Optional[str] = None,
    inference_version: Optional[str] = None,
    confidence_band: Optional[str] = None,      # "high" | "medium" | "low" (inferred only)
    code_source: Optional[str] = None,          # T2: "inline_fixture" | "canonical_code_id"
    canonical_code_id: Optional[str] = None,
    validation_summary: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build the provenance record stamped onto a visual model (§10.1). `tier` is
    derived from `state_source` so the two can never disagree."""
    return {
        "state_source": state_source,
        "tier": tier_for(state_source),
        "shape_projector_status": shape_projector_status,
        "projection_source": projection_source,
        "projection_contract": projection_contract,
        "projector_version": projector_version,
        "inference_version": inference_version,
        "confidence_band": confidence_band,
        "code_source": code_source,
        "canonical_code_id": canonical_code_id,
        "validation_summary": validation_summary or {},
    }


def stamp(model: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
    """Attach (or replace) a model's provenance record. No-op on non-dict input."""
    if isinstance(model, dict):
        model["provenance"] = provenance
    return model


def stamp_if_absent(model: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
    """Stamp only if the model has no provenance yet — used by the legacy bridge so a
    model already stamped by the computed path is never relabelled `legacy_raw`."""
    if isinstance(model, dict) and not model.get("provenance"):
        model["provenance"] = provenance
    return model
