"""Worked-example card contracts (spec §4).

Base cards (math / algorithm / proof / concept, §4.1) carry ``reasoning``; coding
cards (§4.2) replace it with ``how`` and add the code-anchored fields. ``state_delta``
is nullable and paired with ``state_relevance`` (§4.1 / §7). These are typed contracts
only — derivation/validation live in :mod:`state` and :mod:`validators`.

In the default ``post_generation_trace`` mode the model emits **teaching anchors**, NOT
``trace_range``/``included_event_ids`` (the reconciler attaches those after execution,
§4.2/§6.1) — so those fields are absent from the authored card shape here.
"""
from __future__ import annotations

from typing import Literal, TypedDict

from .state import StateDelta

StateRelevance = Literal["stateful", "static", "none"]
ExplanationMode = Literal["reasoning", "implementation_how"]
TeachingNoteType = Literal["key_idea", "invariant", "watch_for", "check"]

# Fields the model authors on a base card. Backend-derived fields (resolved_state_after,
# prior_state, ids, totals, fallbacks, §4.1) are NOT part of the authored contract.
BASE_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {"title", "goal", "work", "result", "state_relevance"}
)
# Coding cards must teach via `how` + concrete work/result. The code anchors
# (primary_kind / code_refs / explanation_mode) are RECOMMENDED, not hard-required —
# a missing/low code_refs density is an audit trigger (§8), not a reason to drop the
# whole worked example. explanation_mode is backend-derived in normalize (§9.2).
CODING_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {"title", "goal", "how", "work", "result", "state_relevance"}
)


class TeachingNote(TypedDict, total=False):
    type: TeachingNoteType
    content: str


class BaseCard(TypedDict, total=False):
    """§4.1 base contract (the authored shape)."""

    title: str
    goal: str
    reasoning: str                 # the decisive justification (omit if self-evident)
    work: list[str]
    result: str
    state_delta: StateDelta | None  # None when state_relevance != "stateful" (§4.1)
    state_relevance: StateRelevance
    cases_covered: list[str]
    teaching_note: TeachingNote


class CodingCard(TypedDict, total=False):
    """§4.2 coding extension — ``how`` instead of ``reasoning`` + teaching anchors.

    Shown in the default ``post_generation_trace`` shape: no ``trace_range`` /
    ``included_event_ids`` (attached by the reconciler, §6.1).
    """

    title: str
    goal: str
    how: str                       # how the code performs this step (§4.2)
    work: list[str]
    result: str
    state_delta: StateDelta | None
    state_relevance: StateRelevance
    cases_covered: list[str]
    teaching_note: TeachingNote
    # coding-specific (§4.2)
    primary_kind: str
    subkinds: list[str]
    explanation_mode: ExplanationMode
    teaching_sequence_index: int
    expected_state_effect: list[str]
    code_refs: list[int]           # single flat 1-based line list (Option A, §4.2)


def is_coding_card(card: dict) -> bool:
    """A card is coding-shaped when it teaches *how the code does it* (§4.2)."""
    return "how" in card or card.get("explanation_mode") == "implementation_how"
