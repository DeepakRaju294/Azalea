"""claim_class classifier (Q24 §3) — what a span MEANS (distinct from where its truth comes from).

Default is **factual** (a declarative sentence is a factual assertion → must be established or it is unsupported).
A span is `non_factual_framing` only when it reads as framing AND carries no checkable/technical/causal signal;
`prompt` when it is a question. This bias-to-factual is deliberate: in shadow it measures exactly how much free
text has no establishment basis (the number that decides when a family is safe to enforce).
"""
from __future__ import annotations

import re

from . import relations
from .validator import FACTUAL, NON_FACTUAL_FRAMING, PROMPT

_FRAMING_MARKERS = (
    "matters", "is important", "worth", "interesting", "beautiful", "elegant", "note that",
    "in practice", "keep in mind", "as we'll see", "helps us", "let's", "we'll", "you'll",
    "appreciate", "intuitively", "the big picture", "at a high level",
)
# a checkable/technical/causal signal that forces `factual` even amid framing words
_ABSOLUTE = re.compile(r"\b(always|never|every|all|none|no |cannot|must|guarantee[sd]?|is defined|equals?)\b",
                       re.IGNORECASE)
# a DEFINITIONAL copula (not bare "is"/"are", which also appear in framing like "is worth appreciating")
_COPULA = re.compile(r"\b(is|are)\s+(a|an|the)\b|\b(means|refers to|is called|is defined)\b", re.IGNORECASE)
_CAUSAL = re.compile(r"\b(because|therefore|so that|hence|thus|as a result|due to)\b", re.IGNORECASE)


def _has_checkable_signal(text: str) -> bool:
    if relations.find_relations(text) or relations.find_operation_phrase(text):
        return True
    return bool(_ABSOLUTE.search(text) or _COPULA.search(text) or _CAUSAL.search(text))


def classify_claim(text: str) -> str:
    """Classify a span. Default factual; framing only when clearly framing with no checkable signal."""
    stripped = text.strip()
    if stripped.endswith("?"):
        return PROMPT
    low = stripped.lower()
    if any(m in low for m in _FRAMING_MARKERS) and not _has_checkable_signal(stripped):
        return NON_FACTUAL_FRAMING
    return FACTUAL
