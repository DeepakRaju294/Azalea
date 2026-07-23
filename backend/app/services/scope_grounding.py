"""StudyPathScope Phase 1B — adapter-backed grounding, first slice (STUDY_PATH_SCOPE_SPEC §10).

Pure translation layer, mirroring scope_shadow.py's own split: THIS module stays pure (no flag check, no
route/deps import at module scope — the deferred import below avoids leaking .env into tests that import
this module), the caller (scope_shadow.py) decides whether to call it at all. Routes a concept through the
EXISTING adapter catalog (`route_adapter` — the same routing production lessons already use, not
reinvented) and turns the result into a `ConceptGrounding`: grounded (`AlgorithmGrounding`) when a verified
adapter matches, degraded (`GeneralConceptGrounding`) otherwise. Never invents (§6.1) — a concept with no
adapter match gets an explicit degrade_reason, not silence or a fabricated fact.

This slice records that a verified adapter is ROUTED, not that its trace was re-executed — executable trace
audits (§4.12), notation unification (§6.2), and the other 8 §1.3 grounding variants (no verifier backend
exists for any of them yet — sympy/code-exec/reference are Phase 3, §13) are all explicitly deferred."""
from __future__ import annotations

from typing import Any

from app.core.study_path_scope import (
    AlgorithmGrounding, Concept, ConceptGrounding, GeneralConceptGrounding, GroundingArtifact,
    GroundingSummary,
)


def _topic_dict(topic: Any) -> dict[str, Any]:
    """The duck-typed shape `route_adapter` reads — same fields scope_shadow.py already assembles from a
    pipeline topic (title / course_type / subject_key via decomposition_metadata)."""
    md = getattr(topic, "decomposition_metadata", None) or {}
    return {
        "title": getattr(topic, "title", "") or "",
        "topic_type": getattr(topic, "course_type", None) or "",
        "subject_key": md.get("subject_key") or md.get("capability_id") or "",
    }


def ground_concept(concept: Concept, topic: Any) -> ConceptGrounding:
    """Ground ONE concept via the existing adapter catalog. `concept` supplies identity (kept on the call
    for callers that want it for telemetry — routing itself only reads `topic`); `topic` is the duck-typed
    pipeline object `route_adapter` already knows how to read."""
    from app.services.examples.trace_pipeline import route_adapter  # deferred: avoid importing routes/deps
    adapter = route_adapter(_topic_dict(topic))
    if adapter is not None:
        return AlgorithmGrounding(
            adapter_slug=adapter.slug,
            artifacts={"adapter_slug": GroundingArtifact(name="adapter_slug", value=adapter.slug)},
            summary=GroundingSummary(completeness=1.0, required_artifacts_present=True),
        )
    return GeneralConceptGrounding(
        degrade_reason="no_adapter_match",
        summary=GroundingSummary(completeness=0.0, required_artifacts_present=False),
    )


def ground_concepts(concepts: list[Concept], topics_by_key: dict[str, Any]) -> dict[str, ConceptGrounding]:
    """Ground every concept in a built plan's curriculum, keyed by canonical_concept_key. `topics_by_key`
    maps that same key to the original duck-typed pipeline topic — the caller (scope_shadow.py) already
    computes this key per topic for its own baseline, so it's passed in rather than recomputed here."""
    out: dict[str, ConceptGrounding] = {}
    for c in concepts:
        topic = topics_by_key.get(c.identity.canonical_concept_key)
        if topic is not None:
            out[c.identity.canonical_concept_key] = ground_concept(c, topic)
    return out


def grounding_counts(groundings: dict[str, ConceptGrounding]) -> dict[str, int]:
    """adapter-hit vs degraded rollup for telemetry — additive JSONL field, no schema break for readers."""
    grounded = sum(1 for g in groundings.values() if isinstance(g, AlgorithmGrounding))
    degraded = sum(1 for g in groundings.values() if isinstance(g, GeneralConceptGrounding))
    return {"grounded": grounded, "degraded": degraded}
