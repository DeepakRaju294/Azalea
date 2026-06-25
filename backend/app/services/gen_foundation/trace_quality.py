"""Worked-example trace-quality checks (inaccuracy #5: "second code walkthrough" instead of a trace).

A coding worked example must TRACE the algorithm on a concrete input — operate on real values — not
re-DEFINE the code. The Kruskal example degenerated into cards titled "find function…"/"union function…"
whose work was `def find(...)`/`def union(...)` and whose result was "function ready for use": that is a
code walkthrough wearing a worked-example label. These checks flag that so it routes to repair.

Pure, defensive, conservative — only flags the strong signals (a step that DEFINES a function/class, or
a result that announces a construct is "ready" rather than a computed value).
"""
from __future__ import annotations

import re
from typing import Any

_DEF_LINE = re.compile(r"^\s*(?:async\s+def|def|class)\s+\w")
_READY_RESULT = re.compile(
    r"\b(?:ready (?:for|to) use|ready for combining|function (?:is )?(?:now )?(?:ready|defined|implemented)"
    r"|(?:defined|implemented) (?:the|a) \w+ function|set up the \w+ function)\b",
    re.IGNORECASE,
)


def _work_lines(card: dict[str, Any]) -> list[str]:
    return [str(w) for w in (card.get("work") or [])]


def walkthrough_mode_violations(cards: list[dict[str, Any]]) -> list[str]:
    """Flag worked-example cards that DEFINE code instead of tracing concrete values (#5)."""
    violations: list[str] = []
    for i, card in enumerate(cards):
        lines = _work_lines(card)
        # the verbatim-code form is "code // explanation"; only inspect the code part
        code_parts = [ln.split("//", 1)[0] for ln in lines]
        if any(_DEF_LINE.match(part) for part in code_parts):
            violations.append(
                f"card {i}: a worked-example step DEFINES a function/class (def/class) — a trace must run "
                f"the algorithm on concrete values, not re-define the code (call the helper and show its "
                f"return, e.g. find('A') -> 'A')")
            continue
        if _READY_RESULT.search(str(card.get("result") or "")):
            violations.append(
                f"card {i}: the result announces a construct is 'ready/defined' rather than a computed "
                f"value — a worked-example step must produce a concrete result")
    return violations
