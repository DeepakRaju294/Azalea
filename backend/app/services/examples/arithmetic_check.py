"""Deterministic arithmetic-consistency checker for a free-prose worked example (adapter-free accuracy).

No adapter, no LLM, no oracle — pure text/number checks over the worked-example cards. It catches the two
internal-consistency failures that self-graded prose routinely ships, and that an endpoint answer-anchor
misses (they are about the STEPS, not just the final answer):

  (1) EQUATION doesn't hold — a chain "a = b = c" where the arithmetic segments are not equal, e.g.
      "1900 / 11700 = 19 / 95"  (0.162 != 0.2)   →  the 19/95 fraction slip.
  (2) SYMBOL bound to two DIFFERENT values — "P(A) = 0.68" in one card, "P(A) = 0.88" in another  →
      the self-contradicting "verification" step.

Runs offline; returns a list of human-readable violation strings ([] == consistent)."""
from __future__ import annotations

import ast
import re
from typing import Any, Iterable, Optional

_ARITH_ONLY = re.compile(r"^[\d\s+\-*/().]+$")
_SYMBOL_OK = re.compile(r"^[A-Za-z][A-Za-z0-9()|_'.\s]*$")   # a plausible math symbol/name, not a prose clause
_TOL = 1e-6


def _eval_node(n: ast.AST) -> Optional[float]:
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
        return float(n.value)
    if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        a, b = _eval_node(n.left), _eval_node(n.right)
        if a is None or b is None:
            return None
        if isinstance(n.op, ast.Add):
            return a + b
        if isinstance(n.op, ast.Sub):
            return a - b
        if isinstance(n.op, ast.Mult):
            return a * b
        return a / b if b != 0 else None
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
        v = _eval_node(n.operand)
        if v is None:
            return None
        return v if isinstance(n.op, ast.UAdd) else -v
    return None


def _safe_eval(expr: str) -> Optional[float]:
    """Evaluate a PURE-arithmetic string (numbers and + - * / ( ) only). None if it isn't pure arithmetic."""
    s = expr.strip()
    if not s or not _ARITH_ONLY.match(s) or not re.search(r"\d", s):
        return None
    try:
        return _eval_node(ast.parse(s, mode="eval").body)
    except (SyntaxError, ValueError, RecursionError):
        return None


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= _TOL * max(1.0, abs(a), abs(b))


def _strip_thousands(s: str) -> str:
    return re.sub(r"(?<=\d),(?=\d\d\d\b)", "", s)          # "1,900" -> "1900" (only 3-digit groups)


def _lines(cards: Iterable[Any]) -> Iterable[str]:
    for c in cards or []:
        if not isinstance(c, dict):
            if c:
                yield str(c)
            continue
        pts = c.get("points")
        if isinstance(pts, list):
            for p in pts:
                yield str(p)
        elif pts:
            yield str(pts)
        for k in ("body", "result", "reasoning", "work"):
            v = c.get(k)
            if isinstance(v, list):
                for x in v:
                    yield str(x)
            elif v:
                yield str(v)


def check_arithmetic_consistency(cards: Iterable[Any]) -> list[str]:
    """Return a list of arithmetic-consistency violations across the worked-example cards ([] == clean)."""
    violations: list[str] = []
    symbol_value: dict[str, tuple[float, str]] = {}
    for raw in _lines(cards):
        line = _strip_thousands(raw)
        segs = [s.strip() for s in line.split("=")]
        if len(segs) < 2:
            continue
        vals = [_safe_eval(s) for s in segs]
        # (1) equation consistency — adjacent arithmetic segments of an "a = b = c" chain must be equal.
        for i in range(len(vals) - 1):
            if vals[i] is not None and vals[i + 1] is not None and not _close(vals[i], vals[i + 1]):
                violations.append(
                    f"equation does not hold: '{segs[i]}' ({round(vals[i], 6)}) != "
                    f"'{segs[i + 1]}' ({round(vals[i + 1], 6)})")
        # (2) symbol consistency — "SYM = ... = number" binds SYM to the chain's final numeric value; the
        # same symbol must not later be bound to a DIFFERENT value (the self-contradicting "verify" step).
        lhs = segs[0]
        if vals[0] is None and _SYMBOL_OK.match(lhs) and len(lhs) <= 24 and lhs.count(" ") <= 3:
            final_val = next((v for v in reversed(vals) if v is not None), None)
            if final_val is not None:
                sym = re.sub(r"\s+", "", lhs).lower().rstrip(":")
                if sym in symbol_value and not _close(symbol_value[sym][0], final_val):
                    prev, prev_line = symbol_value[sym]
                    violations.append(
                        f"symbol {lhs!r} bound to conflicting values: {prev} ('{prev_line}') vs "
                        f"{final_val} ('{line.strip()}')")
                else:
                    symbol_value.setdefault(sym, (final_val, line.strip()))
    return violations
