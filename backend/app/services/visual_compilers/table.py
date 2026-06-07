"""Table compiler.

Supports comparison tables, truth tables, variable traces, symbol tables,
decision tables, and similar row/column visuals.

State shape:
  base.columns          : list[str]
  base.rows             : list[list[str]]
  state_after.active_row: int | null
  state_after.active_cell: [row, col] | null
  state_after.changed_cells: list[[row, col]]
  state_after.cell_values: dict["r,c", str]
"""

from __future__ import annotations

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
from app.services.visual_compilers import register
from app.services.visual_compilers.base import VisualCompiler


class TableCompiler(VisualCompiler):
    base_type = "table_diagram"

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        base = self._build_base(plan, intent, context)
        if not base.get("columns") and not base.get("rows"):
            return self._empty_model(intent)
        if plan is None:
            return self._compile_static(intent, base, context)
        return self._compile_dynamic(intent, plan, base, context)

    def _build_base(
        self,
        plan: WorkedExamplePlan | None,
        intent: VisualIntent,
        context: CompileContext,
    ) -> dict[str, Any]:
        base_state = plan.get("base_state") if plan is not None else {}
        if not isinstance(base_state, dict):
            base_state = {}
        columns = [str(x) for x in (base_state.get("columns") or [])]
        rows = []
        for raw_row in base_state.get("rows") or []:
            if isinstance(raw_row, list):
                rows.append([str(value) for value in raw_row])
        row_labels = [str(x) for x in (base_state.get("row_labels") or [])]
        # Cross-card reuse: when this card has no plan or columns/rows of its
        # own, inherit from a previously-compiled table model (e.g. a
        # follow-up card reusing the comparison table from the background card).
        if plan is None and not columns and not rows:
            for prior in context["already_compiled_models"].values():
                if prior["base_type"] == self.base_type and (
                    prior["base"].get("columns") or prior["base"].get("rows")
                ):
                    import copy as _copy
                    return _copy.deepcopy(prior["base"])
        return {
            "mode": intent["mode"],
            "columns": columns,
            "rows": rows,
            "row_labels": row_labels,
            "caption": str(base_state.get("caption") or intent["purpose"]).strip(),
        }

    def _empty_model(self, intent: VisualIntent) -> VisualModel:
        return {
            "id": "empty_table",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": {"columns": [], "rows": [], "row_labels": [], "mode": intent["mode"]},
            "frames": [],
            "element_catalog": [],
        }

    def _compile_static(
        self,
        intent: VisualIntent,
        base: dict[str, Any],
        context: CompileContext,
    ) -> VisualModel:
        state = self._normalize_state({}, base)
        frame: VisualFrame = {
            "index": 0,
            "state": state,
            "highlights": {},
            "annotations": [],
            "selectable_elements": self.selectable_elements(state, base, intent["mode"]),
            "transitions": [],
        }
        return {
            "id": f"table_static_{context['topic_id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": [frame],
            "element_catalog": self._catalog(base),
        }

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
            frame: VisualFrame = {
                "index": index,
                "state": state,
                "highlights": {
                    "active_row": state.get("active_row"),
                    "active_cell": state.get("active_cell"),
                    "changed_cells": state.get("changed_cells") or [],
                },
                "annotations": [
                    {
                        "id": f"table_note_{index}",
                        "text": str(step.get("reason") or ""),
                        "attached_to_element_id": self._active_element_id(state),
                        "appears_in_frame": index,
                    }
                ],
                "selectable_elements": self.selectable_elements(state, base, intent["mode"]),
                "transitions": self.transitions(
                    prev_state,
                    state,
                    base,
                    intent["mode"],
                    step.get("transition_hints") or [],
                ),
            }
            frames.append(frame)
            prev_state = state
        return {
            "id": f"table_{context['topic_id']}_{plan['id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": frames,
            "element_catalog": self._catalog(base),
        }

    def _normalize_state(self, raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        row_count = len(base.get("rows") or [])
        column_count = max(len(base.get("columns") or []), *(len(row) for row in base.get("rows") or [[]]))

        def _coord(value: Any) -> list[int] | None:
            if isinstance(value, (list, tuple)) and len(value) == 2:
                try:
                    r, c = int(value[0]), int(value[1])
                except (TypeError, ValueError):
                    return None
                if 0 <= r < row_count and 0 <= c < column_count:
                    return [r, c]
            return None

        active_row = raw.get("active_row")
        if not isinstance(active_row, int) or not (0 <= active_row < row_count):
            active_row = None
        active_cell = _coord(raw.get("active_cell"))
        changed_cells = []
        for raw_cell in raw.get("changed_cells") or []:
            coord = _coord(raw_cell)
            if coord is not None and coord not in changed_cells:
                changed_cells.append(coord)
        values = raw.get("cell_values") or {}
        if not isinstance(values, dict):
            values = {}
        return {
            "active_row": active_row,
            "active_cell": active_cell,
            "changed_cells": changed_cells,
            "cell_values": {str(k): str(v) for k, v in values.items()},
        }

    def selectable_elements(
        self,
        frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
    ) -> list[SelectableElement]:
        elements: list[SelectableElement] = []
        keyboard_index = 0
        columns = base.get("columns") or []
        rows = base.get("rows") or []
        cell_values = frame_state.get("cell_values") or {}

        for column_index, label in enumerate(columns):
            elements.append(
                {
                    "element_id": f"column_{column_index}",
                    "element_type": "column",
                    "semantic_label": f"column {column_index + 1}: {label}",
                    "bounds": {"x": float(column_index) * 20.0, "y": 0.0, "width": 20.0, "height": 10.0},
                    "aria_label": f"Column {column_index + 1}: {label}",
                    "keyboard_index": keyboard_index,
                    "payload": {"column": column_index, "label": label},
                }
            )
            keyboard_index += 1

        for row_index, row in enumerate(rows):
            elements.append(
                {
                    "element_id": f"row_{row_index}",
                    "element_type": "row",
                    "semantic_label": f"row {row_index + 1}",
                    "bounds": {"x": 0.0, "y": 10.0 + float(row_index) * 10.0, "width": 100.0, "height": 10.0},
                    "aria_label": f"Row {row_index + 1}",
                    "keyboard_index": keyboard_index,
                    "payload": {"row": row_index, "values": row},
                }
            )
            keyboard_index += 1
            for column_index, base_value in enumerate(row):
                key = f"{row_index},{column_index}"
                value = cell_values.get(key, base_value)
                elements.append(
                    {
                        "element_id": f"cell_{row_index}_{column_index}",
                        "element_type": "cell",
                        "semantic_label": f"cell row {row_index + 1}, column {column_index + 1}: {value}",
                        "bounds": {
                            "x": float(column_index) * 20.0,
                            "y": 10.0 + float(row_index) * 10.0,
                            "width": 20.0,
                            "height": 10.0,
                        },
                        "aria_label": f"Cell {row_index + 1},{column_index + 1}: {value}",
                        "keyboard_index": keyboard_index,
                        "payload": {"row": row_index, "column": column_index, "value": value},
                    }
                )
                keyboard_index += 1
        return elements

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
        # Mode palette: truth_table + variable_trace get distinct accents.
        if mode == "truth_table":
            accent = "#1976D2"
        elif mode == "variable_trace_table":
            accent = "#5B2EE0"
        elif mode == "comparison_table":
            accent = "#7C4EF0"
        elif mode == "decision_table":
            accent = "#2E7D32"
        elif mode == "distance_table":
            accent = "#E76F51"
        else:
            accent = "#7C4EF0"

        transitions: list[Transition] = []
        prev_row = prev_frame_state.get("active_row")
        curr_row = curr_frame_state.get("active_row")
        if curr_row != prev_row and isinstance(curr_row, int):
            transitions.append(
                {
                    "kind": "move",
                    "target_element_id": "active_row_highlight",
                    "duration_ms": 250,
                    "delay_ms": 0,
                    "easing": "ease_in_out",
                    "spec": {
                        "from": {"row": prev_row if isinstance(prev_row, int) else -1},
                        "to": {"row": curr_row},
                    },
                }
            )

        # Active cell change — move pulse + value_change if the cell text
        # changed under it.
        prev_cell = prev_frame_state.get("active_cell")
        curr_cell = curr_frame_state.get("active_cell")
        if curr_cell != prev_cell and isinstance(curr_cell, list) and len(curr_cell) == 2:
            r, c = curr_cell
            transitions.append(
                {
                    "kind": "highlight_pulse",
                    "target_element_id": f"cell_{r}_{c}",
                    "duration_ms": 400,
                    "delay_ms": 150,
                    "easing": "ease_out",
                    "spec": {"color": accent, "cycles": 1},
                }
            )

        changed_cells = curr_frame_state.get("changed_cells") or []
        # If many cells changed at once (typical for SQL UPDATE / DP fill),
        # cascade them as a stagger_group instead of independent pulses.
        if len(changed_cells) > 2:
            ids = [f"cell_{r}_{c}" for r, c in changed_cells]
            transitions.append(
                {
                    "kind": "stagger_group",
                    "target_element_id": ids[0],
                    "duration_ms": 300 * len(ids),
                    "delay_ms": 0,
                    "easing": "ease_out",
                    "spec": {"group_element_ids": ids, "stagger_ms": 80},
                }
            )
        else:
            for r, c in changed_cells:
                transitions.append(
                    {
                        "kind": "value_change",
                        "target_element_id": f"cell_{r}_{c}",
                        "duration_ms": 300,
                        "delay_ms": 50,
                        "easing": "ease_in_out",
                        "spec": {"from_value": "", "to_value": "updated"},
                    }
                )
                transitions.append(
                    {
                        "kind": "highlight_pulse",
                        "target_element_id": f"cell_{r}_{c}",
                        "duration_ms": 450,
                        "delay_ms": 0,
                        "easing": "ease_out",
                        "spec": {"color": accent, "cycles": 1},
                    }
                )
        return transitions

    def _active_element_id(self, state: dict[str, Any]) -> str | None:
        active_cell = state.get("active_cell")
        if isinstance(active_cell, list) and len(active_cell) == 2:
            return f"cell_{active_cell[0]}_{active_cell[1]}"
        active_row = state.get("active_row")
        if isinstance(active_row, int):
            return f"row_{active_row}"
        return None

    def _catalog(self, base: dict[str, Any]) -> list:
        catalog = []
        for column_index, _ in enumerate(base.get("columns") or []):
            catalog.append(
                {
                    "element_id": f"column_{column_index}",
                    "element_type": "column",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": float(column_index) * 20.0, "y": 0.0, "width": 20.0, "height": 10.0},
                }
            )
        for row_index, row in enumerate(base.get("rows") or []):
            catalog.append(
                {
                    "element_id": f"row_{row_index}",
                    "element_type": "row",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": 0.0, "y": 10.0 + float(row_index) * 10.0, "width": 100.0, "height": 10.0},
                }
            )
            for column_index, _ in enumerate(row):
                catalog.append(
                    {
                        "element_id": f"cell_{row_index}_{column_index}",
                        "element_type": "cell",
                        "first_frame": 0,
                        "last_frame": -1,
                        "initial_bounds": {
                            "x": float(column_index) * 20.0,
                            "y": 10.0 + float(row_index) * 10.0,
                            "width": 20.0,
                            "height": 10.0,
                        },
                    }
                )
        return catalog


register(TableCompiler())
