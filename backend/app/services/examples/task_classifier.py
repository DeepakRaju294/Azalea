"""Task-kind classifier (WORKED_EXAMPLE_ACCURACY_SPEC §3.5) — the routing keystone.

Emits a `WorkedExampleTask` for a topic's worked-example slot. Booleans-from-evidence are PRIMARY;
`task_kind` is descriptive. Layered, highest-confidence source wins: L1 explicit metadata, L2 deterministic
rules (course_type + adapter availability), L4 conservative fallback. The L3 LLM layer is deferred until the
gold-set safety bar is met (Phase A3) — until then this is fully deterministic and offline.

Asymmetric safety: false-illustrative (a real computation shipped unverified) is dangerous; false-
computational (conceptual → withhold/guided) is safe — so ambiguity biases toward the ladder, "don't know"
biases to guided-explanation, never silently illustrative.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# course_type values that are inherently computational (a worked example is a determinate run)
COMPUTATIONAL_COURSE_TYPES = {
    "coding_implementation", "truncated_coding_implementation", "algorithm_walkthrough",
}
# course_type values that are inherently conceptual (no determinate worked computation)
CONCEPTUAL_COURSE_TYPES = {"study_path_introduction", "conceptual_overview", "topic_overview"}


@dataclass
class WorkedExampleTask:
    task_kind: str                                  # deterministic_execution | closed_form_computation | …
    can_construct_valid_instance: bool              # pre-Stage-0: could a valid bounded instance be produced?
    instance_is_fixed: bool                         # post-Stage-0: this example already has a concrete input
    has_executable_terminal_condition: bool         # execution halts → Tier-1 eligibility
    has_independently_checkable_endpoint: bool      # conclusion checkable w/o execution → Tier-2 eligibility
    has_unique_or_equivalent_answer: bool
    requested_learning_goal: str = ""
    classification_status: str = "resolved"         # resolved | ambiguous | unsupported
    task_contract_confidence: float = 0.0
    classification_source: str = "fallback_heuristic"
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def is_determinate(self) -> bool:
        """A determinate computation the ladder can attempt to verify (Tier 1/2)."""
        return self.has_executable_terminal_condition and self.has_unique_or_equivalent_answer


def _course_type(topic: dict[str, Any]) -> str:
    return str(topic.get("topic_type") or topic.get("course_type") or "").lower()


def classify_worked_example_task(topic: dict[str, Any]) -> WorkedExampleTask:
    ct = _course_type(topic)
    goal = str(topic.get("learning_goal") or topic.get("concept") or topic.get("title") or "")
    try:
        from .trace_pipeline import route_adapter
        adapter = route_adapter(topic)
    except Exception:  # noqa: BLE001 — classification must never raise into generation
        adapter = None

    # L1/L2 — a registered, applicable adapter ⇒ determinate execution, high confidence.
    if adapter is not None:
        return WorkedExampleTask(
            task_kind="deterministic_execution", can_construct_valid_instance=True, instance_is_fixed=False,
            has_executable_terminal_condition=True, has_independently_checkable_endpoint=True,
            has_unique_or_equivalent_answer=True, requested_learning_goal=goal,
            classification_status="resolved", task_contract_confidence=0.95,
            classification_source="deterministic_rule",
            evidence={"adapter": getattr(adapter, "slug", "?"), "course_type": ct})

    # L2 — computational course type but NO adapter ⇒ determinate-intent, unsupported by an adapter.
    # Ambiguous (we know it's a computation, but can't construct/verify it here) → the ladder owns it
    # (Tier 2 / guided), never illustrative.
    if ct in COMPUTATIONAL_COURSE_TYPES:
        return WorkedExampleTask(
            task_kind="deterministic_execution", can_construct_valid_instance=False, instance_is_fixed=False,
            has_executable_terminal_condition=True, has_independently_checkable_endpoint=False,
            has_unique_or_equivalent_answer=True, requested_learning_goal=goal,
            classification_status="ambiguous", task_contract_confidence=0.55,
            classification_source="deterministic_rule", evidence={"course_type": ct, "adapter": None})

    # L2 — explicitly conceptual course type ⇒ illustrative.
    if ct in CONCEPTUAL_COURSE_TYPES:
        return WorkedExampleTask(
            task_kind="conceptual_illustration", can_construct_valid_instance=False, instance_is_fixed=False,
            has_executable_terminal_condition=False, has_independently_checkable_endpoint=False,
            has_unique_or_equivalent_answer=False, requested_learning_goal=goal,
            classification_status="resolved", task_contract_confidence=0.80,
            classification_source="deterministic_rule", evidence={"course_type": ct})

    # L4 — unknown: we cannot tell whether a valid worked computation even exists ⇒ UNSUPPORTED ⇒ guided
    # (NOT illustrative — defaulting "don't know" to illustrative is what would ship an invented trace).
    return WorkedExampleTask(
        task_kind="conceptual_illustration", can_construct_valid_instance=False, instance_is_fixed=False,
        has_executable_terminal_condition=False, has_independently_checkable_endpoint=False,
        has_unique_or_equivalent_answer=False, requested_learning_goal=goal,
        classification_status="unsupported", task_contract_confidence=0.30,
        classification_source="fallback_heuristic", evidence={"course_type": ct or "unknown"})
