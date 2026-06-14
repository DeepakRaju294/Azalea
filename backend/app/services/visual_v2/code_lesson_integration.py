"""Phase 1.6 — wire code_execution into a legacy lesson_json.

For a flag-enabled coding-implementation traversal topic: pull the (already
layout-fixed) code out of the lesson, run it through the SANDBOXED tracer, compile
a code_execution_panel model the frontend renders, and replace the worked-example
cards with milestone step cards (one per value appended) that reference the real
recorded frames. Guarded by the default-off flag; failures never break the lesson.
"""
from __future__ import annotations

import ast
import logging
import os
import re
from typing import Any, Optional

_log = logging.getLogger(__name__)

from .compilers.code_execution import compile_from_trace
from .delta_fold import DeltaFoldEngine
from .example_invariants import validate_example
from .flags import is_v2_enabled
from .profiles import delta_vocabulary, profile_for_mode
from .simulators.code_tracer import simulate_code_execution

# Canonical inputs for the trace. Tree for traversals; a 15-element sorted array +
# a target that takes >= 4 probes (searching the first element) for array algorithms.
_CANONICAL_TREE = [50, 30, 70, 20, 40, 60, 80]
_CANONICAL_ARRAY = list(range(1, 16))
_CANONICAL_TARGET = 1
# A 5-node connected graph (adjacency map) for graph-traversal coding worked examples.
_CANONICAL_GRAPH = {"A": ["B", "C"], "B": ["A", "D"], "C": ["A", "E"], "D": ["B", "E"], "E": ["C", "D"]}


def _dfs_canonical_code() -> str:
    return (
        "def dfs(graph, start):\n    visited = []\n    stack = [start]\n"
        "    while stack:\n        node = stack.pop()\n        if node in visited:\n            continue\n"
        "        visited.append(node)\n        for nb in graph[node]:\n"
        "            if nb not in visited:\n                stack.append(nb)\n    return visited"
    )


def _bfs_canonical_code() -> str:
    return (
        "def bfs(graph, start):\n    visited = []\n    queue = [start]\n"
        "    while queue:\n        node = queue.pop(0)\n        if node in visited:\n            continue\n"
        "        visited.append(node)\n        for nb in graph[node]:\n"
        "            if nb not in visited:\n                queue.append(nb)\n    return visited"
    )


# Canonical, correct, runnable implementations for well-known algorithms. Used when
# the lesson's own code is malformed (no def / missing line / broken indentation), so
# the worked example still shows a complete, valid program executing.
_BINARY_SEARCH_CODE = (
    "def binary_search(arr, target):\n    low = 0\n    high = len(arr) - 1\n"
    "    while low <= high:\n        mid = (low + high) // 2\n"
    "        if arr[mid] == target:\n            return mid\n"
    "        elif arr[mid] < target:\n            low = mid + 1\n"
    "        else:\n            high = mid - 1\n    return -1"
)


def _traversal_code(order: str) -> str:
    visit = "result.append(node.val)"
    left = "traverse(node.left, result)"
    right = "traverse(node.right, result)"
    body = {"inorder": [left, visit, right], "preorder": [visit, left, right], "postorder": [left, right, visit]}[order]
    helper_body = "\n".join("    " + line for line in body)
    return (
        f"def {order}Traversal(root):\n    result = []\n    traverse(root, result)\n    return result\n\n\n"
        f"def traverse(node, result):\n    if node is None:\n        return\n{helper_body}"
    )


def _canonical_for_topic(topic: dict[str, Any]) -> Optional[tuple[str, str, dict[str, Any]]]:
    """A correct (code, entry, input) for a recognised algorithm topic, or None."""
    title = str(topic.get("title", "")).lower()
    if "binary search" in title:
        return _BINARY_SEARCH_CODE, "binary_search", {"array": _CANONICAL_ARRAY, "target": _CANONICAL_TARGET}
    for order in ("postorder", "preorder", "inorder"):
        if order in title.replace("-", "").replace(" ", ""):
            return _traversal_code(order), f"{order}Traversal", {"tree": _CANONICAL_TREE}
    flat = title.replace("-", " ")
    if "depth first" in flat or "dfs" in flat:
        return _dfs_canonical_code(), "dfs", {"args": [dict(_CANONICAL_GRAPH), "A"]}
    if "breadth first" in flat or "bfs" in flat:
        return _bfs_canonical_code(), "bfs", {"args": [dict(_CANONICAL_GRAPH), "A"]}
    return None


def _is_coding_topic(topic: dict[str, Any]) -> bool:
    """Any coding-implementation topic. Input construction + the tracer gate whether
    it actually applies (unconstructible input or a trace failure → fall back)."""
    topic_type = str(topic.get("topic_type") or topic.get("course_type") or "").lower()
    return "coding" in topic_type


def _detect_input_spec(code: str, entry: str) -> Optional[dict[str, Any]]:
    """Build the entry-function input from how the code uses its argument: a tree if
    it touches `.left`/`.right`, otherwise an array (+ a target for a 2-arg search)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    uses_tree = any(isinstance(n, ast.Attribute) and n.attr in ("left", "right") for n in ast.walk(tree))
    entry_fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == entry), None)
    params = [a.arg for a in entry_fn.args.args] if entry_fn else []
    n_params = len(params)
    if uses_tree:
        return {"tree": _CANONICAL_TREE}
    # Graph traversal: a parameter named like an adjacency map (graph/adj/g) + a start
    # node. Pass the canonical adjacency + a real start key — NOT an array (the old
    # default crashed `graph[node]` with an int).
    graph_param = any(p.lower() in ("graph", "adj", "adjacency", "g", "adjlist", "adjacency_list") for p in params)
    start_param = any(p.lower() in ("start", "source", "src", "root", "s", "node") for p in params[1:])
    if graph_param and (start_param or n_params >= 2):
        return {"args": [dict(_CANONICAL_GRAPH), "A"]}
    if n_params >= 2:
        return {"array": _CANONICAL_ARRAY, "target": _CANONICAL_TARGET}
    return {"array": _CANONICAL_ARRAY}


def _line_description(line_text: str, real_line: int, frames: list[dict[str, Any]]) -> str:
    """A trace-derived note for one code line: the variable(s) it changed when it ran,
    else the line itself. Deterministic — no LLM."""
    for i, frame in enumerate(frames):
        state = frame.get("state_after") or {}
        if real_line in (state.get("highlight_lines") or []):
            after = state.get("variables") or {}
            before = ((frames[i - 1].get("state_after") or {}).get("variables") or {}) if i > 0 else {}
            if isinstance(after, dict):
                changed = {k: v for k, v in after.items() if before.get(k) != v}
                if changed:
                    parts = ", ".join(f"{k} = {v}" for k, v in list(changed.items())[:3])
                    return f"Line {real_line} runs — {parts}."
            return f"Line {real_line} runs: `{line_text.strip()}`."
    return f"`{line_text.strip()}`"


def _build_walkthrough_from_trace(code: str, frames: list[dict[str, Any]], model_id: str) -> list[dict[str, Any]]:
    """One code_walkthrough card per non-blank line of the REAL code, with cumulative
    code, the line highlighted, and a trace-derived description — so the walkthrough
    covers EVERY line (not just the first few the LLM wrote)."""
    original = code.splitlines()
    nonblank = [(pos, ln) for pos, ln in enumerate(original) if ln.strip()]
    total = len(nonblank)
    cards: list[dict[str, Any]] = []
    for n, (pos, text) in enumerate(nonblank, start=1):
        real_line = pos + 1
        desc = _line_description(text, real_line, frames)
        cards.append({
            "id": f"v2-cw-{model_id}-{n}",
            "blueprint_key": "code_walkthrough",
            "card_type": "code_walkthrough",
            "title": f"Code Walkthrough: line {real_line}",
            "points": [desc],
            "body": [],
            "main_concept": desc,
            "code_snippet": "\n".join(original[: pos + 1]),
            "code_language": "python",
            "visual_type": "code_trace",
            "highlight_lines_per_step": [[real_line, real_line]],
            "continuation_group_id": f"v2-cw-{model_id}",
            "continuation_index": n,
            "continuation_total": total,
            "continuation_reason": "one_code_line_per_card",
            "continues_from_previous": n > 1,
            "estimated_seconds": 20,
        })
    return cards


def _swap_walkthrough_cards(lesson_json: dict[str, Any], new_cards: list[dict[str, Any]]) -> None:
    """Replace the lesson's code_walkthrough run with the trace-built one. Only swaps
    when the topic already HAS a walkthrough slot (respects the blueprint)."""
    cards = list(lesson_json.get("lesson_cards") or [])
    has_walkthrough = any(
        str(c.get("blueprint_key") or c.get("card_type") or "").lower() == "code_walkthrough"
        for c in cards if isinstance(c, dict)
    )
    if not has_walkthrough or not new_cards:
        return
    rebuilt: list[dict[str, Any]] = []
    inserted = False
    for card in cards:
        if str(card.get("blueprint_key") or card.get("card_type") or "").lower() == "code_walkthrough":
            if not inserted:
                rebuilt.extend(new_cards)
                inserted = True
            continue
        rebuilt.append(card)
    lesson_json["lesson_cards"] = rebuilt


def _entry_params(code: str, entry: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == entry), None)
    return [a.arg for a in fn.args.args] if fn else []


def _lesson_text_blob(lesson_json: dict[str, Any]) -> str:
    parts: list[str] = []
    for card in lesson_json.get("lesson_cards") or []:
        if not isinstance(card, dict):
            continue
        for key in ("points", "body", "bullets"):
            val = card.get(key)
            if isinstance(val, list):
                parts += [str(x) for x in val]
        for key in ("content", "main_concept", "learning_goal", "visual_description",
                    "what_to_notice", "attention_note", "example", "title"):
            if card.get(key):
                parts.append(str(card.get(key)))
        # The bridge's worked-example narration often lives under visual_focus.
        focus = card.get("visual_focus")
        if isinstance(focus, dict) and focus.get("attention_note"):
            parts.append(str(focus["attention_note"]))
    return "\n".join(parts)


def _first_adjacency(blob: str) -> Optional[dict[Any, list[Any]]]:
    for match in re.finditer(r"\{[^{}]+\}", blob):
        try:
            val = ast.literal_eval(match.group(0))
        except (ValueError, SyntaxError):
            continue
        if isinstance(val, dict) and val and all(isinstance(v, list) for v in val.values()):
            return val
    return None


def _first_number_array(blob: str) -> Optional[list[Any]]:
    for match in re.finditer(r"\[[^\[\]]+\]", blob):
        try:
            val = ast.literal_eval(match.group(0))
        except (ValueError, SyntaxError):
            continue
        if isinstance(val, list) and len(val) >= 3 and all(
            isinstance(x, (int, float)) and not isinstance(x, bool) for x in val
        ):
            return val
    return None


def _extract_example_input(lesson_json: dict[str, Any], code: str, entry: str) -> Optional[dict[str, Any]]:
    """Build the trace input from the LESSON'S OWN content — the graph/array the LLM is
    actually teaching on — so the computed visual matches the prose. No hardcoded values;
    returns None (→ drop) when the lesson states no usable input."""
    params = [p.lower() for p in _entry_params(code, entry)]
    blob = _lesson_text_blob(lesson_json)

    if any(p in ("graph", "adj", "adjacency", "g", "adjlist", "adjacency_list") for p in params):
        graph = _first_adjacency(blob)
        if graph is None:
            return None
        start = next(iter(graph))  # default: first node
        hit = re.search(r"(?:from|at|start\w*)\s+(?:node\s+)?([A-Za-z0-9]+)", blob, re.IGNORECASE)
        if hit:
            for node in graph:
                if str(node) == hit.group(1):
                    start = node
                    break
        return {"args": [graph, start]}

    array = _first_number_array(blob)
    if array is None:
        array = _array_from_visual_models(lesson_json)  # structured fallback
    if array is not None:
        spec: dict[str, Any] = {"array": array}
        if len(params) >= 2:
            hit = re.search(r"(?:find|target|search(?:\s+for)?|locate)\s+(-?\d+)", blob, re.IGNORECASE)
            spec["target"] = int(hit.group(1)) if hit else array[0]
        return spec
    return None


def _array_from_visual_models(lesson_json: dict[str, Any]) -> Optional[list[Any]]:
    """Last-resort input: an array the lesson already carries in a visual model's base
    values (the bridge extracted it). Prefer prose, but this beats dropping."""
    for model in lesson_json.get("visual_models") or []:
        if not isinstance(model, dict) or str(model.get("base_type")) != "indexed_sequence_diagram":
            continue
        values = (model.get("base") or {}).get("values")
        if isinstance(values, list) and len(values) >= 3:
            nums: list[Any] = []
            for v in values:
                try:
                    nums.append(int(v))
                except (TypeError, ValueError):
                    return None
            return nums
    return None


def _loop_line_numbers(code: str) -> frozenset[int]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return frozenset()
    return frozenset(n.lineno for n in ast.walk(tree) if isinstance(n, (ast.While, ast.For)))


def _extract_code_and_entry(lesson_json: dict[str, Any]) -> Optional[tuple[str, str]]:
    """COMBINE every parseable code_snippet in the lesson into one module, then pick the
    entry as the root of the call graph.

    The longest *single* snippet isn't enough: an algorithm like merge sort defines the
    `merge_sort` recursion in one card and its `merge` helper in another, so tracing the
    entry alone fails (`merge` undefined) and the example silently drops to the LLM's
    cut-short cards. Combining all definitions (deduped by name, keeping the longest body)
    makes helpers available; the entry is the function no OTHER function calls (self-
    recursion ignored), so we trace `merge_sort`, not the `merge` helper."""
    snippets: list[str] = []
    for card in lesson_json.get("lesson_cards") or []:
        if str(card.get("blueprint_key") or card.get("card_type") or "").lower() in ("worked_example", "code_walkthrough"):
            snippet = str(card.get("code_snippet") or "").strip()
            if snippet:
                snippets.append(snippet)
    if not snippets:
        return None

    # Dedup function definitions by name across snippets (keep the longest body), so the
    # combined module defines each function exactly once, in first-seen order.
    defs: dict[str, tuple[int, str]] = {}  # name -> (size, source)
    order: list[str] = []
    for snippet in snippets:
        try:
            tree = ast.parse(snippet)
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            src = ast.get_source_segment(snippet, node)
            if not src:
                continue
            if node.name not in defs:
                order.append(node.name)
            if node.name not in defs or len(src) > defs[node.name][0]:
                defs[node.name] = (len(src), src)
    if not defs:
        return None

    combined = "\n\n\n".join(defs[name][1] for name in order)
    try:
        tree = ast.parse(combined)
    except SyntaxError:
        # A combined module that won't parse — fall back to the single longest snippet.
        best = max(snippets, key=len)
        try:
            single = ast.parse(best)
        except SyntaxError:
            return None
        funcs = [n for n in single.body if isinstance(n, ast.FunctionDef)]
        if not funcs:
            return None
        return best, min(funcs, key=lambda f: len(f.args.args)).name

    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if not funcs:
        return None
    # Entry = a function NOT called by any OTHER defined function (self-recursion ignored).
    called_by_others: set[str] = set()
    for name, fn in funcs.items():
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                callee = sub.func.id
                if callee in funcs and callee != name:
                    called_by_others.add(callee)
    roots = [name for name in order if name in funcs and name not in called_by_others]
    pool = roots or list(funcs)
    entry = min(pool, key=lambda nm: len(funcs[nm].args.args))
    return combined, entry


def _hl(frame: dict[str, Any]) -> Optional[int]:
    lines = frame["state_after"].get("highlight_lines") or []
    return lines[0] if lines else None


def _milestone_frame_indices(frames: list[dict[str, Any]], loop_lines: frozenset[int] = frozenset()) -> list[int]:
    """Pick the cards. Accumulator algorithms → one per appended value. Loop
    algorithms (binary search, two-pointer) → the SETUP lines (each as its own
    card, one at a time) + one card per loop iteration. Else → every line."""
    last = len(frames) - 1
    if last < 0:
        return []

    # 1. Accumulator: one card per value appended to the output.
    out_indices, prev = [], None
    for i, frame in enumerate(frames):
        output = frame["state_after"].get("output")
        if output and output != prev:
            out_indices.append(i)
        prev = output
    if len(out_indices) >= 2:
        return sorted(set(out_indices + [last]))

    # 2. Loop: setup frames (before the first loop iteration) + one per iteration.
    if loop_lines:
        first_loop = next((i for i, f in enumerate(frames) if _hl(f) in loop_lines), None)
        if first_loop is not None:
            setup = list(range(first_loop))  # init lines (low = 0, high = ...), one each
            iterations = [i for i, f in enumerate(frames) if _hl(f) in loop_lines]
            milestones = sorted(set(setup + iterations + [last]))
            if len(milestones) >= 2:
                return milestones

    # 3. Fallback: every recorded line.
    return list(range(len(frames)))


def cap_milestones(milestones: list[int], *, cap: int = 12) -> list[int]:
    """Keep a worked example to a readable number of cards. When milestone selection
    over-granulates (recursive / divide-and-conquer code can emit one card per element —
    merge sort produced 60), keep the FIRST and LAST plus evenly-spaced milestones
    between. No per-algorithm logic; applies to every code worked example."""
    if len(milestones) <= cap:
        return milestones
    first, last = milestones[0], milestones[-1]
    middle = milestones[1:-1]
    keep = max(1, cap - 2)
    step = len(middle) / keep
    sampled = [middle[min(int(i * step), len(middle) - 1)] for i in range(keep)]
    return sorted({first, *sampled, last})


def _fmt_output(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(str(v) for v in value) + "]"
    return str(value)


def _build_code_step_cards(model: dict[str, Any], frames, milestones, entry: str) -> list[dict[str, Any]]:
    cards = []
    for n, fi in enumerate(milestones):
        state = model["frames"][fi]["state"]
        line = (state.get("highlight_lines") or [0])[0]
        output = frames[fi]["state_after"].get("output")
        cards.append({
            "id": f"v2-code-{model['id']}-{n + 1}",
            "blueprint_key": "worked_example",
            "card_type": "worked_example",
            "title": f"{entry}: Step {n + 1}",
            "points": [f"Line {line} executes.", f"Result so far: {_fmt_output(output)}."],
            "body": [],
            "main_concept": f"Step {n + 1} of the recorded execution.",
            "visual_type": "code_trace",
            "visual_v2_ref": {"visual_model_id": model["id"], "frame_index": fi, "source": "v2_code_execution"},
            "estimated_seconds": 30,
        })
    return cards


def _attach_code_diagram(
    lesson_json: dict[str, Any],
    step_cards: list[dict[str, Any]],
    frames: list[dict[str, Any]],
    trace_steps: list[dict[str, Any]],
    code_model_id: str,
    code: Optional[str] = None,
) -> None:
    """Build a diagram from the code's own trace and attach it as the diagram slot of
    each step card, synced by progress + event_id. Failure-safe: no diagram simply means
    clean code-only (validate-or-degrade)."""
    try:
        from app.services.examples.code_diagram import attach_diagram_to_cards, build_diagram_from_trace

        diagram = build_diagram_from_trace(trace_steps, model_id=f"{code_model_id}_diagram", code=code)
        attach_diagram_to_cards(lesson_json, step_cards, frames, diagram, source="v2_code_diagram")
    except Exception as exc:  # noqa: BLE001 — additive; never break the lesson
        _log.warning("visual_v2 code_execution: diagram attach failed (%s); code-only", exc)


def apply_code_execution_to_lesson(lesson_json: dict[str, Any], topic: dict[str, Any], *, sandboxed: bool = True) -> bool:
    """If enabled, replace the worked example with a real traced execution. Returns
    True if applied (lesson_json mutated)."""
    if not isinstance(lesson_json, dict):
        return False
    if not is_v2_enabled("code_execution", "code_execution"):
        return False
    if not _is_coding_topic(topic):
        return False

    # Use the lesson's OWN code traced on the lesson's OWN input (the graph/array the
    # LLM is teaching on), so the worked example + diagram match the prose. Contents
    # come from the LLM, not hardcoded fixtures. If the lesson states no usable input,
    # we DROP (the canonical fallback is gated OFF by default, so real performance is
    # visible). The structure of the visual is fixed; the contents are the LLM's.
    from app.services.visual_v2.invariant_metrics import GLOBAL as _INV

    attempts: list[tuple[str, str, dict[str, Any]]] = []
    extracted = _extract_code_and_entry(lesson_json)
    if extracted:
        cand_code, cand_entry = extracted
        try:
            ast.parse(cand_code)
            real_input = _extract_example_input(lesson_json, cand_code, cand_entry)
            if real_input is None:
                # Trees are STRUCTURAL (built from TreeNode), not stated parseably in
                # prose — so a tree's shape isn't an LLM "value we place in". Keep the
                # structural tree input; graph/array contents must come from the lesson.
                spec = _detect_input_spec(cand_code, cand_entry)
                if spec is not None and "tree" in spec:
                    real_input = spec
            if real_input is not None:
                attempts.append((cand_code, cand_entry, real_input))
        except SyntaxError:
            pass
    if not attempts and os.getenv("AZALEA_CODE_CANONICAL_FALLBACK", "").strip().lower() in {"1", "true", "on"}:
        canonical = _canonical_for_topic(topic)
        if canonical is not None:
            attempts.append(canonical)
    if not attempts:
        reason = "no_code" if not extracted else "no_input"
        _log.info("visual_v2 code_execution: dropping for %s (%s, no canonical)", topic.get("id"), reason)
        _INV.record_code_drop(reason)
        return False

    code = entry = trace = None
    frames: list[dict[str, Any]] = []
    for cand_code, cand_entry, cand_spec in attempts:
        example = {
            "example_id": f"code_{topic.get('id', 'topic')}",
            "base_type": "code_execution_panel",
            "mode": "code_execution",
            "algorithm": "code_execution",
            "code": cand_code,
            "entry_function": cand_entry,
            "input": cand_spec,
        }
        if validate_example(example):
            continue
        try:
            cand_trace = simulate_code_execution(example, sandboxed=sandboxed)
        except Exception as exc:  # noqa: BLE001 — a bad candidate is skipped, not fatal
            _log.info("visual_v2 code_execution: candidate failed for %s (entry=%s): %s", topic.get("id"), cand_entry, exc)
            continue
        cand_frames = DeltaFoldEngine().fold(
            cand_trace["initial_state"], cand_trace["steps"], set(), delta_vocabulary("code_execution")
        )
        if cand_frames:
            code, entry, trace, frames = cand_code, cand_entry, cand_trace, cand_frames
            break
    if trace is None or not frames:
        _log.info("visual_v2 code_execution: no candidate traced for topic %s", topic.get("id"))
        _INV.record_code_drop("trace_failed")
        return False

    model_id = f"v2_code_{topic.get('id', 'topic')}"
    model, _render = compile_from_trace(
        trace=trace, frames=frames, code=code, profile=profile_for_mode("code_execution"), model_id=model_id,
    )
    # Completion: the trace runs the algorithm to the end, and milestone selection
    # always includes the terminal frame — so the worked example reaches the final
    # answer. Stamp that explicitly so it's auditable (and never silently cut short).
    milestones = cap_milestones(_milestone_frame_indices(frames, _loop_line_numbers(code)))
    if milestones and milestones[-1] != len(frames) - 1:
        milestones = sorted(set(milestones) | {len(frames) - 1})
    step_cards = _build_code_step_cards(model, frames, milestones, entry)
    if not step_cards:
        return False
    last = step_cards[-1]
    # The algorithm's actual return value is ground truth; fall back to the terminal
    # frame's accumulator only if the function returns nothing.
    final_output = trace.get("return_value")
    if final_output is None:
        final_output = (frames[-1].get("state_after") or {}).get("output")
    last.setdefault("metadata", {})["reaches_final_answer"] = True
    if final_output is not None:
        last["points"] = list(last.get("points") or []) + [f"Final result: {_fmt_output(final_output)}."]

    models = lesson_json.setdefault("visual_models", [])
    models[:] = [m for m in models if m.get("id") != model_id]
    models.append(model)

    # DIAGRAM slot (INV-DUAL-SLOT): build a diagram from the SAME trace and attach it
    # alongside the code, synced per step. Validate-or-degrade: if the trace isn't
    # diagrammable it returns None and we ship clean code-only.
    _attach_code_diagram(lesson_json, step_cards, frames, trace["steps"], model_id, code=code)

    cards = list(lesson_json.get("lesson_cards") or [])
    rebuilt: list[dict[str, Any]] = []
    inserted = False
    for card in cards:
        if str(card.get("blueprint_key") or card.get("card_type") or "").lower() == "worked_example":
            if not inserted:
                rebuilt.extend(step_cards)
                inserted = True
            continue
        rebuilt.append(card)
    if not inserted:
        idx = next((j for j, c in enumerate(rebuilt) if str(c.get("blueprint_key") or "").lower() == "practice"), len(rebuilt))
        rebuilt[idx:idx] = step_cards
    lesson_json["lesson_cards"] = rebuilt

    # Rebuild the code walkthrough from the REAL traced code — every line, in order,
    # highlighted — replacing the LLM's (often truncated) walkthrough.
    _swap_walkthrough_cards(lesson_json, _build_walkthrough_from_trace(code, frames, model_id))

    lesson_json.setdefault("metadata", {})["visual_v2_code_execution"] = {
        "model_id": model_id, "steps": len(step_cards), "total_frames": len(frames),
    }
    return True
