"""Generic exercise ownership + preparation lifecycle (spec §2.5, §13.2) — Milestone C, unit 10a/10b.

Decision-INDEPENDENT domain logic, pure and in-memory: no database, no live route, no frontend. Persistence
(the four tables) and certification/solver wiring layer ON TOP of this once the §19 migration/latency
decisions are closed. Runtime binding is the FIRST consumer of a generic exercise-ownership model.

Ownership is transactional: at most one `active` claim exists per `(path_plan_version, ownership_tuple)`, and
activating a replacement atomically supersedes the prior. Claim currency (the freeze-time check, §6.6) is true
only while a claim is still the active, non-superseded owner — a path re-certification or re-arbitration
between certification and freeze invalidates it. `path_plan_version` is a deterministic digest of the certified
scope plan because no explicit plan-version column exists yet (§2.5).
"""

from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Literal, Optional

# ----------------------------------------------------------------------------------------------------------
# path plan version


def path_plan_version(certified_topics: Iterable[dict[str, Any]]) -> str:
    """Deterministic digest of the certified scope plan: each topic's id, owned scope, role, and ORDER.
    Any re-certification that changes this serialization yields a new version and supersedes the plan's
    claims. A future explicit plan-version column can replace this digest without changing claim semantics."""
    canonical = [
        {
            "topic_id": str(t.get("topic_id", t.get("id", ""))),
            "scope_in": sorted(str(s) for s in (t.get("scope_in") or [])),
            "role": str(t.get("role", "")),
            "order": i,
        }
        for i, t in enumerate(certified_topics)
    ]
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "ppv_" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


# ----------------------------------------------------------------------------------------------------------
# exercise ownership


@dataclass(frozen=True)
class OwnershipTuple:
    concept_contract_id: str
    variant: str
    grammar_id: str
    lesson_intent_kind: str


@dataclass(frozen=True)
class ExerciseClaim:
    claim_id: str
    claim_version: int
    path_plan_version: str
    ownership_tuple: OwnershipTuple
    owner_topic_id: str
    status: Literal["active", "lost", "superseded"]
    superseded_by_claim_id: Optional[str]
    created_seq: int
    lost_to_topic_id: Optional[str] = None


class ClaimError(ValueError):
    pass


class ClaimLedger:
    """In-memory transactional claim ledger. `claim()` is the arbitration point: the first topic to claim a
    `(path_plan_version, ownership_tuple)` wins (`active`); a different topic claiming the same key `lost`s and
    records the winner. A new `path_plan_version` is a fresh key; `supersede_plan()` retires an old plan's
    active claims when it re-certifies."""

    def __init__(self) -> None:
        self._active: dict[tuple[str, OwnershipTuple], str] = {}
        self._claims: dict[str, ExerciseClaim] = {}
        self._seq = itertools.count(1)

    def _key(self, ppv: str, tup: OwnershipTuple) -> tuple[str, OwnershipTuple]:
        return (ppv, tup)

    def claim(self, ppv: str, tup: OwnershipTuple, owner_topic_id: str) -> ExerciseClaim:
        key = self._key(ppv, tup)
        active_id = self._active.get(key)
        if active_id is not None:
            active = self._claims[active_id]
            if active.owner_topic_id == owner_topic_id:
                return active                              # idempotent re-claim by the same owner
            seq = next(self._seq)
            lost = ExerciseClaim(
                claim_id=f"claim_{seq}", claim_version=1, path_plan_version=ppv, ownership_tuple=tup,
                owner_topic_id=owner_topic_id, status="lost", superseded_by_claim_id=None,
                created_seq=seq, lost_to_topic_id=active.owner_topic_id,
            )
            self._claims[lost.claim_id] = lost
            return lost
        seq = next(self._seq)
        won = ExerciseClaim(
            claim_id=f"claim_{seq}", claim_version=1, path_plan_version=ppv, ownership_tuple=tup,
            owner_topic_id=owner_topic_id, status="active", superseded_by_claim_id=None, created_seq=seq,
        )
        self._claims[won.claim_id] = won
        self._active[key] = won.claim_id
        return won

    def is_current(self, claim: ExerciseClaim) -> bool:
        """Claim currency (§6.6): the claim is still the active, non-superseded owner of its key."""
        stored = self._claims.get(claim.claim_id)
        if stored is None or stored.status != "active":
            return False
        return self._active.get(self._key(stored.path_plan_version, stored.ownership_tuple)) == stored.claim_id

    def supersede_plan(self, old_ppv: str) -> None:
        """Re-certification to a new plan version retires every active claim of the old plan version."""
        for key, claim_id in list(self._active.items()):
            if key[0] == old_ppv:
                claim = self._claims[claim_id]
                self._claims[claim_id] = replace(claim, status="superseded")
                del self._active[key]

    def get(self, claim_id: str) -> Optional[ExerciseClaim]:
        return self._claims.get(claim_id)


# ----------------------------------------------------------------------------------------------------------
# preparation lifecycle

PreparationStatus = Literal["preparing", "ready", "failed", "stale"]


@dataclass(frozen=True)
class PreparationIdentity:
    topic_id: str
    path_plan_version: str
    sibling_claim_id: str
    sibling_claim_version: int
    contract_version: int
    grammar_version: int
    pedagogical_policy_version: int
    resolution_registry_version: int
    resolution_entry_version: int
    binding_digest: str
    execution_environment_digest: str

    def digest(self) -> str:
        payload = {k: getattr(self, k) for k in self.__dataclass_fields__}
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return "prepid_" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class PreparedRuntimeBinding:
    preparation_id: str
    identity: PreparationIdentity
    preparation_identity_digest: str
    status: PreparationStatus
    status_version: int
    safety_block_version: int
    superseded_by_preparation_id: Optional[str]
    failure_reason: str
    created_seq: int


class PreparationError(ValueError):
    pass


class PreparationLedger:
    """In-memory preparation lifecycle. Status transitions use compare-and-swap on `status_version`: a worker
    that read an older version cannot mark itself ready. At most one non-superseded `preparing|ready`
    preparation may exist per identity digest. A safety incident bumps a global `safety_block_version` and
    stales affected preparations. Retrying a failed preparation creates a NEW preparation; it never mutates a
    failed artifact into a ready one (§13.2)."""

    def __init__(self) -> None:
        self._preps: dict[str, PreparedRuntimeBinding] = {}
        self._active_by_identity: dict[str, str] = {}
        self._seq = itertools.count(1)
        self._safety_block_version = 0

    @property
    def safety_block_version(self) -> int:
        return self._safety_block_version

    def request(self, identity: PreparationIdentity) -> PreparedRuntimeBinding:
        digest = identity.digest()
        existing_id = self._active_by_identity.get(digest)
        if existing_id is not None:
            existing = self._preps[existing_id]
            if existing.status in ("preparing", "ready"):
                return existing                            # idempotent: reuse the live preparation
        seq = next(self._seq)
        prep = PreparedRuntimeBinding(
            preparation_id=f"prep_{seq}", identity=identity, preparation_identity_digest=digest,
            status="preparing", status_version=1, safety_block_version=self._safety_block_version,
            superseded_by_preparation_id=None, failure_reason="", created_seq=seq,
        )
        self._preps[prep.preparation_id] = prep
        self._active_by_identity[digest] = prep.preparation_id
        return prep

    def _cas(self, prep: PreparedRuntimeBinding, expected_status_version: int) -> PreparedRuntimeBinding:
        current = self._preps[prep.preparation_id]
        if current.status_version != expected_status_version:
            raise PreparationError(
                f"stale status_version for {prep.preparation_id}: "
                f"expected {expected_status_version}, current {current.status_version}"
            )
        return current

    def mark_ready(
        self, prep: PreparedRuntimeBinding, expected_status_version: int, claim_ledger: ClaimLedger,
        claim: ExerciseClaim,
    ) -> PreparedRuntimeBinding:
        current = self._cas(prep, expected_status_version)
        if current.status != "preparing":
            raise PreparationError(f"cannot mark_ready from {current.status}")
        if current.safety_block_version != self._safety_block_version:
            raise PreparationError("safety block advanced since preparation started")
        if not claim_ledger.is_current(claim):
            raise PreparationError("authorizing claim is no longer current")
        updated = replace(current, status="ready", status_version=current.status_version + 1)
        self._preps[updated.preparation_id] = updated
        return updated

    def mark_failed(self, prep: PreparedRuntimeBinding, expected_status_version: int, reason: str) -> PreparedRuntimeBinding:
        current = self._cas(prep, expected_status_version)
        updated = replace(current, status="failed", status_version=current.status_version + 1, failure_reason=reason)
        self._preps[updated.preparation_id] = updated
        self._active_by_identity.pop(current.preparation_identity_digest, None)
        return updated

    def mark_stale(self, prep: PreparedRuntimeBinding, reason: str) -> PreparedRuntimeBinding:
        current = self._preps[prep.preparation_id]
        updated = replace(current, status="stale", status_version=current.status_version + 1, failure_reason=reason)
        self._preps[updated.preparation_id] = updated
        self._active_by_identity.pop(current.preparation_identity_digest, None)
        return updated

    def bump_safety_block(self) -> int:
        """A safety incident: increment the global version and stale every live preparation."""
        self._safety_block_version += 1
        for prep in list(self._preps.values()):
            if prep.status in ("preparing", "ready"):
                self.mark_stale(prep, "safety_block_incremented")
        return self._safety_block_version

    def retry(self, failed: PreparedRuntimeBinding) -> PreparedRuntimeBinding:
        current = self._preps[failed.preparation_id]
        if current.status not in ("failed", "stale"):
            raise PreparationError(f"can only retry a failed/stale preparation, not {current.status}")
        return self.request(current.identity)              # brand-new preparation; failed one is untouched

    def get(self, preparation_id: str) -> Optional[PreparedRuntimeBinding]:
        return self._preps.get(preparation_id)
