"""Trace interface + a bounded, AST-gated Python tracer (spec §6, §12 step 7).

`run_trace(code, language, input)` -> ordered semantic states (the authoritative
``trace_events``), or ``None`` when execution is skipped/unsafe — the caller then stays
``model_only`` with ``trace_confidence: low`` (§6/§6.3).

Safety posture (spec §6 "execution is gated and sandboxed"):
* **Off by default.** Execution only happens when ``AZALEA_GEN_FOUNDATION_EXECUTE`` is set
  AND the language is Python AND the source passes the AST gate.
* **AST allow-list** — no imports, no ``with``/``global``/``nonlocal``, no dunder access,
  no dangerous builtins (``eval``/``exec``/``open``/``getattr``/...); only a curated safe
  builtin set is exposed.
* **Bounded** — max traced steps, wall-clock, and per-snapshot state size.

This runs OUR generated, deterministic educational snippets in-process. For untrusted
input, production should additionally run it under OS-level isolation (subprocess +
resource limits / seccomp / container); the function signature is the same plug seam.
"""
from __future__ import annotations

import ast
import builtins as _builtins
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

TraceEvent = dict[str, Any]
TraceEvents = list[TraceEvent]
ExecutorFn = Callable[[str, str, Any], Optional[TraceEvents]]


@dataclass
class ExecutionResult:
    """Structured execution outcome (Layer 1)."""
    status: str                       # executed | skipped | error | overflow
    skip_reason: Optional[str]        # why skipped/errored, for shadow telemetry
    trace_events: Optional["TraceEvents"]
    return_value: Any                 # the entry function's return (the executed final answer)
    exception: Optional[str]
    elapsed_ms: float

MAX_STEPS = 4000
MAX_SECONDS = 1.0
MAX_STATE_ENTRIES = 32
MAX_COLLECTION = 64
_SENTINEL_FILE = "<gen_foundation_trace>"

# Only these AST node types may appear (allow-list is safer than a deny-list).
_ALLOWED_NODES: frozenset[type] = frozenset({
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return,
    ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Expr, ast.Pass,
    ast.If, ast.For, ast.While, ast.Break, ast.Continue, ast.IfExp,
    ast.Call, ast.Name, ast.Load, ast.Store, ast.Del, ast.Starred, ast.keyword,
    ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.Set,
    ast.Subscript, ast.Slice, ast.Index if hasattr(ast, "Index") else ast.Slice,
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Attribute,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.LShift, ast.RShift, ast.BitOr, ast.BitAnd, ast.BitXor,
    ast.USub, ast.UAdd, ast.Not, ast.Invert, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot, ast.In, ast.NotIn,
    ast.FormattedValue, ast.JoinedStr,
    ast.Import, ast.ImportFrom, ast.alias,   # only for the curated allow-list below (Layer 1)
})

# Curated standard-library modules the canonical implementations actually use (mirrors
# code_repair.ALLOWED_STDLIB_MODULES). These are the SAME modules generation is now allowed to emit, so
# the executor can run exactly the algorithms it most needs to verify (heapq/deque/...). Imports outside
# this set are rejected at the AST gate AND by the guarded __import__ below (defence in depth).
_ALLOWED_IMPORT_MODULES = frozenset({
    "heapq", "collections", "math", "itertools", "bisect", "functools",
})

_DANGEROUS_NAMES = frozenset({
    "eval", "exec", "open", "compile", "__import__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "input", "exit", "quit", "help", "memoryview",
    "breakpoint", "__builtins__",
})

_SAFE_BUILTIN_NAMES = (
    "abs", "min", "max", "sum", "len", "range", "enumerate", "sorted", "reversed",
    "list", "dict", "set", "tuple", "str", "int", "float", "bool", "zip", "map",
    "filter", "all", "any", "round", "divmod", "isinstance",
)
_SAFE_BUILTINS: dict[str, Any] = {
    name: getattr(_builtins, name) for name in _SAFE_BUILTIN_NAMES if hasattr(_builtins, name)
}

_real_import = _builtins.__import__


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    """A drop-in __import__ that only permits the curated allow-list (no relative imports)."""
    if level != 0 or name.split(".")[0] not in _ALLOWED_IMPORT_MODULES:
        raise ImportError(f"import of {name!r} is not permitted in the sandbox")
    return _real_import(name, globals, locals, fromlist, level)


_EXEC_BUILTINS: dict[str, Any] = {**_SAFE_BUILTINS, "__import__": _guarded_import}


def _flag_execute() -> bool:
    return os.getenv("AZALEA_GEN_FOUNDATION_EXECUTE", "").strip().lower() in {"1", "true", "yes", "on"}


def _ast_safe(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            return False
        if isinstance(node, ast.Name) and (node.id in _DANGEROUS_NAMES or node.id.startswith("__")):
            return False
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return False
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] not in _ALLOWED_IMPORT_MODULES for alias in node.names):
                return False
        if isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in _ALLOWED_IMPORT_MODULES:
                return False
    return True


def parse_safe(code: str, language: str) -> Optional[ast.AST]:
    """Return the parsed AST if ``code`` is Python that passes the gate, else ``None``."""
    if (language or "").lower() not in ("python", "py"):
        return None
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    return tree if _ast_safe(tree) else None


def _safe_value(value: Any, depth: int = 0) -> Any:
    """Reduce a local to a JSON-safe, bounded snapshot (semantic state, §7)."""
    if isinstance(value, bool) or value is None or isinstance(value, (int, float, str)):
        return value
    if depth >= 3:
        return None
    if isinstance(value, (list, tuple)):
        return [_safe_value(v, depth + 1) for v in list(value)[:MAX_COLLECTION]]
    if isinstance(value, dict):
        out = {}
        for i, (k, v) in enumerate(value.items()):
            if i >= MAX_STATE_ENTRIES:
                break
            if isinstance(k, (str, int, float, bool)):
                out[str(k)] = _safe_value(v, depth + 1)
        return out
    return None  # functions, objects, etc. are not part of semantic state


def _snapshot(local_vars: dict[str, Any]) -> dict[str, Any]:
    snap: dict[str, Any] = {}
    for i, (name, val) in enumerate(local_vars.items()):
        if name.startswith("__") or i >= MAX_STATE_ENTRIES:
            continue
        reduced = _safe_value(val)
        if reduced is not None or val is None:
            snap[name] = reduced
    return snap


def _entry_and_args(tree: ast.AST, input_spec: Any) -> tuple[Optional[str], list, dict]:
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    if isinstance(input_spec, dict):
        entry = input_spec.get("entry") or (funcs[-1] if funcs else None)
        return entry, list(input_spec.get("args") or []), dict(input_spec.get("kwargs") or {})
    if isinstance(input_spec, (list, tuple)):
        return (funcs[-1] if funcs else None), list(input_spec), {}
    return (funcs[-1] if funcs else None), ([input_spec] if input_spec is not None else []), {}


def execution_skip_reason(code: str, language: str, input: Any = None) -> Optional[str]:
    """Why execution would be skipped (for shadow telemetry), or None if it would run. Cheap: it only
    checks the flag + parses/gates the code, never executes."""
    if not _flag_execute():
        return "execution_disabled"
    if (language or "").lower() not in ("python", "py"):
        return "unsupported_language"
    if parse_safe(code, language) is None:
        return "unsafe_or_unparseable"
    entry, _, _ = _entry_and_args(parse_safe(code, language), input)
    if not entry:
        return "no_entry_function"
    return None


def execute(code: str, language: str, input: Any) -> ExecutionResult:
    """Run the snippet under the gate + bounds and return a STRUCTURED result (Layer 1): trace events,
    the function's return value, any exception, and a skip/error reason — so the pipeline can compare
    the executed answer against the model's claim and measure why execution was (not) possible."""
    started = time.time()
    skip = execution_skip_reason(code, language, input)
    if skip:
        return ExecutionResult(status="skipped", skip_reason=skip, trace_events=None,
                               return_value=None, exception=None, elapsed_ms=0.0)
    tree = parse_safe(code, language)
    entry, args, kwargs = _entry_and_args(tree, input)

    safe_globals: dict[str, Any] = {"__builtins__": _EXEC_BUILTINS}
    try:
        exec(compile(code, _SENTINEL_FILE, "exec"), safe_globals)  # restricted namespace + guarded import
    except Exception as exc:  # noqa: BLE001
        return ExecutionResult("error", "exec_failed", None, None, repr(exc),
                               round((time.time() - started) * 1000, 2))
    fn = safe_globals.get(entry)
    if not callable(fn):
        return ExecutionResult("error", "entry_not_callable", None, None, None,
                               round((time.time() - started) * 1000, 2))

    events: TraceEvents = []
    state = {"overflow": False, "steps": 0}

    class _Stop(Exception):
        pass

    def _tracer(frame, event, arg):  # local trace fn — only our sentinel frames
        if frame.f_code.co_filename != _SENTINEL_FILE:
            return None
        if event == "line":
            state["steps"] += 1
            if state["steps"] > MAX_STEPS or (time.time() - started) > MAX_SECONDS:
                state["overflow"] = True
                raise _Stop()
            events.append({
                "step_index": len(events),
                "code_line_refs": [frame.f_lineno],
                "state": _snapshot(frame.f_locals),
                "func": frame.f_code.co_name,
            })
        return _tracer

    prev = sys.gettrace()
    sys.settrace(_tracer)
    try:
        result = fn(*args, **kwargs)
    except _Stop:
        return ExecutionResult("overflow", "step_or_time_budget_exceeded", None, None, None,
                               round((time.time() - started) * 1000, 2))
    except Exception as exc:  # noqa: BLE001
        return ExecutionResult("error", "raised", None, None, repr(exc),
                               round((time.time() - started) * 1000, 2))
    finally:
        sys.settrace(prev)

    if not events:
        return ExecutionResult("error", "no_events", None, _safe_value(result), None,
                               round((time.time() - started) * 1000, 2))
    events.append({"step_index": len(events), "code_line_refs": [], "state": {},
                   "return_value": _safe_value(result)})
    return ExecutionResult("executed", None, events, _safe_value(result), None,
                           round((time.time() - started) * 1000, 2))


def run_trace(code: str, language: str, input: Any) -> Optional[TraceEvents]:
    """Back-compat events-or-None wrapper over :func:`execute` (the injected ExecutorFn shape, §6)."""
    return execute(code, language, input).trace_events
