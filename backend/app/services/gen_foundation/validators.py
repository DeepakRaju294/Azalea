"""Deterministic validators (spec §9, §9.1) — pure, prose-free.

Each validator returns ``list[str]`` (empty == valid), matching the repo's existing
validator convention. They check the authored artifact before render: card-field
contracts (§4.1), the state-delta -> resolved chain (§7), projection caps (§5.2), the
projection-coverage map (§9.1, mode-aware), and trace-confidence metadata (§6.3).

No LLM, no DB, no prose parsing.
"""
from __future__ import annotations

from typing import Any

from . import trace as trace_mod
from .cards import (
    BASE_REQUIRED_FIELDS,
    CODING_REQUIRED_FIELDS,
    is_coding_card,
)
from .state import (
    InvalidStateDeltaError,
    StateBounds,
    StateSchema,
    DEFAULT_BOUNDS,
    apply_delta,
    validate_delta_bounds,
    validate_state_bounds,
)

_VALID_RELEVANCE = {"stateful", "static", "none"}


# --- card field contracts (§4.1 / §4.2) ----------------------------------------

def validate_card(card: dict[str, Any]) -> list[str]:
    """Required fields present + state_relevance/state_delta consistency (§4.1).

    Coding cards must carry ``how`` (not ``reasoning``) and the code anchors (§4.2);
    base cards carry ``reasoning``. ``state_delta`` must be null unless
    ``state_relevance == "stateful"``. Crash-proof on arbitrary model JSON.
    """
    if not isinstance(card, dict):
        return ["card is not an object"]
    errors: list[str] = []
    coding = is_coding_card(card)
    required = CODING_REQUIRED_FIELDS if coding else BASE_REQUIRED_FIELDS
    for f in required:
        if card.get(f) in (None, "", [], {}):
            errors.append(f"card missing required field {f!r}")

    relevance = card.get("state_relevance")
    if relevance not in _VALID_RELEVANCE:
        errors.append(f"state_relevance {relevance!r} not in {sorted(_VALID_RELEVANCE)}")
    else:
        has_delta = card.get("state_delta") is not None
        if relevance == "stateful" and not has_delta:
            errors.append("state_relevance 'stateful' requires a non-null state_delta (§7.1)")
        if relevance in ("static", "none") and has_delta:
            errors.append(f"state_relevance {relevance!r} must have state_delta == null (§4.1)")

    if coding:
        if "reasoning" in card:
            errors.append("coding card must use 'how', not 'reasoning' (§4.2)")
        # code_refs are RECOMMENDED (a soft audit signal when missing, §8); only flag a
        # MALFORMED present value, never absence.
        refs = card.get("code_refs")
        if refs is not None and (
            not isinstance(refs, list)
            or not all(isinstance(r, int) and not isinstance(r, bool) and r > 0 for r in refs)
        ):
            errors.append("code_refs, when present, must be positive 1-based line numbers (§4.2)")
    else:
        if "how" in card:
            errors.append("base card must use 'reasoning', not 'how' (§4.1)")

    work = card.get("work")
    if isinstance(work, list) and len(work) > trace_mod.MAX_WORK_LINES_PER_CARD:
        errors.append(
            f"card has {len(work)} work lines > max {trace_mod.MAX_WORK_LINES_PER_CARD} (§5.2)"
        )
    return errors


# --- state-delta chain (§7) ----------------------------------------------------

def validate_state_chain(
    initial_resolved_state: dict[str, Any],
    cards: list[dict[str, Any]],
    schema: StateSchema,
    bounds: StateBounds = DEFAULT_BOUNDS,
) -> list[str]:
    """Each ``stateful`` card's delta must resolve and chain to the next (§7, §9).

    A failed delta is reported against its card and the chain stops there (a bad
    delta must not corrupt the rest of the chain, §7).
    """
    errors: list[str] = []
    current = dict(initial_resolved_state if isinstance(initial_resolved_state, dict) else {})
    errors.extend(f"initial_resolved_state: {e}" for e in validate_state_bounds(current, bounds))
    for idx, card in enumerate(cards):
        delta = card.get("state_delta") if isinstance(card, dict) else None
        if not isinstance(delta, dict):
            continue
        errors.extend(f"card {idx}: {e}" for e in validate_delta_bounds(delta, bounds))
        try:
            current = apply_delta(current, delta, schema)
        except InvalidStateDeltaError as exc:
            errors.append(f"card {idx}: state_delta does not resolve: {exc}")
            break
        errors.extend(f"card {idx} resolved_state: {e}" for e in validate_state_bounds(current, bounds))
    return errors


# --- projection caps (§5.2) ----------------------------------------------------

def validate_projection_caps(category: str, cards: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    result = trace_mod.check_card_count(category, len(cards))
    if not result.ok:
        errors.append(result.reason)
    for idx, card in enumerate(cards):
        work = card.get("work")
        if isinstance(work, list) and len(work) > trace_mod.MAX_WORK_LINES_PER_CARD:
            errors.append(f"card {idx}: {len(work)} work lines > max {trace_mod.MAX_WORK_LINES_PER_CARD}")
    return errors


def validate_trace_event_budget(
    span_event_count: int, compressed_approved: bool
) -> list[str]:
    """A teaching step references <= budget events (§5); larger needs approved compression."""
    budget = trace_mod.trace_event_budget(compressed_approved)
    if span_event_count > budget:
        kind = "compressed" if compressed_approved else "default"
        return [f"teaching step spans {span_event_count} events > {kind} budget {budget} (§5)"]
    return []


# --- projection coverage (§9.1), mode-aware ------------------------------------

def validate_projection_coverage(
    coverage: dict[str, Any],
    required_cases: list[str],
    step_ids: list[str],
    mode: str,
    *,
    step_trace_ranges: dict[str, trace_mod.TraceRange] | None = None,
    case_event_index: dict[str, int] | None = None,
    final_trace_event_index: int | None = None,
) -> list[str]:
    """Every required case maps to >=1 real step; final step reaches the terminal event (§9.1).

    ``post_generation_trace``/``model_only`` are checked at the *semantic* level only
    (case -> step membership), since no trace exists at authoring time; trace-backed
    proof (a step's ``trace_range`` actually containing the case's event) is required
    only for ``preexisting_trace``/``canonical`` and only when the extra maps are given.
    """
    if not isinstance(coverage, dict):
        return ["projection_coverage is not an object (§9.1)"]
    errors: list[str] = []
    cov = coverage.get("required_cases")
    if not isinstance(cov, dict):
        cov = {}
    step_id_set = set(step_ids)

    for case in required_cases:
        steps = cov.get(case)
        if not steps:
            errors.append(f"required case {case!r} is not covered by any teaching step (§9.1)")
            continue
        for sid in steps:
            if sid not in step_id_set:
                errors.append(f"case {case!r} maps to unknown step {sid!r}")

    trace_backed = mode in ("preexisting_trace", "canonical")
    if trace_backed and step_trace_ranges is not None and case_event_index is not None:
        for case in required_cases:
            event = case_event_index.get(case)
            if event is None:
                continue
            covering = cov.get(case) or []
            if not any(
                sid in step_trace_ranges
                and step_trace_ranges[sid]["start"] <= event <= step_trace_ranges[sid]["end"]
                for sid in covering
            ):
                errors.append(
                    f"case {case!r}: no covering step's trace_range contains its event {event} (§9.1)"
                )

    final_step = coverage.get("teaching_step_reaching_final")
    if final_step is None:
        errors.append("projection_coverage missing teaching_step_reaching_final (§9.1)")
    elif final_step not in step_id_set:
        errors.append(f"teaching_step_reaching_final {final_step!r} is not a real step")
    elif (
        trace_backed
        and step_trace_ranges is not None
        and final_trace_event_index is not None
        and final_step in step_trace_ranges
    ):
        tr = step_trace_ranges[final_step]
        if not (tr["start"] <= final_trace_event_index <= tr["end"]):
            errors.append("final teaching step's trace_range does not include the terminal event (§9.1)")
    return errors


# --- full before-render gate (§9) ---------------------------------------------

def validate_artifact(artifact: dict[str, Any]) -> list[str]:
    """The deterministic before-render gate (§9): schema, cards, state chain, caps,
    coverage, confidence, final answer + setup present.

    ``artifact`` shape (the worked-example portion the validators cover):
        {category, state_schema, initial_resolved_state, cards[], step_ids[],
         projection_coverage, confidence_meta, final_answer}
    """
    if not isinstance(artifact, dict):
        return ["artifact is not an object"]
    errors: list[str] = []
    cards = artifact.get("cards")
    if not isinstance(cards, list) or not cards:
        return ["artifact has no cards (or 'cards' is not a list)"]
    if not all(isinstance(c, dict) for c in cards):
        return ["every card must be an object"]

    category = artifact.get("category")
    if category:
        # HARD: never exceed the cap (oversize -> split the topic, §5.2/§7.2). Below the
        # minimum is a SOFT audit signal (count_at_extreme, §8), not a reason to drop a
        # complete-but-short example here.
        try:
            res = trace_mod.check_card_count(category, len(cards))
            ceiling = min(res.high, trace_mod.ABSOLUTE_CEILING)
            if len(cards) > ceiling:
                errors.append(f"{len(cards)} cards exceed cap {ceiling}; split the topic (§5.2/§7.2)")
        except ValueError:
            pass

    for idx, card in enumerate(cards):
        errors.extend(f"card {idx}: {e}" for e in validate_card(card))

    schema_name = artifact.get("state_schema")
    if schema_name:
        from .state import get_schema  # local import keeps the module dependency-light
        try:
            schema = get_schema(schema_name)
            errors.extend(
                validate_state_chain(artifact.get("initial_resolved_state") or {}, cards, schema)
            )
        except InvalidStateDeltaError as exc:
            errors.append(f"state_schema: {exc}")

    meta = artifact.get("confidence_meta")
    if meta is not None:
        errors.extend(validate_confidence_meta(meta))
    mode = meta.get("trace_mode", "model_only") if isinstance(meta, dict) else "model_only"

    coverage = artifact.get("projection_coverage")
    if coverage is not None:
        step_ids = artifact.get("step_ids") or [f"step_{i+1}" for i in range(len(cards))]
        required = sorted({
            str(rc) for card in cards for rc in (card.get("cases_covered") or [])
            if isinstance(card.get("cases_covered"), list)
        })
        errors.extend(validate_projection_coverage(coverage, required, step_ids, mode))

    if "final_answer" not in artifact or artifact.get("final_answer") in (None, ""):
        errors.append("artifact missing final_answer (§9)")
    else:
        # Layer 0 completeness gate: a checkable final answer must be REACHED by a rendered step,
        # closing the teaching_step_reaching_final tautology (works even in model_only mode).
        from .completeness import completeness_errors
        errors.extend(completeness_errors(artifact))
    if artifact.get("initial_resolved_state") is None and schema_name:
        errors.append("stateful artifact missing initial_resolved_state setup (§7/§9)")
    return errors


# --- trace-confidence metadata (§6.3) ------------------------------------------

def validate_confidence_meta(meta: dict[str, Any]) -> list[str]:
    if not isinstance(meta, dict):
        return ["confidence_meta is not an object (§6.3)"]
    errors: list[str] = []
    mode = meta.get("trace_mode")
    if mode not in ("post_generation_trace", "preexisting_trace", "canonical", "model_only"):
        errors.append(f"trace_mode {mode!r} invalid (§6.3)")
    if meta.get("trace_confidence") not in ("high", "medium", "low"):
        errors.append(f"trace_confidence {meta.get('trace_confidence')!r} invalid (§6.3)")
    if meta.get("trace_validation_status") not in ("passed", "partial", "unavailable"):
        errors.append(f"trace_validation_status {meta.get('trace_validation_status')!r} invalid (§6.3)")
    return errors
