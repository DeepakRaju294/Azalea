"""Operability — lifecycle status + reproducible debug payload (VISUAL_SYSTEM_SPEC §7).

Generation lifecycle only; interaction/usage events are separate.
"""
from __future__ import annotations

from typing import Any

# §7.0 — generation lifecycle (usage events live elsewhere).
VISUAL_STATUSES = (
    "planned",
    "traced",
    "compiled",
    "validated",
    "rendered",
    "fallback_used",
    "failed",
)


def debug_payload(
    *,
    example: dict[str, Any],
    trace: dict[str, Any] | None = None,
    visual_status: str,
    failed_validator: str = "",
    topic_id: str = "",
    lesson_id: str = "",
    card_id: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A payload that drops straight into a regression test (§7.1)."""
    payload: dict[str, Any] = {
        "topic_id": topic_id,
        "lesson_id": lesson_id,
        "card_id": card_id,
        "example_id": example.get("example_id", ""),
        "trace_id": (trace or {}).get("trace_id", ""),
        "trace_source": (trace or {}).get("trace_source", ""),
        "base_type": example.get("base_type", ""),
        "mode": example.get("mode", ""),
        "algorithm": example.get("algorithm", ""),
        "visual_status": visual_status,
        "failed_validator": failed_validator,
    }
    if extra:
        payload.update(extra)
    return payload
