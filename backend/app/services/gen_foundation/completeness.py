"""Deterministic completeness gate (Layer 0): does a rendered step actually REACH the final answer?

This closes the tautology where ``teaching_step_reaching_final = ids[-1]`` "proved" completion by
definition. Without an executor we can only check **self-consistency** — that the example's own claimed
``final_answer`` is actually represented by one of its steps — but that already catches the large class
of truncation failures (Prim's stops at vertex B while claiming an MST weight that appears nowhere).

Conservative by design: it only fails when the answer has a checkable CANONICAL SIGNATURE (a result
number, or a numeric sequence) and NO card represents it. Purely textual answers ("the list is now
sorted") are reported as not-checkable rather than risk false-rejecting a valid example. The richer
``{kind, canonical_value}`` form is the Layer 2 target, where execution can PRODUCE the value instead
of the model self-declaring it.
"""
from __future__ import annotations

import re
from typing import Any, Optional

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_BRACKETED = re.compile(r"\[[^\[\]]*\]")
_MIN_SEQUENCE = 3  # a "sequence answer" (e.g. a sorted array) must have at least this many elements


def _numbers(text: str) -> list[str]:
    return _NUMBER.findall(text or "")


def _answer_signature(final_answer: Any) -> dict[str, Any]:
    """Extract the canonical signature to look for. Prefer a numeric SEQUENCE (sorted array, traversal
    order); else the RESULT VALUE (the last number, where results are usually stated: 'total = 57')."""
    text = str(final_answer or "").strip()
    if not text:
        return {"checkable": False}
    # longest bracketed numeric sequence, if any
    best_seq: list[str] = []
    for group in _BRACKETED.findall(text):
        nums = _numbers(group)
        if len(nums) > len(best_seq):
            best_seq = nums
    if len(best_seq) >= _MIN_SEQUENCE:
        return {"checkable": True, "kind": "sequence", "sequence": best_seq}
    nums = _numbers(text)
    if nums:
        return {"checkable": True, "kind": "scalar", "result_value": nums[-1]}
    return {"checkable": False}


def _card_text(card: dict[str, Any]) -> str:
    parts = [str(card.get("result") or "")]
    parts.extend(str(w) for w in (card.get("work") or []))
    return " ".join(parts)


def _is_contiguous_sublist(seq: list[str], whole: list[str]) -> bool:
    if not seq or len(seq) > len(whole):
        return False
    for i in range(len(whole) - len(seq) + 1):
        if whole[i:i + len(seq)] == seq:
            return True
    return False


def _card_reaches(card: dict[str, Any], sig: dict[str, Any]) -> bool:
    nums = _numbers(_card_text(card))
    if sig["kind"] == "sequence":
        return _is_contiguous_sublist(sig["sequence"], nums)
    return sig["result_value"] in nums  # exact numeric token (so "57" never matches "157")


def step_reaching_final(
    cards: list[dict[str, Any]], step_ids: list[str], final_answer: Any
) -> Optional[str]:
    """The id of the LAST card whose state represents ``final_answer`` (the terminal step), or None.
    Returns None for a non-checkable answer too — callers treat that as 'unknown', not 'reached'."""
    sig = _answer_signature(final_answer)
    if not sig.get("checkable"):
        return None
    ids = step_ids or [f"step_{i+1}" for i in range(len(cards))]
    for card, sid in zip(reversed(cards), reversed(ids)):  # scan from the end — the answer is terminal
        if _card_reaches(card, sig):
            return sid
    return None


def completeness_errors(artifact: dict[str, Any]) -> list[str]:
    """Hard gate: a checkable final answer must be reached by some rendered step (§9.1, Layer 0)."""
    final_answer = artifact.get("final_answer")
    sig = _answer_signature(final_answer)
    if not sig.get("checkable"):
        return []  # nothing we can verify deterministically; not a failure (see module docstring)
    cards = artifact.get("cards") or []
    step_ids = artifact.get("step_ids") or [f"step_{i+1}" for i in range(len(cards))]
    if step_reaching_final(cards, step_ids, final_answer) is None:
        return ["no rendered step reaches the claimed final_answer "
                "(incomplete/truncated worked example, §9.1 completeness)"]
    return []
