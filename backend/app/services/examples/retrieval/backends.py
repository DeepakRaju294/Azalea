"""Pluggable source backends behind one retrieval seam.

Acquisition is decoupled from verification: every backend returns the SAME `CandidateArtifact`, which the
(source-agnostic) verification pipeline then judges. Today only the offline curated corpus is live; the
computational-API and web-fetch backends drop in here when their online access + keys are available, WITHOUT
touching the pipeline. `try_resolve` walks the registered backends in priority order and returns the first hit.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from app.services.examples.retrieval import sources
from app.services.examples.retrieval.compute_backend import ComputationalApiBackend
from app.services.examples.retrieval.model import CandidateArtifact


@runtime_checkable
class SourceBackend(Protocol):
    name: str
    def fetch(self, topic: dict[str, Any]) -> Optional[CandidateArtifact]:
        """Return a candidate for this topic, or None on a miss. MUST be side-effect-free w.r.t. output and
        MUST fail closed (return None) rather than raise into generation."""
    # optional: `available(self) -> bool` — a backend that needs config (e.g. an API key) reports False when
    # unconfigured, and resolve_candidate skips it. Backends without the method are always available.


class CuratedCorpusBackend:
    """Offline curated corpus (no network). The seed/fallback that always works."""
    name = "curated_corpus"

    def available(self) -> bool:
        return True

    def fetch(self, topic: dict[str, Any]) -> Optional[CandidateArtifact]:
        from app.services.examples.retrieval.producer import _concept_key  # local import avoids cycle
        key = _concept_key(topic)
        return sources.lookup(key) if key else None


# Priority order (§3): the online computational API is PRIMARY (authoritative computed answer); the curated
# corpus is the offline fallback. `compute_api` is UNAVAILABLE (skipped) until AZALEA_WOLFRAM_APPID is set, so
# with no key this reduces to corpus-only and changes nothing. web-fetch (where compute is N/A) appends later.
_BACKENDS: list[SourceBackend] = [ComputationalApiBackend(), CuratedCorpusBackend()]


def registered_backends() -> tuple[SourceBackend, ...]:
    return tuple(_BACKENDS)


def _is_available(backend: SourceBackend) -> bool:
    avail = getattr(backend, "available", None)
    try:
        return bool(avail()) if callable(avail) else True
    except Exception:  # noqa: BLE001
        return False


def resolve_candidate(topic: dict[str, Any]) -> tuple[Optional[CandidateArtifact], Optional[str]]:
    """First AVAILABLE backend that hits wins. Returns (candidate, backend_name) or (None, None). A backend
    that raises is treated as a miss (fail-closed) so acquisition can never break generation."""
    for backend in _BACKENDS:
        if not _is_available(backend):
            continue
        try:
            cand = backend.fetch(topic)
        except Exception:  # noqa: BLE001 - a backend failure is a miss, never a crash
            cand = None
        if cand is not None:
            return cand, backend.name
    return None, None
