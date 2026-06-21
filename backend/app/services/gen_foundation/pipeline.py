"""Shadow single-pass orchestration (spec §1, §9.2, §12 steps 2-4).

The operating model end-to-end, behind the shadow flag (renders nothing in production):

    pre-pass config (§2)
      -> first pass (ONE model call: complete cards + state + coverage)
      -> deterministic validation (§9)            [fail -> recovery §9.2]
      -> reconcile if post_generation_trace (§6.1) [executor stubbed -> model_only]
      -> mandatory worked-example audit (§8: patch-only, re-validate, reject-on-fail)
      -> final validation
      -> RunResult (artifact + telemetry)

All three model interactions (solver / auditor / repair) are injected, so the whole
pipeline is deterministic and offline in tests. Nothing here is wired into production.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from . import prompts
from .audit import PatchBudgetError, apply_patch
from .executor import ExecutorFn, run_trace
from .llm import ModelFn, default_auditor, default_repair, default_solver
from .normalize import normalize_artifact
from .prepass import PrepassConfig, build_prepass_config
from .reconcile import reconcile
from .validators import validate_artifact


@dataclass
class RunResult:
    ok: bool
    artifact: Optional[dict[str, Any]]
    model_calls: int = 0
    validation_errors: list[str] = field(default_factory=list)
    audit_telemetry: dict[str, Any] = field(default_factory=dict)
    reconciliation_telemetry: dict[str, Any] = field(default_factory=dict)
    degraded: bool = False
    note: str = ""


def _assign_ids(artifact: dict[str, Any]) -> None:
    cards = artifact.get("cards") or []
    ids: list[str] = []
    for i, card in enumerate(cards):
        card.setdefault("card_id", f"step_{i + 1}")
        ids.append(card["card_id"])
    artifact["step_ids"] = ids


def _ensure_coverage(artifact: dict[str, Any]) -> None:
    """Derive projection_coverage deterministically from the cards (§9.1) when the model
    didn't supply it — so step-id↔case mapping is backend-owned, never a model guess."""
    if isinstance(artifact.get("projection_coverage"), dict):
        return  # keep a well-formed model-supplied map; otherwise derive a clean one
    cards = artifact.get("cards") or []
    ids = artifact.get("step_ids") or [f"step_{i+1}" for i in range(len(cards))]
    required: dict[str, list[str]] = {}
    for sid, card in zip(ids, cards):
        for case in card.get("cases_covered") or []:
            required.setdefault(str(case), []).append(sid)
    artifact["projection_coverage"] = {
        "required_cases": required,
        "teaching_step_reaching_final": ids[-1] if ids else None,
    }


def _enrich_for_validation(artifact: dict[str, Any], config: PrepassConfig) -> None:
    artifact.setdefault("category", config.example_category)
    if config.state_schema:
        artifact.setdefault("state_schema", config.state_schema)
    artifact.setdefault(
        "confidence_meta",
        {
            "trace_mode": config.trace_mode,
            "trace_confidence": "low" if config.trace_mode in ("post_generation_trace", "model_only") else "high",
            "trace_validation_status": "unavailable" if config.trace_mode == "model_only" else "partial",
        },
    )
    _ensure_coverage(artifact)


def run_first_pass(
    topic: dict[str, Any],
    *,
    solver: ModelFn = default_solver,
    auditor: ModelFn = default_auditor,
    repair: ModelFn = default_repair,
    executor: ExecutorFn = run_trace,
    run_audit: bool = True,
) -> RunResult:
    config = build_prepass_config(topic)
    calls = 0

    # 1. First pass — one call produces the whole renderable artifact.
    artifact = solver(prompts.build_first_pass_payload(config, topic))
    calls += 1
    if not artifact:
        return RunResult(False, None, calls, ["first pass returned nothing"], note="solver_unavailable")
    normalize_artifact(artifact, config.state_schema)  # deterministic lossless fixes (§9.2 step 1)
    _assign_ids(artifact)                                # ids/coverage derived from cleaned cards
    _enrich_for_validation(artifact, config)

    # 2. Deterministic validation — on failure, enter recovery (§9.2), not normal flow.
    errors = validate_artifact(artifact)
    if errors:
        repaired = _recover(artifact, errors, config, repair)
        calls += 1
        if repaired is None:
            return RunResult(
                True, _degrade(artifact), calls, errors, degraded=True, note="degraded_after_failed_repair"
            )
        artifact = repaired
        errors = validate_artifact(artifact)
        if errors:
            return RunResult(True, _degrade(artifact), calls, errors, degraded=True, note="degraded_repair_invalid")

    # 3. Reconcile (post_generation_trace) — execute the generated code if enabled (§6/§6.1).
    #    The executor returns None when disabled/unsafe, so this stays model_only by default.
    recon_tele: dict[str, Any] = {}
    if config.trace_mode == "post_generation_trace":
        code = artifact.get("code") or topic.get("code")
        trace_events = (
            executor(code, topic.get("code_language") or "python",
                     artifact.get("example_input") or artifact.get("problem"))
            if code else None
        )
        recon = reconcile(
            artifact.get("cards") or [], trace_events,
            model_final_answer=artifact.get("final_answer"),
            step_ids=artifact.get("step_ids"),
        )
        recon_tele = recon.telemetry()
        if trace_events is not None:
            artifact["reconciliation"] = recon_tele
            artifact["trace_ranges"] = recon.attached_ranges

    # 4. Mandatory worked-example audit (§8) — patch-only, re-validate, reject-on-fail.
    audit_tele: dict[str, Any] = {}
    if run_audit:
        artifact, audit_tele, calls = _run_audit(artifact, auditor, calls)

    final_errors = validate_artifact(artifact)
    return RunResult(
        ok=not final_errors,
        artifact=artifact,
        model_calls=calls,
        validation_errors=final_errors,
        audit_telemetry=audit_tele,
        reconciliation_telemetry=recon_tele,
    )


def _run_audit(artifact: dict[str, Any], auditor: ModelFn, calls: int) -> tuple[dict, dict, int]:
    report = validate_artifact(artifact)  # clean by now, but the auditor sees the report contract
    patch = auditor(prompts.build_audit_payload(artifact, report))
    calls += 1
    if not patch:
        return artifact, {"audit_status": "pass_no_edits", "audit_trigger": "worked_example_required"}, calls
    try:
        patched_cards, tele = apply_patch(artifact.get("cards") or [], patch)
    except PatchBudgetError as exc:
        # Reject the whole patch set; ship the valid first-pass output (never a 3rd pass, §8).
        return artifact, {
            "audit_status": "pass_with_edits", "patches_proposed": len(patch.get("edits") or []),
            "patches_applied": 0, "patches_rejected": len(patch.get("edits") or []),
            "rejection_reason": str(exc),
        }, calls
    candidate = {**artifact, "cards": patched_cards}
    _assign_ids(candidate)
    if validate_artifact(candidate):
        # Patched artifact fails post-audit validation -> reject the patch, keep first pass (§8/§9).
        t = tele.as_dict()
        t.update(patches_applied=0, patches_rejected=t.get("patches_proposed", 0),
                 rejection_reason="patched artifact failed post-audit validation")
        return artifact, t, calls
    return candidate, tele.as_dict(), calls


def _recover(
    artifact: dict[str, Any], errors: list[str], config: PrepassConfig, repair: ModelFn
) -> Optional[dict[str, Any]]:
    """First-pass failure recovery (§9.2): one targeted repair call (deterministic
    normalization would precede it in production; kept minimal here)."""
    repaired = repair(prompts.build_repair_payload(artifact, errors))
    # Only accept a repair that preserves the cards — a card-less "repair" must not clobber
    # a card-bearing first pass (we'd rather degrade with the original, flagged, §9.2).
    if not isinstance(repaired, dict) or not isinstance(repaired.get("cards"), list) or not repaired["cards"]:
        return None
    normalize_artifact(repaired, config.state_schema)
    _assign_ids(repaired)
    _enrich_for_validation(repaired, config)
    return repaired


def _degrade(artifact: dict[str, Any]) -> dict[str, Any]:
    """Ship a safe degraded lesson (§9.2): flag the worked example as unavailable rather
    than silently shipping an invalid one."""
    return {**artifact, "worked_example_status": "withheld_invalid"}
