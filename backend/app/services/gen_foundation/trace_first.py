"""Trace-first worked-example construction (inaccuracy fix D — the root fix for #1/#2/#3/#6).

The model can't be trusted to hand-simulate code: it truncates (#1), miscomputes intermediate state
(#2), declares a wrong/incomplete answer (#3), and drifts from the code (#6). This builds the
worked-example card SKELETON from the executor's REAL recorded states, so those four failures are
structurally impossible — the states are recorded, not invented; the run goes to completion; the
final answer is the real return value. A downstream LLM pass writes only the prose (goal/reasoning)
around states it did not author.

Pure: trace events in, card skeletons out. The executor (executor.execute) supplies the events.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

_MAX_WORK_LINES = 6  # per-card projection cap (§5.2) — trace-first cards must stay within it to validate


def canonical_final_answer(value: Any) -> dict[str, Any]:
    """Structured final-answer schema ({kind, value, display}) derived from a REAL return value, so the
    answer is produced by execution rather than self-declared by the model (feeds the property checks)."""
    if value is None:
        return {"kind": "none", "value": None, "display": ""}
    if isinstance(value, bool):
        return {"kind": "bool", "value": value, "display": str(value)}
    if isinstance(value, (int, float)):
        return {"kind": "scalar", "value": value, "display": str(value)}
    if isinstance(value, (list, tuple)):
        return {"kind": "sequence", "value": list(value), "display": repr(list(value))}
    if isinstance(value, dict):
        return {"kind": "mapping", "value": value, "display": repr(value)}
    return {"kind": "other", "value": str(value), "display": str(value)}


NarratorFn = Callable[[dict[str, Any]], Any]


def _code_part(work_line: str) -> str:
    return str(work_line).split("//", 1)[0].rstrip()


def narrate_cards(
    cards: list[dict[str, Any]],
    *,
    problem: str = "",
    model_fn: Optional[NarratorFn] = None,
) -> list[dict[str, Any]]:
    """Narration-polish pass (#1): an LLM rewrites goal/reasoning/per-line explanations as readable prose
    AROUND the real recorded states. It is given the verified states and may ONLY describe them — the
    code lines, the `state`, and the final answer are never changed. Any failure or shape mismatch falls
    back to the terse trace narration, so prose is never traded for accuracy. Pure given ``model_fn``."""
    if not cards:
        return cards
    fn = model_fn or _default_narrator
    steps = [{
        "step": i + 1,
        "code": [_code_part(w) for w in (c.get("work") or [])],
        "before_state": c.get("prior_state"),
        "after_state": c.get("state"),
    } for i, c in enumerate(cards)]
    try:
        narration = fn({"problem": problem, "steps": steps})
    except Exception:  # noqa: BLE001 — narration must never break a correct trace
        return cards
    per = narration.get("steps") if isinstance(narration, dict) else None
    if not isinstance(per, list):
        return cards

    for card, note in zip(cards, per):
        if not isinstance(note, dict):
            continue
        if note.get("title"):
            card["title"] = str(note["title"])
        if note.get("goal"):
            card["goal"] = str(note["goal"])
        if note.get("reasoning"):
            card["reasoning"] = str(note["reasoning"])
        if note.get("result"):
            card["result"] = str(note["result"])  # prose result; the real `state` field is untouched
        # rewrite per-line explanations only when the count matches the verified code lines
        code_parts = [_code_part(w) for w in (card.get("work") or [])]
        exps = note.get("work")
        if isinstance(exps, list) and len(exps) == len(code_parts) and all(isinstance(e, str) for e in exps):
            card["work"] = [f"{code} // {exp}".rstrip(" /") for code, exp in zip(code_parts, exps)]
    return cards


def _default_narrator(payload: dict[str, Any]) -> Any:
    from app.services.llm_client import generate_trace_narration
    return generate_trace_narration(payload)


def _significant(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep events whose semantic state actually changed (drop no-op line steps) + the final return."""
    out: list[dict[str, Any]] = []
    last_state: Any = None
    for ev in events:
        if "return_value" in ev:
            out.append(ev)
            continue
        state = ev.get("state")
        if state != last_state:
            out.append(ev)
            last_state = state
    return out


def _group(events: list[dict[str, Any]], max_cards: int) -> list[list[dict[str, Any]]]:
    """Group contiguous events into <= max_cards teaching steps (one action per card, not one event)."""
    steps = [e for e in events if "return_value" not in e]
    if not steps:
        return []
    n = len(steps)
    if n <= max_cards:
        return [[e] for e in steps]
    per = (n + max_cards - 1) // max_cards  # ceil
    return [steps[i:i + per] for i in range(0, n, per)]


def _state_summary(state: dict[str, Any] | None) -> str:
    if not isinstance(state, dict) or not state:
        return ""
    return ", ".join(f"{k}={v!r}" for k, v in list(state.items())[:6])


def _state_delta_narration(prior: dict[str, Any] | None, after: dict[str, Any]) -> str:
    """A truthful, deterministic description of what changed — built from REAL states, so it cannot
    misstate the computation. Falls back to a full-state summary when there's no clear single delta."""
    prior = prior or {}
    changed = [k for k in after if after.get(k) != prior.get(k)]
    if len(changed) == 1:
        k = changed[0]
        return f"{k} is now {after[k]!r}"
    if changed:
        return ", ".join(f"{k} = {after[k]!r}" for k in changed[:4])
    return _state_summary(after) or "(state updated)"


def build_cards_from_trace(
    trace_events: Optional[list[dict[str, Any]]],
    *,
    code: str = "",
    max_cards: int = 10,
) -> dict[str, Any]:
    """Build COMPLETE state-accurate worked-example cards from real execution events. Returns
    {cards, final_answer, trace_backed: True} or {} when there's no usable trace.

    Work lines are the ACTUAL source lines executed (from `code` + the recorded line refs), and the
    result is a truthful description of the REAL state change — both produced from execution, so the
    trace cannot truncate, drift, or misstate state. `final_answer` is the executor's actual return."""
    if not trace_events:
        return {}
    final = next((e.get("return_value") for e in reversed(trace_events) if "return_value" in e), None)
    src_lines = code.split("\n") if code else []
    events = _significant(trace_events)
    groups = _group(events, max_cards)
    if not groups:
        return {}

    def line_text(n: int) -> str:
        return src_lines[n - 1].strip() if 0 < n <= len(src_lines) else f"line {n}"

    cards: list[dict[str, Any]] = []
    prior_state: dict[str, Any] | None = None
    for idx, group in enumerate(groups, start=1):
        last = group[-1]
        after = last.get("state") if isinstance(last.get("state"), dict) else {}
        code_refs = sorted({ln for ev in group for ln in (ev.get("code_line_refs") or [])
                            if isinstance(ln, int)})
        narration = _state_delta_narration(prior_state, after)
        # Cap work lines to the per-card limit (§5.2): show the LAST lines of the action (the ones that
        # produced the recorded state) so the card stays within the projection cap and validates.
        work = [f"{line_text(ln)} // {narration}" for ln in code_refs[-_MAX_WORK_LINES:]] or [narration]
        cards.append({
            "card_id": f"step_{idx}",
            "title": f"Step {idx}",
            "goal": f"Run line{'s' if len(code_refs) > 1 else ''} "
                    f"{', '.join(map(str, code_refs)) or 'of the algorithm'} on the current state.",
            "reasoning": narration,
            "work": work,
            "result": _state_summary(after) or "(state updated)",
            "prior_state": prior_state,
            "state": after,              # REAL recorded state — not model-invented (carried directly)
            "code_refs": code_refs,
            "state_relevance": "none",   # state is carried on the card, not reconstructed via deltas
            "state_delta": None,
            "cases_covered": [],
            "trace_backed": True,
        })
        prior_state = after

    return {
        "cards": cards,
        "final_answer": final,
        "final_answer_struct": canonical_final_answer(final),
        "trace_backed": True,
        "source": "trace_first",
    }
