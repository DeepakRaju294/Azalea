"""Deterministic topic-decomposition validator (TOPIC_DECOMPOSITION_SPEC.md Part B.4–B.6).

Pure over `(path_plan, topics)`: validates coverage/reachability, ownership, dependency ordering,
role↔type, and duplicates; applies SAFE_REPAIRs and CLEAR_DUPLICATE drops deterministically; routes
genuine AMBIGUOUS_OVERLAP to an injected resolver (default: flag + keep the safer path). No LLM, no I/O.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.core.decision_trace import record_topic_decision
from app.core.topic_decomposition import (
    canonical_action,
    is_coding_type,
    match_action,
    normalize_subject_key,
    resolve_topic_type,
    role_matches_type,
)

IMPLEMENTATION_FOLLOW_UP = "implementation_follow_up"

# Outcomes
CLEAR_DUPLICATE = "CLEAR_DUPLICATE"
SAFE_REPAIR = "SAFE_REPAIR"
AMBIGUOUS_OVERLAP = "AMBIGUOUS_OVERLAP"
REPAIR = "REPAIR"                    # a coverage gap repaired by synthesizing a topic (B.4.1)
SUBJECT_MERGE = "SUBJECT_MERGE"      # understand+apply of one subject folded into a single topic (B.4.2b)

# Non-coding teaching types eligible for the same-subject merge, ranked by how COMPLETE their card
# blueprint is (lower = richer arc, wins the merge). A single topic of the richest type teaches the
# concept end-to-end (intuition → worked example → practice), so an "understand X" + "apply X" pair is
# one topic, not two. Coding types (coding_implementation) and study_path_introduction are excluded:
# trace-vs-implement is a genuine split, and the intro is never a concept topic.
_MERGEABLE_TYPE_PRIORITY: dict[str, int] = {
    "math_formula_method": 0,
    "proof_reasoning": 1,
    "algorithm_walkthrough": 2,
    "data_structure_operation": 3,
    "science_mechanism": 4,
    "problem_solving_application": 5,
    "process_walkthrough": 6,
    "compare_distinguish": 7,
    "terminology_components": 8,
    "concept_intuition": 9,
}

# Trailing tokens that denote a TREATMENT of a subject, not the subject identity — stripped so
# "bayes_theorem" and "bayes_theorem_application" collapse to the same base subject for the merge.
_FACET_SUFFIX_TOKENS = frozenset({
    "application", "applications", "applied", "apply", "applying",
    "interpretation", "interpret", "interpreting",
    "calculation", "calculations", "computation", "computing", "calculate",
    "method", "methods", "usage", "use", "uses", "using",
    "problem", "problems", "example", "examples", "practice", "practicing",
})

# Leading study-verbs stripped from a merged title so "Applying Bayes' Theorem" → "Bayes' Theorem".
_LEADING_ACTION_WORDS = frozenset({
    "applying", "understanding", "using", "interpreting", "calculating",
    "computing", "solving", "exploring", "mastering", "analyzing",
})


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

    def _is_opener(t: dict[str, Any]) -> bool:
        # The orientation intro is ALWAYS first — it frames the whole path and must not float on the
        # capability graph (the LLM does not reliably make every concept depend on it).
        return (str(t.get("topic_type") or "") == "study_path_introduction"
                or str(t.get("content_role") or "").lower() == "orientation")

    # openers first, then the rest by capability topological rank (embedded-owned caps have no topic)
    ordered = sorted(topics, key=lambda t: (0 if _is_opener(t) else 1,
                                            rank.get(str(t.get("capability_id")), 10**6)))
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
def _synthesize_topic_for_capability(cid: str, cap: dict[str, Any]) -> dict[str, Any]:
    """Build a standalone topic for a REQUIRED capability the model dropped (B.4.1 coverage repair). Deterministic:
    identity + role/type/action come from the capability record, so a goal that names two techniques always yields
    two topics even if the LLM emitted one. Ordering is assigned afterward by _assign_order_index."""
    subject = normalize_subject_key(str(cap.get("subject_key") or cid))
    role = str(cap.get("content_role") or cap.get("role") or "concept_intuition")
    ttype = resolve_topic_type(role) or "concept_intuition"
    description = " ".join(str(cap.get("description") or "").split()).strip().rstrip(".")
    # Title preference: primary_capability → a readable subject → the capability description. Never fall
    # through to the raw capability_id (live: a stub topic literally titled "C1" reached the learner-facing
    # path when the capability carried neither a subject_key nor a primary_capability).
    subject_words = subject.replace("_", " ").strip()
    subject_is_opaque = not subject_words or subject_words == str(cid).strip().lower()
    title = str(cap.get("primary_capability") or "").strip()
    if not title:
        title = description[:80] if subject_is_opaque and description else subject_words
    if title:
        title = title[0].upper() + title[1:]
    topic = {
        "topic_id": f"synth_{cid}",
        "capability_id": cid,
        "title": title,
        "subject_key": subject,
        "primary_action": canonical_action(cap.get("primary_action")) or "explain",
        "content_role": role,
        "topic_type": ttype,
        "practice_evidence_type": str(cap.get("practice_evidence_type") or ""),
        "expected_output": str(cap.get("expected_output") or ""),
        "basis": str(cap.get("basis") or "coverage_repair"),
        "topic_relationships": [],
        # the capability's own description is the one content commitment we KNOW this topic owns
        "in_scope": [description] if description else [],
        "learner_outcome": description or None,
        # a real learner-facing purpose — without it, the mapping falls through to the synthetic
        # "Reach the capability: <X>" default, which leaked into the intro's roadmap card (live)
        "primary_capability": str(cap.get("primary_capability") or title or "").strip() or None,
        "purpose": description or None,
        "provenance": {"synthesized": True, "reason": "coverage_repair"},
    }
    record_topic_decision(
        topic, "validator.synthesized_for_coverage", f"created {title!r}",
        "a REQUIRED capability had no owning topic anywhere in the model's plan (dropped entirely, or its "
        "covers_requirements claim failed verification) — B.4.1 coverage repair builds a standalone topic "
        "deterministically from the capability record itself, never from the raw capability_id",
        capability_id=cid, basis=topic["basis"])
    return topic


def _base_subject(subject_key: Any) -> str:
    """Base subject identity for the merge: normalize, then strip trailing facet tokens so an
    'apply/interpret/compute' variant collapses onto the concept it treats."""
    s = normalize_subject_key(str(subject_key or ""))
    tokens = [t for t in s.split("_") if t]
    while len(tokens) > 1 and tokens[-1] in _FACET_SUFFIX_TOKENS:
        tokens.pop()
    return "_".join(tokens) if tokens else s


def _clean_merged_title(title: Any) -> str:
    t = str(title or "").strip()
    parts = t.split(None, 1)
    if len(parts) == 2 and parts[0].lower() in _LEADING_ACTION_WORDS:
        return parts[1]
    return t


def _absorb_topic(keeper: dict[str, Any], victim: dict[str, Any],
                  caps: dict[str, dict[str, Any]]) -> None:
    """Fold `victim` into `keeper`: union scope, carry practice-capability if missing, and re-home the
    victim's capability as embedded under keeper (so coverage/reachability still hold)."""
    for f in ("in_scope", "out_of_scope"):
        merged = list(keeper.get(f) or [])
        for x in victim.get(f) or []:
            if x not in merged:
                merged.append(x)
        if merged:
            keeper[f] = merged
    for f in ("practice_target", "practice_format", "practice_evidence_type", "expected_output"):
        if not str(keeper.get(f) or "").strip() and str(victim.get(f) or "").strip():
            keeper[f] = victim[f]
    keeper["title"] = _clean_merged_title(keeper.get("title"))

    kcid, vcid = str(keeper.get("capability_id")), str(victim.get("capability_id"))
    kcap, vcap = caps.get(kcid), caps.get(vcid)
    if vcap is not None:
        vcap["ownership_mode"] = "embedded"
        vcap["owner_topic_id"] = str(keeper.get("topic_id"))
        if kcap is not None:
            k_end = list(kcap.get("satisfies_end_actions") or [])
            for a in vcap.get("satisfies_end_actions") or []:
                if a not in k_end:
                    k_end.append(a)
            kcap["satisfies_end_actions"] = k_end
            k_pre = {p for p in (kcap.get("prerequisite_capability_ids") or []) if p not in (kcid, vcid)}
            k_pre |= {p for p in (vcap.get("prerequisite_capability_ids") or []) if p not in (kcid, vcid)}
            kcap["prerequisite_capability_ids"] = sorted(k_pre)
    # anything that depended on the victim now depends on the keeper
    for cid, cap in caps.items():
        if cid in (kcid, vcid):
            continue
        pres = cap.get("prerequisite_capability_ids") or []
        if vcid in pres:
            cap["prerequisite_capability_ids"] = [kcid if p == vcid else p for p in pres]


def _merge_same_subject_topics(topics: list[dict[str, Any]], caps: dict[str, dict[str, Any]],
                               actions: list[ValidatorAction]) -> list[dict[str, Any]]:
    """B.4.2b — collapse an 'understand X' + 'apply X' split into ONE teaching topic. Fires only on
    same-base-subject, non-coding teaching topics whose learner ACTIONS DIFFER (a real facet split);
    same-action pairs are left to duplicate detection so the sole-owner guard is untouched. The richest
    blueprint type wins; the leaner topic's capability is embedded under it."""
    pos = {id(t): i for i, t in enumerate(topics)}
    groups: dict[str, list[dict[str, Any]]] = {}
    for t in topics:
        if str(t.get("topic_type") or "") not in _MERGEABLE_TYPE_PRIORITY:
            continue
        base = _base_subject(t.get("subject_key"))
        if base:
            groups.setdefault(base, []).append(t)

    remove: set[int] = set()
    for base, group in groups.items():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda t: (_MERGEABLE_TYPE_PRIORITY[str(t.get("topic_type"))], pos[id(t)]))
        keeper = ordered[0]
        used_actions = {canonical_action(keeper.get("primary_action"))}
        for t in ordered[1:]:
            ca = canonical_action(t.get("primary_action"))
            if ca is None or ca in used_actions:
                continue  # same action -> a duplicate, not a facet split; leave it for dedup
            _absorb_topic(keeper, t, caps)
            used_actions.add(ca)
            remove.add(id(t))
            actions.append(ValidatorAction(
                "subject_merge", SUBJECT_MERGE,
                f"folded {t.get('title')!r} into {keeper.get('title')!r} "
                f"(same subject {base!r}; understand+apply → one topic)",
                [str(keeper.get("topic_id")), str(t.get("topic_id"))]))
    return [t for t in topics if id(t) not in remove]


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

    # B.4.2b same-subject merge — fold an understand+apply split into one teaching topic BEFORE dedup
    # (only different-action pairs merge, so same-action duplicates still reach the dedup/sole-owner pass).
    topics = _merge_same_subject_topics(topics, caps, actions)

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

    # B.4.1 coverage REPAIR — synthesize a topic for any REQUIRED standalone capability the model dropped, BEFORE
    # ordering so the new topic is ordered by its prerequisites. This is the fix for the dropped-concept bug: a
    # goal naming two techniques (e.g. total probability + Bayes) always yields a topic for each.
    owned_now = {str(t.get("capability_id")) for t in topics}
    for cid, cap in caps.items():
        if str(cap.get("ownership_mode") or "") == "standalone" and cid not in owned_now:
            synth = _synthesize_topic_for_capability(cid, cap)
            topics.append(synth)
            owned_now.add(cid)
            actions.append(ValidatorAction(
                "coverage", REPAIR, f"synthesized topic for uncovered required capability {cid}",
                [synth["topic_id"]]))

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
