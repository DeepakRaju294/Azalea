"""StudyPathScope — Phase-1A production shadow (STUDY_PATH_SCOPE_SPEC §10).

The ONE piece that bridges the pure `app.core.study_path_scope` package to the live product: it maps the
pipeline's already-generated topics onto a `DecompositionInput`, builds the scope plan, and diffs the plan
against today's output — emitting NEUTRAL counts/distances (never mutating anything, never touching
generation). Dark behind `AZALEA_STUDY_PATH_SCOPE`.

Deliberately does NOT import any route/`deps` module (that would leak `.env` flags into tests) — only the pure
scope package + stdlib. Topics are duck-typed (`.title`, `.course_type`, `.order_index`,
`.decomposition_metadata`, `.assumed_prerequisites`), so this is testable without the DB.

Fidelity caveat (Phase 1A): the plan is derived from the SAME topics it is diffed against, so it mainly
verifies the scope's own transforms (facet consolidation, prereq/concept split, ordering, domain legality)
agree with the pipeline. Requirements are synthesized one-per-concept (the persisted topics carry no explicit
GoalRequirement list). Independent goal-decomposition and prereq-edge extraction are later refinements.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from app.core.study_path_scope import (
    ConceptDraft, DecompositionInput, GoalRequirement, PrereqDraft, SelectionMethod, ShadowBaseline,
    ShadowMetrics, build_plan, failed_invariants, shadow_diff, stable_slug,
)

_log = logging.getLogger(__name__)

_FLAG = "AZALEA_STUDY_PATH_SCOPE"
_INTRO_TYPES = {"study_path_introduction"}


def _enabled() -> bool:
    return os.getenv(_FLAG, "").strip().lower() in ("1", "true", "yes", "on")


def _md(topic: Any) -> dict:
    return getattr(topic, "decomposition_metadata", None) or {}


def _is_intro(topic: Any) -> bool:
    """The intro is DERIVED by the scope, not a concept — exclude it from both plan and baseline."""
    ct = str(getattr(topic, "course_type", None) or "").lower()
    return ct in _INTRO_TYPES or str(_md(topic).get("content_role") or "").lower() == "orientation"


def _concept_key(topic: Any) -> str:
    """Stable canonical key: the decomposition's subject_key / capability_id if present, else a slug of the
    title (so a rename does not churn identity)."""
    md = _md(topic)
    return stable_slug(md.get("subject_key") or md.get("capability_id") or getattr(topic, "title", ""))


def _concept_topics(topics: list[Any]) -> list[Any]:
    return sorted((t for t in topics if not _is_intro(t)), key=lambda t: getattr(t, "order_index", 0) or 0)


def topics_to_decomposition_input(goal: str, domain: str, topics: list[Any],
                                  source_revision: str = "") -> DecompositionInput:
    concepts = _concept_topics(topics)
    requirements: list[GoalRequirement] = []
    drafts: list[ConceptDraft] = []
    mention: list[str] = []
    prereq_names: dict[str, str] = {}
    for t in concepts:
        key = _concept_key(t)
        rid = f"req_{key}"
        requirements.append(GoalRequirement(requirement_id=rid, description=str(getattr(t, "title", "") or key)))
        drafts.append(ConceptDraft(
            canonical_concept_key=key, name=str(getattr(t, "title", "") or key),
            topic_type=str(getattr(t, "course_type", None) or "concept"),
            covers_requirements=[rid], selection_method=SelectionMethod.curriculum_graph))
        mention.append(key)
        for pre in (getattr(t, "assumed_prerequisites", None) or []):
            prereq_names.setdefault(stable_slug(pre), str(pre))
    concept_keys = {d.canonical_concept_key for d in drafts}
    prereqs = [PrereqDraft(id=pid, name=name) for pid, name in prereq_names.items()
               if pid not in concept_keys]                      # a prereq that is also taught is not a prereq
    return DecompositionInput(
        goal=goal, domain=domain, source_revision=source_revision, requirements=requirements,
        concepts=drafts, prereqs=prereqs, mention_order=mention, source_order=mention)


def topics_to_baseline(topics: list[Any]) -> ShadowBaseline:
    concepts = _concept_topics(topics)
    keys = [_concept_key(t) for t in concepts]
    concept_key_set = set(keys)
    prereq_ids = []
    for t in concepts:
        for pre in (getattr(t, "assumed_prerequisites", None) or []):
            pid = stable_slug(pre)
            if pid not in concept_key_set and pid not in prereq_ids:
                prereq_ids.append(pid)
    return ShadowBaseline(
        concept_keys=keys, prereq_ids=prereq_ids, concept_order=keys,
        topic_types={_concept_key(t): str(getattr(t, "course_type", None) or "") for t in concepts})


def shadow_report(goal: str, domain: str, topics: list[Any], source_revision: str = "") -> dict[str, Any]:
    """Build the scope plan from the topics, diff it against them, and return a flat log record. Pure over its
    inputs (no DB, no flag check) — callers gate on `_enabled()`."""
    inp = topics_to_decomposition_input(goal, domain, topics, source_revision)
    plan = build_plan(inp)
    metrics: ShadowMetrics = shadow_diff(plan, topics_to_baseline(topics))
    return {
        "scope_id": plan.identity.scope_id,
        "planning_status": plan.identity.planning_status.value,
        "failed_invariants": failed_invariants(plan.validation),
        "concept_count": len(plan.curriculum.concepts),
        "diff_class": metrics.diff_class.value,
        "metrics": metrics.model_dump(),
    }


def maybe_log_shadow(goal: str, domain: str, topics: list[Any],
                     source_revision: str = "") -> Optional[dict[str, Any]]:
    """Flag-gated, never-throwing shadow log. Safe to call from anywhere in the pipeline: returns None when the
    flag is off or anything goes wrong, and never affects generation."""
    if not _enabled():
        return None
    try:
        report = shadow_report(goal, domain, topics, source_revision)
        _log.info("scope_shadow %s", report)
        return report
    except Exception as exc:  # noqa: BLE001 — shadow telemetry must never break generation
        _log.warning("scope_shadow failed: %s", exc)
        return None
