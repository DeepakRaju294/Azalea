"""LLM schemas v2 — JSON schemas the LLM emits in the new pipeline.

The v2 schemas ask the LLM for INTENT ONLY (no render data fields like
visual_nodes, visual_edges, visual_array_values, etc.) plus per-card
worked_example plans where dynamic visuals are warranted.

These schemas are sent to OpenAI with `strict=False` (NOT strict mode).
Two fields are intentionally polymorphic and incompatible with strict
mode's "every property declared + additionalProperties=false" rule:

  - WorkedExamplePlan.base_state — shape varies by base_type
    (node_link: {nodes, edges}; indexed_sequence: {values,
    pointer_definitions}; code_execution: {code, language}; etc.)
  - WorkedExampleStep.state_after — same: per-base_type overlay shape

Both use additionalProperties=true so the LLM can put base_type-specific
content there. Backend validators (validate_lesson_v2 +
validate_worked_example_plan + validate_visual_model) catch real shape
issues that strict mode would have caught at output time.

All OTHER objects in this schema do follow strict-mode hygiene
(additionalProperties=false, every property declared in required,
nullable via type unions) so re-enabling strict mode would only require
making base_state + state_after JSON-encoded strings.

Coexists with the legacy schemas in llm_client.py. Nothing here modifies
the legacy schemas.
"""

from __future__ import annotations

from typing import Any

# ===========================================================================
# VISUAL INTENT — what the LLM emits per card
# ===========================================================================

VISUAL_INTENT_SCHEMA: dict[str, Any] = {
    "type": ["object", "null"],
    "description": (
        "What this card's visual is FOR. NO render data — that is the "
        "backend compiler's job. Set to null for purely textual cards "
        "(takeaway, some process cards)."
    ),
    "properties": {
        "base_type": {
            "type": "string",
            "description": (
                "One of the 12 base visual types OR one of the support "
                "visuals. Allowed values: 'coordinate_graph', "
                "'node_link_diagram', 'indexed_sequence_diagram', "
                "'grid_matrix_diagram', 'table_diagram', "
                "'memory_layout_diagram', 'code_execution_panel', "
                "'geometric_diagram', 'formula_symbolic_expression', "
                "'timeline_sequence_interaction', 'set_region_diagram', "
                "'image_real_world_illustration', 'step_flow', "
                "'practice_feedback', 'path_progress', 'source_annotation', "
                "'topic_snapshot'."
            ),
        },
        "mode": {
            "type": "string",
            "description": (
                "Subject-specific layout inside the base_type. E.g. for "
                "node_link_diagram: 'tree_hierarchy' | 'graph_network' | "
                "'state_machine' | 'circuit' | etc. Each base_type has its "
                "own valid mode set; see visual_ontology_v2.MODES_BY_BASE_TYPE."
            ),
        },
        "description": {
            "type": "string",
            "description": (
                "Plain-English scene/state storyboard. For a BST background "
                "card: 'BST with root 50, children 30 and 70, …'. For a "
                "binary search worked example: 'sorted array with l, m, r "
                "pointers; current state: l=0 r=6 m=3'."
            ),
        },
        "purpose": {
            "type": "string",
            "description": (
                "ONE sentence stating what the learner should UNDERSTAND "
                "from this visual. Banned verbs: 'shows', 'displays', "
                "'represents'. Use specific verbs like 'trace the order of', "
                "'predict the next visited', 'compare'."
            ),
        },
        "static_or_dynamic": {
            "type": "string",
            "enum": ["static", "dynamic"],
            "description": (
                "'static' for background, components_terms, edge_case, "
                "takeaway. 'dynamic' for worked_example, code_walkthrough."
            ),
        },
    },
    "required": [
        "base_type",
        "mode",
        "description",
        "purpose",
        "static_or_dynamic",
    ],
    "additionalProperties": False,
}


# ===========================================================================
# TRANSITION HINT — LLM-provided ordering hint for animations
# ===========================================================================

TRANSITION_HINT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Optional hint that overrides the compiler's default transition "
        "generation when the natural order matters. Example for binary "
        "search step where m is computed then l updates: "
        "{description: 'compute m, then move l', "
        " sequence: ['m', 'l'], stagger_ms: 200}."
    ),
    "properties": {
        "description": {"type": "string"},
        "sequence": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Element IDs in the order their transitions should fire. "
                "Empty array = use compiler default."
            ),
        },
        "stagger_ms": {
            "type": "integer",
            "description": "Delay between consecutive transitions. Default 150.",
        },
    },
    "required": ["description", "sequence", "stagger_ms"],
    "additionalProperties": False,
}


# ===========================================================================
# WORKED EXAMPLE PLAN — universal across all base_types
# ===========================================================================

WORKED_EXAMPLE_STEP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "One step in the worked example. state_after's shape depends on "
        "the visual_intent.base_type — see the base-type-specific notes "
        "in the prompt for what fields it should carry."
    ),
    "properties": {
        "step_number": {"type": "integer"},
        "action": {
            "type": "string",
            "description": (
                "One-sentence imperative naming what happens this step. "
                "Example for BFS: 'Pop node B from the queue and visit it'."
            ),
        },
        "reason": {
            "type": "string",
            "description": "One sentence: why this happens NOW.",
        },
        "text_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Bullet content for the learner-facing card. Main bullet + "
                "1-3 sub-bullets. Sub-bullets start with '  - '."
            ),
        },
        "state_after": {
            "type": "object",
            "description": (
                "OPAQUE to the schema; shape is base_type-specific. For "
                "node_link: {active_node, completed_nodes, "
                "node_state_map, runtime_state}. For indexed_sequence: "
                "{pointers, ranges, highlighted_cells, swapped_cells}. "
                "For code_execution: {visible_until_line, highlight_lines, "
                "variables, call_stack, output}. The compiler validates "
                "and normalizes per base_type."
            ),
            "additionalProperties": True,
        },
        "transition_hints": {
            "type": "array",
            "items": TRANSITION_HINT_SCHEMA,
            "description": (
                "Optional. Use when the natural transition order matters "
                "for clarity (e.g. binary search 'compute m, then move l')."
            ),
        },
    },
    "required": [
        "step_number",
        "action",
        "reason",
        "text_points",
        "state_after",
        "transition_hints",
    ],
    "additionalProperties": False,
}


WORKED_EXAMPLE_PLAN_SCHEMA_V2: dict[str, Any] = {
    "type": ["object", "null"],
    "description": (
        "UNIVERSAL worked-example plan. Replaces the two pilots "
        "(math worked_example_plan + algorithm node_link_worked_example). "
        "REQUIRED (non-null) for cards with role='worked_example' or "
        "role='code_walkthrough' on topics where the visual is dynamic. "
        "May be null for purely textual or static cards. "
        "base_state shape is base_type-specific; see prompt for details."
    ),
    "properties": {
        "id": {"type": "string"},
        "visual_intent": VISUAL_INTENT_SCHEMA,
        "problem_setup": {
            "type": "string",
            "description": (
                "One paragraph stating the concrete input the worked example "
                "traces. For a BST inorder traversal: state the tree values. "
                "For binary search: state the sorted array + target."
            ),
        },
        "terminal_state": {
            "type": "string",
            "description": (
                "One sentence stating what 'done' looks like (e.g. 'Output "
                "list contains all 7 values in ascending order'; 'Target "
                "found at index 3')."
            ),
        },
        "base_state": {
            "type": "object",
            "description": (
                "The persistent structure all step cards share. OPAQUE to "
                "the schema; shape is base_type-specific. For node_link: "
                "{nodes, edges}. For indexed_sequence: {values, indices, "
                "pointer_definitions}. For code_execution: {code, "
                "language, variable_definitions}."
            ),
            "additionalProperties": True,
        },
        "steps": {
            "type": "array",
            "items": WORKED_EXAMPLE_STEP_SCHEMA,
            "description": (
                "At least 5 steps for non-boundary topics. Last step must "
                "match terminal_state."
            ),
        },
    },
    "required": [
        "id",
        "visual_intent",
        "problem_setup",
        "terminal_state",
        "base_state",
        "steps",
    ],
    "additionalProperties": False,
}


# ===========================================================================
# LEAN CARD V2 — intent only, no render data
# ===========================================================================

LEAN_CARD_V2_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "A single card. Carries intent + content, NO render data. The "
        "backend compiler turns visual_intent + worked_example_plan into "
        "renderable VisualModels."
    ),
    "properties": {
        "id": {"type": "string"},
        "role": {
            "type": "string",
            "enum": [
                "background",
                "components_terms",
                "process",
                "worked_example",
                "code_walkthrough",
                "edge_case",
                "comparison",
                "practice",
                "takeaway",
            ],
        },
        "title": {"type": "string"},
        "learning_job": {
            "type": "string",
            "description": "One sentence: what cognitive job this card does.",
        },
        "points": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Bullet content. Main bullets at top-level; sub-bullets "
                "prefixed with '  - '."
            ),
        },
        "visual_intent": VISUAL_INTENT_SCHEMA,
        "worked_example_plan_id": {
            "type": ["string", "null"],
            "description": (
                "Reference to a WorkedExamplePlan in the lesson's "
                "worked_example_plans array. Required when role is "
                "'worked_example' or 'code_walkthrough'. Null otherwise."
            ),
        },
        "practice_question_index": {
            "type": ["integer", "null"],
            "description": (
                "Reference into practice_questions[]. Required when "
                "role='practice'. Null otherwise."
            ),
        },
        "estimated_seconds": {"type": "integer"},
    },
    "required": [
        "id",
        "role",
        "title",
        "learning_job",
        "points",
        "visual_intent",
        "worked_example_plan_id",
        "practice_question_index",
        "estimated_seconds",
    ],
    "additionalProperties": False,
}


# ===========================================================================
# PRACTICE QUESTION
# ===========================================================================

PRACTICE_QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "question_type": {
            "type": "string",
            "enum": ["multiple_choice", "short_answer", "coding"],
        },
        "question_text": {"type": "string"},
        "correct_answer": {"type": "string"},
        "choices": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Empty array for short_answer/coding questions.",
        },
        "skill_target": {"type": "string"},
        "concept_tested": {"type": "string"},
    },
    "required": [
        "id",
        "question_type",
        "question_text",
        "correct_answer",
        "choices",
        "skill_target",
        "concept_tested",
    ],
    "additionalProperties": False,
}


# ===========================================================================
# LESSON V2 — top-level lesson contract from the LLM
# ===========================================================================

LESSON_V2_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Top-level lesson the LLM emits. No `lesson_cards` array — that's "
        "the legacy shape. Backend compiles cards[] + worked_example_plans[] "
        "into VisualModel[] + RenderStep[]."
    ),
    "properties": {
        "title": {"type": "string"},
        "topic_summary": {"type": "string"},
        "estimated_minutes": {"type": "integer"},
        "cards": {
            "type": "array",
            "items": LEAN_CARD_V2_SCHEMA,
        },
        "worked_example_plans": {
            "type": "array",
            "items": WORKED_EXAMPLE_PLAN_SCHEMA_V2,
            "description": (
                "Plans referenced by cards via worked_example_plan_id. "
                "Empty array if the lesson has no worked examples."
            ),
        },
        "practice_questions": {
            "type": "array",
            "items": PRACTICE_QUESTION_SCHEMA,
        },
    },
    "required": [
        "title",
        "topic_summary",
        "estimated_minutes",
        "cards",
        "worked_example_plans",
        "practice_questions",
    ],
    "additionalProperties": False,
}


# ===========================================================================
# TOPIC CLASSIFICATION V2 — adds visual_domain
# ===========================================================================

TOPIC_CLASSIFICATION_V2_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Topic classification with visual_domain added. Used by the new "
        "topic classifier to pre-route the lesson's default base_type."
    ),
    "properties": {
        "topic_type": {
            "type": "string",
            "description": "Existing CourseType enum value.",
        },
        "secondary_topic_types": {
            "type": "array",
            "items": {"type": "string"},
        },
        "knowledge_level": {
            "type": ["integer", "null"],
        },
        "visual_domain": {
            "type": "string",
            "enum": [
                "tree",
                "graph",
                "linked_list",
                "array",
                "string",
                "matrix",
                "table",
                "memory",
                "code",
                "coordinate_math",
                "geometry",
                "formula",
                "timeline_protocol",
                "set_logic",
                "real_world",
                "generic",
            ],
        },
        "visual_mode_hint": {
            "type": "string",
            "description": (
                "Suggested mode under the domain's base_type. May be "
                "overridden by individual cards' visual_intent.mode."
            ),
        },
        "reason": {
            "type": "string",
            "description": (
                "One sentence: why this topic_type and visual_domain match."
            ),
        },
    },
    "required": [
        "topic_type",
        "secondary_topic_types",
        "knowledge_level",
        "visual_domain",
        "visual_mode_hint",
        "reason",
    ],
    "additionalProperties": False,
}
