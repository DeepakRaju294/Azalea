"""Application profiles + title→application patterns (EXAMPLE_SYSTEM_SPEC.md §3.4, §5.1).

An `ApplicationProfile` holds the reusable rules every fixture of an application
inherits (the WHAT's defaults + its code lens). `APPLICATION_PATTERNS` maps a topic
title to an application (the WHAT), first-hit in a defined priority order.

Pure data + compiled regexes; importing has no side effects beyond regex compile.
This phase seeds the first slice; widen application-by-application (spec §9.4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final, Optional

from app.core import example_ontology as eo

Visual = tuple[str, str]  # (base_type, mode), real in visual_ontology_v2


@dataclass(frozen=True)
class ApplicationProfile:
    """The reusable rules an application owns (spec §3.4). A fixture inherits these.

    The *conceptual* lens fields (example_type/pattern/default_visual/algorithm) are
    used for concept topics; the *code* lens fields (code_*) are used when a
    coding_implementation topic resolves this application to `code_execution_trace`.
    """

    application: str
    example_type: str                      # conceptual lens (spec §3.1)
    pattern: str                           # conceptual run-shape (the HOW)
    default_visual: Visual                 # tandem target for the conceptual lens
    algorithm: Optional[str] = None        # simulator-registry key for the conceptual trace
    trace_authority: str = "simulator"     # simulator | deterministic_eval | llm_validated
    # Code lens (optional): present iff the application can be shown as runnable code.
    code_example_type: Optional[str] = None
    code_pattern: Optional[str] = None
    code_visual: Optional[Visual] = None
    code_algorithm: Optional[str] = None   # "code_execution" (the tracer)
    # Sub-operations whose traces differ; a fixture MUST set `variant` if non-empty.
    variants: tuple[str, ...] = ()
    # How raw frames group into cards (spec §3.4); generalises _milestone_frame_indices.
    milestone_policy: str = "every_state_change"

    def __post_init__(self) -> None:
        assert eo.is_valid_application(self.application), self.application
        assert eo.is_valid_example_type(self.example_type), self.example_type
        if self.code_example_type is not None:
            assert self.code_example_type == "code_execution_trace", self.code_example_type

    @property
    def step_roles(self) -> tuple[str, ...]:
        return eo.STEP_ROLES_BY_EXAMPLE_TYPE[self.example_type]


# ---------------------------------------------------------------------------
# APPLICATION_PROFILES — the first slice. The four sim-ready applications already
# have a registered simulator (visual_v2/simulators/registry.py); quadratic_formula
# is deterministic_eval (its simulator + compiler land in Phase 6).
# ---------------------------------------------------------------------------

_CODE_VISUAL: Final[Visual] = ("code_execution_panel", "code_execution_trace")

APPLICATION_PROFILES: Final[dict[str, ApplicationProfile]] = {
    "binary_search": ApplicationProfile(
        application="binary_search",
        example_type="sequence_state_trace",
        pattern="range_halving",
        default_visual=("indexed_sequence_diagram", "binary_search_range"),
        algorithm="binary_search",
        code_example_type="code_execution_trace",
        code_pattern="loop_execution",
        code_visual=_CODE_VISUAL,
        code_algorithm="code_execution",
        milestone_policy="grouped_by_iteration",
    ),
    "bfs": ApplicationProfile(
        application="bfs",
        example_type="node_link_trace",
        pattern="frontier_expansion",
        default_visual=("node_link_diagram", "graph_network"),
        algorithm="bfs",
        code_example_type="code_execution_trace",
        code_pattern="loop_execution",
        code_visual=_CODE_VISUAL,
        code_algorithm="code_execution",
        milestone_policy="grouped_by_frontier_level",
    ),
    "dfs": ApplicationProfile(
        application="dfs",
        example_type="node_link_trace",
        pattern="frontier_expansion",
        default_visual=("node_link_diagram", "graph_network"),
        algorithm="dfs",
        code_example_type="code_execution_trace",
        code_pattern="recursive_execution",
        code_visual=_CODE_VISUAL,
        code_algorithm="code_execution",
        milestone_policy="grouped_by_iteration",
    ),
    "tree_traversal": ApplicationProfile(
        application="tree_traversal",
        example_type="node_link_trace",
        pattern="tree_walk",
        default_visual=("node_link_diagram", "tree_hierarchy"),
        algorithm=None,  # no conceptual tree-traversal simulator yet — code lens only
        code_example_type="code_execution_trace",
        code_pattern="recursive_execution",
        code_visual=_CODE_VISUAL,
        code_algorithm="code_execution",
        milestone_policy="every_state_change",
    ),
    "unique_paths": ApplicationProfile(
        application="unique_paths",
        example_type="grid_table_trace",
        pattern="dp_table_fill",
        default_visual=("grid_matrix_diagram", "dp_table"),
        algorithm="unique_paths",
        milestone_policy="grouped_by_cell",
    ),
    "quadratic_formula": ApplicationProfile(
        application="quadratic_formula",
        example_type="symbolic_derivation",
        pattern="formula_substitution",
        default_visual=("formula_symbolic_expression", "substitution"),
        algorithm="quadratic_formula",
        trace_authority="deterministic_eval",
        milestone_policy="every_state_change",
    ),
    "linear_equation": ApplicationProfile(
        application="linear_equation",
        example_type="symbolic_derivation",
        pattern="equation_solving",
        default_visual=("formula_symbolic_expression", "substitution"),
        algorithm="linear_equation",
        trace_authority="deterministic_eval",
        milestone_policy="every_state_change",
    ),
    "distance_formula": ApplicationProfile(
        application="distance_formula",
        example_type="symbolic_derivation",
        pattern="formula_substitution",
        default_visual=("formula_symbolic_expression", "substitution"),
        algorithm="distance_formula",
        trace_authority="deterministic_eval",
        milestone_policy="every_state_change",
    ),
    "compound_interest": ApplicationProfile(
        application="compound_interest",
        example_type="symbolic_derivation",
        pattern="formula_substitution",
        default_visual=("formula_symbolic_expression", "substitution"),
        algorithm="compound_interest",
        trace_authority="deterministic_eval",
        milestone_policy="every_state_change",
    ),
    "linear_search": ApplicationProfile(
        application="linear_search",
        example_type="sequence_state_trace",
        pattern="linear_scan",
        default_visual=("indexed_sequence_diagram", "array_state"),
        algorithm=None,  # no conceptual simulator yet — code lens only
        code_example_type="code_execution_trace",
        code_pattern="loop_execution",
        code_visual=_CODE_VISUAL,
        code_algorithm="code_execution",
        milestone_policy="grouped_by_iteration",
    ),
    "coin_change": ApplicationProfile(
        application="coin_change",
        example_type="grid_table_trace",
        pattern="dp_table_fill",
        default_visual=("grid_matrix_diagram", "dp_table"),
        algorithm="coin_change",
        milestone_policy="grouped_by_cell",
    ),
    # --- the six remaining example-type verticals (§9.4) ---
    "set_operation": ApplicationProfile(
        application="set_operation",
        example_type="set_logic_region_reasoning",
        pattern="set_counting",
        default_visual=("set_region_diagram", "venn_diagram"),
        algorithm="set_operation",
        trace_authority="deterministic_eval",
        milestone_policy="every_state_change",
    ),
    "function_graph_analysis": ApplicationProfile(
        application="function_graph_analysis",
        example_type="coordinate_plot_analysis",
        pattern="plot_analysis",
        default_visual=("coordinate_graph", "function_curve"),
        algorithm="function_graph_analysis",
        trace_authority="deterministic_eval",
        milestone_policy="every_state_change",
    ),
    "stack_heap_allocation": ApplicationProfile(
        application="stack_heap_allocation",
        example_type="memory_reference_trace",
        pattern="memory_reveal",
        default_visual=("memory_layout_diagram", "stack_heap"),
        algorithm="stack_heap_allocation",
        trace_authority="deterministic_eval",
        milestone_policy="every_state_change",
    ),
    "protocol_sequence": ApplicationProfile(
        application="protocol_sequence",
        example_type="timeline_interaction_trace",
        pattern="protocol_exchange",
        default_visual=("timeline_sequence_interaction", "protocol_sequence"),
        algorithm="protocol_sequence",
        trace_authority="deterministic_eval",
        milestone_policy="every_state_change",
    ),
    "triangle_geometry": ApplicationProfile(
        application="triangle_geometry",
        example_type="geometric_spatial_construction",
        pattern="construction",
        default_visual=("geometric_diagram", "triangle_geometry"),
        algorithm="triangle_geometry",
        trace_authority="deterministic_eval",
        milestone_policy="every_state_change",
    ),
    "induction_proof": ApplicationProfile(
        application="induction_proof",
        example_type="proof_reasoning_chain",
        pattern="induction",
        default_visual=("formula_symbolic_expression", "substitution"),
        algorithm="induction_proof",
        trace_authority="deterministic_eval",
        milestone_policy="every_state_change",
    ),
    "algorithm_comparison": ApplicationProfile(
        application="algorithm_comparison",
        example_type="case_comparison_example",
        pattern="contrast_table",
        default_visual=("table_diagram", "comparison_table"),
        algorithm="algorithm_comparison",
        trace_authority="deterministic_eval",
        milestone_policy="every_state_change",
    ),
    # --- projected node_link verticals (PROJECTOR_SYSTEM_SPEC §7, T2) ---
    # No registered simulator: the conceptual trace is computed by running verified
    # code through the tracer + a GraphProjection (default_visual mode graph_projection).
    # The rendered visual IS a graph_network node_link (a real ontology pair); only the
    # *pipeline* mode is graph_projection, set by the handoff when a fixture carries a
    # GraphProjection. So default_visual stays graph_network here.
    "minimum_spanning_tree": ApplicationProfile(
        application="minimum_spanning_tree",
        example_type="node_link_trace",
        pattern="edge_selection",
        default_visual=("node_link_diagram", "graph_network"),
        algorithm=None,
        trace_authority="llm_validated",   # projection-driven, validated (§6.3 + guardrail)
        milestone_policy="every_state_change",
    ),
    "shortest_path": ApplicationProfile(
        application="shortest_path",
        example_type="node_link_trace",
        pattern="edge_relaxation",
        default_visual=("node_link_diagram", "graph_network"),
        algorithm=None,
        trace_authority="llm_validated",
        milestone_policy="every_state_change",
    ),
}


# ---------------------------------------------------------------------------
# APPLICATION_PATTERNS — title → application (spec §5.1). Ordered, first-hit;
# most specific first. The declaration tests assert no two claim the same title.
# ---------------------------------------------------------------------------

_PATTERN_SOURCES: Final[tuple[tuple[str, str], ...]] = (
    ("binary_search", r"\bbinary\s+search\b"),
    ("linear_search", r"\blinear\s+search\b"),
    ("unique_paths", r"\bunique\s+paths\b"),
    ("coin_change", r"\bcoin\s+change\b|\bfewest\s+coins\b|\bmin(imum)?\s+coins\b"),
    ("quadratic_formula", r"\bquadratic\s+(formula|equation)s?\b"),
    ("linear_equation", r"\blinear\s+equations?\b|\bone[\s-]*variable\s+equations?\b"),
    ("distance_formula", r"\bdistance\s+formula\b|\bdistance\s+between\s+(two\s+)?points\b"),
    ("compound_interest", r"\bcompound\s+interest\b"),
    ("tree_traversal", r"\b(in|pre|post)\s*-?\s*order\b|\btree\s+traversal\b|\blevel\s*-?\s*order\b"),
    ("minimum_spanning_tree", r"\bminimum\s+spanning\s+tree\b|\bmst\b|\bprim'?s?\b|\bkruskal'?s?\b"),
    ("shortest_path", r"\bshortest\s+path\b|\bdijkstra'?s?\b|\bbellman[\s-]*ford\b"),
    # A BFS↔DFS comparison must win over the single-algorithm patterns (both named).
    ("algorithm_comparison", r"(\bbfs\b|\bbreadth).{0,40}(\bdfs\b|\bdepth)|(\bdfs\b|\bdepth).{0,40}(\bbfs\b|\bbreadth)"),
    ("bfs", r"\bbfs\b|\bbreadth[\s-]*first\b"),
    ("dfs", r"\bdfs\b|\bdepth[\s-]*first\b"),
    # remaining type verticals
    ("set_operation", r"\bset\s+(operations?|theory)\b|\bunion\s+and\s+intersection\b|\bvenn\b"),
    ("function_graph_analysis", r"\bparabola\b|\bgraph(ing|s)?\s+(a\s+)?(quadratic|parabola)|\bquadratic\s+graph\b"),
    ("stack_heap_allocation", r"\bstack\s+(and|vs\.?|versus)\s+heap\b|\bheap\s+allocation\b|\bmemory\s+allocation\b"),
    ("protocol_sequence", r"\btcp\b|\bthree[\s-]*way\s+handshake\b|\bhandshake\b"),
    ("triangle_geometry", r"\bpythagore(an|as)\b|\bright\s+triangle\b|\bhypotenuse\b"),
    ("induction_proof", r"\b(mathematical\s+)?induction\b|\bproof\s+by\s+induction\b"),
)

APPLICATION_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = tuple(
    (app, re.compile(src, re.IGNORECASE)) for app, src in _PATTERN_SOURCES
)


def match_application(title: str) -> Optional[str]:
    """First application whose pattern matches the title, in priority order."""
    text = title or ""
    for application, pattern in APPLICATION_PATTERNS:
        if pattern.search(text):
            return application
    return None
