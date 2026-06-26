"""Worked-example trace pipeline — orchestration (WORKED_EXAMPLE_REASONING_SPEC.md v7, Phase 1).

Additive and flag-gated (`AZALEA_WORKED_EXAMPLE_TRACE_PIPELINE`, default OFF). Stages:
  0 select teaching instance  ·  1 produce trace (adapter-owned reference)  ·  2 verify (structural gate)
  ·  3 format cards (LLM writes PROSE ONLY; backend attaches state)  ·  4 fidelity  ·  4b prose fidelity.
Returns a legacy-shaped worked-example dict, or `None` to defer to the existing systems. The formatter is
injectable, so the whole pipeline is testable offline.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Callable, Optional

from .trace_adapters import ADAPTERS
from .trace_contract import (ContractTrace, structural_invariants, validate_fidelity, validate_prose)

_log = logging.getLogger(__name__)

FormatFn = Callable[[dict[str, str]], Optional[Any]]   # {"system","user"} -> {"cards":[...]} | None
_MAX_FORMAT_ATTEMPTS = max(1, int(os.getenv("AZALEA_TRACE_PIPELINE_MAX_FORMAT_ATTEMPTS", "2")))


def _enabled() -> bool:
    return os.getenv("AZALEA_WORKED_EXAMPLE_TRACE_PIPELINE", "").strip().lower() in {"1", "true", "on", "yes"}


# --- routing (explicit, non-fuzzy, §17) ----------------------------------------------------------

def route_adapter(topic: dict[str, Any]):
    """Phase 1: only an explicit binary-search topic enters the pipeline; everything else returns None."""
    slug = str(topic.get("slug") or topic.get("topic_family") or topic.get("family") or "").lower()
    title = str(topic.get("title") or topic.get("name") or "").lower()
    if "binary_search" in slug or "binary search" in title or "binary_search" in title:
        return ADAPTERS["binary_search"]
    return None


def _seed_for(topic: dict[str, Any]) -> int:
    key = str(topic.get("id") or topic.get("title") or topic.get("name") or "x")
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % 1_000_000


# --- Stage 0 + 1: select a teaching instance and build its trace --------------------------------

def select_instance(adapter, seed: int) -> Optional[ContractTrace]:
    for attempt, cand in enumerate(adapter.candidates(seed), start=1):
        trace = adapter.reference(cand, candidate_id=str(cand.get("_id", "")), attempt=attempt, seed=seed)
        if adapter.is_teaching_trace(trace):
            return trace
    return None


# --- Stage 3: prose-only formatter + backend state attach ---------------------------------------

def build_format_payload(trace: ContractTrace) -> dict[str, str]:
    steps = [{
        "id": s.id, "operation": s.operation, "inputs": s.inputs,
        "prior_state": s.prior_state, "state_after": s.state_after,
        "expected_visible_result": s.expected_visible_result, "facts": s.facts,
    } for s in trace.steps]
    system = (
        "You format an ALREADY-CORRECT, verified solution into learner-facing step cards. Write EXACTLY "
        "one card per step, in order. For each card write only: title, goal, reasoning, work (list), "
        "result. Use ONLY the step's facts — state the required_facts, use only allowed_values, never make "
        "a forbidden_claim. Describe the operation and resulting window accurately; do NOT invent or alter "
        "any value, and do NOT output any machine-state/JSON-state fields. "
        'Return ONLY JSON: {"cards":[{"title","goal","reasoning","work":[...],"result"}, ...]}'
    )
    user = f"PROBLEM: {trace.problem}\nSTEPS (verified, describe faithfully):\n{json.dumps(steps, default=str)}"
    return {"system": system, "user": user}


def _normalize_and_attach(raw: Any, trace: ContractTrace) -> Optional[list[dict[str, Any]]]:
    cards = raw.get("cards") if isinstance(raw, dict) else raw
    if not isinstance(cards, list) or len(cards) != len(trace.steps):   # v1: one card per step
        return None
    out: list[dict[str, Any]] = []
    for card, step in zip(cards, trace.steps):
        if not isinstance(card, dict):
            return None
        c: dict[str, Any] = {
            "title": str(card.get("title", "")).strip(),
            "goal": str(card.get("goal", "")).strip(),
            "reasoning": str(card.get("reasoning", "")).strip(),
            "work": [str(w) for w in (card.get("work") or [])],
            "result": str(card.get("result", "")).strip(),
        }
        # backend attaches the truth-bearing fields deterministically (§11) — the model never produced them
        c["trace_step_ids"] = [step.id]
        c["prior_state"] = step.prior_state
        c["result_state"] = step.state_after
        c["visual_state"] = step.visual_state
        c["visual_delta"] = step.visual_delta
        if not c["work"] or not c["result"]:
            return None
        out.append(c)
    return out


def _final_answer_text(trace: ContractTrace) -> str:
    k = (trace.final_answer or {}).get("found_index")
    return f"found at index {k}" if isinstance(k, int) and k >= 0 else "target is absent (index -1)"


def _to_solve_result(trace: ContractTrace, cards: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "problem": trace.problem,
        "cards": cards,
        "final_answer": _final_answer_text(trace),
        "expected_final_answer": _final_answer_text(trace),
        "generated_by": "trace_pipeline",
        "trace_first": True,
        "metadata": {"worked_example_source": "trace_pipeline", "provenance": trace.provenance},
    }


# --- top-level orchestration --------------------------------------------------------------------

def solve_trace_pipeline(topic: dict[str, Any], *, format_fn: Optional[FormatFn] = None,
                         seed: Optional[int] = None) -> Optional[dict[str, Any]]:
    adapter = route_adapter(topic)
    if adapter is None:
        return None
    fmt = format_fn or default_format_fn
    seed = seed if seed is not None else _seed_for(topic)

    trace = select_instance(adapter, seed)                         # Stage 0 + 1
    if trace is None:
        return None
    if structural_invariants(trace, adapter):                     # §5 gate (Stage 2 is ground truth here)
        _log.warning("trace_pipeline: %s trace failed structural gate", adapter.slug)
        return None

    for _ in range(_MAX_FORMAT_ATTEMPTS):                         # Stage 3 + 4 + 4b
        cards = _normalize_and_attach(fmt(build_format_payload(trace)), trace)
        if cards is None:
            continue
        fid = validate_fidelity(cards, trace, adapter)
        prose = validate_prose(cards, trace, adapter)
        if fid.ok and not prose:
            return _to_solve_result(trace, cards)
    return None                                                  # withhold — defer to existing systems


def default_format_fn(payload: dict[str, str]) -> Optional[Any]:
    """Production prose-only formatter call (mirrors examples.llm); None offline / on failure."""
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip().lower() == "dummy":
        return None
    try:
        from app.services.llm_client import OPENAI_MODEL, client, llm_call
        with llm_call("worked_example_trace_pipeline"):
            response = client.with_options(
                timeout=float(os.getenv("AZALEA_ENRICH_TIMEOUT_SECONDS", "60")),
                max_retries=max(0, int(os.getenv("AZALEA_ENRICH_MAX_RETRIES", "2"))),
            ).responses.create(
                model=OPENAI_MODEL,
                input=[{"role": "system", "content": payload.get("system", "")},
                       {"role": "user", "content": payload.get("user", "")}],
                text={"format": {"type": "json_object"}},
            )
        return json.loads(response.output_text)
    except Exception as exc:  # noqa: BLE001
        _log.warning("trace_pipeline format call failed: %s", exc)
        return None
