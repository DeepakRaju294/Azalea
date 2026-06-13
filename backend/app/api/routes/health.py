from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def health_check():
    return {"status": "ok"}

@router.get("/v2-metrics")
def v2_metrics():
    """Process-local V2 telemetry (visual pipeline + example ontology), so rollout
    decisions are measured: apply rate, fallback reasons, per-application counts,
    and the SS8.1 widening gates."""
    from app.services.examples.metrics import GLOBAL as EXAMPLE_METRICS
    from app.services.visual_v2.invariant_metrics import GLOBAL as INVARIANT_METRICS
    from app.services.visual_v2.metrics import GLOBAL as VISUAL_METRICS, widening_gates

    return {
        "example_ontology": EXAMPLE_METRICS.snapshot(),
        "visual_pipeline": VISUAL_METRICS.snapshot(),
        "widening_gates": widening_gates(VISUAL_METRICS),
        # PROJECTOR_SYSTEM_SPEC §14 — per-tier resolution, invariant failures,
        # inference outcomes, and empty-legacy fallbacks. Watch the T5 tail shrink.
        "projector": INVARIANT_METRICS.snapshot(),
    }
