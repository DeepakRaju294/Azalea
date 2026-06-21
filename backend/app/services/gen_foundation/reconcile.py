"""post_generation_trace reconciler (spec §4.2, §5, §6.1).

In the default ``post_generation_trace`` mode the model emits **teaching anchors**, the
executor runs AFTER and produces ``trace_events``, and the reconciler:

* validates the model's anchors / state effects / code_refs / final answer / coverage
  against the real trace (deterministic, structural),
* attaches ``trace_range`` (+ optional ``included_event_ids``) to each card,
* classifies the disagreement minor/major and emits reconciliation telemetry.

The reconciler does NOT judge free-text ``work`` narration — that is the audit's job
(§6.1/§6.2). Pure given a trace; when no trace exists it reports ``unavailable``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .executor import TraceEvents
from .trace import TraceRange, classify_reconciliation


@dataclass
class ReconResult:
    reconciliation_status: str            # matched | partial | mismatched
    mismatch_severity: str                # minor | major
    unaligned_cards: int
    invalid_code_refs_percent: float
    coverage_after_execution: str         # passed | failed | unavailable
    attached_ranges: dict[str, TraceRange] = field(default_factory=dict)  # step_id -> range
    final_answer_matches: bool = True
    execution_succeeded: bool = True

    def telemetry(self) -> dict[str, Any]:
        return {
            "reconciliation_status": self.reconciliation_status,
            "unaligned_cards": self.unaligned_cards,
            "invalid_code_refs_percent": round(self.invalid_code_refs_percent, 1),
            "coverage_after_execution": self.coverage_after_execution,
            "mismatch_severity": self.mismatch_severity,
        }


def _event_lines(events: TraceEvents) -> set[int]:
    lines: set[int] = set()
    for ev in events:
        for ln in ev.get("code_line_refs") or ev.get("code_refs") or []:
            if isinstance(ln, int):
                lines.add(ln)
    return lines


def reconcile(
    cards: list[dict[str, Any]],
    trace_events: Optional[TraceEvents],
    *,
    model_final_answer: Any = None,
    executor_final_answer: Any = None,
    step_ids: Optional[list[str]] = None,
) -> ReconResult:
    """Reconcile model anchors against the executor trace (§6.1).

    With no trace (executor unavailable) the result is ``unavailable`` and nothing is
    attached — the example stays ``model_only`` and visuals are withheld (§6.3/§10.1).
    """
    if not trace_events:
        return ReconResult(
            reconciliation_status="partial",
            mismatch_severity="minor",
            unaligned_cards=0,
            invalid_code_refs_percent=0.0,
            coverage_after_execution="unavailable",
            execution_succeeded=False,
        )

    ids = step_ids or [f"step_{i+1}" for i in range(len(cards))]
    n = len(trace_events)
    valid_lines = _event_lines(trace_events)

    # code-ref validity: fraction of cited lines that never appear in the real trace.
    cited = 0
    invalid = 0
    for card in cards:
        for ln in card.get("code_refs") or []:
            cited += 1
            if valid_lines and ln not in valid_lines:
                invalid += 1
    invalid_pct = (100.0 * invalid / cited) if cited else 0.0

    # naive deterministic alignment: distribute events evenly across cards as ranges, and
    # count a card "unaligned" when it cites code lines that don't exist in the trace.
    attached: dict[str, TraceRange] = {}
    unaligned = 0
    per = max(1, n // max(1, len(cards)))
    cursor = 0
    for idx, card in enumerate(cards):
        start = cursor
        end = min(n - 1, start + per - 1) if idx < len(cards) - 1 else n - 1
        attached[ids[idx]] = {"start": start, "end": end}
        cursor = end + 1
        refs = card.get("code_refs") or []
        if refs and valid_lines and not (set(refs) & valid_lines):
            unaligned += 1

    final_matches = (
        executor_final_answer is None
        or model_final_answer is None
        or model_final_answer == executor_final_answer
    )
    coverage_holds = unaligned <= 2

    severity = classify_reconciliation(
        final_answer_matches=final_matches,
        execution_succeeded=True,
        unaligned_cards=unaligned,
        coverage_holds=coverage_holds,
        invalid_code_refs_percent=invalid_pct,
    )
    if final_matches and unaligned == 0 and invalid_pct == 0.0:
        status = "matched"
    elif severity == "major":
        status = "mismatched"
    else:
        status = "partial"

    return ReconResult(
        reconciliation_status=status,
        mismatch_severity=severity,
        unaligned_cards=unaligned,
        invalid_code_refs_percent=invalid_pct,
        coverage_after_execution="passed" if coverage_holds else "failed",
        attached_ranges=attached,
        final_answer_matches=final_matches,
        execution_succeeded=True,
    )
