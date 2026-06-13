"""Example ontology — the single source of truth for the worked-example system.

In tandem with `app/core/visual_ontology_v2.py`. Where the visual ontology answers
"what is drawn and how," this answers "what is being worked through." Twelve example
types are the irreducible *shapes* of a worked example (the analogue of the 12 visual
base types); applications are the recognisable topics inside each (the analogue of
modes). See EXAMPLE_SYSTEM_SPEC.md §3.

Three axes (spec §3.2), kept distinct:
  - application = WHAT  (binary_search, unique_paths, quadratic_formula) — here.
  - pattern     = HOW   (range_halving, loop_execution, dp_table_fill)   — on the
                         ApplicationProfile (example_applications.py).
  - variant     = WHICH (insert, delete_two_child, bubble)               — on the
                         fixture (example_fixtures.py).

`code_execution_trace` is a *lens*, not a home for applications: its entries are
`execution_pattern` values, and the real application is the algorithm (binary_search,
bfs, inorder) carried over from its conceptual type and shown as code.

This file is pure data — no logic, no side effects on import.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# EXAMPLE TYPES — the 12 irreducible worked-example shapes (spec §3.1)
# ---------------------------------------------------------------------------

EXAMPLE_TYPES: Final[tuple[str, ...]] = (
    "sequence_state_trace",
    "node_link_trace",
    "grid_table_trace",
    "code_execution_trace",
    "memory_reference_trace",
    "symbolic_derivation",
    "coordinate_plot_analysis",
    "geometric_spatial_construction",
    "set_logic_region_reasoning",
    "case_comparison_example",
    "timeline_interaction_trace",
    "proof_reasoning_chain",
)


EXAMPLE_TYPE_DESCRIPTIONS: Final[dict[str, str]] = {
    "sequence_state_trace": "A 1-D ordered sequence where indices, ranges, pointers, or windows change over time.",
    "node_link_trace": "Nodes and edges where traversal, hierarchy, connectivity, or references change.",
    "grid_table_trace": "Values filled, updated, compared, or read across rows / columns / cells.",
    "code_execution_trace": "A line-by-line execution of real code — active lines, variables, calls, returns, output.",
    "memory_reference_trace": "Memory: stack/heap, references, pointers, object layout, addresses.",
    "symbolic_derivation": "Manipulating symbols, expressions, equations, or formulas step by step.",
    "coordinate_plot_analysis": "Constructing, reading, or analysing a graph on coordinate axes.",
    "geometric_spatial_construction": "Building or measuring shapes, angles, lengths, vectors, or regions.",
    "set_logic_region_reasoning": "Sets, events, logical regions, or probability spaces.",
    "case_comparison_example": "A composite pairing two+ cases / approaches / structures side by side.",
    "timeline_interaction_trace": "Actors, processes, threads, messages, or events unfolding over time.",
    "proof_reasoning_chain": "Deriving a conclusion through a chain of justified reasoning steps.",
}


# ---------------------------------------------------------------------------
# EXAMPLE_TYPE_TO_DEFAULT_VISUAL — tandem default (base_type, mode) per type.
# A profile's default_visual / a fixture's visual_override win (spec §3.3); this
# is only the fallback for unfixtured cases. Every pair MUST be a real entry in
# visual_ontology_v2.MODES_BY_BASE_TYPE (asserted by the load-time test).
# ---------------------------------------------------------------------------

EXAMPLE_TYPE_TO_DEFAULT_VISUAL: Final[dict[str, tuple[str, str]]] = {
    "sequence_state_trace": ("indexed_sequence_diagram", "array_state"),
    "node_link_trace": ("node_link_diagram", "graph_network"),
    "grid_table_trace": ("grid_matrix_diagram", "dp_table"),
    "code_execution_trace": ("code_execution_panel", "code_execution_trace"),
    "memory_reference_trace": ("memory_layout_diagram", "pointer_reference"),
    "symbolic_derivation": ("formula_symbolic_expression", "substitution"),
    "coordinate_plot_analysis": ("coordinate_graph", "function_curve"),
    "geometric_spatial_construction": ("geometric_diagram", "triangle_geometry"),
    "set_logic_region_reasoning": ("set_region_diagram", "venn_diagram"),
    "case_comparison_example": ("table_diagram", "comparison_table"),
    "timeline_interaction_trace": ("timeline_sequence_interaction", "protocol_sequence"),
    "proof_reasoning_chain": ("formula_symbolic_expression", "algebraic_transformation"),
}


# ---------------------------------------------------------------------------
# APPLICATIONS BY TYPE — the recognisable topics inside each shape (spec §3.2).
# NOTE: `code_execution_trace` is a lens — its entries are execution_pattern
# values (the HOW), not standalone applications; the real application is the
# algorithm from its conceptual type shown as code.
# ---------------------------------------------------------------------------

APPLICATIONS_BY_TYPE: Final[dict[str, tuple[str, ...]]] = {
    "sequence_state_trace": (
        "binary_search", "linear_search", "two_pointer", "sliding_window", "prefix_sum",
        "kadane", "sorting_pass", "merge_partition", "string_scan", "palindrome_check",
        "anagram_check",
    ),
    "node_link_trace": (
        "bfs", "dfs", "tree_traversal", "bst_operation", "heap_operation",
        "linked_list_operation", "trie_operation", "union_find", "shortest_path",
        "minimum_spanning_tree", "topological_sort", "state_machine_run", "automata_run",
    ),
    "grid_table_trace": (
        "unique_paths", "coin_change", "knapsack_01", "longest_common_subsequence",
        "edit_distance", "min_path_sum", "matrix_multiplication", "row_reduction",
        "floyd_warshall", "truth_table_evaluation", "sql_join", "confusion_matrix_metrics",
    ),
    "code_execution_trace": (  # execution_pattern values (the lens) — see module note
        "loop_execution", "function_call_trace", "recursive_execution", "nested_loop_execution",
        "condition_execution", "backtracking_execution", "dp_code_execution",
        "pointer_code_execution", "oop_method_execution",
    ),
    "memory_reference_trace": (
        "stack_heap_allocation", "pointer_assignment", "pointer_dereference", "object_layout",
        "array_memory_layout", "shallow_vs_deep_copy", "linked_structure_relinking",
        "cache_access", "virtual_memory_translation",
    ),
    "symbolic_derivation": (
        "quadratic_formula", "linear_equation", "system_elimination", "compound_interest",
        "distance_formula", "mean_variance", "bayes_formula", "chain_rule",
        "integration_by_parts", "big_o_simplification", "recurrence_expansion",
    ),
    "coordinate_plot_analysis": (
        "function_graph_analysis", "slope_or_derivative_at_point", "area_under_curve",
        "intersection_analysis", "distribution_reading", "regression_fit",
        "runtime_growth_comparison", "loss_curve_interpretation", "roc_curve_interpretation",
    ),
    "geometric_spatial_construction": (
        "triangle_geometry", "circle_geometry", "right_triangle_trig", "coordinate_geometry",
        "vector_operation", "projection", "linear_algebra_geometry", "solid_geometry",
        "integration_region", "optimization_geometry",
    ),
    "set_logic_region_reasoning": (
        "set_operation", "venn_counting", "conditional_probability", "bayes_reasoning",
        "inclusion_exclusion", "truth_region_reasoning", "classification_overlap", "logic_region",
    ),
    "case_comparison_example": (
        "algorithm_comparison", "data_structure_comparison", "approach_comparison",
        "valid_vs_invalid", "normal_vs_edge_case", "correct_vs_incorrect", "before_vs_after",
        "tradeoff_analysis",
    ),
    "timeline_interaction_trace": (
        "request_response_flow", "protocol_sequence", "thread_interleaving", "race_condition",
        "lock_acquisition", "transaction_timeline", "pipeline_flow", "scheduling_trace",
        "network_handshake",
    ),
    "proof_reasoning_chain": (
        "direct_proof", "contradiction_proof", "contrapositive_proof", "induction_proof",
        "strong_induction_proof", "loop_invariant_proof", "algorithm_correctness_proof",
        "set_equality_proof", "greedy_exchange_proof", "dp_recurrence_proof",
    ),
}


APPLICATION_DESCRIPTIONS: Final[dict[str, str]] = {
    # sequence_state_trace
    "binary_search": "Halve a sorted range each probe until the target is found or ruled out.",
    "linear_search": "Scan left→right comparing each element to the target.",
    "two_pointer": "Move two indices inward / at a lag to meet a pair or order condition.",
    "sliding_window": "Grow and shrink a contiguous window maintaining a running constraint.",
    "prefix_sum": "Build a running cumulative total to answer range queries.",
    "kadane": "Keep the best running subarray sum while scanning once.",
    "sorting_pass": "One pass of a comparison sort (bubble / selection / insertion).",
    "merge_partition": "The merge step of merge sort or the partition step of quick sort.",
    "string_scan": "Sweep a string tracking characters / frequencies (RLE, dedupe).",
    "palindrome_check": "Converge two ends comparing mirrored characters.",
    "anagram_check": "Count and compare character frequencies across two strings.",
    # node_link_trace
    "bfs": "Breadth-first frontier expansion: queue + visited, level order.",
    "dfs": "Depth-first descent: stack / recursion + visited.",
    "tree_traversal": "Inorder / preorder / postorder / level-order visit of a tree.",
    "bst_operation": "Search / insert / delete on a BST preserving its ordering.",
    "heap_operation": "Sift-up / sift-down on a binary heap (push / pop).",
    "linked_list_operation": "Traverse / insert / delete / reverse by relinking nodes.",
    "trie_operation": "Walk and extend prefix branches for a key.",
    "union_find": "Union-by-rank / path-compression over connectivity.",
    "shortest_path": "Relax edges to find least-cost paths (Dijkstra / Bellman-Ford).",
    "minimum_spanning_tree": "Grow a min-weight spanning tree by selecting edges (Prim / Kruskal).",
    "topological_sort": "Emit nodes in dependency order (Kahn / DFS finish).",
    "state_machine_run": "Follow an FSM's transitions on an input.",
    "automata_run": "Run a DFA / NFA, tracking the active state(s).",
    # grid_table_trace
    "unique_paths": "Count lattice paths by filling a DP grid from its recurrence.",
    "coin_change": "Min coins / number of ways via a DP table.",
    "knapsack_01": "Max value under a weight cap via a 2-D DP table.",
    "longest_common_subsequence": "LCS length via a 2-D DP table.",
    "edit_distance": "Minimum edits via a 2-D DP table.",
    "min_path_sum": "Least-cost grid path via DP.",
    "matrix_multiplication": "Multiply two matrices entry by entry.",
    "row_reduction": "Gaussian-eliminate a matrix to row-echelon form.",
    "floyd_warshall": "All-pairs shortest paths by relaxing a distance table.",
    "truth_table_evaluation": "Enumerate inputs and evaluate a logical expression per row.",
    "sql_join": "Join / filter / group rows of relations.",
    "confusion_matrix_metrics": "Read TP/FP/FN/TN cells to compute precision / recall.",
    # code_execution_trace (execution_pattern values)
    "loop_execution": "Step a for / while loop, tracking the loop variable and accumulator.",
    "function_call_trace": "Follow a call into a function and its return value.",
    "recursive_execution": "Trace recursion frames pushing / popping on the call stack.",
    "nested_loop_execution": "Step inner / outer loops building a result.",
    "condition_execution": "Evaluate an if/elif/else and take the live branch.",
    "backtracking_execution": "Choose → recurse → un-choose over a search space.",
    "dp_code_execution": "Run bottom-up / top-down DP code filling a table or memo.",
    "pointer_code_execution": "Execute in-place pointer / linked-structure relinking.",
    "oop_method_execution": "Dispatch a method or constructor on an object.",
    # memory_reference_trace
    "stack_heap_allocation": "Show where locals vs allocated objects live across a call.",
    "pointer_assignment": "Bind / rebind a pointer and what it now references.",
    "pointer_dereference": "Follow a pointer to read or write the pointed-to value.",
    "object_layout": "Lay out a struct / object's fields in memory.",
    "array_memory_layout": "Show contiguous elements and the index→address mapping.",
    "shallow_vs_deep_copy": "Compare which references are shared vs duplicated.",
    "linked_structure_relinking": "Repoint next / prev around an inserted or deleted node.",
    "cache_access": "Resolve an address to a cache line and hit / miss.",
    "virtual_memory_translation": "Translate a virtual address via the page table / TLB.",
    # symbolic_derivation
    "quadratic_formula": "Solve ax^2+bx+c=0 by substituting into the formula.",
    "linear_equation": "Isolate x through inverse operations.",
    "system_elimination": "Solve a 2-variable system by elimination / substitution.",
    "compound_interest": "Evaluate A = P(1 + r/n)^(nt).",
    "distance_formula": "Compute the distance between two points.",
    "mean_variance": "Compute the mean, then variance / std of a dataset.",
    "bayes_formula": "Update a probability with Bayes' rule.",
    "chain_rule": "Differentiate a composite function.",
    "integration_by_parts": "Integrate a product via the parts rule.",
    "big_o_simplification": "Drop constants and lower-order terms to a Big-O class.",
    "recurrence_expansion": "Unroll a recurrence toward a closed form (Master theorem).",
    # coordinate_plot_analysis
    "function_graph_analysis": "Plot and read a function's key features (intercepts, asymptotes).",
    "slope_or_derivative_at_point": "Find the slope / tangent at a point.",
    "area_under_curve": "Compute a definite integral / Riemann sum as area.",
    "intersection_analysis": "Locate where two curves meet.",
    "distribution_reading": "Read a probability distribution (z-score, area).",
    "regression_fit": "Fit and interpret a line through data points.",
    "runtime_growth_comparison": "Compare Big-O growth curves.",
    "loss_curve_interpretation": "Read a training loss curve over epochs.",
    "roc_curve_interpretation": "Read an ROC / precision-recall curve.",
    # geometric_spatial_construction
    "triangle_geometry": "Apply angle-sum / similarity / congruence to a triangle.",
    "circle_geometry": "Reason over radius / chord / tangent / arc / sector.",
    "right_triangle_trig": "Solve a right triangle (sine/cosine/tangent, law of sines/cosines).",
    "coordinate_geometry": "Compute midpoint / distance / slope on the plane.",
    "vector_operation": "Add vectors or take dot / cross products geometrically.",
    "projection": "Project a vector or point onto a line or subspace.",
    "linear_algebra_geometry": "Visualise span / basis / linear transformation / eigenvectors.",
    "solid_geometry": "Compute volume / surface area of a 3-D solid.",
    "integration_region": "Set up the region for area-between-curves / solid of revolution.",
    "optimization_geometry": "Find an optimum over a feasible region (incl. Lagrange).",
    # set_logic_region_reasoning
    "set_operation": "Compute union / intersection / complement / difference.",
    "venn_counting": "Count elements across overlapping Venn regions.",
    "conditional_probability": "Compute P(A|B) over a sample-space region.",
    "bayes_reasoning": "Update a probability with Bayes' rule.",
    "inclusion_exclusion": "Count a union via inclusion-exclusion.",
    "truth_region_reasoning": "Reason over logical regions / equivalences.",
    "classification_overlap": "Read TP / FP / FN regions for precision and recall.",
    "logic_region": "Evaluate predicate-logic membership regions.",
    # case_comparison_example
    "algorithm_comparison": "Run two algorithms on the same input to contrast time / space.",
    "data_structure_comparison": "Contrast structures on one operation (array vs list, BST vs hash).",
    "approach_comparison": "Contrast two solution styles (iterative vs recursive, top-down vs bottom-up).",
    "valid_vs_invalid": "Show an instance that satisfies vs violates the invariant.",
    "normal_vs_edge_case": "Contrast a typical run with a boundary run.",
    "correct_vs_incorrect": "Contrast a correct trace with a common buggy one.",
    "before_vs_after": "Contrast the state before and after a transformation.",
    "tradeoff_analysis": "Compare options across cost / benefit dimensions.",
    # timeline_interaction_trace
    "request_response_flow": "Trace a client<->server request and its response.",
    "protocol_sequence": "Step a protocol exchange (TCP / TLS / DNS / OAuth) message by message.",
    "thread_interleaving": "Show interleaved execution of concurrent threads.",
    "race_condition": "Expose a data race from a specific interleaving.",
    "lock_acquisition": "Trace mutex / semaphore acquire / release (and deadlock).",
    "transaction_timeline": "Commit / rollback a database transaction over time.",
    "pipeline_flow": "Move an item through pipeline stages.",
    "scheduling_trace": "Run a CPU scheduler (round-robin / priority) over a timeline.",
    "network_handshake": "Trace a connection handshake's stages.",
    # proof_reasoning_chain
    "direct_proof": "Derive the conclusion straight from the assumptions.",
    "contradiction_proof": "Assume the negation and derive a contradiction.",
    "contrapositive_proof": "Prove not-Q implies not-P in place of P implies Q.",
    "induction_proof": "Prove a base case, then the inductive step.",
    "strong_induction_proof": "Induct using all smaller cases.",
    "loop_invariant_proof": "Show an invariant holds before and after each iteration.",
    "algorithm_correctness_proof": "Argue an algorithm meets its specification.",
    "set_equality_proof": "Prove A = B by mutual inclusion.",
    "greedy_exchange_proof": "Justify a greedy choice via an exchange argument.",
    "dp_recurrence_proof": "Justify a DP recurrence's optimal substructure.",
}


# ---------------------------------------------------------------------------
# STEP ROLES — the semantic role vocabulary per example type (spec §3.4). The
# simulator/trace tags each grouped step with one of these; the roles drive the
# prose slots (§4.1) so the LLM explains a KIND of reasoning move, not "frame 4".
# ---------------------------------------------------------------------------

STEP_ROLES_BY_EXAMPLE_TYPE: Final[dict[str, tuple[str, ...]]] = {
    "sequence_state_trace": (
        "setup", "inspect_position", "make_comparison", "update_pointer_or_range",
        "repeat", "terminate", "return_output",
    ),
    "node_link_trace": (
        "setup", "select_active", "examine_neighbours", "enqueue_push", "visit_complete",
        "record_output", "terminate",
    ),
    "grid_table_trace": (
        "define_table", "initialize_base_case", "select_cell", "read_dependencies",
        "apply_rule", "write_cell", "read_final_answer",
    ),
    "code_execution_trace": (
        "bind_input", "enter_function", "execute_line", "evaluate_condition",
        "update_variable", "call_return", "produce_output",
    ),
    "memory_reference_trace": (
        "setup_memory_state", "allocate", "bind_reference", "dereference", "mutate_value",
        "update_aliases", "show_final_state",
    ),
    "symbolic_derivation": (
        "state_expression", "choose_rule", "apply_rule", "simplify", "substitute",
        "isolate", "state_result",
    ),
    "coordinate_plot_analysis": (
        "define_axes", "plot_object", "mark_feature", "compute_value", "interpret_feature",
        "conclude",
    ),
    "geometric_spatial_construction": (
        "draw_base_figure", "label_knowns", "add_helper_element", "apply_property",
        "compute_measure", "conclude",
    ),
    "set_logic_region_reasoning": (
        "define_universe", "mark_regions", "apply_operation", "count_region",
        "compute_probability", "conclude",
    ),
    "case_comparison_example": (
        "setup_cases", "run_left_case", "run_right_case", "compare_dimension", "extract_rule",
        "conclude",
    ),
    "timeline_interaction_trace": (
        "setup_actors", "send_event", "receive_event", "update_state", "expose_interleaving",
        "conclude",
    ),
    "proof_reasoning_chain": (
        "state_claim", "state_assumption", "apply_definition", "derive_step", "justify_step",
        "conclude",
    ),
}


# ---------------------------------------------------------------------------
# Helpers — mirror visual_ontology_v2.describe / is_valid_* (pure lookups).
# ---------------------------------------------------------------------------

def is_valid_example_type(value: str) -> bool:
    return value in EXAMPLE_TYPES


def is_valid_application(value: str) -> bool:
    return any(value in apps for apps in APPLICATIONS_BY_TYPE.values())


def example_type_of(application: str) -> str | None:
    """The example type that owns this application, or None."""
    for example_type, apps in APPLICATIONS_BY_TYPE.items():
        if application in apps:
            return example_type
    return None


def describe(value: str) -> str:
    """One-line description for an example type or application; '' if unknown."""
    if value in EXAMPLE_TYPE_DESCRIPTIONS:
        return EXAMPLE_TYPE_DESCRIPTIONS[value]
    return APPLICATION_DESCRIPTIONS.get(value, "")
