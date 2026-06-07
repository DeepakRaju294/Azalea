"""Timeline / sequence interaction compiler.

Supports protocol sequence diagrams, request/response flows, thread schedules,
transactions, and lock acquisition timelines.

State shape:
  base.actors                 : list[{id, label}]
  base.messages               : list[{id, from, to, label, time}]
  state_after.active_actor    : str | null
  state_after.active_message  : str | null
  state_after.visible_messages: list[str] | null
  state_after.actor_states    : dict[actor_id, state]
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


class TimelineSequenceCompiler(VisualCompiler):
    base_type = "timeline_sequence_interaction"

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        base = self._build_base(plan, intent, context)
        if not base.get("actors"):
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
            if model["base_type"] == self.base_type and model["base"].get("actors"):
                return copy.deepcopy(model["base"])
        return self._normalize_base({}, intent)

    def _normalize_base(self, raw: dict[str, Any], intent: VisualIntent) -> dict[str, Any]:
        actors: list[dict[str, str]] = []
        for index, raw_actor in enumerate(raw.get("actors") or []):
            if not isinstance(raw_actor, dict):
                continue
            actor_id = str(raw_actor.get("id") or f"actor_{index}")
            actors.append({"id": actor_id, "label": str(raw_actor.get("label") or actor_id)})
        actor_ids = {actor["id"] for actor in actors}

        messages: list[dict[str, Any]] = []
        for index, raw_message in enumerate(raw.get("messages") or []):
            if not isinstance(raw_message, dict):
                continue
            from_id = str(raw_message.get("from") or "")
            to_id = str(raw_message.get("to") or "")
            if from_id not in actor_ids or to_id not in actor_ids:
                continue
            message_id = str(raw_message.get("id") or f"message_{index}")
            try:
                time = float(raw_message.get("time", index))
            except (TypeError, ValueError):
                time = float(index)
            messages.append(
                {
                    "id": message_id,
                    "from": from_id,
                    "to": to_id,
                    "label": str(raw_message.get("label") or message_id),
                    "time": time,
                }
            )

        return {
            "mode": intent["mode"],
            "actors": actors,
            "messages": sorted(messages, key=lambda item: item["time"]),
            "caption": str(raw.get("caption") or intent["purpose"]).strip(),
        }

    def _empty_model(self, intent: VisualIntent) -> VisualModel:
        return {
            "id": "empty_timeline_sequence",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": {"actors": [], "messages": [], "mode": intent["mode"]},
            "frames": [],
            "element_catalog": [],
        }

    def _compile_static(
        self,
        intent: VisualIntent,
        base: dict[str, Any],
        context: CompileContext,
    ) -> VisualModel:
        state = self._normalize_state({"visible_messages": [message["id"] for message in base.get("messages") or []]}, base)
        frame: VisualFrame = {
            "index": 0,
            "state": state,
            "highlights": {},
            "annotations": [],
            "selectable_elements": self.selectable_elements(state, base, intent["mode"]),
            "transitions": [],
        }
        return {
            "id": f"timeline_static_{context['topic_id']}",
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
                    "active_actor": state.get("active_actor"),
                    "active_message": state.get("active_message"),
                },
                "annotations": [
                    {
                        "id": f"timeline_note_{index}",
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
            "id": f"timeline_{context['topic_id']}_{plan['id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": frames,
            "element_catalog": self._catalog(base),
        }

    def _normalize_state(self, raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        actor_ids = {actor["id"] for actor in base.get("actors") or []}
        message_ids = {message["id"] for message in base.get("messages") or []}
        active_actor = self._known_id(raw.get("active_actor"), actor_ids)
        active_message = self._known_id(raw.get("active_message"), message_ids)
        visible_messages = self._visible_ids(raw.get("visible_messages"), message_ids)
        actor_states = raw.get("actor_states") or {}
        if not isinstance(actor_states, dict):
            actor_states = {}
        return {
            "active_actor": active_actor,
            "active_message": active_message,
            "visible_messages": visible_messages,
            "actor_states": {str(k): str(v) for k, v in actor_states.items() if str(k) in actor_ids},
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
        actors = base.get("actors") or []
        visible_messages = set(frame_state.get("visible_messages") or [message["id"] for message in base.get("messages") or []])
        for index, actor in enumerate(actors):
            elements.append(
                {
                    "element_id": actor["id"],
                    "element_type": "actor_lane",
                    "semantic_label": f"actor {actor['label']}",
                    "bounds": {"x": float(index) * 25.0, "y": 0.0, "width": 20.0, "height": 100.0},
                    "aria_label": f"Actor {actor['label']}",
                    "keyboard_index": keyboard_index,
                    "payload": actor,
                }
            )
            keyboard_index += 1
        for message in base.get("messages") or []:
            if message["id"] not in visible_messages:
                continue
            elements.append(
                {
                    "element_id": message["id"],
                    "element_type": "message",
                    "semantic_label": f"message {message['label']} from {message['from']} to {message['to']}",
                    "bounds": {"x": 0.0, "y": float(message["time"]) * 12.0, "width": 100.0, "height": 8.0},
                    "aria_label": f"Message {message['label']}",
                    "keyboard_index": keyboard_index,
                    "payload": message,
                }
            )
            keyboard_index += 1
        return elements

    def _mode_palette(self, mode: str) -> dict[str, Any]:
        if mode == "protocol_sequence":
            return {"accent": "#7C4EF0", "message_draw_ms": 350}
        if mode == "request_response":
            return {"accent": "#1976D2", "message_draw_ms": 320}
        if mode == "message_passing":
            return {"accent": "#5B2EE0", "message_draw_ms": 330}
        if mode == "race_condition":
            return {"accent": "#D32F2F", "message_draw_ms": 280}
        if mode == "thread_schedule":
            return {"accent": "#2E7D32", "message_draw_ms": 300}
        if mode == "lock_acquisition":
            return {"accent": "#E76F51", "message_draw_ms": 380}
        if mode == "oauth_flow":
            return {"accent": "#1976D2", "message_draw_ms": 340}
        if mode == "transaction_timeline":
            return {"accent": "#2E7D32", "message_draw_ms": 360}
        return {"accent": "#7C4EF0", "message_draw_ms": 350}

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
        old_visible = set(prev_frame_state.get("visible_messages") or [])
        new_visible: list[str] = [
            mid for mid in (curr_frame_state.get("visible_messages") or [])
            if mid not in old_visible
        ]
        # If many messages appear at once (typical for handshake completion
        # or transaction commit), cascade them as a stagger_group.
        if len(new_visible) > 1:
            transitions.append({
                "kind": "stagger_group",
                "target_element_id": new_visible[0],
                "duration_ms": palette["message_draw_ms"] * len(new_visible),
                "delay_ms": 0,
                "easing": "ease_out",
                "spec": {"group_element_ids": new_visible, "stagger_ms": 180},
            })
        else:
            for message_id in new_visible:
                transitions.append(
                    {
                        "kind": "appear",
                        "target_element_id": message_id,
                        "duration_ms": palette["message_draw_ms"],
                        "delay_ms": 0,
                        "easing": "ease_out",
                        "spec": {"draw": True, "color": palette["accent"]},
                    }
                )

        active = curr_frame_state.get("active_message") or curr_frame_state.get("active_actor")
        if active:
            transitions.append(
                {
                    "kind": "highlight_pulse",
                    "target_element_id": str(active),
                    "duration_ms": 420,
                    "delay_ms": 100,
                    "easing": "ease_out",
                    "spec": {"color": palette["accent"]},
                }
            )

        # Mode-specific: race_condition + lock_acquisition pulse blocked
        # actor lanes so the learner sees waiting/contention.
        if mode in ("race_condition", "lock_acquisition"):
            curr_blocked = set(curr_frame_state.get("blocked_actors") or [])
            prev_blocked = set(prev_frame_state.get("blocked_actors") or [])
            for actor_id in curr_blocked - prev_blocked:
                transitions.append({
                    "kind": "highlight_pulse",
                    "target_element_id": str(actor_id),
                    "duration_ms": 600,
                    "delay_ms": 0,
                    "easing": "ease_out",
                    "spec": {"color": "#D32F2F", "cycles": 2},
                })
            for actor_id in prev_blocked - curr_blocked:
                transitions.append({
                    "kind": "style_change",
                    "target_element_id": str(actor_id),
                    "duration_ms": 280,
                    "delay_ms": 0,
                    "easing": "ease_out",
                    "spec": {"from_style": "blocked", "to_style": "running"},
                })
        return transitions

    def _active_element_id(self, state: dict[str, Any]) -> str | None:
        return state.get("active_message") or state.get("active_actor")

    def _catalog(self, base: dict[str, Any]) -> list:
        catalog = []
        for index, actor in enumerate(base.get("actors") or []):
            catalog.append(
                {
                    "element_id": actor["id"],
                    "element_type": "actor_lane",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": float(index) * 25.0, "y": 0.0, "width": 20.0, "height": 100.0},
                }
            )
        for message in base.get("messages") or []:
            catalog.append(
                {
                    "element_id": message["id"],
                    "element_type": "message",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {"x": 0.0, "y": float(message["time"]) * 12.0, "width": 100.0, "height": 8.0},
                }
            )
        return catalog


register(TimelineSequenceCompiler())
