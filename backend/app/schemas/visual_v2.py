"""Visual System V2 — data contracts.

TypedDicts for the v2 lesson pipeline. All shapes here are the SOURCE OF
TRUTH for what the LLM emits (VisualIntent + WorkedExamplePlan), what the
backend compilers produce (VisualModel + VisualFrame), what the frontend
consumes (RenderStep + LessonV2), and what the chat sidebar receives when
a learner clicks a visual element (VisualContextPayload).

Mirrored in `frontend/lib/visual_v2_types.ts` (keep in sync).

Coexists with all legacy schemas; does NOT import or modify them.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict


# ===========================================================================
# CORE TYPES — used by every visual
# ===========================================================================


class ElementBounds(TypedDict):
    """Bounding box in renderer-local coordinates (0-100 unit space).

    Used both for click hit-testing (mapped into actual pixels by the
    frontend at render time) and for transition `move` specs.
    """
    x: float
    y: float
    width: float
    height: float


class SelectableElement(TypedDict):
    """A clickable element in a visual frame.

    `element_id` is stable across frames for the same conceptual element
    (e.g. node "30" in step 1 has the same element_id as node "30" in
    step 5). This stability is what makes transitions animate instead of
    teleporting and what makes click-to-ask reference the right thing.
    """
    element_id: str
    element_type: str        # see ELEMENT_TYPES below
    semantic_label: str      # learner-readable, becomes part of QA prompt
    bounds: ElementBounds
    aria_label: str
    keyboard_index: int      # tab order among elements on this frame
    payload: dict[str, Any]  # element_type-specific snapshot for QA context


# Valid element_type values. Each compiler emits a subset.
ELEMENT_TYPES = (
    "node",                  # node_link
    "edge",                  # node_link
    "edge_label",            # node_link
    "stack_item",            # node_link (call_stack panel)
    "output_item",           # node_link / code_execution
    "frontier_item",         # node_link
    "cell",                  # indexed_sequence, grid_matrix, table
    "pointer",               # indexed_sequence (l, r, m, etc.)
    "range",                 # indexed_sequence (sliding window, sorted prefix)
    "code_line",             # code_execution
    "code_variable",         # code_execution (variables panel)
    "code_frame",            # code_execution (call stack)
    "subexpression",         # formula
    "symbol_definition",     # formula
    "row",                   # table
    "column",                # table
    "row_header",            # table, grid_matrix
    "column_header",         # table, grid_matrix
    "axis_label",            # coordinate_graph
    "curve_segment",         # coordinate_graph
    "plotted_point",         # coordinate_graph
    "shaded_region",         # coordinate_graph, set_region
    "tangent_line",          # coordinate_graph
    "shape",                 # geometric
    "side",                  # geometric
    "angle",                 # geometric
    "measurement_label",     # geometric
    "message",               # timeline_sequence
    "actor_lane",            # timeline_sequence
    "time_tick",             # timeline_sequence
    "memory_frame",          # memory_layout
    "heap_object",           # memory_layout
    "pointer_arrow",         # memory_layout
    "variable_binding",      # memory_layout
    "set",                   # set_region
    "region",                # set_region
    "element_in_region",     # set_region
    "hotspot",               # image_illustration
    "support_step",          # support visual (step_flow), each step
)


# ===========================================================================
# TRANSITIONS — frame-to-frame animation specs
# ===========================================================================


TransitionKind = Literal[
    "move",                  # element changes position
    "fade_in",               # element appears (opacity 0 → 1)
    "fade_out",              # element disappears
    "appear",                # element enters the frame for the first time
    "disappear",             # element leaves the frame
    "style_change",          # color/stroke/fill change (e.g. node becomes "current")
    "value_change",          # text content updates (e.g. variable trace number flips)
    "swap",                  # two elements exchange positions
    "highlight_pulse",       # one-shot attention pulse
    "stagger_group",         # group of child transitions with staggered timing
]


TransitionEasing = Literal["ease", "ease_in", "ease_out", "ease_in_out", "linear", "spring"]


class Transition(TypedDict):
    """How `target_element_id` arrives at its frame N+1 state from frame N.

    The frontend transition layer interprets `kind` + `spec` and animates
    accordingly. Defaults: duration_ms=300, delay_ms=0, easing="ease_in_out".
    """
    kind: TransitionKind
    target_element_id: str
    duration_ms: int
    delay_ms: int
    easing: TransitionEasing
    spec: dict[str, Any]      # kind-specific payload


class TransitionHint(TypedDict):
    """LLM-provided ordering / semantic hint that overrides default
    transition generation. E.g. in binary search, the LLM specifies
    'compute m before moving l' so the compiler emits the m highlight
    transition before the l move transition.
    """
    description: str
    sequence: list[str]       # element_ids in the order their transitions should fire
    stagger_ms: int           # delay between consecutive transitions


# ===========================================================================
# FRAMES + ANNOTATIONS
# ===========================================================================


class FrameAnnotation(TypedDict):
    """A learner-facing callout on a frame. Can attach to an element so
    the renderer positions it near that element."""
    id: str
    text: str
    attached_to_element_id: str | None
    appears_in_frame: int     # for staggered annotation entry


class VisualFrame(TypedDict):
    """One frame of a VisualModel — a static snapshot plus the transitions
    that move INTO it from the previous frame."""
    index: int
    state: dict[str, Any]              # overlay over VisualModel.base; compiler-specific
    highlights: dict[str, Any]         # active node/edge/cell/line
    annotations: list[FrameAnnotation]
    selectable_elements: list[SelectableElement]
    transitions: list[Transition]      # empty on frame 0


# ===========================================================================
# CATALOG — model-level element registry for pre-allocation
# ===========================================================================


class ElementCatalogEntry(TypedDict):
    """Every element_id that appears in any frame of the model, with its
    lifetime range. The frontend pre-allocates render nodes to avoid
    mount/unmount churn during transitions."""
    element_id: str
    element_type: str
    first_frame: int          # frame index where this element first appears
    last_frame: int           # -1 means "all frames from first_frame onward"
    initial_bounds: ElementBounds


# ===========================================================================
# VISUAL INTENT (LLM output) + VISUAL MODEL (compiler output)
# ===========================================================================


class VisualIntent(TypedDict):
    """What the LLM emits per card. Pure description, no render data."""
    base_type: str            # one of BASE_VISUAL_TYPES or SUPPORT_VISUALS
    mode: str
    description: str          # plain-English scene/state storyboard
    purpose: str              # one sentence: what learner should UNDERSTAND
    static_or_dynamic: Literal["static", "dynamic"]


class VisualModel(TypedDict):
    """What the compiler produces. The frontend renders this directly."""
    id: str
    base_type: str
    mode: str
    base: dict[str, Any]                  # compiled base structure (nodes, code, cells, etc.)
    frames: list[VisualFrame]
    element_catalog: list[ElementCatalogEntry]


# ===========================================================================
# WORKED EXAMPLE PLAN — universal across visual types
# ===========================================================================


class WorkedExampleStep(TypedDict):
    """One step in a worked-example trace. Independent of base_type;
    `state_after` shape is interpreted by the compiler."""
    step_number: int
    action: str
    reason: str
    text_points: list[str]
    state_after: dict[str, Any]
    transition_hints: list[TransitionHint]


class WorkedExamplePlan(TypedDict):
    """Universal worked-example plan. Replaces the two pilot plans
    (math `worked_example_plan` + algorithm `node_link_worked_example`)."""
    id: str
    visual_intent: VisualIntent
    problem_setup: str
    terminal_state: str
    base_state: dict[str, Any]
    steps: list[WorkedExampleStep]


# ===========================================================================
# SUPPORT VISUALS — bypass compilation
# ===========================================================================


class SupportVisualPayload(TypedDict):
    """For step_flow, practice_feedback, etc. Renders via existing
    components without going through the compiler registry."""
    support_type: str
    mode: str
    data: dict[str, Any]
    selectable_elements: list[SelectableElement]


# ===========================================================================
# RENDER STEP + LESSON V2 — frontend consumption format
# ===========================================================================


class RenderStep(TypedDict):
    """One step in the lesson flow. Points to a (visual_model, frame_index)
    or carries a support visual. The frontend iterates render_steps to
    drive the lesson."""
    id: str
    card_id: str
    title: str
    points: list[str]
    role: str                          # one of CARD_ROLES
    visual_model_id: str | None
    frame_index: int | None
    code_model_id: str | None
    code_frame_index: int | None
    support_visual: SupportVisualPayload | None
    animate_into: bool                 # if True, animate from prev step's frame
    notes: str                         # learner-facing focus note
    # Set when role == "practice"; resolves to a PracticeQuestion in
    # LessonV2.practice_questions[] by .id. None for non-practice steps.
    practice_question_id: str | None


class PracticeQuestion(TypedDict):
    """Practice question stored separately from render flow. RenderStep
    role='practice' references practice_question_index."""
    id: str
    question_type: str
    question_text: str
    correct_answer: str
    choices: list[str]
    skill_target: str
    concept_tested: str


class LessonMetadata(TypedDict):
    starting_mode: str
    estimated_state: str
    adaptation_summary: str
    teaching_strategy: str


class LessonV2(TypedDict):
    """Top-level lesson contract. No legacy `lesson_cards[]`."""
    lesson_version: int                # always 2
    title: str
    topic_summary: str
    estimated_minutes: int
    visual_models: list[VisualModel]
    render_steps: list[RenderStep]
    practice_questions: list[PracticeQuestion]
    source_chunk_ids: list[str]
    source_summary: str
    metadata: LessonMetadata


# ===========================================================================
# VISUAL CONTEXT PAYLOAD — click-to-ask input to QA backend
# ===========================================================================


class VisualContextPayload(TypedDict):
    """Sent to /lessons-v2/visual-qa when the learner clicks an element.

    `formatted_context` is filled in by the backend VisualContextFormatter
    before the chat LLM call — the frontend leaves it empty.
    """
    visual_model_id: str
    frame_index: int
    element: SelectableElement
    surrounding_state: dict[str, Any]   # frame.state at click time
    base_type: str
    mode: str
    formatted_context: str              # backend-generated, empty when sent from frontend


# ===========================================================================
# COMPILE CONTEXT — passed to every compiler
# ===========================================================================


class CompileContext(TypedDict):
    """Context the orchestrator passes to each compiler. Lets compilers
    share state across the same lesson (e.g. worked-example reuses the
    background card's structure)."""
    topic_id: str
    topic_hint: str
    topic_type: str
    visual_domain: str
    locale: str
    source_chunks_excerpt: str
    already_compiled_models: dict[str, VisualModel]  # keyed by visual_model_id
