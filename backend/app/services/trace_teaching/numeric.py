"""Numeric normalization contract (Q23 §5) — makes C1/C4 operational.

Numbers are parsed into a canonical rational form (3, 3.0, 3.00 are equivalent); units are parsed SEPARATELY from
magnitudes. An UNRECOGNIZED numeric-like token is a hard fail (fail closed), never silently ignored. Variable-like
identifiers (v2, x1) are NOT numeric literals.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import List, Optional, Tuple

_SUPERSCRIPT = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5",
                "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-"}


def _desuper(s: str) -> str:
    return "".join(_SUPERSCRIPT.get(c, c) for c in s)


def canonical_number(token: str) -> Optional[Fraction]:
    """Parse a numeric literal to a canonical Fraction; None if it isn't a recognized number."""
    t = _desuper(token.strip().replace("−", "-").replace(",", ""))
    if not t:
        return None
    # integer / decimal
    if re.fullmatch(r"-?\d+", t) or re.fullmatch(r"-?\d*\.\d+", t) or re.fullmatch(r"-?\d+\.\d*", t):
        return Fraction(t) if "." not in t else Fraction(t).limit_denominator(10**9)
    # fraction a/b
    m = re.fullmatch(r"(-?\d+)/(\d+)", t)
    if m:
        return Fraction(int(m.group(1)), int(m.group(2)))
    # scientific 1e-3 / 1.5E4
    if re.fullmatch(r"-?\d+(\.\d+)?[eE]-?\d+", t):
        return Fraction(float(t)).limit_denominator(10**12)
    # power form 10^-3, 2^3
    m = re.fullmatch(r"(-?\d+)\^(-?\d+)", t)
    if m:
        base, exp = int(m.group(1)), int(m.group(2))
        return Fraction(base) ** exp
    return None


_IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")           # v2, x1 — not literals
_HAS_DIGIT = re.compile(r"\d")
_UNIT_TOKEN = re.compile(r"^[A-Za-zµΩ°%/][A-Za-z0-9/·°%]*$")   # N, kg, m/s, %, ° … (superscripts desuper'd first)
_STRIP = " \t\n.,;:!?()[]{}\"'"
# common words that can follow a number but are NOT units (else "4 and 5" reads "and" as a unit)
_UNIT_STOPWORDS = frozenset({
    "and", "or", "to", "the", "a", "an", "is", "are", "was", "were", "be", "of", "in", "on", "at", "by",
    "for", "with", "then", "gives", "give", "giving", "plus", "minus", "times", "equals", "so", "we", "get",
    "gets", "into", "from", "as", "that", "this", "it", "its", "here", "there", "both", "each", "yields",
    "more", "less", "than", "when", "if", "and/or", "up", "down", "left", "right",
})


@dataclass(frozen=True)
class NumberToken:
    token: str
    value: Optional[Fraction]        # None ⇒ unrecognized numeric-like token (C1 fail-closed)
    unrecognized: bool


def extract_numbers(text: str) -> List[NumberToken]:
    """Extract numeric literals (not identifiers). A digit-bearing token that doesn't parse is unrecognized."""
    out: List[NumberToken] = []
    for raw in text.split():
        tok = raw.strip(_STRIP)
        if not tok or _IDENTIFIER.match(tok):
            continue
        if not _HAS_DIGIT.search(tok):
            continue
        val = canonical_number(tok)
        out.append(NumberToken(tok, val, val is None))
    return out


def _normalize_unit(u: str) -> str:
    return _desuper(u.strip(_STRIP)).replace(" ", "")


def extract_value_unit_pairs(text: str) -> List[Tuple[Fraction, Optional[str]]]:
    """Pair each recognized number with an immediately-following unit token (else unit None)."""
    tokens = text.split()
    pairs: List[Tuple[Fraction, Optional[str]]] = []
    for i, raw in enumerate(tokens):
        tok = raw.strip(_STRIP)
        if not tok or _IDENTIFIER.match(tok):
            continue
        val = canonical_number(tok)
        if val is None:
            continue
        unit = None
        if i + 1 < len(tokens):
            nxt = tokens[i + 1].strip(_STRIP)
            if (nxt and nxt.lower() not in _UNIT_STOPWORDS and canonical_number(nxt) is None
                    and _UNIT_TOKEN.match(_desuper(nxt))):
                unit = _normalize_unit(nxt)
        pairs.append((val, unit))
    return pairs


def units_equal(a: Optional[str], b: Optional[str]) -> bool:
    if a is None or b is None:
        return a == b
    return _normalize_unit(a) == _normalize_unit(b)
