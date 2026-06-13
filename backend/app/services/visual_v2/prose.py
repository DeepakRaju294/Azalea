"""Prose generation + TextVisualSyncValidator (VISUAL_SYSTEM_SPEC §5.5).

Prose is downstream of the locked trace: it may explain/compress/rephrase, never
introduce a new state fact. The model emits `text_refs` for what it claims; the
validator compares those against the frame's folded state (no NLP). A deterministic
prose fallback (derived straight from the trace) is always in-sync by construction.
"""
from __future__ import annotations

from typing import Any

from .schemas import FrameState, Trace


def derive_text_refs(frame: FrameState) -> dict[str, Any]:
    """Text refs implied by a frame — used by the deterministic fallback (always in-sync)."""
    after = frame["state_after"]
    diff = frame.get("diff") or {}
    mentioned: list[str] = []
    if diff.get("set_active"):
        mentioned.append(diff["set_active"])
    mentioned.extend(diff.get("newly_added") or [])
    return {
        "mentioned_elements": mentioned,
        "mentioned_values": {
            "active": after.get("active"),
            "output": list(after.get("output") or []),
            "frontier": list((after.get("frontier") or {}).get("items") or []),
        },
        "code_line_refs": [],
    }


def validate_text_sync(text_refs: dict[str, Any], frame: FrameState, valid_ids: set[str]) -> list[str]:
    """Reject prose that mentions an element/value not in the frame's folded state."""
    errors: list[str] = []
    after = frame["state_after"]

    for element in text_refs.get("mentioned_elements") or []:
        if element not in valid_ids:
            errors.append(f"prose mentions {element!r}, which is not a node in the visual")

    values = text_refs.get("mentioned_values") or {}
    if "active" in values and values["active"] != after.get("active"):
        errors.append(f"prose active {values['active']!r} != frame active {after.get('active')!r}")
    if "output" in values and list(values["output"]) != list(after.get("output") or []):
        errors.append(f"prose output {values['output']} != frame output {after.get('output')}")
    if "frontier" in values:
        frame_frontier = list((after.get("frontier") or {}).get("items") or [])
        if list(values["frontier"]) != frame_frontier:
            errors.append(f"prose frontier {values['frontier']} != frame frontier {frame_frontier}")
    return errors


def deterministic_prose(trace: Trace, frames: list[FrameState]) -> list[dict[str, Any]]:
    """Prose derived purely from the trace — guaranteed in-sync; the fallback."""
    steps = list(trace.get("steps") or [])
    result: list[dict[str, Any]] = []
    for i, frame in enumerate(frames):
        step = steps[i] if i < len(steps) else {}
        notice = str(step.get("learner_should_notice") or "")
        result.append(
            {
                "step_index": frame["step_index"],
                "points": [notice] if notice else [],
                "text_refs": derive_text_refs(frame),
            }
        )
    return result
