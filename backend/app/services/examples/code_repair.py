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


def looks_like_setup_only(code: str) -> bool:
    """True when the code defines functions but DOES NOTHING with them — only assignments, with no
    loop, no recursion, no comprehension, and no value-returning result. That signature (`def bfs:
    visited = set(); queue = [start]` with no `while` loop) means the model emitted just the setup
    and dropped the algorithm body, so the walkthrough/worked example reference lines the code never
    contains. Such code should be regenerated into a complete implementation."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not funcs:
        return False
    has_iteration = any(
        isinstance(n, (ast.For, ast.AsyncFor, ast.While, ast.ListComp, ast.SetComp,
                       ast.DictComp, ast.GeneratorExp))
        for n in ast.walk(tree)
    )
    fn_names = {f.name for f in funcs}
    has_recursion = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in fn_names
        for n in ast.walk(tree)
    )
    has_value_return = any(isinstance(n, ast.Return) and n.value is not None for n in ast.walk(tree))
    return not (has_iteration or has_recursion or has_value_return)


# Standard-library modules whose data structures ARE the idiomatic/canonical form of common
# algorithms (a `heapq` priority queue is Dijkstra/Prim/Huffman; a `deque` is BFS's queue). These are
# zero-install and exactly what a learner gets when they look up the real implementation, so we KEEP
# them rather than forcing an inefficient `sorted()`+`pop(0)` hand-roll. Anything outside this set — a
# third-party package, or a stdlib module that hides system state / non-determinism — is regenerated
# away, because a library that performs the algorithm defeats the lesson and the trace must stay
# deterministic and self-contained.
ALLOWED_STDLIB_MODULES = frozenset({
    "heapq", "collections", "math", "itertools", "bisect", "functools",
})


def _imported_module_roots(code: str) -> set[str]:
    """Root module names imported by the code (``from collections import deque`` -> ``collections``)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    roots: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in n.names)
        elif isinstance(n, ast.ImportFrom):
            roots.add(n.module.split(".")[0] if (n.module and not n.level) else ".")  # "." = relative
    return roots


def has_disallowed_imports(code: str) -> bool:
    """True if the code imports anything OUTSIDE the curated stdlib allow-list. Allowed stdlib
    (heapq/collections/math/itertools/bisect/functools) is the idiomatic form of canonical algorithms
    and is kept; third-party packages and algorithm-doing libraries are regenerated away."""
    return bool(_imported_module_roots(code) - ALLOWED_STDLIB_MODULES)


def _is_closure_free(fn: ast.AST, module_names: set[str]) -> bool:
    """A nested function can be lifted to top level only if it captures NOTHING from its enclosing
    scope — every Name it loads is its own param/local, a module-level name, or a builtin."""
    bound = {getattr(fn, "name", "")}
    for node in ast.walk(fn):
        if isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not fn:
            bound.add(node.name)
    loaded = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return not (loaded - bound - module_names - _BUILTINS)


def lift_nested_helpers(code: str) -> str:
    """Standardize coding examples so helpers are SEPARATE top-level functions, not nested inside the
    entry function (e.g. inorderTraversal + traverse as two defs). Only closure-free nested functions
    are lifted; the entry function keeps its position and its helper follows it. Returns the code
    UNCHANGED when nothing is safe to lift, so an already-flat implementation keeps its exact
    formatting (we only reformat when we actually un-nest)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    module_names = {n.name for n in tree.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    lifted_by_parent: dict[int, list[ast.stmt]] = {}
    lifted_ids: set[int] = set()
    for parent in tree.body:
        if not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in parent.body:
            if (isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and _is_closure_free(child, module_names)):
                lifted_by_parent.setdefault(id(parent), []).append(child)
                lifted_ids.add(id(child))
    if not lifted_ids:
        return code
    new_body: list[ast.stmt] = []
    for stmt in tree.body:
        if id(stmt) in lifted_by_parent and isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stmt.body = [c for c in stmt.body if id(c) not in lifted_ids]
            new_body.append(stmt)                         # entry function stays first
            new_body.extend(lifted_by_parent[id(stmt)])   # its helper(s) follow as top-level defs
        else:
            new_body.append(stmt)
    tree.body = new_body
    ast.fix_missing_locations(tree)
    try:
        out = ast.unparse(tree)
    except Exception:  # noqa: BLE001 — fall back to the original on any unparse hiccup
        return code
    # ast.unparse drops blank lines between defs; restore 2 blank lines for readability.
    return re.sub(r"\n+(def |async def |class )", r"\n\n\n\1", out)


_CODE_GEN_SYSTEM = (
    "You implement algorithms in Python. Output ONLY the complete, correct, runnable "
    "implementation — the clearest version a textbook would teach FIRST. Rules: an entry-point "
    "function named for the ALGORITHM itself (never `main`); a separate helper ONLY if the algorithm "
    "genuinely needs one (e.g. merge sort = `merge_sort` + `merge`) — define every helper as its OWN "
    "TOP-LEVEL function, NEVER nested inside another function; every variable defined before it "
    "is used; no `if __name__` block, no driver, no example usage, no prints, no comments. "
    "USE THE STANDARD LIBRARY THE REAL IMPLEMENTATION USES — `import heapq` for a priority queue "
    "(Dijkstra / Prim / Huffman / top-k / k-way merge), `from collections import deque` for a FIFO "
    "queue (BFS / sliding window), `defaultdict` / `Counter` for grouping and counting, and `math`, "
    "`itertools`, `bisect`, `functools` where idiomatic. Do NOT hand-roll these with `sorted()` + "
    "`pop(0)` or a list you re-`.sort()` every iteration — that is slower and is NOT how the algorithm "
    "is actually written; a learner who looks this up should see the SAME code. HARD LIMITS: NEVER use "
    "a third-party package (numpy, pandas, networkx, sortedcontainers, ...), NEVER call a library "
    "function that performs the task itself (e.g. `networkx.minimum_spanning_tree`, or `heapq.nsmallest`/"
    "`sorted()` used to REPLACE the algorithm's own loop) — the learner must SEE the algorithm run, not "
    "delegate it — and no `random` / `os` / `sys` (keep it deterministic and self-contained). "
    "PREFER VISIBLE DATA FLOW: a function that RETURNS its result and a caller that reassigns it, over "
    "one that mutates a passed-in argument and returns None — for divide-and-conquer (e.g. merge sort) "
    "write `return merge(left, right)` with `left = merge_sort(arr[:mid])`, NOT an in-place "
    "`merge_sort(left_half)` that returns None. EXCEPTION: keep inherently in-place algorithms in place "
    "(in-place reversal, partition/swap sorts, linked-list pointer surgery). "
    "CONTRACT — get the INPUT and OUTPUT shape exactly right, this is where implementations silently go "
    "wrong: decide a clear input representation and a clear return value, and make the code actually "
    "produce THAT. For a graph algorithm, return the real result the name promises — an MST function "
    "returns the tree's EDGES as (u, v, weight) tuples that connect ALL vertices (exactly V-1 of them), "
    "never a list of (weight, vertex) records; a shortest-path function returns distances/paths. Handle "
    "the obvious edge cases (empty input, a single element, a disconnected graph) without crashing or "
    "silently dropping a vertex. Reason through a tiny example before finalizing to confirm the output "
    "is COMPLETE and CORRECT (e.g. an MST on N nodes has N-1 edges covering every node). "
    'Return ONLY JSON: {"code": "<the python implementation>"}.'
)


def _default_generator(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip().lower() == "dummy":
        return None
    try:
        from app.services.llm_client import OPENAI_MODEL, client, llm_call

        # Per-call timeout caps a hung call; KEEP retries so a transient rate-limit/5xx recovers
        # rather than silently dropping the regenerated code.
        timeout = float(os.getenv("AZALEA_ENRICH_TIMEOUT_SECONDS", "60"))
        retries = max(0, int(os.getenv("AZALEA_ENRICH_MAX_RETRIES", "2")))
        with llm_call("clean_code"):
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
        # Focused-call-first (AZALEA_FOCUSED_CODE_GEN): get the authoritative code from ONE focused,
        # full-attention "implement X" call rather than stitching the mega-lesson call's by-product.
        # Used verbatim when valid; falls back to the combined snippets otherwise.
        focused = (generate_clean_code(topic, generator=generator)
                   if os.getenv("AZALEA_FOCUSED_CODE_GEN", "") not in ("", "0") else None)
        if focused:
            authoritative = focused
        else:
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
        # Setup-only: parses and has no undefined names, but has no loop/recursion/return — just
        # initialization (the BFS `while` loop, the traversal recursion, etc. were dropped). The
        # walkthrough/worked example then reference lines the code never contains. Regenerate.
        if authoritative and looks_like_setup_only(authoritative):
            regenerated = generate_clean_code(topic, broken_code=authoritative, generator=generator)
            if regenerated and not looks_like_setup_only(regenerated):
                _log.info("code_repair: %s code was setup-only — regenerated full implementation", topic.get("id"))
                authoritative = regenerated
        # Imports: KEEP the curated stdlib the canonical implementation uses (heapq / deque /
        # defaultdict / ...); regenerate only when the code pulls in a third-party package or an
        # algorithm-doing library, which would hide the algorithm from the learner.
        if authoritative and has_disallowed_imports(authoritative):
            regenerated = generate_clean_code(topic, broken_code=authoritative, generator=generator)
            if regenerated and not has_disallowed_imports(regenerated):
                _log.info("code_repair: %s used a disallowed import — regenerated within the stdlib allow-list",
                          topic.get("id"))
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
