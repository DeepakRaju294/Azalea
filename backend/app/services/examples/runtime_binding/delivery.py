"""Derived trust level (§9) + canonical delivery serialization (§5.10) — Milestone C unit 10c, pure.

Both are decision-independent pure functions. The trust level is derived from execution route, contract
authority, and the verification vector — never asserted by the binding. The canonical delivery payload is the
VERSIONED serialization of the exact structured lesson payload handed to the frontend (structured claims +
card links), NOT a DOM/HTML/layout hash; its `canonical_delivery_serialization_version` pins key ordering,
number/unit encoding, null omission, and list-order so a conformant frontend renderer can be proven to
preserve semantic identity without freezing client-side layout.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Literal

from app.services.examples.runtime_binding.evidence import EvidencePackage
from app.services.examples.runtime_binding.verification import VerificationVector

ExecutionRoute = Literal["registered_adapter", "gen_foundation", "runtime_binding"]
ContractAuthority = Literal["reviewed", "authoritative_retrieval", "user_source", "unresolved"]

DerivedTrustLevel = Literal[
    "reviewed_adapter",
    "verified_gen_foundation",
    "reviewed_contract_runtime_binding",
    "grounded_runtime_binding",
    "user_source_grounded_binding",
    "mechanically_verified_only",
    "illustrative",
    "withheld",
]

CANONICAL_DELIVERY_SERIALIZATION_VERSION = 1


def derived_trust_level(
    execution_route: ExecutionRoute,
    contract_authority: ContractAuthority,
    verification: VerificationVector,
) -> DerivedTrustLevel:
    """Spec §9. Runtime binding earns `reviewed_contract_runtime_binding` only with a reviewed contract, a
    `reviewed_match` resolution, and a fully passing vector; a non-reviewed-match resolution caps at
    `mechanically_verified_only`; a failed vector is `withheld`."""
    if not verification.computationally_sound:
        return "withheld"
    if execution_route == "registered_adapter":
        return "reviewed_adapter"
    if execution_route == "gen_foundation":
        return "verified_gen_foundation"
    # runtime_binding: a non-reviewed-match resolution caps at the diagnostic level (v1 withholds it as a
    # separate shipping policy — the derived LABEL is still mechanically_verified_only per §9).
    if verification.resolution_validity != "reviewed_match":
        return "mechanically_verified_only"
    if contract_authority == "reviewed":
        return "reviewed_contract_runtime_binding"
    if contract_authority == "authoritative_retrieval":
        return "grounded_runtime_binding"
    if contract_authority == "user_source":
        return "user_source_grounded_binding"
    return "mechanically_verified_only"


def _canon_number(text: str) -> str:
    """Stable numeric encoding: an integer-valued display drops the trailing '.0'; otherwise unchanged."""
    if text.endswith(".0"):
        return text[:-2]
    return text


def canonical_delivery_payload(package: EvidencePackage) -> dict:
    """The structured, frontend-facing payload — deterministic, layout-free. Only structured claims and their
    evidence references travel; prose is not authoritative and is not part of the digest."""
    def norm(s: str) -> str:
        return unicodedata.normalize("NFC", s)

    cards = [
        {
            "card_id": link.card_id,
            "checkpoint_ids": list(link.checkpoint_ids),
            "trace_step_ids": list(link.trace_step_ids),
            "structured_claims": [
                {
                    "claim_kind": claim.claim_kind,
                    "display_payload": norm(claim.display_payload),
                    "evidence_ref": claim.evidence_ref,
                }
                for claim in link.structured_claims
            ],
        }
        for link in package.card_links
    ]
    return {
        "serialization_version": CANONICAL_DELIVERY_SERIALIZATION_VERSION,
        "evidence_id": package.evidence_id,
        "evidence_digest": package.evidence_digest,
        "problem": norm(package.problem),
        "result": {"value": _canon_number(package.result_display), "unit": norm(package.result_unit)},
        "cards": cards,
    }


def canonical_delivery_json(package: EvidencePackage) -> str:
    return json.dumps(
        canonical_delivery_payload(package), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def canonical_delivery_payload_digest(package: EvidencePackage) -> str:
    return hashlib.sha256(canonical_delivery_json(package).encode("utf-8")).hexdigest()
