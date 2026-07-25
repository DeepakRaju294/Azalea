"""Plain-language title enforcement for surfaces that do not render mathematics."""

from __future__ import annotations

import re
from typing import Any


_DELIMITED_MATH = re.compile(
    r"\$\$.*?\$\$|\$[^$\n]*\$|\\\(.*?\\\)|\\\[.*?\\\]",
    re.DOTALL,
)
_SYMBOLIC_START = re.compile(r"[∫∮∑∏√∞≈≠≤≥]|\\(?:int|oint|sum|prod|frac|sqrt|nabla)\b")
_EQUATION_START = re.compile(
    r"(?<!\w)(?:[A-Za-zΑ-Ωα-ω][A-Za-z0-9Α-Ωα-ω_{}()'\u2032]*|[A-Z]\([^)]*\))\s*"
    r"(?:=|≈|≠|≤|≥|<|>)"
)
_MATHY_SUFFIX = re.compile(r"[=∫∮∑∏√∞≈≠≤≥·×]|\\[A-Za-z]+|[_^{}]")


def _cut_at_math(text: str) -> str:
    starts = [
        match.start()
        for pattern in (_SYMBOLIC_START, _EQUATION_START)
        if (match := pattern.search(text)) is not None
    ]
    if not starts:
        return text
    start = min(starts)
    prefix = text[:start]
    # Remove a connective that exists only to introduce the stripped equation.
    prefix = re.sub(r"\s+(?:for|using|with|as|where)\s*$", "", prefix, flags=re.IGNORECASE)
    return prefix


def plain_language_title(value: Any, *, fallback: str) -> str:
    """Return a title with math expressions removed, never an empty title."""
    text = str(value or "").strip()
    text = _DELIMITED_MATH.sub(" ", text)
    text = re.sub(r"\s+(?:for|using|with|as|where)\s*$", "", text, flags=re.IGNORECASE)

    # A colon/dash commonly separates a useful prose title from its equation.
    for match in re.finditer(r"\s*:\s*|\s+[—–-]\s+", text):
        if _MATHY_SUFFIX.search(text[match.end():]):
            text = text[:match.start()]
            break

    text = _cut_at_math(text)
    text = re.sub(r"\s+", " ", text).strip(" \t\r\n:;,.—–-")
    return text or fallback
