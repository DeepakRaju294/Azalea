"""Static-visual path (VISUAL_SYSTEM_SPEC §5.0).

`define_structure` / `compare_cases` visuals are `base + one validated at-rest
state` — no simulator, no trace, no fold. This is the cheap breadth unlock: once a
base type has a compiler, its "show this structure at rest" mode is reachable
here. Slice: node_link (tree/graph at rest); extends to other base types as their
compilers land.
"""
from __future__ import annotations

from typing import Any

from .compilers.node_link import compile_node_link
from .example_invariants import validate_static_example
from .profiles import profile_for_mode
from .schemas import CanonicalExample, FrameState
from .telemetry import debug_payload
from .validators import pedagogical_check, validate_model

# At-rest states per base type (everything un-acted-on).
_REST_STATE = {
    "node_link_diagram": {"active": None, "frontier": {"kind": "queue", "items": []}, "visited": [], "output": []},
}


def run_static_visual(
    example: CanonicalExample,
    *,
    model_id: str = "v2_static",
    topic_id: str = "",
) -> dict[str, Any]:
    """Build a single-frame at-rest visual. Returns the same result shape as the
    dynamic pipeline (status / model / render_steps / debug)."""
    mode = str(example.get("mode") or "")
    profile = profile_for_mode(mode)

    def fail(stage: str, errors: list[str]) -> dict[str, Any]:
        return {
            "status": "failed", "stage": stage, "errors": errors,
            "model": None, "render_steps": [], "frames": [],
            "debug": debug_payload(example=example, visual_status="failed", failed_validator=stage, topic_id=topic_id),
        }

    if profile is None:
        return fail("no_profile", [f"no profile for mode {mode!r}"])

    errors = validate_static_example(example)
    if errors:
        return fail("StaticExampleValidator", errors)

    base_type = profile["base_type"]
    rest = _REST_STATE.get(base_type)
    if rest is None:
        return fail("no_static_compiler", [f"no static path for base_type {base_type!r} yet"])

    frame = FrameState(step_index=0, state_before=rest, delta={}, state_after=rest, diff={"no_op": True})

    if base_type == "node_link_diagram":
        model, render_steps = compile_node_link(
            base_structure=example["base_structure"], frames=[frame], trace_steps=[],
            profile=profile, mode=mode, model_id=model_id, example_id=str(example.get("example_id", "")),
        )
    else:  # pragma: no cover — guarded above
        return fail("no_static_compiler", [base_type])

    model_errors = validate_model(model)
    if model_errors:
        return fail("VisualModelValidator", model_errors)

    pedagogy = pedagogical_check(model, profile)
    if pedagogy["verdict"] == "reject":
        return fail("PedagogicalVisualValidator", [m for _, m in pedagogy["issues"]])

    return {
        "status": "validated", "stage": "validated", "errors": [],
        "model": model, "render_steps": render_steps, "frames": [frame],
        "static": True, "pedagogy": pedagogy,
        "debug": debug_payload(example=example, visual_status="validated", topic_id=topic_id),
    }
