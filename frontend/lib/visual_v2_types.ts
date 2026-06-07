/**
 * Visual System V2 — TypeScript types.
 *
 * Mirrors backend/venv/app/schemas/visual_v2.py. Keep in sync.
 *
 * Coexists with all legacy types. The v2 frontend route imports from here.
 */

// ===========================================================================
// CORE TYPES
// ===========================================================================

export type ElementBounds = {
  x: number;
  y: number;
  width: number;
  height: number;
};

/**
 * Valid element_type values. Each compiler emits a subset.
 */
export type ElementType =
  | "node"
  | "edge"
  | "edge_label"
  | "stack_item"
  | "output_item"
  | "frontier_item"
  | "cell"
  | "pointer"
  | "range"
  | "code_line"
  | "code_variable"
  | "code_frame"
  | "subexpression"
  | "symbol_definition"
  | "row"
  | "column"
  | "row_header"
  | "column_header"
  | "axis_label"
  | "curve_segment"
  | "plotted_point"
  | "shaded_region"
  | "tangent_line"
  | "shape"
  | "side"
  | "angle"
  | "measurement_label"
  | "message"
  | "actor_lane"
  | "time_tick"
  | "memory_frame"
  | "heap_object"
  | "pointer_arrow"
  | "variable_binding"
  | "set"
  | "region"
  | "element_in_region"
  | "hotspot"
  | "support_step";

/**
 * A clickable element. element_id is stable across frames for the same
 * conceptual element (node "30", pointer "l", code line 5, etc.).
 */
export type SelectableElement = {
  element_id: string;
  element_type: ElementType;
  semantic_label: string;
  bounds: ElementBounds;
  aria_label: string;
  keyboard_index: number;
  payload: Record<string, unknown>;
};

// ===========================================================================
// TRANSITIONS
// ===========================================================================

export type TransitionKind =
  | "move"
  | "fade_in"
  | "fade_out"
  | "appear"
  | "disappear"
  | "style_change"
  | "value_change"
  | "swap"
  | "highlight_pulse"
  | "stagger_group";

export type TransitionEasing =
  | "ease"
  | "ease_in"
  | "ease_out"
  | "ease_in_out"
  | "linear"
  | "spring";

export type Transition = {
  kind: TransitionKind;
  target_element_id: string;
  duration_ms: number;
  delay_ms: number;
  easing: TransitionEasing;
  spec: Record<string, unknown>;
};

export type TransitionHint = {
  description: string;
  sequence: string[];
  stagger_ms: number;
};

// ===========================================================================
// FRAMES + ANNOTATIONS
// ===========================================================================

export type FrameAnnotation = {
  id: string;
  text: string;
  attached_to_element_id: string | null;
  appears_in_frame: number;
};

export type VisualFrame = {
  index: number;
  state: Record<string, unknown>;
  highlights: Record<string, unknown>;
  annotations: FrameAnnotation[];
  selectable_elements: SelectableElement[];
  transitions: Transition[];
};

// ===========================================================================
// CATALOG
// ===========================================================================

export type ElementCatalogEntry = {
  element_id: string;
  element_type: ElementType;
  first_frame: number;
  last_frame: number;
  initial_bounds: ElementBounds;
};

// ===========================================================================
// VISUAL INTENT + VISUAL MODEL
// ===========================================================================

export type VisualIntent = {
  base_type: string;
  mode: string;
  description: string;
  purpose: string;
  static_or_dynamic: "static" | "dynamic";
};

export type VisualModel = {
  id: string;
  base_type: string;
  mode: string;
  base: Record<string, unknown>;
  frames: VisualFrame[];
  element_catalog: ElementCatalogEntry[];
};

// ===========================================================================
// WORKED EXAMPLE PLAN
// ===========================================================================

export type WorkedExampleStep = {
  step_number: number;
  action: string;
  reason: string;
  text_points: string[];
  state_after: Record<string, unknown>;
  transition_hints: TransitionHint[];
};

export type WorkedExamplePlan = {
  id: string;
  visual_intent: VisualIntent;
  problem_setup: string;
  terminal_state: string;
  base_state: Record<string, unknown>;
  steps: WorkedExampleStep[];
};

// ===========================================================================
// SUPPORT VISUALS
// ===========================================================================

export type SupportVisualPayload = {
  support_type: string;
  mode: string;
  data: Record<string, unknown>;
  selectable_elements: SelectableElement[];
};

// ===========================================================================
// RENDER STEP + LESSON V2
// ===========================================================================

export type CardRole =
  | "background"
  | "components_terms"
  | "process"
  | "worked_example"
  | "code_walkthrough"
  | "edge_case"
  | "comparison"
  | "practice"
  | "takeaway";

export type RenderStep = {
  id: string;
  card_id: string;
  title: string;
  points: string[];
  role: CardRole;
  visual_model_id: string | null;
  frame_index: number | null;
  code_model_id: string | null;
  code_frame_index: number | null;
  support_visual: SupportVisualPayload | null;
  animate_into: boolean;
  notes: string;
  // Set when role === "practice"; resolves to a question in
  // LessonV2.practice_questions[] by .id.
  practice_question_id?: string | null;
};

export type PracticeQuestion = {
  id: string;
  question_type: string;
  question_text: string;
  correct_answer: string;
  choices: string[];
  skill_target: string;
  concept_tested: string;
};

export type LessonMetadata = {
  starting_mode: string;
  estimated_state: string;
  adaptation_summary: string;
  teaching_strategy: string;
};

export type LessonV2 = {
  lesson_version: number;
  title: string;
  topic_summary: string;
  estimated_minutes: number;
  visual_models: VisualModel[];
  render_steps: RenderStep[];
  practice_questions: PracticeQuestion[];
  source_chunk_ids: string[];
  source_summary: string;
  metadata: LessonMetadata;
};

// ===========================================================================
// VISUAL CONTEXT PAYLOAD
// ===========================================================================

export type VisualContextPayload = {
  visual_model_id: string;
  frame_index: number;
  element: SelectableElement;
  surrounding_state: Record<string, unknown>;
  base_type: string;
  mode: string;
  formatted_context: string;
};
