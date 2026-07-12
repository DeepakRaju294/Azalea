"""Prerequisite-links — production shadow (PREREQ_LINKS_SPEC v8 §6.1/§6.3a/§6.7).

Bridges the pure `app.core.prereq_links` package to the live product: it maps the pipeline's already-generated
topics + their assumed-prerequisite metadata onto a `DecompositionClassification` and runs the Tier-2
classification validator (§6.3a) in SHADOW — emitting neutral telemetry (ok / fallback_reason counts), never
mutating anything, never touching generation. Dark behind `AZALEA_PREREQ_LINKS`.

Deliberately does NOT import any route/`deps` module (that would leak `.env` flags into tests) — only the pure
`prereq_links` + `study_path_scope` packages + stdlib. Topics are duck-typed (`.title`, `.course_type`,
`.order_index`, `.decomposition_metadata`, `.assumed_prerequisites`), so this is testable without the DB.

Fidelity caveat (this phase): today's decomposition does NOT yet emit the §3.1 scope_rule or a real
in-scope/out-of-scope split, so this shadow validates the STRUCTURAL contracts (disjointness §A11, unique
ownership §A37, navigation-alias uniqueness) against the current prereq/concept graph — it does not yet exercise
the LLM scope classification. `target_goal`/`scope_rule` are synthesized as valid so those checks don't
false-positive on data that legitimately lacks them today. Wiring the real §6.1 classification (prompt-level) is
the later, heavier half."""
from __future__ import annotations

import logging
import os
from collections import Counter
from typing import Any, Optional

from app.core.prereq_links import (
    AssumedPrerequisite, DecompositionClassification, ScopeRule, TopicConceptIdentity, validate_classification,
)
from app.core.study_path_scope import stable_slug

_log = logging.getLogger(__name__)

_FLAG = "AZALEA_PREREQ_LINKS"
_INTRO_TYPES = {"study_path_introduction"}


def _enabled() -> bool:
    return os.getenv(_FLAG, "").strip().lower() in ("1", "true", "yes", "on")


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


def topics_to_classification(topics: list[Any]) -> DecompositionClassification:
    """Best-effort map of live topics → the Tier-2 validator input. Concept topics become owning
    `TopicConceptIdentity` records; every distinct assumed-prerequisite name becomes an `AssumedPrerequisite`.
    Prereqs that ALSO name a taught concept are kept (NOT filtered) so the validator can flag the overlap."""
    concepts = _concept_topics(topics)
    identities: list[TopicConceptIdentity] = []
    for i, t in enumerate(concepts):
        identities.append(TopicConceptIdentity(
            topic_id=str(getattr(t, "id", None) or f"t{i}"), topic_index=i,
            concept_id=_concept_key(t), canonical_name=str(getattr(t, "title", "") or _concept_key(t))))

    prereqs: dict[str, AssumedPrerequisite] = {}
    for t in concepts:
        for pre in (getattr(t, "assumed_prerequisites", None) or []):
            name = str(pre)
            cid = stable_slug(name)
            prereqs.setdefault(cid, AssumedPrerequisite(
                concept_id=cid, canonical_name=name, display_text=name,
                target_goal=f"Understand the basics of {name}.",   # synthesized (see fidelity caveat)
                scope_rule=ScopeRule.recognition_only_fallback))
    return DecompositionClassification(
        topic_identities=identities, assumed_prerequisites=list(prereqs.values()))


def shadow_report(topics: list[Any]) -> dict[str, Any]:
    """Run the Tier-2 validator over the classification and return a flat log record. Pure over its inputs."""
    dc = topics_to_classification(topics)
    result = validate_classification(dc)
    reasons = Counter(f.reason.value for f in result.failures)
    return {
        "ok": result.ok,
        "fallback_reason": result.fallback_reason.value if result.fallback_reason else None,
        "fallback_reasons": dict(sorted(reasons.items())),
        "n_topics": len(dc.topic_identities),
        "n_prereqs": len(dc.assumed_prerequisites),
        "n_failures": len(result.failures),
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


def maybe_log_prereq_links_shadow(goal: str, domain: str, topics: list[Any]) -> Optional[dict[str, Any]]:
    """Flag-gated, never-throwing shadow log (§6.7 telemetry). Returns None when the flag is off or anything
    goes wrong; never affects generation."""
    if not _enabled():
        return None
    try:
        report = shadow_report(topics)
        _log.info("prereq_links_shadow %s", report)
        _append_telemetry(report, goal, domain)
        return report
    except Exception as exc:  # noqa: BLE001 — shadow telemetry must never break generation
        _log.warning("prereq_links_shadow failed: %s", exc)
        return None
