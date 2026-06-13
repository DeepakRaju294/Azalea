"""Core artifacts of the V2 visual pipeline (VISUAL_SYSTEM_SPEC §6.5).

Flow: CanonicalExample -> Trace -> (DeltaFoldEngine) FrameState[] -> VisualModel.
These are typed contracts so fields don't scatter across prompts/intents/cards.
"""
from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict

# Versioning (§6.5) — attribute quality/regressions to a specific version.
VISUAL_SPEC_VERSION = 2
DELTA_SCHEMA_VERSION = 1
SIMULATOR_VERSION = "0.1.0"

TraceSource = Literal["deterministic_simulator", "llm_authored", "hybrid_repaired"]


class CanonicalExample(TypedDict, total=False):
    """Output of pipeline step 1; input to ExampleInvariantValidator + simulator.

    For a graph example: base_structure = {"nodes": [...], "edges": [[a,b],...]},
    input = {"start": "A"}.
    """

    example_id: str
    domain_object: str
    base_type: str
    mode: str
    algorithm: Optional[str]
    input: dict[str, Any]
    base_structure: dict[str, Any]
    expected_output: Any
    why_this_example: str
    learner_goal: str


class Decision(TypedDict, total=False):
    condition: str
    evaluated_to: Any  # bool OR enum, e.g. "less_than" | "greater_than" | "equal"
    reason: str


class TraceStep(TypedDict, total=False):
    step_index: int
    trace_step_id: str
    kind: str  # initialize|select_active|compare|enqueue|dequeue|visit|...
    delta: dict[str, Any]  # a state change OR {"no_op": True, "checked_element_ids": [...], "reason": ...}
    primary_change: str  # the ONE teaching focus (a delta key)
    decision: Decision
    learner_should_notice: str
    code_line_refs: list[int]
    runtime_label: str


class Trace(TypedDict, total=False):
    trace_id: str
    example_id: str
    trace_source: TraceSource
    initial_state: dict[str, Any]
    steps: list[TraceStep]
    visual_spec_version: int
    delta_schema_version: int
    simulator_version: str


class FrameState(TypedDict):
    """Output of the DeltaFoldEngine — one per step, fully computed."""

    step_index: int
    state_before: dict[str, Any]
    delta: dict[str, Any]
    state_after: dict[str, Any]
    diff: dict[str, Any]  # highlight metadata (set_active, newly_added, newly_completed, ...)


class VisualModel(TypedDict, total=False):
    """Compiler output consumed by the frontend renderer (read-only there).

    `base` holds the structure once; `frames[i].state` holds the per-step
    semantic state the renderer themes to colours. Shape matches what
    components/visuals_v2/NodeLinkVisual.tsx reads (base + frame.state).
    """

    id: str
    base_type: str
    mode: str
    example_id: str
    trace_id: str
    base: dict[str, Any]  # {"nodes": [...], "edges": [...]}
    frames: list[dict[str, Any]]  # [{"state": {...}}]
    provenance: dict[str, Any]  # PROJECTOR_SYSTEM_SPEC §10.1 — state_source/tier/... (see provenance.py)


class RenderStep(TypedDict, total=False):
    step_index: int
    frame_index: int
    trace_step_id: str
    primary_change: str
    caption: str  # learner_should_notice (placeholder until prose is generated)
