"""C.2 — LLM tie-break for the AMBIGUOUS minority (DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §3).

Deterministic-first: `classify_domain()` is authoritative for `classified` (fast, free, verifiable). ONLY when it
returns `ambiguous` (low margin / mixed / unknown — the cases keyword coverage can't settle) does this call a
BOUNDED LLM to pick one of the four coarse gate families. Properties:
- **Flag-gated** (`AZALEA_DOMAIN_LLM_FALLBACK`, off by default) → with the flag unset, this is a strict no-op and
  the deterministic result stands.
- **Best-effort** → any LLM error/timeout/invalid reply keeps the deterministic result (never blocks generation).
- **Bounded** → the LLM may only pick coding | math | science | expository, or abstain; it never authors anything
  else. An abstain leaves the result `ambiguous` (non-gating, the safe fallback).
- **Testable offline** → the LLM call is an injected `classify_fn`; the resolver is pure and needs no API key.
"""
from __future__ import annotations

import logging
import os
from typing import Callable, Optional

from app.services.domain_classifier import DomainSignals

_log = logging.getLogger(__name__)
_FLAG = "AZALEA_DOMAIN_LLM_FALLBACK"

# The coarse gate families the LLM may choose (the classifier's gate_family vocabulary). `concept` is the
# user-facing alias for `expository`.
_GATE_FAMILIES = ("coding", "math", "science", "expository", "cs", "data_science", "ee", "quant")
_FAMILY_TO_FINE = {"coding": "coding", "math": "math", "science": "science", "expository": "concept",
                   "cs": "computer_science", "data_science": "statistics", "ee": "electrical_engineering",
                   "quant": "finance"}

# goal -> one of _GATE_FAMILIES, or None to abstain.
LlmClassify = Callable[[str], Optional[str]]


def _enabled() -> bool:
    return str(os.getenv(_FLAG, "") or "").strip().lower() in ("1", "true", "on")


def resolve_with_llm(
    goal: str,
    deterministic: DomainSignals,
    *,
    classify_fn: Optional[LlmClassify] = None,
    force_enabled: Optional[bool] = None,
) -> DomainSignals:
    """Return a possibly-upgraded DomainSignals. No-op unless the flag is on AND the deterministic result was
    `ambiguous`. A confident deterministic result is never second-guessed."""
    enabled = _enabled() if force_enabled is None else force_enabled
    if not enabled:
        return deterministic
    if deterministic.classification_status != "ambiguous":
        return deterministic                                  # only tie-break what the deterministic pass couldn't

    fn = classify_fn or _default_llm_classify
    try:
        family = fn(goal)
    except Exception:  # noqa: BLE001 — classification must never block; fall back to deterministic
        _log.warning("domain LLM tie-break failed for %r; keeping deterministic result", goal, exc_info=True)
        return deterministic

    if family not in _GATE_FAMILIES:
        return deterministic                                  # LLM abstained/invalid -> stay ambiguous (non-gating)

    return DomainSignals(
        domain=_FAMILY_TO_FINE[family],
        gate_family=family,
        confidence=deterministic.confidence,
        classification_status="classified",                  # the LLM resolved it -> confident enough to route
        subdomain_family=deterministic.subdomain_family,
        scores=deterministic.scores,
        source="llm",
    )


def _default_llm_classify(goal: str) -> Optional[str]:
    """The real bounded LLM call (lazy import so this module stays import-safe/offline-testable)."""
    import json

    from app.services.llm_client import OPENAI_MODEL, _create_with_usage

    system = (
        "Classify a learning goal into exactly one content type. Reply ONLY with JSON "
        '{"domain": "<coding|cs|math|data_science|science|ee|quant|concept|unknown>"}. '
        "coding = writing programs, algorithms, data structures, software implementation; "
        "cs = computer-science SYSTEMS that are NOT about writing one algorithm — networking/TCP/protocols, "
        "operating systems, distributed systems, computer architecture, databases; "
        "math = formulas, proofs, algebra, calculus, step-by-step solving, linear algebra; "
        "data_science = statistics, probability, data analysis, machine learning, z-scores, distributions; "
        "science = physics, chemistry, biology, natural phenomena; "
        "ee = electrical engineering, circuits, voltage/current, signals, electronics; "
        "quant = finance, economics, investing, interest, markets, valuation; "
        "concept = history, humanities, definitions, other non-quantitative ideas. "
        "Use \"unknown\" only if it is genuinely impossible to tell."
    )
    resp = _create_with_usage(
        "domain_classify",
        prompt_cache_key="azalea_domain_classify_v1",
        model=OPENAI_MODEL,
        input=[{"role": "system", "content": system},
               {"role": "user", "content": str(goal or "")}],
        text={"format": {"type": "json_object"}},
    )
    data = json.loads(resp.output_text)
    d = str(data.get("domain", "")).strip().lower()
    if d == "concept":
        return "expository"
    return d if d in _GATE_FAMILIES else None
