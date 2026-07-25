"""Reviewed contract fixtures for Milestone B (spec §17.2 group B).

Three reviewed `ConceptContract`s deliberately ABSENT from the live registered adapter / FormulaSpec manifest,
so the offline end-to-end test exercises a genuine registered-lookup MISS before runtime binding runs
(each title was checked against `route_adapter` and returns no registered owner):

  1. single-output division with a nonzero-domain constraint     (volumetric flow rate, Q = V / t)
  2. nested add/multiply with a dimensional convention           (total charge, Q = i1 t1 + i2 t2)
  3. integer-power with a physical applicability condition       (free-fall distance, d = 1/2 g t^2)

`test_runtime_binding_contract.py` asserts each stays absent from the live routing manifest and FAILS if
future catalog growth registers one — the anti-drift guard the spec requires.
"""

from __future__ import annotations

from fractions import Fraction

from app.services.examples.runtime_binding.contract import (
    ConceptContract,
    GroundedArtifact,
    NormalizedRelationship,
    SymbolContract,
)
from app.services.examples.runtime_binding.resolution import (
    ContractResolutionEntry,
    ContractResolutionRegistry,
)

VOLUMETRIC_FLOW_RATE = ConceptContract(
    contract_id="volumetric_flow_rate@1",
    version=1,
    contract_concept_id="volumetric_flow_rate",
    variant="rate_from_volume_time",
    definition=GroundedArtifact(
        "vfr:def", "definition",
        "Volumetric flow rate is the volume that passes a point divided by the time taken.", "reviewed:fluids",
    ),
    relationship=NormalizedRelationship("vfr:Q", "direct_formula_calculation", "V / t", "Q"),
    symbols=(
        SymbolContract("V", "input", "m^3", "volume transported", Fraction(1), Fraction(1000)),
        SymbolContract("t", "input", "s", "elapsed time", Fraction(1), Fraction(600)),
        SymbolContract("Q", "output", "m^3/s", "volumetric flow rate"),
    ),
    applicability_conditions=(
        GroundedArtifact("vfr:app", "applicability", "Elapsed time must be nonzero.", "reviewed:fluids"),
    ),
    expected_interpretations=(
        GroundedArtifact("vfr:interp", "interpretation",
                         "The result is the steady volume crossing the section each second.", "reviewed:fluids"),
    ),
)

TOTAL_CHARGE = ConceptContract(
    contract_id="total_charge_two_currents@1",
    version=1,
    contract_concept_id="total_charge_two_currents",
    variant="charge_from_two_currents",
    definition=GroundedArtifact(
        "charge:def", "definition",
        "Charge delivered by a steady current is current times time; two currents contribute additively.",
        "reviewed:circuits",
    ),
    relationship=NormalizedRelationship(
        "charge:Q", "direct_formula_calculation", "i1 * t1 + i2 * t2", "Q"
    ),
    symbols=(
        SymbolContract("i1", "input", "A", "first branch current", Fraction(1), Fraction(20)),
        SymbolContract("t1", "input", "s", "first branch duration", Fraction(1), Fraction(60)),
        SymbolContract("i2", "input", "A", "second branch current", Fraction(1), Fraction(20)),
        SymbolContract("t2", "input", "s", "second branch duration", Fraction(1), Fraction(60)),
        SymbolContract("Q", "output", "A*s", "total charge delivered"),
    ),
    assumptions=(
        GroundedArtifact("charge:assume", "assumption",
                         "Each branch current is steady over its own interval.", "reviewed:circuits"),
    ),
    conventions=(
        GroundedArtifact("charge:conv", "convention",
                         "Both currents are counted positive in the same direction into the node.",
                         "reviewed:circuits"),
    ),
)

FREE_FALL_DISTANCE = ConceptContract(
    contract_id="free_fall_distance@1",
    version=1,
    contract_concept_id="free_fall_distance",
    variant="distance_from_rest",
    definition=GroundedArtifact(
        "free_fall:def", "definition",
        "An object released from rest falls a distance of one half g t squared in time t.", "reviewed:kinematics",
    ),
    relationship=NormalizedRelationship("free_fall:d", "direct_formula_calculation", "(1/2) * g * t**2", "d"),
    symbols=(
        SymbolContract("t", "input", "s", "time falling", Fraction(1), Fraction(10)),
        SymbolContract("g", "constant", "m/s^2", "gravitational acceleration"),
        SymbolContract("d", "output", "m", "distance fallen"),
    ),
    constants={"g": "49/5"},   # 9.8 m/s^2 exactly
    applicability_conditions=(
        GroundedArtifact("free_fall:app", "applicability",
                         "The object starts from rest and air resistance is neglected.", "reviewed:kinematics"),
    ),
)

MILESTONE_B_CONTRACTS: dict[str, ConceptContract] = {
    c.contract_id: c for c in (VOLUMETRIC_FLOW_RATE, TOTAL_CHARGE, FREE_FALL_DISTANCE)
}


def _entry(contract: ConceptContract, aliases: tuple[str, ...]) -> ContractResolutionEntry:
    return ContractResolutionEntry(
        scope_concept_id=contract.contract_concept_id,
        reviewed_aliases=aliases,
        contract_concept_id=contract.contract_concept_id,
        contract_id=contract.contract_id,
        allowed_variants=(contract.variant,),
        default_variant=contract.variant,
        version=contract.version,
        review_provenance=f"milestone_b_fixture:{contract.contract_id}",
    )


MILESTONE_B_REGISTRY = ContractResolutionRegistry(
    version=1,
    entries=[
        _entry(VOLUMETRIC_FLOW_RATE, ("volumetric flow rate", "computing volumetric flow rate")),
        _entry(TOTAL_CHARGE, ("total charge from two currents", "combined charge of two currents")),
        _entry(FREE_FALL_DISTANCE, ("free fall distance", "free-fall distance from rest")),
    ],
)

# Titles used by the absence assertion (must NOT route to any registered adapter / FormulaSpec).
MILESTONE_B_ABSENCE_TITLES: tuple[str, ...] = (
    "Volumetric Flow Rate",
    "Total Charge From Two Currents",
    "Free-Fall Distance From Rest",
)
