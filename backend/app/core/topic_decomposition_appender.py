"""Coding follow-up graph mutation (TOPIC_DECOMPOSITION_SPEC.md A.7 / B.5 step 5).

For every algorithm_walkthrough / data_structure_operation topic, guarantee a following
coding_implementation topic that is linked to it by an `implementation_follow_up` edge — and,
critically, add the matching implementation CAPABILITY to the path-plan graph (basis=required_by_policy,
prerequisite=the walkthrough capability) so coverage/reachability stay consistent. Pure, no LLM.

Runs BEFORE overlap validation (spec B.5) so the validator sees the final sibling set.
"""
from __future__ import annotations

from typing import Any

from app.core.topic_decomposition import canonical_action

IMPLEMENTATION_FOLLOW_UP = "implementation_follow_up"
POLICY_REASON = "walkthrough_requires_implementation_follow_up"
CODE_ABLE_TYPES = frozenset({"algorithm_walkthrough", "data_structure_operation"})


def _is_implementation_topic(topic: dict[str, Any]) -> bool:
    return (str(topic.get("topic_type") or "") == "coding_implementation"
            or canonical_action(topic.get("primary_action")) == "implement")


def append_coding_follow_ups(
    path_plan: dict[str, Any],
    topics: list[dict[str, Any]],
    *,
    enabled: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Insert a coding follow-up topic + its implementation capability after each code-able topic that
    lacks one. Idempotent: a subject that already has an implementation topic is skipped. Returns new
    (path_plan, topics) objects; inputs are not mutated."""
    if not enabled:
        return path_plan, topics

    path_plan = {**path_plan, "required_capabilities": list(path_plan.get("required_capabilities") or [])}
    caps_by_id = {str(c.get("capability_id")): c for c in path_plan["required_capabilities"]}

    # subjects that already have an implementation topic -> don't synthesize another
    have_impl_subjects = {
        str(t.get("subject_key")) for t in topics
        if t.get("subject_key") and _is_implementation_topic(t)
    }

    result: list[dict[str, Any]] = []
    for t in topics:
        result.append(t)
        ttype = str(t.get("topic_type") or "")
        subject = str(t.get("subject_key") or "")
        if ttype not in CODE_ABLE_TYPES or not subject or subject in have_impl_subjects:
            continue
        have_impl_subjects.add(subject)

        parent_tid = str(t.get("topic_id") or subject)
        parent_cid = str(t.get("capability_id") or subject)
        impl_cid = f"{subject}_implementation"
        impl_tid = f"{parent_tid}_implementation"

        # capability added to the graph (the fix for "appended topic has a capability not in the graph")
        if impl_cid not in caps_by_id:
            cap = {
                "capability_id": impl_cid,
                "description": f"Implement {subject.replace('_', ' ')} in code.",
                "ownership_mode": "standalone",
                "owner_topic_id": None,
                "prerequisite_capability_ids": [parent_cid] if parent_cid in caps_by_id else [],
                "satisfies_end_actions": ["implement"],
                "basis": "required_by_policy",
                "policy_reason": POLICY_REASON,
            }
            caps_by_id[impl_cid] = cap
            path_plan["required_capabilities"].append(cap)

        result.append({
            "topic_id": impl_tid,
            "capability_id": impl_cid,
            "subject_key": subject,
            "primary_action": "implement",
            "content_role": "implementation",
            "topic_type": "coding_implementation",
            "topic_relationships": [{"parent_topic_id": parent_tid, "relationship": IMPLEMENTATION_FOLLOW_UP}],
            "primary_capability": f"Implement {subject.replace('_', ' ')}",
            "practice_target": f"Implement and run {subject.replace('_', ' ')} on a concrete input.",
            "practice_format": "coding",
            "practice_evidence_type": "write_code",
            "expected_output": "A working, runnable implementation.",
            "basis": "required_by_policy",
            "policy_reason": POLICY_REASON,
            "unit_title": t.get("unit_title"),
        })

    return path_plan, result
