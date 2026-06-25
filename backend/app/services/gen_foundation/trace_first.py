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

from typing import Any, Optional


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
        work = [f"{line_text(ln)} // {narration}" for ln in code_refs] or [narration]
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
