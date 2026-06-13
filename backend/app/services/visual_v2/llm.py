"""LLM adapters for the V2 pipeline (VISUAL_SYSTEM_SPEC §3.4, §6.3, §5.5).

Two narrow, "boring" calls:
  1. example selection — data only (structure + input + why + goal), NO render data
  2. prose from the locked trace — read-only; emits `text_refs` for sync validation

These are RUNTIME-ONLY (they import the OpenAI client lazily, so importing this
module does not pull in `openai`). Tests inject stubs via build.build_v2_visual
and never reach the lazy import.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from .schemas import CanonicalExample, Trace

# --- prompt builders (pure; safe to unit-test) -----------------------------

EXAMPLE_SYSTEM = (
    "You select a concrete EXAMPLE for an educational visual. Return DATA ONLY as "
    "strict JSON — never colours, coordinates, layout, or step sequences. The "
    "backend computes the trace and renders it."
)


def build_example_prompt(topic: dict[str, Any], mode: str, algorithm: str) -> tuple[str, str]:
    title = topic.get("title", "")
    if mode == "graph_network":
        shape = (
            "5-8 single-letter nodes (A, B, C, ...), several edges with at least one "
            "branch, and a start node."
        )
        schema_hint = '{ "nodes": ["A",...], "edges": [["A","B"],...], "start": "A", '
    else:
        shape = "a small, non-trivial example appropriate to the mode."
        schema_hint = '{ "nodes": [...], "edges": [...], "start": null, '
    user = (
        f"Topic: {title}\nMode: {mode}   Algorithm: {algorithm}\n"
        f"Pick ONE small, non-trivial example: {shape}\n"
        f"Return JSON: {schema_hint}"
        '"why_this_example": "...", "learner_goal": "..." }\n'
        "Data only — no coordinates, colours, or steps."
    )
    return EXAMPLE_SYSTEM, user


PROSE_SYSTEM = (
    "You write the learner-facing bullets for each step of a locked algorithm "
    "trace. You receive the trace READ-ONLY. You may explain, compress, or "
    "rephrase. You may NOT introduce a new state fact (node, value, step). For "
    "each step emit `text_refs` naming exactly the elements/values you reference."
)


def build_prose_prompt(trace: Trace) -> tuple[str, str]:
    compact = {
        "initial_state": trace.get("initial_state"),
        "steps": [
            {"step_index": s.get("step_index"), "delta": s.get("delta"), "notice": s.get("learner_should_notice")}
            for s in (trace.get("steps") or [])
        ],
    }
    user = (
        "Locked trace (read-only):\n"
        + json.dumps(compact, indent=2)
        + "\n\nReturn JSON: { \"steps\": [ { \"step_index\": int, \"points\": [str], "
        '"text_refs": { "mentioned_elements": [ids], "mentioned_values": {"output": [...], '
        '"frontier": [...], "active": id}, "code_line_refs": [] } } ] }'
    )
    return PROSE_SYSTEM, user


# --- default runtime generators (lazy LLM import) --------------------------


def _structured_json(system: str, user: str) -> dict[str, Any]:
    # Lazy import so this module stays import-clean for unit tests.
    from app.services.llm_client import client, OPENAI_MODEL  # type: ignore

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        text={"format": {"type": "json_object"}},
    )
    return json.loads(response.output_text)


def default_example_generator(*, topic: dict[str, Any], mode: str, algorithm: str) -> CanonicalExample:
    system, user = build_example_prompt(topic, mode, algorithm)
    raw = _structured_json(system, user)
    return CanonicalExample(
        example_id=f"{mode}:{algorithm}:{uuid.uuid4().hex[:8]}",
        domain_object="graph" if mode == "graph_network" else mode,
        base_type="node_link_diagram",
        mode=mode,
        algorithm=algorithm,
        input={"start": raw.get("start")},
        base_structure={"nodes": raw.get("nodes") or [], "edges": raw.get("edges") or []},
        why_this_example=str(raw.get("why_this_example", "")),
        learner_goal=str(raw.get("learner_goal", "")),
    )


def default_prose_generator(*, trace: Trace, render_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    system, user = build_prose_prompt(trace)
    raw = _structured_json(system, user)
    return list(raw.get("steps") or [])
