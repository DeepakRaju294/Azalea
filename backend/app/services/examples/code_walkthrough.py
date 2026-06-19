"""Rebuild coding `code_walkthrough` cards as a per-LINE, one-step-at-a-time walkthrough.

The general lesson prompt summarizes code (a few vague bullets for a whole function) and the
tiny-card merge pass then collapses what little structure remains, so the learner never gets a
real line-by-line walkthrough. This pass mirrors the worked-example solver: it takes the
authoritative complete code (already unified by `code_repair`) and asks the model for EXACTLY
ONE explanation per line, then emits deterministic cards — one card per logical block, one main
bullet + one single-line highlight per line — so the panel highlights one line at a time as the
learner steps.

The STRUCTURE is deterministic (blocks and line numbers come from the code itself); only the
per-line wording is LLM-authored. Runs at enrichment, after `apply_clean_code_to_lesson`.
Failure-safe (any problem leaves the existing cards untouched) and injectable for tests; no
network when the key is absent/dummy.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Optional

_log = logging.getLogger(__name__)

ExplainFn = Callable[[dict[str, Any]], Optional[dict[str, Any]]]

# Soft cap on lines per card so a long blank-line-free function doesn't become one giant card.
_MAX_LINES_PER_CARD = 6


_EXPLAIN_SYSTEM = (
    "You explain code to a learner ONE LINE AT A TIME. You receive the complete code with line "
    "numbers. For EVERY non-blank line, write ONE plain-English sentence (about 10-28 words) that "
    "says what that line does and how/why it works — never a restatement of the syntax, and with NO "
    "raw code tokens, operators, brackets, or call expressions in the sentence (single identifiers "
    "used as plain nouns like 'result' or 'left' are fine). Return ONLY JSON of this exact shape:\n"
    '{"explanations": [{"line": <line number>, "text": "<one sentence>"}, ...]}\n'
    "Cover EVERY non-blank line, in order. Never skip a line as 'obvious'."
)


def _default_explainer(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip().lower() == "dummy":
        return None
    try:
        from app.services.llm_client import OPENAI_MODEL, client

        # Per-call timeout caps a hung call; KEEP retries so a transient rate-limit/5xx recovers
        # rather than silently dropping the walkthrough.
        timeout = float(os.getenv("AZALEA_ENRICH_TIMEOUT_SECONDS", "60"))
        retries = max(0, int(os.getenv("AZALEA_ENRICH_MAX_RETRIES", "2")))
        response = client.with_options(timeout=timeout, max_retries=retries).responses.create(
            model=OPENAI_MODEL,
            input=[
                {"role": "system", "content": _EXPLAIN_SYSTEM},
                {"role": "user", "content": str(payload.get("user") or "")},
            ],
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text)
    except Exception as exc:  # noqa: BLE001
        _log.warning("code_walkthrough: LLM call failed: %s", exc)
        return None


def _key(card: dict[str, Any]) -> str:
    return str(card.get("blueprint_key") or card.get("card_type") or "").strip().lower()


def _authoritative_code(cards: list[Any]) -> str:
    """The complete implementation — the longest code_snippet on a code card (code_repair has
    already unified them, so they should be identical; longest is a safe tie-break)."""
    snippets = [
        str(c.get("code_snippet") or "")
        for c in cards
        if isinstance(c, dict) and _key(c) in ("code_walkthrough", "worked_example")
        and str(c.get("code_snippet") or "").strip()
    ]
    return max(snippets, key=lambda s: len(s.splitlines()), default="")


def _code_language(cards: list[Any]) -> str:
    for c in cards:
        if isinstance(c, dict) and str(c.get("code_language") or "").strip():
            return str(c["code_language"])
    return "python"


def _walkthrough_blocks(code: str, max_lines: int = _MAX_LINES_PER_CARD) -> list[list[int]]:
    """Partition the code's NON-BLANK line numbers into card-sized blocks: break on blank lines
    and at every new top-level `def`/`class`, then split any block longer than `max_lines`."""
    lines = code.split("\n")
    blocks: list[list[int]] = []
    cur: list[int] = []
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            if cur:
                blocks.append(cur)
                cur = []
            continue
        top_level = raw[:1] not in (" ", "\t")
        if cur and top_level and stripped.startswith(("def ", "class ", "async def ")):
            blocks.append(cur)
            cur = []
        cur.append(idx)
    if cur:
        blocks.append(cur)

    out: list[list[int]] = []
    for block in blocks:
        for k in range(0, len(block), max_lines):
            out.append(block[k : k + max_lines])
    return out


def explain_lines(code: str, *, explainer: Optional[ExplainFn] = None) -> Optional[dict[int, str]]:
    """One explanation per NON-BLANK line. Returns {line_number: sentence} covering EVERY non-blank
    line, or None if the model didn't (failure-safe — the caller then leaves the lesson alone)."""
    fn = explainer or _default_explainer
    lines = code.split("\n")
    nonblank = [i for i, ln in enumerate(lines, start=1) if ln.strip()]
    if not nonblank:
        return None
    numbered = "\n".join(f"{i}: {ln}" for i, ln in enumerate(lines, start=1) if ln.strip())
    user = f"Complete code:\n\n{numbered}\n\nExplain each non-blank line."
    try:
        raw = fn({"user": user, "code": code})
    except Exception as exc:  # noqa: BLE001
        _log.warning("code_walkthrough: explainer raised: %s", exc)
        return None
    if not isinstance(raw, dict):
        return None

    items = raw.get("explanations") or raw.get("lines") or []
    mapping: dict[int, str] = {}
    if isinstance(items, dict):
        for k, v in items.items():
            try:
                mapping[int(k)] = str(v).strip()
            except (TypeError, ValueError):
                continue
    elif isinstance(items, list):
        for it in items:
            if isinstance(it, dict) and it.get("line") is not None:
                try:
                    mapping[int(it["line"])] = str(it.get("text") or "").strip()
                except (TypeError, ValueError):
                    continue

    out: dict[int, str] = {}
    for ln in nonblank:
        text = mapping.get(ln)
        if not text:
            return None  # incomplete coverage -> bail, don't fabricate
        out[ln] = text
    return out


def _replace_walkthrough_cards(cards: list[Any], new_cards: list[dict[str, Any]]) -> None:
    idxs = [i for i, c in enumerate(cards) if isinstance(c, dict) and _key(c) == "code_walkthrough"]
    if idxs:
        first = idxs[0]
        for i in reversed(idxs):
            cards.pop(i)
        for off, card in enumerate(new_cards):
            cards.insert(first + off, card)
        return
    # No existing walkthrough cards (under-production): insert before the first worked_example.
    we = next((i for i, c in enumerate(cards) if isinstance(c, dict) and _key(c) == "worked_example"), None)
    pos = we if we is not None else min(1, len(cards))
    for off, card in enumerate(new_cards):
        cards.insert(pos + off, card)


def apply_line_explained_walkthrough(
    lesson_json: dict[str, Any], topic: dict[str, Any], *, explainer: Optional[ExplainFn] = None,
) -> bool:
    """Rebuild a coding topic's code_walkthrough as one card per logical block, one main bullet +
    one single-line highlight per code line, with the complete code on every card. Failure-safe."""
    try:
        if str(topic.get("topic_type") or "").lower() != "coding_implementation":
            return False
        cards = lesson_json.get("lesson_cards")
        if not isinstance(cards, list) or not cards:
            return False
        code = _authoritative_code(cards)
        if not code.strip():
            # The lean pass produced NO code at all (it skipped code_walkthrough). Generate the clean
            # implementation so the coding topic actually has code to walk through — and so the
            # worked-example solver downstream finds code and runs its CODE-anchored path instead of
            # falling back to an algorithm-style trace.
            from app.services.examples.code_repair import generate_clean_code

            code = (generate_clean_code(topic) or "").strip()
            if not code:
                return False
        blocks = _walkthrough_blocks(code)
        if not blocks:
            return False
        explanations = explain_lines(code, explainer=explainer)
        if not explanations:
            return False

        lang = _code_language(cards)
        title = f"Code Walkthrough: {str(topic.get('title') or 'Implementation').strip()}"
        new_cards: list[dict[str, Any]] = []
        for block in blocks:
            points = [explanations.get(ln, "") for ln in block]
            if any(not p for p in points):
                return False  # a line in this block had no explanation -> bail
            new_cards.append({
                "blueprint_key": "code_walkthrough",
                "card_type": "code_walkthrough",
                "title": title,
                "points": points,
                "code_snippet": code,
                "code_language": lang,
                "visual_type": "code_trace",
                "highlight_lines_per_step": [[ln, ln] for ln in block],
                "metadata": {"line_explained_walkthrough": True},
            })

        _replace_walkthrough_cards(cards, new_cards)
        lesson_json.setdefault("metadata", {})["line_explained_walkthrough"] = True
        return True
    except Exception as exc:  # noqa: BLE001 — never break a lesson
        _log.warning("code_walkthrough: rebuild failed for %s: %s", topic.get("id"), exc)
        return False
