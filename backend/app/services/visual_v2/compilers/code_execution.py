"""CodeExecutionCompiler — folded FrameState[] -> a code_execution_panel VisualModel.

Targets the EXACT contract the frontend `CodeExecutionPanel.tsx` reads:
  base  = { code, language }
  frame = { index, state, highlights, annotations, selectable_elements, transitions }
  state = { visible_until_line, highlight_lines:[start,end],
            variables:[{name,value}], call_stack:[str], output:[str] }
Styles the recorded execution; never re-decides it (§6.3).
"""
from __future__ import annotations

from typing import Any

from ..schemas import FrameState, RenderStep, Trace, TraceStep, VisualModel


def _frame_state(after: dict[str, Any], total_lines: int) -> dict[str, Any]:
    lines = list(after.get("highlight_lines") or [])
    line = lines[0] if lines else 0
    variables = [
        {"name": str(k), "value": _fmt(v)} for k, v in (after.get("variables") or {}).items()
    ]
    output_val = after.get("output")
    if isinstance(output_val, list):
        output = [", ".join(_fmt(v) for v in output_val)] if output_val else []
    elif output_val in (None, ""):
        output = []
    else:
        output = [_fmt(output_val)]
    return {
        "visible_until_line": total_lines,
        "highlight_lines": [line, line],
        "variables": variables,
        "call_stack": [str(x) for x in (after.get("call_stack") or [])],
        "output": output,
    }


def _fmt(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_fmt(v) for v in value) + "]"
    return str(value)


def compile_code_execution(
    *,
    code: str,
    frames: list[FrameState],
    trace_steps: list[TraceStep],
    profile: dict[str, Any],
    model_id: str,
    language: str = "python",
    example_id: str = "",
    trace_id: str = "",
) -> tuple[VisualModel, list[RenderStep]]:
    total_lines = len(code.split("\n"))
    model_frames: list[dict[str, Any]] = []
    for i, frame in enumerate(frames):
        model_frames.append(
            {
                "index": i,
                "state": _frame_state(frame["state_after"], total_lines),
                "highlights": {"active_node": "", "highlight_path": []},
                "annotations": [],
                "selectable_elements": [],
                "transitions": [],
            }
        )

    model = VisualModel(
        id=model_id,
        base_type=str(profile.get("base_type", "code_execution_panel")),
        mode="code_execution",
        example_id=example_id,
        trace_id=trace_id,
        base={"code": code, "language": language},
        frames=model_frames,
        element_catalog=[],
    )

    render_steps: list[RenderStep] = []
    for i, frame in enumerate(frames):
        step = trace_steps[i] if i < len(trace_steps) else {}
        lines = frame["state_after"].get("highlight_lines") or []
        render_steps.append(
            RenderStep(
                step_index=int(frame.get("step_index", i)),
                frame_index=i,
                trace_step_id=str(step.get("trace_step_id", f"s{i}")),
                primary_change="set_highlight_lines",
                caption=str(step.get("learner_should_notice") or (f"Line {lines[0]} runs." if lines else "")),
            )
        )
    return model, render_steps


def compile_from_trace(
    *,
    trace: Trace,
    frames: list[FrameState],
    code: str,
    profile: dict[str, Any],
    model_id: str,
    language: str = "python",
) -> tuple[VisualModel, list[RenderStep]]:
    return compile_code_execution(
        code=code,
        frames=frames,
        trace_steps=list(trace.get("steps") or []),
        profile=profile,
        model_id=model_id,
        language=language,
        example_id=str(trace.get("example_id", "")),
        trace_id=str(trace.get("trace_id", "")),
    )
