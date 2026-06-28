"""Deterministic trace -> code-line mapper (Option 1; no LLM call, no canonical/hardcoded code).

A coding worked example shows TWO already-existing artifacts side by side:
  * the implementation the LLM wrote for the lesson (the `code_snippet` panel), and
  * the verified, adapter-produced trace (conceptual: "consider edge (A,B,2); accept").
The verified trace carries no line numbers of its own (it is intentionally code-agnostic), so the
code panel sits static with nothing highlighted. This module bridges the two by matching each
worked-example WORK action (LLM prose such as "call find(A)", "union the two components",
"append edge (A,B,2) to the MST") onto the line of the shown code that shares the most identifiers.

Because the trace is ALREADY verified independently of the code, a near-miss line is only a cosmetic
mislocation of the highlight — it can never make the example wrong. That is what makes a best-effort
heuristic acceptable here (and why we don't need to store or generate any code).
"""
from __future__ import annotations

import ast
import keyword
import re
from typing import Optional

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Pure English/structural glue that carries no mapping signal. Deliberately SMALL: operation words
# (find, union, append, push, pop, sort, parent, visited, ...) are exactly the bridge between the
# prose and the code, so they are NOT stopped. Python keywords are stopped (every line has them).
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "is", "are", "be", "in", "on", "at", "for", "with",
    "as", "by", "it", "its", "so", "now", "then", "this", "that", "these", "those", "we", "i",
    "from", "into", "not", "no", "out", "up", "do", "does", "has", "have", "was", "were", "will",
    "self", "true", "false", "none",
} | set(keyword.kwlist)


def _idents(text: str) -> set[str]:
    """Lower-cased identifier tokens in `text`, minus glue/keywords."""
    return {m.group(0).lower() for m in _IDENT.finditer(text or "")} - _STOP


def map_work_lines_to_code(code: str, work: list[str]) -> Optional[list[list[int]]]:
    """One ``[line]`` per WORK action (1-based), chosen by maximum identifier overlap with a code
    line. Ties break toward forward progress (closest to the previously chosen line) so a step's
    actions read top-to-bottom through the body; an action with no overlap holds on the previous
    line rather than jumping. Returns ``None`` when nothing maps (caller then leaves the card as-is).

    Called PER CARD with that one step's work actions, so the bias is intra-step only — consecutive
    loop iterations (separate cards) each start fresh and re-highlight the same body.
    """
    if not code or not work:
        return None
    raw_lines = code.split("\n")
    line_idents = [(_idents(ln), bool(ln.strip())) for ln in raw_lines]
    out: list[list[int]] = []
    prev = 0                                    # last chosen 1-based line (0 = none yet this card)
    matched_any = False
    for action in work:
        wt = _idents(action)
        best_line, best_score = 0, 0
        if wt:
            for i, (lt, nonblank) in enumerate(line_idents, start=1):
                if not nonblank or not lt:
                    continue
                score = len(wt & lt)
                if score == 0:
                    continue
                if score > best_score:
                    best_score, best_line = score, i
                elif score == best_score and best_line and prev and \
                        abs(i - prev) < abs(best_line - prev):
                    best_line = i                # same overlap: prefer the line nearer the cursor
        if best_line:
            matched_any = True
            prev = best_line
            out.append([best_line])
        else:
            out.append([prev] if prev else [])   # no signal: hold on the cursor (or empty)
    return out if matched_any else None


# --- structural fallback ---------------------------------------------------------------------------
# When the work prose is a STATE dump (e.g. "selected_edges: []", "chosen edge: ['A','B',2]") rather
# than operation narration, identifier overlap finds nothing. But a worked-example step is exactly ONE
# iteration of the algorithm's main loop, so the honest highlight is that loop's body — narrowed to
# just the guard line for a "negative" step (a skip/no-op iteration). Fully structural (AST), so it
# works on any implementation without hardcoding a single line number.

_NEGATIVE = re.compile(
    r"\b(skip|skipp|reject|cycle|already|no improvement|unchanged|not added|"
    r"discard|ignore|prune|not found|absent)\b", re.I)


def looks_negative(text: str) -> bool:
    """True when a step's prose marks a no-progress iteration (skip/reject/cycle/unchanged/…)."""
    return bool(_NEGATIVE.search(text or ""))


def main_loop_span(code: str) -> Optional[tuple[int, int, int]]:
    """``(body_start, body_end, guard_line)`` of the implementation's DOMINANT loop (the one whose
    body spans the most lines — the algorithm's main pass), all 1-based. ``guard_line`` is the first
    ``if`` test inside the loop (or ``body_start`` when there is none). ``None`` if unparseable / no
    loop. Used to highlight "the code this iteration runs"."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return None
    best: Optional[tuple[int, int, int, int]] = None     # (span, body_start, body_end, guard)
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)) and node.body:
            body_start = node.body[0].lineno
            body_end = max((getattr(n, "end_lineno", None) or n.lineno) for n in ast.walk(node)
                           if hasattr(n, "lineno"))
            guard = next((n.test.end_lineno or n.test.lineno
                          for n in node.body if isinstance(n, ast.If)), body_start)
            span = body_end - body_start
            if best is None or span > best[0]:
                best = (span, body_start, body_end, guard)
    if best is None:
        return None
    return (best[1], best[2], best[3])


def code_block_for_step(code: str, *, negative: bool) -> Optional[list[int]]:
    """``[start, end]`` lines to highlight for ONE worked-example step: the main loop body for a
    normal (progress) iteration, or just the loop guard for a negative (skip) iteration. ``None`` when
    the code has no parseable loop (caller then leaves the card unhighlighted)."""
    span = main_loop_span(code)
    if span is None:
        return None
    body_start, body_end, guard = span
    return [body_start, guard] if negative else [body_start, body_end]
