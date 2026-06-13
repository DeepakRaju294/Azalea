"""Slice 5b — apply a V2 graph-traversal visual into a legacy lesson_json.

Flow: maybe_build_v2_visual (authoritative trace + prose) -> WorkedExamplePlan ->
the existing NodeLinkCompiler (frontend-proven VisualModel) -> swap the lesson's
worked-example cards for V2 step cards that reference the model frame-by-frame.

Guarded by the default-off feature flag: `apply_v2_to_lesson` returns False and
leaves lesson_json untouched unless the topic's (mode, algorithm) is enabled.
"""
from __future__ import annotations

import copy
import math
from typing import Any, Callable, Optional

from app.services.visual_compilers import get_compiler

from .integration import detect_mode_algorithm, maybe_build_v2_visual

_ALGO_LABEL = {"bfs": "Breadth-First Search", "dfs": "Depth-First Search"}


def _layout(nodes: list[str]) -> dict[str, tuple[float, float]]:
    n = max(len(nodes), 1)
    return {
        node: (round(50 + 36 * math.cos(2 * math.pi * i / n - math.pi / 2), 1),
               round(50 + 36 * math.sin(2 * math.pi * i / n - math.pi / 2), 1))
        for i, node in enumerate(nodes)
    }


def _node_state(node, active, visited, frontier, newly) -> str:
    if node == active:
        return "current"
    if node in visited:
        return "completed"
    if node in newly:
        return "newly_discovered"
    if node in frontier:
        return "discovered"
    return "unvisited"


def to_worked_example_plan(*, example: dict, frames: list[dict], render_steps: list[dict],
                           prose: list[dict], mode: str) -> dict:
    """Convert the authoritative trace into the existing WorkedExamplePlan shape."""
    nodes = list((example.get("base_structure") or {}).get("nodes") or [])
    edges = list((example.get("base_structure") or {}).get("edges") or [])
    pos = _layout(nodes)
    base_nodes = [{"id": n, "label": n, "relation": "node", "x": pos[n][0], "y": pos[n][1]} for n in nodes]
    base_edges = [{"from": e[0], "to": e[1], "label": "", "style": "solid"}
                  for e in edges if isinstance(e, (list, tuple)) and len(e) == 2]

    steps = []
    for i, frame in enumerate(frames):
        after = frame["state_after"]
        diff = frame.get("diff") or {}
        active = after.get("active") or ""
        visited = list(after.get("visited") or [])
        frontier = list((after.get("frontier") or {}).get("items") or [])
        newly = set(diff.get("newly_added") or []) | set(diff.get("newly_completed") or [])
        node_state_map = [{"node_id": n, "state": _node_state(n, active, visited, frontier, newly)} for n in nodes]
        step_prose = prose[i] if i < len(prose) else {}
        caption = str((render_steps[i] if i < len(render_steps) else {}).get("caption", ""))
        steps.append({
            "step_number": i + 1,
            "action": caption,
            "reason": "",
            "text_points": list(step_prose.get("points") or []),
            "state_after": {
                "active_node": active,
                "completed_nodes": visited,
                "node_state_map": node_state_map,
                "runtime_state": {
                    "call_stack": [],
                    "output": list(after.get("output") or []),
                    "frontier": frontier,
                    "frontier_kind": (after.get("frontier") or {}).get("kind", ""),
                },
                "attention_note": caption,
            },
            "transition_hints": [],
        })

    intent = {
        "base_type": "node_link_diagram",
        "mode": mode,
        "description": str(example.get("learner_goal", "")),
        "purpose": str(example.get("why_this_example", "")),
        "static_or_dynamic": "dynamic",
    }
    return {
        "id": f"{example.get('example_id', 'ex')}_plan",
        "visual_intent": intent,
        "problem_setup": str(example.get("learner_goal", "")),
        "terminal_state": "",
        "base_state": {"mode": mode, "nodes": base_nodes, "edges": base_edges},
        "steps": steps,
    }


def compile_model(*, plan: dict, topic: dict, mode: str, model_id: str) -> Optional[dict]:
    compiler = get_compiler("node_link_diagram")
    if compiler is None:
        return None
    context = {
        "topic_id": str(topic.get("id", "")),
        "topic_hint": str(topic.get("title", "")),
        "topic_type": str(topic.get("topic_type", "") or topic.get("course_type", "") or ""),
        "visual_domain": "graph",
        "locale": "en",
        "source_chunks_excerpt": "",
        "already_compiled_models": {},
    }
    model = compiler.compile(plan["visual_intent"], plan, context)
    if model:
        model["id"] = model_id
    return model


def _v2_step_cards(*, model: dict, prose: list[dict], render_steps: list[dict], algorithm: str) -> list[dict]:
    label = _ALGO_LABEL.get(algorithm, "Traversal")
    frames = model.get("frames") or []
    cards = []
    for i, frame in enumerate(frames):
        state = frame.get("state") or {}
        active = state.get("active_node") or ""
        caption = str((render_steps[i] if i < len(render_steps) else {}).get("caption", ""))
        points = list((prose[i] if i < len(prose) else {}).get("points") or [])
        cards.append({
            "id": f"v2-{model['id']}-step-{i + 1}",
            "blueprint_key": "worked_example",
            "card_type": "worked_example",
            "title": f"{label} Step {i + 1}: Visit {active}" if active else f"{label} Step {i + 1}",
            "points": points,
            "body": [],
            "bullets": [],
            "main_concept": caption,
            "visual_type": "node_link_diagram",
            "visual_v2_ref": {"visual_model_id": model["id"], "frame_index": i, "source": "v2_pipeline"},
            "visual_focus": {"active_nodes": [active] if active else [], "highlight_path": [],
                             "active_step": i, "attention_note": caption},
            "estimated_seconds": 30,
        })
    return cards


def apply_v2_to_lesson(
    lesson_json: dict,
    topic: dict,
    *,
    generate_example: Optional[Callable[..., Any]] = None,
    generate_prose: Optional[Callable[..., Any]] = None,
) -> bool:
    """If the topic is V2-enabled, replace its worked-example cards with a V2
    trace and attach the model. Returns True if applied (lesson_json mutated)."""
    if not isinstance(lesson_json, dict):
        return False
    mode, algorithm = detect_mode_algorithm(topic)
    if not mode or not algorithm:
        return False

    result = maybe_build_v2_visual(topic, generate_example=generate_example, generate_prose=generate_prose)
    if not result or result.get("status") != "validated":
        return False

    example = result["example"]
    model_id = f"v2_{algorithm}_{topic.get('id', 'topic')}"
    plan = to_worked_example_plan(
        example=example, frames=result["frames"], render_steps=result["render_steps"],
        prose=result.get("prose") or [], mode=mode,
    )
    model = compile_model(plan=plan, topic=topic, mode=mode, model_id=model_id)
    if not model or not model.get("frames"):
        return False

    step_cards = _v2_step_cards(model=model, prose=result.get("prose") or [],
                               render_steps=result["render_steps"], algorithm=algorithm)
    if not step_cards:
        return False

    # Attach the model.
    models = lesson_json.setdefault("visual_models", [])
    models[:] = [m for m in models if m.get("id") != model_id]
    models.append(model)

    # Replace the existing worked-example cards with the V2 step cards (in place).
    cards = list(lesson_json.get("lesson_cards") or [])
    rebuilt: list[dict] = []
    inserted = False
    for card in cards:
        is_worked = str(card.get("blueprint_key") or card.get("card_type") or "").lower() == "worked_example"
        if is_worked:
            if not inserted:
                rebuilt.extend(step_cards)
                inserted = True
            continue  # drop the legacy worked card
        rebuilt.append(card)
    if not inserted:
        # No existing worked cards — insert before the first practice card, else append.
        idx = next((j for j, c in enumerate(rebuilt)
                    if str(c.get("blueprint_key") or "").lower() == "practice"), len(rebuilt))
        rebuilt[idx:idx] = step_cards
    lesson_json["lesson_cards"] = rebuilt
    lesson_json.setdefault("metadata", {})["visual_v2_applied"] = {
        "mode": mode, "algorithm": algorithm, "model_id": model_id, "steps": len(step_cards),
    }
    return True
