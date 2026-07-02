"""The adapter/orchestration artifact chain — FIRST-CLASS artifacts, not ad-hoc dicts
(ADAPTER_AND_GENERATION_SYSTEM_SPEC §2.5–2.8).

The chain, upstream → downstream:

    LessonIntent            §2.5.1  WHY the example exists (orchestration-owned, upstream of the adapter)
        ↓
    (adapter runs the reference, verifies the trace)
        ↓
    AdapterOutput           §2.6    the SINGLE standardized return of an adapter — everything downstream
        ├─ TeachingProjection   §2.5.2  the interface: which transitions are surfaced, order, required/terminal
        ├─ TeachingObjectives   §2.7    adapter-owned QUALITY (what a GOOD example teaches), not just correctness
        ├─ step_band            §2.3    predicted teaching step count {min, target, max}
        └─ AdapterDiagnostics   §2.6.1  the why-this-output record (debugging, never learner-facing)

These are declarative dataclasses; the adapter base assembles them from a verified `ContractTrace`."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class LessonIntent:
    """§2.5.1 — WHY an example exists, owned by ORCHESTRATION upstream of the adapter. The adapter consumes it
    to choose a representative instance and objectives; it never invents intent."""
    concept: str
    learning_goal: str = ""
    audience_level: str = "intro"                       # intro | standard | advanced
    must_show: list[str] = field(default_factory=list)  # transitions the lesson wants surfaced
    constraints: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_topic(cls, topic: dict[str, Any]) -> "LessonIntent":
        get = topic.get if isinstance(topic, dict) else (lambda k, d=None: getattr(topic, k, d))
        return cls(
            concept=str(get("title", "") or get("concept", "") or ""),
            learning_goal=str(get("learning_goal", "") or ""),
            audience_level=str(get("audience_level", "") or "intro"),
        )


@dataclass(frozen=True)
class TeachingProjection:
    """§2.5.2 — the INTERFACE between execution and narration: the teaching-shaped view of the verified trace
    (which transitions are surfaced, in what order, which are required, which is terminal, and each one's step
    kind), independent of how it is finally rendered."""
    transition_ids: list[str]
    required_transition_ids: list[str]
    terminal_transition_id: str
    step_kinds: dict[str, str] = field(default_factory=dict)     # transition_id -> operation/step-kind
    label_convention: str = ""                                   # "letters" | "ints" | ""


@dataclass(frozen=True)
class TeachingCheckpoint:
    """§7.3 — a learner-facing checkpoint + its PROVENANCE back to the verified trace. A checkpoint may collapse
    several supporting semantic events into one card, but only if it names its complete `source_step_ids` range
    and the `state_before`/`state_after` bounding that range — so every card/frame is traceable:
    card/frame → checkpoint_id → source semantic steps → verified reference trace. Required-case + terminal
    events are always their own (or an included) checkpoint; they are never silently absorbed."""
    checkpoint_id: str
    source_step_ids: list[str]                          # the complete contiguous range this checkpoint covers
    visible_transition: str                             # the single transition the learner sees
    state_before_step_id: str                           # first source step's prior_state anchor
    state_after_step_id: str                            # last source step's state_after anchor
    source_step_start: str = ""                         # explicit range bounds (contiguity is mechanically
    source_step_end: str = ""                           # obvious — a gap can't hide inside an id LIST)
    required_cases_covered: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RawExecutionProvenance:
    """§7.0 — enough to REGENERATE the exact raw execution log on demand, so the raw layer stays auditable
    WITHOUT shipping it in the lesson payload or storing it forever for every generated lesson. The backend
    retains the full raw log only for fixture/pilot/failure/sampled-production runs; otherwise it keeps just
    this (adapter version + deterministic instance + digest) and replays to reproduce."""
    adapter_slug: str
    adapter_version: int
    instance_seed: int
    normalized_instance_hash: str = ""
    raw_log_digest: str = ""


@dataclass(frozen=True)
class TeachingObjectives:
    """§2.7 — adapter-owned QUALITY (not just correctness): what a GOOD example of this concept teaches — the
    decisions worth surfacing, the classic misconception to preempt, the intended pacing."""
    surfaces: list[str] = field(default_factory=list)
    preempts_misconception: str = ""
    ideal_pacing: str = ""


@dataclass(frozen=True)
class AdapterDiagnostics:
    """§2.6.1 — the why-this-output record: which instance, whether it was accepted, coverage of the required
    cases, structural validity. Debugging/audit only — never learner-facing."""
    adapter: str
    adapter_version: int
    seed: int
    candidate_id: str
    instance_accepted: bool
    rejected_candidates: int = 0
    required_cases: list[str] = field(default_factory=list)
    missing_required_cases: list[str] = field(default_factory=list)
    structural_ok: bool = True
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorkedExamplePayload:
    """§4.1 — what the BACKEND ships to the frontend. The verified TEXT cards are ALWAYS present; the compiled
    visual frames are optional. On a visual/render failure the backend deliberately sets `render_mode` to
    `text_only_verified` and supplies the reason — the frontend RENDERS, it never has to recover semantics from
    a crash. An invalid trace produces no payload at all (nothing ships)."""
    verified_text_cards: list[dict[str, Any]]
    compiled_visual_frames: Optional[list[dict[str, Any]]] = None
    render_mode: str = "visual"                         # visual | text_only_verified
    verification_level: str = "trace_verified"
    degradation_reason: Optional[str] = None            # None | visual_compile_failure | frontend_render_failure


@dataclass(frozen=True)
class WorkedExampleFailure:
    """§4.1 — the STRUCTURED result an invalid trace returns (never a bare `null`). The caller gets a reason it
    can branch on + telemetry, instead of having to guess why nothing shipped."""
    reason: str                                         # invalid_trace | prose_claim_violation | ...
    adapter_slug: str = ""
    retryable: bool = True
    telemetry_id: str = ""
    detail: str = ""


@dataclass(frozen=True)
class AdapterOutput:
    """§2.6 — the SINGLE standardized return of an adapter. Everything downstream consumes THIS (the verified
    trace + its projection + step band + objectives + diagnostics), instead of reaching into ad-hoc fields."""
    trace: Any                                          # the verified ContractTrace (executable truth)
    projection: TeachingProjection
    step_band: dict[str, int]                           # {min, target, max}
    objectives: TeachingObjectives
    diagnostics: AdapterDiagnostics
    verification_level: str = "trace_verified"
