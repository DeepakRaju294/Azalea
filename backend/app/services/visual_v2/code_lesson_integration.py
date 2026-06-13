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


def _loop_line_numbers(code: str) -> frozenset[int]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return frozenset()
    return frozenset(n.lineno for n in ast.walk(tree) if isinstance(n, (ast.While, ast.For)))


def _extract_code_and_entry(lesson_json: dict[str, Any]) -> Optional[tuple[str, str]]:
    """The longest PARSEABLE code_snippet in the lesson + its entry function. Prefers
    valid code so a mis-indented walkthrough card can't block the tracer."""
    candidates: list[str] = []
    for card in lesson_json.get("lesson_cards") or []:
        if str(card.get("blueprint_key") or card.get("card_type") or "").lower() in ("worked_example", "code_walkthrough"):
            snippet = str(card.get("code_snippet") or "").strip()
            if snippet:
                candidates.append(snippet)
    parseable: list[str] = []
    for snippet in candidates:
        try:
            ast.parse(snippet)
            parseable.append(snippet)
        except SyntaxError:
            continue
    pool = parseable or candidates
    if not pool:
        return None
    best = max(pool, key=len)
    try:
        tree = ast.parse(best)
    except SyntaxError:
        return None
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if not funcs:
        return None
    # The entry takes the fewest args (the main takes `root`; the helper takes
    # `node, result`) — robust to function order.
    entry = min(funcs, key=lambda f: len(f.args.args))
    return best, entry.name


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
) -> None:
    """Build a node_link diagram from the code's own trace and attach it as the diagram
    slot of each step card, synced by visit progress + event_id. Failure-safe: no
    diagram simply means clean code-only (validate-or-degrade)."""
    try:
        from app.services.examples.code_diagram import attach_diagram_to_cards, build_diagram_from_trace

        diagram = build_diagram_from_trace(trace_steps, model_id=f"{code_model_id}_diagram")
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

    # Prefer the lesson's own (valid) code; if its detected input is wrong (the old
    # array-default crashed graph code) or the code is malformed, fall back to a
    # canonical implementation. We try each candidate through the tracer and keep the
    # FIRST that actually executes — so a bad input-guess degrades, never crashes.
    attempts: list[tuple[str, str, dict[str, Any]]] = []
    extracted = _extract_code_and_entry(lesson_json)
    if extracted:
        cand_code, cand_entry = extracted
        try:
            ast.parse(cand_code)
            spec = _detect_input_spec(cand_code, cand_entry)
            if spec is not None:
                attempts.append((cand_code, cand_entry, spec))
        except SyntaxError:
            pass
    canonical = _canonical_for_topic(topic)
    if canonical is not None:
        attempts.append(canonical)
    if not attempts:
        _log.info("visual_v2 code_execution: no usable/canonical code for topic %s", topic.get("id"))
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
        return False

    model_id = f"v2_code_{topic.get('id', 'topic')}"
    model, _render = compile_from_trace(
        trace=trace, frames=frames, code=code, profile=profile_for_mode("code_execution"), model_id=model_id,
    )
    milestones = cap_milestones(_milestone_frame_indices(frames, _loop_line_numbers(code)))
    step_cards = _build_code_step_cards(model, frames, milestones, entry)
    if not step_cards:
        return False

    models = lesson_json.setdefault("visual_models", [])
    models[:] = [m for m in models if m.get("id") != model_id]
    models.append(model)

    # DIAGRAM slot (INV-DUAL-SLOT): build a node_link diagram from the SAME trace and
    # attach it alongside the code, synced per step. Validate-or-degrade: if the trace
    # isn't graph-shaped it returns None and we ship clean code-only.
    _attach_code_diagram(lesson_json, step_cards, frames, trace["steps"], model_id)

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
    lesson_json.setdefault("metadata", {})["visual_v2_code_execution"] = {
        "model_id": model_id, "steps": len(step_cards), "total_frames": len(frames),
    }
    return True
