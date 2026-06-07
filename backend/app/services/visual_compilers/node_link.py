"""NodeLink compiler — produces VisualModels for tree/graph/state-machine/
linked-list/circuit visuals.

Ports the logic from `_materialize_node_link_worked_example_to_cards` and
`_synthesize_node_link_plan_from_lean_cards` in the legacy generator, with
two additions:
  - emits SelectableElement[] per frame (nodes, edges, stack items, output)
  - emits Transition[] per frame (state_change, move, appear, fade_in)

The compiler is fully self-contained — does not import from the legacy
generator at runtime (it imports a few validators but they're pure
functions). The legacy generator continues to use its own materializer.
"""

from __future__ import annotations

import copy
from typing import Any

from app.schemas.visual_v2 import (
    CompileContext,
    ElementBounds,
    ElementCatalogEntry,
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
from app.services.v2_aria_localization import localize_aria


# ---------------------------------------------------------------------------
# Internal node/edge canonical shape used inside the compiler.
# These are dicts (not TypedDicts) for ergonomics; we validate keys at
# entry/exit.
# ---------------------------------------------------------------------------

_NODE_REQUIRED_KEYS = ("id", "label", "relation", "x", "y")
_EDGE_REQUIRED_KEYS = ("from", "to", "label", "style")


# State strings allowed in state_after.node_state_map (mirrors the legacy
# _NODE_STATE_TO_RELATION_OVERLAY mapping).
_NODE_STATES = frozenset({
    "unvisited",
    "discovered",
    "newly_discovered",
    "current",
    "completed",
    "skipped",
})

_EDGE_STATES = frozenset({
    "unchecked",
    "active",
    "traversed",
    "checked",
    "skipped",
    "completed",
})


def _normalize_node(raw: Any, fallback_index: int) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    node_id = str(raw.get("id") or raw.get("label") or "").strip()
    if not node_id:
        return None
    return {
        "id": node_id,
        "label": str(raw.get("label") or node_id).strip(),
        "relation": str(raw.get("relation") or "node").strip(),
        "description": str(raw.get("description") or "").strip(),
        "x": float(raw["x"]) if isinstance(raw.get("x"), (int, float)) else 50.0,
        "y": (
            float(raw["y"])
            if isinstance(raw.get("y"), (int, float))
            else 20.0 + fallback_index * 12.0
        ),
        "state": str(raw.get("state") or "unvisited").strip(),
    }


def _normalize_edge(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    from_id = str(raw.get("from") or "").strip()
    to_id = str(raw.get("to") or "").strip()
    if not from_id or not to_id:
        return None
    return {
        "from": from_id,
        "to": to_id,
        "label": str(raw.get("label") or "").strip(),
        "style": str(raw.get("style") or "solid").strip(),
        "state": str(raw.get("state") or "unchecked").strip(),
    }


def _normalize_runtime_variables(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    variables: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        value = item.get("value")
        if isinstance(value, list):
            normalized_value: Any = [str(v) for v in value]
        elif value is None:
            normalized_value = []
        else:
            normalized_value = str(value)
        variables.append({"name": name, "value": normalized_value})
    return variables


# ---------------------------------------------------------------------------
# COMPILER
# ---------------------------------------------------------------------------


class NodeLinkCompiler(VisualCompiler):
    base_type = "node_link_diagram"

    # ---- main entrypoint --------------------------------------------------

    def compile(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan | None,
        context: CompileContext,
    ) -> VisualModel:
        # Build the base structure
        base = self._build_base(plan, intent, context)
        if not base.get("nodes"):
            # Empty visual — emit a placeholder model so the orchestrator
            # has something to point at, but with no frames worth rendering.
            return self._empty_model(intent)

        # Static visual (no plan): one frame with everything unvisited
        if plan is None:
            return self._compile_static(intent, base, context)

        # Dynamic visual: one frame per plan.steps[i]
        return self._compile_dynamic(intent, plan, base, context)

    # ---- base structure ---------------------------------------------------

    def _build_base(
        self,
        plan: WorkedExamplePlan | None,
        intent: VisualIntent,
        context: CompileContext,
    ) -> dict[str, Any]:
        """Pull nodes/edges from plan.base_state, or fall back to the
        already-compiled background card's nodes if available."""

        if plan is not None:
            base_state = plan.get("base_state") or {}
            raw_nodes = base_state.get("nodes") or []
            raw_edges = base_state.get("edges") or []
            nodes = []
            for index, raw in enumerate(raw_nodes):
                normalized = _normalize_node(raw, index)
                if normalized:
                    nodes.append(normalized)
            edges = []
            for raw in raw_edges:
                normalized = _normalize_edge(raw)
                if normalized:
                    edges.append(normalized)
            if nodes:
                return {
                    "mode": intent["mode"],
                    "nodes": nodes,
                    "edges": edges,
                    "visual_blueprint": str(
                        base_state.get("visual_blueprint") or ""
                    ),
                    "purpose": intent["purpose"],
                }

        # Fallback: look at already-compiled background-card model in context
        bg_model = self._find_background_model(context)
        if bg_model:
            return {
                "mode": intent["mode"],
                "nodes": [dict(n) for n in bg_model["base"].get("nodes") or []],
                "edges": [dict(e) for e in bg_model["base"].get("edges") or []],
                "visual_blueprint": str(
                    bg_model["base"].get("visual_blueprint") or ""
                ),
                "purpose": intent["purpose"],
            }

        return {"mode": intent["mode"], "nodes": [], "edges": [], "purpose": intent["purpose"]}

    def _find_background_model(
        self,
        context: CompileContext,
    ) -> VisualModel | None:
        for model in context["already_compiled_models"].values():
            if model["base_type"] == self.base_type and model["base"].get("nodes"):
                # Prefer the model that's marked as static (background)
                if model["base"].get("source") == "background":
                    return model
        # Fallback: any node_link model with nodes
        for model in context["already_compiled_models"].values():
            if model["base_type"] == self.base_type and model["base"].get("nodes"):
                return model
        return None

    def _empty_model(self, intent: VisualIntent) -> VisualModel:
        return {
            "id": f"empty_{intent['base_type']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": {"nodes": [], "edges": []},
            "frames": [],
            "element_catalog": [],
        }

    # ---- static (background) ---------------------------------------------

    def _compile_static(
        self,
        intent: VisualIntent,
        base: dict[str, Any],
        context: CompileContext,
    ) -> VisualModel:
        base["source"] = "background"
        frame_state: dict[str, Any] = {
            "active_node": "",
            "completed_nodes": [],
            "node_state_map": [],
            "runtime_state": {"call_stack": [], "output": [], "frontier": []},
        }
        selectable = self.selectable_elements(frame_state, base, intent["mode"])
        frame: VisualFrame = {
            "index": 0,
            "state": frame_state,
            "highlights": {"active_node": "", "highlight_path": []},
            "annotations": [],
            "selectable_elements": selectable,
            "transitions": [],
        }
        catalog = self._build_catalog(base, [frame])
        return {
            "id": f"node_link_{context['topic_id']}_background",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": [frame],
            "element_catalog": catalog,
        }

    # ---- dynamic (worked example) ----------------------------------------

    def _compile_dynamic(
        self,
        intent: VisualIntent,
        plan: WorkedExamplePlan,
        base: dict[str, Any],
        context: CompileContext,
    ) -> VisualModel:
        steps = plan["steps"]
        frames: list[VisualFrame] = []
        prev_state: dict[str, Any] | None = None

        for index, step in enumerate(steps):
            curr_state = self._normalize_state_after(step.get("state_after") or {}, base)
            selectable = self.selectable_elements(curr_state, base, intent["mode"])
            transitions = self.transitions(
                prev_state,
                curr_state,
                base,
                intent["mode"],
                step.get("transition_hints") or [],
            )

            attention = (
                str(curr_state.get("attention_note") or "").strip()
                or f"Step {index + 1}: {step.get('action') or ''}".strip(": ")
            )
            annotation_id = f"step_{index + 1}_note"
            annotations: list[dict[str, Any]] = []
            if attention:
                annotations.append({
                    "id": annotation_id,
                    "text": attention,
                    "attached_to_element_id": (
                        curr_state.get("active_node") or None
                    ),
                    "appears_in_frame": index,
                })

            frame: VisualFrame = {
                "index": index,
                "state": curr_state,
                "highlights": {
                    "active_node": curr_state.get("active_node") or "",
                    "highlight_path": list(
                        curr_state.get("completed_nodes") or []
                    ),
                },
                "annotations": annotations,
                "selectable_elements": selectable,
                "transitions": transitions,
            }
            frames.append(frame)
            prev_state = curr_state

        catalog = self._build_catalog(base, frames)
        return {
            "id": f"node_link_{context['topic_id']}_{plan['id']}",
            "base_type": self.base_type,
            "mode": intent["mode"],
            "base": base,
            "frames": frames,
            "element_catalog": catalog,
        }

    # ---- state_after normalization ---------------------------------------

    def _normalize_state_after(
        self,
        raw: dict[str, Any],
        base: dict[str, Any],
    ) -> dict[str, Any]:
        valid_node_ids = {str(n["id"]) for n in base["nodes"]}

        active_node = str(raw.get("active_node") or "").strip()
        if active_node not in valid_node_ids:
            active_node = ""

        completed_nodes = [
            str(n) for n in (raw.get("completed_nodes") or [])
            if str(n) in valid_node_ids
        ]
        # de-dupe preserving order
        seen: set[str] = set()
        completed_nodes = [
            n for n in completed_nodes if not (n in seen or seen.add(n))
        ]

        node_state_map: list[dict[str, str]] = []
        raw_map = raw.get("node_state_map") or []
        if isinstance(raw_map, list):
            for entry in raw_map:
                if not isinstance(entry, dict):
                    continue
                node_id = str(entry.get("node_id") or "").strip()
                state = str(entry.get("state") or "").strip()
                if node_id in valid_node_ids and state in _NODE_STATES:
                    node_state_map.append({"node_id": node_id, "state": state})

        active_edge_from = str(raw.get("active_edge_from") or "").strip()
        active_edge_to = str(raw.get("active_edge_to") or "").strip()
        if active_edge_from not in valid_node_ids or active_edge_to not in valid_node_ids:
            active_edge_from = ""
            active_edge_to = ""

        completed_edges = [
            (str(f), str(t))
            for f, t in zip(
                raw.get("completed_edges_from") or [],
                raw.get("completed_edges_to") or [],
            )
            if str(f) in valid_node_ids and str(t) in valid_node_ids
        ]

        runtime = raw.get("runtime_state") or {}
        if not isinstance(runtime, dict):
            runtime = {}
        runtime_state = {
            "call_stack": [str(x) for x in (runtime.get("call_stack") or [])],
            "output": [str(x) for x in (runtime.get("output") or [])],
            "frontier": [str(x) for x in (runtime.get("frontier") or [])],
            "frontier_kind": str(runtime.get("frontier_kind") or ""),
            "variables": _normalize_runtime_variables(runtime.get("variables") or []),
        }

        return {
            "active_node": active_node,
            "completed_nodes": completed_nodes,
            "node_state_map": node_state_map,
            "active_edge_from": active_edge_from,
            "active_edge_to": active_edge_to,
            "completed_edges": completed_edges,
            "runtime_state": runtime_state,
            "attention_note": str(raw.get("attention_note") or "").strip(),
        }

    # ---- catalog ---------------------------------------------------------

    def _build_catalog(
        self,
        base: dict[str, Any],
        frames: list[VisualFrame],
    ) -> list[ElementCatalogEntry]:
        catalog: list[ElementCatalogEntry] = []
        for node in base["nodes"]:
            catalog.append({
                "element_id": str(node["id"]),
                "element_type": "node",
                "first_frame": 0,
                "last_frame": -1,
                "initial_bounds": {
                    "x": float(node["x"]) - 4.0,
                    "y": float(node["y"]) - 4.0,
                    "width": 8.0,
                    "height": 8.0,
                },
            })
        for edge in base.get("edges") or []:
            edge_id = f"{edge['from']}->{edge['to']}"
            # Bounds = midpoint of the edge endpoints (approximate)
            from_node = next(
                (n for n in base["nodes"] if str(n["id"]) == str(edge["from"])),
                None,
            )
            to_node = next(
                (n for n in base["nodes"] if str(n["id"]) == str(edge["to"])),
                None,
            )
            if from_node and to_node:
                mx = (float(from_node["x"]) + float(to_node["x"])) / 2.0
                my = (float(from_node["y"]) + float(to_node["y"])) / 2.0
                catalog.append({
                    "element_id": edge_id,
                    "element_type": "edge",
                    "first_frame": 0,
                    "last_frame": -1,
                    "initial_bounds": {
                        "x": mx - 3.0,
                        "y": my - 3.0,
                        "width": 6.0,
                        "height": 6.0,
                    },
                })
        # Stack / output / frontier items — these are dynamic. We add them
        # under a synthetic id like "stack_item_0", "output_item_3" so the
        # frontend can render them inside the side panels.
        max_stack_depth = 0
        max_output_len = 0
        for frame in frames:
            runtime = frame["state"].get("runtime_state") or {}
            max_stack_depth = max(max_stack_depth, len(runtime.get("call_stack") or []))
            max_output_len = max(max_output_len, len(runtime.get("output") or []))
        for i in range(max_stack_depth):
            catalog.append({
                "element_id": f"stack_item_{i}",
                "element_type": "stack_item",
                "first_frame": 0,
                "last_frame": -1,
                "initial_bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
            })
        for i in range(max_output_len):
            catalog.append({
                "element_id": f"output_item_{i}",
                "element_type": "output_item",
                "first_frame": 0,
                "last_frame": -1,
                "initial_bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
            })
        return catalog

    # ---- selectable elements ---------------------------------------------

    def selectable_elements(
        self,
        frame_state: dict[str, Any],
        base: dict[str, Any],
        mode: str,
    ) -> list[SelectableElement]:
        elements: list[SelectableElement] = []
        keyboard_index = 0

        node_state_map = {
            entry["node_id"]: entry["state"]
            for entry in (frame_state.get("node_state_map") or [])
            if isinstance(entry, dict)
        }
        active_node = str(frame_state.get("active_node") or "")
        completed = set(str(n) for n in (frame_state.get("completed_nodes") or []))

        for node in base["nodes"]:
            node_id = str(node["id"])
            if node_id in node_state_map:
                state = node_state_map[node_id]
            elif node_id == active_node and active_node:
                state = "current"
            elif node_id in completed:
                state = "completed"
            else:
                state = "unvisited"
            semantic = f"node {node['label']}"
            if state == "current":
                semantic += " (current node, being processed now)"
            elif state == "completed":
                semantic += " (already visited)"
            elements.append({
                "element_id": node_id,
                "element_type": "node",
                "semantic_label": semantic,
                "bounds": {
                    "x": float(node["x"]) - 4.0,
                    "y": float(node["y"]) - 4.0,
                    "width": 8.0,
                    "height": 8.0,
                },
                "aria_label": localize_aria(
                    "node_with_role" if node.get("relation") else "node",
                    label=node["label"],
                    role=node.get("relation") or "",
                    state=state,
                ),
                "keyboard_index": keyboard_index,
                "payload": {
                    "node_id": node_id,
                    "label": node["label"],
                    "relation": node["relation"],
                    "state": state,
                },
            })
            keyboard_index += 1

        active_edge_from = str(frame_state.get("active_edge_from") or "")
        active_edge_to = str(frame_state.get("active_edge_to") or "")
        completed_edges = {
            (str(f), str(t))
            for f, t in (frame_state.get("completed_edges") or [])
        }
        for edge in base.get("edges") or []:
            edge_id = f"{edge['from']}->{edge['to']}"
            if edge["from"] == active_edge_from and edge["to"] == active_edge_to:
                edge_state = "active"
            elif (edge["from"], edge["to"]) in completed_edges:
                edge_state = "traversed"
            else:
                edge_state = "unchecked"
            elements.append({
                "element_id": edge_id,
                "element_type": "edge",
                "semantic_label": (
                    f"edge from {edge['from']} to {edge['to']}, state {edge_state}"
                ),
                "bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
                "aria_label": localize_aria(
                    "edge_with_label" if edge.get("label") else "edge",
                    from_id=edge["from"],
                    to_id=edge["to"],
                    label=edge.get("label") or "",
                ),
                "keyboard_index": keyboard_index,
                "payload": {
                    "from": edge["from"],
                    "to": edge["to"],
                    "state": edge_state,
                },
            })
            keyboard_index += 1

        # Side-panel items
        runtime = frame_state.get("runtime_state") or {}
        active_node = str(frame_state.get("active_node") or "")
        if active_node:
            elements.append({
                "element_id": "runtime_current",
                "element_type": "runtime_variable",
                "semantic_label": f"current node: {active_node}",
                "bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
                "aria_label": f"Current node {active_node}",
                "keyboard_index": keyboard_index,
                "payload": {"name": "current", "value": active_node},
            })
            keyboard_index += 1
        for i, item in enumerate(runtime.get("call_stack") or []):
            elements.append({
                "element_id": f"stack_item_{i}",
                "element_type": "stack_item",
                "semantic_label": f"call stack entry: {item}",
                "bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
                "aria_label": localize_aria("stack_item", depth=i, value=item),
                "keyboard_index": keyboard_index,
                "payload": {"depth": i, "value": item},
            })
            keyboard_index += 1
        frontier = runtime.get("frontier") or []
        frontier_kind = str(runtime.get("frontier_kind") or "")
        if active_node and frontier_kind and not frontier:
            elements.append({
                "element_id": "frontier_empty",
                "element_type": "runtime_variable",
                "semantic_label": f"{frontier_kind} is currently empty",
                "bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
                "aria_label": f"{frontier_kind} is empty",
                "keyboard_index": keyboard_index,
                "payload": {"name": frontier_kind, "value": "[]"},
            })
            keyboard_index += 1
        for i, item in enumerate(frontier):
            elements.append({
                "element_id": f"frontier_item_{i}",
                "element_type": "runtime_variable",
                "semantic_label": f"{frontier_kind or 'frontier'} entry: {item}",
                "bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
                "aria_label": f"{frontier_kind or 'frontier'} item {item}",
                "keyboard_index": keyboard_index,
                "payload": {"index": i, "value": item, "name": frontier_kind or "frontier"},
            })
            keyboard_index += 1
        if active_node and not (runtime.get("output") or []):
            elements.append({
                "element_id": "output_empty",
                "element_type": "output_item",
                "semantic_label": "output is currently empty",
                "bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
                "aria_label": "Output is empty",
                "keyboard_index": keyboard_index,
                "payload": {"index": 0, "value": "[]"},
            })
            keyboard_index += 1
        for i, item in enumerate(runtime.get("output") or []):
            elements.append({
                "element_id": f"output_item_{i}",
                "element_type": "output_item",
                "semantic_label": f"output entry: {item}",
                "bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
                "aria_label": localize_aria("output_item", index=i, value=item),
                "keyboard_index": keyboard_index,
                "payload": {"index": i, "value": item},
            })
            keyboard_index += 1
        for variable_index, variable in enumerate(runtime.get("variables") or []):
            if not isinstance(variable, dict):
                continue
            name = str(variable.get("name") or "").strip()
            if not name or name.lower() in {"current", "output", "result"}:
                continue
            values = variable.get("value")
            value_list = values if isinstance(values, list) else [values]
            if not value_list:
                value_list = ["[]"]
            for value_index, value in enumerate(value_list):
                element_id = f"runtime_variable_{variable_index}_{value_index}"
                elements.append({
                    "element_id": element_id,
                    "element_type": "runtime_variable",
                    "semantic_label": f"{name}: {value}",
                    "bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
                    "aria_label": f"{name}: {value}",
                    "keyboard_index": keyboard_index,
                    "payload": {"name": name, "value": value},
                })
                keyboard_index += 1

        return elements

    # ---- transitions -----------------------------------------------------

    def _mode_palette(self, mode: str) -> dict[str, Any]:
        """Per-mode color + pulse policy. Helps the learner distinguish
        a state_machine transition from a tree-traversal highlight."""
        if mode == "state_machine":
            return {"active_color": "#1976D2", "pulse_duration_ms": 700, "pulse_cycles": 2}
        if mode == "circuit":
            return {"active_color": "#E76F51", "pulse_duration_ms": 500, "pulse_cycles": 1}
        if mode == "er_diagram":
            return {"active_color": "#2E7D32", "pulse_duration_ms": 500, "pulse_cycles": 1}
        if mode == "automata":
            return {"active_color": "#1976D2", "pulse_duration_ms": 700, "pulse_cycles": 2}
        if mode == "data_pipeline":
            return {"active_color": "#5B2EE0", "pulse_duration_ms": 500, "pulse_cycles": 1}
        # tree_hierarchy, graph_network, linked_list_chain, dependency_graph,
        # recursion_tree, resource_graph, architecture_container — default
        return {"active_color": "#7C4EF0", "pulse_duration_ms": 600, "pulse_cycles": 1}

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

        # Node state changes
        prev_active = str(prev_frame_state.get("active_node") or "")
        curr_active = str(curr_frame_state.get("active_node") or "")
        prev_completed = set(str(n) for n in (prev_frame_state.get("completed_nodes") or []))
        curr_completed = set(str(n) for n in (curr_frame_state.get("completed_nodes") or []))

        # Node that was active becomes completed
        if prev_active and prev_active != curr_active and prev_active in curr_completed:
            transitions.append({
                "kind": "style_change",
                "target_element_id": prev_active,
                "duration_ms": 300,
                "delay_ms": 0,
                "easing": "ease_out",
                "spec": {"from_style": "current", "to_style": "completed"},
            })

        # New active node
        if curr_active and curr_active != prev_active:
            # Mode-specific palette: state_machine + circuit get distinctive
            # colors so the learner can tell base_types apart at a glance.
            palette = self._mode_palette(mode)
            transitions.append({
                "kind": "style_change",
                "target_element_id": curr_active,
                "duration_ms": 300,
                "delay_ms": 100 if prev_active else 0,
                "easing": "ease_in_out",
                "spec": {"from_style": "unvisited", "to_style": "current"},
            })
            transitions.append({
                "kind": "highlight_pulse",
                "target_element_id": curr_active,
                "duration_ms": palette["pulse_duration_ms"],
                "delay_ms": 200,
                "easing": "ease_out",
                "spec": {"color": palette["active_color"], "cycles": palette["pulse_cycles"]},
            })

        # Newly completed nodes (excluding the prev_active handled above)
        newly_completed = curr_completed - prev_completed - {prev_active}
        for node_id in sorted(newly_completed):
            transitions.append({
                "kind": "style_change",
                "target_element_id": node_id,
                "duration_ms": 300,
                "delay_ms": 0,
                "easing": "ease_out",
                "spec": {"from_style": "unvisited", "to_style": "completed"},
            })

        # Edge state changes
        prev_edge = (
            str(prev_frame_state.get("active_edge_from") or ""),
            str(prev_frame_state.get("active_edge_to") or ""),
        )
        curr_edge = (
            str(curr_frame_state.get("active_edge_from") or ""),
            str(curr_frame_state.get("active_edge_to") or ""),
        )
        if curr_edge != prev_edge and curr_edge[0] and curr_edge[1]:
            transitions.append({
                "kind": "style_change",
                "target_element_id": f"{curr_edge[0]}->{curr_edge[1]}",
                "duration_ms": 300,
                "delay_ms": 0,
                "easing": "ease_in_out",
                "spec": {"from_style": "unchecked", "to_style": "active"},
            })

        # Call stack changes — appear/disappear stagger
        prev_stack = list(prev_frame_state.get("runtime_state", {}).get("call_stack") or [])
        curr_stack = list(curr_frame_state.get("runtime_state", {}).get("call_stack") or [])
        # Items appended
        for i in range(len(prev_stack), len(curr_stack)):
            transitions.append({
                "kind": "appear",
                "target_element_id": f"stack_item_{i}",
                "duration_ms": 250,
                "delay_ms": (i - len(prev_stack)) * 100,
                "easing": "ease_out",
                "spec": {"value": curr_stack[i]},
            })
        # Items popped
        for i in range(len(curr_stack), len(prev_stack)):
            transitions.append({
                "kind": "disappear",
                "target_element_id": f"stack_item_{i}",
                "duration_ms": 200,
                "delay_ms": 0,
                "easing": "ease_in",
                "spec": {},
            })

        # Output appends
        prev_output = list(prev_frame_state.get("runtime_state", {}).get("output") or [])
        curr_output = list(curr_frame_state.get("runtime_state", {}).get("output") or [])
        for i in range(len(prev_output), len(curr_output)):
            transitions.append({
                "kind": "appear",
                "target_element_id": f"output_item_{i}",
                "duration_ms": 300,
                "delay_ms": 400,  # after node/edge animations
                "easing": "ease_out",
                "spec": {"value": curr_output[i]},
            })

        # Apply LLM-provided hint ordering if present
        if hints:
            transitions = self._reorder_by_hints(transitions, hints)

        return transitions

    def _reorder_by_hints(
        self,
        transitions: list[Transition],
        hints: list[TransitionHint],
    ) -> list[Transition]:
        """Apply LLM-provided ordering. The hint's `sequence` is a list of
        element_ids; transitions targeting them get sorted to that order
        with stagger_ms applied. Transitions on unmentioned elements stay
        in their original relative order at the end.
        """
        if not transitions or not hints:
            return transitions

        primary_hint = hints[0]
        order = list(primary_hint.get("sequence") or [])
        stagger = int(primary_hint.get("stagger_ms") or 150)
        if not order:
            return transitions

        ordered: list[Transition] = []
        remaining = list(transitions)
        cumulative_delay = 0
        for element_id in order:
            matched = [t for t in remaining if t["target_element_id"] == element_id]
            for t in matched:
                t = copy.deepcopy(t)
                t["delay_ms"] = cumulative_delay
                ordered.append(t)
                remaining.remove(next(r for r in remaining if r is matched[matched.index(t)]))
            if matched:
                cumulative_delay += stagger
        ordered.extend(remaining)
        return ordered

    # ---- synthesizer fallback --------------------------------------------

    def synthesize_plan_from_legacy_cards(
        self,
        legacy_cards: list[dict[str, Any]],
        context: CompileContext,
    ) -> WorkedExamplePlan | None:
        """Reconstruct a worked_example_plan from legacy lean cards.

        This is the v2 home for the synthesizer pattern in
        lean_lesson_generator._synthesize_node_link_plan_from_lean_cards.

        Pulls base_state.nodes/edges from the background card; pulls each
        step's state_after from the per-step worked_example cards' text
        (current=X, Call stack: [a→b], result=[...]).
        """
        # Find background card with node_link visual
        base_nodes: list[dict[str, Any]] = []
        base_edges: list[dict[str, Any]] = []
        for card in legacy_cards:
            if str(card.get("blueprint_key") or "").strip().lower() != "background":
                continue
            visual_plan = card.get("visual_plan") if isinstance(card.get("visual_plan"), dict) else {}
            visual_type = str(
                card.get("visual_type")
                or visual_plan.get("type")
                or ""
            ).strip().lower()
            if "node_link" not in visual_type:
                continue
            raw_nodes = card.get("visual_nodes") or visual_plan.get("nodes") or []
            raw_edges = card.get("visual_edges") or visual_plan.get("edges") or []
            for i, raw in enumerate(raw_nodes):
                normalized = _normalize_node(raw, i)
                if normalized:
                    base_nodes.append(normalized)
            for raw in raw_edges:
                normalized = _normalize_edge(raw)
                if normalized:
                    base_edges.append(normalized)
            if base_nodes:
                break
        if not base_nodes:
            return None

        # Find worked_example cards
        worked_cards = [
            c for c in legacy_cards
            if str(c.get("blueprint_key") or "").strip().lower() == "worked_example"
            and not _is_worked_example_setup_card(c)
        ]
        if not worked_cards:
            return None

        valid_labels = {str(n["label"]) for n in base_nodes} | {str(n["id"]) for n in base_nodes}

        import re

        def extract_current(card: dict[str, Any]) -> str:
            text = " ".join([
                str(card.get("title") or ""),
                str(card.get("visual_description") or ""),
                " ".join(str(p) for p in (card.get("points") or [])),
            ])
            # Node labels are numbers for trees (BST) but LETTERS for graphs
            # (A, B, C). Match either and filter against the real label set, so
            # graph traces get a current/active node (and thus highlighting),
            # not just numeric BST traces.
            for pattern in (
                r"\bcurrent\s*[=:]\s*([A-Za-z0-9_]{1,4})\b",
                r"\bat\s+(?:root\s+|node\s+)?([A-Za-z0-9_]{1,4})\b",
            ):
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match and match.group(1) in valid_labels:
                    return match.group(1)
            return ""

        def extract_call_stack(card: dict[str, Any]) -> list[str]:
            text = " ".join(str(p) for p in (card.get("points") or []))
            matches = list(
                re.finditer(
                    r"call\s*stack\s*[:=]\s*\[([^\]]+)\]",
                    text,
                    flags=re.IGNORECASE,
                )
            )
            if not matches:
                return []
            tokens = re.findall(r"\d{1,3}|[A-Za-z][A-Za-z0-9_]*", matches[-1].group(1))
            return [t for t in tokens if t in valid_labels]

        def extract_frontier(card: dict[str, Any]) -> tuple[list[str], str]:
            text = " ".join(str(p) for p in (card.get("points") or []))
            matches = list(
                re.finditer(
                    r"(?<!call\s)\b(stack|queue)\s*[:=]\s*\[([^\]]*)\]",
                    text,
                    flags=re.IGNORECASE,
                )
            )
            if not matches:
                return ([], "")
            kind = matches[-1].group(1).lower()
            tokens = re.findall(r"\d{1,3}|[A-Za-z]{1,2}", matches[-1].group(2))
            return ([t for t in tokens if t in valid_labels], kind)

        def extract_output(card: dict[str, Any]) -> list[str]:
            text = " ".join(str(p) for p in (card.get("points") or []))
            # Graphs report the accumulated set as "visited={A, B}" (curly
            # braces, letters); trees report "result=[16, 31]" (square brackets,
            # numbers). Match result/output/visited, either bracket style, and
            # both label kinds so the OUTPUT/visited panel renders for graphs too.
            matches = list(
                re.finditer(
                    r"(?:result|output|visited)\s*[:=]\s*[\[\{]([^\]\}]*)[\]\}]",
                    text,
                    flags=re.IGNORECASE,
                )
            )
            if not matches:
                return []
            tokens = re.findall(r"\d{1,3}|[A-Za-z][A-Za-z0-9_]*", matches[-1].group(1))
            return [t for t in tokens if t in valid_labels]

        steps = []
        cumulative_output: list[str] = []
        for i, card in enumerate(worked_cards):
            active = extract_current(card)
            stack = extract_call_stack(card)
            frontier, frontier_kind = extract_frontier(card)
            output_now = extract_output(card)
            for v in output_now:
                if v not in cumulative_output:
                    cumulative_output.append(v)
            node_state_map = [
                {"node_id": v, "state": "completed"}
                for v in cumulative_output
                if v != active
            ]
            if active:
                node_state_map.append({"node_id": active, "state": "current"})

            steps.append({
                "step_number": i + 1,
                "action": str(card.get("title") or f"Step {i + 1}"),
                "reason": str(card.get("learning_job") or ""),
                "text_points": [
                    str(p).rstrip()
                    for p in (card.get("points") or [])
                    if str(p).strip()
                ],
                "state_after": {
                    "active_node": active,
                    "completed_nodes": list(cumulative_output),
                    "node_state_map": node_state_map,
                    "active_edge_from": "",
                    "active_edge_to": "",
                    "completed_edges_from": [],
                    "completed_edges_to": [],
                    "runtime_state": {
                        "call_stack": stack,
                        "output": list(cumulative_output),
                        "frontier": frontier,
                        "frontier_kind": frontier_kind,
                        "variables": [
                            {"name": "current", "value": active or "done"},
                            {"name": "result", "value": list(cumulative_output)},
                        ],
                    },
                    "attention_note": str(card.get("what_to_notice") or ""),
                },
                "transition_hints": [],
            })

        if not steps:
            return None

        return {
            "id": "synthesized_node_link_plan",
            "visual_intent": {
                "base_type": "node_link_diagram",
                "mode": "tree_hierarchy",
                "description": f"Reconstructed from {len(worked_cards)} legacy worked-example cards.",
                "purpose": "Trace the algorithm through the structure.",
                "static_or_dynamic": "dynamic",
            },
            "problem_setup": f"Trace through the {len(base_nodes)}-node structure.",
            "terminal_state": "All steps complete.",
            "base_state": {
                "nodes": base_nodes,
                "edges": base_edges,
                "visual_blueprint": "",
            },
            "steps": steps,
        }


# Module load: register the compiler
register(NodeLinkCompiler())


def _is_worked_example_setup_card(card: dict[str, Any]) -> bool:
    metadata = card.get("metadata") if isinstance(card.get("metadata"), dict) else {}
    if metadata.get("worked_example_setup") is True:
        return True
    example_type = str(card.get("example_type") or "").strip().lower()
    if example_type in {"problem_setup", "initial_state", "worked_example_setup"}:
        return True
    title = str(card.get("title") or "").strip().lower()
    return "setup" in title or "initial state" in title or title.startswith("problem:")
