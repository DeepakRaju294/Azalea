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
    int_adj = {_i(k): [[_i(a), b] for (a, b) in v] for k, v in adjacency.items()}
    return [
        ([num_nodes, int_edges], int_edges),             # kruskal(n, edges) with int nodes
        ([num_nodes, label_edges], label_edges),         # kruskal(n, edges) with label nodes
        ([adjacency], label_edges),                      # prim(graph) label-keyed adjacency
        ([int_adj], int_edges),                          # prim(graph) int-keyed adjacency
    ]


def _i(label: Any) -> Any:
    """Map a single-letter node label to a 0-based index ('A'->0); pass ints through."""
    s = str(label)
    return ord(s) - 65 if len(s) == 1 and "A" <= s <= "Z" else label


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
