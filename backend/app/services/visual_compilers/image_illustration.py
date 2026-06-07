"""Image / real-world illustration compiler.

This deterministic renderer does not generate bitmap assets. It compiles a
scene card with semantic hotspots so real-world analogy cards can be visual
and clickable without network or image-generation dependencies.

State shape:
  base.scene_title            : str
  base.description            : str
  base.hotspots               : list[{id, label, x, y, description}]
  state_after.active_hotspot  : str | null
  state_after.visible_hotspots: list[str] | null
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


class ImageIllustrationCompiler(VisualCompiler):
    base_type = "image_real_world_illustration"

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        base = self._build_base(plan, intent, context)
        if not base.get("scene_title") and not base.get("description"):
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
            if model["base_type"] == self.base_type and model["base"].get("scene_title"):
                return copy.deepcopy(model["base"])
        return self._normalize_base(
            {
                "scene_title": intent["purpose"],
                "description": intent["description"],
                "hotspots": [],
            },
            intent,
        )

    def _normalize_base(self, raw: dict[str, Any], intent: VisualIntent) -> dict[str, Any]:
        hotspots: list[dict[str, Any]] = []
        for index, raw_hotspot in enumerate(raw.get("hotspots") or []):
            if not isinstance(raw_hotspot, dict):
                continue
            hotspot_id = str(raw_hotspot.get("id") or f"hotspot_{index}")
            try:
                x = float(raw_hotspot.get("x", 20 + index * 20))
                y = float(raw_hotspot.get("y", 50))
            except (TypeError, ValueError):
                x, y = 20.0 + index * 20.0, 50.0
            hotspots.append(
                {
                    "id": hotspot_id,
                    "label": str(raw_hotspot.get("label") or hotspot_id),
                    "x": x,
                    "y": y,
                    "description": str(raw_hotspot.get("description") or ""),
                }
            )

        return {
            "mode": intent["mode"],
            "scene_title": str(raw.get("scene_title") or intent["purpose"]).strip(),
            "description": str(raw.get("description") or intent["description"]).strip(),
            "hotspots": hotspots,
            "caption": str(raw.get("caption") or intent["purpose"]).strip(),
        }

    def _empty_model(self, intent: VisualIntent) -> VisualModel:
        return {
            "id": "empty_image_illustration",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": {"scene_title": "", "description": "", "hotspots": [], "mode": intent["mode"]},
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
            "id": f"image_illustration_static_{context['topic_id']}",
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
                "highlights": {"active_hotspot": state.get("active_hotspot")},
                "annotations": [
                    {
                        "id": f"image_note_{index}",
                        "text": str(step.get("reason") or ""),
                        "attached_to_element_id": state.get("active_hotspot"),
                        "appears_in_frame": index,
                    }
                ],
                "selectable_elements": self.selectable_elements(state, base, intent["mode"]),
                "transitions": self.transitions(prev_state, state, base, intent["mode"], step.get("transition_hints") or []),
            }
            frames.append(frame)
            prev_state = state
        return {
            "id": f"image_illustration_{context['topic_id']}_{plan['id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": frames,
            "element_catalog": self._catalog(base),
        }

    def _normalize_state(self, raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        hotspot_ids = {hotspot["id"] for hotspot in base.get("hotspots") or []}
        active_hotspot = raw.get("active_hotspot")
        if active_hotspot is not None:
            active_hotspot = str(active_hotspot)
        if active_hotspot not in hotspot_ids:
            active_hotspot = None
        visible_hotspots = None
        if isinstance(raw.get("visible_hotspots"), list):
            visible_hotspots = []
            for item in raw["visible_hotspots"]:
                item_id = str(item)
                if item_id in hotspot_ids and item_id not in visible_hotspots:
                    visible_hotspots.append(item_id)
        return {"active_hotspot": active_hotspot, "visible_hotspots": visible_hotspots}

    def selectable_elements(
        self,
        frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
    ) -> list[SelectableElement]:
        elements: list[SelectableElement] = []
        visible = set(frame_state.get("visible_hotspots") or [hotspot["id"] for hotspot in base.get("hotspots") or []])
        for index, hotspot in enumerate(base.get("hotspots") or []):
            if hotspot["id"] not in visible:
                continue
            elements.append(
                {
                    "element_id": hotspot["id"],
                    "element_type": "hotspot",
                    "semantic_label": f"hotspot {hotspot['label']}",
                    "bounds": {"x": hotspot["x"] - 3.0, "y": hotspot["y"] - 3.0, "width": 6.0, "height": 6.0},
                    "aria_label": f"Hotspot {hotspot['label']}",
                    "keyboard_index": index,
                    "payload": hotspot,
                }
            )
        return elements

    def _mode_palette(self, mode: str) -> dict[str, Any]:
        if mode == "analogy_image":
            return {"accent": "#7C4EF0", "hotspot_duration_ms": 280}
        if mode == "real_world_scene":
            return {"accent": "#2E7D32", "hotspot_duration_ms": 250}
        if mode == "physical_intuition":
            return {"accent": "#1976D2", "hotspot_duration_ms": 280}
        if mode == "topic_motivation":
            return {"accent": "#5B2EE0", "hotspot_duration_ms": 350}
        if mode == "system_metaphor":
            return {"accent": "#E76F51", "hotspot_duration_ms": 320}
        return {"accent": "#7C4EF0", "hotspot_duration_ms": 280}

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

        old_visible = set(prev_frame_state.get("visible_hotspots") or [])
        new_hotspots = [
            hid for hid in (curr_frame_state.get("visible_hotspots") or [])
            if hid not in old_visible
        ]
        # Stagger when multiple hotspots reveal at once — analogy images
        # often introduce 2-3 highlighted regions in sequence.
        if len(new_hotspots) > 1:
            transitions.append({
                "kind": "stagger_group",
                "target_element_id": new_hotspots[0],
                "duration_ms": palette["hotspot_duration_ms"] * len(new_hotspots),
                "delay_ms": 0,
                "easing": "ease_out",
                "spec": {"group_element_ids": new_hotspots, "stagger_ms": 200},
            })
        else:
            for hotspot_id in new_hotspots:
                transitions.append(
                    {
                        "kind": "appear",
                        "target_element_id": hotspot_id,
                        "duration_ms": palette["hotspot_duration_ms"],
                        "delay_ms": 0,
                        "easing": "ease_out",
                        "spec": {"scale": True, "color": palette["accent"]},
                    }
                )
        # Hotspots that vanish (the illustration cycles through scenes)
        gone = old_visible - set(curr_frame_state.get("visible_hotspots") or [])
        for hotspot_id in gone:
            transitions.append({
                "kind": "disappear",
                "target_element_id": hotspot_id,
                "duration_ms": 220,
                "delay_ms": 0,
                "easing": "ease_in",
                "spec": {},
            })

        active = curr_frame_state.get("active_hotspot")
        if active and active != prev_frame_state.get("active_hotspot"):
            transitions.append(
                {
                    "kind": "highlight_pulse",
                    "target_element_id": str(active),
                    "duration_ms": 450,
                    "delay_ms": 100,
                    "easing": "ease_out",
                    "spec": {"color": palette["accent"]},
                }
            )
        return transitions

    def _catalog(self, base: dict[str, Any]) -> list:
        return [
            {
                "element_id": hotspot["id"],
                "element_type": "hotspot",
                "first_frame": 0,
                "last_frame": -1,
                "initial_bounds": {"x": hotspot["x"] - 3.0, "y": hotspot["y"] - 3.0, "width": 6.0, "height": 6.0},
            }
            for hotspot in base.get("hotspots") or []
        ]


register(ImageIllustrationCompiler())
