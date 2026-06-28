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
from .trace_contract import (ContractTrace, hard_prose_violations, structural_invariants,
                             validate_fidelity, validate_prose)

_log = logging.getLogger(__name__)

FormatFn = Callable[[dict[str, str]], Optional[Any]]   # {"system","user"} -> {"cards":[...]} | None
_MAX_FORMAT_ATTEMPTS = max(1, int(os.getenv("AZALEA_TRACE_PIPELINE_MAX_FORMAT_ATTEMPTS", "2")))


def _enabled() -> bool:
    return os.getenv("AZALEA_WORKED_EXAMPLE_TRACE_PIPELINE", "").strip().lower() in {"1", "true", "on", "yes"}


# --- routing (explicit, non-fuzzy, §17) ----------------------------------------------------------

def route_adapter(topic: dict[str, Any]):
    """Explicit (non-fuzzy) routing: a topic enters the pipeline only when its slug/metadata or a tight
    title alias names one of the supported algorithms. Anything else (e.g. a broad 'graph algorithms'
    topic) returns None and defers to the existing systems.

    C2 Part 1 (no canonical code): coding-implementation topics now ALSO route to the adapter — they get the
    same VERIFIED conceptual trace as the walkthrough (correct), without per-step code-line highlighting
    (canonical code is Part 2, deferred). The code-walkthrough card still shows the code separately."""
    slug = str(topic.get("slug") or topic.get("topic_family") or topic.get("family") or "").lower()
    text = (slug + " " + str(topic.get("title") or topic.get("name") or "")).lower()
    if "binary_search" in slug or "binary search" in text:
        return ADAPTERS["binary_search"]
    if "kruskal" in text:
        return ADAPTERS["kruskal"]
    if "prim" in text:
        return ADAPTERS["prim"]
    if "merge sort" in text or "merge_sort" in text:
        return ADAPTERS["merge_sort"]
    if "breadth-first" in text or "breadth first" in text or " bfs" in f" {text}":
        return ADAPTERS["bfs"]
    if "depth-first" in text or "depth first" in text or " dfs" in f" {text}":
        return ADAPTERS["dfs_iter"]
    if "order of operations" in text or "evaluate expression" in text or "arithmetic expression" in text:
        return ADAPTERS["arithmetic_eval"]
    if "dijkstra" in text or "shortest path" in text or "shortest-path" in text:
        return ADAPTERS["dijkstra"]
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

# Coding worked-example field contract (carried over from solver._CODING_CARDS_SYSTEM, §ADAPTER): the
# trace is the verified source of truth; the formatter's only job is to MAP each verified step onto the
# code the learner is shown — Work = the literal code line(s), Result = the runtime state. This is what
# makes the per-bullet active-line highlight precise (each Work bullet anchors to one source line).
_CODING_FORMAT_SYSTEM = (
    "You format an ALREADY-CORRECT, verified execution trace into CODE-ANCHORED worked-example cards — "
    "EXACTLY one card per step, in order. The trace is the source of truth: use ONLY each step's "
    "operation/decision/facts; never invent or alter a value, never add, remove, or reorder steps.\n"
    "FIELDS per card:\n"
    "- goal: leave EMPTY — the card title already states the structural step (do not restate it).\n"
    "- reasoning: WHICH code construct implements it and why (the condition / loop / call / branch).\n"
    "- work: REQUIRED list. Each line BEGINS with the LITERAL code line from the CODE below, quoted "
    "VERBATIM with its variable names (e.g. `if ds.find(u) != ds.find(v):` then `mst.append((u, v, w))`), "
    "THEN — REQUIRED on every line — ` // <plain-English of what this line does NOW, naming the concrete "
    "value(s) from this step>`. Do NOT substitute the values into the code itself — put them in the // "
    "part. A line with no ` // ` is INVALID. List the lines this step executes, in source order.\n"
    "- result: the concrete RUNTIME state after this step (variables/structures mutated, branch taken).\n"
    "- code_lines: for EACH work action, the 1-based line number(s) in the CODE it maps to, as a list of "
    "lists (e.g. [[18],[19],[20]]); use [] for a pure-narration line. One entry per work line.\n"
    'Return ONLY JSON: {"cards":[{"title","goal","reasoning","work":[...],"result","code_lines":[...]}, ...]}'
)


def _retry_feedback(reason: str, detail: list[str], n_steps: int) -> str:
    """Targeted feedback for the NEXT format attempt (the dominant withholds — prose_fail/count_mismatch
    — were retried with the SAME payload, so they never improved). Evidence from M7."""
    if reason == "count_mismatch":
        return (f"Your previous output had the WRONG number of cards. Produce EXACTLY {n_steps} cards — "
                "ONE per verified step, in order. Do not split a step into several cards or merge steps.")
    if reason == "prose_fail":
        return ("Your previous output failed these checks: " + "; ".join(detail) + ". "
                "Fix each: every step must NAME the exact entity/values it acts on (e.g. the edge and its "
                "weight) AND explicitly state its decision in words (accept/add vs skip/reject-as-cycle).")
    return ""


# §1a (STUDY_PATH_CONTENT_SPEC) — the instructional grammar the formatter was flying blind without.
_STAGE_GRAMMAR_RULE = (
    "\nINSTRUCTIONAL GRAMMAR — use STAGE_GUIDANCE below (keyed by each step's `operation`):\n"
    "- Lead the `reasoning` with the stage's `teaching_focus` (the ONE thing the step teaches).\n"
    "- In `work`: surface the `required` operation as the step's single DECISION line; combine ALL "
    "`aggregated_supporting` operations into ONE summary line; OMIT `internal` operations unless the "
    "teaching_focus needs them. Aim for ~1-2 work lines — surface the decision, do not narrate machinery."
)


def _stage_guidance(adapter: Any) -> dict[str, Any]:
    """Per-operation instructional grammar from the adapter's example_spec: teaching_focus + the role of
    each contained operation (required / aggregated_supporting / internal). Empty if not declared."""
    spec = getattr(adapter, "example_spec", None)
    stages = getattr(spec, "stages", None) if spec is not None else None
    if not stages:
        return {}
    out: dict[str, Any] = {}
    for sid, st in stages.items():
        contains = getattr(st, "contains", None) or {}
        out[sid] = {
            "teaching_focus": getattr(st, "teaching_focus", "") or "",
            "required": [op for op, r in contains.items() if r == "required"],
            "aggregated_supporting": [op for op, r in contains.items() if r == "aggregated_supporting"],
            "internal": [op for op, r in contains.items() if r == "internal"],
        }
    return out


def build_format_payload(trace: ContractTrace, code: Optional[str] = None,
                         feedback: str = "", adapter: Any = None) -> dict[str, str]:
    steps = [{
        "id": s.id, "operation": s.operation, "inputs": s.inputs,
        "prior_state": s.prior_state, "state_after": s.state_after,
        "expected_visible_result": s.expected_visible_result, "facts": s.facts,
    } for s in trace.steps]
    fb = f"\n\nFIX FROM THE PREVIOUS ATTEMPT (address ALL of this):\n{feedback}" if feedback else ""
    guidance = _stage_guidance(adapter)
    g_rule = _STAGE_GRAMMAR_RULE if guidance else ""
    g_text = f"\n\nSTAGE_GUIDANCE (per step.operation):\n{json.dumps(guidance, default=str)}" if guidance else ""
    if code:                                                   # coding topic — anchor Work to the shown code
        numbered = "\n".join(f"{i:>3}  {ln}" for i, ln in enumerate(code.split("\n"), start=1))
        user = (f"PROBLEM: {trace.problem}\n\nCODE (1-based line numbers — anchor every work line and "
                f"code_lines entry to THESE lines):\n{numbered}{g_text}{fb}\n\nSTEPS (verified, describe "
                f"faithfully):\n{json.dumps(steps, default=str)}")
        return {"system": _CODING_FORMAT_SYSTEM + g_rule, "user": user}
    system = (
        "You format an ALREADY-CORRECT, verified solution into learner-facing step cards. Write EXACTLY "
        "one card per step, in order (do NOT split or merge steps). For each card write only: title, goal, "
        "reasoning, work (list), result. Use ONLY the step's facts — state EVERY required_fact, use only "
        "allowed_values, never make a forbidden_claim. "
        "EACH card MUST (a) NAME the exact entity and values the step acts on — e.g. the edge and its weight "
        "like '(A,C,13)' — and (b) STATE the decision in words (e.g. 'add it to the MST' / 'accept', or "
        "'skip it — it would form a cycle'). A step that omits the entity/values or the decision is INVALID. "
        "On the step that COMPLETES the structure (the final accept that finishes the spanning tree / the "
        "result), say so explicitly in the result (e.g. 'all vertices connected — the MST is complete'). "
        "Do NOT invent or alter any value, and do NOT output any machine-state/JSON-state fields. "
        'Return ONLY JSON: {"cards":[{"title","goal","reasoning","work":[...],"result"}, ...]}'
    ) + g_rule
    user = (f"PROBLEM: {trace.problem}{g_text}{fb}\nSTEPS (verified, describe faithfully):\n"
            f"{json.dumps(steps, default=str)}")
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
        if isinstance(card.get("code_lines"), list):           # coding path: per-action anchors (validated downstream)
            c["code_lines"] = card["code_lines"]
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
    fa = trace.final_answer
    if isinstance(fa, dict):
        if "found_index" in fa:
            k = fa["found_index"]
            return f"found at index {k}" if isinstance(k, int) and k >= 0 else "target is absent (index -1)"
        if "visit_order" in fa:
            return "visit order: " + ", ".join(map(str, fa["visit_order"]))
        if "mst_edges" in fa:
            return f"MST edges {fa['mst_edges']} (total weight {fa.get('total_weight')})"
        if "sorted" in fa:
            return f"sorted: {fa['sorted']}"
        if "value" in fa:
            return f"= {fa['value']}"
        if "dist" in fa:
            return "shortest distances: " + ", ".join(f"{k}:{v}" for k, v in fa["dist"].items())
    return str(fa)


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

def _reason_extract_enabled() -> bool:
    return os.getenv("AZALEA_WORKED_EXAMPLE_REASON_EXTRACT", "").strip().lower() in {"1", "true", "on", "yes"}


def solve_trace_pipeline(topic: dict[str, Any], *, format_fn: Optional[FormatFn] = None,
                         reason_fn: Optional[FormatFn] = None, extract_fn: Optional[FormatFn] = None,
                         critic_fn: Optional[FormatFn] = None, seed: Optional[int] = None,
                         code: Optional[str] = None
                         ) -> Optional[dict[str, Any]]:
    from . import generation_report as _gr
    fmt = format_fn or default_format_fn
    title = str(topic.get("title") or topic.get("name") or topic.get("id") or "?")
    ctype = str(topic.get("topic_type") or topic.get("course_type") or "?")
    adapter = route_adapter(topic)
    if adapter is not None:                                        # deterministic path (HARD guarantee)
        _log.info("WORKED-EXAMPLE ADAPTER: topic=%r type=%s -> adapter=%s (verified trace path)",
                  title, ctype, adapter.slug)
        _gr.we(adapter=adapter.slug, tp_attempted=True)
        seed = seed if seed is not None else _seed_for(topic)
        trace = select_instance(adapter, seed)                     # Stage 0 + 1
        if trace is None or structural_invariants(trace, adapter):  # §5 gate (Stage 2 is ground truth)
            _log.warning("WORKED-EXAMPLE ADAPTER: topic=%r adapter=%s -> WITHHELD (no teaching trace) — defer",
                         title, adapter.slug)
            _gr.we(tp_shipped=False, tp_reason="no_teaching_trace")
            return None
        result = _format_validate_ship(topic, trace, adapter, fmt, code=code)
        _log.info("WORKED-EXAMPLE ADAPTER: topic=%r adapter=%s -> %s",
                  title, adapter.slug, "SHIPPED (verified)" if result is not None else "withheld (defer)")
        return result
    _guard = " [BLOCKED by coding_implementation guard - needs C2]" if ctype == "coding_implementation" else ""
    _log.info("WORKED-EXAMPLE ADAPTER: topic=%r type=%s -> NO adapter%s (deferring to gen_foundation/legacy)",
              title, ctype, _guard)
    _gr.we(adapter=None, tp_attempted=False, tp_reason="no_adapter")
    if _reason_extract_enabled():                                  # non-deterministic path (SOFT) — opt-in
        return _solve_via_reason_extract(topic, fmt, reason_fn, extract_fn, critic_fn)
    return None                                                    # defer to existing systems


def _format_validate_ship(topic, trace, adapter, fmt, *, code: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Stage 3 + 4 + 4b (WORKED_EXAMPLE_REASONING_SPEC v8 §13): prose-only format, backend state-attach,
    then SPLIT BY FAILURE SOURCE — a fidelity failure is a backend/trace defect a formatter retry cannot
    fix (withhold + log immediately); only a HARD prose contradiction is worth re-formatting; missing/soft
    prose is advisory in Phase 1 (logged, not blocking). `validate_visual_state=False` in Phase 1."""
    from . import generation_report as _gr
    last_raw, last_cards, last_prose = None, None, None
    reason, detail, attempts, feedback = "formatter_none", [], 0, ""
    n_steps = len(trace.steps)
    for _ in range(_MAX_FORMAT_ATTEMPTS):
        attempts += 1
        raw = fmt(build_format_payload(trace, code=code, feedback=feedback, adapter=adapter))   # §1a + M7 retry
        cards = _normalize_and_attach(raw, trace)
        last_raw, last_cards = raw, cards
        if cards is None:                                          # formatter produced nothing usable -> retry
            n_raw = len(raw["cards"]) if isinstance(raw, dict) and isinstance(raw.get("cards"), list) else None
            reason = "count_mismatch" if (n_raw is not None and n_raw != n_steps) else "formatter_none"
            detail = [f"formatter cards={n_raw} vs verified steps={n_steps}"] if reason == "count_mismatch" else ["formatter returned no usable cards"]
            feedback = _retry_feedback(reason, detail, n_steps)
            continue
        fid = validate_fidelity(cards, trace, adapter, validate_visual_state=False)
        if not fid.ok:                                             # BACKEND/TRACE defect — retry can't fix it
            _log.error("trace_pipeline: %s fidelity failure %r (backend/trace defect) — withholding",
                       getattr(adapter, "slug", "?"), fid.code)
            _retain_debug(topic, trace, raw, cards, fid, [], shipped=False)
            _gr.we(tp_shipped=False, tp_reason="fidelity_fail", tp_detail=[str(fid.code)],
                   verified_steps=n_steps, formatter_cards=len(cards), tp_attempts=attempts)
            return None
        prose = validate_prose(cards, trace, adapter, code_anchored=bool(code))
        last_prose = prose
        hard = hard_prose_violations(prose)
        advisory = [v for v in prose if v.severity != "hard"]
        if advisory:
            _log.info("trace_pipeline: %s advisory prose (missing/soft) x%d", adapter.slug, len(advisory))
        if not hard:                                               # contradictions are the only blocker
            _retain_debug(topic, trace, raw, cards, fid, prose, shipped=True)
            _gr.we(tp_shipped=True, tp_reason="shipped", verified_steps=n_steps,
                   formatter_cards=len(cards), tp_attempts=attempts)
            return _to_solve_result(trace, cards)
        reason = "prose_fail"                                      # a hard contradiction -> re-format
        detail = [f"{v.code} {v.detail} ({v.trace_step_id})" for v in hard][:6]
        feedback = _retry_feedback(reason, detail, n_steps)        # targeted: tell it exactly what to fix
    _retain_debug(topic, trace, last_raw, last_cards, None, last_prose, shipped=False)
    _gr.we(tp_shipped=False, tp_reason=reason, tp_detail=detail, verified_steps=n_steps,
           formatter_cards=(len(last_cards) if last_cards else None), tp_attempts=attempts)
    return None


def _solve_via_reason_extract(topic, fmt, reason_fn, extract_fn, critic_fn) -> Optional[dict[str, Any]]:
    """SOFT path: the model reasons in prose then a trace is extracted; a critic verifies it (Stage 2);
    then the same format + fidelity + prose machinery applies. Offline / on any miss -> None (defer)."""
    from .reason_extract import produce_via_reason_extract
    from .verifiers import verify_via_critic
    from .trace_adapters.generic import GenericAdapter
    trace = produce_via_reason_extract(
        topic, topic.get("example_input") or {},
        reason_fn=reason_fn or _default_reason_fn, extract_fn=extract_fn or _default_extract_fn)
    if trace is None:
        return None
    adapter = GenericAdapter()
    if structural_invariants(trace, adapter):
        return None
    if verify_via_critic(trace, critic_fn=critic_fn or _default_critic_fn).illegal_step:
        return None                                               # critic rejected -> withhold
    return _format_validate_ship(topic, trace, adapter, fmt)


def _retain_debug(topic: dict[str, Any], trace: ContractTrace, raw: Any, cards: Any,
                  fid: Any, prose: Any, *, shipped: bool) -> None:
    """Internal-only debug payload (§18): input, conventions, trace, formatter raw, cards, results — so a
    failure reads as 'reference correct -> formatter prose drifted at card N'. Off unless a path is set."""
    path = os.getenv("AZALEA_TRACE_PIPELINE_DEBUG_PATH")
    if not path:
        return
    try:
        from dataclasses import asdict
        payload = {
            "topic": {k: topic.get(k) for k in ("id", "title", "slug")},
            "shipped": shipped, "provenance": trace.provenance, "conventions": trace.conventions,
            "problem": trace.problem, "final_answer": trace.final_answer,
            "steps": [asdict(s) for s in trace.steps],
            "formatter_raw": raw, "normalized_cards": cards,
            "fidelity": (asdict(fid) if fid else None),
            "prose_violations": [asdict(p) for p in (prose or [])],
        }
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception as exc:  # noqa: BLE001 — debug retention must never affect generation
        _log.debug("trace_pipeline debug retain failed: %s", exc)


def _llm_call(payload: dict[str, str], label: str, *, json_mode: bool = True) -> Optional[Any]:
    """Shared LLM seam (None offline / on failure). json_mode=True parses a JSON object; False returns text."""
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip().lower() == "dummy":
        return None
    try:
        from app.services.llm_client import OPENAI_MODEL, client, llm_call
        kwargs: dict[str, Any] = {
            "model": OPENAI_MODEL,
            "input": [{"role": "system", "content": payload.get("system", "")},
                      {"role": "user", "content": payload.get("user", "")}],
        }
        if json_mode:
            kwargs["text"] = {"format": {"type": "json_object"}}
        with llm_call(label):
            response = client.with_options(
                timeout=float(os.getenv("AZALEA_ENRICH_TIMEOUT_SECONDS", "60")),
                max_retries=max(0, int(os.getenv("AZALEA_ENRICH_MAX_RETRIES", "2"))),
            ).responses.create(**kwargs)
        return json.loads(response.output_text) if json_mode else response.output_text
    except Exception as exc:  # noqa: BLE001
        _log.warning("trace_pipeline %s call failed: %s", label, exc)
        return None


def default_format_fn(payload: dict[str, str]) -> Optional[Any]:
    return _llm_call(payload, "we_trace_format", json_mode=True)


def _default_reason_fn(payload: dict[str, str]) -> Optional[Any]:
    return _llm_call(payload, "we_trace_reason", json_mode=False)


def _default_extract_fn(payload: dict[str, str]) -> Optional[Any]:
    return _llm_call(payload, "we_trace_extract", json_mode=True)


def _default_critic_fn(payload: dict[str, str]) -> Optional[Any]:
    return _llm_call(payload, "we_trace_critic", json_mode=True)
