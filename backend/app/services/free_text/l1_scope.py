"""L1 — scope adherence (Q24 §3, deterministic).

Do not introduce terminology outside the prerequisites or what the topic teaches. Enforced against a topic-level
VOCABULARY OBJECT so ordinary prose is never mistaken for a technical term: ONLY tokens the tokenizer classifies as
technical are checked; an ordinary word is never rejected merely for being absent. Term membership is matched by the
stable `intro_card_id`, never by card title/type/position (a reordered sequence must not change what terminology is
allowed). A high-confidence unknown technical token is a hard fail; a low-confidence one is routed to review (L4),
not an unconditional hard fail — the tokenizer isn't trusted to hard-fail until proven.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

PASS = "pass"
FAIL = "fail"
REVIEW = "review"   # low-confidence unknown technical token → L4 / controlled review


@dataclass(frozen=True)
class IntroducedTerm:
    term_id: str
    display: str
    intro_card_id: str


@dataclass(frozen=True)
class TopicVocabulary:
    """The topic's terminology contract (spec §3 L1 vocabulary object)."""
    assumed_prerequisite_terms: FrozenSet[str] = frozenset()
    introduced_terms: Tuple[IntroducedTerm, ...] = ()
    approved_operations: FrozenSet[str] = frozenset()
    approved_symbols: FrozenSet[str] = frozenset()
    term_aliases: Dict[str, str] = field(default_factory=dict)          # alias(lower) → canonical display(lower)
    technical_terms: FrozenSet[str] = frozenset()                       # the tokenizer's technical lexicon (lower)
    low_confidence_terms: FrozenSet[str] = frozenset()                  # technical tokens the tokenizer is unsure of

    def allowed_terms(self) -> FrozenSet[str]:
        """Terms the topic may use: prerequisites + everything it teaches (all introduced_terms, matched by id)."""
        taught = {t.display.lower() for t in self.introduced_terms}
        return frozenset({p.lower() for p in self.assumed_prerequisite_terms} | taught)


@dataclass(frozen=True)
class L1Result:
    status: str                          # PASS | FAIL | REVIEW
    out_of_scope_terms: Tuple[str, ...]  # high-confidence unknown technical tokens (hard fail)
    review_terms: Tuple[str, ...]        # low-confidence unknown technical tokens (→ L4/review)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def check_scope(text: str, vocab: TopicVocabulary) -> L1Result:
    """Flag technical tokens used outside the topic's allowed terminology. Ordinary words are never flagged."""
    norm = _normalize(text)
    allowed = vocab.allowed_terms()

    out_of_scope: List[str] = []
    review: List[str] = []

    # Only tokenizer-technical terms are checked. Longest terms first so "net force" wins over "force".
    for term in sorted(vocab.technical_terms, key=len, reverse=True):
        canonical = vocab.term_aliases.get(term, term)
        # word-boundary presence of the (possibly multi-word) technical term or one of its aliases
        aliases = [term] + [a for a, c in vocab.term_aliases.items() if c == canonical]
        present = any(re.search(r"\b" + re.escape(a) + r"\b", norm) for a in aliases)
        if not present:
            continue
        if canonical in allowed:
            continue
        if term in vocab.low_confidence_terms:
            review.append(term)
        else:
            out_of_scope.append(term)

    if out_of_scope:
        return L1Result(FAIL, tuple(sorted(set(out_of_scope))), tuple(sorted(set(review))))
    if review:
        return L1Result(REVIEW, (), tuple(sorted(set(review))))
    return L1Result(PASS, (), ())
