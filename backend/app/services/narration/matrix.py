"""Card-contract coverage matrix + eligibility gate (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §2/§2.1).

Every (card_type × narration_domain) cell is in exactly one canonical status: `defined` (contract written +
eligible), `not_applicable` (must never occur in v1), or `deferred_from_initial_rollout` (domain-compatible but
excluded until its contract + fact-source registry are complete). The eligibility gate runs at runtime AFTER
blueprint resolution and BEFORE narration/render-model compilation, deciding per planned card: proceed / prune /
withhold / safety-failure.

`domain` here is the coarse *narration domain* (coding · math · science · concept). Map a fine/family domain via
`narration_domain_of()` (expository → concept). The matrix is the spec table; the live-inventory reconciliation
(does every emitted blueprint card appear here?) is the Phase-2A audit and is asserted in tests.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.domain_classifier import gate_family_of

# --- canonical status enum (code-facing, §2) --------------------------------------------------------------
DEFINED = "defined"
NOT_APPLICABLE = "not_applicable"
DEFERRED = "deferred_from_initial_rollout"

NARRATION_DOMAINS = ("coding", "math", "science", "concept")

# Abbreviations for the table below.
_D, _NA, _DEF = DEFINED, NOT_APPLICABLE, DEFERRED

# (card_type) -> {coding, math, science, concept} status. Straight from the §2 matrix.
CARD_CONTRACT_MATRIX: dict[str, dict[str, str]] = {
    #                    coding  math   science  concept
    "background":            {"coding": _D,  "math": _D,  "science": _D,  "concept": _D},
    "components_terms":      {"coding": _D,  "math": _D,  "science": _D,  "concept": _D},
    "process":               {"coding": _D,  "math": _D,  "science": _D,  "concept": _D},
    "worked_example":        {"coding": _D,  "math": _D,  "science": _D,  "concept": _D},
    "edge_case":             {"coding": _D,  "math": _D,  "science": _D,  "concept": _D},
    "practice":              {"coding": _D,  "math": _D,  "science": _D,  "concept": _D},
    "formula_breakdown":     {"coding": _NA, "math": _DEF, "science": _DEF, "concept": _NA},
    "proof_plan":            {"coding": _NA, "math": _DEF, "science": _NA, "concept": _NA},
    "code_walkthrough":      {"coding": _DEF, "math": _NA, "science": _NA, "concept": _NA},
    "complexity_analysis":   {"coding": _D,  "math": _NA, "science": _NA, "concept": _NA},
    "comparison":            {"coding": _DEF, "math": _DEF, "science": _DEF, "concept": _DEF},
    "roadmap":               {"coding": _DEF, "math": _DEF, "science": _DEF, "concept": _DEF},
    "prerequisites":         {"coding": _DEF, "math": _DEF, "science": _DEF, "concept": _DEF},
}


def narration_domain_of(domain: str | None) -> str | None:
    """Coarse narration domain (coding · math · science · concept) for a fine/family/alias `domain`. Reuses the
    Phase-0 family resolver; the expository family surfaces as the learner-facing `concept`. Returns None for a
    non-gating domain (mixed/unknown) — narration then has no domain contract to enforce."""
    family = gate_family_of(domain)
    if family == "expository":
        return "concept"
    return family or None


def card_status(card_type: str, domain: str) -> str | None:
    """The matrix status for a (card_type, narration_domain) cell. `domain` may be fine/family/coarse — it is
    normalized. None when the card_type is unknown or the domain is non-gating."""
    nd = narration_domain_of(domain) or (domain if domain in NARRATION_DOMAINS else None)
    if nd is None:
        return None
    return CARD_CONTRACT_MATRIX.get(str(card_type or "").strip().lower(), {}).get(nd)


# --- eligibility gate (§2.1) ------------------------------------------------------------------------------
# Actions the gate can return.
PROCEED = "proceed"                 # defined + contract/fact-sources ready → narrate/render
PRUNE = "prune"                     # a blueprint-OPTIONAL deferred card → drop deterministically
WITHHOLD = "withhold"              # required-but-not-ready (deferred-required or defined-not-registered)
SAFETY_FAILURE = "safety_failure"  # not_applicable card appeared → domain_card_safety_validation failure


@dataclass(frozen=True)
class EligibilityDecision:
    action: str          # PROCEED | PRUNE | WITHHOLD | SAFETY_FAILURE
    status: str | None   # the matrix status that drove it
    reason: str          # machine-readable reason code (telemetry)


def evaluate_card(
    card_type: str,
    domain: str,
    *,
    blueprint_optional: bool,
    contract_registered: bool = False,
    fact_sources_ready: bool = False,
) -> EligibilityDecision:
    """Evaluate one planned card against its (card_type, narration_domain) status (§2.1).

    - `defined`  → PROCEED only when its narration contract AND required fact-source entries are registered;
                   otherwise WITHHOLD (`contract_or_fact_source_missing`) — never fall back to generic narration.
    - `not_applicable` → SAFETY_FAILURE (`not_applicable_card`) — the card must never have been planned.
    - `deferred` → optional blueprint card ⇒ PRUNE (`deferred_card_pruned`); required blueprint card ⇒ WITHHOLD
                   (`deferred_required_blocks_rollout`) — do NOT silently prune, and never generic-narrate it.
    - unknown card/domain ⇒ WITHHOLD (`unmapped_card`) fail-closed.
    """
    status = card_status(card_type, domain)
    if status is None:
        return EligibilityDecision(WITHHOLD, None, "unmapped_card")
    if status == NOT_APPLICABLE:
        return EligibilityDecision(SAFETY_FAILURE, status, "not_applicable_card")
    if status == DEFERRED:
        if blueprint_optional:
            return EligibilityDecision(PRUNE, status, "deferred_card_pruned")
        return EligibilityDecision(WITHHOLD, status, "deferred_required_blocks_rollout")
    # DEFINED
    if contract_registered and fact_sources_ready:
        return EligibilityDecision(PROCEED, status, "contract_ready")
    return EligibilityDecision(WITHHOLD, status, "contract_or_fact_source_missing")
