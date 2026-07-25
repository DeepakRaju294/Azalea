"""Immutable evidence package (spec §5.9, §5.10) — in-memory / fixture only for Milestone B.

After computational/conceptual verification passes, the authoritative pre-narration facts are frozen into an
immutable `EvidencePackage` with an `evidence_digest`. Cards are a VIEW over it, never a second solution; each
`CardEvidenceLink` carries structured claims that reference the package by id. Regeneration creates a new
evidence id/digest — the store is insert-only (no production tables in Milestone B).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from app.services.examples.runtime_binding.binding import ValidatedBinding
from app.services.examples.runtime_binding.generation import GeneratedInstance
from app.services.examples.runtime_binding.trace import TraceBundle
from app.services.examples.runtime_binding.verification import VerificationVector


class EvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class StructuredEvidenceClaim:
    claim_kind: str                       # formula | assumption | decision | result
    display_payload: str
    evidence_ref: str


@dataclass(frozen=True)
class CardEvidenceLink:
    card_id: str
    checkpoint_ids: tuple[str, ...]
    trace_step_ids: tuple[str, ...]
    structured_claims: tuple[StructuredEvidenceClaim, ...]


@dataclass(frozen=True)
class EvidencePackage:
    evidence_id: str
    evidence_schema_version: int
    evidence_digest: str
    binding_digest: str
    instance_digest: str
    resolution_registry_version: int
    resolution_entry_version: int
    pedagogical_policy_version: int
    contract_id: str
    contract_version: int
    problem: str
    visible_givens: tuple[tuple[str, str], ...]
    final_result: str
    result_display: str
    result_unit: str
    trace_step_ids: tuple[str, ...]
    checkpoint_ids: tuple[str, ...]
    verification: VerificationVector
    card_links: tuple[CardEvidenceLink, ...]


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _evidence_digest(fields: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(fields).encode("utf-8")).hexdigest()


def _verification_fingerprint(v: VerificationVector) -> dict[str, Any]:
    return {
        "resolution_validity": v.resolution_validity,
        "specification_validity": v.specification_validity,
        "execution_validity": v.execution_validity,
        "conceptual_validity": v.conceptual_validity,
        "problem_solvability": v.problem_solvability,
        "pedagogical_fitness": v.pedagogical_fitness,
        "narration_fidelity": v.narration_fidelity,
        "checks": [[c.check_id, c.check_type, c.status] for c in v.checks],
    }


def _default_card_links(bundle: TraceBundle, contract_id: str) -> tuple[CardEvidenceLink, ...]:
    """One structured card per checkpoint. Structured claims (formula/result) reference the package by the
    step id they descend from; prose is not authored here (pre-narration)."""
    links: list[CardEvidenceLink] = []
    for step, cp in zip(bundle.trace.steps, bundle.checkpoints):
        kind = "result" if step.operation == "compute" else ("formula" if step.operation == "substitute" else "decision")
        claim = StructuredEvidenceClaim(kind, step.decision, f"{contract_id}:{step.id}")
        links.append(CardEvidenceLink(
            card_id=f"card_{step.id}",
            checkpoint_ids=(cp.checkpoint_id,),
            trace_step_ids=(step.id,),
            structured_claims=(claim,),
        ))
    return tuple(links)


def freeze_evidence(
    binding: ValidatedBinding,
    instance: GeneratedInstance,
    bundle: TraceBundle,
    verification: VerificationVector,
) -> EvidencePackage:
    if not verification.passed:
        raise EvidenceError(
            f"{binding.contract.contract_id}: cannot freeze evidence on a failed verification vector"
        )
    contract = binding.contract
    card_links = _default_card_links(bundle, contract.contract_id)
    core = {
        "schema_version": 1,
        "binding_digest": binding.binding_digest,
        "instance_digest": instance.instance_digest,
        "resolution_registry_version": binding.resolution.resolution_registry_version,
        "resolution_entry_version": binding.resolution.resolution_entry_version,
        "pedagogical_policy_version": instance.pedagogical_policy_version,
        "contract_id": contract.contract_id,
        "contract_version": contract.version,
        "problem": bundle.trace.problem,
        "visible_givens": list(instance.visible_values),
        "final_result": instance.expected_result,
        "result_display": instance.result_display,
        "result_unit": contract.output.unit,
        "trace_step_ids": [s.id for s in bundle.trace.steps],
        "checkpoint_ids": [cp.checkpoint_id for cp in bundle.checkpoints],
        "verification": _verification_fingerprint(verification),
        "card_links": [
            [l.card_id, list(l.checkpoint_ids), list(l.trace_step_ids),
             [[c.claim_kind, c.display_payload, c.evidence_ref] for c in l.structured_claims]]
            for l in card_links
        ],
    }
    digest = _evidence_digest(core)
    return EvidencePackage(
        evidence_id=f"ev_{digest[:16]}",
        evidence_schema_version=1,
        evidence_digest=digest,
        binding_digest=binding.binding_digest,
        instance_digest=instance.instance_digest,
        resolution_registry_version=binding.resolution.resolution_registry_version,
        resolution_entry_version=binding.resolution.resolution_entry_version,
        pedagogical_policy_version=instance.pedagogical_policy_version,
        contract_id=contract.contract_id,
        contract_version=contract.version,
        problem=bundle.trace.problem,
        visible_givens=instance.visible_values,
        final_result=instance.expected_result,
        result_display=instance.result_display,
        result_unit=contract.output.unit,
        trace_step_ids=tuple(s.id for s in bundle.trace.steps),
        checkpoint_ids=tuple(cp.checkpoint_id for cp in bundle.checkpoints),
        verification=verification,
        card_links=card_links,
    )


class InMemoryEvidenceStore:
    """Insert-only in-memory store. A re-freeze of identical inputs yields the same digest and is idempotent;
    a different digest is a distinct record. No production persistence (Milestone C)."""

    def __init__(self) -> None:
        self._by_id: dict[str, EvidencePackage] = {}

    def insert(self, package: EvidencePackage) -> None:
        existing = self._by_id.get(package.evidence_id)
        if existing is not None and existing.evidence_digest != package.evidence_digest:
            raise EvidenceError(f"evidence id collision with differing digest: {package.evidence_id}")
        self._by_id[package.evidence_id] = package

    def get(self, evidence_id: str) -> EvidencePackage | None:
        return self._by_id.get(evidence_id)

    def __len__(self) -> int:
        return len(self._by_id)
