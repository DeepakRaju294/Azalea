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
    """Work/step lines from a card in either shape: gen_foundation `work[]` or lesson-card `points[]`."""
    if card.get("work"):
        return [str(w) for w in card["work"]]
    out: list[str] = []
    for p in (card.get("points") or []):
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, dict):
            out.append(str(p.get("text") or p.get("value") or p.get("label") or ""))
    return out


def worked_example_correctness_violations(
    cards: list[dict[str, Any]], topic: dict[str, Any]
) -> list[str]:
    """Reference-backed correctness for a FINAL worked example (any generator: gen_foundation OR the
    legacy solver). Recovers the input graph from the problem card, derives the family, and runs the
    structural + differential gates on the stated final answer — plus an MST-completeness check that
    catches a VAGUE/incomplete final ('Final MST edges collection') the structural parser can't. This is
    what gates the legacy path, where the wrong/vague MST examples actually ship."""
    if not cards:
        return []
    from app.core.topic_family import derive_topic_family
    from .property_checks import (
        claimed_answer_violations, parse_weighted_graph_from_text, _claimed_groups,
    )

    family = derive_topic_family(topic.get("title"), topic.get("topic_type") or topic.get("course_type"))
    problem = " ".join(_work_lines(cards[0]))
    final = " ".join(_work_lines(cards[-1]))
    example_input = parse_weighted_graph_from_text(problem)

    violations = list(walkthrough_mode_violations(cards))
    violations.extend(claimed_answer_violations(family, example_input, final))

    # MST completeness: a vague/incomplete final states fewer than V-1 edges (claimed_answer_violations
    # can't fire when it parses 0 edges, so check it explicitly here).
    if "mst" in family or "spanning" in family:
        labels = {str(n) for n in example_input.get("nodes") or []}
        v = len(labels)
        if v >= 2:
            final_edges = sum(
                1 for g in _claimed_groups(final)
                if len([t for t in re.findall(r"[A-Za-z_]\w*", g) if t in labels]) >= 2)
            if final_edges < v - 1:
                violations.append(
                    f"worked example: the final answer states {final_edges} MST edges, but a complete MST "
                    f"on {v} nodes has V-1={v - 1} — the example is vague or incomplete")
    return violations


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
