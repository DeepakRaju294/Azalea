"""Memory layout compiler.

Supports stack frames, heap objects, variable bindings, and pointer arrows.

State shape:
  base.frames              : list[{id, label, variables}]
  base.objects             : list[{id, label, fields}]
  base.pointers            : list[{id, from, to, label}]
  state_after.active_frame : str | null
  state_after.active_object: str | null
  state_after.active_pointer: str | null
  state_after.changed_bindings: list[str]
  state_after.visible_frames : list[str] | null
  state_after.visible_objects: list[str] | null
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


class MemoryLayoutCompiler(VisualCompiler):
    base_type = "memory_layout_diagram"

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        base = self._build_base(plan, intent, context)
        if not base.get("frames") and not base.get("objects"):
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
            if model["base_type"] == self.base_type and (model["base"].get("frames") or model["base"].get("objects")):
                return copy.deepcopy(model["base"])
        return self._normalize_base({}, intent)

    def _normalize_base(self, raw: dict[str, Any], intent: VisualIntent) -> dict[str, Any]:
        frames: list[dict[str, Any]] = []
        for index, raw_frame in enumerate(raw.get("frames") or []):
            if not isinstance(raw_frame, dict):
                continue
            frame_id = str(raw_frame.get("id") or f"frame_{index}")
            variables = []
            for raw_var in raw_frame.get("variables") or []:
                if not isinstance(raw_var, dict):
                    continue
                name = str(raw_var.get("name") or "")
                if not name:
                    continue
                variables.append(
                    {
                        "id": str(raw_var.get("id") or f"{frame_id}.{name}"),
                        "name": name,
                        "value": str(raw_var.get("value") or ""),
                        "target": str(raw_var.get("target") or ""),
                    }
                )
            frames.append({"id": frame_id, "label": str(raw_frame.get("label") or frame_id), "variables": variables})

        objects: list[dict[str, Any]] = []
        for index, raw_object in enumerate(raw.get("objects") or []):
            if not isinstance(raw_object, dict):
                continue
            object_id = str(raw_object.get("id") or f"object_{index}")
            fields = []
            for raw_field in raw_object.get("fields") or []:
                if not isinstance(raw_field, dict):
                    continue
                name = str(raw_field.get("name") or "")
                if not name:
                    continue
                fields.append({"name": name, "value": str(raw_field.get("value") or ""), "target": str(raw_field.get("target") or "")})
            objects.append({"id": object_id, "label": str(raw_object.get("label") or object_id), "fields": fields})

        pointers: list[dict[str, str]] = []
        for index, raw_pointer in enumerate(raw.get("pointers") or []):
            if not isinstance(raw_pointer, dict):
                continue
            from_id = str(raw_pointer.get("from") or "")
            to_id = str(raw_pointer.get("to") or "")
            if not from_id or not to_id:
                continue
            pointer_id = str(raw_pointer.get("id") or f"ptr_{index}")
            pointers.append({"id": pointer_id, "from": from_id, "to": to_id, "label": str(raw_pointer.get("label") or "")})

        return {
            "mode": intent["mode"],
            "frames": frames,
            "objects": objects,
            "pointers": pointers,
            "caption": str(raw.get("caption") or intent["purpose"]).strip(),
        }

    def _empty_model(self, intent: VisualIntent) -> VisualModel:
        return {
            "id": "empty_memory_layout",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": {"frames": [], "objects": [], "pointers": [], "mode": intent["mode"]},
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
            "id": f"memory_static_{context['topic_id']}",
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
                    "active_frame": state.get("active_frame"),
                    "active_object": state.get("active_object"),
                    "active_pointer": state.get("active_pointer"),
                },
                "annotations": [
                    {
                        "id": f"memory_note_{index}",
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
            "id": f"memory_{context['topic_id']}_{plan['id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": frames,
            "element_catalog": self._catalog(base),
        }

    def _normalize_state(self, raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        frame_ids = {frame["id"] for frame in base.get("frames") or []}
        object_ids = {obj["id"] for obj in base.get("objects") or []}
        pointer_ids = {ptr["id"] for ptr in base.get("pointers") or []}
        variable_ids = {var["id"] for frame in base.get("frames") or [] for var in frame.get("variables") or []}

        active_frame = self._known_id(raw.get("active_frame"), frame_ids)
        active_object = self._known_id(raw.get("active_object"), object_ids)
        active_pointer = self._known_id(raw.get("active_pointer"), pointer_ids)

        changed_bindings = []
        for raw_id in raw.get("changed_bindings") or []:
            binding_id = self._known_id(raw_id, variable_ids)
            if binding_id is not None and binding_id not in changed_bindings:
                changed_bindings.append(binding_id)

        visible_frames = self._visible_ids(raw.get("visible_frames"), frame_ids)
        visible_objects = self._visible_ids(raw.get("visible_objects"), object_ids)

        return {
            "active_frame": active_frame,
            "active_object": active_object,
            "active_pointer": active_pointer,
            "changed_bindings": changed_bindings,
            "visible_frames": visible_frames,
            "visible_objects": visible_objects,
        }

    def _known_id(self, value: Any, known: set[str]) -> str | None:
        if value is None:
            return None
        candidate = str(value)
        return candidate if candidate in known else None

    def _visible_ids(self, raw: Any, known: set[str]) -> list[str] | None:
        if raw is None:
            return None
        if not isinstance(raw, list):
            return None
        values = []
        for item in raw:
            known_id = self._known_id(item, known)
            if known_id is not None and known_id not in values:
                values.append(known_id)
        return values

    def selectable_elements(
        self,
        frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
    ) -> list[SelectableElement]:
        elements: list[SelectableElement] = []
        keyboard_index = 0
        visible_frames = set(frame_state.get("visible_frames") or [frame["id"] for frame in base.get("frames") or []])
        visible_objects = set(frame_state.get("visible_objects") or [obj["id"] for obj in base.get("objects") or []])

        for frame_index, frame in enumerate(base.get("frames") or []):
            if frame["id"] not in visible_frames:
                continue
            elements.append(
                {
                    "element_id": frame["id"],
                    "element_type": "memory_frame",
                    "semantic_label": f"stack frame {frame['label']}",
                    "bounds": {"x": 0.0, "y": float(frame_index) * 16.0, "width": 42.0, "height": 14.0},
                    "aria_label": f"Stack frame {frame['label']}",
                    "keyboard_index": keyboard_index,
                    "payload": {"frame_id": frame["id"], "label": frame["label"]},
                }
            )
            keyboard_index += 1
            for var_index, variable in enumerate(frame.get("variables") or []):
                elements.append(
                    {
                        "element_id": variable["id"],
                        "element_type": "variable_binding",
                        "semantic_label": f"variable {variable['name']} = {variable['value']}",
                        "bounds": {"x": 2.0, "y": float(frame_index) * 16.0 + 4.0 + var_index * 3.0, "width": 36.0, "height": 3.0},
                        "aria_label": f"Variable {variable['name']}: {variable['value']}",
                        "keyboard_index": keyboard_index,
                        "payload": variable,
                    }
                )
                keyboard_index += 1

        for object_index, obj in enumerate(base.get("objects") or []):
            if obj["id"] not in visible_objects:
                continue
            elements.append(
                {
                    "element_id": obj["id"],
                    "element_type": "heap_object",
                    "semantic_label": f"heap object {obj['label']}",
                    "bounds": {"x": 58.0, "y": float(object_index) * 16.0, "width": 42.0, "height": 14.0},
                    "aria_label": f"Heap object {obj['label']}",
                    "keyboard_index": keyboard_index,
                    "payload": {"object_id": obj["id"], "label": obj["label"]},
                }
            )
            keyboard_index += 1

        for pointer in base.get("pointers") or []:
            elements.append(
                {
                    "element_id": pointer["id"],
                    "element_type": "pointer_arrow",
                    "semantic_label": f"pointer {pointer['label'] or pointer['id']} from {pointer['from']} to {pointer['to']}",
                    "bounds": {"x": 42.0, "y": 0.0, "width": 16.0, "height": 100.0},
                    "aria_label": f"Pointer {pointer['label'] or pointer['id']}",
                    "keyboard_index": keyboard_index,
                    "payload": pointer,
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
        transitions: list[Transition] = []

        # call_stack / stack_heap modes get appear/disappear on the stack
        # frame visibility list — push and pop are the most informative
        # animations for these modes.
        if mode in ("call_stack", "stack_heap", "pointer_reference"):
            prev_visible_frames = set(
                str(x) for x in (prev_frame_state.get("visible_frames") or []) if x is not None
            )
            curr_visible_frames = set(
                str(x) for x in (curr_frame_state.get("visible_frames") or []) if x is not None
            )
            for new_id in curr_visible_frames - prev_visible_frames:
                transitions.append(
                    {
                        "kind": "appear",
                        "target_element_id": new_id,
                        "duration_ms": 280,
                        "delay_ms": 0,
                        "easing": "ease_out",
                        "spec": {"slide_from": "top"},
                    }
                )
            for gone_id in prev_visible_frames - curr_visible_frames:
                transitions.append(
                    {
                        "kind": "disappear",
                        "target_element_id": gone_id,
                        "duration_ms": 220,
                        "delay_ms": 0,
                        "easing": "ease_in",
                        "spec": {"slide_to": "top"},
                    }
                )

            # Heap object allocations
            prev_visible_objects = set(
                str(x) for x in (prev_frame_state.get("visible_objects") or []) if x is not None
            )
            curr_visible_objects = set(
                str(x) for x in (curr_frame_state.get("visible_objects") or []) if x is not None
            )
            for new_id in curr_visible_objects - prev_visible_objects:
                transitions.append(
                    {
                        "kind": "fade_in",
                        "target_element_id": new_id,
                        "duration_ms": 350,
                        "delay_ms": 100,
                        "easing": "ease_out",
                        "spec": {},
                    }
                )

        # Active-X pulse for every active mode
        for key, kind in (
            ("active_frame", "memory_frame"),
            ("active_object", "heap_object"),
            ("active_pointer", "pointer_arrow"),
        ):
            active = curr_frame_state.get(key)
            if active and active != prev_frame_state.get(key):
                # Pointer rebind also gets a `move` (the arrow swings to the
                # new target) for pointer_reference mode.
                if key == "active_pointer" and mode == "pointer_reference":
                    prev_active = prev_frame_state.get(key)
                    if prev_active:
                        transitions.append(
                            {
                                "kind": "move",
                                "target_element_id": str(active),
                                "duration_ms": 320,
                                "delay_ms": 0,
                                "easing": "ease_in_out",
                                "spec": {
                                    "from": {"element_id": str(prev_active)},
                                    "to": {"element_id": str(active)},
                                },
                            }
                        )
                transitions.append(
                    {
                        "kind": "highlight_pulse",
                        "target_element_id": str(active),
                        "duration_ms": 450,
                        "delay_ms": 0,
                        "easing": "ease_out",
                        "spec": {"element_type": kind, "color": "#7C4EF0"},
                    }
                )
        for binding_id in curr_frame_state.get("changed_bindings") or []:
            transitions.append(
                {
                    "kind": "value_change",
                    "target_element_id": binding_id,
                    "duration_ms": 300,
                    "delay_ms": 0,
                    "easing": "ease_in_out",
                    "spec": {"changed": True},
                }
            )
        return transitions

    def _active_element_id(self, state: dict[str, Any]) -> str | None:
        return state.get("active_frame") or state.get("active_object") or state.get("active_pointer")

    def _catalog(self, base: dict[str, Any]) -> list:
        catalog = []
        for index, frame in enumerate(base.get("frames") or []):
            catalog.append(
                {
                    "element_id": frame["id"],
                    "element_type": "memory_frame",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": 0.0, "y": float(index) * 16.0, "width": 42.0, "height": 14.0},
                }
            )
            for var_index, variable in enumerate(frame.get("variables") or []):
                catalog.append(
                    {
                        "element_id": variable["id"],
                        "element_type": "variable_binding",
                        "first_frame": 0,
                        "last_frame": -1,
                        "initial_bounds": {"x": 2.0, "y": float(index) * 16.0 + 4.0 + var_index * 3.0, "width": 36.0, "height": 3.0},
                    }
                )
        for index, obj in enumerate(base.get("objects") or []):
            catalog.append(
                {
                    "element_id": obj["id"],
                    "element_type": "heap_object",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": 58.0, "y": float(index) * 16.0, "width": 42.0, "height": 14.0},
                }
            )
        for pointer in base.get("pointers") or []:
            catalog.append(
                {
                    "element_id": pointer["id"],
                    "element_type": "pointer_arrow",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": 42.0, "y": 0.0, "width": 16.0, "height": 100.0},
                }
            )
        return catalog


register(MemoryLayoutCompiler())
