"""Prerequisite-links — production shadow (PREREQ_LINKS_SPEC v8 §6.1/§6.3a/§6.7).

Bridges the pure `app.core.prereq_links` package to the live product: it maps the pipeline's already-generated
topics + their assumed-prerequisite metadata onto a `DecompositionClassification` and runs the Tier-2
classification validator (§6.3a) in SHADOW — emitting neutral telemetry (ok / fallback_reason counts), never
mutating anything, never touching generation. Dark behind `AZALEA_PREREQ_LINKS`.

Deliberately does NOT import any route/`deps` module (that would leak `.env` flags into tests) — only the pure
`prereq_links` + `study_path_scope` packages + stdlib. Topics are duck-typed (`.title`, `.course_type`,
`.order_index`, `.decomposition_metadata`, `.assumed_prerequisites`), so this is testable without the DB.

Real §3.1 classification (app/services/prereq_scope_classifier.py) is wired in behind a SEPARATE kill-switch,
`AZALEA_PREREQ_SCOPE_CLASSIFICATION` (default off) — independent of `AZALEA_PREREQ_LINKS` so real classification
can be flipped back to today's synthesized-stub behavior instantly (no code revert) if it ever misbehaves, without
touching the already-trusted structural validation this module has run since Phase 1 started. With it off (or
`goal` empty), output is byte-identical to the old stub: `target_goal` synthesized, `scope_rule` always
`recognition_only_fallback`, no `InPathFoundation`s, no mismatch/distribution telemetry."""
from __future__ import annotations

import logging
import os
from collections import Counter
from typing import Any, Optional

from app.core.prereq_links import (
    IN_SCOPE_RULES, AssumedPrerequisite, DecompositionClassification, InPathFoundation, ScopeRule,
    TopicConceptIdentity, validate_classification,
)
from app.core.study_path_scope import stable_slug
from app.services.prereq_scope_classifier import build_prerequisite_goal, classify_recommended_scope_rule

_log = logging.getLogger(__name__)

_FLAG = "AZALEA_PREREQ_LINKS"
_CLASSIFICATION_FLAG = "AZALEA_PREREQ_SCOPE_CLASSIFICATION"
_INTRO_TYPES = {"study_path_introduction"}


def _enabled() -> bool:
    return os.getenv(_FLAG, "").strip().lower() in ("1", "true", "yes", "on")


def _classification_enabled() -> bool:
    return os.getenv(_CLASSIFICATION_FLAG, "").strip().lower() in ("1", "true", "yes", "on")


def _md(topic: Any) -> dict:
    return getattr(topic, "decomposition_metadata", None) or {}


def _is_intro(topic: Any) -> bool:
    ct = str(getattr(topic, "course_type", None) or "").lower()
    return ct in _INTRO_TYPES or str(_md(topic).get("content_role") or "").lower() == "orientation"


def _concept_key(topic: Any) -> str:
    md = _md(topic)
    return stable_slug(md.get("subject_key") or md.get("capability_id") or getattr(topic, "title", ""))


def _concept_topics(topics: list[Any]) -> list[Any]:
    return sorted((t for t in topics if not _is_intro(t)), key=lambda t: getattr(t, "order_index", 0) or 0)


def _build_classification(
    topics: list[Any], goal: str, domain: str, model_fn: Any,
) -> tuple[DecompositionClassification, list[dict[str, Any]], dict[str, int]]:
    """The real work behind `topics_to_classification`. Returns `(classification, scope_mismatches,
    classified_scope_rule_distribution)`. Classification is attempted only when `goal` is non-empty AND
    `AZALEA_PREREQ_SCOPE_CLASSIFICATION` is on; each candidate is classified in ISOLATION — one candidate's
    failure degrades only that candidate to the fallback, it never drops the candidate, never touches the
    unconditionally-built `TopicConceptIdentity` list, and never affects any other candidate."""
    concepts = _concept_topics(topics)
    # One canonical OWNER per concept (§1.1b): when several topics share a concept key (the natural
    # walkthrough + implementation shape of one algorithm), the EARLIEST is the owner and the rest are
    # non-owning application/synthesis topics — NOT a duplicate-ownership contradiction. Collapse to the first,
    # so the shadow models the spec invariant instead of false-flagging multi-topic-per-concept paths.
    identities: list[TopicConceptIdentity] = []
    owner_topic_by_concept: dict[str, Any] = {}
    seen_concepts: set[str] = set()
    for i, t in enumerate(concepts):
        cid = _concept_key(t)
        if cid in seen_concepts:
            continue
        seen_concepts.add(cid)
        owner_topic_by_concept[cid] = t
        identities.append(TopicConceptIdentity(
            topic_id=str(getattr(t, "id", None) or f"t{i}"), topic_index=i,
            concept_id=cid, canonical_name=str(getattr(t, "title", "") or cid)))

    # Prerequisites are stored on the INTRO topic (which names them without teaching), not the concept topics —
    # so harvest from ALL topics, else n_prereqs is always 0 and the overlap check never sees them.
    #
    # Split by scope (the §3.1 insight the corpus revealed): a "prerequisite" whose concept is an EARLIER TOPIC
    # in this same path is an intra-path dependency → an IN-scope review reference (review_earlier_topic), NOT an
    # external prerequisite. Only a prereq that matches no taught topic is a true external assumed_prerequisite
    # (open_study_path). Conflating the two is what made benign "topic B builds on earlier topic A" links look
    # like a disjointness violation.
    prereq_first_mention: dict[str, tuple[str, Any]] = {}   # cid -> (name, the topic that first named it)
    review_refs: set[str] = set()
    for t in topics:
        for pre in (getattr(t, "assumed_prerequisites", None) or []):
            name = str(pre)
            cid = stable_slug(name)
            if cid in seen_concepts:                     # names an earlier taught topic → review-earlier (in-path)
                review_refs.add(cid)
                continue
            prereq_first_mention.setdefault(cid, (name, t))    # first mention wins -> one classifier call/candidate

    run_classification = bool(goal.strip()) and _classification_enabled()
    cache: dict[tuple[str, str], tuple[ScopeRule, str]] = {}
    mismatches: list[dict[str, Any]] = []
    classified_distribution: Counter[str] = Counter()

    def _classify(cid: str, name: str, candidate_kind: str) -> tuple[ScopeRule, str]:
        key = (cid, candidate_kind)
        if key not in cache:
            cache[key] = classify_recommended_scope_rule(
                canonical_name=name, goal=goal, domain=domain, candidate_kind=candidate_kind, model_fn=model_fn)
        rule, rationale = cache[key]
        classified_distribution[rule.value] += 1
        return rule, rationale

    in_path_foundations: list[InPathFoundation] = []
    if run_classification:
        for cid, t in owner_topic_by_concept.items():
            if str(_md(t).get("content_role") or "").lower() != "foundation":
                continue
            name = str(getattr(t, "title", "") or cid)
            try:
                rule, rationale = _classify(cid, name, "taught_foundation")
                if rule in IN_SCOPE_RULES:
                    in_path_foundations.append(InPathFoundation(
                        concept_id=cid, canonical_name=name, topic_id=str(getattr(t, "id", None) or ""),
                        scope_rule=rule, scope_rationale=rationale))
                else:
                    mismatches.append({"canonical_name": name, "candidate_kind": "taught_foundation",
                                       "direction": "taught_but_model_says_fallback",
                                       "assigned_rule": None, "classified_rule": rule.value})
            except Exception as exc:  # noqa: BLE001 — one candidate's failure must never affect the others
                _log.warning("prereq_scope_classifier: foundation candidate %r failed: %s", cid, exc)

    prereqs: dict[str, AssumedPrerequisite] = {}
    for cid, (name, origin_topic) in prereq_first_mention.items():
        origin_title = str(getattr(origin_topic, "title", "") or "")
        target_goal = build_prerequisite_goal(name, domain, origin_title)   # always computed, never gated (§A15)
        rationale = ""
        if run_classification:
            try:
                rule, rationale = _classify(cid, name, "assumed_prerequisite")
                if rule in IN_SCOPE_RULES:
                    mismatches.append({"canonical_name": name, "candidate_kind": "assumed_prerequisite",
                                       "direction": "assumed_but_model_says_in_scope",
                                       "assigned_rule": ScopeRule.recognition_only_fallback.value,
                                       "classified_rule": rule.value})
            except Exception as exc:  # noqa: BLE001 — a failed classification degrades to no rationale, never drops
                _log.warning("prereq_scope_classifier: prerequisite candidate %r failed: %s", cid, exc)
        prereqs[cid] = AssumedPrerequisite(
            concept_id=cid, canonical_name=name, display_text=name, target_goal=target_goal,
            scope_rule=ScopeRule.recognition_only_fallback,   # ALWAYS the fallback — never the classifier's rule
            scope_rationale=rationale)

    dc = DecompositionClassification(
        in_path_foundations=in_path_foundations, topic_identities=identities,
        assumed_prerequisites=list(prereqs.values()), review_referenced_concept_ids=sorted(review_refs))
    return dc, mismatches, dict(sorted(classified_distribution.items()))


def topics_to_classification(
    topics: list[Any], goal: str = "", domain: str = "", model_fn: Any = None,
) -> DecompositionClassification:
    """Best-effort map of live topics → the Tier-2 validator input. Concept topics become owning
    `TopicConceptIdentity` records; every distinct assumed-prerequisite name becomes an `AssumedPrerequisite`.
    Prereqs that ALSO name a taught concept are kept (NOT filtered) so the validator can flag the overlap.
    `goal`/`domain`/`model_fn` are optional — see module docstring for the exact conditions real classification
    requires; omitting `goal` reproduces the old stub-only behavior exactly."""
    dc, _mismatches, _distribution = _build_classification(topics, goal, domain, model_fn)
    return dc


def shadow_report(
    topics: list[Any], *, goal: str = "", domain: str = "", model_fn: Any = None,
) -> dict[str, Any]:
    """Run the Tier-2 validator over the classification and return a flat log record. Pure over its inputs
    (aside from `_classification_enabled()`'s own env read)."""
    dc, mismatches, classified_distribution = _build_classification(topics, goal, domain, model_fn)
    result = validate_classification(dc)
    reasons = Counter(f.reason.value for f in result.failures)
    assigned_distribution = Counter(
        [f.scope_rule.value for f in dc.in_path_foundations] + [p.scope_rule.value for p in dc.assumed_prerequisites])
    return {
        "ok": result.ok,
        "fallback_reason": result.fallback_reason.value if result.fallback_reason else None,
        "fallback_reasons": dict(sorted(reasons.items())),
        "n_topics": len(dc.topic_identities),
        "n_prereqs": len(dc.assumed_prerequisites),
        "n_failures": len(result.failures),
        # §3.1's own stated telemetry purpose: which rule fires most, and where classification disagrees with
        # what decomposition already did. `scope_rule_distribution` counts VALIDATED/EMITTED values (every
        # assumed_prerequisite counts as recognition_only_fallback here, by contract); `classified_scope_rule_
        # distribution` counts the RAW classifier outputs before that contract coercion — the two differ exactly
        # by the mismatches below.
        "scope_rule_distribution": dict(sorted(assigned_distribution.items())),
        "classified_scope_rule_distribution": classified_distribution,
        "scope_mismatches": mismatches,
    }


def _append_telemetry(report: dict[str, Any], goal: str, domain: str) -> None:
    """Persist one shadow report as a JSONL line when AZALEA_PREREQ_LINKS_TELEMETRY_PATH is set. Best-effort."""
    path = os.getenv("AZALEA_PREREQ_LINKS_TELEMETRY_PATH", "").strip()
    if not path:
        return
    import datetime
    import json
    row = {"ts": datetime.datetime.utcnow().isoformat(), "goal": goal, "domain": domain, **report}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def maybe_log_prereq_links_shadow(
    goal: str, domain: str, topics: list[Any], model_fn: Any = None,
) -> Optional[dict[str, Any]]:
    """Flag-gated, never-throwing shadow log (§6.7 telemetry). Returns None when the flag is off or anything
    goes wrong; never affects generation."""
    if not _enabled():
        return None
    try:
        report = shadow_report(topics, goal=goal, domain=domain, model_fn=model_fn)
        _log.info("prereq_links_shadow %s", report)
        _append_telemetry(report, goal, domain)
        return report
    except Exception as exc:  # noqa: BLE001 — shadow telemetry must never break generation
        _log.warning("prereq_links_shadow failed: %s", exc)
        return None
