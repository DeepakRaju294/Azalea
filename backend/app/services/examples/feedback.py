"""Regeneration / feedback interface (PROJECTOR_SYSTEM_SPEC §11).

User feedback improves the system by re-running a *deterministic derivation*, never by
re-rolling an LLM or editing per-frame state. A correction targets the projection
contract, the input, or the code; the system re-projects and verifies the model changed
*in the targeted way* (the 4-part definition of a successful regeneration, §11.3).

This module owns the data shapes + the local (Stage-1) regeneration. Patch promotion
(Stage-2) is proposed here and gated by goldens before it can widen scope.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

# §11.2 — normalize what users report to the contract field a fix should target.
ISSUE_TO_TARGET: dict[str, str] = {
    "wrong_active_node": "projection",
    "missing_visited_node": "projection",
    "wrong_visit_order": "projection",
    "missing_selected_edge": "projection",
    "wrong_selected_edge": "projection",
    "missing_frontier": "projection",
    "wrong_base_structure": "input",
    "trace_truncated": "code",
    "code_visual_step_mismatch": "milestone_policy",
    "empty_state": "projection",
    "prose_visual_mismatch": "prose",
}


def issue_to_target(issue_type: str) -> str:
    return ISSUE_TO_TARGET.get(issue_type, "projection")


@dataclass(frozen=True)
class RegenerationRequest:
    topic_id: str
    shape: str                       # "node_link"
    correction_target: str           # projection | input | code | milestone_policy | prose
    correction: dict[str, Any]       # e.g. {"current_from": "u"} or {"base_structure": {...}}


@dataclass(frozen=True)
class RegenerationDiff:
    before_tier: str
    after_tier: str
    before_projection_contract: Optional[dict[str, Any]]
    after_projection_contract: Optional[dict[str, Any]]
    before_event_ids: list[str]
    after_event_ids: list[str]
    changed_frames: list[int]
    changed_nodes: list[str]
    changed_edges: list[tuple[str, str]]


@dataclass(frozen=True)
class FeedbackRecord:
    topic_id: str
    application: Optional[str]
    pattern: Optional[str]
    shape: str
    tier: str
    fixture_id: Optional[str]
    visual_model_id: str
    frame_index: Optional[int]
    issue_type: str
    user_text: str
    severity: str                    # minor | major | blocking
    user_confidence: str             # low | medium | high
    system_confidence: float
    correction_target: str
    accepted_correction: dict[str, Any]
    post_regen_validation_status: str
    targeted_change_observed: bool


@dataclass(frozen=True)
class ProjectionPatch:
    patch_id: str
    shape: str
    application: Optional[str]
    pattern: Optional[str]
    issue_type: str
    correction_target: str
    correction: dict[str, Any]
    scope: Literal["fixture", "application_profile", "shape_projector", "inference_rule"]
    created_from_topic_id: str
    validation_result: str


# ---------------------------------------------------------------------------
# Stage-1 local regeneration (§11.5). Apply the correction to THIS example, re-run
# the deterministic route, and verify the model changed in the targeted way.
# ---------------------------------------------------------------------------


def _apply_correction(example: dict[str, Any], request: RegenerationRequest) -> dict[str, Any]:
    ex = dict(example)
    if request.correction_target == "projection":
        ex["graph_projection"] = {**dict(ex.get("graph_projection") or {}), **request.correction}
    elif request.correction_target == "input":
        if "base_structure" in request.correction:
            ex["base_structure"] = request.correction["base_structure"]
        if "input" in request.correction:
            ex["input"] = request.correction["input"]
    elif request.correction_target == "code":
        if "code" in request.correction:
            ex["code"] = request.correction["code"]
        if "entry_function" in request.correction:
            ex["entry_function"] = request.correction["entry_function"]
    return ex


def _frame_sigs(model: Optional[dict[str, Any]]) -> list[tuple]:
    sigs: list[tuple] = []
    for frame in (model or {}).get("frames") or []:
        state = frame.get("state") or {}
        nodes = frozenset((str(e.get("node_id")), str(e.get("state"))) for e in state.get("node_state_map") or [])
        edges = frozenset(zip(state.get("completed_edges_from") or [], state.get("completed_edges_to") or []))
        sigs.append((str(state.get("active_node") or ""), nodes, edges))
    return sigs


def _diff(before: dict[str, Any], after: dict[str, Any], request: RegenerationRequest) -> RegenerationDiff:
    bm, am = before.get("model"), after.get("model")
    bsig, asig = _frame_sigs(bm), _frame_sigs(am)
    changed_frames = [i for i in range(max(len(bsig), len(asig)))
                      if i >= len(bsig) or i >= len(asig) or bsig[i] != asig[i]]
    bnodes = {n for _, ns, _ in bsig for n, _s in ns}
    anodes = {n for _, ns, _ in asig for n, _s in ns}
    bedges = {e for _, _, es in bsig for e in es}
    aedges = {e for _, _, es in asig for e in es}

    def prov(m, key):
        return ((m or {}).get("provenance") or {}).get(key)

    def event_ids(res):
        proj = res.get("projection")
        return [d.get("event_id") for d in (getattr(proj, "deltas", None) or [])]

    return RegenerationDiff(
        before_tier=prov(bm, "tier") or "",
        after_tier=prov(am, "tier") or "",
        before_projection_contract=prov(bm, "projection_contract"),
        after_projection_contract=prov(am, "projection_contract"),
        before_event_ids=event_ids(before),
        after_event_ids=event_ids(after),
        changed_frames=changed_frames,
        changed_nodes=sorted(bnodes ^ anodes),
        changed_edges=sorted(bedges ^ aedges),
    )


def regenerate(example: dict[str, Any], request: RegenerationRequest, *, model_id: str = "regen") -> dict[str, Any]:
    """Stage-1: re-derive `example` with the correction applied. Returns the before/after
    results, the diff, and whether the regeneration SUCCEEDED — all four of: correction
    applied, pipeline re-ran, validators passed, model changed in the targeted way."""
    from app.services.visual_v2.pipeline import run_for_registered

    before = run_for_registered(example, model_id=f"{model_id}_before")
    corrected = _apply_correction(example, request)
    after = run_for_registered(corrected, model_id=f"{model_id}_after")
    diff = _diff(before, after, request)

    validators_passed = after.get("status") == "validated"
    targeted_change_observed = bool(diff.changed_frames or diff.changed_nodes or diff.changed_edges)
    success = validators_passed and targeted_change_observed
    return {
        "before": before,
        "after": after,
        "diff": diff,
        "validators_passed": validators_passed,
        "targeted_change_observed": targeted_change_observed,
        "success": success,
    }


def propose_patch(record: FeedbackRecord, *, scope: str = "fixture") -> ProjectionPatch:
    """Stage-2 proposal (§11.4). Defaults to the narrowest scope; widening requires the
    golden gate (`promotion_gate`) and human approval (§11.5)."""
    return ProjectionPatch(
        patch_id=f"patch-{record.topic_id}-{record.issue_type}",
        shape=record.shape,
        application=record.application,
        pattern=record.pattern,
        issue_type=record.issue_type,
        correction_target=record.correction_target,
        correction=dict(record.accepted_correction),
        scope=scope,  # type: ignore[arg-type]
        created_from_topic_id=record.topic_id,
        validation_result=record.post_regen_validation_status,
    )


def promotion_gate(patch: ProjectionPatch, checks: list[Any]) -> dict[str, Any]:
    """A patch ABOVE fixture scope must pass every supplied check — the original failing
    lesson, the shape goldens, and at least one unrelated same-shape fixture (§11.5).
    `checks` is a list of zero-arg callables returning bool."""
    if patch.scope == "fixture":
        return {"approved": True, "reason": "fixture scope needs no golden gate"}
    if len(checks) < 3:
        return {"approved": False, "reason": "promotion needs original + goldens + an unrelated fixture"}
    results = [bool(c()) for c in checks]
    return {"approved": all(results), "results": results}
