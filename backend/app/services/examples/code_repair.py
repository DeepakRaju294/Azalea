"""Validate coding-implementation code and repair it with a clean LLM regeneration.

The lean pipeline builds code_walkthrough snippets incrementally and runs them through
several AST transforms; on real algorithms (merge sort) this drops lines and ships code
that uses undefined variables (`left`/`right` with no `left = arr[:mid]`). Asked plainly,
the model produces correct code every time — so instead of trusting the transforms, we
VALIDATE the lesson's code and, when it's broken, replace it with one focused, clean,
validated regeneration. Minimal edits, LLM-authored, correct.

Re-solvable: runs at enrichment time (alongside the worked-example solver). Failure-safe:
any problem leaves the existing code untouched. The generator is injectable for tests.
"""
from __future__ import annotations

import ast
import builtins
import json
import logging
import os
from typing import Any, Callable, Optional

_log = logging.getLogger(__name__)

_BUILTINS = set(dir(builtins)) | {"self", "cls"}
GenFn = Callable[[dict[str, Any]], Optional[dict[str, Any]]]


def _assigned_in(fn: ast.AST) -> set[str]:
    """Every name BOUND anywhere in a function — params, assignments, loop/with/except
    targets, comprehension targets, nested def/class names. Over-approximates (ignores
    order) on purpose: it must not flag a name that is assigned somewhere, only ones that
    are NEVER assigned (the real bug)."""
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.alias):
            names.add((node.asname or node.name).split(".")[0])
    return names


def code_has_undefined_names(code: str) -> bool:
    """True if the code won't parse, defines no function, or a function loads a name that
    is never a parameter/assignment/import/builtin/module function (e.g. merge sort using
    `left` and `right` that were never sliced out)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return True
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not funcs:
        return True
    module_names = _BUILTINS | {n.name for n in tree.body
                                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    module_names.add(sub.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                module_names.add((a.asname or a.name).split(".")[0])
    for fn in funcs:
        bound = module_names | _assigned_in(fn)
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in bound:
                return True
    return False


_CODE_GEN_SYSTEM = (
    "You implement algorithms in Python. Output ONLY the complete, correct, runnable "
    "implementation — exactly the clean solution you would give if asked plainly to "
    "'implement <algorithm>'. Rules: an entry-point function named for the ALGORITHM "
    "itself (never `main`); a separate helper ONLY if the algorithm genuinely needs one "
    "(e.g. merge sort = `merge_sort` + `merge`); every variable defined before it is used; "
    "no `if __name__` block, no driver, no example usage, no prints, no comments. "
    'Return ONLY JSON: {"code": "<the python implementation>"}.'
)


def _default_generator(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip().lower() == "dummy":
        return None
    try:
        from app.services.llm_client import OPENAI_MODEL, client

        response = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {"role": "system", "content": _CODE_GEN_SYSTEM},
                {"role": "user", "content": str(payload.get("user") or "")},
            ],
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text)
    except Exception as exc:  # noqa: BLE001
        _log.warning("code_repair: LLM call failed: %s", exc)
        return None


def generate_clean_code(
    topic: dict[str, Any], *, broken_code: str = "", generator: Optional[GenFn] = None,
) -> Optional[str]:
    """Focused regeneration of the complete, correct implementation. Returns the code only
    if it parses and has no undefined names; else None."""
    fn = generator or _default_generator
    title = str(topic.get("title") or "").strip() or "the algorithm"
    user = f"Implement {title} in Python — the clean, complete, correct implementation."
    if broken_code:
        user += ("\n\nThe lesson's current code is broken (uses undefined variables / is "
                 "incomplete). Produce a correct complete replacement:\n\n" + broken_code)
    try:
        raw = fn({"user": user, "topic": topic})
    except Exception as exc:  # noqa: BLE001
        _log.warning("code_repair: generator raised: %s", exc)
        return None
    if not isinstance(raw, dict):
        return None
    code = str(raw.get("code") or "").strip()
    if not code or code_has_undefined_names(code):
        return None
    return code


def _coding_code_cards(cards: list[Any]) -> list[dict[str, Any]]:
    return [
        c for c in cards
        if isinstance(c, dict)
        and str(c.get("blueprint_key") or c.get("card_type") or "").lower() in ("code_walkthrough", "worked_example")
        and str(c.get("code_snippet") or "").strip()
    ]


def apply_clean_code_to_lesson(
    lesson_json: dict[str, Any], topic: dict[str, Any], *, generator: Optional[GenFn] = None,
) -> bool:
    """For a coding topic whose code is BROKEN, replace every code card's snippet with one
    clean, validated regeneration. Valid code is left as the LLM wrote it. Failure-safe."""
    try:
        if str(topic.get("topic_type") or "").lower() != "coding_implementation":
            return False
        cards = lesson_json.get("lesson_cards")
        if not isinstance(cards, list):
            return False
        code_cards = _coding_code_cards(cards)
        if not code_cards:
            return False
        # Longest snippet is the most complete candidate; validate that.
        current = max((str(c.get("code_snippet")) for c in code_cards), key=len)
        if not code_has_undefined_names(current):
            return False  # the LLM's own code is already valid — keep it

        clean = generate_clean_code(topic, broken_code=current, generator=generator)
        if not clean:
            _log.warning("code_repair: %s has broken code but regeneration failed", topic.get("id"))
            return False
        for card in code_cards:
            card["code_snippet"] = clean
            card["highlight_lines_per_step"] = []  # code changed — old highlights are stale
            card.setdefault("metadata", {})["clean_code_repair"] = True
        lesson_json.setdefault("metadata", {})["clean_code_repair"] = True
        return True
    except Exception as exc:  # noqa: BLE001 — never break a lesson
        _log.warning("code_repair: apply failed for %s: %s", topic.get("id"), exc)
        return False
