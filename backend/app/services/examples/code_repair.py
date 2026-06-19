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
import re
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
    "implementation — the clearest version a textbook would teach FIRST. Rules: an entry-point "
    "function named for the ALGORITHM itself (never `main`); a separate helper ONLY if the algorithm "
    "genuinely needs one (e.g. merge sort = `merge_sort` + `merge`); every variable defined before it "
    "is used; no `if __name__` block, no driver, no example usage, no prints, no comments. "
    "PREFER VISIBLE DATA FLOW: a function that RETURNS its result and a caller that reassigns it, over "
    "one that mutates a passed-in argument and returns None — for divide-and-conquer (e.g. merge sort) "
    "write `return merge(left, right)` with `left = merge_sort(arr[:mid])`, NOT an in-place "
    "`merge_sort(left_half)` that returns None. EXCEPTION: keep inherently in-place algorithms in place "
    "(in-place reversal, partition/swap sorts, linked-list pointer surgery). "
    'Return ONLY JSON: {"code": "<the python implementation>"}.'
)


def _default_generator(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip().lower() == "dummy":
        return None
    try:
        from app.services.llm_client import OPENAI_MODEL, client

        # Per-call timeout caps a hung call; KEEP retries so a transient rate-limit/5xx recovers
        # rather than silently dropping the regenerated code.
        timeout = float(os.getenv("AZALEA_ENRICH_TIMEOUT_SECONDS", "60"))
        retries = max(0, int(os.getenv("AZALEA_ENRICH_MAX_RETRIES", "2")))
        response = client.with_options(timeout=timeout, max_retries=retries).responses.create(
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


_TITLE_STOPWORDS = {
    "implement", "implementing", "implementation", "the", "a", "an", "in", "python",
    "code", "coding", "algorithm", "algorithms", "using", "use", "with", "to", "of",
    "how", "for", "and", "build", "building", "write", "writing", "create", "creating",
    "function", "method", "approach", "version", "recursive", "iterative",
}


def _title_tokens(title: str) -> list[str]:
    raw = re.split(r"[^a-z0-9]+", str(title or "").lower())
    return [t for t in raw if t and t not in _TITLE_STOPWORDS]


def _missing_entrypoint(code: str, topic: dict[str, Any]) -> bool:
    """True when the code parses but never defines a function named for the topic's
    algorithm — a sign the walkthrough built only a helper (e.g. `merge`) and dropped
    the entry point (`merge_sort`). Conservative: only judges when the title yields
    tokens AND the code defines functions; otherwise returns False (leave it alone)."""
    tokens = _title_tokens(topic.get("title"))
    if not tokens:
        return False
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    fn_names = [n.name.lower() for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not fn_names:
        return False
    expected = "_".join(tokens)
    for name in fn_names:
        if name == expected or all(tok in name for tok in tokens):
            return False
    return True


def _combine_snippets(snippets: list[str]) -> str:
    """Merge all snippets into one module — every function defined across them, deduped by name
    (longest/most-complete body wins), in first-seen order. This lets merge_sort + merge that
    were split across separate cards validate TOGETHER, instead of a partial-but-valid `merge`
    beating the full implementation."""
    defs: dict[str, tuple[int, str]] = {}
    order: list[str] = []
    for snippet in snippets:
        try:
            tree = ast.parse(snippet)
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                src = ast.get_source_segment(snippet, node)
                if not src:
                    continue
                if node.name not in defs:
                    order.append(node.name)
                if node.name not in defs or len(src) > defs[node.name][0]:
                    defs[node.name] = (len(src), src)
    return "\n\n\n".join(defs[name][1] for name in order)


def _block_highlights(walkthrough_snippets: list[str], complete_code: str) -> list[list[list[int]]]:
    """For each code_walkthrough card (cumulative incremental code, in order), the highlight is
    the line range in the COMPLETE code that this card NEWLY introduces — its logical block — so
    the panel can highlight the part being explained."""
    full = complete_code.splitlines()
    content_to_lines: dict[str, list[int]] = {}
    for i, line in enumerate(full, start=1):
        s = line.strip()
        if s:
            content_to_lines.setdefault(s, []).append(i)

    out: list[list[list[int]]] = []
    prev: set[str] = set()
    used: set[int] = set()
    for snippet in walkthrough_snippets:
        cur = {ln.strip() for ln in snippet.splitlines() if ln.strip()}
        new = cur - prev
        prev = cur
        nums = sorted({n for s in new for n in content_to_lines.get(s, []) if n not in used})
        used.update(nums)
        out.append([[nums[0], nums[-1]]] if nums else [])
    return out


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
    """Make EVERY code card in a coding topic show the SAME complete, valid implementation, and
    give each code_walkthrough card a highlight range for the block it explains.

    The AUTHORITATIVE code is the COMBINED module (all functions across the cards, deduped,
    longest body each) when that validates — so merge_sort + merge split across cards become the
    full implementation, not a partial-but-valid `merge`. Otherwise the longest valid single
    snippet; otherwise a clean regeneration. Failure-safe."""
    try:
        if str(topic.get("topic_type") or "").lower() != "coding_implementation":
            return False
        cards = lesson_json.get("lesson_cards")
        if not isinstance(cards, list):
            return False
        code_cards = _coding_code_cards(cards)
        if not code_cards:
            return False

        snippets = [str(c.get("code_snippet")) for c in code_cards]
        combined = _combine_snippets(snippets)
        if combined and not code_has_undefined_names(combined):
            authoritative = combined
        else:
            valid = [s for s in snippets if not code_has_undefined_names(s)]
            authoritative = max(valid, key=len) if valid else generate_clean_code(
                topic, broken_code=max(snippets, key=len), generator=generator,
            )
        # Valid-but-incomplete: the assembled code parses and has no undefined names,
        # yet never defines the algorithm's own entry function (e.g. a merge sort topic
        # whose walkthrough only ever built `merge`, never `merge_sort`). Asked plainly,
        # the model returns the complete implementation — regenerate and prefer it only
        # when it actually supplies the missing entry point.
        if authoritative and _missing_entrypoint(authoritative, topic):
            regenerated = generate_clean_code(topic, broken_code=authoritative, generator=generator)
            if regenerated and not _missing_entrypoint(regenerated, topic):
                _log.info("code_repair: %s missing entry point — regenerated complete code", topic.get("id"))
                authoritative = regenerated
        if not authoritative:
            _log.warning("code_repair: %s has no valid code and regeneration failed", topic.get("id"))
            return False

        # Per-card block highlights for the walkthrough, derived from the ORIGINAL snippets mapped
        # onto the authoritative code — used only when a card's code actually changes (its own
        # per-bullet highlights then go stale). When the card already carried the complete code,
        # its LLM-authored per-bullet highlight_lines_per_step are kept as-is.
        walkthrough = [c for c in code_cards
                       if str(c.get("blueprint_key") or "").lower() == "code_walkthrough"]
        wt_originals = [str(c.get("code_snippet")) for c in walkthrough]
        wt_block_highlights = _block_highlights(wt_originals, authoritative)

        changed = False
        for card in code_cards:
            if str(card.get("code_snippet")) != authoritative:
                card["code_snippet"] = authoritative
                card.setdefault("metadata", {})["clean_code_repair"] = True
                changed = True
        for card, hl, orig in zip(walkthrough, wt_block_highlights, wt_originals):
            if orig != authoritative:  # this card's code changed -> its highlights were stale
                card["highlight_lines_per_step"] = hl
        if changed:
            lesson_json.setdefault("metadata", {})["clean_code_repair"] = True
        return changed
    except Exception as exc:  # noqa: BLE001 — never break a lesson
        _log.warning("code_repair: apply failed for %s: %s", topic.get("id"), exc)
        return False
