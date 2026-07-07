"""The closed deterministic algebra for L2 class-3 transformation checks (Q24 §3).

A relation is a single-variable (x) polynomial equation `lhs = rhs`. This is intentionally NOT a general CAS: it
covers exactly the registered operations the slice needs (square / subtract-constant / divide-by-constant) over
monomial+constant relations, deterministically and without an LLM. Every operation is a pure function
`Relation -> Relation`; the intent lexicon maps a surfaced phrase to a registered `operation_id` by exact
normalized match (never inference).

Canonical relation equality is orientation- and scale-independent: both relations are moved to `lhs - rhs = 0`,
sign-normalized so the highest-degree coefficient is positive, and reduced by the gcd of coefficients. So `x⁴ = 16`
and `16 = x⁴` compare equal, while `x⁴ = 16` and `x² = 0` do not — which is what refutes the §6 slice on target
conformance.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from math import gcd
from typing import Callable, Dict, Optional, Tuple

# ── expression + relation model ────────────────────────────────────────────────────────────────────────────────

# A polynomial in x: {exponent: coefficient}, zero coefficients pruned.
Coeffs = Dict[int, Fraction]


def _prune(c: Coeffs) -> Coeffs:
    return {k: v for k, v in c.items() if v != 0}


@dataclass(frozen=True)
class Poly:
    """A single-variable polynomial (immutable). Empty coeffs == the zero polynomial."""
    coeffs: Tuple[Tuple[int, Fraction], ...]  # sorted (exponent, coefficient), pruned

    @staticmethod
    def of(mapping: Coeffs) -> "Poly":
        return Poly(tuple(sorted(_prune(mapping).items())))

    def as_map(self) -> Coeffs:
        return {k: v for k, v in self.coeffs}

    def __add__(self, other: "Poly") -> "Poly":
        m = self.as_map()
        for k, v in other.coeffs:
            m[k] = m.get(k, Fraction(0)) + v
        return Poly.of(m)

    def __sub__(self, other: "Poly") -> "Poly":
        m = self.as_map()
        for k, v in other.coeffs:
            m[k] = m.get(k, Fraction(0)) - v
        return Poly.of(m)

    def __mul__(self, other: "Poly") -> "Poly":
        m: Coeffs = {}
        for k1, v1 in self.coeffs:
            for k2, v2 in other.coeffs:
                m[k1 + k2] = m.get(k1 + k2, Fraction(0)) + v1 * v2
        return Poly.of(m)

    def scaled(self, factor: Fraction) -> "Poly":
        return Poly.of({k: v * factor for k, v in self.coeffs})

    def power(self, exp: int) -> "Poly":
        if exp < 0:
            raise ValueError("negative powers are outside this algebra")
        result = Poly.of({0: Fraction(1)})
        for _ in range(exp):
            result = result * self
        return result


@dataclass(frozen=True)
class Relation:
    """`lhs = rhs`, each a Poly."""
    lhs: Poly
    rhs: Poly

    def moved(self) -> Poly:
        """lhs - rhs (== 0 form)."""
        return self.lhs - self.rhs

    def canonical(self) -> Poly:
        """Orientation/scale-independent normal form of `lhs - rhs`."""
        p = self.moved()
        if not p.coeffs:
            return p  # 0 == 0
        # sign-normalize on the highest-degree term
        top_exp = max(k for k, _ in p.coeffs)
        top_coef = p.as_map()[top_exp]
        sign = Fraction(-1) if top_coef < 0 else Fraction(1)
        m = {k: v * sign for k, v in p.coeffs}
        # reduce by gcd of numerators over lcm of denominators → integer, primitive
        denoms = [v.denominator for v in m.values()]
        lcm = 1
        for d in denoms:
            lcm = lcm * d // gcd(lcm, d)
        ints = {k: int(v * lcm) for k, v in m.items()}
        g = 0
        for v in ints.values():
            g = gcd(g, abs(v))
        if g:
            ints = {k: v // g for k, v in ints.items()}
        return Poly.of({k: Fraction(v) for k, v in ints.items()})


def relations_equal(a: Relation, b: Relation) -> bool:
    return a.canonical() == b.canonical()


# ── parsing ────────────────────────────────────────────────────────────────────────────────────────────────────

# unicode → ascii the parser understands
_SUPERSCRIPT = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5",
                "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9"}


def _normalize_math(s: str) -> str:
    s = s.replace("−", "-").replace("–", "-").replace("×", "*")
    # superscript digit(s) → ^N  (e.g. x²  → x^2 ,  x⁴ → x^4)
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in _SUPERSCRIPT:
            digits = ""
            while i < len(s) and s[i] in _SUPERSCRIPT:
                digits += _SUPERSCRIPT[s[i]]
                i += 1
            out.append("^" + digits)
        else:
            out.append(ch)
            i += 1
    return "".join(out)


_TERM_RE = re.compile(r"([+-]?)\s*(\d*)\s*(\*?)\s*(x?)\s*(?:\^\s*(\d+))?")


def _parse_side(text: str) -> Optional[Poly]:
    """Parse one side of the equation into a Poly; None if it isn't a clean polynomial."""
    t = text.strip().replace(" ", "")
    if not t:
        return None
    m: Coeffs = {}
    pos = 0
    consumed_any = False
    while pos < len(t):
        match = _TERM_RE.match(t, pos)
        if not match or match.end() == pos:
            return None
        sign, num, _star, xtok, exp = match.groups()
        if not (num or xtok):
            return None  # stray operator / empty term
        coef = Fraction(int(num)) if num else Fraction(1)
        if sign == "-":
            coef = -coef
        if xtok:
            power = int(exp) if exp else 1
        else:
            power = 0
        m[power] = m.get(power, Fraction(0)) + coef
        consumed_any = True
        pos = match.end()
    if not consumed_any:
        return None
    return Poly.of(m)


def parse_relation(text: str) -> Optional[Relation]:
    """Parse `LHS = RHS` (unicode-aware). None if it doesn't parse as a single-`=` polynomial relation."""
    norm = _normalize_math(text)
    if norm.count("=") != 1:
        return None
    left, right = norm.split("=")
    lhs = _parse_side(left)
    rhs = _parse_side(right)
    if lhs is None or rhs is None:
        return None
    return Relation(lhs, rhs)


# ── registered operations (canonical application) ────────────────────────────────────────────────────────────────

OperationFn = Callable[[Relation], Relation]


@dataclass(frozen=True)
class RegisteredOperation:
    operation_id: str
    operation_version: str
    apply: OperationFn
    # Whether the operation preserves the solution set under any domain (an equivalence rewrite). Squaring is NOT
    # equivalence-preserving (it can add solutions), so a `square_both_sides` rendered as an equivalence is refused.
    preserves_equivalence: bool = False


def _square_both_sides(rel: Relation) -> Relation:
    return Relation(rel.lhs.power(2), rel.rhs.power(2))


def _subtract_2(rel: Relation) -> Relation:
    two = Poly.of({0: Fraction(2)})
    return Relation(rel.lhs - two, rel.rhs - two)


def _divide_by_2(rel: Relation) -> Relation:
    half = Fraction(1, 2)
    return Relation(rel.lhs.scaled(half), rel.rhs.scaled(half))


_OPERATIONS: Dict[str, RegisteredOperation] = {
    op.operation_id: op
    for op in (
        RegisteredOperation("square_both_sides", "v1", _square_both_sides, preserves_equivalence=False),
        RegisteredOperation("subtract_2_from_both_sides", "v1", _subtract_2, preserves_equivalence=True),
        RegisteredOperation("divide_both_sides_by_2", "v1", _divide_by_2, preserves_equivalence=True),
    )
}


def get_operation(operation_id: str) -> Optional[RegisteredOperation]:
    return _OPERATIONS.get(operation_id)


# ── intent lexicon: surfaced phrase → registered operation_id (exact normalized match, never inference) ──────────

_INTENT_LEXICON: Dict[str, str] = {
    "square both sides": "square_both_sides",
    "squaring both sides": "square_both_sides",
    "subtract 2 from both sides": "subtract_2_from_both_sides",
    "subtracting 2 from both sides": "subtract_2_from_both_sides",
    "divide both sides by 2": "divide_both_sides_by_2",
    "dividing both sides by 2": "divide_both_sides_by_2",
}


def normalize_operation_phrase(phrase: str) -> Optional[str]:
    """Deterministically normalize a surfaced operation phrase to a registered operation_id (exact lexicon match).

    Returns None when the phrase is not a registered operation — the caller treats that as 'no operation surfaced',
    never a guess.
    """
    key = re.sub(r"\s+", " ", phrase.strip().lower()).rstrip(":.")
    return _INTENT_LEXICON.get(key)


_KNOWN_PHRASES = tuple(sorted(_INTENT_LEXICON, key=len, reverse=True))


def find_operation_phrase(text: str) -> Optional[Tuple[str, int, int]]:
    """Locate a known operation phrase in free prose → (matched_text, start, end). Longest phrase wins."""
    low = text.lower()
    for phrase in _KNOWN_PHRASES:
        idx = low.find(phrase)
        if idx != -1:
            return text[idx:idx + len(phrase)], idx, idx + len(phrase)
    return None


_RELATION_RE = re.compile(r"[0-9xX²³⁴⁰¹⁵⁶⁷⁸⁹\^\+\-\*\s]*=[\s]*[+\-−]?[0-9xX²³⁴⁰¹⁵⁶⁷⁸⁹\^\+\-\*\s]*")


def find_relations(text: str) -> Tuple[Tuple[Relation, int, int], ...]:
    """Find substrings that parse as relations → (relation, start, end), left to right."""
    found = []
    for m in _RELATION_RE.finditer(text):
        chunk = m.group().strip()
        rel = parse_relation(chunk)
        if rel is not None:
            found.append((rel, m.start(), m.end()))
    return tuple(found)
