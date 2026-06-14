"""Code-execution tracer (VISUAL_SYSTEM_SPEC §5.4, §6.1).

"Run once, read the truth": execute the generated code a single time on the
example input under `sys.settrace`, recording the real line / variables /
call-stack at every executed line. That recording IS the trace — the visual is
derived from it, never guessed from the source text.

Trusted-code path (in-process) for tests + the deterministic core. Untrusted
production code must run via the subprocess+timeout sandbox (see
`run_code_execution_sandboxed`, which reuses the code_runner pattern); the
recording/serialization logic is identical either way.
"""
from __future__ import annotations

import ast
import sys
from collections import deque
from typing import Any

from ..schemas import (
    DELTA_SCHEMA_VERSION,
    SIMULATOR_VERSION,
    VISUAL_SPEC_VERSION,
    CanonicalExample,
    Trace,
    TraceStep,
)

_USERCODE_FILE = "<usercode>"
_MAX_STEPS = 600
# Variable names that conventionally hold the accumulating answer.
_ACCUMULATOR_NAMES = ("result", "output", "res", "ans", "path", "order", "visited", "acc")


class TreeNode:
    def __init__(self, val: Any = 0, left: "TreeNode | None" = None, right: "TreeNode | None" = None):
        self.val = val
        self.left = left
        self.right = right


class _StepLimit(Exception):
    pass


def build_tree(values: list[Any]) -> TreeNode | None:
    """Level-order (LeetCode-style) tree builder; `None` marks a missing child."""
    if not values:
        return None
    vals = list(values)
    root = TreeNode(vals[0])
    queue: deque[TreeNode] = deque([root])
    i = 1
    while queue and i < len(vals):
        node = queue.popleft()
        if i < len(vals):
            if vals[i] is not None:
                node.left = TreeNode(vals[i])
                queue.append(node.left)
            i += 1
        if i < len(vals):
            if vals[i] is not None:
                node.right = TreeNode(vals[i])
                queue.append(node.right)
            i += 1
    return root


def serialize_value(value: Any, _depth: int = 0) -> Any:
    """Convert a runtime object to a readable display value for the panels."""
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    if _depth > 4:
        return "…"
    if hasattr(value, "val") or hasattr(value, "value"):
        return getattr(value, "val", getattr(value, "value", None))
    if isinstance(value, (list, tuple)):
        return [serialize_value(v, _depth + 1) for v in list(value)[:50]]
    if isinstance(value, set):
        return sorted(serialize_value(v, _depth + 1) for v in list(value)[:50])
    if isinstance(value, dict):
        return {str(k): serialize_value(v, _depth + 1) for k, v in list(value.items())[:50]}
    return repr(value)[:60]


def _build_args(input_spec: dict[str, Any]) -> list[Any]:
    """Construct the entry-function arguments from the declared input spec."""
    args: list[Any] = []
    if "tree" in input_spec:
        args.append(build_tree(input_spec["tree"]))
    elif "array" in input_spec:
        args.append(list(input_spec["array"]))
    elif "args" in input_spec:
        args.extend(input_spec["args"])
    for key in ("target", "k", "n"):
        if key in input_spec:
            args.append(input_spec[key])
    return args


def _returned_vars(code: str) -> dict[str, str]:
    """Map each function to the variable it RETURNS — its own 'result' — so the
    accumulator is derived from the code, not matched against a hardcoded name list (the
    LLM may call it `sorted_array`, `merged`, anything). `return f(x)` (a call, e.g.
    merge_sort's `return merge(...)`) has no single variable and is skipped; the last
    `return <name>` wins when a function has several."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {}
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Name):
                    out[node.name] = sub.value.id
    return out


def _accumulator(local_vars: dict[str, Any], preferred: str | None = None) -> Any:
    # The function's OWN returned variable first (derived from the code), then the
    # conventional names as a fallback for functions that return an expression.
    if preferred and isinstance(local_vars.get(preferred), list):
        return serialize_value(local_vars[preferred])
    for name in _ACCUMULATOR_NAMES:
        if name in local_vars and isinstance(local_vars[name], list):
            return serialize_value(local_vars[name])
    return None


def trace_execution(
    code: str,
    entry_function: str,
    input_spec: dict[str, Any],
    *,
    max_steps: int = _MAX_STEPS,
) -> tuple[list[dict[str, Any]], Any]:
    """Run `code` once and return (raw_steps, return_value).

    Each raw step: {line, vars, call_stack, output}. TRUSTED in-process path —
    callers handling untrusted code must use the sandbox wrapper.
    """
    namespace: dict[str, Any] = {"TreeNode": TreeNode}
    compiled = compile(code, _USERCODE_FILE, "exec")
    exec(compiled, namespace)  # noqa: S102 — trusted/sandboxed code only
    if entry_function not in namespace:
        raise ValueError(f"entry function {entry_function!r} not defined")
    args = _build_args(input_spec)
    returned = _returned_vars(code)  # function -> its returned variable (its result)

    steps: list[dict[str, Any]] = []

    def _call_stack(frame: Any) -> list[str]:
        names: list[str] = []
        f = frame
        while f is not None and f.f_code.co_filename == _USERCODE_FILE:
            names.append(f.f_code.co_name)
            f = f.f_back
        return list(reversed(names))

    def tracer(frame: Any, event: str, arg: Any):  # noqa: ANN001
        if frame.f_code.co_filename != _USERCODE_FILE:
            return tracer
        if event == "line":
            if len(steps) >= max_steps:
                raise _StepLimit()
            local_vars = {k: serialize_value(v) for k, v in frame.f_locals.items()}
            steps.append(
                {
                    "line": frame.f_lineno,
                    "vars": local_vars,
                    "call_stack": _call_stack(frame),
                    "output": _accumulator(frame.f_locals, returned.get(frame.f_code.co_name)),
                }
            )
        return tracer

    sys.settrace(tracer)
    try:
        result = namespace[entry_function](*args)
    except _StepLimit:
        result = None
    finally:
        sys.settrace(None)
    return steps, serialize_value(result)


def simulate_code_execution(
    example: CanonicalExample,
    *,
    sandboxed: bool = False,
    timeout: float = 3.0,
) -> Trace:
    """Registered simulator for the `code_execution` mode. `sandboxed=True` runs the
    code in the subprocess sandbox (use in production for untrusted code); the
    default in-process path is for trusted code + deterministic tests."""
    code = str(example.get("code") or (example.get("base_structure") or {}).get("code") or "")
    entry = str(example.get("entry_function") or (example.get("input") or {}).get("entry_function") or "")
    input_spec = dict(example.get("input") or {})
    if sandboxed:
        from .sandbox import run_sandboxed

        raw_steps, _result = run_sandboxed(code, entry, input_spec, timeout=timeout)
    else:
        raw_steps, _result = trace_execution(code, entry, input_spec)

    steps: list[TraceStep] = []
    for i, rs in enumerate(raw_steps):
        delta: dict[str, Any] = {
            "set_highlight_lines": [rs["line"]],
            "set_locals": rs["vars"],
            "set_call_stack": rs["call_stack"],
        }
        if rs["output"] is not None:
            delta["set_output"] = rs["output"]
        steps.append(
            TraceStep(
                step_index=i,
                trace_step_id=f"s{i}",
                kind="line",
                delta=delta,
                primary_change="set_highlight_lines",
                runtime_label=" › ".join(rs["call_stack"]),
                learner_should_notice=f"Line {rs['line']} runs.",
            )
        )

    trace = Trace(
        trace_id=f"{example.get('example_id', 'ex')}:code_execution",
        example_id=str(example.get("example_id", "")),
        trace_source="deterministic_simulator",
        initial_state={"highlight_lines": [], "variables": {}, "call_stack": [], "output": []},
        steps=steps,
        visual_spec_version=VISUAL_SPEC_VERSION,
        delta_schema_version=DELTA_SCHEMA_VERSION,
        simulator_version=SIMULATOR_VERSION,
    )
    # The algorithm's ACTUAL return value — the ground truth for "Final result" on the
    # terminal card. Reading a per-step accumulator misses it for code that returns an
    # expression or a non-conventionally-named variable (e.g. `sorted_array`).
    trace["return_value"] = _result
    return trace


def run_harness() -> None:
    """Subprocess entry point: read {code, entry, input} as JSON on stdin, run the
    tracer, emit {steps, result} (or {error}) as JSON on stdout. Run via
    `python -m app.services.visual_v2.simulators.code_tracer` from the sandbox."""
    import json

    try:
        payload = json.loads(sys.stdin.read() or "{}")
        steps, result = trace_execution(
            str(payload.get("code") or ""),
            str(payload.get("entry") or ""),
            dict(payload.get("input") or {}),
        )
        sys.stdout.write(json.dumps({"steps": steps, "result": result}))
    except Exception as exc:  # noqa: BLE001 — report failure to the parent, don't crash
        sys.stdout.write(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))


if __name__ == "__main__":
    run_harness()
