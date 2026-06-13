"""Tier-3 — LLM-authored, validated projection (PROJECTOR_SYSTEM_SPEC §9).

When neither a registered simulator nor an inferable contract exists, the LLM supplies
the *inputs* (real code + the graph + a proposed GraphProjection) and the deterministic
core still owns the *truth*: we RUN the code (and check it produces the claimed output,
so the algorithm is real, not hallucinated), VALIDATE the projection (§6.3), then project
+ compile + validate exactly as the §7 route — stamped llm_validated_projection (T4).

The LLM *call* is flag-gated (`AZALEA_PROJECTOR_TIER3`) and injectable; this module owns
the verification, which is what makes "responsive to regeneration inputs" safe.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

_log = logging.getLogger(__name__)

_REQUIRED = ("code", "entry_function", "base_structure", "graph_projection")


def tier3_enabled() -> bool:
    return os.getenv("AZALEA_PROJECTOR_TIER3", "").strip().lower() in {"1", "true", "on", "all"}


def validate_payload(payload: dict[str, Any]) -> list[str]:
    """Shape check before we touch the code/projection."""
    errors = [f"missing {k}" for k in _REQUIRED if not payload.get(k)]
    if not (payload.get("base_structure") or {}).get("nodes"):
        errors.append("base_structure has no nodes")
    return errors


def run_tier3(payload: dict[str, Any], *, model_id: str = "tier3") -> dict[str, Any]:
    """Validate + run an LLM-authored projection payload (§9). The LLM proposes; the
    tracer and validators dispose."""
    from app.services.visual_v2.pipeline import _run_graph_projection
    from app.services.visual_v2.simulators.code_tracer import trace_execution

    def fail(stage: str, errors: list[str]) -> dict[str, Any]:
        return {"status": "failed", "stage": stage, "errors": errors, "model": None}

    shape_errors = validate_payload(payload)
    if shape_errors:
        return fail("Tier3Payload", shape_errors)

    # 1. The code must actually run — and produce the declared output when one is
    #    claimed. A hallucinated algorithm is rejected here, before any rendering.
    try:
        _steps, return_value = trace_execution(
            str(payload["code"]), str(payload["entry_function"]), dict(payload.get("input") or {})
        )
    except Exception as exc:  # noqa: BLE001
        return fail("Tier3Execution", [f"{type(exc).__name__}: {exc}"])
    claimed = payload.get("expected_output")
    if claimed is not None and return_value != claimed:
        return fail("Tier3OutputMismatch", [f"code returned {return_value!r} != claimed {claimed!r}"])

    # 2. Project + compile + validate exactly as the §7 route, marked llm_authored (T4).
    example = {
        "example_id": payload.get("example_id", "tier3"),
        "base_type": "node_link_diagram",
        "mode": "graph_projection",
        "code": payload["code"],
        "entry_function": payload["entry_function"],
        "input": dict(payload.get("input") or {}),
        "base_structure": payload["base_structure"],
        "graph_projection": payload["graph_projection"],
        "learner_goal": payload.get("learner_goal", ""),
    }
    return _run_graph_projection(example, model_id=model_id, projection_source="llm_authored")


def author_and_run(
    topic: dict[str, Any],
    *,
    model_id: str = "tier3",
    author: Optional[Callable[[dict[str, Any]], Optional[dict[str, Any]]]] = None,
) -> Optional[dict[str, Any]]:
    """Flag-gated entry point: ask `author` (the LLM, injectable for tests) for a
    payload, then verify + run it. Returns None when disabled or no payload. The LLM
    is never trusted for per-frame state — only for code/graph/contract proposals."""
    if not tier3_enabled():
        return None
    if author is None:
        return None  # no live author wired yet; tests inject one
    try:
        payload = author(topic)
    except Exception as exc:  # noqa: BLE001
        _log.warning("tier3: author failed: %s", exc)
        return None
    if not payload:
        return None
    return run_tier3(payload, model_id=model_id)
