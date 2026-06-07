"""Set / region compiler.

Supports Venn diagrams, sample spaces, classification overlap, and probability
regions.

State shape:
  base.sets                 : list[{id, label, x, y, r}]
  base.elements             : list[{id, label, x, y, regions}]
  state_after.active_set    : str | null
  state_after.active_region : str | null
  state_after.shaded_regions: list[str]
  state_after.active_element: str | null
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


class SetRegionCompiler(VisualCompiler):
    base_type = "set_region_diagram"

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        base = self._build_base(plan, intent, context)
        if not base.get("sets"):
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
            if model["base_type"] == self.base_type and model["base"].get("sets"):
                return copy.deepcopy(model["base"])
        return self._normalize_base({}, intent)

    def _normalize_base(self, raw: dict[str, Any], intent: VisualIntent) -> dict[str, Any]:
        sets: list[dict[str, Any]] = []
        for index, raw_set in enumerate(raw.get("sets") or []):
            if not isinstance(raw_set, dict):
                continue
            set_id = str(raw_set.get("id") or f"set_{index}")
            try:
                x = float(raw_set.get("x", 40 + index * 20))
                y = float(raw_set.get("y", 50))
                r = float(raw_set.get("r", 28))
            except (TypeError, ValueError):
                x, y, r = 40.0 + index * 20.0, 50.0, 28.0
            sets.append({"id": set_id, "label": str(raw_set.get("label") or set_id), "x": x, "y": y, "r": r})

        elements: list[dict[str, Any]] = []
        for index, raw_element in enumerate(raw.get("elements") or []):
            if not isinstance(raw_element, dict):
                continue
            element_id = str(raw_element.get("id") or f"element_{index}")
            try:
                x = float(raw_element.get("x"))
                y = float(raw_element.get("y"))
            except (TypeError, ValueError):
                x, y = 20.0 + index * 8.0, 85.0
            regions = [str(item) for item in (raw_element.get("regions") or [])]
            elements.append({"id": element_id, "label": str(raw_element.get("label") or element_id), "x": x, "y": y, "regions": regions})

        return {
            "mode": intent["mode"],
            "sets": sets,
            "elements": elements,
            "caption": str(raw.get("caption") or intent["purpose"]).strip(),
        }

    def _empty_model(self, intent: VisualIntent) -> VisualModel:
        return {
            "id": "empty_set_region",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": {"sets": [], "elements": [], "mode": intent["mode"]},
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
            "id": f"set_region_static_{context['topic_id']}",
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
                    "active_set": state.get("active_set"),
                    "active_region": state.get("active_region"),
                    "active_element": state.get("active_element"),
                    "shaded_regions": state.get("shaded_regions") or [],
                },
                "annotations": [
                    {
                        "id": f"set_region_note_{index}",
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
            "id": f"set_region_{context['topic_id']}_{plan['id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": frames,
            "element_catalog": self._catalog(base),
        }

    def _normalize_state(self, raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        set_ids = {item["id"] for item in base.get("sets") or []}
        element_ids = {item["id"] for item in base.get("elements") or []}
        active_set = self._known_id(raw.get("active_set"), set_ids)
        active_element = self._known_id(raw.get("active_element"), element_ids)
        shaded_regions = []
        for raw_region in raw.get("shaded_regions") or []:
            region = str(raw_region)
            if region in set_ids or "_" in region:
                shaded_regions.append(region)
        active_region = raw.get("active_region")
        if active_region is not None:
            active_region = str(active_region)
        if active_region not in set_ids and active_region not in shaded_regions:
            active_region = None
        return {
            "active_set": active_set,
            "active_region": active_region,
            "shaded_regions": shaded_regions,
            "active_element": active_element,
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
        for item in base.get("sets") or []:
            elements.append(
                {
                    "element_id": item["id"],
                    "element_type": "set",
                    "semantic_label": f"set {item['label']}",
                    "bounds": {"x": item["x"] - item["r"], "y": item["y"] - item["r"], "width": item["r"] * 2, "height": item["r"] * 2},
                    "aria_label": f"Set {item['label']}",
                    "keyboard_index": keyboard_index,
                    "payload": item,
                }
            )
            keyboard_index += 1
        for element in base.get("elements") or []:
            elements.append(
                {
                    "element_id": element["id"],
                    "element_type": "element_in_region",
                    "semantic_label": f"element {element['label']}",
                    "bounds": {"x": element["x"] - 2.0, "y": element["y"] - 2.0, "width": 4.0, "height": 4.0},
                    "aria_label": f"Element {element['label']}",
                    "keyboard_index": keyboard_index,
                    "payload": element,
                }
            )
            keyboard_index += 1
        for region in frame_state.get("shaded_regions") or []:
            elements.append(
                {
                    "element_id": f"region_{region}",
                    "element_type": "region",
                    "semantic_label": f"region {region}",
                    "bounds": {"x": 0.0, "y": 0.0, "width": 100.0, "height": 100.0},
                    "aria_label": f"Region {region}",
                    "keyboard_index": keyboard_index,
                    "payload": {"region": region},
                }
            )
            keyboard_index += 1
        return elements

    def _mode_palette(self, mode: str) -> dict[str, Any]:
        if mode == "venn_diagram":
            return {"accent": "#7C4EF0", "region_opacity": 0.32}
        if mode == "union":
            return {"accent": "#2E7D32", "region_opacity": 0.32}
        if mode == "intersection":
            return {"accent": "#5B2EE0", "region_opacity": 0.40}
        if mode == "complement":
            return {"accent": "#D32F2F", "region_opacity": 0.22}
        if mode == "sample_space":
            return {"accent": "#1976D2", "region_opacity": 0.28}
        if mode == "probability_region":
            return {"accent": "#7C4EF0", "region_opacity": 0.30}
        if mode == "classification_overlap":
            return {"accent": "#E76F51", "region_opacity": 0.28}
        if mode == "logic_region":
            return {"accent": "#5B2EE0", "region_opacity": 0.28}
        return {"accent": "#7C4EF0", "region_opacity": 0.28}

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
        for target in (curr_frame_state.get("active_set"), curr_frame_state.get("active_element")):
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
        old_regions = set(prev_frame_state.get("shaded_regions") or [])
        curr_regions = set(curr_frame_state.get("shaded_regions") or [])
        for region in curr_regions - old_regions:
            transitions.append(
                {
                    "kind": "fade_in",
                    "target_element_id": f"region_{region}",
                    "duration_ms": 300,
                    "delay_ms": 0,
                    "easing": "ease_out",
                    "spec": {"opacity": palette["region_opacity"]},
                }
            )
        for region in old_regions - curr_regions:
            transitions.append(
                {
                    "kind": "fade_out",
                    "target_element_id": f"region_{region}",
                    "duration_ms": 280,
                    "delay_ms": 0,
                    "easing": "ease_in",
                    "spec": {},
                }
            )

        # Mode-specific: complement mode pulses the universal-set boundary
        # so the learner sees "everything outside A" not just A.
        if mode == "complement" and curr_frame_state.get("active_region"):
            transitions.append({
                "kind": "highlight_pulse",
                "target_element_id": "universal_boundary",
                "duration_ms": 500,
                "delay_ms": 200,
                "easing": "ease_out",
                "spec": {"color": palette["accent"]},
            })

        # Element placement: when an element moves into/out of a region,
        # emit a `move` so the learner watches the element fly in.
        prev_placements = prev_frame_state.get("element_placements") or {}
        curr_placements = curr_frame_state.get("element_placements") or {}
        if isinstance(prev_placements, dict) and isinstance(curr_placements, dict):
            for element_id, target_region in curr_placements.items():
                if prev_placements.get(element_id) != target_region:
                    transitions.append({
                        "kind": "move",
                        "target_element_id": str(element_id),
                        "duration_ms": 380,
                        "delay_ms": 100,
                        "easing": "ease_in_out",
                        "spec": {
                            "from": {"region": prev_placements.get(element_id)},
                            "to": {"region": target_region},
                        },
                    })
        return transitions

    def _active_element_id(self, state: dict[str, Any]) -> str | None:
        return state.get("active_element") or state.get("active_set") or (f"region_{state['active_region']}" if state.get("active_region") else None)

    def _catalog(self, base: dict[str, Any]) -> list:
        catalog = []
        for item in base.get("sets") or []:
            catalog.append(
                {
                    "element_id": item["id"],
                    "element_type": "set",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": item["x"] - item["r"], "y": item["y"] - item["r"], "width": item["r"] * 2, "height": item["r"] * 2},
                }
            )
        for element in base.get("elements") or []:
            catalog.append(
                {
                    "element_id": element["id"],
                    "element_type": "element_in_region",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": element["x"] - 2.0, "y": element["y"] - 2.0, "width": 4.0, "height": 4.0},
                }
            )
        return catalog


register(SetRegionCompiler())
