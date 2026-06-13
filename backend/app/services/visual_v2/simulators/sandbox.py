"""Subprocess sandbox for the code tracer (VISUAL_SYSTEM_SPEC §5.4).

Runs the tracer harness in a separate process with a hard timeout, so untrusted
LLM-generated code can't hang or corrupt the server process (same pattern as
`code_runner`). This is isolation + a time budget — NOT a full security sandbox;
defense-in-depth (restricted builtins / no fs+network / container) is a follow-up,
and acceptable here because the code is validated educational algorithm code, not
arbitrary user input.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# backend/ = code_tracer.py → simulators → visual_v2 → services → app → backend
_BACKEND_DIR = Path(__file__).resolve().parents[4]
_HARNESS_MODULE = "app.services.visual_v2.simulators.code_tracer"


class SandboxError(RuntimeError):
    pass


def run_sandboxed(
    code: str,
    entry_function: str,
    input_spec: dict[str, Any],
    *,
    timeout: float = 3.0,
) -> tuple[list[dict[str, Any]], Any]:
    """Run the tracer in a subprocess; return (raw_steps, result). Raises
    SandboxError on timeout, crash, or harness error."""
    payload = json.dumps({"code": code, "entry": entry_function, "input": input_spec})
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_BACKEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        completed = subprocess.run(
            [sys.executable, "-m", _HARNESS_MODULE],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(_BACKEND_DIR),
        )
    except subprocess.TimeoutExpired as exc:
        raise SandboxError(f"code execution exceeded {timeout:.1f}s") from exc

    out = (completed.stdout or "").strip()
    if not out:
        raise SandboxError(f"no output from tracer (stderr: {(completed.stderr or '')[:200]})")
    try:
        data = json.loads(out.splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise SandboxError(f"unparseable tracer output: {out[:200]}") from exc
    if "error" in data:
        raise SandboxError(data["error"])
    return data.get("steps", []), data.get("result")
