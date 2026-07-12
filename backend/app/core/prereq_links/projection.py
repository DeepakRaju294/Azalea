"""Plain-text scan projection + token-boundary matching (PREREQ_LINKS_SPEC v8 §2.2). Pure — no app imports.

The SAME projection must be used by the scanner, the Tier-1 validator, and (eventually) the frontend, so
offsets/phrases never diverge (§A33). Code spans are dropped (ineligible, §2.2); bold/math delimiters are
stripped keeping inner text."""
from __future__ import annotations

import re

from .validation import _APOSTROPHES

_INLINE_CODE = re.compile(r"`[^`]*`")               # `code` → dropped (ineligible region, §2.2)
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")       # **bold** / __bold__ → inner text
_MATH_DELIM = re.compile(r"\\[()]")                  # \( \) → removed, inner kept


def project_to_plain_text(markdown: str) -> str:
    """Learner-visible plain-text projection of eligible card text (§2.2). Deterministic; offsets are the
    scanner's own concern (not persisted). Bold/math delimiters stripped (inner kept); inline code removed."""
    s = markdown or ""
    s = _INLINE_CODE.sub(" ", s)                     # drop code spans (ineligible)
    s = _BOLD.sub(lambda m: m.group(1) or m.group(2) or "", s)
    s = _MATH_DELIM.sub("", s)
    return s


def _straighten_apostrophes(s: str) -> str:
    """1:1 char replacement (offset-preserving) so curly apostrophes match a straight-apostrophe phrase."""
    return "".join(_APOSTROPHES.get(ch, ch) for ch in s)


def find_token_matches(text: str, phrase: str) -> list[tuple[int, int, str]]:
    """All token-boundary occurrences of `phrase` in `text`, returned as (start, end, surface) with the surface
    kept in the text's REAL casing (anchoring is case-sensitive on the selected surface, §2.2/§5).

    - word boundaries so "ring" never matches inside "spring" (boundary = adjacent alphanumeric/underscore);
    - runs of whitespace in the phrase match runs of whitespace in the text;
    - apostrophe variants are normalized on both sides (offset-preserving);
    - single-character alphanumeric phrases are NOT scanned (symbol policy; would match everywhere, §2.2).
    """
    phrase = (phrase or "").strip()
    if not phrase:
        return []
    if len(phrase) == 1 and phrase.isalnum():        # single-char symbol → needs a registered policy; skip
        return []

    norm_phrase = _straighten_apostrophes(phrase)
    parts = [re.escape(tok) for tok in norm_phrase.split()]
    core = r"\s+".join(parts) if len(parts) > 1 else re.escape(norm_phrase)
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){core}(?![A-Za-z0-9_])", re.IGNORECASE)

    hay = _straighten_apostrophes(text or "")        # same length as text → offsets valid against `text`
    out: list[tuple[int, int, str]] = []
    for m in pattern.finditer(hay):
        out.append((m.start(), m.end(), text[m.start():m.end()]))
    return out
