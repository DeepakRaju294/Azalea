"""Verified-contract cache (§10, §S2) — the amortization layer that stores VERIFIED RESULTS, not documents.

The first time a concept instance is verified, its tiny contract (fingerprints + assurance level + provenance)
is cached by `subject_fingerprint`. A repeat of the same instance is served from the cache WITHOUT re-fetching
a source or re-running the solver — the S2 saving, and the reason online retrieval never means "store
documents": we keep a few hundred bytes of verified contract per concept, never the source.

Monotonic (§10 issue 27): a stronger result overwrites a weaker one, never the reverse. Only delivery-eligible
levels are cached (verified_reproduction, provisional); `guided` (a refuted/empty outcome) is never cached.
Optional jsonl persistence (goal_plan_cache pattern) so the catalog survives restarts.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from app.services.examples.retrieval.model import AssuranceStrength, InstanceAssuranceLevel

_STRENGTH = {
    "verified_reproduction": AssuranceStrength.REPRODUCED_INSTANCE,
    "provisional": AssuranceStrength.PROVISIONAL,
    "guided": AssuranceStrength.GUIDED,
}
_CACHEABLE = {"verified_reproduction", "provisional"}   # guided is never cached


@dataclass(frozen=True)
class CachedContract:
    concept_key: str
    subject_fingerprint: str
    semantic_fingerprint: str
    level: InstanceAssuranceLevel
    assurance_id: str
    assurance_policy_version: str
    created_at: str
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @property
    def strength(self) -> int:
        return int(_STRENGTH.get(self.level, AssuranceStrength.GUIDED))


class VerifiedContractCache:
    def __init__(self, path: Optional[str] = None) -> None:
        self._by_subject: dict[str, CachedContract] = {}
        self._lock = threading.Lock()
        self._path = Path(path) if path else None
        if self._path and self._path.exists():
            self._load()

    def _load(self) -> None:
        assert self._path is not None
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                self._by_subject[json.loads(line)["subject_fingerprint"]] = CachedContract(**json.loads(line))
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

    def _append(self, entry: CachedContract) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry), ensure_ascii=False, sort_keys=True) + "\n")

    def get(self, subject_fingerprint: str) -> Optional[CachedContract]:
        with self._lock:
            return self._by_subject.get(subject_fingerprint)

    def put(self, entry: CachedContract) -> bool:
        """Insert iff cacheable AND strictly stronger than any existing entry for the same subject (monotonic).
        Returns True if stored."""
        if entry.level not in _CACHEABLE:
            return False
        with self._lock:
            existing = self._by_subject.get(entry.subject_fingerprint)
            if existing is not None and entry.strength <= existing.strength:
                return False
            self._by_subject[entry.subject_fingerprint] = entry
        self._append(entry)
        return True

    def __len__(self) -> int:
        return len(self._by_subject)

    def __bool__(self) -> bool:
        return True   # an EMPTY cache is still a valid cache — never falsy (guards `cache or default` misuse)


_DEFAULT: Optional[VerifiedContractCache] = None


def default_cache() -> VerifiedContractCache:
    """Process-wide cache, persisted to AZALEA_RETRIEVAL_CACHE_PATH when set."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = VerifiedContractCache(os.getenv("AZALEA_RETRIEVAL_CACHE_PATH"))
    return _DEFAULT
