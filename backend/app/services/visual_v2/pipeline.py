"""V2 visual pipeline orchestrator (VISUAL_SYSTEM_SPEC §6).

For a REGISTERED algorithm: validate example → simulate (authoritative trace) →
fold → compile → validate model → pedagogical gate. Deterministic; no LLM. The
unregistered/llm-authored path and prose generation arrive in Slice 4.
"""
from __future__ import annotations

from typing import Any

from .compilers import code_execution as _code_compiler
from .compilers import formula_symbolic as _formula_compiler
from .compilers import grid_matrix as _grid_compiler
from .compilers import indexed_sequence as _seq_compiler
from .compilers import node_link as _node_compiler
from .compilers.concept import COMPILERS as _CONCEPT_COMPILERS
from .delta_fold import DeltaFoldEngine
from .example_invariants import validate_example
from .profiles import delta_vocabulary, profile_for_mode
from .schemas import CanonicalExample
from .simulators.registry import get_simulator, is_registered
from .telemetry import debug_payload
from .validators import (
    pedagogical_check,
    validate_model,
    validate_trace,
    validate_visual_invariants,
)


def _valid_ids_for(example: CanonicalExample, mode: str) -> set:
    base = example.get("base_structure") or {}
    if mode == "graph_network":
        return set(base.get("nodes") or [])
    if mode == "binary_search_range":
        return set(range(len(base.get("array") or [])))
    return set()  # dp_table / code_execution — cell/line ops aren't validated as element ids


def _compile_for_mode(mode, *, trace, frames, example, profile, model_id):
    """Dispatch to the mode's compiler. None if no compiler is wired for the mode."""
    base = example.get("base_structure") or {}
    if mode == "graph_network":
        return _node_compiler.compile_from_trace(
            trace=trace, frames=frames, base_structure=example["base_structure"],
            profile=profile, mode=mode, model_id=model_id,
        )
    if mode == "binary_search_range":
        return _seq_compiler.compile_from_trace(
            trace=trace, frames=frames, array=list(base.get("array") or []),
            profile=profile, mode=mode, model_id=model_id,
        )
    if mode == "dp_table":
        return _grid_compiler.compile_from_trace(
            trace=trace, frames=frames, rows=int(base.get("rows") or 0), cols=int(base.get("cols") or 0),
            profile=profile, mode=mode, model_id=model_id,
        )
    if mode == "code_execution":
        return _code_compiler.compile_from_trace(
            trace=trace, frames=frames, code=str(example.get("code") or ""),
            profile=profile, model_id=model_id,
        )
    if mode == "formula_substitution":
        formula = str((trace.get("initial_state") or {}).get("formula") or base.get("formula") or "")
        return _formula_compiler.compile_from_trace(
            trace=trace, frames=frames, formula=formula,
            symbols=dict(example.get("input") or {}),
            profile=profile, mode=mode, model_id=model_id,
        )
    if mode in _CONCEPT_COMPILERS:
        return _CONCEPT_COMPILERS[mode](
            trace=trace, frames=frames, example=example, profile=profile, mode=mode, model_id=model_id,
        )
    return None


def _run_graph_projection(
    example: CanonicalExample,
    *,
    model_id: str,
    topic_id: str = "",
    lesson_id: str = "",
    card_id: str = "",
    projection_source: str = "authored",
    inference_version: str | None = None,
) -> dict[str, Any]:
    """The computed node_link route from code + a GraphProjection (§7). Runs the
    universal tracer, validates + applies the projection, folds/compiles to a
    node_link model, gates it with the full guardrail, and stamps T2/T3 provenance.
    Self-contained so it never needs a registered simulator."""
    from .projectors.node_link import GraphProjection, project_node_link, validate_projection
    from .provenance import make_provenance, stamp
    from .simulators.code_tracer import trace_execution

    def fail(stage: str, errors: list[str]) -> dict[str, Any]:
        return {"status": "failed", "stage": stage, "errors": errors, "model": None,
                "render_steps": [], "trace": None}

    from .projectors.node_link import infer_projection
    from .provenance import INFERENCE_VERSION

    base = dict(example.get("base_structure") or {})
    code = str(example.get("code") or "")
    entry = str(example.get("entry_function") or "")
    proj_dict = dict(example.get("graph_projection") or {})
    if not (code and entry and base.get("nodes")):
        return fail("graph_projection_inputs", ["missing code / entry_function / nodes"])

    profile = profile_for_mode("graph_network")
    input_spec = dict(example.get("input") or {})
    try:
        steps, _ = trace_execution(code, entry, input_spec)
    except Exception as exc:  # noqa: BLE001
        return fail("tracer_failed", [f"{type(exc).__name__}: {exc}"])

    # Authored contract (T2) if supplied; else INFER one from the trace (T3, §8).
    confidence_band: str | None = None
    if proj_dict:
        try:
            projection = GraphProjection(**proj_dict)
        except TypeError as exc:
            return fail("graph_projection_contract", [f"bad contract: {exc}"])
        source, inf_version = (projection_source, inference_version)
    else:
        from .invariant_metrics import GLOBAL as INV
        candidate = infer_projection(steps, base)
        if candidate is None:
            INV.record_inference(accepted=False)
            return fail("ProjectionInference", ["could not infer a valid projection from the trace"])
        INV.record_inference(accepted=True, confidence_band=candidate.confidence_band)
        projection = candidate.projection
        confidence_band = candidate.confidence_band
        source, inf_version = ("inferred", INFERENCE_VERSION)

    proj_errors = validate_projection(steps, base, projection)
    if proj_errors:
        return fail("ProjectionValidator", proj_errors)

    result = project_node_link(steps, base, projection, projection_source=source, inference_version=inf_version)
    if not result.deltas:
        return fail("ProjectionValidator", ["projection produced no steps"])

    valid_ids = {str(n) for n in base.get("nodes") or []}
    start = input_spec.get("start")
    # A priority-queue frontier (Dijkstra/Prim) reads differently from a plain queue.
    frontier_kind = "priority_queue" if (projection.frontier_priority_key or projection.frontier_node_key) else "queue"
    frames = DeltaFoldEngine().fold(
        result.initial_state(start, frontier_kind=frontier_kind), result.deltas, valid_ids,
        delta_vocabulary("graph_network"),
    )
    model, render_steps = _node_compiler.compile_from_trace(
        trace={"steps": result.deltas}, frames=frames, base_structure=base,
        profile=profile, mode="graph_network", model_id=model_id,
    )

    model_errors = validate_model(model)
    if model_errors:
        return fail("VisualModelValidator", model_errors)
    invariant_errors = validate_visual_invariants(model, example.get("expected_output"))
    if invariant_errors:
        from .invariant_metrics import GLOBAL as INV
        for err in invariant_errors:
            INV.record_invariant_failure(err.split(":", 1)[0])
        return fail("VisualInvariantValidator", invariant_errors)
    pedagogy = pedagogical_check(model, profile)
    if pedagogy["verdict"] == "reject":
        return fail("PedagogicalVisualValidator", [m for _, m in pedagogy["issues"]])

    state_source = {
        "inferred": "inferred_projection",
        "llm_authored": "llm_validated_projection",
    }.get(source, "authored_projection")
    stamp(model, make_provenance(
        state_source,
        projection_source=result.projection_source,
        projection_contract=result.projection_contract,
        projector_version=result.projector_version,
        inference_version=result.inference_version,
        confidence_band=confidence_band,
        code_source="inline_fixture",
        validation_summary={
            "pipeline": "validated", "frames": len(frames),
            "raw_steps": result.raw_step_count, "emitted_steps": result.emitted_step_count,
            "warnings": result.warnings,
            "invariants_passed": ["node_link_state", "INV-RENDER", "INV-COMPLETE"],
        },
    ))
    from .invariant_metrics import GLOBAL as INV
    INV.record_tier(model["provenance"]["tier"])

    return {
        "status": "validated", "stage": "validated", "errors": [],
        "model": model, "render_steps": render_steps,
        "trace": {"steps": result.deltas}, "frames": frames,
        "projection": result, "pedagogy": pedagogy,
    }


def run_for_registered(
    example: CanonicalExample,
    *,
    model_id: str = "v2_model",
    topic_id: str = "",
    lesson_id: str = "",
    card_id: str = "",
) -> dict[str, Any]:
    """Run the deterministic pipeline. Returns status + model + render_steps + report."""
    mode = str(example.get("mode") or "")
    algorithm = example.get("algorithm")

    # T2/T3 projected route (PROJECTOR_SYSTEM_SPEC §7): code + a GraphProjection,
    # no registered simulator. Diverges before the is_registered gate.
    if mode == "graph_projection":
        return _run_graph_projection(
            example, model_id=model_id, topic_id=topic_id, lesson_id=lesson_id, card_id=card_id
        )

    profile = profile_for_mode(mode)

    def fail(stage: str, errors: list[str], trace: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "status": "failed",
            "stage": stage,
            "errors": errors,
            "model": None,
            "render_steps": [],
            "trace": trace,
            "debug": debug_payload(
                example=example, trace=trace, visual_status="failed", failed_validator=stage,
                topic_id=topic_id, lesson_id=lesson_id, card_id=card_id,
            ),
        }

    if profile is None:
        return fail("no_profile", [f"no profile for mode {mode!r}"])
    if not is_registered(algorithm):
        return fail("not_registered", [f"algorithm {algorithm!r} is not registered (use the LLM path)"])

    # Pre-trace: validate the example before tracing (§6.0).
    example_errors = validate_example(example)
    if example_errors:
        return fail("ExampleInvariantValidator", example_errors)

    # Trace: the simulator owns the delta timeline (§5.3.1).
    trace = get_simulator(algorithm)(example)
    valid_ids = _valid_ids_for(example, mode)

    trace_errors = validate_trace(trace, valid_ids, mode)
    if trace_errors:
        return fail("TraceValidator", trace_errors, trace)

    # Fold + compile (deterministic) — dispatched per mode (§6).
    frames = DeltaFoldEngine().fold(trace["initial_state"], trace["steps"], valid_ids, delta_vocabulary(mode))

    compiled = _compile_for_mode(mode, trace=trace, frames=frames, example=example, profile=profile, model_id=model_id)
    if compiled is None:
        return fail("no_compiler", [f"no compiler wired for mode {mode!r}"], trace)
    model, render_steps = compiled

    model_errors = validate_model(model)
    if model_errors:
        return fail("VisualModelValidator", model_errors, trace)

    pedagogy = pedagogical_check(model, profile)
    if pedagogy["verdict"] == "reject":
        return fail("PedagogicalVisualValidator", [m for _, m in pedagogy["issues"]], trace)

    # Guardrail (§6.1 + INV-RENDER + INV-COMPLETE): a node_link worked example can
    # never render with empty/static/malformed/truncated state. Other shapes no-op.
    invariant_errors = validate_visual_invariants(model, example.get("expected_output"))
    if invariant_errors:
        from .invariant_metrics import GLOBAL as INV
        for err in invariant_errors:
            INV.record_invariant_failure(err.split(":", 1)[0])
        return fail("VisualInvariantValidator", invariant_errors, trace)

    # Provenance (§10.1): the registered-simulator pipeline is the T1 computed source.
    # (The T2/T3 projection routes stamp authored_/inferred_projection in step 5+.)
    from .provenance import make_provenance, stamp
    stamp(model, make_provenance(
        "registered_simulator",
        validation_summary={
            "pipeline": "validated",
            "frames": len(frames),
            "pedagogy_verdict": pedagogy.get("verdict"),
            "invariants_passed": ["node_link_state", "INV-RENDER", "INV-COMPLETE"],
        },
    ))
    from .invariant_metrics import GLOBAL as INV
    INV.record_tier(model["provenance"]["tier"])

    return {
        "status": "validated",
        "stage": "validated",
        "errors": [],
        "model": model,
        "render_steps": render_steps,
        "trace": trace,
        "frames": frames,
        "pedagogy": pedagogy,
        "debug": debug_payload(
            example=example, trace=trace, visual_status="validated",
            topic_id=topic_id, lesson_id=lesson_id, card_id=card_id,
        ),
    }
