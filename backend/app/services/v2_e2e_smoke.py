"""End-to-end smoke verification for the v2 lesson pipeline.

The pipeline has been smoke-tested only on node_link / BST. This script
exercises every base_type with a synthetic topic + mock LLM output and
runs the full compile path. Failures surface compiler-side bugs that
the contract tests can't catch (state shape inconsistencies, missing
selectable_element ids, etc.).

Two modes:

  1. SYNTHETIC (no LLM): runs each base_type through compile_lesson_v2()
     with a minimal hand-crafted lesson_v2_raw dict. Verifies the
     compiler + orchestrator + validator chain end-to-end without
     depending on the LLM.

  2. LIVE (with LLM): given a topic_id, fetches the actual v2 lesson via
     the live LLM call. Use this to gut-check each base_type with real
     prompts before Phase 7 cutover.

Run:
    python -m app.services.v2_e2e_smoke              # synthetic mode
    python -m app.services.v2_e2e_smoke --topic <id> # live mode
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app.core.visual_ontology_v2 import (
    BASE_VISUAL_TYPES,
    DOMAIN_TO_BASE_TYPE,
    DOMAIN_TO_DEFAULT_MODE,
    MODES_BY_BASE_TYPE,
)
from app.services.lean_lesson_generator_v2 import compile_lesson_v2
from app.services.visual_validators_v2 import validate_lesson_v2


# ---------------------------------------------------------------------------
# Synthetic base_states — minimal but compiler-acceptable structure per type.
# Each one must be enough to make the compiler emit a non-empty model.
# ---------------------------------------------------------------------------

_SYNTHETIC_BASE_STATES: dict[str, dict[str, Any]] = {
    "node_link_diagram": {
        "nodes": [
            {"id": "A", "label": "A", "relation": "root", "x": 50.0, "y": 16.0},
            {"id": "B", "label": "B", "relation": "node", "x": 28.0, "y": 42.0},
            {"id": "C", "label": "C", "relation": "node", "x": 72.0, "y": 42.0},
        ],
        "edges": [
            {"from": "A", "to": "B", "label": "", "style": "solid"},
            {"from": "A", "to": "C", "label": "", "style": "solid"},
        ],
    },
    "indexed_sequence_diagram": {
        "values": ["1", "3", "5", "7", "9"],
        "pointer_definitions": [
            {"id": "l", "label": "left"},
            {"id": "r", "label": "right"},
        ],
    },
    "code_execution_panel": {
        "code": "def f(n):\n    if n <= 1:\n        return n\n    return f(n-1) + f(n-2)",
        "language": "python",
    },
    "formula_symbolic_expression": {
        "expression": "P(A|B) = P(B|A) * P(A) / P(B)",
        "symbols": [{"symbol": "P(A|B)", "meaning": "posterior", "value": ""}],
    },
    "table_diagram": {
        "columns": ["Algorithm", "Time", "Space"],
        "rows": [["BFS", "O(V+E)", "O(V)"], ["DFS", "O(V+E)", "O(V)"]],
    },
    "grid_matrix_diagram": {
        "cells": [["0", "0", "0"], ["0", "0", "0"], ["0", "0", "0"]],
        "row_labels": ["r0", "r1", "r2"],
        "column_labels": ["c0", "c1", "c2"],
    },
    "coordinate_graph": {
        "axes": {"x_min": 0.0, "x_max": 10.0, "y_min": 0.0, "y_max": 1.0,
                 "x_label": "x", "y_label": "y"},
        "curves": [
            {
                "id": "c1",
                "label": "y = x/10",
                "points": [{"x": float(i), "y": float(i) / 10.0} for i in range(11)],
            }
        ],
        "points": [],
    },
    "memory_layout_diagram": {
        "frames": [{"id": "main", "label": "main", "variables": [{"name": "n", "value": "5"}]}],
        "objects": [],
        "pointers": [],
    },
    "geometric_diagram": {
        "points": [
            {"id": "p1", "label": "A", "x": 10.0, "y": 10.0},
            {"id": "p2", "label": "B", "x": 50.0, "y": 10.0},
            {"id": "p3", "label": "C", "x": 30.0, "y": 40.0},
        ],
        "segments": [
            {"id": "s1", "from": "p1", "to": "p2", "label": ""},
            {"id": "s2", "from": "p2", "to": "p3", "label": ""},
            {"id": "s3", "from": "p3", "to": "p1", "label": ""},
        ],
        "regions": [{"id": "tri", "label": "Triangle ABC", "points": ["p1", "p2", "p3"]}],
    },
    "timeline_sequence_interaction": {
        "actors": [{"id": "client", "label": "Client"}, {"id": "server", "label": "Server"}],
        "messages": [{"id": "m1", "from": "client", "to": "server", "label": "SYN", "time": 0}],
    },
    "set_region_diagram": {
        "sets": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
        "regions": [{"id": "A_intersect_B", "label": "A ∩ B", "members": ["A", "B"]}],
        "elements": [],
    },
    "image_real_world_illustration": {
        "image_prompt": "A small fast desk drawer next to a large filing cabinet",
        "caption": "Cache as a fast desk drawer",
    },
}


def _synthetic_step(state_after: dict[str, Any]) -> dict[str, Any]:
    return {
        "step_number": 1,
        "action": "Synthetic step",
        "reason": "Smoke test",
        "text_points": ["smoke"],
        "state_after": state_after,
        "transition_hints": [],
    }


def _build_synthetic_lesson(base_type: str, mode: str) -> dict[str, Any]:
    """Build a minimal lesson_v2_raw with one background card + one worked
    example for the given base_type. The orchestrator + compiler chain runs
    on this without any LLM call."""
    base_state = _SYNTHETIC_BASE_STATES[base_type]
    visual_intent = {
        "base_type": base_type,
        "mode": mode,
        "description": f"Synthetic {base_type} for smoke verification.",
        "purpose": "Verify the compile path produces a valid model.",
        "static_or_dynamic": "dynamic",
    }
    plan_id = f"plan_{base_type}"
    return {
        "title": f"E2E smoke: {base_type}",
        "topic_summary": "Synthetic smoke run.",
        "estimated_minutes": 5,
        "cards": [
            {
                "id": "card_bg",
                "role": "background",
                "title": "Background",
                "learning_job": "Show the structure at rest.",
                "points": ["bullet 1"],
                "visual_intent": {**visual_intent, "static_or_dynamic": "static"},
                "worked_example_plan_id": plan_id,
                "practice_question_index": None,
                "estimated_seconds": 60,
            },
            {
                "id": "card_we",
                "role": "worked_example",
                "title": "Worked example",
                "learning_job": "Trace through.",
                "points": ["bullet 1"],
                "visual_intent": visual_intent,
                "worked_example_plan_id": plan_id,
                "practice_question_index": None,
                "estimated_seconds": 120,
            },
        ],
        "worked_example_plans": [
            {
                "id": plan_id,
                "visual_intent": visual_intent,
                "problem_setup": "Synthetic setup.",
                "terminal_state": "Synthetic terminal.",
                "base_state": base_state,
                "steps": [_synthetic_step(base_state)],
            }
        ],
        "practice_questions": [],
    }


def run_synthetic_smoke() -> tuple[int, int, list[str]]:
    """Run synthetic smoke for every base_type. Returns (pass, total, errors)."""
    passed = 0
    total = 0
    errors: list[str] = []
    for base_type in BASE_VISUAL_TYPES:
        total += 1
        modes = MODES_BY_BASE_TYPE.get(base_type, ())
        mode = modes[0] if modes else "default"
        raw = _build_synthetic_lesson(base_type, mode)
        try:
            lesson = compile_lesson_v2(
                lesson_v2_raw=raw,
                topic_id=f"smoke_{base_type}",
                topic_hint=base_type,
                topic_type="algorithm_walkthrough",
                visual_domain="generic",
                source_chunks_excerpt="",
                source_chunk_ids=[],
                source_summary="",
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{base_type}: compile threw {type(exc).__name__}: {exc}")
            continue

        # Basic shape checks
        if not lesson.get("visual_models"):
            errors.append(f"{base_type}: no visual_models")
            continue
        if not lesson.get("render_steps"):
            errors.append(f"{base_type}: no render_steps")
            continue
        if not any(m.get("frames") for m in lesson["visual_models"]):
            errors.append(f"{base_type}: every model has zero frames")
            continue

        # Validator must not reject the lesson
        report = validate_lesson_v2(lesson)
        err_codes = [i.code for i in report.errors()]
        if err_codes:
            errors.append(f"{base_type}: validator errors {err_codes}")
            continue

        passed += 1
    return passed, total, errors


def run_live_smoke(topic_id: str) -> dict[str, Any]:
    """Make a real LLM call via the lessons_v2 endpoint and return the
    compiled lesson + validator report. Requires a configured DB +
    OpenAI client + valid topic_id. Caller is responsible for env setup.
    """
    from app.db.database import SessionLocal
    from app.models.topic import Topic
    from app.prompts.lean_lesson_prompt_v2 import (
        SYSTEM_PROMPT_V2,
        build_lesson_v2_prompt,
    )
    from app.services.llm_client import client
    from app.services.llm_schemas_v2 import LESSON_V2_SCHEMA
    from app.services.topic_classifier_v2 import classify_topic_v2

    db = SessionLocal()
    try:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if topic is None:
            return {"error": f"topic {topic_id} not found"}
        classification = classify_topic_v2(
            topic_title=topic.title or "",
            topic_summary=getattr(topic, "description", "") or "",
            topic_type=str(getattr(topic, "topic_type", None) or "concept_intuition"),
            knowledge_level=None,
        )
        user_prompt = build_lesson_v2_prompt(
            topic_title=topic.title or "",
            topic_summary=getattr(topic, "description", "") or "",
            topic_type=classification["topic_type"],
            visual_domain=classification["visual_domain"],
            visual_mode_hint=classification["visual_mode_hint"],
            knowledge_level=None,
            chunks_text="",
        )
        response = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "system", "content": SYSTEM_PROMPT_V2},
                {"role": "user", "content": user_prompt},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "lesson_v2",
                    "strict": True,
                    "schema": LESSON_V2_SCHEMA,
                },
            },
        )
        raw = json.loads(response.output_text)
        lesson = compile_lesson_v2(
            lesson_v2_raw=raw,
            topic_id=str(topic.id),
            topic_hint=topic.title or "",
            topic_type=classification["topic_type"],
            visual_domain=classification["visual_domain"],
            source_chunks_excerpt="",
            source_chunk_ids=[],
            source_summary="",
        )
        report = validate_lesson_v2(lesson)
        return {
            "classification": classification,
            "visual_models_count": len(lesson["visual_models"]),
            "render_steps_count": len(lesson["render_steps"]),
            "validator_errors": [i.code for i in report.errors()],
            "validator_warnings": [i.code for i in report.warnings()],
        }
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", type=str, default="", help="topic_id for live LLM smoke")
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    args = parser.parse_args()

    if args.topic:
        result = run_live_smoke(args.topic)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for key, value in result.items():
                print(f"{key}: {value}")
        return 0 if not result.get("error") and not result.get("validator_errors") else 1

    passed, total, errors = run_synthetic_smoke()
    print(f"Synthetic smoke: {passed}/{total} base_types passed")
    for line in errors:
        print(f"  FAIL: {line}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
