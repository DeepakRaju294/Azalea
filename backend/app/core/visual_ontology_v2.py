"""Visual ontology v2 — the single source of truth for the new visual system.

The v2 system separates VISUAL INTENT (what the LLM decides) from VISUAL
RENDERING (what the backend compiles + frontend draws). Twelve base visual
types form the irreducible renderer families. Modes are subject-specific
layouts inside a base type. Card roles describe the instructional job.

This file is pure data — no logic. Importing it has no side effects.

Coexists with the legacy ontology in app/core/course_blueprints.py; the
v2 system does NOT modify or depend on legacy structures.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# BASE VISUAL TYPES — the 12 irreducible renderer families
# ---------------------------------------------------------------------------

BASE_VISUAL_TYPES: Final[tuple[str, ...]] = (
    "coordinate_graph",
    "node_link_diagram",
    "indexed_sequence_diagram",
    "grid_matrix_diagram",
    "table_diagram",
    "memory_layout_diagram",
    "code_execution_panel",
    "geometric_diagram",
    "formula_symbolic_expression",
    "timeline_sequence_interaction",
    "set_region_diagram",
    "image_real_world_illustration",
)


# ---------------------------------------------------------------------------
# SUPPORT VISUALS — NOT base types, used when no concrete base fits.
# These continue to exist as standalone visuals; they are NOT modes under
# any base type. They typically render directly without going through a
# compiler.
# ---------------------------------------------------------------------------

SUPPORT_VISUALS: Final[tuple[str, ...]] = (
    "step_flow",            # process map — when no concrete base is better
    "practice_feedback",    # prediction/feedback overlay on practice cards
    "path_progress",        # study-path progress (roadmap cards)
    "source_annotation",    # uploaded-material excerpt with annotations
    "topic_snapshot",       # static intro preview when domain is generic
)


# ---------------------------------------------------------------------------
# MODES BY BASE TYPE — subject-specific layouts inside each base type.
# The compiler reads (base_type, mode) to dispatch to the right frame logic.
# ---------------------------------------------------------------------------

MODES_BY_BASE_TYPE: Final[dict[str, tuple[str, ...]]] = {
    "coordinate_graph": (
        "function_curve",
        "scatter_plot",
        "distribution_curve",
        "loss_curve",
        "runtime_growth",
        "area_under_curve",
        "tangent_secant",
        "vector_field",
        "phase_portrait",
        "regression_plot",
        "roc_curve",
    ),
    "node_link_diagram": (
        "tree_hierarchy",
        "graph_network",
        "linked_list_chain",
        "state_machine",
        "circuit",
        "dependency_graph",
        "resource_graph",
        "automata",
        "er_diagram",
        "architecture_container",
        "data_pipeline",
        "recursion_tree",
    ),
    "indexed_sequence_diagram": (
        "array_state",
        "string_state",
        "binary_search_range",
        "sliding_window",
        "two_pointer",
        "sorting_pass",
        "merge_partition",
        "token_sequence",
        "prefix_sum",
    ),
    "grid_matrix_diagram": (
        "matrix",
        "dp_table",
        "adjacency_matrix",
        "grid_traversal",
        "confusion_matrix",
        "karnaugh_map",
        "heatmap",
        "cell_dependency",
    ),
    "table_diagram": (
        "comparison_table",
        "truth_table",
        "sql_table",
        "variable_trace_table",
        "distance_table",
        "symbol_table",
        "routing_table",
        "page_table",
        "decision_table",
    ),
    "memory_layout_diagram": (
        "stack_heap",
        "call_stack",
        "pointer_reference",
        "object_layout",
        "array_memory",
        "virtual_memory",
        "page_table",
        "cache_lines",
        "buffer_layout",
    ),
    "code_execution_panel": (
        # Growing mode: visible_until_line increases per frame.
        "code_walkthrough_growing",
        # Execution mode: full code visible from frame 1, highlight moves.
        "code_execution_trace",
        "debug_trace",
        "recursive_execution",
        "loop_trace",
        "condition_evaluation",
        "input_output_trace",
    ),
    "geometric_diagram": (
        "triangle_geometry",
        "circle_geometry",
        "vector_geometry",
        "projection",
        "3d_solid",
        "integration_region",
        "related_rates",
        "linear_algebra_geometry",
        "optimization_geometry",
    ),
    "formula_symbolic_expression": (
        "formula_breakdown",
        "symbol_definition",
        "substitution",
        "algebraic_transformation",
        "calculus_derivation",
        "recurrence_expansion",
        "big_o_expression",
        "boolean_expression",
        "matrix_formula",
        "loss_function",
    ),
    "timeline_sequence_interaction": (
        "protocol_sequence",
        "request_response",
        "message_passing",
        "thread_schedule",
        "transaction_timeline",
        "race_condition",
        "lock_acquisition",
        "oauth_flow",
    ),
    "set_region_diagram": (
        "venn_diagram",
        "union",
        "intersection",
        "complement",
        "sample_space",
        "probability_region",
        "classification_overlap",
        "logic_region",
    ),
    "image_real_world_illustration": (
        "analogy_image",
        "real_world_scene",
        "physical_intuition",
        "topic_motivation",
        "system_metaphor",
    ),
}


# ---------------------------------------------------------------------------
# DESCRIPTIONS — what each base type and mode IS, in one line.
#
# These are the seed of a richer per-subtype profile. Today they document the
# taxonomy (so the LLM can pick the right subtype, and humans can read it). In
# future, based on user feedback / issues / quality improvements, each entry is
# the natural home to attach render rules (layout, label convention, valid
# node/edge states, which side panels apply) — i.e. promote `str` to a profile
# dict per mode. Keep descriptions short, concrete, and about WHAT IT SHOWS.
# ---------------------------------------------------------------------------

BASE_TYPE_DESCRIPTIONS: Final[dict[str, str]] = {
    "coordinate_graph": "Plot on x/y axes — curves, points, distributions, growth.",
    "node_link_diagram": "Nodes joined by edges — trees, graphs, lists, circuits, state machines.",
    "indexed_sequence_diagram": "A linear row of indexed cells — arrays/strings and pointers/windows over them.",
    "grid_matrix_diagram": "A 2-D grid of cells — matrices, DP tables, adjacency, heatmaps.",
    "table_diagram": "Rows by labelled columns — comparisons, truth/symbol/routing tables.",
    "memory_layout_diagram": "Memory regions and references — stack/heap, pointers, page tables, cache.",
    "code_execution_panel": "Source code with an execution cursor and variable state.",
    "geometric_diagram": "2-D/3-D geometric figures — triangles, circles, vectors, regions.",
    "formula_symbolic_expression": "A formula broken into symbols and transformation steps.",
    "timeline_sequence_interaction": "Actors exchanging messages over time — protocols, threads, transactions.",
    "set_region_diagram": "Overlapping regions/sets — Venn, probability, classification overlap.",
    "image_real_world_illustration": "A real-world picture or metaphor that anchors intuition, not data.",
}


MODE_DESCRIPTIONS: Final[dict[str, str]] = {
    # coordinate_graph
    "function_curve": "A single function y=f(x) drawn as a smooth curve.",
    "scatter_plot": "Discrete (x, y) data points with no connecting line.",
    "distribution_curve": "A probability/frequency distribution (e.g. a normal bell curve).",
    "loss_curve": "Training loss versus epoch/iteration during model learning.",
    "runtime_growth": "Algorithm runtime versus input size (Big-O growth comparison).",
    "area_under_curve": "A curve with the integral/area beneath it shaded.",
    "tangent_secant": "A curve with a tangent or secant line at a point (derivatives).",
    "vector_field": "A grid of arrows showing a vector field's direction and magnitude.",
    "phase_portrait": "Trajectories of a dynamical system drawn in state space.",
    "regression_plot": "Data points with a fitted regression line/curve.",
    "roc_curve": "True-positive versus false-positive rate for a classifier.",
    # node_link_diagram
    "tree_hierarchy": "A rooted parent/child hierarchy — BST, heap, syntax tree.",
    "graph_network": "A general graph of vertices and edges — BFS/DFS, shortest path, MST.",
    "linked_list_chain": "A linear chain of nodes joined by next-pointers.",
    "state_machine": "States and labelled transitions of a finite-state machine.",
    "circuit": "Electrical/logic components wired together — gates, resistors, nodes.",
    "dependency_graph": "Directed dependencies between tasks/modules (topological order).",
    "resource_graph": "Processes and resources with allocation/request edges (deadlock).",
    "automata": "DFA/NFA states with input-symbol transitions and accept states.",
    "er_diagram": "Database entities and their relationships (keys, cardinality).",
    "architecture_container": "System components/services and the calls between them.",
    "data_pipeline": "Stages of a data flow connected source → transform → sink.",
    "recursion_tree": "The call tree of a recursive function, one node per call.",
    # indexed_sequence_diagram
    "array_state": "A 1-D array of indexed cells whose values evolve per step.",
    "string_state": "A string shown as a row of indexed characters.",
    "binary_search_range": "An array with low/high/mid pointers narrowing a search range.",
    "sliding_window": "An array with a moving window (left/right bounds) over it.",
    "two_pointer": "An array with two pointers converging or scanning.",
    "sorting_pass": "One pass of a sort showing compares/swaps across the array.",
    "merge_partition": "An array split into / merged from sub-arrays (merge/quick sort).",
    "token_sequence": "A sequence of tokens (lexing/parsing) with the current token.",
    "prefix_sum": "An array shown alongside its running prefix-sum array.",
    # grid_matrix_diagram
    "matrix": "A 2-D matrix of numbers for linear-algebra operations.",
    "dp_table": "A dynamic-programming table filled cell by cell.",
    "adjacency_matrix": "A graph's adjacency matrix (rows/cols are vertices).",
    "grid_traversal": "A 2-D grid being traversed — path-finding, flood fill.",
    "confusion_matrix": "Predicted-versus-actual class counts for a classifier.",
    "karnaugh_map": "A K-map grid for Boolean minimisation.",
    "heatmap": "A grid coloured by each cell's magnitude.",
    "cell_dependency": "A grid where each cell depends on neighbours (DP recurrence arrows).",
    # table_diagram
    "comparison_table": "Items compared across labelled attribute columns.",
    "truth_table": "Boolean input combinations mapped to an output per row.",
    "sql_table": "A relational table with typed columns and rows.",
    "variable_trace_table": "Variable values traced down the rows as code runs.",
    "distance_table": "A shortest-distance/estimate table (Dijkstra/Floyd-Warshall).",
    "symbol_table": "Identifiers mapped to their attributes (compilers/scoping).",
    "routing_table": "Destinations mapped to next-hop/interface.",
    "page_table": "Virtual pages mapped to physical frames, with flags.",
    "decision_table": "Condition combinations mapped to actions/outcomes.",
    # memory_layout_diagram
    "stack_heap": "The call-stack and heap regions of process memory.",
    "call_stack": "Stacked call frames with their local variables.",
    "pointer_reference": "Variables and the addresses/objects their pointers reference.",
    "object_layout": "An object/struct's fields laid out in memory.",
    "array_memory": "An array's contiguous cells with addresses/indices.",
    "virtual_memory": "Virtual-to-physical address-translation regions.",
    "cache_lines": "Cache lines/sets and what each currently holds.",
    "buffer_layout": "A byte buffer's regions — header, payload, offsets.",
    # code_execution_panel
    "code_walkthrough_growing": "Code revealed line by line as each line is introduced.",
    "code_execution_trace": "Full code shown; a cursor moves as it executes.",
    "debug_trace": "Step-through execution with the active line and watched values.",
    "recursive_execution": "Execution highlighting recursive calls and returns.",
    "loop_trace": "A loop's iterations with the loop variable/state each pass.",
    "condition_evaluation": "A branch with its condition evaluated true/false.",
    "input_output_trace": "Inputs consumed and outputs produced as code runs.",
    # geometric_diagram
    "triangle_geometry": "A triangle with sides/angles labelled (trig, proofs).",
    "circle_geometry": "A circle with radius/chord/tangent/arc constructions.",
    "vector_geometry": "Vectors drawn and combined — add, dot, cross.",
    "projection": "A projection of one vector/shape onto another or an axis.",
    "3d_solid": "A 3-D solid for volume/surface-area problems.",
    "integration_region": "The 2-D/3-D region of an integral, shaded.",
    "related_rates": "A geometric setup whose dimensions change over time.",
    "linear_algebra_geometry": "A geometric view of a transformation/span/basis.",
    "optimization_geometry": "A feasible region with the optimum point (LP/calculus).",
    # formula_symbolic_expression
    "formula_breakdown": "A formula with each symbol and term annotated.",
    "symbol_definition": "Each symbol in an expression defined.",
    "substitution": "Values substituted into a formula step by step.",
    "algebraic_transformation": "An expression rewritten across algebra steps.",
    "calculus_derivation": "A derivative or integral derived line by line.",
    "recurrence_expansion": "A recurrence unrolled toward a closed form.",
    "big_o_expression": "Terms of a complexity expression reduced to Big-O.",
    "boolean_expression": "A Boolean expression simplified via laws/identities.",
    "matrix_formula": "A matrix equation or operation written symbolically.",
    "loss_function": "A loss/objective function and its terms.",
    # timeline_sequence_interaction
    "protocol_sequence": "Messages exchanged between parties in protocol order.",
    "request_response": "A client/server request and its response.",
    "message_passing": "Messages passed between concurrent processes/actors.",
    "thread_schedule": "Threads interleaved on a timeline (scheduling).",
    "transaction_timeline": "A transaction's operations through commit/rollback.",
    "race_condition": "Interleaved accesses that produce a race.",
    "lock_acquisition": "Lock acquire/release order across threads.",
    "oauth_flow": "The OAuth token-exchange message sequence.",
    # set_region_diagram
    "venn_diagram": "Overlapping set circles showing membership.",
    "union": "Two or more sets with their union highlighted.",
    "intersection": "Sets with their common region highlighted.",
    "complement": "A set's complement within the universe highlighted.",
    "sample_space": "A probability sample space with events as regions.",
    "probability_region": "Regions sized/shaded by probability.",
    "classification_overlap": "Class regions in feature space with their overlap.",
    "logic_region": "Logical predicates drawn as overlapping regions.",
    # image_real_world_illustration
    "analogy_image": "A concrete analogy image for an abstract concept.",
    "real_world_scene": "A real-world scene that grounds the topic.",
    "physical_intuition": "A physical setup conveying intuition (forces, flow).",
    "topic_motivation": "A motivating picture for why the topic matters.",
    "system_metaphor": "A metaphor depicting how a system behaves.",
}


SUPPORT_VISUAL_DESCRIPTIONS: Final[dict[str, str]] = {
    "step_flow": "A simple ordered process/flow of steps when no concrete base fits.",
    "practice_feedback": "A prediction-then-feedback overlay on a practice card.",
    "path_progress": "Study-path progress across topics (roadmap cards).",
    "source_annotation": "An excerpt of uploaded material with annotations.",
    "topic_snapshot": "A static intro preview when the domain is generic.",
}


# ---------------------------------------------------------------------------
# VISUAL DOMAINS — set by the topic classifier; routes to a default base
# visual type. The card role can further override (e.g. a process card on
# a tree-domain topic might still use step_flow support visual).
# ---------------------------------------------------------------------------

VISUAL_DOMAINS: Final[tuple[str, ...]] = (
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
)


DOMAIN_TO_BASE_TYPE: Final[dict[str, str]] = {
    "tree": "node_link_diagram",
    "graph": "node_link_diagram",
    "linked_list": "node_link_diagram",
    "array": "indexed_sequence_diagram",
    "string": "indexed_sequence_diagram",
    "matrix": "grid_matrix_diagram",
    "table": "table_diagram",
    "memory": "memory_layout_diagram",
    "code": "code_execution_panel",
    "coordinate_math": "coordinate_graph",
    "geometry": "geometric_diagram",
    "formula": "formula_symbolic_expression",
    "timeline_protocol": "timeline_sequence_interaction",
    "set_logic": "set_region_diagram",
    "real_world": "image_real_world_illustration",
    "generic": "image_real_world_illustration",
}


DOMAIN_TO_DEFAULT_MODE: Final[dict[str, str]] = {
    "tree": "tree_hierarchy",
    "graph": "graph_network",
    "linked_list": "linked_list_chain",
    "array": "array_state",
    "string": "string_state",
    "matrix": "matrix",
    "table": "comparison_table",
    "memory": "stack_heap",
    "code": "code_execution_trace",
    "coordinate_math": "function_curve",
    "geometry": "triangle_geometry",
    "formula": "formula_breakdown",
    "timeline_protocol": "protocol_sequence",
    "set_logic": "venn_diagram",
    "real_world": "analogy_image",
    "generic": "topic_motivation",
}


# ---------------------------------------------------------------------------
# CARD ROLES — instructional jobs. Replaces the per-blueprint card_type
# branching in the legacy course_blueprints.py.
# ---------------------------------------------------------------------------

CARD_ROLES: Final[tuple[str, ...]] = (
    "background",
    "components_terms",
    "process",
    "worked_example",
    "code_walkthrough",
    "edge_case",
    "comparison",
    "practice",
    "takeaway",
)


# Visual behavior per role. The compiler uses this to decide whether the
# visual is static (one frame) or dynamic (many frames keyed to steps).
ROLE_TO_VISUAL_BEHAVIOR: Final[dict[str, str]] = {
    "background": "static_preview",
    "components_terms": "static_preview",
    "process": "support_or_text",
    "worked_example": "persistent_base_with_frames",
    "code_walkthrough": "growing_code",
    "edge_case": "boundary_static",
    "comparison": "static_preview",
    "practice": "prediction_feedback",
    "takeaway": "none",
}


# ---------------------------------------------------------------------------
# VALIDATION HELPERS — pure functions over the ontology, no side effects.
# ---------------------------------------------------------------------------

def is_valid_base_type(value: str) -> bool:
    return value in BASE_VISUAL_TYPES


def describe(value: str) -> str:
    """One-line description of a base type, mode, or support visual ('' if unknown)."""
    return (
        BASE_TYPE_DESCRIPTIONS.get(value)
        or MODE_DESCRIPTIONS.get(value)
        or SUPPORT_VISUAL_DESCRIPTIONS.get(value)
        or ""
    )


def is_valid_mode(base_type: str, mode: str) -> bool:
    return mode in MODES_BY_BASE_TYPE.get(base_type, ())


def is_valid_support_visual(value: str) -> bool:
    return value in SUPPORT_VISUALS


def is_valid_domain(value: str) -> bool:
    return value in VISUAL_DOMAINS


def is_valid_role(value: str) -> bool:
    return value in CARD_ROLES


def base_type_for_domain(domain: str) -> str:
    return DOMAIN_TO_BASE_TYPE.get(domain, "image_real_world_illustration")


def default_mode_for_domain(domain: str) -> str:
    return DOMAIN_TO_DEFAULT_MODE.get(domain, "topic_motivation")


def visual_behavior_for_role(role: str) -> str:
    return ROLE_TO_VISUAL_BEHAVIOR.get(role, "none")
