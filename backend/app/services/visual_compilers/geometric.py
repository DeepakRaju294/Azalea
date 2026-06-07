"""Geometric diagram compiler.

Supports basic geometric constructions: points, segments, polygons/regions,
angles, vectors, and measurement labels.

State shape:
  base.points              : list[{id, label, x, y}]
  base.segments            : list[{id, from, to, label}]
  base.regions             : list[{id, label, points}]
  state_after.active_point : str | null
  state_after.active_segment: str | null
  state_after.active_region: str | null
  state_after.shaded_regions: list[str]
  state_after.measurements : dict[element_id, str]
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


class GeometricCompiler(VisualCompiler):
    base_type = "geometric_diagram"

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        base = self._build_base(plan, intent, context)
        if not base.get("points") and not base.get("regions"):
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
            if model["base_type"] == self.base_type and (model["base"].get("points") or model["base"].get("regions")):
                return copy.deepcopy(model["base"])
        return self._normalize_base({}, intent)

    def _normalize_base(self, raw: dict[str, Any], intent: VisualIntent) -> dict[str, Any]:
        points: list[dict[str, Any]] = []
        for index, raw_point in enumerate(raw.get("points") or []):
            if not isinstance(raw_point, dict):
                continue
            point_id = str(raw_point.get("id") or f"P{index + 1}")
            try:
                x = float(raw_point.get("x"))
                y = float(raw_point.get("y"))
            except (TypeError, ValueError):
                continue
            points.append({"id": point_id, "label": str(raw_point.get("label") or point_id), "x": x, "y": y})
        point_ids = {point["id"] for point in points}

        segments: list[dict[str, str]] = []
        for index, raw_segment in enumerate(raw.get("segments") or []):
            if not isinstance(raw_segment, dict):
                continue
            from_id = str(raw_segment.get("from") or "")
            to_id = str(raw_segment.get("to") or "")
            if from_id not in point_ids or to_id not in point_ids:
                continue
            segment_id = str(raw_segment.get("id") or f"{from_id}_{to_id}")
            segments.append({"id": segment_id, "from": from_id, "to": to_id, "label": str(raw_segment.get("label") or "")})

        regions: list[dict[str, Any]] = []
        for index, raw_region in enumerate(raw.get("regions") or []):
            if not isinstance(raw_region, dict):
                continue
            region_points = [str(point_id) for point_id in (raw_region.get("points") or []) if str(point_id) in point_ids]
            if len(region_points) < 3:
                continue
            region_id = str(raw_region.get("id") or f"region_{index}")
            regions.append({"id": region_id, "label": str(raw_region.get("label") or region_id), "points": region_points})

        return {
            "mode": intent["mode"],
            "points": points,
            "segments": segments,
            "regions": regions,
            "caption": str(raw.get("caption") or intent["purpose"]).strip(),
        }

    def _empty_model(self, intent: VisualIntent) -> VisualModel:
        return {
            "id": "empty_geometric",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": {"points": [], "segments": [], "regions": [], "mode": intent["mode"]},
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
            "id": f"geometric_static_{context['topic_id']}",
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
                    "active_segment": state.get("active_segment"),
                    "active_region": state.get("active_region"),
                    "shaded_regions": state.get("shaded_regions") or [],
                },
                "annotations": [
                    {
                        "id": f"geometric_note_{index}",
                        "text": str(step.get("reason") or ""),
                        "attached_to_element_id": self._active_element_id(state),
                        "appears_in_frame": index,
                    }
                ],
                "selectable_elements": self.selectable_elements(state, base, intent["mode"]),
                "transitions": self.transitions(prev_state, state, base, intent["mode"], step.get("transition_hints") or []),
            }
            frames.append(frame)
            prev_state = state
        return {
            "id": f"geometric_{context['topic_id']}_{plan['id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": frames,
            "element_catalog": self._catalog(base),
        }

    def _normalize_state(self, raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        point_ids = {point["id"] for point in base.get("points") or []}
        segment_ids = {segment["id"] for segment in base.get("segments") or []}
        region_ids = {region["id"] for region in base.get("regions") or []}
        shaded_regions = []
        for item in raw.get("shaded_regions") or []:
            region_id = str(item)
            if region_id in region_ids and region_id not in shaded_regions:
                shaded_regions.append(region_id)
        measurements = raw.get("measurements") or {}
        if not isinstance(measurements, dict):
            measurements = {}
        return {
            "active_point": self._known_id(raw.get("active_point"), point_ids),
            "active_segment": self._known_id(raw.get("active_segment"), segment_ids),
            "active_region": self._known_id(raw.get("active_region"), region_ids),
            "shaded_regions": shaded_regions,
            "measurements": {str(k): str(v) for k, v in measurements.items()},
        }

    def _known_id(self, value: Any, known: set[str]) -> str | None:
        if value is None:
            return None
        candidate = str(value)
        return candidate if candidate in known else None

    def selectable_elements(
        self,
        frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
    ) -> list[SelectableElement]:
        elements: list[SelectableElement] = []
        keyboard_index = 0
        for point in base.get("points") or []:
            elements.append(
                {
                    "element_id": point["id"],
                    "element_type": "shape",
                    "semantic_label": f"point {point['label']}",
                    "bounds": {"x": point["x"] - 2.0, "y": point["y"] - 2.0, "width": 4.0, "height": 4.0},
                    "aria_label": f"Point {point['label']}",
                    "keyboard_index": keyboard_index,
                    "payload": point,
                }
            )
            keyboard_index += 1
        for segment in base.get("segments") or []:
            elements.append(
                {
                    "element_id": segment["id"],
                    "element_type": "side",
                    "semantic_label": f"segment {segment['label'] or segment['id']}",
                    "bounds": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0},
                    "aria_label": f"Segment {segment['label'] or segment['id']}",
                    "keyboard_index": keyboard_index,
                    "payload": segment,
                }
            )
            keyboard_index += 1
        for region in base.get("regions") or []:
            elements.append(
                {
                    "element_id": region["id"],
                    "element_type": "shape",
                    "semantic_label": f"region {region['label']}",
                    "bounds": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0},
                    "aria_label": f"Region {region['label']}",
                    "keyboard_index": keyboard_index,
                    "payload": region,
                }
            )
            keyboard_index += 1
        return elements

    def _mode_palette(self, mode: str) -> dict[str, Any]:
        """Triangle (a=opposite, b=adjacent, c=hypotenuse) gets a different
        emphasis from a 3D solid or a vector projection."""
        if mode == "triangle_geometry":
            return {"accent": "#7C4EF0", "region_opacity": 0.18, "measurement_emphasis": True}
        if mode == "circle_geometry":
            return {"accent": "#2E7D32", "region_opacity": 0.18, "measurement_emphasis": True}
        if mode == "vector_geometry":
            return {"accent": "#1976D2", "region_opacity": 0.12, "measurement_emphasis": False}
        if mode == "3d_solid":
            return {"accent": "#5B2EE0", "region_opacity": 0.22, "measurement_emphasis": False}
        if mode == "integration_region":
            return {"accent": "#E76F51", "region_opacity": 0.30, "measurement_emphasis": False}
        if mode == "projection":
            return {"accent": "#1976D2", "region_opacity": 0.15, "measurement_emphasis": False}
        if mode == "related_rates":
            return {"accent": "#D32F2F", "region_opacity": 0.18, "measurement_emphasis": True}
        return {"accent": "#7C4EF0", "region_opacity": 0.18, "measurement_emphasis": False}

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
        for target in (
            curr_frame_state.get("active_point"),
            curr_frame_state.get("active_segment"),
            curr_frame_state.get("active_region"),
        ):
            if target:
                transitions.append(
                    {
                        "kind": "highlight_pulse",
                        "target_element_id": str(target),
                        "duration_ms": 420,
                        "delay_ms": 0,
                        "easing": "ease_out",
                        "spec": {"color": palette["accent"]},
                    }
                )
        previous = set(prev_frame_state.get("shaded_regions") or [])
        for region in curr_frame_state.get("shaded_regions") or []:
            if region not in previous:
                transitions.append(
                    {
                        "kind": "fade_in",
                        "target_element_id": region,
                        "duration_ms": 300,
                        "delay_ms": 0,
                        "easing": "ease_out",
                        "spec": {"opacity": palette["region_opacity"]},
                    }
                )

        # Measurement changes: when a side length / angle gets a new value,
        # emit value_change so the learner watches the number update. Only
        # for modes where measurement is the teaching focus.
        if palette["measurement_emphasis"]:
            prev_measurements = prev_frame_state.get("measurements") or {}
            curr_measurements = curr_frame_state.get("measurements") or {}
            if isinstance(prev_measurements, dict) and isinstance(curr_measurements, dict):
                for element_id, new_value in curr_measurements.items():
                    old_value = prev_measurements.get(element_id)
                    if str(old_value) != str(new_value):
                        transitions.append(
                            {
                                "kind": "value_change",
                                "target_element_id": str(element_id),
                                "duration_ms": 350,
                                "delay_ms": 150,
                                "easing": "ease_in_out",
                                "spec": {"from_value": str(old_value or ""), "to_value": str(new_value)},
                            }
                        )
        return transitions

    def _active_element_id(self, state: dict[str, Any]) -> str | None:
        return state.get("active_point") or state.get("active_segment") or state.get("active_region")

    def _catalog(self, base: dict[str, Any]) -> list:
        catalog = []
        for point in base.get("points") or []:
            catalog.append(
                {
                    "element_id": point["id"],
                    "element_type": "shape",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": point["x"] - 2.0, "y": point["y"] - 2.0, "width": 4.0, "height": 4.0},
                }
            )
        for segment in base.get("segments") or []:
            catalog.append(
                {
                    "element_id": segment["id"],
                    "element_type": "side",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0},
                }
            )
        for region in base.get("regions") or []:
            catalog.append(
                {
                    "element_id": region["id"],
                    "element_type": "shape",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0},
                }
            )
        return catalog


register(GeometricCompiler())
