"""V2 lesson prompt — intent-only.

The LLM is asked for:
  - cards[] (each with visual_intent only — no render data fields)
  - worked_example_plans[] (universal plan with base_state + steps)
  - practice_questions[]

The LLM is NEVER asked to write nodes, edges, array cells, code highlights,
table rows, etc. That is the backend compilers' job.

Coexists with the legacy prompt at lean_lesson_prompt.py. Nothing here
modifies the legacy prompt.
"""

from __future__ import annotations

from typing import Any


SYSTEM_PROMPT_V2 = """You are an expert lesson designer for Azalea, an AI learning platform that compiles your lesson description into interactive visuals.

Your job is to write the LESSON CONTENT and the WORKED EXAMPLE PLAN. Azalea's backend handles ALL visual rendering — you must NEVER write nodes, edges, array cells, code line numbers, table rows, formulas as render data, etc. You only DESCRIBE the visual intent and provide the worked-example state transitions.

Output strict JSON matching the LessonV2 schema. No Markdown.
"""


# ---------------------------------------------------------------------------
# Visual base-type guidance — what to use for what
# ---------------------------------------------------------------------------

BASE_TYPE_GUIDE = """
PICK base_type based on the topic:

| Topic kind                                  | base_type                         | mode example          |
|---------------------------------------------|-----------------------------------|------------------------|
| Tree / BST / linked list / state machine    | node_link_diagram                 | tree_hierarchy, graph_network, linked_list_chain, state_machine |
| Array / string / pointers / sorting         | indexed_sequence_diagram          | array_state, binary_search_range, sliding_window, sorting_pass |
| Matrix / DP table / adjacency / K-map       | grid_matrix_diagram               | matrix, dp_table, adjacency_matrix |
| Comparison / variable trace / truth table   | table_diagram                     | comparison_table, variable_trace_table |
| Coordinate axes / function curve / loss     | coordinate_graph                  | function_curve, distribution_curve, loss_curve |
| Memory / stack frames / pointers / heap     | memory_layout_diagram             | stack_heap, call_stack, pointer_reference |
| Code line-by-line / debugging               | code_execution_panel              | code_walkthrough_growing, code_execution_trace |
| Bayes / formula derivation / algebra        | formula_symbolic_expression       | formula_breakdown, substitution |
| Geometry / vectors / 3D solids              | geometric_diagram                 | triangle_geometry, vector_geometry, 3d_solid |
| Protocol / message passing / threads        | timeline_sequence_interaction     | protocol_sequence, race_condition |
| Set / Venn / probability region             | set_region_diagram                | venn_diagram, sample_space |
| Real-world analogy / intuition only         | image_real_world_illustration     | analogy_image, system_metaphor |

OR use a SUPPORT VISUAL when no concrete base fits:
  - step_flow: process map for general procedures
  - practice_feedback: practice prediction → answer reveal
  - path_progress: roadmap of where in the study path
  - source_annotation: PDF excerpt with annotations
  - topic_snapshot: ultra-light intro preview

NEVER write the structural data (nodes, edges, cells, lines, formulas). The compiler builds them from the worked_example_plan.base_state for dynamic visuals and from the visual_intent.description for static visuals.
"""


# ---------------------------------------------------------------------------
# Card role guidance
# ---------------------------------------------------------------------------

ROLE_GUIDE = """
CARD ROLES (each lesson has 3-7 cards):

- background: ONE card. Static preview of the object/system being studied. visual_intent.static_or_dynamic = "static". For node_link: emit a worked_example_plan with the structure (the compiler reuses it for the background card too).
- components_terms: optional. Key terms with a small concept diagram.
- process: explain the rule. visual_intent may be step_flow OR null for text-only.
- worked_example: trace ONE concrete example. visual_intent.static_or_dynamic = "dynamic". MUST link to a worked_example_plan via worked_example_plan_id.
- code_walkthrough: only for coding_implementation topics. base_type = code_execution_panel, mode = code_walkthrough_growing or code_execution_trace.
- edge_case: a boundary state (empty/single/etc). Static; visual_intent base_type matches the topic's main base_type, mode unchanged.
- comparison: contrast two approaches. base_type = table_diagram, mode = comparison_table.
- practice: link via practice_question_index. visual_intent may be null or support: practice_feedback.
- takeaway: visual_intent = null. Pure text.
"""


# ---------------------------------------------------------------------------
# Worked-example plan guidance per base_type
# ---------------------------------------------------------------------------

PLAN_GUIDE = """
WORKED EXAMPLE PLAN — UNIVERSAL FORMAT:

Every plan has:
  id, visual_intent, problem_setup, terminal_state, base_state, steps[]

base_state shape DEPENDS ON visual_intent.base_type:

node_link_diagram:
  base_state = {
    "nodes": [{"id": "50", "label": "50", "relation": "root", "x": 50, "y": 16}, ...],
    "edges": [{"from": "50", "to": "30", "label": "", "style": "solid"}, ...]
  }
  Each step.state_after = {
    "active_node": "30",
    "completed_nodes": ["50"],
    "node_state_map": [{"node_id": "30", "state": "current"}],
    "active_edge_from": "50",  # optional
    "active_edge_to": "30",    # optional
    "completed_edges_from": [], "completed_edges_to": [],
    "runtime_state": {
      "call_stack": ["50", "30"],
      "output": [],
      "frontier": [],  # for BFS/DFS
      "variables": []
    },
    "attention_note": "Moved to node 30."
  }

indexed_sequence_diagram:
  base_state = {
    "values": ["1", "3", "5", "7", "9"],
    "pointer_definitions": [
      {"id": "l", "label": "left"},
      {"id": "r", "label": "right"},
      {"id": "m", "label": "mid"}
    ]
  }
  Each step.state_after = {
    "pointers": [
      {"id": "l", "position": 0, "label": "left"},
      {"id": "r", "position": 4, "label": "right"},
      {"id": "m", "position": 2, "label": "mid"}
    ],
    "ranges": [{"id": "search_range", "start": 0, "end": 4, "label": "active"}],
    "highlighted_cells": [2],
    "swapped_cells": null,
    "sorted_prefix_end": null
  }

code_execution_panel:
  base_state = {
    "code": "def binary_search(arr, target):\\n    l, r = 0, len(arr) - 1\\n    while l <= r:\\n        ...",
    "language": "python"
  }
  Each step.state_after = {
    "visible_until_line": 7,           # growing mode only; ignored in execution mode
    "highlight_lines": [3, 4],         # 1-indexed inclusive range
    "variables": [{"name": "l", "value": "0"}, {"name": "r", "value": "4"}, {"name": "m", "value": "2"}],
    "call_stack": ["binary_search"],
    "output": []
  }

formula_symbolic_expression:
  base_state = {
    "expression": "P(A|B) = P(B|A)P(A) / P(B)",
    "symbols": [
      {"symbol": "P(A|B)", "meaning": "posterior probability", "value": ""},
      {"symbol": "P(B|A)", "meaning": "likelihood", "value": ""},
      {"symbol": "P(A)", "meaning": "prior probability", "value": ""},
      {"symbol": "P(B)", "meaning": "evidence", "value": ""}
    ],
    "assumptions": ["P(B) is nonzero"]
  }
  Each step.state_after = {
    "active_symbol": "P(A|B)",
    "active_expression": "P(A|B) = P(B|A)P(A) / P(B)",
    "substitution": {"P(B|A)": "0.9", "P(A)": "0.1", "P(B)": "0.18"},
    "transformed_expression": "P(A|B) = (0.9 * 0.1) / 0.18",
    "equivalence_chain": [
      "P(A|B) = P(B|A)P(A) / P(B)",
      "P(A|B) = (0.9 * 0.1) / 0.18"
    ]
  }

table_diagram:
  base_state = {
    "columns": ["Concept", "Correct use", "Common trap"],
    "rows": [
      ["BFS", "Use a queue/frontier", "Accidentally using stack order"],
      ["DFS", "Use a stack or recursion", "Expecting level-order output"]
    ],
    "row_labels": ["BFS", "DFS"],
    "caption": "Compare the two traversal strategies."
  }
  Each step.state_after = {
    "active_row": 0,
    "active_cell": [0, 1],
    "changed_cells": [[0, 1]],
    "cell_values": {"0,1": "Queue processes earliest discovered node first"}
  }

coordinate_graph:
  base_state = {
    "axes": {"x_min": -3, "x_max": 3, "y_min": 0, "y_max": 0.45, "x_label": "z", "y_label": "density"},
    "curves": [
      {
        "id": "normal_pdf",
        "label": "Normal PDF",
        "points": [[-3, 0.004], [-2, 0.054], [-1, 0.242], [0, 0.399], [1, 0.242], [2, 0.054], [3, 0.004]]
      }
    ],
    "points": [{"id": "mean", "label": "mean", "x": 0, "y": 0.399}],
    "caption": "A normal distribution curve."
  }
  Each step.state_after = {
    "active_curve": "normal_pdf",
    "active_point": "mean",
    "shaded_region": {"curve_id": "normal_pdf", "x_start": -1, "x_end": 1, "label": "P(-1 <= Z <= 1)"},
    "tangent_secant_line": null,
    "active_curve_segment": {"curve_id": "normal_pdf", "x_start": -1, "x_end": 1}
  }

memory_layout_diagram:
  base_state = {
    "frames": [
      {"id": "call_1", "label": "dfs(A)", "variables": [{"name": "node", "value": "A", "target": "node_A"}]},
      {"id": "call_2", "label": "dfs(B)", "variables": [{"name": "node", "value": "B", "target": "node_B"}]}
    ],
    "objects": [
      {"id": "node_A", "label": "Node A", "fields": [{"name": "left", "target": "node_B"}]},
      {"id": "node_B", "label": "Node B", "fields": []}
    ],
    "pointers": [{"id": "ptr_call_1_node", "from": "call_1.node", "to": "node_A", "label": "node"}],
    "caption": "Call stack frames reference heap nodes."
  }
  Each step.state_after = {
    "active_frame": "call_2",
    "active_object": "node_B",
    "active_pointer": "ptr_call_1_node",
    "changed_bindings": ["call_2.node"],
    "visible_frames": ["call_1", "call_2"],
    "visible_objects": ["node_A", "node_B"]
  }

set_region_diagram:
  base_state = {
    "sets": [
      {"id": "A", "label": "A", "x": 42, "y": 50, "r": 28},
      {"id": "B", "label": "B", "x": 58, "y": 50, "r": 28}
    ],
    "elements": [
      {"id": "x1", "label": "x1", "x": 50, "y": 50, "regions": ["A", "B"]},
      {"id": "x2", "label": "x2", "x": 34, "y": 50, "regions": ["A"]}
    ],
    "caption": "Two overlapping sets with an intersection."
  }
  Each step.state_after = {
    "active_set": "A",
    "active_region": "A_B",
    "shaded_regions": ["A_B"],
    "active_element": "x1"
  }

timeline_sequence_interaction:
  base_state = {
    "actors": [{"id": "client", "label": "Client"}, {"id": "server", "label": "Server"}],
    "messages": [
      {"id": "request", "from": "client", "to": "server", "label": "request", "time": 1},
      {"id": "response", "from": "server", "to": "client", "label": "response", "time": 2}
    ],
    "caption": "Client-server request/response sequence."
  }
  Each step.state_after = {
    "active_actor": "server",
    "active_message": "request",
    "visible_messages": ["request"],
    "actor_states": {"client": "waiting", "server": "processing"}
  }

geometric_diagram:
  base_state = {
    "points": [
      {"id": "A", "label": "A", "x": 20, "y": 75},
      {"id": "B", "label": "B", "x": 80, "y": 75},
      {"id": "C", "label": "C", "x": 50, "y": 25}
    ],
    "segments": [
      {"id": "AB", "from": "A", "to": "B", "label": "base"},
      {"id": "BC", "from": "B", "to": "C", "label": ""},
      {"id": "CA", "from": "C", "to": "A", "label": ""}
    ],
    "regions": [{"id": "triangle_ABC", "label": "area", "points": ["A", "B", "C"]}],
    "caption": "Triangle ABC with its sides and interior region."
  }
  Each step.state_after = {
    "active_point": "C",
    "active_segment": "AB",
    "active_region": "triangle_ABC",
    "shaded_regions": ["triangle_ABC"],
    "measurements": {"AB": "base = 12"}
  }

image_real_world_illustration:
  base_state = {
    "scene_title": "Factory Assembly Line",
    "description": "Items move through repeated stations, similar to a staged process.",
    "hotspots": [
      {"id": "input", "label": "Input", "x": 22, "y": 48, "description": "The initial material or starting condition."},
      {"id": "process", "label": "Process", "x": 50, "y": 38, "description": "The repeated transformation step."},
      {"id": "output", "label": "Output", "x": 78, "y": 48, "description": "The final result."}
    ],
    "caption": "A real-world analogy with clickable hotspots."
  }
  Each step.state_after = {
    "active_hotspot": "process",
    "visible_hotspots": ["input", "process", "output"]
  }

Other base_types: see schema docs. The compiler validates per base_type.

CRITICAL — STABLE ELEMENT IDS:
- Node ids in step.state_after MUST match base_state.nodes[i].id (e.g. "50", "30").
- Pointer ids (l, r, m) MUST be defined in base_state.pointer_definitions and reused identically in every step.pointers[i].id.
- Variable names MUST be the same across steps.
The animation system uses these stable ids to slide pointers, fade in nodes, etc. Inconsistent ids break the animation.

TRANSITION HINTS (optional):
When the natural order of changes matters (e.g. binary search: compute m FIRST, then move l), set step.transition_hints:
  [{"description": "compute m before moving l", "sequence": ["m", "l"], "stagger_ms": 200}]
Leave empty for trivial steps.

STEP COUNT:
- At least 5 steps for non-boundary topics.
- The last step's state must match terminal_state.
"""


# ---------------------------------------------------------------------------
# Output contract reminder
# ---------------------------------------------------------------------------

OUTPUT_CONTRACT = """
YOUR OUTPUT MUST BE A SINGLE JSON OBJECT matching LessonV2:

{
  "title": "...",
  "topic_summary": "...",
  "estimated_minutes": 5,
  "cards": [
    {
      "id": "card-1",
      "role": "background",
      "title": "...",
      "learning_job": "One sentence stating what this card does.",
      "points": ["bullet 1", "  - sub-bullet", "bullet 2"],
      "visual_intent": {
        "base_type": "node_link_diagram",
        "mode": "tree_hierarchy",
        "description": "A BST with root 50, children 30 and 70...",
        "purpose": "Trace the structure at rest.",
        "static_or_dynamic": "static"
      },
      "worked_example_plan_id": null,
      "practice_question_index": null,
      "estimated_seconds": 60
    },
    {
      "id": "card-2",
      "role": "worked_example",
      "title": "Trace inorder",
      "learning_job": "Trace through inorder traversal.",
      "points": ["Watch the order"],
      "visual_intent": {
        "base_type": "node_link_diagram",
        "mode": "tree_hierarchy",
        "description": "Inorder traversal walking left-node-right",
        "purpose": "Trace the visit order.",
        "static_or_dynamic": "dynamic"
      },
      "worked_example_plan_id": "plan-1",
      "practice_question_index": null,
      "estimated_seconds": 180
    }
  ],
  "worked_example_plans": [
    {
      "id": "plan-1",
      "visual_intent": { ... },
      "problem_setup": "BST with values 50, 30, 70, 20, 40.",
      "terminal_state": "Output list = [20, 30, 40, 50, 70].",
      "base_state": {
        "nodes": [...],
        "edges": [...]
      },
      "steps": [...]
    }
  ],
  "practice_questions": [
    {
      "id": "q-1",
      "question_type": "short_answer",
      "question_text": "What is the inorder traversal of a BST with values 1, 2, 3?",
      "correct_answer": "1, 2, 3",
      "choices": [],
      "skill_target": "Apply inorder traversal",
      "concept_tested": "Inorder traversal"
    }
  ]
}

NO render data fields on cards. NO `visual_nodes`, `visual_edges`, `visual_array_values`, `visual_steps`, `visual_columns`, `visual_rows`, `visual_formula`. Those are FORBIDDEN. They live on worked_example_plans[].base_state and step.state_after where the schema explicitly accepts them.
"""


# ---------------------------------------------------------------------------
# Visual-domain-specific add-ons (chosen by visual_domain from topic classifier)
# ---------------------------------------------------------------------------

DOMAIN_FRAGMENTS: dict[str, str] = {
    "tree": """
TOPIC IS TREE-BASED (BST, binary tree, n-ary tree, heap, trie):
- Use base_type = node_link_diagram, mode = tree_hierarchy.
- Pick 5-10 distinct integer values for the tree; do NOT default to 50/30/70/20/40/60/80 (overused). Pick fresh values per lesson.
- For BSTs, satisfy the BST property and make the tree asymmetric (some internal node with only one child).
- Background card: emit a worked_example_plan even if static, so the compiler has the structure. Set static_or_dynamic = "static" on its visual_intent. Reference it from the background card via worked_example_plan_id.
- Worked example trace: every step's state_after.runtime_state.call_stack must reflect the recursive call stack at that moment. output[] accumulates as nodes are visited.
""",
    "graph": """
TOPIC IS GRAPH-BASED (BFS, DFS, MST, Dijkstra, topological sort):
- Use base_type = node_link_diagram, mode = graph_network.
- 6-8 lettered vertices, 7-10 edges. Weighted only for MST / Dijkstra / Bellman-Ford / A*.
- Worked example: runtime_state.frontier carries the queue/stack/PQ. runtime_state.frontier_kind = "queue" | "stack" | "priority_queue".
- active_edge_from/to mark the edge being considered THIS step.
""",
    "array": """
TOPIC IS ARRAY-BASED (binary search, sliding window, two pointers, sort):
- Use base_type = indexed_sequence_diagram, mode chosen from the algorithm.
- base_state.pointer_definitions MUST be declared upfront (e.g. l, r, m). Every step.state_after.pointers uses those exact ids.
- For binary search: include transition_hints to enforce "compute m, then move l/r" ordering.
- swapped_cells = [i, j] when two cells exchange values in a sort.
""",
    "code": """
TOPIC IS CODE-IMPLEMENTATION:
- Use base_type = code_execution_panel.
- code_walkthrough cards: mode = code_walkthrough_growing. visible_until_line grows per step.
- worked_example cards: mode = code_execution_trace. visible_until_line = base.line_count from frame 1; highlight_lines moves.
- variables[] in state_after captures the trace (name + current value). Names MUST be stable across steps.
""",
    "formula": """
TOPIC IS FORMULA / SYMBOLIC:
- Use base_type = formula_symbolic_expression.
- Use mode = formula_breakdown for definitions, substitution for numeric plug-in, algebraic_transformation for rearranging, calculus_derivation for derivative/integral steps, or recurrence_expansion for recurrence topics.
- Put the persistent formula in base_state.expression.
- Put every important symbol in base_state.symbols with symbol, meaning, and optional value.
- For worked examples, each step.state_after should identify active_symbol or active_expression, include substitutions when values are plugged in, and grow equivalence_chain as the derivation proceeds.
""",
    "table": """
TOPIC IS TABLE / COMPARISON:
- Use base_type = table_diagram.
- Use mode = comparison_table for concept contrasts, variable_trace_table for changing values, truth_table for logical cases, or decision_table for branching rules.
- Put stable column names in base_state.columns and all base rows in base_state.rows.
- Use base_state.row_labels when rows represent named concepts, variables, or cases.
- For dynamic examples, each step.state_after should identify active_row or active_cell and use changed_cells for values introduced or corrected on that step.
- Do not put table render data on cards. Put it only in worked_example_plans[].base_state and steps[].state_after.
""",
    "coordinate_math": """
TOPIC IS COORDINATE / GRAPH-BASED MATH:
- Use base_type = coordinate_graph.
- Use mode = distribution_curve for probability distributions, area_under_curve for probability intervals, function_curve for general functions, runtime_growth for Big-O curves, or tangent_secant for rates of change.
- Put axes, curves, plotted points, and captions in worked_example_plans[].base_state.
- Use a small but faithful sample of curve points. Do not emit hundreds of points.
- For dynamic examples, use active_point for the current x/y focus, shaded_region for probability/area intervals, active_curve_segment for the interval being discussed, and tangent_secant_line for rate/slope ideas.
""",
    "memory": """
TOPIC IS MEMORY / POINTER / CALL-STACK BASED:
- Use base_type = memory_layout_diagram.
- Use mode = call_stack for recursion, stack_heap for stack-vs-heap, pointer_reference for references, object_layout for objects, or array_memory for contiguous memory.
- Put all possible stack frames, heap objects, variable bindings, and pointer arrows in worked_example_plans[].base_state.
- For dynamic examples, reveal progress with visible_frames and visible_objects, and use active_frame, active_object, active_pointer, and changed_bindings to show what changed on the current step.
- Stable ids matter: variable ids should use frame_id.variable_name, and pointers should reuse the same id across all steps.
""",
    "set_logic": """
TOPIC IS SET / LOGIC / PROBABILITY-REGION BASED:
- Use base_type = set_region_diagram.
- Use mode = venn_diagram for set relationships, probability_region or sample_space for probability, classification_overlap for ML/classification overlap, or logic_region for Boolean logic.
- Put all sets and reusable elements in worked_example_plans[].base_state.
- Use active_set, active_region, shaded_regions, and active_element in each step.state_after to show the current focus.
- For intersections, use stable region ids like A_B or A_B_C.
""",
    "timeline_protocol": """
TOPIC IS TIMELINE / PROTOCOL / CONCURRENCY BASED:
- Use base_type = timeline_sequence_interaction.
- Use mode = protocol_sequence for protocol messages, request_response for client/server flows, thread_schedule for concurrency, transaction_timeline for database transactions, or lock_acquisition for lock ordering.
- Put all actors and possible messages in worked_example_plans[].base_state.
- For dynamic examples, use visible_messages to reveal progress, active_message for the current arrow, active_actor for the participant currently doing work, and actor_states for states like waiting, blocked, processing, or done.
""",
    "geometry": """
TOPIC IS GEOMETRY / VECTOR / SPATIAL:
- Use base_type = geometric_diagram.
- Use mode = triangle_geometry for triangles, circle_geometry for circles, vector_geometry for vectors, projection for projection diagrams, integration_region for shaded regions, or related_rates for changing measurements.
- Put points, segments, polygon regions, and captions in worked_example_plans[].base_state.
- For dynamic examples, use active_point, active_segment, active_region, shaded_regions, and measurements to show the current focus.
""",
    "real_world": """
TOPIC IS REAL-WORLD / ANALOGY / INTUITION:
- Use base_type = image_real_world_illustration.
- This does not require an external image. Provide a structured scene_title, description, and hotspots in worked_example_plans[].base_state.
- Use active_hotspot and visible_hotspots in each step.state_after for dynamic analogy walkthroughs.
- Hotspots should name concrete parts of the analogy, not generic labels like "thing" or "part".
""",
    "generic": """
TOPIC IS GENERIC / INTRODUCTORY:
- Prefer support visual topic_snapshot when a concrete visual domain is not available.
- If a real-world analogy helps, use base_type = image_real_world_illustration with a scene_title, description, and 2-4 concrete hotspots.
- Do not invent precise technical render data for a generic topic. Keep the scene conceptual and use hotspots for the focus points.
""",
}


def _domain_fragment(visual_domain: str) -> str:
    return DOMAIN_FRAGMENTS.get(visual_domain, "")


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_lesson_v2_prompt(
    topic_title: str,
    topic_summary: str,
    topic_type: str,
    visual_domain: str,
    visual_mode_hint: str,
    knowledge_level: int | None,
    chunks_text: str,
    learner_goal: str = "",
    feedback: str = "",
) -> str:
    """Compose the user prompt for the v2 LLM call.

    The system prompt is `SYSTEM_PROMPT_V2`. This function returns the
    user message that includes topic context, base-type guidance,
    role guidance, and plan format.
    """

    knowledge_text = (
        f"Knowledge level: {knowledge_level}/5"
        if knowledge_level is not None
        else "Knowledge level: unknown"
    )

    parts: list[str] = [
        f"TOPIC: {topic_title}",
        f"Topic type: {topic_type}",
        f"Visual domain: {visual_domain}",
        f"Default visual mode hint: {visual_mode_hint}",
        knowledge_text,
        "",
        f"Topic summary: {topic_summary}",
    ]
    if learner_goal:
        parts.append(f"\nLearner goal: {learner_goal}")
    if feedback:
        parts.append(f"\nLearner feedback to incorporate: {feedback}")
    if chunks_text:
        parts.append("\n--- SOURCE MATERIAL ---\n" + chunks_text)

    parts.extend([
        "",
        BASE_TYPE_GUIDE,
        ROLE_GUIDE,
        PLAN_GUIDE,
        _domain_fragment(visual_domain),
        OUTPUT_CONTRACT,
    ])

    return "\n".join(parts)
