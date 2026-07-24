"""Prerequisite RELEVANCE — a check that never existed before: is a claimed assumed_prerequisite actually
true/necessary for the goal, as opposed to §3.1/§6.1's SCOPE question (in-scope-taught vs out-of-scope-
prerequisite, app/services/prereq_scope_classifier.py), which assumes the claim is true and only asks where
it belongs. Two live bugs motivated this: a study path for "stokes theorem" listed "vector calculus" as a
prerequisite (circular — Stokes' theorem IS vector calculus, so the claim conflates the goal's own topic with
its parent field) and "differential equations" (unrelated — nothing about Stokes' theorem requires it). Every
existing guard (`_is_circular_prereq`, `_drop_umbrella_prereqs` in topic_decomposition_pipeline.py) only checks
STRUCTURAL properties (does the prereq text overlap the goal text, is it on a static umbrella-terms list) —
none of them check whether the claim is actually correct.

Safety direction is the OPPOSITE of Guard 4's (topic_decomposition_pipeline.py's live foundation-fold override):
Guard 4 fails toward keeping MORE content taught, because adding was the low-risk direction there. Here,
DROPPING a prerequisite is the consequential action, so a classifier failure/timeout/malformed response must
fail toward KEEPING it — exactly today's fully-trusted behavior — never toward silently dropping something
that might be legitimate. Only a confident, successful "not relevant" result drops anything.

Pure over its inputs; the LLM call is injected via `model_fn` (tests never make live calls). The default model
fn imports `llm_client` LAZILY (inside the function body) — `llm_client` calls `load_dotenv()` at import time
and raises if OPENAI_API_KEY is unset, so importing it eagerly here would leak .env into any test that merely
imports this module."""
from __future__ import annotations

from typing import Any, Callable, Optional

RelevanceModelFn = Callable[[dict[str, Any]], Any]

RELEVANCE_CLASSIFICATION_SYSTEM_PROMPT = """You check whether a claimed PREREQUISITE for a learning goal is \
actually true and necessary — not just plausible-sounding.

Reject (relevant=false) in exactly two cases:
  1. CIRCULAR — the prerequisite names the same broader field/subject that the goal's own topic belongs to \
(e.g. goal "learn Stokes' theorem" claiming "vector calculus" as a prerequisite — Stokes' theorem IS a vector \
calculus theorem, so this just restates the goal's own subject as an external prerequisite instead of naming \
a specific sub-skill actually needed beforehand).
  2. UNRELATED — nothing about achieving the goal actually requires the claimed prerequisite (e.g. goal "learn \
Stokes' theorem" claiming "differential equations" — computing a curl or a surface/line integral never \
requires solving a differential equation).

Otherwise (a genuine, specific, necessary prerequisite), accept it: relevant=true.

Respond with `relevant` (true/false) and one sentence of `rationale` justifying the decision."""


def _build_prompt(canonical_name: str, goal: str, gloss: str) -> str:
    gloss_line = f"Claimed prerequisite description: {gloss}\n" if gloss.strip() else ""
    return f"Goal: {goal}\nClaimed prerequisite: {canonical_name}\n{gloss_line}"


def _default_relevance_model_fn(payload: dict[str, Any]) -> Any:
    from app.services.llm_client import generate_prereq_relevance_classification  # lazy: avoid .env at import
    return generate_prereq_relevance_classification(payload["system"], payload["user"])


def classify_prereq_relevance(
    *, canonical_name: str, goal: str, gloss: str = "",
    model_fn: Optional[RelevanceModelFn] = None,
) -> tuple[bool, str]:
    """Empty goal or ANY error (bad shape, non-dict, an exception from `model_fn`, a missing/malformed
    `relevant` field) safely degrades to `(True, "")` — fail toward keeping the prerequisite exactly as
    today, never toward silently dropping something that might be legitimate. Never raises."""
    if not goal.strip() or not canonical_name.strip():
        return True, ""
    fn = model_fn or _default_relevance_model_fn
    try:
        payload = {
            "system": RELEVANCE_CLASSIFICATION_SYSTEM_PROMPT,
            "user": _build_prompt(canonical_name, goal, gloss),
            "canonical_name": canonical_name,
        }
        raw = fn(payload)
        parsed = raw if isinstance(raw, dict) else {}
        relevant = parsed.get("relevant")
        if not isinstance(relevant, bool):
            return True, ""                     # malformed/missing -> fail open, keep the prerequisite
        rationale_raw = parsed.get("rationale")
        rationale = rationale_raw.strip() if isinstance(rationale_raw, str) else ""
        return relevant, rationale
    except Exception:  # noqa: BLE001 — a failed classification must never drop a prerequisite or break decomposition
        return True, ""
