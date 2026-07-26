"""Offline retrieval -> assurance pipeline (curated corpus). NO delivery, no live solver here.

`resolve_and_assure(topic, produced_answer)` retrieves a curated candidate for the topic and runs the Slice-1A
assurance pipeline over it, using a SUPPLIED produced answer (a recorded/fixture solver output). Obtaining the
produced answer from the LIVE solver — and DELIVERING the result — are the live-regen steps that follow; this
proves retrieval + verification end-to-end offline.
"""
from __future__ import annotations

from typing import Any, Optional

from app.services.examples.retrieval.producer import try_resolve
from app.services.examples.retrieval.slice1a import run_slice1a


def resolve_and_assure(topic: dict[str, Any], produced_answer: str,
                       *, run_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Retrieve -> assure. Returns the Slice-1A report augmented with candidate/source provenance, or None if
    no curated candidate matches (a retrieval miss — the caller then escalates per §1.6)."""
    candidate = try_resolve(topic)
    if candidate is None:
        return None
    report = run_slice1a(candidate.payload, produced_answer, run_id=run_id)
    report["concept_key"] = candidate.concept_key
    report["sources"] = [{"source_id": s.source_id, "corpus_family": s.corpus_family,
                          "content_hash": s.snapshot.content_hash, "reuse_policy": s.reuse_policy}
                         for s in candidate.sources]
    return report
