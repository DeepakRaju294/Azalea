"""Evidence integrity + assurance derivation (§5, §5.1).

`validate_assurance_decision` is the SINGLE authority on 'does this evidence set earn this level' — evidence
only, NO shipping policy (the three policy layers stay separate). It runs at derivation (refuse to mint
invalid), catalog load, and delivery — defense in depth. `derive_instance_assurance` mints the correct level
from evidence and then validates it (so a mint can never produce something validation would reject).

Per-level policy (§5.1):
- verified_reproduction: subject_kind=published_instance; >=1 published_answer_reproduction=confirm over the
  subject; and NO reproduction refute over the same subject (confirm+refute = integrity failure, never verified).
- provisional: nothing confirming (a confirm would earn a stronger level), AND nothing refuting the candidate
  (a REFUTED candidate is discarded, never ships even provisionally).
- guided: no delivery-eligible confirmed evidence.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from app.services.examples.retrieval.model import (
    AssuranceStrength, EvidenceIntegrityError, EvidenceRecord, EvidenceRevocation,
    InstanceAssuranceDecision, InstanceAssuranceLevel, InstanceAssuranceProfile, VerifierDependency,
    VerifierName,
)

_REPRO = "published_answer_reproduction"


def _integrity(assurance: InstanceAssuranceDecision, records: Sequence[EvidenceRecord],
               revocations: Mapping[str, EvidenceRevocation]) -> None:
    """Fail-closed structural checks shared by every level."""
    cited = set(assurance.evidence_ids)
    have = {r.evidence_id for r in records}
    missing = cited - have
    if missing:
        raise EvidenceIntegrityError(f"missing assurance evidence: {sorted(missing)}")
    extra = have - cited
    if extra:
        raise EvidenceIntegrityError(f"records not cited by the decision: {sorted(extra)}")
    for r in records:
        if r.evidence_id in revocations:
            raise EvidenceIntegrityError(f"revoked evidence {r.evidence_id}")
        if r.run_id != assurance.run_id:
            raise EvidenceIntegrityError(f"evidence {r.evidence_id} from another run ({r.run_id})")
        dep = assurance.verification_dependencies.get(r.verifier_name)
        if dep is None or dep.verifier_version != r.verifier_version \
                or dep.check_contract_version != r.check_contract_version:
            raise EvidenceIntegrityError(f"verifier {r.verifier_name} version/contract not exactly bound")


def _repro_over_subject(records: Sequence[EvidenceRecord], subject: str, status: str) -> bool:
    return any(r.check == _REPRO and r.status == status and r.subject_fingerprint == subject for r in records)


def validate_assurance_decision(assurance: InstanceAssuranceDecision, records: Sequence[EvidenceRecord],
                                revocations: Mapping[str, EvidenceRevocation] | None = None) -> None:
    """Raise EvidenceIntegrityError unless `records` genuinely earn `assurance.level` for its subject."""
    revocations = revocations or {}
    _integrity(assurance, records, revocations)
    subject = assurance.subject_fingerprint

    confirm = _repro_over_subject(records, subject, "confirm")
    refute = _repro_over_subject(records, subject, "refute")

    if assurance.level == "verified_reproduction":
        if assurance.subject_kind != "published_instance":
            raise EvidenceIntegrityError("verified_reproduction requires subject_kind=published_instance")
        if refute:
            raise EvidenceIntegrityError("confirm+refute conflict on the same subject; never verified")
        if not confirm:
            raise EvidenceIntegrityError("verified_reproduction requires a confirming reproduction over subject")
        if assurance.profile.computational_check != "reproduction" \
                or assurance.profile.automated_strength != AssuranceStrength.REPRODUCED_INSTANCE:
            raise EvidenceIntegrityError("profile does not match verified_reproduction")
    elif assurance.level == "provisional":
        if confirm:
            raise EvidenceIntegrityError("evidence earns a stronger level; provisional not allowed")
        if refute:
            raise EvidenceIntegrityError("a refuted candidate never ships, not even provisionally")
        if assurance.profile.automated_strength != AssuranceStrength.PROVISIONAL:
            raise EvidenceIntegrityError("profile does not match provisional")
    elif assurance.level == "guided":
        if confirm:
            raise EvidenceIntegrityError("evidence earns a real example; guided not allowed")
        if assurance.profile.automated_strength != AssuranceStrength.GUIDED:
            raise EvidenceIntegrityError("profile does not match guided")
    else:  # pragma: no cover - Literal guards this
        raise EvidenceIntegrityError(f"unknown level {assurance.level}")


def derive_instance_assurance(*, assurance_id: str, run_id: str, subject_fingerprint: str,
                              records: Sequence[EvidenceRecord],
                              verification_dependencies: Mapping[VerifierName, VerifierDependency],
                              assurance_policy_version: str,
                              subject_kind: str = "published_instance") -> InstanceAssuranceDecision:
    """Mint the correct level from evidence, then validate (a mint can't produce something validation rejects).

    confirm (no refute) -> verified_reproduction ; refute -> the candidate is discarded -> guided (nothing to
    ship) ; indecisive/none -> provisional (producible but unconfirmed)."""
    confirm = _repro_over_subject(records, subject_fingerprint, "confirm")
    refute = _repro_over_subject(records, subject_fingerprint, "refute")
    has_indecisive = any(r.check == _REPRO and r.status == "indecisive"
                         and r.subject_fingerprint == subject_fingerprint for r in records)

    if confirm and not refute:
        level: InstanceAssuranceLevel = "verified_reproduction"
        profile = InstanceAssuranceProfile(AssuranceStrength.REPRODUCED_INSTANCE, "reproduction")
    elif refute:
        # proven-wrong candidate is discarded; with no shippable example the online floor is guided (tracked).
        level, profile = "guided", InstanceAssuranceProfile(AssuranceStrength.GUIDED, "none")
    elif has_indecisive:
        level, profile = "provisional", InstanceAssuranceProfile(AssuranceStrength.PROVISIONAL, "reproduction")
    else:
        level, profile = "guided", InstanceAssuranceProfile(AssuranceStrength.GUIDED, "none")

    decision = InstanceAssuranceDecision(
        assurance_id=assurance_id, run_id=run_id, subject_kind=subject_kind, level=level, profile=profile,
        subject_fingerprint=subject_fingerprint, assurance_policy_version=assurance_policy_version,
        verification_dependencies=dict(verification_dependencies),
        evidence_ids=tuple(r.evidence_id for r in records))
    validate_assurance_decision(decision, records)   # defense in depth: refuse to mint invalid
    return decision
