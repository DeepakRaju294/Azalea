"""A2 (STUDY_PATH_CONTENT_SPEC §A2) — executable validation of a displayed coding implementation.

A coding worked example shows the LLM's own implementation. Shape-only checks miss code that returns
edges but builds a cycle, omits a vertex, or picks a non-minimal tree — and the live Prim that returned
VERTICES instead of edges. This module RUNS the displayed code on the adapter's teaching instance (in a
subprocess with a timeout) and asserts the result is a valid minimum spanning tree of that graph.

Boundary (spec §A2): full execution applies only to code that is RUNNABLE end-to-end. A partial snippet
(no entry function / undefined free names) is reported `unverifiable` rather than `fail` — the caller
then relies on a snippet contract + generated harness (future work), never on running the fragment alone.

Scope today: the graph MST family (Kruskal / Prim). The pure property checker (`mst_properties`) is
algorithm-agnostic and fully offline-testable; the runner/harness handle the common entry shapes and
return `unverifiable` for anything they can't set up — so this never produces a false `fail`.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

_TIMEOUT_S = 5
# stdlib modules an end-to-end implementation may import without making it a "snippet".
_STDLIB_OK = {"heapq", "collections", "math", "typing", "functools", "itertools", "bisect", "sys", "queue"}


@dataclass
class CodeCheck:
    status: str            # "ok" | "fail" | "unverifiable"
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"


# --- pure MST property checker (algorithm-agnostic, fully offline-testable) ------------------------

def _as_edge(e: Any) -> tuple:
    """Coerce a returned item to (u, v, w) or (None, None, None) when it is not an edge triple."""
    if isinstance(e, (list, tuple)) and len(e) == 3:
        u, v, w = e
        if isinstance(w, (int, float)) and not isinstance(w, bool):
            return (u, v, w)
    return (None, None, None)


def _canon(u: Any, v: Any) -> tuple:
    a, b = sorted((str(u), str(v)))
    return (a, b)


def _split_edges_total(returned: Any) -> tuple:
    """`returned` is either an edge list, or (edges, total). Return (edges_or_None, total_or_None)."""
    if isinstance(returned, (list, tuple)) and len(returned) == 2 \
            and isinstance(returned[0], (list, tuple)) and isinstance(returned[1], (int, float)) \
            and not isinstance(returned[1], bool):
        return list(returned[0]), returned[1]
    if isinstance(returned, (list, tuple)):
        return list(returned), None
    return None, None


def mst_properties(num_nodes: int, graph_edges: list, returned: Any,
                   expected_total: Optional[int]) -> CodeCheck:
    """Validate `returned` (the code's output) as an MST of the graph: items are edges, count == V-1,
    every edge is a real graph edge, the edges form a spanning tree (no cycle, connected), and the total
    weight equals the known minimum (when provided)."""
    edges, _total = _split_edges_total(returned)
    if edges is None:
        return CodeCheck("fail", "output is not an edge list or (edges, total)")
    valid = {}
    for ge in graph_edges:
        u, v, w = _as_edge(ge)
        if u is not None:
            valid[_canon(u, v)] = w
    norm: list[tuple] = []
    for e in edges:
        u, v, w = _as_edge(e)
        if u is None:
            return CodeCheck("fail", f"returned item is not an edge triple: {e!r}")
        norm.append((u, v, w))
    if len(norm) != num_nodes - 1:
        return CodeCheck("fail", f"returned {len(norm)} edges, expected V-1={num_nodes - 1}")
    for (u, v, w) in norm:
        key = _canon(u, v)
        if key not in valid or valid[key] != w:
            return CodeCheck("fail", f"edge {(u, v, w)} is not an edge of the graph")
    if not _is_spanning_tree(num_nodes, graph_edges, norm):
        return CodeCheck("fail", "returned edges are not a spanning tree (cycle or disconnected)")
    total = sum(w for (_, _, w) in norm)
    if expected_total is not None and total != expected_total:
        return CodeCheck("fail", f"total weight {total} != minimum {expected_total}")
    return CodeCheck("ok")


def _is_spanning_tree(num_nodes: int, graph_edges: list, tree: list[tuple]) -> bool:
    """Union-find over `tree`: reject a cycle; require every graph node connected into one component."""
    nodes = set()
    for ge in graph_edges:
        u, v, _ = _as_edge(ge)
        if u is not None:
            nodes.add(str(u)); nodes.add(str(v))
    if len(nodes) != num_nodes:                         # graph itself malformed vs declared V
        nodes |= {str(u) for (u, _, _) in tree} | {str(v) for (_, v, _) in tree}
    parent = {n: n for n in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    for (u, v, _) in tree:
        a, b = find(str(u)), find(str(v))
        if a == b:
            return False                                # cycle
        parent[a] = b
    roots = {find(n) for n in nodes}
    return len(roots) == 1                              # connected


# --- runnable vs snippet -------------------------------------------------------------------------

def find_entry_function(code: str, slug: str = "") -> Optional[str]:
    """Best-effort entry point: a top-level function whose name matches the algorithm, else the last
    top-level function that has no decorator and is not a dunder. None if unparseable / no function."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return None
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if not funcs:
        return None
    key = (slug or "").replace("_", "").lower()
    for f in funcs:
        if key and key in f.name.replace("_", "").lower():
            return f.name
    return funcs[-1].name


def is_runnable(code: str) -> bool:
    """A heuristic for "runnable end-to-end": parses, has an entry function, and references no undefined
    free names beyond stdlib/builtins (so it is not a fragment depending on outside scaffolding)."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return False
    if not any(isinstance(n, ast.FunctionDef) for n in tree.body):
        return False
    defined = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    defined |= {a.asname or a.name.split(".")[0]
                for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in n.names}
    imported_modules = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported_modules |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    if imported_modules - _STDLIB_OK:
        return False                                    # third-party dep -> treat as non-runnable here
    return True


# --- subprocess execution ------------------------------------------------------------------------

def run_implementation(code: str, entry: str, args: list) -> tuple:
    """Run `entry(*args)` in a SUBPROCESS with a timeout; return (result, error_str). Process isolation +
    timeout guard against side effects / infinite loops in generated code."""
    harness = (code + "\n\n"
               "import json as _json, sys as _sys\n"
               f"try:\n    _r = {entry}(*_json.loads(_sys.argv[1]))\n"
               "    print('__RESULT__' + _json.dumps(_r, default=list))\n"
               "except Exception as _e:\n    print('__ERROR__' + repr(_e))\n")
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
            fh.write(harness)
            path = fh.name
        proc = subprocess.run([sys.executable, path, json.dumps(args)],
                              capture_output=True, text=True, timeout=_TIMEOUT_S)
        out = proc.stdout or ""
        if "__RESULT__" in out:
            return json.loads(out.split("__RESULT__", 1)[1].splitlines()[0]), ""
        if "__ERROR__" in out:
            return None, out.split("__ERROR__", 1)[1].splitlines()[0]
        return None, (proc.stderr or "no output").strip().splitlines()[-1:][0] if (proc.stderr or "").strip() else "no result"
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except Exception as exc:  # noqa: BLE001
        return None, repr(exc)
    finally:
        try:
            import os
            os.unlink(path)
        except Exception:  # noqa: BLE001
            pass


def _arg_candidates(num_nodes: int, edges: list, adjacency: dict) -> list:
    """Plausible (args, graph_edges_in_that_representation) for a graph MST entry, tried in order — the
    returned MST is validated against the graph in the SAME representation the code was called with (so a
    code that uses int node indices is checked against int edges, not the label graph)."""
    int_edges = [[_i(u), _i(v), w] for (u, v, w) in edges]
    label_edges = [list(e) for e in edges]
    labels = sorted(adjacency.keys())
    int_adj = {_i(k): [[_i(a), b] for (a, b) in v] for k, v in adjacency.items()}
    nested_adj = {k: {a: b for (a, b) in v} for k, v in adjacency.items()}      # {u: {v: w}}
    s_lbl = labels[0] if labels else "A"               # a start vertex (Prim/BFS/DFS take graph + start)
    s_int = _i(s_lbl)
    return [
        ([num_nodes, int_edges], int_edges),             # kruskal(n, edges) with int nodes
        ([num_nodes, label_edges], label_edges),         # kruskal(n, edges) with label nodes
        ([adjacency], label_edges),                      # prim(graph) label-keyed adjacency [u: [(v,w)]]
        ([int_adj], int_edges),                          # prim(graph) int-keyed adjacency
        ([int_edges], int_edges),                        # kruskal(edges) — edges only, int nodes
        ([label_edges], label_edges),                    # kruskal(edges) — edges only, labels
        ([nested_adj], label_edges),                     # prim(graph) nested-dict adjacency {u: {v: w}}
        ([{"nodes": labels, "edges": label_edges}], label_edges),       # graph dict with nodes/edges keys
        ([{"num_nodes": num_nodes, "edges": int_edges}], int_edges),    # graph dict, int edges
        ([adjacency, s_lbl], label_edges),               # prim(graph, start) label adjacency + start vertex
        ([nested_adj, s_lbl], label_edges),              # prim(graph, start) nested-dict + start
        ([int_adj, s_int], int_edges),                   # prim(graph, start) int adjacency + start
        ([num_nodes, label_edges, s_lbl], label_edges),  # prim(n, edges, start)
    ]


def _i(label: Any) -> Any:
    """Map a single-letter node label to a 0-based index ('A'->0); pass ints through."""
    s = str(label)
    return ord(s) - 65 if len(s) == 1 and "A" <= s <= "Z" else label


def _reference_mst_total(num_nodes: int, edges: list) -> Optional[int]:
    """The true minimum-spanning-tree total weight via Kruskal over the labelled graph — the ground truth
    A2 checks the displayed code against. None if the graph is not connected."""
    nodes: set = set()
    triples = [_as_edge(e) for e in edges]
    for u, v, _ in triples:
        if u is not None:
            nodes.add(str(u)); nodes.add(str(v))
    parent = {n: n for n in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    total, count = 0, 0
    for u, v, w in sorted((t for t in triples if t[0] is not None), key=lambda t: t[2]):
        a, b = find(str(u)), find(str(v))
        if a != b:
            parent[a] = b; total += w; count += 1
    return total if count == num_nodes - 1 else None


def _test_graph(seed: int) -> tuple:
    """A small connected weighted graph (spanning tree + a few cross edges), as (n, edges, adjacency)."""
    import random
    rng = random.Random(seed)
    n = rng.randint(5, 6)
    labels = [chr(65 + i) for i in range(n)]
    edges: list = []
    seen: set = set()                                       # avoid PARALLEL edges (same pair, two weights)
    w = list(range(1, 21)); rng.shuffle(w)                  # distinct weights -> unambiguous MST
    wi = iter(w)
    for j in range(1, n):                                   # spanning tree -> connected
        p = labels[rng.randrange(j)]
        seen.add(frozenset((labels[j], p)))
        edges.append([labels[j], p, next(wi)])
    target, tries = rng.randint(2, 4), 0
    while len(edges) - (n - 1) < target and tries < 30:     # cross edges -> real choices
        tries += 1
        a, b = rng.sample(labels, 2)
        if frozenset((a, b)) in seen:
            continue
        seen.add(frozenset((a, b)))
        edges.append([a, b, next(wi)])
    adjacency: dict = {x: [] for x in labels}
    for u, v, w in edges:
        adjacency[u].append([v, w]); adjacency[v].append([u, w])
    return n, edges, adjacency


def check_graph_topic_code(code: str, slug: str, *, trials: int = 2) -> CodeCheck:
    """A2 entry for a graph-MST coding topic: run the displayed code on freshly generated test graphs and
    assert it produces a valid MST (caught the live Prim-returns-vertices bug). Returns the FIRST `fail`
    or `unverifiable`; `ok` only if every trial passes. `unverifiable` for non-graph topics / unrunnable
    code — never a false `fail`."""
    if slug not in ("kruskal", "prim"):
        return CodeCheck("unverifiable", f"no executable check for adapter {slug!r}")
    for s in range(1, trials + 1):
        n, edges, adjacency = _test_graph(s)
        expected = _reference_mst_total(n, edges)
        if expected is None:
            continue
        result = validate_graph_implementation(code, num_nodes=n, edges=edges, adjacency=adjacency,
                                               expected_total=expected, slug=slug)
        if result.status in ("fail", "unverifiable"):
            return result
    return CodeCheck("ok")


def validate_graph_implementation(code: str, *, num_nodes: int, edges: list, adjacency: dict,
                                  expected_total: Optional[int], slug: str = "") -> CodeCheck:
    """Run the displayed graph-MST code on the instance and check the result is a valid MST. Returns
    `unverifiable` (never `fail`) when the code is a snippet or no argument shape produces output."""
    if not is_runnable(code):
        return CodeCheck("unverifiable", "not runnable end-to-end (snippet / external dependency)")
    entry = find_entry_function(code, slug)
    if not entry:
        return CodeCheck("unverifiable", "no entry function found")
    last_err = ""
    for args, edges_repr in _arg_candidates(num_nodes, edges, adjacency):
        result, err = run_implementation(code, entry, args)
        if result is not None:
            return mst_properties(num_nodes, edges_repr, result, expected_total)
        last_err = err
    return CodeCheck("unverifiable", f"no argument shape ran successfully (last: {last_err})")


# --- executed-reference: array-shaped TRACE reproduction (sorts / search) --------------------------
# The MST checks above validate a graph result by PROPERTY. Array algorithms need a stronger check: the code
# shown must be the SAME VARIANT as the walkthrough trace (a top-down merge beside a bottom-up-queue trace
# still sorts, so a property/final-answer check passes while every per-line annotation contradicts the code).
# So we run the code once on the trace's own instance and require every trace step's STATE to occur among the
# code's real intermediate states. This needs the intermediate states, so it uses the in-process settrace
# recorder (`trace_execution`), not the subprocess runner above.

def _input_array(trace: Any) -> Optional[list]:
    """Derive the entry array from the trace's initial state (a bottom-up merge's single-element `runs` are
    flattened back to the array the code's function takes). None for non-array shapes (graph/tree)."""
    init = getattr(trace, "initial_state", None) or {}
    if isinstance(init.get("array"), list):
        return list(init["array"])
    if isinstance(init.get("runs"), list) and all(isinstance(r, list) for r in init["runs"]):
        return [x for run in init["runs"] for x in run]
    return None


def _list_keys(state: Optional[dict]) -> list:
    return [json.dumps(v, default=str) for v in (state or {}).values() if isinstance(v, list)]


def reproduces_trace_applies(trace: Any, code: Optional[str]) -> bool:
    """True when the executed-reference trace-reproduction gate can run (array-shaped topic + code present)."""
    return bool(code) and find_entry_function(code or "") is not None and _input_array(trace) is not None


def code_reproduces_trace(code: str, trace: Any) -> list:
    """[] when the canonical code, run on the trace's own instance, reproduces the trace — same final answer
    AND every trace step's state occurs among the code's real intermediate states (proving the code is the
    SAME variant as the walkthrough, not a lookalike whose per-line annotations would contradict it).
    Non-empty = variant drift or a broken solution; the code must not be shown beside this walkthrough. SKIPS
    non-array shapes (returns [] — never a false positive)."""
    entry = find_entry_function(code)
    arr = _input_array(trace)
    if not entry or arr is None:
        return []
    try:
        from app.services.visual_v2.simulators.code_tracer import trace_execution
        steps, result = trace_execution(code, entry, {"array": list(arr)})
    except Exception as exc:  # noqa: BLE001 — a canonical solution that will not run is itself a defect
        return [f"canonical code failed to execute on {arr}: {type(exc).__name__}: {exc}"]
    out: list = []
    expected = (getattr(trace, "final_answer", None) or {}).get("sorted")
    if expected is not None and result != expected:
        out.append(f"code result {result} != trace final answer {expected}")
    from collections import deque
    seen: set = set()                                        # every list a variable held at any executed line
    for s in steps:
        for v in (s.get("vars") or {}).values():
            if isinstance(v, deque):                         # a bottom-up merge's run queue -> list of runs
                v = list(v)
            if isinstance(v, list):
                seen.add(json.dumps(v, default=str))
    for st in getattr(trace, "steps", []):
        sigs = _list_keys(getattr(st, "state_after", None))
        if sigs and not any(sig in seen for sig in sigs):
            out.append(f"step {st.id}: trace state {sigs[0]} never occurs in the code's execution "
                       f"(the code is a different variant than the walkthrough)")
            break                                           # one drift proves the mismatch; don't spam
    return out


# --- executed-reference: per-line VALUE attribution (catches a wrong value on a correct-variant line) -------
# The trace-reproduction gate proves the code is the right VARIANT. This finer check proves each card's // comment
# does not attribute a WRONG concrete value to an indexed code expression — the merge `append(left[i]) // append
# value 9` bug where left[i] is really 30. It maps each card to its slice of the real execution (segmenting on
# the trace's own step states), reads the actual value the expression took there, and flags a single-value claim
# that never matches. Deliberately narrow: fires only on a line with exactly ONE index read and exactly ONE
# introduced value, so an unambiguous contradiction — never a comparison/aside — is all it can flag.
import re as _re

_INDEX_READ = _re.compile(r"\b([A-Za-z_]\w*)\s*\[\s*([A-Za-z_]\w*)\s*\]")


def _step_regions(exec_steps: list, trace: Any) -> Optional[list]:
    """Segment the execution into one (start, end) slice per trace step, by finding where each step's state
    first materializes in the run (in order). None if any step can't be located — the caller then SKIPS the
    per-line check rather than guess a mapping (no false positives)."""
    exec_lists = [{json.dumps(list(v) if isinstance(v, deque) else v, default=str)
                   for v in (st.get("vars") or {}).values() if isinstance(v, (list, deque))}
                  for st in exec_steps]
    regions: list = []
    cursor = 0
    for st in getattr(trace, "steps", []):
        sigs = set(_list_keys(getattr(st, "state_after", None)))
        found = next((i for i in range(cursor, len(exec_steps)) if exec_lists[i] & sigs), None)
        if found is None:
            return None
        regions.append((cursor, found))
        cursor = found + 1
    return regions


def executed_reference_violations(cards: list, code: str, trace: Any) -> list:
    """Per-line value check (see block comment). Returns (code, detail) tuples for hard violations — a card's
    // comment attributing a value an indexed expression never held at that step. [] when out of scope or the
    execution can't be mapped (never a false positive)."""
    entry = find_entry_function(code or "")
    arr = _input_array(trace)
    if not entry or arr is None:
        return []
    try:
        from app.services.visual_v2.simulators.code_tracer import trace_execution
        exec_steps, _ = trace_execution(code, entry, {"array": list(arr)})
    except Exception:  # noqa: BLE001 — execution defects are the reproduction gate's job, not this one
        return []
    regions = _step_regions(exec_steps, trace)
    if regions is None:
        return []
    out: list = []
    for k, card in enumerate(cards):
        if k >= len(regions):
            break
        start, end = regions[k]
        region = exec_steps[start:end + 1]
        for wline in (card.get("work") or []):
            if "//" not in str(wline):
                continue
            code_part, _, comment = str(wline).partition("//")
            reads = _INDEX_READ.findall(code_part)
            if len(reads) != 1:                              # ambiguous (swap / compare) -> skip
                continue
            name, idx = reads[0]
            vals: set = set()                                # every value NAME[IDX] took in this step's slice
            for es in region:
                v = es.get("vars") or {}
                seq, i = v.get(name), v.get(idx)
                if isinstance(seq, list) and isinstance(i, int) and 0 <= i < len(seq) and isinstance(seq[i], int):
                    vals.add(seq[i])
            if not vals:
                continue
            comment_nums = {int(x) for x in _re.findall(r"-?\d+", comment)}
            code_nums = {int(x) for x in _re.findall(r"-?\d+", code_part)}
            claim = comment_nums - code_nums                 # values the comment INTRODUCES (not indices/literals)
            if len(claim) == 1 and not (claim & vals):
                out.append(("code_comment_value_mismatch",
                            f"{name}[{idx}] is {sorted(vals)} here, not {claim.pop()}"))
    return out
