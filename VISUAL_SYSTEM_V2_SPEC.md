# Visual System V2 — Implementation Spec

Status: design + active implementation. v2 files coexist with legacy; nothing in the legacy pipeline is modified.

Last updated: 2026-06-02

---

## 1. Purpose

Azalea's visual system today is two systems running in parallel: an older "LLM emits render JSON per card → backend converts to legacy lesson format → frontend infers what to render" pipeline, and two newer "LLM emits a plan, backend materializes per-step cards" pilots (math `worked_example_plan` and `node_link_worked_example`). This spec defines the end state — a single, uniform pipeline where the LLM emits intent only, the backend compiles renderable models, the frontend renders + animates state transitions, and learners can click any element to ask a contextualized question — and proposes a phased migration that:

1. Builds the new system as v2 files alongside the existing code so nothing is broken mid-migration.
2. Lands the biggest learner-facing wins first (consistent worked-example visuals, animated transitions, click-to-ask).
3. Defers the long tail of new visual types (geometric, set_region, timeline, memory_layout, coordinate_graph, image) until there's a topic that needs each.
4. Treats the existing pilots and `_synthesize_node_link_plan_from_lean_cards` as transitional bridges — the synthesizer's pattern becomes the universal compiler's fallback.

**Two cross-cutting capabilities** drive most of the contract decisions and span every base type:

- **Click-to-ask interactivity**: every meaningful element in every visual (node, edge, cell, code line, formula subexpression, table row, etc.) is clickable. Clicking opens the chat sidebar with structured context auto-attached, identical UX to the existing text-highlight-to-ask flow.
- **Animated state transitions in worked examples**: between consecutive frames, the changes are animated, not snapped. A binary-search pointer slides from `l=0` to `l=m+1`; the active BST node smoothly transitions purple; an edge fills in as "traversed". Learners *see* the algorithm move, not just step through state snapshots.

These two capabilities cascade into the data contracts, every compiler, the frontend renderer architecture, the QA backend, and accessibility behavior.

---

## 2. Current state inventory

### 2.1 What the LLM emits today

Defined by `LEAN_CARD_SCHEMA` in [backend/venv/app/services/llm_client.py](backend/venv/app/services/llm_client.py) (around line 1262). Each card includes:

- Intent fields: `card_type`, `blueprint_key`, `title`, `learning_job`, `visual_type`, `visual_description`, `visual_focus`
- Render data fields: `visual_columns`, `visual_rows`, `visual_steps`, `visual_formula`, `visual_symbols`, `visual_center`, `visual_nodes`, `visual_edges`, `visual_array_values`, `visual_array_rows`, `visual_array_pointers`, `visual_array_ranges`, `visual_array_annotations`, `visual_data_points`, `visual_key_points`, `visual_wrong`, `visual_correct`, `visual_wrong_label`, `visual_correct_label`, `visual_why`, `visual_x_label`, `visual_y_label`
- Two top-level optional plans: `worked_example_plan` (math) and `node_link_worked_example` (algorithm/data-structure)

The lesson prompt at [lean_lesson_prompt.py](backend/venv/app/prompts/lean_lesson_prompt.py) tells the LLM to fill the per-card render fields for whatever `visual_type` it chose. For most cards this means the LLM is doing both intent AND rendering — which is the source of the inconsistencies we keep patching.

### 2.2 What the backend produces today

`_convert_lean_to_legacy` in [lean_lesson_generator.py](backend/venv/app/services/lean_lesson_generator.py) (~line 5706) converts the LLM's lean cards into a `lesson_json` shape with a `lesson_cards: [...]` array. Each legacy card has `visual_plan` (the render-ready data) built by `_build_visual_plan` (line 800).

Two materializers exist and are dispatched by topic type:
- `_materialize_worked_example_plan_to_cards` (line ~5294) — for `math_formula_method` topics.
- `_materialize_node_link_worked_example_to_cards` (line ~5568) — for `algorithm_walkthrough` / `data_structure_operation`.
- `_synthesize_node_link_plan_from_lean_cards` (just added) — backstop that reconstructs a node-link plan from the LLM-emitted per-card cards when the LLM nulled the plan field.

Several legacy repair passes also run: `_replace_graph_traversal_worked_examples_with_trace`, `_apply_traversal_highlights_to_worked_examples`, `_add_completion_state_to_background_cards`, `_unify_process_card_steps`, `_ensure_progressive_step_flow_steps`, `_accumulate_code_walkthrough_visuals`, `_sync_coding_worked_examples_to_final_code`, `_ensure_coding_graph_worked_example_visuals`.

### 2.3 What the frontend resolves today

[frontend/app/study-paths/[studyPathId]/learn/page.tsx](frontend/app/study-paths/[studyPathId]/learn/page.tsx) — ~12,400 lines. The visual resolution chain for a flow_card is:

1. `resolveCardVisual(card, visuals)` (~line 7405)
2. `LearningCard.resolvedVisual` (~line 5830) — checks `codeVisualFromCard`, `workedExampleCodeVisualFromCard`, `codingWorkedExampleCompositeVisual`, falling back to `card.visual_plan`
3. `isLessonVisualRenderable` (~line 5003)
4. `VisualRenderer` (~line 8229) dispatches to ~17 typed renderers

The frontend is doing visual recovery work. That logic disappears in v2.

**Today's interactivity surface**: text highlighting opens the chat sidebar (`onAskAboutText`). Clicking a visual does nothing — no element-level interaction. Worked-example step changes are snap-changes; no animated transitions exist.

### 2.4 Topic classification today

`enrich_topic_with_course_type` in [course_type_classifier.py](backend/venv/app/services/course_type_classifier.py) sets `topic_type`. It does NOT set a visual domain — the visual choice is later inferred from blueprint pipe-separated rules.

### 2.5 Existing visual types and what becomes of them in v2

Mapping from current visual types → v2 base type or support visual. **No current visual is dropped without replacement.**

| Today                          | V2 destination                                                  |
|--------------------------------|------------------------------------------------------------------|
| `node_link_diagram`            | base `node_link_diagram` (modes: tree_hierarchy, graph_network, …) |
| `concept_map`                  | base `node_link_diagram` mode `tree_hierarchy` or `dependency_graph` |
| `relationship_map`             | base `node_link_diagram` mode `dependency_graph`                |
| `circuit_diagram`              | base `node_link_diagram` mode `circuit`                          |
| `array_state_diagram`          | base `indexed_sequence_diagram` modes `array_state`, `sliding_window`, `two_pointer`, `binary_search_range`, `sorting_pass` |
| `code_trace`                   | base `code_execution_panel` modes `code_walkthrough_growing`, `code_execution_trace`, `loop_trace`, `recursive_execution` |
| `comparison_table`             | base `table_diagram` mode `comparison_table`                     |
| `state_change`                 | base `table_diagram` mode `variable_trace_table`                 |
| `formula_card`                 | base `formula_symbolic_expression` mode `formula_breakdown`     |
| `graph_chart`                  | base `coordinate_graph` modes `function_curve`, `scatter_plot`, `loss_curve`, `runtime_growth`, etc. |
| `spatial_diagram`              | base `geometric_diagram` modes — currently barely-implemented in legacy; v2 is the real arrival |
| `misconception`                | **role-level mode**, not a base type. Compiles as side-by-side panel inside the active base type. |
| `interactive_parameter`        | base `coordinate_graph` mode `function_curve` with adjustable parameter — defer; currently barely-used. |
| `step_flow`                    | **support visual** — kept. Renders directly. |
| `progressive_step_flow`        | support visual variant of `step_flow` — kept. |
| `causal_chain`                 | support visual variant of `step_flow` — kept. |
| `path_progress`                | **support visual** (roadmap cards only) — kept. |
| `practice_feedback`            | **support visual** — kept; structurally identical, renamed in the ontology. |
| `source_annotation`            | **support visual** — kept. |
| `topic_snapshot`               | **support visual** (low-cost intro mode) — kept. |
| `edge_case_snapshot`           | **role**, not a base type. Renders as the topic's base type with a boundary state. |
| `concept_snapshot`             | base `node_link_diagram` mode `tree_hierarchy` with anatomical labels. |

The 12 base types add: `grid_matrix_diagram` (DP tables, adjacency matrix, K-maps), `memory_layout_diagram` (stack/heap, pointer rendering), `timeline_sequence_interaction` (protocol sequence diagrams), `set_region_diagram` (Venn / probability regions), `image_real_world_illustration` (analogy/intuition prompts).

---

## 3. Target architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────────┐
│ Topic classifier    │    │ Lesson generation   │    │ Visual compilation +    │
│ (LLM call 1)        │    │ (LLM call 2)        │    │ interactivity+transition│
│                     │    │                     │    │ emission (pure backend) │
│ Sets:               │    │ Outputs:            │    │                         │
│  topic_type         │───▶│  cards[] (intent    │───▶│ Inputs:                 │
│  visual_domain      │    │   only, no render)  │    │  intents + plans        │
│  visual_mode_hint   │    │  worked_examples[]  │    │                         │
│                     │    │   (plans)           │    │ Outputs:                │
└─────────────────────┘    └─────────────────────┘    │  visual_models[]        │
                                                       │   .frames[].state       │
                                                       │   .frames[].selectable  │
                                                       │   .frames[].transitions │
                                                       │  render_steps[]         │
                                                       └──────────┬──────────────┘
                                                                  │
                                                                  ▼
                                              ┌──────────────────────────────────┐
                                              │ Frontend (v2 page)               │
                                              │                                  │
                                              │ for each step:                   │
                                              │   model = visual_models[id]      │
                                              │   <VisualRenderer                │
                                              │     model={model}                │
                                              │     frameIndex={step.frame_idx}  │
                                              │     onElementClick={openChat}    │
                                              │     onAdvance={animateFrame}/>   │
                                              │                                  │
                                              │ <TransitionLayer> diff frames    │
                                              │ <InteractivityLayer> clickable   │
                                              │ <ChatSidebar visual_context={…}> │
                                              └──────────────────────────────────┘
```

Key invariants:

- **LLM never writes render data.** Every node, edge, table cell, frame is computed by the backend compiler.
- **One frame per RenderStep.** No "frontend picks the best of several visuals."
- **Worked-example cards share a base visual.** The compiler deep-copies the base into each frame and applies overlays.
- **Static-preview visuals are a degenerate 1-frame VisualModel.**
- **Support visuals bypass compilation.**
- **Every renderable element has a stable, addressable `element_id`** that persists across frames. Transitions animate `element_id` → `element_id`. Click-to-ask references `element_id`.
- **Transitions are explicit, not inferred.** Each frame carries a `transitions[]` list describing what changed from the prior frame. The renderer animates from those specs; no diffing in the browser.

---

## 4. Data contracts

All types below live in `backend/venv/app/schemas/visual_v2.py` (Python TypedDicts) and `frontend/lib/visual_v2_types.ts` (TS mirrors).

### 4.1 VisualIntent — what the LLM emits per card

```python
class VisualIntent(TypedDict):
    base_type: str           # one of BASE_VISUAL_TYPES or SUPPORT_VISUALS
    mode: str                # one of MODES_BY_BASE_TYPE[base_type]
    description: str         # plain-English scene/state storyboard
    purpose: str             # one sentence: what the learner should UNDERSTAND
    static_or_dynamic: Literal["static", "dynamic"]
```

### 4.2 WorkedExamplePlan — universal across all visual types

```python
class WorkedExamplePlan(TypedDict):
    id: str
    visual_intent: VisualIntent
    problem_setup: str
    terminal_state: str
    base_state: dict[str, Any]            # base type-specific structure
    steps: list[WorkedExampleStep]


class WorkedExampleStep(TypedDict):
    step_number: int
    action: str
    reason: str
    text_points: list[str]
    state_after: dict[str, Any]           # base type-specific overlay
    transition_hints: list[TransitionHint] # optional: LLM-provided ordering hints
                                          # e.g. "compute m before moving l"
```

The shape of `base_state` and `state_after` depends on `base_type`. Each compiler defines its own state schema (see Section 6).

### 4.3 VisualModel — what the backend compiler produces

```python
class VisualModel(TypedDict):
    id: str
    base_type: str
    mode: str
    base: dict[str, Any]                  # compiled base structure
    frames: list[VisualFrame]
    # Catalog of all element IDs that appear in any frame.
    # Used by the frontend to render persistent click affordance
    # and by accessibility for keyboard navigation.
    element_catalog: list[ElementCatalogEntry]


class VisualFrame(TypedDict):
    index: int
    state: dict[str, Any]                 # overlay over base
    highlights: dict[str, Any]            # active node/edge/cell/line
    annotations: list[FrameAnnotation]    # learner-facing callouts
    selectable_elements: list[SelectableElement]   # what's clickable on THIS frame
    transitions: list[Transition]         # how this frame arrives from the previous
                                          # (empty on frame 0)


class FrameAnnotation(TypedDict):
    id: str
    text: str
    attached_to_element_id: str | None    # render near this element if set
    appears_in_frame: int                 # for staggered annotation entry
```

### 4.4 RenderStep — the frontend's consumption format

```python
class RenderStep(TypedDict):
    id: str
    card_id: str
    title: str
    points: list[str]
    role: str                             # CardRole
    visual_model_id: str | None           # None for text-only cards
    frame_index: int | None
    code_model_id: str | None             # secondary code panel alongside main visual
    code_frame_index: int | None
    support_visual: SupportVisualPayload | None
    # When True, the frontend animates from the previous step's frame_index
    # to this step's frame_index using the destination frame's transitions[].
    animate_into: bool
    notes: str                            # was visual_focus.attention_note
```

### 4.5 LessonV2 — the full lesson contract

```python
class LessonV2(TypedDict):
    lesson_version: int                   # 2
    title: str
    topic_summary: str
    estimated_minutes: int
    visual_models: list[VisualModel]
    render_steps: list[RenderStep]
    practice_questions: list[PracticeQuestion]
    source_chunk_ids: list[str]
    source_summary: str
    metadata: LessonMetadata
```

No `lesson_cards[]`. The render_steps + visual_models combination replaces it.

### 4.6 SelectableElement — the click-to-ask primitive

Every renderable element that should be clickable. The compiler emits these per frame (since "clickable" may depend on state — e.g., an unvisited node may or may not be clickable depending on policy).

```python
class SelectableElement(TypedDict):
    element_id: str                       # stable across frames for the same conceptual element
    element_type: str                     # "node" | "edge" | "cell" | "pointer" | "code_line"
                                          # | "code_variable" | "subexpression" | "row" | "column"
                                          # | "axis_label" | "curve_segment" | "shaded_region"
                                          # | "message" | "actor_lane" | "memory_frame" | etc.
    semantic_label: str                   # human-readable: "node 30 (current node, being visited)"
    bounds: ElementBounds                 # bounding box in renderer-local coords
    aria_label: str                       # accessibility label
    keyboard_index: int                   # tab order
    payload: dict[str, Any]               # element_type-specific snapshot for QA context


class ElementBounds(TypedDict):
    x: float
    y: float
    width: float
    height: float
```

### 4.7 Transition — frame-to-frame change descriptions

Each frame's `transitions[]` describes what moved/changed from the prior frame. The frontend transition layer interprets these to animate.

```python
class Transition(TypedDict):
    kind: str                             # "move" | "fade_in" | "fade_out" | "style_change"
                                          # | "value_change" | "swap" | "highlight_pulse"
                                          # | "stagger_group" | "appear" | "disappear"
    target_element_id: str
    duration_ms: int                      # default 300
    delay_ms: int                         # default 0
    easing: str                           # "ease" | "ease_in_out" | "linear" | "spring"
    spec: dict[str, Any]                  # kind-specific payload


# Examples of `spec` per kind:
# move:          { from: {x: float, y: float}, to: {x: float, y: float} }
# style_change:  { from_style: str, to_style: str }
# value_change:  { from_value: str, to_value: str }  # e.g. variable trace
# swap:          { other_element_id: str }           # both elements swap positions
# highlight_pulse: { color: str, cycles: int }
# stagger_group: { group_element_ids: list[str], stagger_ms: int }
```

**Coordinate stability invariant**: if `element_id` X has bounds `(x1, y1)` in frame N and bounds `(x2, y2)` in frame N+1, then frame N+1 must include a `move` transition for X from `(x1, y1)` to `(x2, y2)`. The compiler enforces this; the renderer trusts it.

### 4.8 VisualContextPayload — what the chat sidebar receives

When a learner clicks a `SelectableElement`, this is sent to the QA backend.

```python
class VisualContextPayload(TypedDict):
    visual_model_id: str
    frame_index: int
    element: SelectableElement            # the clicked element
    surrounding_state: dict[str, Any]     # frame.state at click time
    base_type: str
    mode: str
    formatted_context: str                # backend-generated NL summary
                                          # "Learner clicked node 30 (current at step 2 of
                                          #  inorder traversal). Its children are 20 and 40."
```

The QA backend's `VisualContextFormatter` produces `formatted_context` from the rest of the payload. The chat LLM receives `formatted_context` as a prefix to the learner's question.

### 4.9 ElementCatalogEntry — model-level element registry

The model carries a catalog of every element_id that appears in any frame, so the frontend can pre-allocate render nodes and avoid mount/unmount churn during transitions.

```python
class ElementCatalogEntry(TypedDict):
    element_id: str
    element_type: str
    first_frame: int                      # frame index where this element first appears
    last_frame: int                       # frame index where this element last appears (-1 = all)
    initial_bounds: ElementBounds         # used for first render
```

### 4.10 SupportVisualPayload — what support visuals carry

Support visuals don't go through compilation; the orchestrator wraps the intent in a thin payload the frontend renders directly. They can still be clickable but use a simpler element model.

```python
class SupportVisualPayload(TypedDict):
    support_type: str                     # one of SUPPORT_VISUALS
    mode: str
    data: dict[str, Any]                  # support-type-specific
    selectable_elements: list[SelectableElement]
```

---

## 5. File structure (parallel v2 namespace)

Nothing in this list overwrites or modifies existing files. The v2 system imports from legacy where useful but never the other way around.

### Backend

```
backend/venv/app/
├── core/
│   ├── visual_ontology_v2.py            ✓ exists (Phase 0)
│   ├── course_blueprints_v2.py          new — role+domain → behavior
│   └── (existing course_blueprints.py)  unchanged
├── schemas/
│   ├── visual_v2.py                     new — TypedDicts (Phase 0)
│   └── (existing schemas)               unchanged
├── services/
│   ├── llm_schemas_v2.py                new — strict JSON schema (Phase 1)
│   ├── topic_classifier_v2.py           new — adds visual_domain field (Phase 3)
│   ├── visual_compilers/
│   │   ├── __init__.py                  new — registry + dispatch (Phase 0)
│   │   ├── base.py                      new — abstract Compiler interface (Phase 0)
│   │   ├── node_link.py                 new — full compiler (Phase 2)
│   │   ├── code_execution.py            new — port from code_trace logic (Phase 2)
│   │   ├── indexed_sequence.py          new — port from array_state logic (Phase 2)
│   │   ├── formula.py                   new (Phase 6)
│   │   ├── table.py                     new (Phase 6)
│   │   ├── grid_matrix.py               new (Phase 6)
│   │   ├── coordinate_graph.py          new (Phase 6)
│   │   ├── memory_layout.py             new (Phase 6)
│   │   ├── geometric.py                 new (Phase 6)
│   │   ├── timeline_sequence.py         new (Phase 6)
│   │   ├── set_region.py                new (Phase 6)
│   │   └── image_illustration.py        new (Phase 6)
│   ├── visual_context_formatter.py      new — VisualContextPayload → NL prefix (Phase 4.5)
│   ├── visual_validators_v2.py          new — VisualIntentValidator etc. (Phase 5)
│   ├── lean_lesson_generator_v2.py      new — orchestrator (Phase 2)
│   └── (existing services)              unchanged
├── prompts/
│   ├── lean_lesson_prompt_v2.py         new — intent-only prompt (Phase 3)
│   └── (existing prompts)               unchanged
└── api/routes/
    ├── lessons_v2.py                    new — v2 lesson endpoints (Phase 2)
    └── visual_qa_v2.py                  new — chat with visual_context (Phase 4.5)
```

### Frontend

```
frontend/
├── app/
│   ├── study-paths/[studyPathId]/learn-v2/
│   │   └── page.tsx                     new — reads RenderStep + VisualModel (Phase 4)
│   └── (existing app routes)            unchanged
├── components/visuals_v2/                new
│   ├── VisualRenderer.tsx               dispatches by base_type (Phase 4)
│   ├── InteractivityLayer.tsx           new — click affordance + keyboard nav (Phase 4.5)
│   ├── TransitionLayer.tsx              new — animation engine (Phase 4.5)
│   ├── VisualContextChip.tsx            new — preview in chat sidebar (Phase 4.5)
│   ├── NodeLinkVisual.tsx               wraps existing renderer (Phase 4)
│   ├── CodeExecutionPanel.tsx           wraps existing renderer (Phase 4)
│   ├── IndexedSequenceVisual.tsx        wraps existing renderer (Phase 4)
│   ├── TableVisual.tsx                  wraps existing renderer (Phase 4)
│   ├── FormulaVisual.tsx                wraps existing renderer (Phase 4)
│   ├── GridMatrixVisual.tsx             new (Phase 6)
│   ├── CoordinateGraphVisual.tsx        new (Phase 6)
│   ├── MemoryLayoutVisual.tsx           new (Phase 6+)
│   ├── GeometricVisual.tsx              new (Phase 6+)
│   ├── TimelineSequenceVisual.tsx       new (Phase 6+)
│   ├── SetRegionVisual.tsx              new (Phase 6+)
│   ├── ImageIllustrationVisual.tsx      new (Phase 6+)
│   └── support/
│       ├── StepFlow.tsx                 new — preserves today's look (Phase 4)
│       ├── PracticeFeedback.tsx         new (Phase 4)
│       └── PathProgress.tsx             new (Phase 4)
└── lib/
    ├── visual_v2_types.ts               new — mirrors visual_v2.py (Phase 0)
    └── visual_v2_transitions.ts         new — animation primitives (Phase 4.5)
```

### What stays untouched

- All files under `backend/venv/app/` except the new ones listed.
- All files under `frontend/` except `learn-v2/` and `components/visuals_v2/`.
- The existing `/study-paths/[id]/learn` route remains the default until cutover.
- The existing API endpoints continue to serve the legacy lesson format.
- The existing chat/QA backend stays for legacy text-highlight flow; v2 adds a parallel endpoint that accepts visual_context.

---

## 6. Per-compiler responsibility

Each compiler implements the same interface but has its own `base_state`, `state_after`, `selectable_elements()`, and `transitions()` shape.

### 6.1 Universal compiler interface

```python
class VisualCompiler(Protocol):
    base_type: str

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        """Produce a VisualModel. For static visuals: 1 frame. For
        worked examples: N frames keyed to plan.steps."""

    def selectable_elements(
        self,
        frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
    ) -> list[SelectableElement]:
        """Which elements are clickable on a given frame. Called per frame."""

    def transitions(
        self,
        prev_frame_state: dict[str, Any] | None,
        curr_frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
        hints: list[TransitionHint],
    ) -> list[Transition]:
        """Compute transitions from prev → curr. Called per frame."""
```

`CompileContext` includes `topic_hint`, `source_chunks_excerpt`, and references to other already-compiled models on the same lesson so cross-card consistency is possible (e.g., the worked example reuses the background card's structure).

### 6.2 NodeLinkCompiler

State shape:
- `base.nodes: list[NodeV2]` — each has `id`, `label`, `relation`, `x`, `y`, mode-specific fields
- `base.edges: list[EdgeV2]` — each has `from`, `to`, `label`, `style`, mode-specific fields
- `state_after.active_node`, `.completed_nodes`, `.node_state_map`, `.active_edge_from`, `.active_edge_to`, `.completed_edges`, `.runtime_state` (call_stack, output, frontier, variables)

**Selectable elements**: every node, every edge, every edge label, items in call_stack/output/frontier panels. `element_id` for nodes = node id; for edges = `"from→to"`; for stack items = `"stack[i]"`.

**Transitions**: node state changes (`unvisited → current` → `style_change` + `highlight_pulse`), edge style changes (`solid → active` → `style_change`), call stack push/pop (`appear` / `disappear` with stagger), output list append (`appear`).

Implementation: lift `_materialize_node_link_worked_example_to_cards` from legacy. Synthesizer pattern stays as fallback.

### 6.3 CodeExecutionCompiler

Modes: `code_walkthrough_growing` (visible_until_line increases per frame) vs `code_execution_trace` (full code from frame 1, highlight moves).

State shape:
- `base.code: str`, `base.language: str`, `base.line_count: int`
- `state_after.visible_until_line: int`, `.highlight_lines: tuple[int, int]`, `.variables: list[VariableTrace]`, `.call_stack: list[str]`, `.output: list[str]`

**Selectable elements**: each code line, each variable in trace panel, each call stack frame, output lines.

**Transitions**: line highlight `move` (slide indicator from old range to new range), variable `value_change` (number flips), call stack `appear`/`disappear`, output line `appear`.

Implementation: lift `_accumulate_code_walkthrough_visuals` + `_sync_coding_worked_examples_to_final_code` logic. Add explicit growing/execution-mode dispatch.

### 6.4 IndexedSequenceCompiler

State shape:
- `base.values: list[str]`, `base.indices: list[int]`
- `state_after.pointers: list[Pointer]` (each pointer has stable `pointer_id` like "l", "r", "m"), `.ranges: list[Range]`, `.highlighted_cells: list[int]`, `.swapped_cells: tuple[int, int] | None`, `.sorted_prefix_end: int | None`

**Selectable elements**: each cell, each pointer (`l`, `r`, `m`), each range, the sorted prefix region.

**Transitions**: pointer `move` (this is the binary-search example — `l` slides from index 0 to index `m+1`), range expansion/contraction (`move` on both endpoints), cell swap (`swap` kind — both cells exchange positions), highlight pulse on the active comparison.

Implementation: lift `_overlay_binary_search_completion`, `_overlay_two_pointer_completion`, `_overlay_sliding_window_completion`, `_overlay_quicksort_completion`, `_overlay_merge_sort_completion`. Wrap under one dispatcher keyed by `mode`.

**Critical**: each pointer needs a stable `pointer_id` the LLM (and synthesizer) commits to. Without that, `l` in frame 2 is a different element from `l` in frame 1 and transitions become teleports.

### 6.5 FormulaCompiler

State shape:
- `base.expression: str` (LaTeX or symbolic form), `base.symbols: list[SymbolDefinition]`
- `state_after.active_subexpression_span: (int, int)`, `.substitution: dict[str, str]`, `.transformed_expression: str`, `.equivalence_chain: list[str]`

**Selectable elements**: each symbol, each subexpression span, each equation in the equivalence chain.

**Transitions**: subexpression highlight `move` (the "active part" slides), substitution `value_change` (variable becomes its value with a flip), equivalence step `fade_in` (next equation slides in below).

### 6.6 TableCompiler

State shape:
- `base.columns: list[str]`, `base.rows: list[list[str]]`
- `state_after.active_row: int | None`, `.active_cell: (int, int) | None`, `.changed_cells: list[(int, int)]`

**Selectable elements**: each cell (`cell[r][c]`), each row header, each column header.

**Transitions**: active row `move` (highlight bar slides down), cell `value_change` (number flips), new row `appear` (slides in from below).

### 6.7 GridMatrixCompiler

State shape:
- `base.cells: list[list[str]]`, `base.row_labels: list[str]`, `base.column_labels: list[str]`
- `state_after.active_cell: (int, int)`, `.completed_cells: set[(int, int)]`, `.dependency_arrows: list[(start, end)]`, `.highlighted_row: int | None`, `.highlighted_column: int | None`

**Selectable elements**: each cell, each row label, each column label, each dependency arrow.

**Transitions**: active cell `move`, dependency arrows `appear` (drawn left-to-right), cell `value_change` when DP cell fills in.

### 6.8 CoordinateGraphCompiler

State shape:
- `base.axes`, `base.curves: list[Curve]`, `base.points: list[Point]`
- `state_after.active_point`, `.shaded_region`, `.tangent_secant_line`, `.active_curve_segment`

**Selectable elements**: each plotted point, each curve, each axis label, the shaded region, tangent/secant line.

**Transitions**: point `move` (rare; usually static), shaded region `value_change` (morphing), tangent line `move` (slide along curve).

### 6.9 MemoryLayoutCompiler (Phase 6+)

**Selectable elements**: each stack frame, each heap object, each pointer arrow, each variable binding.

**Transitions**: new stack frame `appear` (slides in from above), popped frame `disappear`, pointer `move` (arrow re-attaches), heap object allocation `appear`.

### 6.10 GeometricCompiler (Phase 6+)

**Selectable elements**: each shape, side, angle, region.

**Transitions**: side measurement `value_change`, region shading `fade_in`, projection line `move`.

### 6.11 TimelineSequenceCompiler (Phase 6+)

**Selectable elements**: each message, each actor lane, each time tick.

**Transitions**: message arrow `appear` (animated draw from sender lane to receiver lane), actor state `style_change` (blocked, waiting).

### 6.12 SetRegionCompiler (Phase 6+)

**Selectable elements**: each set, each region (including intersections), each element placed in regions.

**Transitions**: region shading `fade_in` / `fade_out`, element `move` (slides from outside into a region).

### 6.13 ImageIllustrationCompiler (Phase 6+)

Selectable elements + transitions usually minimal (static). May annotate hotspots.

### 6.14 Support visual handling (NOT a compiler)

Support visuals (`step_flow`, `practice_feedback`, `path_progress`, `source_annotation`, `topic_snapshot`) bypass the compiler registry. The generator wraps the intent in a `SupportVisualPayload` that the frontend's `<VisualRenderer>` dispatches to existing renderers directly. They still emit `selectable_elements` (e.g., each step in a step_flow is clickable for "explain this step") but typically have no transitions.

---

## 7. Phased migration plan

Each phase ships something usable. No phase requires the next phase to be useful.

### Phase 0 — ontology + schemas + scaffolding (1-2 days)

- ✅ `visual_ontology_v2.py`
- `schemas/visual_v2.py` — TypedDicts including `SelectableElement`, `Transition`, `VisualContextPayload`, `ElementCatalogEntry`
- `lib/visual_v2_types.ts` — TS mirrors
- `visual_compilers/__init__.py` + `base.py` — empty registry + abstract Compiler interface
- No behavioral change; nothing imports the v2 modules at runtime yet.

### Phase 1 — universal worked_example_plan schema (1-2 days)

- Define unified `WorkedExamplePlan` TypedDict in `visual_v2.py`.
- Add `llm_schemas_v2.py` that emits the unified plan schema + the full `LessonV2` JSON schema.
- The existing two pilots in `llm_client.py` stay unchanged for legacy compatibility.

### Phase 2 — orchestrator with 3 compilers + interactivity emission (3-5 days)

Build:
- `lean_lesson_generator_v2.py` — takes lesson_v2 JSON, runs compilers per intent, produces `LessonV2` (VisualModel[] + RenderStep[]).
- `visual_compilers/node_link.py` — full port from current materializer. Emits `selectable_elements` and `transitions` per frame. The synthesizer pattern moves here as fallback.
- `visual_compilers/code_execution.py` — lift growing/execution-mode logic.
- `visual_compilers/indexed_sequence.py` — lift array overlays.
- Stub compilers for the other 9 base types that return a 1-frame model with a placeholder message.

Wire to a v2-only API route `POST /lessons-v2/generate-from-topic`. The default lesson route still uses legacy.

### Phase 3 — `lean_lesson_prompt_v2.py` + `topic_classifier_v2.py` (2-3 days)

- New prompt that asks ONLY for intent + worked_example plans. No render data fields.
- Topic classifier adds `visual_domain` field.
- The LLM can still override base_type per card if it has a reason.

### Phase 4 — `learn-v2/page.tsx` frontend (3-5 days)

- New route `/study-paths/[id]/learn-v2`.
- Reads the lesson_v2 contract.
- Reuses existing visual components (`VisualNodeLinkDiagram`, `VisualCodeBlock`, etc.) as concrete renderers — wrapped in v2 components.
- New components only for new base types where no renderer exists today.
- LearningCard equivalent is much smaller — no resolution logic.
- Feature flag routes test topics to learn-v2.
- **Interactivity not yet wired** (snap-changes only). That's Phase 4.5.

### Phase 4.5 — interactivity layer: click-to-ask + animated transitions (3-5 days)

This is the dedicated interactivity phase. Splits cleanly from Phase 4 so the basic v2 page can ship and be tested first.

**Click-to-ask:**
- `<InteractivityLayer>` component: wraps each renderer, projects `SelectableElement.bounds` into clickable SVG `<g>` / DOM zones with hover affordance (cursor change, light ring, tooltip "Ask about this").
- Click handler calls a new `useVisualChat(payload: VisualContextPayload)` hook → opens chat sidebar with the structured context.
- Backend route `POST /lessons-v2/visual-qa` accepts `VisualContextPayload`. The `VisualContextFormatter` service produces the natural-language prefix injected into the chat LLM call.
- `<VisualContextChip>` in chat sidebar shows "Asking about: [Node 30, current at step 2]" with the element snapshot.
- Selection persists during the chat thread; deselection on chat dismiss.
- Keyboard nav: Tab cycles through `selectable_elements`, Enter activates.
- ARIA labels = `SelectableElement.aria_label`.

**Animated transitions:**
- `<TransitionLayer>` component: reads `frame.transitions[]`, applies them as Framer Motion animations to the SVG elements rendered by the underlying visual component.
- Animation engine maps `Transition.kind` to motion semantics:
  - `move`: CSS transform / Framer `<motion.g animate={{x, y}}>`
  - `fade_in` / `fade_out`: opacity 0 ↔ 1
  - `style_change`: fill/stroke color transition
  - `value_change`: text content fade-swap
  - `swap`: two elements exchange positions via Framer layout animation
  - `highlight_pulse`: scale + ring opacity pulse
  - `stagger_group`: schedule child transitions with stagger
- Animation state machine: `idle → animating → settled`. While `animating`, Next button is debounced. Replay button restarts the current step's transition.
- `prefers-reduced-motion` handling: skip animations, snap to final state immediately. Click affordance unaffected.
- Performance budget: target 60fps for ≤30 animated elements; degrade gracefully for larger structures (skip non-essential animations, batch updates).
- New dependency: `framer-motion` (~30KB gz). Already React-compatible; SVG-friendly.

**Auto-play mode:**
- Once transitions exist, "play through worked example" is a natural affordance. Each step's transition + a pause for reading. Spec defers full UI to Phase 4.5+ stretch.

### Phase 5 — validators (1-2 days)

- `VisualIntentValidator`, `WorkedExamplePlanValidator`, `VisualModelValidator`, `RenderStepValidator`.
- Plus: `SelectableElementValidator` (every element_id stable across frames), `TransitionValidator` (every transition's target_element_id exists in the model's element_catalog), `CoordinateStabilityValidator` (no implicit teleports).

Validators run in the orchestrator. Failures log + degrade gracefully (drop the visual, render text-only, snap-change instead of animate).

### Phase 6 — additional compilers (5-7 days each, prioritized by topic demand)

Order: `grid_matrix` → `formula` → `table` → `coordinate_graph` → `memory_layout` → `set_region` → `timeline_sequence` → `geometric` → `image_illustration`.

Each compiler ships with its own `selectable_elements()` + `transitions()` implementation from day one — no retrofitting interactivity later.

### Phase 7 — cutover (1-2 days)

- Default new lesson generation to the v2 pipeline.
- Legacy route stays for an arbitrary grace period.
- The legacy repair functions are no longer in the active path for new lessons.

### Phase 8 — legacy decommission (deferred)

- After 1+ months stable, remove legacy generator, prompt, materializers, learn/page.tsx.

---

## 8. LLM compliance strategy

Defenses, in priority order:

1. **Strengthened prompt** — already partially done. Must-emit lists by topic type.
2. **Schema-level forcing** — when topic_type pins the base_type, make `worked_example_plan` non-nullable in strict schema.
3. **Backend synthesizer fallback** — generalize the synthesizer pattern per compiler. We have a working node_link version.
4. **Validator-driven retry** — when validator detects an invalid plan, retry the LLM call with a more directive system message. Cap at 1 retry per lesson.

**Interactivity-specific compliance:**

5. **Stable element identity in LLM output** — the LLM must commit to element_ids (node ids, pointer names like `l`/`r`/`m`, variable names) ONCE in the base state and reuse them in every step's `state_after`. The prompt enforces this; the compiler validates and rejects/repairs on mismatch.
6. **Transition hints in plan steps** — for cases where default frame diffing produces confusing order (binary search: m computed before l moves), the plan emits explicit `transition_hints` the compiler reads. Defaults work for simple cases; hints handle the nuanced ones.

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| LLM ignores intent-only contract and emits render data in unused fields | Strict schema: `additionalProperties: false` |
| LLM picks the wrong `(base_type, mode)` | Topic classifier sets `visual_domain` first; LLM choice is constrained |
| Compiler matrix grows faster than topic demand | Phase 6 explicitly defers; stub compilers render placeholder |
| Legacy renderers get out of sync | V2 wraps existing renderers; doesn't modify them |
| Migration takes too long, parallel maintenance burden grows | Phase 7 cutover after Phase 4.5 |
| Tests don't exist for either pipeline | Snapshot test per compiler before cutover |
| **LLM emits unstable element_ids across steps** (l in step 1 ≠ l in step 2) | Synthesizer normalizes ids; validator catches mismatches; compiler uses LLM ids as hints only |
| **Transitions feel janky on slow devices / large structures** | Performance budget per visual; reduced-motion fallback; element count cap per visual |
| **Click-to-ask context too vague for chat LLM to answer well** | `VisualContextFormatter` produces rich NL prefix including frame state + element role + surrounding context |
| **Mobile users can't easily click small elements** | `bounds.width/height` minimums enforced by compiler; mobile-specific minimum 44px tap target |
| **Motion sickness / accessibility for animations** | `prefers-reduced-motion` honored; explicit "disable animations" user pref later |
| **Stagger / sequencing of transitions confuses learner** | `transition_hints` from LLM + opinionated compiler defaults; replay button available |
| **Element bounds become stale after window resize** | Bounds are recomputed by frontend on resize; backend bounds are canonical positions in 0-100 unit coords |
| **Two learners click the same element and ask different things** | Chat is per-learner; visual selection state is local |

---

## 10. Open questions

1. **Hard cut at API boundary or transitional dual-format?** → Hard cut. V2 frontend reads v2 endpoint; legacy stays on legacy.
2. **Where does practice question logic live in v2?** → `practice_questions` as a separate list; `RenderStep.role="practice"` references practice_question_index.
3. **Image illustrations — where do images come from?** → Defer to Phase 6+.
4. **URL for the v2 lesson route?** → `/study-paths/[id]/learn-v2` during migration; swap to `/learn` at cutover.
5. **`visual_focus` overlay subsumed?** → Yes. `attention_note` → `RenderStep.notes`. `active_nodes`/`highlight_path` → `frame.highlights`.
6. **Interactivity: should clicks be allowed during animations?** → No. Animations should be brief enough (<500ms) that "wait then click" is fine. State machine enforces.
7. **Should the visual_context_payload be sticky across chat turns within the same QA thread?** → Yes. First click attaches context; subsequent messages in the thread inherit it until the learner navigates away from the card.
8. **Should learners be able to pin a `SelectableElement` so it stays highlighted while exploring others?** → Defer. v1 behavior: single selection only.
9. **Transitions for static-preview visuals (background card)?** → No. Static visuals have a single frame; nothing to transition.
10. **Replay button per step or per card?** → Per step. Replay re-runs `frame[step].transitions` against frame[step-1]'s state.

---

## 11. What already fits

- **`backend/venv/app/core/visual_ontology_v2.py`** — the 12 base types, modes, domains, support visuals, routing tables. Pure data; imports nothing at runtime.
- **`_synthesize_node_link_plan_from_lean_cards`** in `lean_lesson_generator.py` — the synthesizer pattern. Moves to `visual_compilers/node_link.py` as the "no plan provided" fallback.
- **Existing visual renderers in `learn/page.tsx`** — `VisualNodeLinkDiagram`, `VisualCodeBlock`, `VisualArrayStateDiagram`, etc. The v2 page wraps these unchanged; interactivity + transitions overlay on top via `<InteractivityLayer>` + `<TransitionLayer>`.

Everything else listed in Section 5 needs to be built.

---

## 12. Recommended next action

Phase 0 + Phase 1 land foundation files with no behavioral risk. Phase 2 proves the pipeline end-to-end for node_link topics (the case we just spent hours debugging). Phase 4.5 adds the two new capabilities (click-to-ask + transitions) on top of working basic rendering.

Implementation begins now with Phase 0 and proceeds through Phase 2's node_link compiler.
