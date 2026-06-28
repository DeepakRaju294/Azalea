"""Content-shape checker (STUDY_PATH_CONTENT_SPEC §H / M6) — an instructional-quality linter.

Validators (M3) protect correctness; this protects against quality regression. Given a lesson's cards it
returns the §H content-shape violations (too many Work bullets, raw-dict Result, a coding step with no
code anchor, a redundant raw-stage-id Goal, a missing stopping statement). Pure + offline, so it doubles
as: (a) a regression gate over golden fixtures, and (b) a one-call audit of any generated lesson
(`worked_example_shape_violations(lesson_cards)`) instead of eyeballing the output.
"""
from __future__ import annotations

import re
from typing import Any

_MAX_WORK_LINES = 2
_RAW_STAGE_GOAL = re.compile(r"^\s*goal:\s*[a-z_]+\s*$", re.I)     # "Goal: consider_edge"
_RAW_DICT = re.compile(r"\{\s*['\"]")                              # a JSON/dict literal in the text


def _is_step(card: dict[str, Any]) -> bool:
    return (card.get("blueprint_key") == "worked_example"
            and (card.get("metadata") or {}).get("example", {}).get("role") == "step")


def _work_lines(card: dict[str, Any]) -> list[str]:
    if isinstance(card.get("work"), list):
        return [str(w) for w in card["work"]]
    out = []
    for p in (card.get("points") or []):
        s = str(p)
        if s.startswith("  - ") or s.strip().startswith("- "):
            out.append(s.strip()[1:].strip())
    return out


def _result_text(card: dict[str, Any]) -> str:
    if card.get("result"):
        return str(card["result"])
    for p in (card.get("points") or []):
        if str(p).startswith("Result"):
            return str(p)
    return ""


def _goal_line(card: dict[str, Any]) -> str:
    if card.get("goal"):
        return f"Goal: {card['goal']}"
    return next((str(p) for p in (card.get("points") or []) if str(p).lower().startswith("goal:")), "")


def worked_example_shape_violations(cards: list[dict[str, Any]], *,
                                    coding: bool = False) -> list[str]:
    """The §H content-shape issues in a lesson's worked-example steps (empty list = clean)."""
    steps = [c for c in (cards or []) if isinstance(c, dict) and _is_step(c)]
    issues: list[str] = []
    cap = 4 if coding else _MAX_WORK_LINES          # coding Work = verbatim code lines, so a higher cap
    for c in steps:
        title = str(c.get("title") or "?")[:40]
        work = _work_lines(c)
        if len(work) > cap:
            issues.append(f"{title}: {len(work)} Work lines (> {cap})")
        result = _result_text(c)
        if _RAW_DICT.search(result):
            issues.append(f"{title}: Result is a raw dict, not prose")
        if not result.strip():
            issues.append(f"{title}: no Result")
        if _RAW_STAGE_GOAL.match(_goal_line(c)):
            issues.append(f"{title}: Goal is a raw stage id (redundant with the title)")
        if coding and not ((c.get("metadata") or {}).get("code_lines")
                           or (c.get("metadata") or {}).get("code_block")):
            issues.append(f"{title}: coding step has no code anchor (code_lines/code_block)")
    # titles: a raw stage-id title ("Step 3: Select_edge") repeats every step and reads generated
    suffixes = [re.sub(r"^step\s+\d+\s*[:.\-]?\s*", "", str(c.get("title") or ""), flags=re.I).strip().lower()
                for c in steps]
    if any(re.fullmatch(r"[a-z]+(?:_[a-z]+)*", s) for s in suffixes if s):
        issues.append("a step title is a raw operation id (e.g. 'Select_edge')")
    nonempty = [s for s in suffixes if s]
    if len(nonempty) >= 3 and len(set(nonempty)) == 1:
        issues.append(f"all step titles repeat the same label ('{nonempty[0]}')")
    if steps:
        last = _result_text(steps[-1]).lower()
        if not re.search(r"complete|all (?:nodes|vertices|elements)|finished|done|final", last):
            issues.append("final step does not state completion")
    return issues
