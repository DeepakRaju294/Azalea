"""Snapshot + behavior tests for Visual System V2 compilers.

These extend the contract tests in test_visual_compilers_v2.py with:

  1. Coordinate-stability checks (element bounds don't teleport
     across frames without a corresponding `move` transition).
  2. Element-id stability across frames (the same conceptual element
     keeps the same element_id from frame 0 through the last frame).
  3. Animation-emission checks (every non-first frame emits at least
     one transition for dynamic visuals).
  4. Synthesizer fallback checks for indexed_sequence, code_execution,
     and grid_matrix (the new synthesizers added alongside node_link).
  5. Cross-card model reuse checks (already_compiled_models lookups).

These tests intentionally do NOT do byte-level snapshot comparison
against stored JSON. Compiler output evolves; structural assertions
catch real regressions without breaking on cosmetic field reorderings.
"""

from __future__ import annotations

import copy
import unittest

from app.core.visual_ontology_v2 import BASE_VISUAL_TYPES
from app.services.visual_compilers import get_compiler


# ---------------------------------------------------------------------------
# Synthetic plan fixtures (same shape as v2_e2e_smoke._SYNTHETIC_BASE_STATES)
# ---------------------------------------------------------------------------

_SYNTH_BASES: dict[str, dict] = {
    "node_link_diagram": {
        "mode": "tree_hierarchy",
        "base_state": {
            "nodes": [
                {"id": "A", "label": "A", "relation": "root", "x": 50.0, "y": 16.0},
                {"id": "B", "label": "B", "relation": "node", "x": 28.0, "y": 42.0},
            ],
            "edges": [{"from": "A", "to": "B", "label": "", "style": "solid"}],
        },
        "steps_after": [
            {
                "active_node": "A",
                "completed_nodes": [],
                "node_state_map": [{"node_id": "A", "state": "current"}],
            },
            {
                "active_node": "B",
                "completed_nodes": ["A"],
                "node_state_map": [
                    {"node_id": "A", "state": "completed"},
                    {"node_id": "B", "state": "current"},
                ],
            },
        ],
    },
    "indexed_sequence_diagram": {
        "mode": "array_state",
        "base_state": {
            "values": ["1", "3", "5", "7", "9"],
            "pointer_definitions": [{"id": "l", "label": "left"}, {"id": "r", "label": "right"}],
        },
        "steps_after": [
            {
                "pointers": [{"id": "l", "position": 0, "label": "left"}],
                "ranges": [],
                "highlighted_cells": [0],
                "swapped_cells": None,
                "sorted_prefix_end": None,
            },
            {
                "pointers": [{"id": "l", "position": 2, "label": "left"}],
                "ranges": [],
                "highlighted_cells": [2],
                "swapped_cells": None,
                "sorted_prefix_end": None,
            },
        ],
    },
    "code_execution_panel": {
        "mode": "code_execution_trace",
        "base_state": {
            "code": "def f(n):\n    return n + 1\n",
            "language": "python",
        },
        "steps_after": [
            {"visible_until_line": 2, "highlight_lines": [1, 1], "variables": [], "call_stack": [], "output": []},
            {"visible_until_line": 2, "highlight_lines": [2, 2], "variables": [{"name": "n", "value": "5"}], "call_stack": [], "output": []},
        ],
    },
    "grid_matrix_diagram": {
        "mode": "matrix",
        "base_state": {
            "cells": [["0", "0"], ["0", "0"]],
            "row_labels": ["r0", "r1"],
            "column_labels": ["c0", "c1"],
        },
        "steps_after": [
            {"active_cell": [0, 0], "completed_cells": [], "dependency_arrows": [], "highlighted_row": None, "highlighted_column": None, "cell_values": {}},
            {"active_cell": [0, 1], "completed_cells": [[0, 0]], "dependency_arrows": [], "highlighted_row": None, "highlighted_column": None, "cell_values": {}},
        ],
    },
}


def _intent(base_type: str, mode: str, kind: str = "dynamic") -> dict:
    return {
        "base_type": base_type,
        "mode": mode,
        "description": f"Test {base_type}",
        "purpose": "Snapshot test",
        "static_or_dynamic": kind,
    }


def _plan(base_type: str) -> dict:
    fixture = _SYNTH_BASES[base_type]
    return {
        "id": f"plan_{base_type}",
        "visual_intent": _intent(base_type, fixture["mode"]),
        "problem_setup": "Setup",
        "terminal_state": "Done",
        "base_state": fixture["base_state"],
        "steps": [
            {
                "step_number": i + 1,
                "action": f"Step {i + 1}",
                "reason": "Snapshot test",
                "text_points": [f"point {i + 1}"],
                "state_after": state,
                "transition_hints": [],
            }
            for i, state in enumerate(fixture["steps_after"])
        ],
    }


def _ctx(topic_id: str = "snap-test", already: dict | None = None) -> dict:
    return {
        "topic_id": topic_id,
        "topic_hint": "",
        "topic_type": "algorithm_walkthrough",
        "visual_domain": "generic",
        "source_chunks_excerpt": "",
        "already_compiled_models": already or {},
    }


# ===========================================================================
# 1 + 2 + 3. Coordinate stability, element-id stability, transitions
# ===========================================================================

class SnapshotInvariantsTests(unittest.TestCase):

    def test_element_id_stability_across_frames(self):
        """An element_id present in frame 0 should still be present in
        the final frame (compiler isn't dropping/renaming elements)."""
        for base_type in _SYNTH_BASES:
            with self.subTest(base_type=base_type):
                compiler = get_compiler(base_type)
                intent = _intent(base_type, _SYNTH_BASES[base_type]["mode"])
                model = compiler.compile(intent, _plan(base_type), _ctx())
                frames = model["frames"]
                if len(frames) < 2:
                    continue

                # Pick element ids that should persist (nodes, cells, lines).
                first_persistent = {
                    el["element_id"]
                    for el in frames[0]["selectable_elements"]
                    if el["element_type"] in (
                        "node", "cell", "code_line", "pointer", "symbol_definition",
                    )
                }
                last_persistent = {
                    el["element_id"]
                    for el in frames[-1]["selectable_elements"]
                    if el["element_type"] in (
                        "node", "cell", "code_line", "pointer", "symbol_definition",
                    )
                }
                # Allow new elements to appear; what we don't want is a
                # persistent-element drop without a `disappear` transition.
                disappear_targets = {
                    t["target_element_id"]
                    for f in frames[1:]
                    for t in f["transitions"]
                    if t["kind"] in ("disappear", "fade_out")
                }
                missing = first_persistent - last_persistent - disappear_targets
                self.assertFalse(
                    missing,
                    f"{base_type}: elements vanished without disappear transitions: {missing}",
                )

    def test_coordinate_stability(self):
        """Same element_id across frames keeps same bounds (no teleport)
        for non-pointer types — pointers legitimately move."""
        STABLE_TYPES = {"node", "cell", "code_line", "symbol_definition", "row_header", "column_header"}
        for base_type in _SYNTH_BASES:
            with self.subTest(base_type=base_type):
                compiler = get_compiler(base_type)
                intent = _intent(base_type, _SYNTH_BASES[base_type]["mode"])
                model = compiler.compile(intent, _plan(base_type), _ctx())
                positions: dict[str, tuple[float, float]] = {}
                for frame in model["frames"]:
                    for el in frame["selectable_elements"]:
                        if el["element_type"] not in STABLE_TYPES:
                            continue
                        eid = el["element_id"]
                        pos = (el["bounds"]["x"], el["bounds"]["y"])
                        prev = positions.get(eid)
                        if prev is not None:
                            self.assertAlmostEqual(
                                prev[0], pos[0], delta=1.0,
                                msg=f"{base_type}: element {eid} x changed without transition",
                            )
                            self.assertAlmostEqual(
                                prev[1], pos[1], delta=1.0,
                                msg=f"{base_type}: element {eid} y changed without transition",
                            )
                        positions[eid] = pos

    def test_dynamic_visuals_emit_transitions_after_frame_zero(self):
        """For dynamic visuals with >1 frame, non-first frames should
        emit at least one transition (otherwise nothing animates)."""
        for base_type in _SYNTH_BASES:
            with self.subTest(base_type=base_type):
                compiler = get_compiler(base_type)
                intent = _intent(base_type, _SYNTH_BASES[base_type]["mode"])
                model = compiler.compile(intent, _plan(base_type), _ctx())
                frames = model["frames"]
                if len(frames) < 2:
                    continue
                self.assertEqual(
                    frames[0]["transitions"], [],
                    f"{base_type}: frame 0 should have no transitions",
                )
                later_transition_counts = [
                    len(f["transitions"]) for f in frames[1:]
                ]
                self.assertGreater(
                    sum(later_transition_counts), 0,
                    f"{base_type}: no transitions emitted past frame 0",
                )


# ===========================================================================
# 4. Synthesizer fallbacks
# ===========================================================================

class SynthesizerFallbackTests(unittest.TestCase):

    def test_node_link_synthesizer_reconstructs_from_background(self):
        compiler = get_compiler("node_link_diagram")
        legacy = [
            {
                "blueprint_key": "background",
                "visual_type": "node_link_diagram",
                "visual_nodes": [
                    {"id": "A", "label": "A", "relation": "root", "x": 50, "y": 16},
                    {"id": "B", "label": "B", "relation": "node", "x": 28, "y": 42},
                ],
                "visual_edges": [{"from": "A", "to": "B"}],
            },
            {
                "blueprint_key": "worked_example",
                "title": "Step 1",
                "points": ["current=A", "Call stack: [A]"],
            },
        ]
        plan = compiler.synthesize_plan_from_legacy_cards(legacy, _ctx())
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan["base_state"]["nodes"]), 2)
        self.assertEqual(len(plan["steps"]), 1)

    def test_indexed_sequence_synthesizer_extracts_pointers(self):
        compiler = get_compiler("indexed_sequence_diagram")
        legacy = [
            {
                "blueprint_key": "background",
                "visual_type": "array_state_diagram",
                "visual_array_values": ["1", "3", "5", "7", "9"],
                "visual_array_pointers": [
                    {"id": "l", "label": "left"},
                    {"id": "r", "label": "right"},
                ],
            },
            {
                "blueprint_key": "worked_example",
                "title": "Step 1",
                "points": ["l=0, r=4, m=2"],
            },
        ]
        plan = compiler.synthesize_plan_from_legacy_cards(legacy, _ctx())
        self.assertIsNotNone(plan)
        self.assertEqual(plan["base_state"]["values"], ["1", "3", "5", "7", "9"])
        self.assertEqual(len(plan["steps"]), 1)
        pointers = plan["steps"][0]["state_after"]["pointers"]
        self.assertEqual({p["id"] for p in pointers}, {"l", "r"})

    def test_code_execution_synthesizer_extracts_highlights(self):
        compiler = get_compiler("code_execution_panel")
        legacy = [
            {
                "blueprint_key": "code_walkthrough",
                "code_snippet": "def f(n):\n    return n + 1\n",
                "code_language": "python",
            },
            {
                "blueprint_key": "worked_example",
                "title": "Call f(3)",
                "points": ["line 2: returns n + 1"],
                "highlight_lines_per_step": [[2, 2]],
            },
        ]
        plan = compiler.synthesize_plan_from_legacy_cards(legacy, _ctx())
        self.assertIsNotNone(plan)
        self.assertIn("def f(n)", plan["base_state"]["code"])
        self.assertEqual(plan["steps"][0]["state_after"]["highlight_lines"], [2, 2])

    def test_grid_matrix_synthesizer_extracts_cell_coordinates(self):
        compiler = get_compiler("grid_matrix_diagram")
        legacy = [
            {
                "blueprint_key": "background",
                "visual_type": "comparison_table",
                "visual_columns": ["c0", "c1"],
                "visual_rows": [["0", "0"], ["0", "0"]],
            },
            {
                "blueprint_key": "worked_example",
                "title": "Fill 0,0",
                "points": ["process cell [0, 0]"],
            },
            {
                "blueprint_key": "worked_example",
                "title": "Fill 0,1",
                "points": ["process cell [0, 1]"],
            },
        ]
        plan = compiler.synthesize_plan_from_legacy_cards(legacy, _ctx())
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan["steps"]), 2)
        self.assertEqual(plan["steps"][0]["state_after"]["active_cell"], [0, 0])
        self.assertEqual(plan["steps"][1]["state_after"]["completed_cells"], [[0, 0], [0, 1]])

    def test_synthesizers_return_none_without_background_structure(self):
        for base_type in ("indexed_sequence_diagram", "code_execution_panel", "grid_matrix_diagram"):
            compiler = get_compiler(base_type)
            plan = compiler.synthesize_plan_from_legacy_cards([], _ctx())
            self.assertIsNone(plan, f"{base_type}: should return None for empty cards")


# ===========================================================================
# 5. Cross-card model reuse
# ===========================================================================

class CrossCardReuseTests(unittest.TestCase):

    def _build_first_model(self, base_type: str) -> dict:
        compiler = get_compiler(base_type)
        intent = _intent(base_type, _SYNTH_BASES[base_type]["mode"])
        return compiler.compile(intent, _plan(base_type), _ctx())

    def test_indexed_sequence_reuses_background(self):
        first = self._build_first_model("indexed_sequence_diagram")
        compiler = get_compiler("indexed_sequence_diagram")
        # Compile a static card (plan=None) with the prior model in context
        intent = _intent("indexed_sequence_diagram", "array_state", kind="static")
        ctx = _ctx(already={first["id"]: first})
        second = compiler.compile(intent, None, ctx)
        self.assertEqual(
            second["base"]["values"], first["base"]["values"],
            "indexed_sequence: should reuse background values",
        )

    def test_code_execution_reuses_background(self):
        first = self._build_first_model("code_execution_panel")
        compiler = get_compiler("code_execution_panel")
        intent = _intent("code_execution_panel", "code_execution_trace", kind="static")
        ctx = _ctx(already={first["id"]: first})
        second = compiler.compile(intent, None, ctx)
        self.assertEqual(
            second["base"]["code"], first["base"]["code"],
            "code_execution: should reuse background code",
        )

    def test_grid_matrix_reuses_background(self):
        first = self._build_first_model("grid_matrix_diagram")
        compiler = get_compiler("grid_matrix_diagram")
        intent = _intent("grid_matrix_diagram", "matrix", kind="static")
        ctx = _ctx(already={first["id"]: first})
        second = compiler.compile(intent, None, ctx)
        self.assertEqual(
            second["base"]["cells"], first["base"]["cells"],
            "grid_matrix: should reuse background cells",
        )


if __name__ == "__main__":
    unittest.main()
