"""Per-mode profiles (VISUAL_SYSTEM_SPEC §3.2, §5.7, §6.5).

The single place where per-subtype render rules live, keyed by `mode` — so
"letters vs digits", "which panel", layout, the allowed delta vocabulary, and the
richness floors are table lookups, not per-type code. Slice 1 defines
`graph_network`; new modes are a new row + a registered simulator, not a new
pipeline.
"""
from __future__ import annotations

from typing import Any

MODE_PROFILES: dict[str, dict[str, Any]] = {
    "graph_network": {
        "base_type": "node_link_diagram",
        "layout": "spread",
        "labels": "letters",
        "node_states": ["unvisited", "discovered", "current", "completed"],
        "panels": ["current", "frontier", "output"],
        # Allowed delta operations for this mode (plus the shared no_op form).
        "delta_vocabulary": [
            "set_active",
            "add_to_frontier",
            "remove_from_frontier",
            "newly_visited",
            "append_to_output",
            "set_active_edge",     # PROJECTOR_SYSTEM_SPEC §4.1 — edge-selection algos
            "add_selected_edge",
        ],
        # Richness floor (§5.7) — too-trivial examples fail this.
        "richness": {"min_nodes": 5, "min_branching": 1},
    },
    # Generic array-scan diagram from a code trace (SequenceProjection, §13): named
    # cursors moving over a fixed array (two-pointer / sliding-window / linear scan).
    "indexed_sequence_scan": {
        "base_type": "indexed_sequence_diagram",
        "layout": "linear",
        "labels": "numbers",
        "cell_states": ["active", "in_window", "marked"],
        "panels": ["pointers"],
        "delta_vocabulary": ["set_cursor", "set_window", "mark_cells"],
        "richness": {"min_length": 3},
    },
    "binary_search_range": {
        "base_type": "indexed_sequence_diagram",
        "layout": "linear",
        "labels": "numbers",
        "cell_states": ["active", "mid", "discarded", "found", "in_range"],
        "panels": ["pointers"],
        "delta_vocabulary": [
            "set_pointer",
            "set_vars",
            "mark_mid",
            "shrink_range",
            "mark_discarded",
            "mark_found",
        ],
        "richness": {"min_length": 7},
    },
    "dp_table": {
        "base_type": "grid_matrix_diagram",
        "layout": "grid",
        "labels": "indices",
        "panels": [],
        "delta_vocabulary": ["set_active_cell", "fill_cell", "complete_cell", "set_dependency_arrows"],
        "richness": {"min_cells": 4},
    },
    "formula_substitution": {
        "base_type": "formula_symbolic_expression",
        "layout": "derivation",
        "labels": "symbols",
        "panels": [],
        "delta_vocabulary": ["set_substituted", "add_computation", "set_result"],
        "richness": {"min_steps": 4},
    },
    "venn_diagram": {
        "base_type": "set_region_diagram",
        "layout": "venn",
        "labels": "sets",
        "panels": [],
        "delta_vocabulary": ["set_active_set", "set_shaded_regions", "set_region_counts"],
        "richness": {"min_steps": 3},
    },
    "function_curve": {
        "base_type": "coordinate_graph",
        "layout": "axes",
        "labels": "coordinates",
        "panels": [],
        "delta_vocabulary": ["set_active_curve", "set_active_point", "set_point_value"],
        "richness": {"min_steps": 3},
    },
    "stack_heap": {
        "base_type": "memory_layout_diagram",
        "layout": "memory",
        "labels": "addresses",
        "panels": [],
        "delta_vocabulary": ["set_visible_frames", "set_visible_objects", "set_active_object", "set_active_pointer"],
        "richness": {"min_steps": 3},
    },
    "protocol_sequence": {
        "base_type": "timeline_sequence_interaction",
        "layout": "timeline",
        "labels": "actors",
        "panels": [],
        "delta_vocabulary": ["set_active_message", "set_visible_messages", "set_actor_states"],
        "richness": {"min_steps": 3},
    },
    "triangle_geometry": {
        "base_type": "geometric_diagram",
        "layout": "figure",
        "labels": "vertices",
        "panels": [],
        "delta_vocabulary": ["set_active_segment", "set_active_point", "add_measurement", "set_shaded_regions"],
        "richness": {"min_steps": 3},
    },
    "comparison_table": {
        "base_type": "table_diagram",
        "layout": "table",
        "labels": "columns",
        "panels": [],
        "delta_vocabulary": ["set_active_row"],
        "richness": {"min_steps": 3},
    },
    "code_execution": {
        "base_type": "code_execution_panel",
        "layout": "code_panel",
        "labels": "line_numbers",
        "panels": ["variables", "call_stack", "output"],
        "delta_vocabulary": [
            "set_highlight_lines",
            "set_locals",
            "set_call_stack",
            "set_output",
            "append_output",
        ],
        "richness": {"min_steps": 4},
    },
}

# Shared, mode-independent delta keys (apply everywhere).
SHARED_DELTA_OPS = {"no_op", "checked_element_ids", "reason"}


def profile_for_mode(mode: str) -> dict[str, Any] | None:
    return MODE_PROFILES.get(mode)


def delta_vocabulary(mode: str) -> set[str]:
    """Allowed delta operation keys for a mode (mode ops + shared ops)."""
    profile = MODE_PROFILES.get(mode) or {}
    return set(profile.get("delta_vocabulary") or ()) | SHARED_DELTA_OPS
