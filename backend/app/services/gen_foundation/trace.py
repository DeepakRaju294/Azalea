"""Authoritative trace vs. teaching projection + caps + confidence (spec §5, §5.2, §6).

The complete ``trace_events`` is uncapped; the learner-facing ``teaching_steps``
projection is hard-capped (§5.2). This module owns the projection caps, the
per-card trace-event budget (§5), the trace modes (§6.1), and the first-class
trace-confidence metadata (§6.3). Types + constants + small pure helpers only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, TypedDict

TraceMode = Literal["post_generation_trace", "preexisting_trace", "canonical", "model_only"]
TraceConfidence = Literal["high", "medium", "low"]
TraceValidationStatus = Literal["passed", "partial", "unavailable"]
ReconciliationStatus = Literal["matched", "partial", "mismatched"]

# Example categories that drive the projection caps (§5.2).
ExampleCategory = Literal[
    "simple_concept", "algorithm_walkthrough", "coding_implementation", "complex_recursive_dp"
]


class TraceRange(TypedDict):
    start: int
    end: int


class ConfidenceMeta(TypedDict, total=False):
    """Per-example trace metadata (§6.3) — gates audit + visual provisioning."""

    trace_mode: TraceMode
    trace_confidence: TraceConfidence
    trace_validation_status: TraceValidationStatus


# --- projection caps (§5.2): (min cards, max cards) per category ----------------
# Default = the original TIGHT caps (concise examples — the format we want back). With ground-truth-first
# (trace-first / executed-reference), examples are naturally bounded, so the cap rarely binds and we no
# longer need to raise it to avoid fallbacks. The raised caps remain available via
# AZALEA_GEN_FOUNDATION_RAISED_CAPS=1 for the rare genuinely-long trace, but they are OFF by default.
import os as _os

if _os.getenv("AZALEA_GEN_FOUNDATION_RAISED_CAPS", "0").strip().lower() in {"1", "true", "on", "yes"}:
    PROJECTION_CAPS: dict[str, tuple[int, int]] = {
        "simple_concept": (4, 14),
        "algorithm_walkthrough": (6, 30),
        "coding_implementation": (7, 30),
        "complex_recursive_dp": (8, 30),
    }
    ABSOLUTE_CEILING = 50      # sanity ceiling only (§5.2) — effectively removes the production cap
else:  # original tight caps — restored when the raised-caps flag is off (pre-new-system behavior)
    PROJECTION_CAPS = {
        "simple_concept": (4, 7),
        "algorithm_walkthrough": (6, 10),
        "coding_implementation": (7, 12),
        "complex_recursive_dp": (8, 14),
    }
    ABSOLUTE_CEILING = 16
MAX_WORK_LINES_PER_CARD = 6    # max ~6 work lines per card (§5.2)

# Per-card trace-event budget (§5): default span, and the larger span a backend-approved
# `compressed` flag may allow.
TRACE_EVENT_BUDGET_DEFAULT = 12
TRACE_EVENT_BUDGET_COMPRESSED = 20


@dataclass(frozen=True)
class CapResult:
    ok: bool
    low: int
    high: int
    count: int
    reason: str = ""


def caps_for_category(category: str) -> tuple[int, int]:
    if category not in PROJECTION_CAPS:
        raise ValueError(f"unknown example category {category!r}")
    return PROJECTION_CAPS[category]


def check_card_count(category: str, count: int) -> CapResult:
    """Card count must sit within [min, max] for the category, never above the ceiling (§5.2)."""
    low, high = caps_for_category(category)
    if count < low:
        return CapResult(False, low, high, count, f"{count} cards < minimum {low}")
    if count > min(high, ABSOLUTE_CEILING):
        return CapResult(
            False, low, high, count,
            f"{count} cards > cap {min(high, ABSOLUTE_CEILING)}; split the topic (§7.2)",
        )
    return CapResult(True, low, high, count)


def trace_event_budget(compressed: bool) -> int:
    return TRACE_EVENT_BUDGET_COMPRESSED if compressed else TRACE_EVENT_BUDGET_DEFAULT


def range_len(tr: TraceRange) -> int:
    return tr["end"] - tr["start"] + 1


class ProjectionCoverage(TypedDict, total=False):
    """Backend-derived trace<->teaching link (§9.1)."""

    required_cases: dict[str, list[str]]       # case -> [step_id, ...]
    final_trace_event: str
    teaching_step_reaching_final: str


def classify_reconciliation(
    *,
    final_answer_matches: bool,
    execution_succeeded: bool,
    unaligned_cards: int,
    coverage_holds: bool,
    invalid_code_refs_percent: float,
) -> Literal["minor", "major"]:
    """Deterministic minor/major threshold (§6.1).

    ``major`` if any: final answer differs, execution failed, >2 cards unaligned,
    coverage fails, or >25% of code_refs invalid. Otherwise ``minor``.
    """
    if (
        not final_answer_matches
        or not execution_succeeded
        or unaligned_cards > 2
        or not coverage_holds
        or invalid_code_refs_percent > 25.0
    ):
        return "major"
    return "minor"


def trace_field_owner(mode: TraceMode) -> Literal["model", "reconciler", "deterministic", "none"]:
    """Who produces ``trace_range``/``included_event_ids`` for a step, by mode (§5/§6.1)."""
    if mode == "preexisting_trace":
        return "model"
    if mode == "post_generation_trace":
        return "reconciler"
    if mode == "canonical":
        return "deterministic"
    return "none"  # model_only
