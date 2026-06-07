"""Grid / matrix compiler — DP tables, adjacency matrices, K-maps,
confusion matrices, grid traversals.

State shape:
  base.cells              : list[list[str]]
  base.row_labels         : list[str]
  base.column_labels      : list[str]
  base.mode               : "matrix" | "dp_table" | "adjacency_matrix" | ...
  state_after.active_cell : [row, col] | null
  state_after.completed_cells : list[[row, col]]
  state_after.dependency_arrows : list[{from: [r,c], to: [r,c]}]
  state_after.highlighted_row : int | null
  state_after.highlighted_column : int | null
  state_after.cell_values : dict[str, str] — overrides; key "r,c"
"""

from __future__ import annotations

import copy
from typing import Any

from app.schemas.visual_v2 import (
    CompileContext,
    SelectableElement,
    Transition,
    TransitionHint,
    VisualFrame,
    VisualIntent,
    VisualModel,
    WorkedExamplePlan,
)
from app.services.v2_aria_localization import localize_aria
from app.services.visual_compilers import register
from app.services.visual_compilers.base import VisualCompiler


class GridMatrixCompiler(VisualCompiler):
    base_type = "grid_matrix_diagram"

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        base = self._build_base(plan, intent, context)
        if not base.get("cells"):
            return self._empty_model(intent)
        if plan is None:
            return self._compile_static(intent, base, context)
        return self._compile_dynamic(intent, plan, base, context)

    # ---- base structure ---------------------------------------------------

    def _build_base(
        self,
        plan: WorkedExamplePlan | None,
        intent: VisualIntent,
        context: CompileContext,
    ) -> dict[str, Any]:
        if plan is not None:
            base_state = plan.get("base_state") or {}
            raw_cells = base_state.get("cells") or []
            cells = [
                [str(v) for v in row] if isinstance(row, list) else []
                for row in raw_cells
            ]
            return {
                "mode": intent["mode"],
                "cells": cells,
                "row_labels": [str(x) for x in (base_state.get("row_labels") or [])],
                "column_labels": [str(x) for x in (base_state.get("column_labels") or [])],
            }
        # Look at already-compiled background card
        for model in context["already_compiled_models"].values():
            if model["base_type"] == self.base_type and model["base"].get("cells"):
                return copy.deepcopy(model["base"])
        return {"mode": intent["mode"], "cells": [], "row_labels": [], "column_labels": []}

    def _empty_model(self, intent: VisualIntent) -> VisualModel:
        return {
            "id": "empty_grid_matrix",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": {"cells": [], "row_labels": [], "column_labels": [], "mode": intent["mode"]},
            "frames": [],
            "element_catalog": [],
        }

    # ---- static ---------------------------------------------------------

    def _compile_static(
        self,
        intent: VisualIntent,
        base: dict[str, Any],
        context: CompileContext,
    ) -> VisualModel:
        state = {
            "active_cell": None,
            "completed_cells": [],
            "dependency_arrows": [],
            "highlighted_row": None,
            "highlighted_column": None,
            "cell_values": {},
        }
        frame: VisualFrame = {
            "index": 0,
            "state": state,
            "highlights": {},
            "annotations": [],
            "selectable_elements": self.selectable_elements(state, base, intent["mode"]),
            "transitions": [],
        }
        return {
            "id": f"grid_static_{context['topic_id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": [frame],
            "element_catalog": self._catalog(base),
        }

    # ---- dynamic --------------------------------------------------------

    def _compile_dynamic(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan,
        base: dict[str, Any],
        context: CompileContext,
    ) -> VisualModel:
        frames: list[VisualFrame] = []
        prev_state: dict[str, Any] | None = None
        for index, step in enumerate(plan["steps"]):
            state = self._normalize_state(step.get("state_after") or {}, base)
            transitions = self.transitions(prev_state, state, base, intent["mode"], step.get("transition_hints") or [])
            frame: VisualFrame = {
                "index": index,
                "state": state,
                "highlights": {
                    "active_cell": state.get("active_cell"),
                    "completed_cells": list(state.get("completed_cells") or []),
                },
                "annotations": [],
                "selectable_elements": self.selectable_elements(state, base, intent["mode"]),
                "transitions": transitions,
            }
            frames.append(frame)
            prev_state = state
        return {
            "id": f"grid_{context['topic_id']}_{plan['id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": frames,
            "element_catalog": self._catalog(base),
        }

    # ---- state normalization -------------------------------------------

    def _normalize_state(self, raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        n_rows = len(base["cells"])
        n_cols = len(base["cells"][0]) if n_rows > 0 else 0

        def _coords(value: Any) -> list[int] | None:
            if isinstance(value, (list, tuple)) and len(value) == 2:
                try:
                    r, c = int(value[0]), int(value[1])
                except (TypeError, ValueError):
                    return None
                if 0 <= r < n_rows and 0 <= c < n_cols:
                    return [r, c]
            return None

        active_cell = _coords(raw.get("active_cell"))
        completed_cells: list[list[int]] = []
        for v in (raw.get("completed_cells") or []):
            coord = _coords(v)
            if coord is not None and coord not in completed_cells:
                completed_cells.append(coord)

        dependency_arrows: list[dict[str, list[int]]] = []
        for arrow in (raw.get("dependency_arrows") or []):
            if not isinstance(arrow, dict):
                continue
            f = _coords(arrow.get("from"))
            t = _coords(arrow.get("to"))
            if f and t:
                dependency_arrows.append({"from": f, "to": t})

        cell_values: dict[str, str] = {}
        raw_values = raw.get("cell_values") or {}
        if isinstance(raw_values, dict):
            for k, v in raw_values.items():
                cell_values[str(k)] = str(v)

        return {
            "active_cell": active_cell,
            "completed_cells": completed_cells,
            "dependency_arrows": dependency_arrows,
            "highlighted_row": raw.get("highlighted_row") if isinstance(raw.get("highlighted_row"), int) else None,
            "highlighted_column": raw.get("highlighted_column") if isinstance(raw.get("highlighted_column"), int) else None,
            "cell_values": cell_values,
        }

    # ---- selectable elements -------------------------------------------

    def selectable_elements(
        self,
        frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
    ) -> list[SelectableElement]:
        elements: list[SelectableElement] = []
        keyboard_index = 0
        cells = base["cells"]
        active = frame_state.get("active_cell")
        completed_set = {tuple(c) for c in (frame_state.get("completed_cells") or []) if isinstance(c, list)}
        cell_values = frame_state.get("cell_values") or {}

        for r, row in enumerate(cells):
            for c, base_val in enumerate(row):
                key = f"{r},{c}"
                value = cell_values.get(key, base_val)
                if active == [r, c]:
                    state = "active"
                elif (r, c) in completed_set:
                    state = "completed"
                else:
                    state = "empty" if not value else "filled"
                elements.append({
                    "element_id": f"cell_{r}_{c}",
                    "element_type": "cell",
                    "semantic_label": f"cell at row {r}, column {c}, value {value or 'empty'}",
                    "bounds": {"x": float(c) * 10.0, "y": float(r) * 10.0, "width": 10.0, "height": 10.0},
                    "aria_label": localize_aria(
                        "grid_cell",
                        row=r,
                        column=c,
                        value=value or "empty",
                    ),
                    "keyboard_index": keyboard_index,
                    "payload": {"row": r, "column": c, "value": value, "state": state},
                })
                keyboard_index += 1

        for i, label in enumerate(base.get("row_labels") or []):
            elements.append({
                "element_id": f"row_header_{i}",
                "element_type": "row_header",
                "semantic_label": f"row label: {label}",
                "bounds": {"x": -8.0, "y": float(i) * 10.0, "width": 8.0, "height": 10.0},
                "aria_label": f"Row {i}: {label}",
                "keyboard_index": keyboard_index,
                "payload": {"row": i, "label": label},
            })
            keyboard_index += 1
        for j, label in enumerate(base.get("column_labels") or []):
            elements.append({
                "element_id": f"col_header_{j}",
                "element_type": "column_header",
                "semantic_label": f"column label: {label}",
                "bounds": {"x": float(j) * 10.0, "y": -8.0, "width": 10.0, "height": 8.0},
                "aria_label": f"Column {j}: {label}",
                "keyboard_index": keyboard_index,
                "payload": {"column": j, "label": label},
            })
            keyboard_index += 1
        return elements

    # ---- transitions ---------------------------------------------------

    def transitions(
        self,
        prev_frame_state: dict[str, Any] | None,
        curr_frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
        hints: list[TransitionHint],
    ) -> list[Transition]:
        if prev_frame_state is None:
            return []
        transitions: list[Transition] = []

        # Mode-specific palette so adjacency_matrix doesn't look like dp_table.
        # All modes share the same overlay primitives; only color + duration
        # differ. Defaults match dp_table (the default-mode color is purple).
        mode_palette = self._mode_palette(mode)

        # Active cell move
        prev_active = prev_frame_state.get("active_cell")
        curr_active = curr_frame_state.get("active_cell")
        if curr_active and curr_active != prev_active:
            r, c = curr_active[0], curr_active[1]
            transitions.append({
                "kind": "style_change",
                "target_element_id": f"cell_{r}_{c}",
                "duration_ms": mode_palette["active_duration_ms"],
                "delay_ms": 0,
                "easing": "ease_in_out",
                "spec": {"from_style": "empty", "to_style": "active"},
            })
            transitions.append({
                "kind": "highlight_pulse",
                "target_element_id": f"cell_{r}_{c}",
                "duration_ms": 500,
                "delay_ms": 150,
                "easing": "ease_out",
                "spec": {"color": mode_palette["active_color"], "cycles": 1},
            })
            # adjacency_matrix: also pulse the corresponding row + column
            # headers so the learner sees which two vertices form the edge.
            if mode == "adjacency_matrix":
                transitions.append({
                    "kind": "highlight_pulse",
                    "target_element_id": f"row_header_{r}",
                    "duration_ms": 400,
                    "delay_ms": 100,
                    "easing": "ease_out",
                    "spec": {"color": mode_palette["active_color"], "cycles": 1},
                })
                transitions.append({
                    "kind": "highlight_pulse",
                    "target_element_id": f"col_header_{c}",
                    "duration_ms": 400,
                    "delay_ms": 100,
                    "easing": "ease_out",
                    "spec": {"color": mode_palette["active_color"], "cycles": 1},
                })

        # Newly completed cells
        prev_completed = {tuple(c) for c in (prev_frame_state.get("completed_cells") or []) if isinstance(c, list)}
        curr_completed = {tuple(c) for c in (curr_frame_state.get("completed_cells") or []) if isinstance(c, list)}
        new_completed = curr_completed - prev_completed
        for r, c in sorted(new_completed):
            if curr_active and curr_active == [r, c]:
                continue
            transitions.append({
                "kind": "style_change",
                "target_element_id": f"cell_{r}_{c}",
                "duration_ms": 300,
                "delay_ms": 0,
                "easing": "ease_out",
                "spec": {"from_style": "empty", "to_style": "completed"},
            })

        # Cell value changes (DP fill)
        prev_values = prev_frame_state.get("cell_values") or {}
        curr_values = curr_frame_state.get("cell_values") or {}
        for key, new_val in curr_values.items():
            old_val = prev_values.get(key, "")
            if str(old_val) != str(new_val):
                try:
                    r, c = key.split(",")
                    transitions.append({
                        "kind": "value_change",
                        "target_element_id": f"cell_{r}_{c}",
                        "duration_ms": 300,
                        "delay_ms": 200,
                        "easing": "ease_in_out",
                        "spec": {"from_value": str(old_val), "to_value": str(new_val)},
                    })
                except ValueError:
                    pass

        return transitions

    def _mode_palette(self, mode: str) -> dict[str, Any]:
        """Per-mode color/duration palette. Centralizes the differences so
        compile() / transitions() stay readable."""
        if mode == "adjacency_matrix":
            return {"active_color": "#2E7D32", "active_duration_ms": 300}
        if mode == "karnaugh_map":
            return {"active_color": "#E76F51", "active_duration_ms": 350}
        if mode == "confusion_matrix":
            return {"active_color": "#1976D2", "active_duration_ms": 300}
        if mode == "heatmap":
            return {"active_color": "#D32F2F", "active_duration_ms": 200}
        if mode == "grid_traversal":
            return {"active_color": "#7C4EF0", "active_duration_ms": 200}
        # dp_table (default) and matrix
        return {"active_color": "#7C4EF0", "active_duration_ms": 250}

    def _catalog(self, base: dict[str, Any]) -> list:
        catalog = []
        for r, row in enumerate(base["cells"]):
            for c in range(len(row)):
                catalog.append({
                    "element_id": f"cell_{r}_{c}",
                    "element_type": "cell",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": float(c) * 10.0, "y": float(r) * 10.0, "width": 10.0, "height": 10.0},
                })
        return catalog

    # ---- LLM-compliance fallback ------------------------------------------

    def synthesize_plan_from_legacy_cards(
        self,
        legacy_cards: list[dict[str, Any]],
        context: CompileContext,
    ) -> WorkedExamplePlan | None:
        """Reconstruct a grid_matrix plan from legacy lean cards.

        Pulls base_state.cells from the background card's
        `visual_columns` + `visual_rows`. Per-step state_after extracted
        from each worked_example card's text (active row N, column M,
        cell [r,c] patterns).
        """
        import re

        columns: list[str] = []
        rows: list[list[str]] = []
        for card in legacy_cards:
            if str(card.get("blueprint_key") or "").strip().lower() != "background":
                continue
            visual_type = str(card.get("visual_type") or "").strip().lower()
            if "matrix" not in visual_type and "table" not in visual_type and "grid" not in visual_type:
                continue
            raw_cols = card.get("visual_columns") or []
            raw_rows = card.get("visual_rows") or []
            if raw_cols and raw_rows:
                columns = [str(x) for x in raw_cols]
                for row in raw_rows:
                    if isinstance(row, list):
                        rows.append([str(v) for v in row])
                break
        if not rows:
            return None

        worked_cards = [
            c for c in legacy_cards
            if str(c.get("blueprint_key") or "").strip().lower() == "worked_example"
        ]
        if not worked_cards:
            return None

        n_rows = len(rows)
        n_cols = len(rows[0]) if n_rows else 0
        steps: list[dict[str, Any]] = []
        completed_cells: list[list[int]] = []
        for index, card in enumerate(worked_cards):
            text = " ".join(str(p) for p in (card.get("points") or []))
            active_cell = None
            match = re.search(
                r"(?:cell|position)\s*\[?\s*(\d+)\s*[,;]\s*(\d+)\s*\]?",
                text,
                re.IGNORECASE,
            )
            if match:
                r, c = int(match.group(1)), int(match.group(2))
                if 0 <= r < n_rows and 0 <= c < n_cols:
                    active_cell = [r, c]
                    if [r, c] not in completed_cells:
                        completed_cells.append([r, c])
            action = str(card.get("title") or "").strip() or f"Step {index + 1}"
            reason = str(card.get("learning_job") or "").strip()
            steps.append({
                "step_number": index + 1,
                "action": action,
                "reason": reason,
                "text_points": [
                    str(p).rstrip() for p in (card.get("points") or []) if str(p).strip()
                ],
                "state_after": {
                    "active_cell": active_cell,
                    "completed_cells": [list(c) for c in completed_cells],
                    "dependency_arrows": [],
                    "highlighted_row": None,
                    "highlighted_column": None,
                    "cell_values": {},
                },
                "transition_hints": [],
            })

        if not steps:
            return None

        visual_intent = {
            "base_type": self.base_type,
            "mode": "matrix",
            "description": "Synthesized from legacy cards.",
            "purpose": "Reconstructed matrix trace.",
            "static_or_dynamic": "dynamic",
        }
        return {
            "id": f"synth_grid_matrix_{context.get('topic_id', 'unknown')}",
            "visual_intent": visual_intent,
            "problem_setup": f"Trace through {n_rows}x{n_cols} grid.",
            "terminal_state": "All cells visited.",
            "base_state": {
                "cells": rows,
                "column_labels": columns,
                "row_labels": [],
            },
            "steps": steps,
        }


register(GridMatrixCompiler())
