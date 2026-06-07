"""Coordinate graph compiler.

Supports function curves, distribution curves, runtime growth graphs,
scatter plots, shaded probability regions, and tangent/secant overlays.

State shape:
  base.axes                    : dict with x_min/x_max/y_min/y_max/x_label/y_label
  base.curves                  : list[{id, label, points}]
  base.points                  : list[{id, label, x, y}]
  state_after.active_point     : str | null
  state_after.active_curve     : str | null
  state_after.shaded_region    : {curve_id, x_start, x_end, label} | null
  state_after.tangent_secant_line : {id, x1, y1, x2, y2, label} | null
  state_after.active_curve_segment : {curve_id, x_start, x_end} | null
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
from app.services.visual_compilers import register
from app.services.visual_compilers.base import VisualCompiler


DEFAULT_AXES = {
    "x_min": -5.0,
    "x_max": 5.0,
    "y_min": 0.0,
    "y_max": 1.0,
    "x_label": "x",
    "y_label": "y",
}


class CoordinateGraphCompiler(VisualCompiler):
    base_type = "coordinate_graph"

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        base = self._build_base(plan, intent, context)
        if not base.get("curves") and not base.get("points"):
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
        if plan is not None:
            base_state = plan.get("base_state") or {}
            if not isinstance(base_state, dict):
                base_state = {}
            return self._normalize_base(base_state, intent)
        for model in context["already_compiled_models"].values():
            if model["base_type"] == self.base_type and (model["base"].get("curves") or model["base"].get("points")):
                return copy.deepcopy(model["base"])
        return self._normalize_base({}, intent)

    def _normalize_base(self, raw: dict[str, Any], intent: VisualIntent) -> dict[str, Any]:
        axes = dict(DEFAULT_AXES)
        raw_axes = raw.get("axes") or {}
        if isinstance(raw_axes, dict):
            for key in ("x_min", "x_max", "y_min", "y_max"):
                try:
                    axes[key] = float(raw_axes.get(key, axes[key]))
                except (TypeError, ValueError):
                    pass
            for key in ("x_label", "y_label"):
                axes[key] = str(raw_axes.get(key, axes[key]) or axes[key])
        if axes["x_min"] >= axes["x_max"]:
            axes["x_min"], axes["x_max"] = DEFAULT_AXES["x_min"], DEFAULT_AXES["x_max"]
        if axes["y_min"] >= axes["y_max"]:
            axes["y_min"], axes["y_max"] = DEFAULT_AXES["y_min"], DEFAULT_AXES["y_max"]

        curves: list[dict[str, Any]] = []
        for curve_index, raw_curve in enumerate(raw.get("curves") or []):
            if not isinstance(raw_curve, dict):
                continue
            points = self._normalize_points(raw_curve.get("points") or [])
            if not points:
                continue
            curve_id = str(raw_curve.get("id") or f"curve_{curve_index}")
            curves.append(
                {
                    "id": curve_id,
                    "label": str(raw_curve.get("label") or curve_id),
                    "points": points,
                    "color": str(raw_curve.get("color") or "#7C4EF0"),
                }
            )

        points: list[dict[str, Any]] = []
        for point_index, raw_point in enumerate(raw.get("points") or []):
            point = self._normalize_point(raw_point, f"point_{point_index}")
            if point is not None:
                points.append(point)

        return {
            "mode": intent["mode"],
            "axes": axes,
            "curves": curves,
            "points": points,
            "caption": str(raw.get("caption") or intent["purpose"]).strip(),
        }

    def _normalize_points(self, raw_points: list[Any]) -> list[dict[str, float]]:
        points: list[dict[str, float]] = []
        for raw_point in raw_points:
            x_value: Any = None
            y_value: Any = None
            if isinstance(raw_point, dict):
                x_value = raw_point.get("x")
                y_value = raw_point.get("y")
            elif isinstance(raw_point, (list, tuple)) and len(raw_point) >= 2:
                x_value = raw_point[0]
                y_value = raw_point[1]
            try:
                points.append({"x": float(x_value), "y": float(y_value)})
            except (TypeError, ValueError):
                continue
        return points

    def _normalize_point(self, raw_point: Any, fallback_id: str) -> dict[str, Any] | None:
        if not isinstance(raw_point, dict):
            return None
        try:
            x = float(raw_point.get("x"))
            y = float(raw_point.get("y"))
        except (TypeError, ValueError):
            return None
        point_id = str(raw_point.get("id") or fallback_id)
        return {
            "id": point_id,
            "label": str(raw_point.get("label") or point_id),
            "x": x,
            "y": y,
        }

    def _empty_model(self, intent: VisualIntent) -> VisualModel:
        return {
            "id": "empty_coordinate_graph",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": {"axes": DEFAULT_AXES, "curves": [], "points": [], "mode": intent["mode"]},
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
            "id": f"coordinate_static_{context['topic_id']}",
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
                    "active_point": state.get("active_point"),
                    "active_curve": state.get("active_curve"),
                    "shaded_region": state.get("shaded_region"),
                },
                "annotations": [
                    {
                        "id": f"coordinate_note_{index}",
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
            "id": f"coordinate_{context['topic_id']}_{plan['id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": frames,
            "element_catalog": self._catalog(base),
        }

    def _normalize_state(self, raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        point_ids = {point["id"] for point in base.get("points") or []}
        curve_ids = {curve["id"] for curve in base.get("curves") or []}
        active_point = raw.get("active_point")
        if active_point is not None:
            active_point = str(active_point)
        if active_point not in point_ids:
            active_point = None
        active_curve = raw.get("active_curve")
        if active_curve is not None:
            active_curve = str(active_curve)
        if active_curve not in curve_ids:
            active_curve = None

        return {
            "active_point": active_point,
            "active_curve": active_curve,
            "shaded_region": self._normalize_region(raw.get("shaded_region"), curve_ids),
            "tangent_secant_line": self._normalize_line(raw.get("tangent_secant_line")),
            "active_curve_segment": self._normalize_segment(raw.get("active_curve_segment"), curve_ids),
        }

    def _normalize_region(self, raw: Any, curve_ids: set[str]) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        curve_id = str(raw.get("curve_id") or "")
        if curve_id not in curve_ids:
            return None
        try:
            x_start = float(raw.get("x_start"))
            x_end = float(raw.get("x_end"))
        except (TypeError, ValueError):
            return None
        if x_start > x_end:
            x_start, x_end = x_end, x_start
        return {
            "curve_id": curve_id,
            "x_start": x_start,
            "x_end": x_end,
            "label": str(raw.get("label") or "shaded region"),
        }

    def _normalize_segment(self, raw: Any, curve_ids: set[str]) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        curve_id = str(raw.get("curve_id") or "")
        if curve_id not in curve_ids:
            return None
        try:
            x_start = float(raw.get("x_start"))
            x_end = float(raw.get("x_end"))
        except (TypeError, ValueError):
            return None
        if x_start > x_end:
            x_start, x_end = x_end, x_start
        return {"curve_id": curve_id, "x_start": x_start, "x_end": x_end}

    def _normalize_line(self, raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        try:
            x1 = float(raw.get("x1"))
            y1 = float(raw.get("y1"))
            x2 = float(raw.get("x2"))
            y2 = float(raw.get("y2"))
        except (TypeError, ValueError):
            return None
        line_id = str(raw.get("id") or "tangent_secant_line")
        return {"id": line_id, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "label": str(raw.get("label") or line_id)}

    def selectable_elements(
        self,
        frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
    ) -> list[SelectableElement]:
        elements: list[SelectableElement] = []
        keyboard_index = 0
        axes = base["axes"]

        for axis_id, label in (("x_axis", axes["x_label"]), ("y_axis", axes["y_label"])):
            elements.append(
                {
                    "element_id": axis_id,
                    "element_type": "axis_label",
                    "semantic_label": f"{axis_id.replace('_', ' ')} labeled {label}",
                    "bounds": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 10.0},
                    "aria_label": f"{axis_id.replace('_', ' ')}: {label}",
                    "keyboard_index": keyboard_index,
                    "payload": {"axis": axis_id, "label": label},
                }
            )
            keyboard_index += 1

        for curve in base.get("curves") or []:
            elements.append(
                {
                    "element_id": curve["id"],
                    "element_type": "curve_segment",
                    "semantic_label": f"curve {curve['label']}",
                    "bounds": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0},
                    "aria_label": f"Curve {curve['label']}",
                    "keyboard_index": keyboard_index,
                    "payload": {"curve_id": curve["id"], "label": curve["label"]},
                }
            )
            keyboard_index += 1

        for point in base.get("points") or []:
            x_pct, y_pct = self._point_bounds(point["x"], point["y"], axes)
            elements.append(
                {
                    "element_id": point["id"],
                    "element_type": "plotted_point",
                    "semantic_label": f"point {point['label']} at ({point['x']}, {point['y']})",
                    "bounds": {"x": x_pct - 2.0, "y": y_pct - 2.0, "width": 4.0, "height": 4.0},
                    "aria_label": f"Point {point['label']}: x {point['x']}, y {point['y']}",
                    "keyboard_index": keyboard_index,
                    "payload": {"point_id": point["id"], "x": point["x"], "y": point["y"]},
                }
            )
            keyboard_index += 1

        if frame_state.get("shaded_region"):
            region = frame_state["shaded_region"]
            elements.append(
                {
                    "element_id": "shaded_region",
                    "element_type": "shaded_region",
                    "semantic_label": str(region.get("label") or "shaded region"),
                    "bounds": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0},
                    "aria_label": str(region.get("label") or "Shaded region"),
                    "keyboard_index": keyboard_index,
                    "payload": region,
                }
            )
            keyboard_index += 1
        if frame_state.get("tangent_secant_line"):
            line = frame_state["tangent_secant_line"]
            elements.append(
                {
                    "element_id": line["id"],
                    "element_type": "tangent_line",
                    "semantic_label": str(line.get("label") or "tangent or secant line"),
                    "bounds": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0},
                    "aria_label": str(line.get("label") or "Tangent or secant line"),
                    "keyboard_index": keyboard_index,
                    "payload": line,
                }
            )
        return elements

    def _mode_palette(self, mode: str) -> dict[str, Any]:
        """Per-mode palette for coordinate_graph. ROC + loss + distribution
        each carry a recognizable color so the learner anchors to the type
        before reading axes."""
        if mode == "roc_curve":
            return {"active_color": "#1976D2", "region_opacity": 0.18}
        if mode == "loss_curve":
            return {"active_color": "#D32F2F", "region_opacity": 0.15}
        if mode == "distribution_curve":
            return {"active_color": "#7C4EF0", "region_opacity": 0.28}
        if mode == "runtime_growth":
            return {"active_color": "#2E7D32", "region_opacity": 0.15}
        if mode == "area_under_curve":
            return {"active_color": "#7C4EF0", "region_opacity": 0.32}
        if mode == "regression_plot":
            return {"active_color": "#5B2EE0", "region_opacity": 0.15}
        return {"active_color": "#7C4EF0", "region_opacity": 0.22}

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
        palette = self._mode_palette(mode)
        transitions: list[Transition] = []
        if curr_frame_state.get("active_point") and curr_frame_state.get("active_point") != prev_frame_state.get("active_point"):
            transitions.append(
                {
                    "kind": "move",
                    "target_element_id": str(curr_frame_state["active_point"]),
                    "duration_ms": 350,
                    "delay_ms": 0,
                    "easing": "ease_in_out",
                    "spec": {
                        "from": {
                            "element_id": str(prev_frame_state.get("active_point") or ""),
                        },
                        "to": {
                            "element_id": str(curr_frame_state["active_point"]),
                        },
                    },
                }
            )
            transitions.append(
                {
                    "kind": "highlight_pulse",
                    "target_element_id": str(curr_frame_state["active_point"]),
                    "duration_ms": 450,
                    "delay_ms": 200,
                    "easing": "ease_out",
                    "spec": {"color": palette["active_color"]},
                }
            )
        if curr_frame_state.get("shaded_region") != prev_frame_state.get("shaded_region") and curr_frame_state.get("shaded_region"):
            transitions.append(
                {
                    "kind": "fade_in",
                    "target_element_id": "shaded_region",
                    "duration_ms": 350,
                    "delay_ms": 0,
                    "easing": "ease_out",
                    "spec": {"opacity": palette["region_opacity"]},
                }
            )
        if curr_frame_state.get("tangent_secant_line") != prev_frame_state.get("tangent_secant_line") and curr_frame_state.get("tangent_secant_line"):
            line = curr_frame_state["tangent_secant_line"]
            transitions.append(
                {
                    "kind": "appear",
                    "target_element_id": line["id"],
                    "duration_ms": 300,
                    "delay_ms": 0,
                    "easing": "ease_out",
                    "spec": {"draw": True},
                }
            )
        # Active curve segment change — emit a stagger_group so the
        # learner sees the segment fill in piece by piece (only when
        # the mode is one that benefits from it).
        if mode in ("loss_curve", "runtime_growth", "regression_plot"):
            prev_seg = prev_frame_state.get("active_curve_segment") or {}
            curr_seg = curr_frame_state.get("active_curve_segment") or {}
            if curr_seg and curr_seg != prev_seg:
                transitions.append(
                    {
                        "kind": "stagger_group",
                        "target_element_id": f"curve_segment_{curr_seg.get('curve_id', '')}",
                        "duration_ms": 600,
                        "delay_ms": 100,
                        "easing": "ease_out",
                        "spec": {
                            "group_element_ids": [
                                f"curve_segment_{curr_seg.get('curve_id', '')}",
                            ],
                            "stagger_ms": 80,
                        },
                    }
                )
        return transitions

    def _point_bounds(self, x: float, y: float, axes: dict[str, Any]) -> tuple[float, float]:
        x_pct = (x - axes["x_min"]) / (axes["x_max"] - axes["x_min"]) * 100.0
        y_pct = 100.0 - (y - axes["y_min"]) / (axes["y_max"] - axes["y_min"]) * 100.0
        return x_pct, y_pct

    def _active_element_id(self, state: dict[str, Any]) -> str | None:
        if state.get("active_point"):
            return str(state["active_point"])
        if state.get("active_curve"):
            return str(state["active_curve"])
        if state.get("shaded_region"):
            return "shaded_region"
        if state.get("tangent_secant_line"):
            return str(state["tangent_secant_line"]["id"])
        return None

    def _catalog(self, base: dict[str, Any]) -> list:
        catalog = [
            {
                "element_id": "x_axis",
                "element_type": "axis_label",
                "first_frame": 0,
                "last_frame": -1,
                "initial_bounds": {"x": 0.0, "y": 92.0, "width": 100.0, "height": 8.0},
            },
            {
                "element_id": "y_axis",
                "element_type": "axis_label",
                "first_frame": 0,
                "last_frame": -1,
                "initial_bounds": {"x": 0.0, "y": 0.0, "width": 8.0, "height": 100.0},
            },
        ]
        for curve in base.get("curves") or []:
            catalog.append(
                {
                    "element_id": curve["id"],
                    "element_type": "curve_segment",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0},
                }
            )
        for point in base.get("points") or []:
            x_pct, y_pct = self._point_bounds(point["x"], point["y"], base["axes"])
            catalog.append(
                {
                    "element_id": point["id"],
                    "element_type": "plotted_point",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": x_pct - 2.0, "y": y_pct - 2.0, "width": 4.0, "height": 4.0},
                }
            )
        return catalog


register(CoordinateGraphCompiler())
