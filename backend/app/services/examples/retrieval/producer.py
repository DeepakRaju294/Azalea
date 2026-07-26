"""Retrieval producer — the narrow interface the existing resolver calls (§18, single-resolver design).

`try_resolve(topic) -> CandidateArtifact | None`. It does NOT re-implement adapter/foundation routing; the
existing `solve_worked_example` cascade owns ordering and only reaches retrieval on a genuine miss. Concept
resolution is CONSERVATIVE (issue 23): a wrong concept key retrieves a valid-but-wrong-topic example, which is
worse than nothing, so an ambiguous/low-confidence match returns None (a miss) rather than guessing.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.examples.retrieval import sources
from app.services.examples.retrieval.model import CandidateArtifact

# reviewed aliases -> corpus concept_key. Deliberately explicit (no fuzzy guessing).
_ALIASES: dict[str, str] = {
    "motional emf": "motional_emf", "motional electromotive force": "motional_emf",
    "faradays law": "faraday_emf", "faraday's law": "faraday_emf", "faraday law": "faraday_emf",
    "induced emf": "faraday_emf",
    "inductor energy": "inductor_energy", "energy stored in an inductor": "inductor_energy",
    "magnetic energy": "inductor_energy",
    "rl time constant": "rl_time_constant", "rl circuit time constant": "rl_time_constant",
    "time constant": "rl_time_constant",
    "kinetic energy": "kinetic_energy",
    "ohms law": "ohms_law", "ohm's law": "ohms_law", "ohm law": "ohms_law",
    "compound interest": "compound_interest",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(s or "").lower()).strip()


def _concept_key(topic: dict[str, Any]) -> str | None:
    get = topic.get if isinstance(topic, dict) else (lambda k, d=None: getattr(topic, k, d))
    # 1) explicit subject_key that IS a corpus key (raw, then space->underscore normalized)
    raw_subj = str(get("subject_key", "") or "").strip().lower()
    for cand in (raw_subj, _norm(raw_subj).replace(" ", "_")):
        if cand and sources.lookup(cand):
            return cand
    # 2) alias table on the normalized title/subject
    for field in ("title", "subject_key"):
        norm = _norm(get(field, ""))
        if norm in _ALIASES:
            return _ALIASES[norm]
        # a title CONTAINING an alias phrase (e.g. "Understanding Motional EMF")
        hits = {key for phrase, key in _ALIASES.items() if phrase in norm}
        if len(hits) == 1:                 # exactly one -> confident; 0 or >1 -> ambiguous, miss
            return next(iter(hits))
    return None


def try_resolve(topic: dict[str, Any]) -> CandidateArtifact | None:
    """Return a candidate for this topic from the registered source backends (curated corpus now; computational
    API / web-fetch when live), or None on a miss / ambiguous concept resolution."""
    from app.services.examples.retrieval.backends import resolve_candidate  # avoid import cycle at module load
    cand, _backend = resolve_candidate(topic)
    return cand
