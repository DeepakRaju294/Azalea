"""Deterministic topic-decomposition validator (TOPIC_DECOMPOSITION_SPEC.md Part B.4–B.6).

Pure over `(path_plan, topics)`: validates coverage/reachability, ownership, dependency ordering,
role↔type, and duplicates; applies SAFE_REPAIRs and CLEAR_DUPLICATE drops deterministically; routes
genuine AMBIGUOUS_OVERLAP to an injected resolver (default: flag + keep the safer path). No LLM, no I/O.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.core.topic_decomposition import (
    is_coding_type,
    match_action,
    role_matches_type,
)

IMPLEMENTATION_FOLLOW_UP = "implementation_follow_up"

# Outcomes
CLEAR_DUPLICATE = "CLEAR_DUPLICATE"
SAFE_REPAIR = "SAFE_REPAIR"
AMBIGUOUS_OVERLAP = "AMBIGUOUS_OVERLAP"


@dataclass
class ValidatorAction:
    rule: str
    outcome: str          # CLEAR_DUPLICATE | SAFE_REPAIR | AMBIGUOUS_OVERLAP | FLAG | REPAIR
    detail: str
    topic_ids: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    path_plan: dict[str, Any]
    topics: list[dict[str, Any]]
    actions: list[ValidatorAction] = field(default_factory=list)
    ok: bool = True       # final coverage/reachability passed with no `unowned`


# Optional injected resolver for AMBIGUOUS_OVERLAP: (topic_a, topic_b) -> action dict or None.
OverlapResolver = Callable[[dict[str, Any], dict[str, Any]], Optional[dict[str, Any]]]


def _norm_output(text: Any) -> str:
    """Normalize an expected_output for equivalence: lowercase, collapse non-alphanumerics."""
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _equivalent_output(a: Any, b: Any) -> bool:
    na, nb = _norm_output(a), _norm_output(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = set(na.split()), set(nb.split())
    return bool(ta) and bool(tb) and len(ta & tb) / max(len(ta), len(tb)) >= 0.8


def _capabilities(path_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(c.get("capability_id")): c
            for c in (path_plan.get("required_capabilities") or [])
            if isinstance(c, dict) and c.get("capability_id")}


def _parents(topic: dict[str, Any]) -> list[tuple[str, str]]:
    """(parent_topic_id, relationship) edges from topic_relationships (+ legacy singular fields)."""
    edges = []
    for e in topic.get("topic_relationships") or []:
        if isinstance(e, dict) and e.get("parent_topic_id"):
            edges.append((str(e["parent_topic_id"]), str(e.get("relationship") or "")))
    return edges


def _is_follow_up(topic: dict[str, Any]) -> bool:
    return any(rel == IMPLEMENTATION_FOLLOW_UP for _, rel in _parents(topic))


# --------------------------------------------------------------------------------------------------
# Ordering — order_index from capability prerequisites (B.4.4: capability prereqs are canonical).
# --------------------------------------------------------------------------------------------------
def _topological_capability_order(caps: dict[str, dict[str, Any]]) -> Optional[list[str]]:
    """Kahn's algorithm over prerequisite_capability_ids. Returns ordered ids, or None on a cycle."""
    indeg = {cid: 0 for cid in caps}
    adj: dict[str, list[str]] = {cid: [] for cid in caps}
    for cid, cap in caps.items():
        for pre in cap.get("prerequisite_capability_ids") or []:
            if pre in caps:
                adj[pre].append(cid)
                indeg[cid] += 1
    queue = sorted([cid for cid, d in indeg.items() if d == 0])
    order: list[str] = []
    while queue:
        cid = queue.pop(0)
        order.append(cid)
        for nxt in sorted(adj[cid]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    return order if len(order) == len(caps) else None


def _assign_order_index(topics: list[dict[str, Any]], caps: dict[str, dict[str, Any]],
                        actions: list[ValidatorAction]) -> None:
    """Set each topic's order_index from the capability topological order (B.4.4)."""
    cap_order = _topological_capability_order(caps)
    if cap_order is None:
        actions.append(ValidatorAction("dependency_dag", "FLAG",
                                       "prerequisite cycle in capability graph"))
        return
    rank = {cid: i for i, cid in enumerate(cap_order)}
    # topics ordered by their capability's rank (embedded-owned capabilities don't have a topic)
    ordered = sorted(topics, key=lambda t: rank.get(str(t.get("capability_id")), 10**6))
    for i, t in enumerate(ordered, start=1):
        t["order_index"] = i


# --------------------------------------------------------------------------------------------------
# Practice-capability (B.4.1)
# --------------------------------------------------------------------------------------------------
def _is_practice_capable(topic: dict[str, Any]) -> bool:
    return (
        bool(str(topic.get("practice_target") or "").strip())
        and bool(str(topic.get("practice_format") or "").strip())
        and bool(str(topic.get("practice_evidence_type") or "").strip())
        and bool(str(topic.get("expected_output") or "").strip())
    )


# --------------------------------------------------------------------------------------------------
# Duplicate detection (B.4.2 + the tightened CLEAR_DUPLICATE / sole-owner guard)
# --------------------------------------------------------------------------------------------------
def _is_parent_child(a: dict[str, Any], b: dict[str, Any]) -> bool:
    ids = {str(a.get("topic_id")), str(b.get("topic_id"))}
    for t in (a, b):
        for pid, _ in _parents(t):
            if pid in ids:
                return True
    return False


def _duplicate_outcome(a: dict[str, Any], b: dict[str, Any]) -> Optional[str]:
    if str(a.get("subject_key")) != str(b.get("subject_key")) or not a.get("subject_key"):
        return None
    if match_action(a.get("primary_action"), b.get("primary_action")) == "none":
        return None  # different learner action on the same subject -> keep (trace vs implement)
    if _is_parent_child(a, b):
        return None  # allowed complementary pair
    same_evidence = (a.get("practice_evidence_type") == b.get("practice_evidence_type")
                     and a.get("practice_evidence_type"))
    same_role = a.get("content_role") == b.get("content_role")
    if same_role and same_evidence and _equivalent_output(a.get("expected_output"), b.get("expected_output")):
        return CLEAR_DUPLICATE
    return AMBIGUOUS_OVERLAP


def _sole_owner_of_required(topic: dict[str, Any], topics: list[dict[str, Any]],
                            caps: dict[str, dict[str, Any]]) -> bool:
    """True if `topic` is the only standalone owner of a REQUIRED capability (B.4 sole-owner guard)."""
    cid = str(topic.get("capability_id"))
    if cid not in caps:
        return False
    others = [t for t in topics if t is not topic and str(t.get("capability_id")) == cid]
    return not others


# --------------------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------------------
def validate_topic_decomposition(
    path_plan: dict[str, Any],
    topics: list[dict[str, Any]],
    goal: str = "",
    *,
    resolve_overlap: Optional[OverlapResolver] = None,
) -> ValidationResult:
    topics = [dict(t) for t in topics]  # don't mutate caller's objects
    caps = _capabilities(path_plan)
    actions: list[ValidatorAction] = []

    # B.4.3 SAFE_REPAIR — a coding follow-up that inherited the parent's non-coding practice.
    for t in topics:
        if is_coding_type(t.get("topic_type")) and _is_follow_up(t):
            if str(t.get("practice_format") or "").lower() not in ("coding", ""):
                t["practice_format"] = "coding"
                t["practice_evidence_type"] = "write_code"
                actions.append(ValidatorAction("pair_distinctness", SAFE_REPAIR,
                                               "coding follow-up practice forced to coding",
                                               [str(t.get("topic_id"))]))

    # B.4.5 role↔type consistency.
    for t in topics:
        role, tt = t.get("content_role"), t.get("topic_type")
        if role and tt and not role_matches_type(str(role), str(tt)):
            actions.append(ValidatorAction("role_type", "FLAG",
                                           f"role {role!r} != type {tt!r}", [str(t.get("topic_id"))]))

    # B.4.2 duplicates — drop CLEAR_DUPLICATE (later, unless sole owner), route AMBIGUOUS.
    survivors: list[dict[str, Any]] = []
    for t in topics:
        dropped = False
        for kept in survivors:
            outcome = _duplicate_outcome(kept, t)
            if outcome == CLEAR_DUPLICATE:
                if _sole_owner_of_required(t, topics, caps):
                    outcome = AMBIGUOUS_OVERLAP  # sole-owner guard
                else:
                    actions.append(ValidatorAction("duplicate", CLEAR_DUPLICATE,
                                                   "same subject/action/evidence/output",
                                                   [str(kept.get("topic_id")), str(t.get("topic_id"))]))
                    dropped = True
                    break
            if outcome == AMBIGUOUS_OVERLAP:
                decision = resolve_overlap(kept, t) if resolve_overlap else None
                if decision and decision.get("decision") == "drop_topic":
                    surviving = str(decision.get("surviving_topic_id") or "")
                    pair = [str(kept.get("topic_id")), str(t.get("topic_id"))]
                    actions.append(ValidatorAction("duplicate", AMBIGUOUS_OVERLAP, "resolved: drop_topic", pair))
                    if surviving == str(t.get("topic_id")):  # keep t, drop kept
                        survivors.remove(kept)
                        break
                    dropped = True  # keep kept, drop t
                    break
                actions.append(ValidatorAction("duplicate", AMBIGUOUS_OVERLAP,
                                               "flagged for review (kept both)",
                                               [str(kept.get("topic_id")), str(t.get("topic_id"))]))
        if not dropped:
            survivors.append(t)
    topics = survivors

    # B.4.4 ordering from capability prerequisites.
    _assign_order_index(topics, caps, actions)

    # B.4.1 coverage & reachability (mechanical) — final gate.
    ok = True
    owned_standalone = {str(t.get("capability_id")) for t in topics}
    for cid, cap in caps.items():
        mode = str(cap.get("ownership_mode") or "")
        if mode == "standalone" and cid not in owned_standalone:
            actions.append(ValidatorAction("coverage", "FLAG", f"unowned required capability {cid}", []))
            ok = False
        elif mode == "embedded" and not cap.get("owner_topic_id"):
            actions.append(ValidatorAction("coverage", "FLAG", f"embedded capability {cid} has no owner", []))
            ok = False
        elif mode == "unowned":
            actions.append(ValidatorAction("coverage", "FLAG", f"`unowned` forbidden at persist: {cid}", []))
            ok = False
    for t in topics:
        if not str(t.get("basis") or "").strip():
            actions.append(ValidatorAction("coverage", "FLAG", "orphan topic (no basis)", [str(t.get("topic_id"))]))
    # end-capability reachability via satisfies_end_actions + practice-capable owners
    practice_capable_caps = {str(t.get("capability_id")) for t in topics if _is_practice_capable(t)}
    for act in path_plan.get("end_capability_actions") or []:
        satisfied = any(
            act in (cap.get("satisfies_end_actions") or []) and cid in practice_capable_caps
            for cid, cap in caps.items())
        if not satisfied:
            actions.append(ValidatorAction("reachability", "FLAG",
                                           f"end action {act!r} not satisfied by a practice-capable topic", []))
            ok = False

    return ValidationResult(path_plan=path_plan, topics=topics, actions=actions, ok=ok)
