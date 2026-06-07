"""Contract tests for Visual System V2 compilers.

These tests intentionally use small synthetic plans. They are not checking
subject-matter quality; they check that every compiler can produce a stable
VisualModel shape that the frontend can consume.
"""

from __future__ import annotations

import unittest

from app.core.visual_ontology_v2 import BASE_VISUAL_TYPES
from app.services.visual_compilers import get_compiler, registered_base_types


def _intent(base_type: str, mode: str) -> dict:
    return {
        "base_type": base_type,
        "mode": mode,
        "description": f"Minimal {base_type} visual.",
        "purpose": "Verify compiler contract.",
        "static_or_dynamic": "dynamic",
    }


def _context() -> dict:
    return {
        "topic_id": "compiler-contract",
        "topic_hint": "Compiler contract smoke test",
        "topic_type": "algorithm_walkthrough",
        "visual_domain": "generic",
        "source_chunks_excerpt": "",
        "already_compiled_models": {},
    }


def _step(step_number: int, state_after: dict, action: str = "Update") -> dict:
    return {
        "step_number": step_number,
        "action": action,
        "reason": "Synthetic compiler contract step.",
        "text_points": [action],
        "state_after": state_after,
        "transition_hints": [],
    }


COMPILER_CASES: dict[str, dict] = {
    "coordinate_graph": {
        "mode": "function_curve",
        "base_state": {
            "x_label": "x",
            "y_label": "f(x)",
            "curves": [
                {
                    "id": "curve_0",
                    "label": "f(x)",
                    "points": [{"x": -1, "y": 1}, {"x": 0, "y": 0}, {"x": 1, "y": 1}],
                }
            ],
            "points": [{"id": "p0", "label": "minimum", "x": 0, "y": 0}],
        },
        "steps": [
            _step(1, {"active_curve": "curve_0", "active_point": "p0"}),
            _step(2, {"active_curve": "curve_0", "shaded_region": "region_0"}),
        ],
    },
    "node_link_diagram": {
        "mode": "tree_hierarchy",
        "base_state": {
            "nodes": [
                {"id": "A", "label": "A", "relation": "root", "x": 50, "y": 20},
                {"id": "B", "label": "B", "relation": "node", "x": 30, "y": 55},
                {"id": "C", "label": "C", "relation": "node", "x": 70, "y": 55},
            ],
            "edges": [
                {"from": "A", "to": "B", "label": "", "style": "solid"},
                {"from": "A", "to": "C", "label": "", "style": "solid"},
            ],
        },
        "steps": [
            _step(1, {"active_node": "A", "runtime_state": {"call_stack": ["A"], "output": []}}),
            _step(
                2,
                {
                    "active_node": "B",
                    "completed_nodes": ["A"],
                    "active_edge_from": "A",
                    "active_edge_to": "B",
                    "runtime_state": {"call_stack": ["B"], "output": ["A"]},
                },
            ),
        ],
    },
    "indexed_sequence_diagram": {
        "mode": "array_state",
        "base_state": {
            "values": [4, 2, 7],
            "pointers": [{"id": "i", "label": "i", "index": 0}],
        },
        "steps": [
            _step(1, {"active_indices": [0], "pointers": [{"id": "i", "index": 0}]}),
            _step(2, {"active_indices": [1], "pointers": [{"id": "i", "index": 1}]}),
        ],
    },
    "grid_matrix_diagram": {
        "mode": "dp_table",
        "base_state": {
            "rows": 2,
            "columns": 2,
            "row_labels": ["0", "1"],
            "column_labels": ["0", "1"],
            "cells": [["0", ""], ["", ""]],
        },
        "steps": [
            _step(1, {"active_cell": [0, 0], "cell_values": {"0,0": "0"}}),
            _step(2, {"active_cell": [1, 1], "completed_cells": [[0, 0]], "cell_values": {"1,1": "1"}}),
        ],
    },
    "table_diagram": {
        "mode": "comparison_table",
        "base_state": {
            "columns": ["Idea", "Value"],
            "rows": [["A", "1"], ["B", "2"]],
        },
        "steps": [
            _step(1, {"active_row": 0, "active_cell": [0, 1]}),
            _step(2, {"active_row": 1, "changed_cells": [[1, 1]], "cell_values": {"1,1": "3"}}),
        ],
    },
    "memory_layout_diagram": {
        "mode": "stack_heap",
        "base_state": {
            "frames": [{"id": "main", "label": "main", "bindings": [{"name": "x", "value": "1"}]}],
            "heap_objects": [{"id": "obj", "label": "list", "fields": [{"name": "0", "value": "1"}]}],
            "pointers": [{"id": "ptr", "from": "x", "to": "obj"}],
        },
        "steps": [
            _step(1, {"active_frame": "main", "visible_frames": ["main"]}),
            _step(2, {"active_object": "obj", "visible_frames": ["main"], "visible_objects": ["obj"]}),
        ],
    },
    "code_execution_panel": {
        "mode": "code_execution_trace",
        "base_state": {
            "language": "python",
            "code": "def add(a, b):\n    total = a + b\n    return total",
        },
        "steps": [
            _step(1, {"visible_until_line": 3, "highlight_lines": [1, 1]}),
            _step(2, {"visible_until_line": 3, "highlight_lines": [2, 2], "variables": [{"name": "total", "value": "3"}]}),
        ],
    },
    "geometric_diagram": {
        "mode": "triangle_geometry",
        "base_state": {
            "points": [
                {"id": "A", "label": "A", "x": 20, "y": 70},
                {"id": "B", "label": "B", "x": 80, "y": 70},
                {"id": "C", "label": "C", "x": 50, "y": 25},
            ],
            "segments": [{"id": "AB", "from": "A", "to": "B"}, {"id": "BC", "from": "B", "to": "C"}],
        },
        "steps": [
            _step(1, {"active_point": "A"}),
            _step(2, {"active_segment": "AB", "measurements": [{"id": "mAB", "label": "c"}]}),
        ],
    },
    "formula_symbolic_expression": {
        "mode": "formula_breakdown",
        "base_state": {
            "expression": "a^2 + b^2 = c^2",
            "symbols": [{"symbol": "a", "meaning": "leg"}, {"symbol": "c", "meaning": "hypotenuse"}],
        },
        "steps": [
            _step(1, {"active_symbol": "a", "equivalence_chain": ["a^2 + b^2 = c^2"]}),
            _step(2, {"active_symbol": "c", "equivalence_chain": ["3^2 + 4^2 = c^2", "25 = c^2"]}),
        ],
    },
    "timeline_sequence_interaction": {
        "mode": "protocol_sequence",
        "base_state": {
            "actors": [{"id": "client", "label": "Client"}, {"id": "server", "label": "Server"}],
            "messages": [{"id": "m1", "from": "client", "to": "server", "label": "request"}],
        },
        "steps": [
            _step(1, {"active_actor": "client", "visible_messages": []}),
            _step(2, {"active_message": "m1", "visible_messages": ["m1"]}),
        ],
    },
    "set_region_diagram": {
        "mode": "venn_diagram",
        "base_state": {
            "sets": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
            "regions": [{"id": "A_only", "label": "A only"}, {"id": "intersection", "label": "A and B"}],
            "elements": [{"id": "x", "label": "x", "region": "intersection"}],
        },
        "steps": [
            _step(1, {"active_set": "A"}),
            _step(2, {"active_region": "intersection", "shaded_regions": ["intersection"]}),
        ],
    },
    "image_real_world_illustration": {
        "mode": "analogy_image",
        "base_state": {
            "scene_title": "Warehouse analogy",
            "description": "Boxes move through stations.",
            "hotspots": [{"id": "station", "label": "Station", "x": 50, "y": 50}],
        },
        "steps": [
            _step(1, {"active_hotspot": "station", "visible_hotspots": ["station"]}),
            _step(2, {"visible_hotspots": ["station"]}),
        ],
    },
}


OVERLAY_TRANSITION_TARGETS = {
    "active_cell_highlight",
    "active_column_highlight",
    "active_row_highlight",
    "highlight_bar",
}


def _plan(base_type: str, case: dict) -> dict:
    intent = _intent(base_type, case["mode"])
    return {
        "id": f"{base_type}_contract_plan",
        "visual_intent": intent,
        "problem_setup": "Synthetic compiler test setup.",
        "terminal_state": "Synthetic compiler test complete.",
        "base_state": case["base_state"],
        "steps": case["steps"],
    }


class VisualCompilerV2ContractTests(unittest.TestCase):
    def test_every_base_type_has_a_registered_compiler(self) -> None:
        missing = sorted(set(BASE_VISUAL_TYPES) - set(registered_base_types()))
        self.assertEqual(missing, [])

    def test_compilers_emit_frontend_consumable_dynamic_models(self) -> None:
        for base_type in BASE_VISUAL_TYPES:
            with self.subTest(base_type=base_type):
                case = COMPILER_CASES[base_type]
                compiler = get_compiler(base_type)
                self.assertIsNotNone(compiler)

                intent = _intent(base_type, case["mode"])
                model = compiler.compile(intent, _plan(base_type, case), _context())

                self.assertEqual(model["base_type"], base_type)
                self.assertEqual(model["mode"], case["mode"])
                self.assertTrue(model["frames"], f"{base_type} emitted no frames")
                self.assertEqual(len(model["frames"]), len(case["steps"]))
                self.assertIsInstance(model["base"], dict)
                self.assertIsInstance(model["element_catalog"], list)

                catalog_ids = {entry["element_id"] for entry in model["element_catalog"]}
                self.assertTrue(
                    catalog_ids,
                    f"{base_type} emitted an empty element catalog",
                )

                for expected_index, frame in enumerate(model["frames"]):
                    self.assertEqual(frame["index"], expected_index)
                    self.assertIsInstance(frame["state"], dict)
                    self.assertIsInstance(frame["highlights"], dict)
                    self.assertIsInstance(frame["selectable_elements"], list)
                    self.assertIsInstance(frame["transitions"], list)

                    selectable_ids = {
                        element["element_id"] for element in frame["selectable_elements"]
                    }
                    self.assertTrue(
                        selectable_ids,
                        f"{base_type} frame {expected_index} has no selectable elements",
                    )

                    for element in frame["selectable_elements"]:
                        self.assertTrue(element["element_id"])
                        self.assertTrue(element["element_type"])
                        self.assertTrue(element["semantic_label"])
                        self.assertTrue(element["aria_label"])

                    known_ids = catalog_ids | selectable_ids | OVERLAY_TRANSITION_TARGETS
                    for transition in frame["transitions"]:
                        self.assertTrue(transition["kind"])
                        self.assertIn(transition["target_element_id"], known_ids)
                        self.assertGreaterEqual(transition["duration_ms"], 0)
                        self.assertGreaterEqual(transition["delay_ms"], 0)


if __name__ == "__main__":
    unittest.main()
