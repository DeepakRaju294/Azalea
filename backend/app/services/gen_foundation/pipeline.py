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

import os
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


def _executable_input(code: Any, example_input: Any) -> Any:
    """Adapt a graph example_input ({nodes, edges}) into executable {entry, args} matching the code's
    entry-function signature, relabeling node names to integer indices (most graph code uses
    list(range(n))). Returns the input unchanged when it's already executable or can't be adapted, so
    execution simply stays off in that case. Heuristic but safe — never raises."""
    if not isinstance(example_input, dict) or "entry" in example_input:
        return example_input
    if isinstance(example_input.get("graph"), dict):      # inputs arrive as {'graph': {nodes, edges}}
        example_input = example_input["graph"]
    edges = example_input.get("edges")
    if not isinstance(edges, list) or not edges:
        return example_input
    try:
        import ast as _ast
        funcs = [n for n in _ast.parse(str(code or "")).body if isinstance(n, _ast.FunctionDef)]
        if not funcs:
            return example_input
        entry = funcs[-1]
        params = [a.arg.lower() for a in entry.args.args]
        nodes = example_input.get("nodes") or sorted({str(e[0]) for e in edges} | {str(e[1]) for e in edges})
        idx = {str(n): i for i, n in enumerate(nodes)}
        n = len(nodes)
        int_edges = [[idx[str(e[0])], idx[str(e[1])], e[2]] for e in edges
                     if str(e[0]) in idx and str(e[1]) in idx and len(e) >= 3]
        adj = {i: [] for i in range(n)}
        for u, v, w in int_edges:
            adj[u].append((v, w))
            adj[v].append((u, w))
        args: list[Any] = []
        for p in params:
            if p in ("n", "v", "num_vertices", "vertices", "num_nodes", "nodes", "size", "count"):
                args.append(n)
            elif "edge" in p:
                args.append(int_edges)
            elif "graph" in p or "adj" in p:
                args.append(adj)
            else:
                args.append(int_edges)  # default to the edge list
        return {"entry": entry.name, "args": args}
    except Exception:  # noqa: BLE001
        return example_input


def _executor_final_answer(trace_events: Optional[list[dict[str, Any]]]) -> Any:
    """The executed function's return value (the last trace event carries it), or None."""
    if not trace_events:
        return None
    return trace_events[-1].get("return_value")


def _answers_agree(model_answer: Any, executor_return: Any) -> Optional[bool]:
    """Tolerant agreement between the model's free-text final answer and the executor's return value:
    compare their canonical numeric signatures (the model says 'MST weight 57', the executor returns
    (57, [...])). None when neither side has a checkable number — don't claim (dis)agreement we can't see."""
    import re

    from .completeness import _answer_signature

    sig = _answer_signature(model_answer)
    exec_numbers = re.findall(r"-?\d+(?:\.\d+)?", str(executor_return))
    if not sig.get("checkable") or not exec_numbers:
        return None
    if sig["kind"] == "scalar":
        return sig["result_value"] in exec_numbers
    return all(tok in exec_numbers for tok in sig["sequence"])  # sequence elements all present


def _state_agreement(cards: list[dict[str, Any]], trace_events: Optional[list[dict[str, Any]]]) -> Optional[float]:
    """Per-step state agreement (#4, the Layer 2 signal): fraction of cards whose result numbers all
    appear among the executor's recorded states. None when there's no trace or nothing numeric to compare."""
    import re
    if not trace_events:
        return None
    state_nums: set[str] = set()
    for ev in trace_events:
        for val in (ev.get("state") or {}).values():
            state_nums.update(re.findall(r"-?\d+", str(val)))
    if not state_nums:
        return None
    agree = total = 0
    for c in cards or []:
        nums = re.findall(r"-?\d+", str(c.get("result", "")))
        if not nums:
            continue
        total += 1
        if all(n in state_nums for n in nums):
            agree += 1
    return round(agree / total, 2) if total else None


def _execution_telemetry(
    code: Any, lang: str, example_input: Any,
    trace_events: Optional[list[dict[str, Any]]], model_answer: Any, executor_final: Any,
    *, topic_family: str = "", cards: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Shadow execution telemetry (Layer 1 + 3 + 4): did we execute, why not, does the executed answer
    agree with the model's claim, do the executed answer's invariants hold (Layer 3), and how well the
    model's per-step states match the trace (#4). Measured, not gated — post_generation_trace isn't trace_backed."""
    from .executor import execution_skip_reason
    from .property_checks import family_properties

    executed = trace_events is not None
    return {
        "attempted": bool(code),
        "executed": executed,
        "skip_reason": None if executed else (execution_skip_reason(str(code or ""), lang, example_input)
                                              if code else "no_code"),
        "executor_final_answer": executor_final,
        "final_answer_agreement": _answers_agree(model_answer, executor_final) if executed else None,
        "property_violations": (family_properties(topic_family, example_input, executor_final)
                                if executed else []),
        "state_agreement": _state_agreement(cards or [], trace_events),
    }


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
    # Evidence-based: the step that actually represents the final answer (not just ids[-1]). Falls back
    # to the last id only when the answer isn't deterministically checkable — the completeness gate in
    # validate_artifact is what fails a truly unreached answer.
    from .completeness import step_reaching_final
    reaching = step_reaching_final(cards, ids, artifact.get("final_answer"))
    artifact["projection_coverage"] = {
        "required_cases": required,
        "teaching_step_reaching_final": reaching or (ids[-1] if ids else None),
    }


def _enrich_for_validation(artifact: dict[str, Any], config: PrepassConfig) -> None:
    artifact.setdefault("category", config.example_category)
    artifact.setdefault("topic_family", config.topic_family)        # for the model-only property gate (#1)
    artifact.setdefault("topic_type", config.topic_type)            # telemetry slice dimension (#4)
    artifact.setdefault("example_input", config.example_input)
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
    #    Layer 1: we ALSO record execution telemetry (skip reason + model-vs-executor answer agreement)
    #    without gating — post_generation_trace is not `trace_backed`, so this is pure shadow measurement.
    recon_tele: dict[str, Any] = {}
    if config.trace_mode in ("post_generation_trace", "preexisting_trace"):  # both have code to execute
        code = artifact.get("code") or topic.get("code")
        lang = topic.get("code_language") or "python"
        example_input = artifact.get("example_input") or artifact.get("problem")
        # Adapt the graph input into executable {entry, args} matching the code's signature so the
        # executor can actually RUN it (the property gate keeps the {nodes, edges} form).
        exec_input = _executable_input(code, example_input)
        trace_events = executor(code, lang, exec_input) if code else None
        executor_final = _executor_final_answer(trace_events)
        recon = reconcile(
            artifact.get("cards") or [], trace_events,
            model_final_answer=artifact.get("final_answer"),
            executor_final_answer=executor_final,
            step_ids=artifact.get("step_ids"),
        )
        recon_tele = recon.telemetry()
        recon_tele["execution"] = _execution_telemetry(
            code, lang, exec_input, trace_events, artifact.get("final_answer"), executor_final,
            topic_family=config.topic_family, cards=artifact.get("cards"))
        if trace_events is not None:
            artifact["reconciliation"] = recon_tele
            artifact["trace_ranges"] = recon.attached_ranges
            # D (trace-first, AZALEA_TRACE_FIRST): replace the model's hand-simulated cards with cards
            # built from the REAL execution trace -- states recorded not invented, run to completion.
            if os.getenv("AZALEA_TRACE_FIRST", "") not in ("", "0"):
                from .trace_first import build_cards_from_trace
                tf = build_cards_from_trace(trace_events, code=str(code or ""))
                if tf.get("cards"):
                    from .trace_first import narrate_cards
                    # narration polish (#1): readable prose AROUND the verified states (falls back to
                    # the terse deterministic narration when offline — accuracy is never traded).
                    artifact["cards"] = narrate_cards(
                        tf["cards"], problem=str(artifact.get("problem") or ""))
                    artifact["final_answer"] = tf["final_answer"]
                    artifact["final_answer_struct"] = tf.get("final_answer_struct")
                    artifact["trace_first"] = True
                    _assign_ids(artifact)
                    _ensure_coverage(artifact)

    # 3b. Reference-first (correctness for algorithmic families WITHOUT an executable trace): when
    #     execution didn't yield trace-first cards — walkthroughs have no code; some code won't run —
    #     build the worked example from a TRUSTED reference run of the algorithm on the real input.
    #     Ground-truth-sourced like trace_first, so it carries the same trace_first flag (gate skip).
    if not artifact.get("trace_first") and os.getenv("AZALEA_TRACE_FIRST", "") not in ("", "0"):
        from .reference_first import build_reference_cards
        ref = build_reference_cards(config.topic_family, str(topic.get("title") or ""),
                                    config.example_input)
        if ref.get("cards"):
            from .trace_first import narrate_cards
            if ref.get("problem"):
                artifact["problem"] = ref["problem"]  # state the same graph the cards solve
            artifact["cards"] = narrate_cards(ref["cards"], problem=str(artifact.get("problem") or ""))
            artifact["final_answer"] = ref["final_answer"]
            artifact["final_answer_struct"] = ref.get("final_answer_struct")
            artifact["trace_first"] = True
            artifact["reference_backed"] = True
            _assign_ids(artifact)
            _ensure_coverage(artifact)

    # 4. Mandatory worked-example audit (§8) — patch-only, re-validate, reject-on-fail.
    audit_tele: dict[str, Any] = {}
    if run_audit:
        artifact, audit_tele, calls = _run_audit(artifact, auditor, calls)

    final_errors = validate_artifact(artifact)
    # Layer 1 gating: for families on the AZALEA_TRACE_BACKED_FAMILIES allowlist, a model trace that
    # DISAGREES with the executed run (or whose executed output violates its invariants) is a hard
    # failure -> withhold, not just shadow telemetry. Reliable families only (data-promoted). Skipped for
    # trace_first artifacts -- those are BUILT from the execution, so they're already correct.
    if not artifact.get("trace_first"):
        final_errors = final_errors + _execution_gate_errors(
            recon_tele.get("execution") or {}, config.topic_family)
    return RunResult(
        ok=not final_errors,
        artifact=artifact,
        model_calls=calls,
        validation_errors=final_errors,
        audit_telemetry=audit_tele,
        reconciliation_telemetry=recon_tele,
    )


def _execution_gate_errors(execution: dict[str, Any], topic_family: str) -> list[str]:
    """Hard-gate a family on the trace-backed allowlist when execution contradicts the model (Layer 1)."""
    import os
    allow = {f.strip().lower() for f in os.getenv("AZALEA_TRACE_BACKED_FAMILIES", "").split(",") if f.strip()}
    fam = (topic_family or "").lower()
    if not allow or not any(a in fam for a in allow) or not execution.get("executed"):
        return []
    errors: list[str] = []
    if execution.get("final_answer_agreement") is False:
        errors.append("execution gate: model's final answer disagrees with the executed result (§Layer1)")
    if execution.get("property_violations"):
        errors.append("execution gate: executed output violates its invariants: "
                      f"{execution['property_violations'][:2]}")
    return errors


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
