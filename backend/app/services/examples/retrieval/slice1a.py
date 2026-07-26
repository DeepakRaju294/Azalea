"""Slice 1A — the assurance-only pipeline (§15). NO delivery, retrieval, or caching.

    PublishedInstance + produced answer -> InstanceFingerprintSet -> reproduction_check -> EvidenceRecord
    -> derive_instance_assurance -> InstanceAssuranceDecision -> report

`produced_answer` is supplied (a recorded/fixture solver output). Running the LIVE solver to obtain it is the
Phase-0/G0 go/no-go run (needs an API key) and is deliberately NOT part of this offline slice — this proves the
evidence->assurance machinery deterministically. Reuses the Phase-0 `reproduction_check`.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.services.examples.retrieval.compare import compare_answer
from app.services.examples.retrieval.fingerprints import build_instance_fingerprints
from app.services.examples.retrieval.model import (
    EvidenceRecord, PublishedInstance, VerifierDependency,
)
from app.services.examples.retrieval.validate import derive_instance_assurance

# frozen contract/policy identities for Phase 1A (would be bumped when the check's meaning changes).
REPRO_VERIFIER_VERSION = "reproduction_checker/1.0"
REPRO_CHECK_CONTRACT_VERSION = "repro-contract/v1"
ASSURANCE_POLICY_VERSION = "instance-assurance/v1"


def run_slice1a(inst: PublishedInstance, produced_answer: str, *, run_id: str | None = None) -> dict[str, Any]:
    """Deterministic assurance-only slice. Returns a report; raises nothing on refute/indecisive (those are
    valid outcomes, not errors)."""
    run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
    fp = build_instance_fingerprints(inst, check_contract_version=REPRO_CHECK_CONTRACT_VERSION)

    outcome = compare_answer(inst.published_answer, produced_answer, inst.comparison)
    record = EvidenceRecord(
        evidence_id=f"ev-{uuid.uuid4().hex[:12]}", check="published_answer_reproduction",
        status=outcome.status, subject_fingerprint=fp.evidence_subject,
        verifier_name="reproduction_checker", verifier_version=REPRO_VERIFIER_VERSION,
        check_contract_version=REPRO_CHECK_CONTRACT_VERSION, run_id=run_id,
        evidence={"published": inst.published_answer, "produced": produced_answer,
                  "comparison_kind": inst.comparison.kind, "detail": outcome.detail})

    deps = {"reproduction_checker": VerifierDependency(REPRO_VERIFIER_VERSION, REPRO_CHECK_CONTRACT_VERSION)}
    decision = derive_instance_assurance(
        assurance_id=f"as-{uuid.uuid4().hex[:12]}", run_id=run_id, subject_fingerprint=fp.evidence_subject,
        records=[record], verification_dependencies=deps, assurance_policy_version=ASSURANCE_POLICY_VERSION,
        subject_kind="published_instance")

    return {
        "target": inst.target,
        "level": decision.level,
        "reproduction_status": record.status,
        "comparison_kind": inst.comparison.kind,
        "fingerprints": {"semantic": fp.semantic, "evidence_subject": fp.evidence_subject,
                         "presentation": fp.presentation, "comparison_policy": fp.comparison_policy},
        "assurance_id": decision.assurance_id,
        "run_id": run_id,
        "evidence_id": record.evidence_id,
        "detail": outcome.detail,
    }
