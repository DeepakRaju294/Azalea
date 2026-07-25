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

from app.services.examples.retrieval.fingerprints import build_instance_fingerprints
from app.services.examples.retrieval.model import (
    EvidenceRecord, PublishedInstance, VerifierDependency,
)
from app.services.examples.retrieval.validate import derive_instance_assurance
from app.services.examples.retrieval_verify import reproduction_check

# frozen contract/policy identities for Phase 1A (would be bumped when the check's meaning changes).
REPRO_VERIFIER_VERSION = "reproduction_checker/1.0"
REPRO_CHECK_CONTRACT_VERSION = "repro-contract/v1"
ASSURANCE_POLICY_VERSION = "instance-assurance/v1"

_STATUS = {True: "confirm", False: "refute", None: "indecisive"}


def _comparison_params(inst: PublishedInstance) -> tuple[float, bool]:
    """Derive reproduction_check params from the answer's comparison contract."""
    rel_tol = 0.01
    if inst.comparison.kind == "relative_tolerance" and inst.comparison.tolerance:
        try:
            rel_tol = float(inst.comparison.tolerance)
        except (TypeError, ValueError):
            rel_tol = 0.01
    require_unit = inst.comparison.unit_semantics != "dimensionless" and inst.comparison.unit_dimension != ""
    return rel_tol, require_unit


def run_slice1a(inst: PublishedInstance, produced_answer: str, *, run_id: str | None = None) -> dict[str, Any]:
    """Deterministic assurance-only slice. Returns a report; raises nothing on refute/indecisive (those are
    valid outcomes, not errors)."""
    run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
    fp = build_instance_fingerprints(inst, check_contract_version=REPRO_CHECK_CONTRACT_VERSION)
    rel_tol, require_unit = _comparison_params(inst)

    result = reproduction_check(inst.published_answer, produced_answer,
                                rel_tol=rel_tol, require_unit_match=require_unit)
    record = EvidenceRecord(
        evidence_id=f"ev-{uuid.uuid4().hex[:12]}", check="published_answer_reproduction",
        status=_STATUS[result.matched], subject_fingerprint=fp.evidence_subject,
        verifier_name="reproduction_checker", verifier_version=REPRO_VERIFIER_VERSION,
        check_contract_version=REPRO_CHECK_CONTRACT_VERSION, run_id=run_id,
        evidence={"published": inst.published_answer, "produced": produced_answer,
                  "unit_status": result.unit_status, "detail": result.detail})

    deps = {"reproduction_checker": VerifierDependency(REPRO_VERIFIER_VERSION, REPRO_CHECK_CONTRACT_VERSION)}
    decision = derive_instance_assurance(
        assurance_id=f"as-{uuid.uuid4().hex[:12]}", run_id=run_id, subject_fingerprint=fp.evidence_subject,
        records=[record], verification_dependencies=deps, assurance_policy_version=ASSURANCE_POLICY_VERSION,
        subject_kind="published_instance")

    return {
        "target": inst.target,
        "level": decision.level,
        "reproduction_status": record.status,
        "unit_status": result.unit_status,
        "fingerprints": {"semantic": fp.semantic, "evidence_subject": fp.evidence_subject,
                         "presentation": fp.presentation, "comparison_policy": fp.comparison_policy},
        "assurance_id": decision.assurance_id,
        "run_id": run_id,
        "evidence_id": record.evidence_id,
        "detail": result.detail,
    }
