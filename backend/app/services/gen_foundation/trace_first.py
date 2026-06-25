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


def build_cards_from_trace(
    trace_events: Optional[list[dict[str, Any]]],
    *,
    max_cards: int = 10,
) -> dict[str, Any]:
    """Build a state-accurate worked-example skeleton from real execution events. Returns
    {cards, final_answer, trace_backed: True} or {} when there's no usable trace.

    Each card carries the REAL before/after state and the code lines that produced it; `goal`/`reasoning`
    are left empty for the narration pass. `final_answer` is the executor's actual return value."""
    if not trace_events:
        return {}
    final = next((e.get("return_value") for e in reversed(trace_events) if "return_value" in e), None)
    events = _significant(trace_events)
    groups = _group(events, max_cards)
    if not groups:
        return {}

    cards: list[dict[str, Any]] = []
    prior_state: dict[str, Any] | None = None
    for idx, group in enumerate(groups, start=1):
        last = group[-1]
        after = last.get("state") if isinstance(last.get("state"), dict) else {}
        code_refs = sorted({ln for ev in group for ln in (ev.get("code_line_refs") or [])
                            if isinstance(ln, int)})
        cards.append({
            "card_id": f"step_{idx}",
            "title": "",                 # narration pass fills these
            "goal": "",
            "reasoning": "",
            "work": [f"line {ln}" for ln in code_refs] or ["(step)"],
            "result": _state_summary(after) or "(state updated)",
            "prior_state": prior_state,
            "state": after,              # REAL recorded state — not model-invented
            "code_refs": code_refs,
            "state_relevance": "stateful" if after else "none",
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
