"""Top-level V2 build orchestration (VISUAL_SYSTEM_SPEC §6).

example (LLM, boring) → deterministic pipeline → prose (LLM, from the locked
trace) → sync-validate → attach. The LLM callables are injected so the whole
orchestration is testable without a live client; on prose drift we fall back to
the deterministic prose, which is in-sync by construction.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from .metrics import GLOBAL as METRICS
from .pipeline import run_for_registered
from .prose import deterministic_prose, validate_text_sync
from .schemas import CanonicalExample

ExampleGenerator = Callable[..., CanonicalExample]
ProseGenerator = Callable[..., list[dict[str, Any]]]


def build_v2_visual(
    *,
    topic: dict[str, Any],
    mode: str,
    algorithm: str,
    generate_example: ExampleGenerator,
    generate_prose: Optional[ProseGenerator] = None,
    model_id: str = "v2_model",
) -> dict[str, Any]:
    # 1. The LLM picks a concrete example (data only — §6.3 "boring output").
    example = generate_example(topic=topic, mode=mode, algorithm=algorithm)

    # 2. Deterministic pipeline: validate → simulate → fold → compile → validate.
    result = run_for_registered(example, model_id=model_id, topic_id=str(topic.get("id", "")))
    result["example"] = example
    if result["status"] != "validated":
        METRICS.record(result)  # §7.2 — record the failure (with its stage)
        return result  # already a structured failure with a debug payload

    trace = result["trace"]
    frames = result["frames"]
    render_steps = result["render_steps"]
    valid_ids = set((example.get("base_structure") or {}).get("nodes") or [])

    # 3. Prose from the locked trace (LLM polishes; deterministic fallback otherwise).
    prose: Optional[list[dict[str, Any]]] = None
    if generate_prose is not None:
        try:
            prose = generate_prose(trace=trace, render_steps=render_steps)
        except Exception:  # noqa: BLE001 — never let prose generation kill the visual
            prose = None
    if prose is None:
        prose = deterministic_prose(trace, frames)

    # 4. Validate prose ↔ trace sync; on any drift, fall back to in-sync prose.
    sync_errors: list[str] = []
    for i, step_prose in enumerate(prose):
        if i < len(frames):
            sync_errors.extend(
                f"step {i}: {err}"
                for err in validate_text_sync(step_prose.get("text_refs") or {}, frames[i], valid_ids)
            )
    if sync_errors:
        prose = deterministic_prose(trace, frames)
        result["prose_repaired"] = True
        result["sync_errors"] = sync_errors

    # 5. Attach prose to the render steps.
    for render_step, step_prose in zip(render_steps, prose):
        render_step["points"] = step_prose.get("points") or []
        render_step["text_refs"] = step_prose.get("text_refs") or {}
    result["prose"] = prose
    METRICS.record(result)  # §7.2 — record success (+ whether prose was repaired)
    return result
