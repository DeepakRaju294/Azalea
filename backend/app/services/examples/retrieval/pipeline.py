"""Offline retrieval -> (cache | assurance) pipeline. NO delivery, no live solver here.

Cache-first (§S2): if this exact instance was verified before, serve the cached contract WITHOUT re-fetching a
source or re-running the solver — `resolve_from_cache` needs no produced answer at all. On a cache miss,
`resolve_and_assure` runs the Slice-1A assurance over a SUPPLIED produced answer (a recorded/fixture solver
output) and caches a verified/provisional result. Obtaining the produced answer from the LIVE solver, and
DELIVERING, are the live-regen steps that follow.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Optional

from app.services.examples.retrieval.backends import resolve_candidate
from app.services.examples.retrieval.cache import CachedContract, VerifiedContractCache, default_cache
from app.services.examples.retrieval.fingerprints import build_instance_fingerprints
from app.services.examples.retrieval.model import CandidateArtifact
from app.services.examples.retrieval.slice1a import REPRO_CHECK_CONTRACT_VERSION, run_slice1a


def _fingerprint_subject(candidate: CandidateArtifact):
    return build_instance_fingerprints(candidate.payload, check_contract_version=REPRO_CHECK_CONTRACT_VERSION)


def _provenance(candidate: CandidateArtifact, backend: Optional[str]) -> dict[str, Any]:
    return {"concept_key": candidate.concept_key, "backend": backend,
            "sources": [{"source_id": s.source_id, "corpus_family": s.corpus_family,
                         "content_hash": s.snapshot.content_hash, "reuse_policy": s.reuse_policy}
                        for s in candidate.sources]}


def resolve_from_cache(topic: dict[str, Any], *, cache: Optional[VerifiedContractCache] = None
                       ) -> Optional[dict[str, Any]]:
    """Cache-only path: needs NO produced answer. Returns the cached report if this exact instance was verified
    before, else None (caller then fetches + runs the solver)."""
    cache = cache if cache is not None else default_cache()
    candidate, _backend = resolve_candidate(topic)
    if candidate is None:
        return None
    fp = _fingerprint_subject(candidate)
    hit = cache.get(fp.evidence_subject)
    if hit is None:
        return None
    return {"level": hit.level, "concept_key": hit.concept_key, "from_cache": True,
            "assurance_id": hit.assurance_id, "fingerprints": {"semantic": hit.semantic_fingerprint,
                                                               "evidence_subject": hit.subject_fingerprint},
            "provenance": dict(hit.provenance)}


def resolve_and_assure(topic: dict[str, Any], produced_answer: str, *, run_id: Optional[str] = None,
                       cache: Optional[VerifiedContractCache] = None) -> Optional[dict[str, Any]]:
    """Retrieve -> (cache hit | assure + cache). Returns the report + provenance, or None on a retrieval miss."""
    cache = cache if cache is not None else default_cache()
    candidate, backend = resolve_candidate(topic)
    if candidate is None:
        return None
    fp = _fingerprint_subject(candidate)

    cached = cache.get(fp.evidence_subject)
    if cached is not None and cached.level == "verified_reproduction":
        return {"level": cached.level, "concept_key": cached.concept_key, "from_cache": True,
                "assurance_id": cached.assurance_id,
                "fingerprints": {"semantic": cached.semantic_fingerprint,
                                 "evidence_subject": cached.subject_fingerprint},
                "provenance": dict(cached.provenance)}

    report = run_slice1a(candidate.payload, produced_answer, run_id=run_id)
    report["from_cache"] = False
    report.update(_provenance(candidate, backend))

    cache.put(CachedContract(
        concept_key=candidate.concept_key, subject_fingerprint=report["fingerprints"]["evidence_subject"],
        semantic_fingerprint=report["fingerprints"]["semantic"], level=report["level"],
        assurance_id=report["assurance_id"], assurance_policy_version="instance-assurance/v1",
        created_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        provenance=_provenance(candidate, backend)))
    return report
