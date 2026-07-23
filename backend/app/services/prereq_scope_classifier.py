"""§3.1/§6.1 real scope classification (PREREQ_LINKS_SPEC v8) — the "later, heavier half" prereq_links_shadow.py
previously stubbed out. Two independent pieces:

  * `classify_recommended_scope_rule` — the auditable §3.1 procedure (LLM-permitted, contract-constrained, must
    emit a rationale). Named "recommended" because its return value is the model's judgment, not necessarily the
    legally-storable value: an `AssumedPrerequisite.scope_rule` can ONLY ever be `recognition_only_fallback`
    (app/core/prereq_links/validation.py's Tier-2 check #6), so a recommended in-scope rule for an
    assumed-prerequisite candidate is never written onto that object — callers surface it as telemetry only.
  * `build_prerequisite_goal` — the SEPARATE §3 deterministic (non-LLM) target_goal builder. Always produces a
    non-empty string (§A15), independent of whether classification ran at all.

Both are pure over their inputs; the LLM call itself is injected via `model_fn` (tests never make live calls).
`_default_scope_model_fn` imports `llm_client` LAZILY (inside the function body) — `llm_client` calls
`load_dotenv()` at import time and raises if OPENAI_API_KEY is unset, so importing it eagerly here would leak
.env into any test that merely imports this module (the same landmine prereq_links_shadow.py's own docstring
already documents for itself)."""
from __future__ import annotations

from typing import Any, Callable, Optional

from app.core.prereq_links import ScopeRule

ScopeModelFn = Callable[[dict[str, Any]], Any]

# PREREQ_LINKS_SPEC.md v8 §3.1 — the auditable procedure, verbatim rule intent (not a byte-identical copy —
# a dedicated drift test checks each rule's key phrase still appears here).
SCOPE_CLASSIFICATION_SYSTEM_PROMPT = """You classify whether a concept a learner needs is IN SCOPE for a study \
path (should be taught as its own topic) or OUT OF SCOPE (the learner is assumed to already recognize it, and \
gets a link to a separate path instead).

A dependency is `in_path_foundation` (in scope) when AT LEAST ONE holds:
  1. explicit_objective — the goal explicitly asks the learner to LEARN / explain / calculate with / compare / \
demonstrate competency in the dependency, not merely mentions it as context.
  2. beginner_minimum_sequence — the goal contains beginner/from-scratch language AND the dependency is part of \
the minimum teaching sequence.
  3. competency_required — achieving the goal requires the learner to DEVELOP or DEMONSTRATE COMPETENCY in the \
dependency itself, not merely recognize enough of it to follow the target concept.
  4. source_or_user_objective — the user explicitly requires it, or the instructional scope selected for the \
path identifies it as an OBJECTIVE of the requested path.

Otherwise, if the dependency is needed only to RECOGNIZE or UNDERSTAND an in-scope concept (not to achieve the \
goal itself), classify it `recognition_only_fallback` (out of scope, assumed_prerequisite).

Respond with the single scope_rule value that fired (one of: explicit_objective, beginner_minimum_sequence, \
competency_required, source_or_user_objective, recognition_only_fallback) and one sentence of scope_rationale \
justifying it."""


def _candidate_framing(candidate_kind: str) -> str:
    if candidate_kind == "taught_foundation":
        return ("This concept is CURRENTLY being taught as its own topic in the path. Decide whether that is "
                "scope-justified, or whether it should really only be assumed prior knowledge.")
    return ("This concept is CURRENTLY NOT taught in the path (the learner is assumed to already know it). "
            "Decide whether that is correct, or whether the goal actually requires teaching it.")


def _build_prompt(canonical_name: str, goal: str, domain: str, candidate_kind: str) -> str:
    domain_line = f"Domain: {domain}\n" if domain.strip() else ""
    return (f"Goal: {goal}\n{domain_line}Concept: {canonical_name}\n\n{_candidate_framing(candidate_kind)}")


def _default_scope_model_fn(payload: dict[str, Any]) -> Any:
    from app.services.llm_client import generate_prereq_scope_classification  # lazy: avoid .env at import time
    return generate_prereq_scope_classification(payload["system"], payload["user"])


def classify_recommended_scope_rule(
    *, canonical_name: str, goal: str, domain: str, candidate_kind: str,
    model_fn: Optional[ScopeModelFn] = None,
) -> tuple[ScopeRule, str]:
    """The §3.1 procedure. `candidate_kind` is "taught_foundation" or "assumed_prerequisite" (frames the prompt
    differently — same rule contract either way). Empty `goal` short-circuits to the fallback with NO call at
    all. Never raises: any error (bad shape, non-dict, an exception from `model_fn`) safely degrades to
    `(recognition_only_fallback, "")`, exactly like today's stub — this is shadow telemetry, not a gate."""
    if not goal.strip():
        return ScopeRule.recognition_only_fallback, ""
    fn = model_fn or _default_scope_model_fn
    try:
        payload = {
            "system": SCOPE_CLASSIFICATION_SYSTEM_PROMPT,
            "user": _build_prompt(canonical_name, goal, domain, candidate_kind),
            "canonical_name": canonical_name,
            "candidate_kind": candidate_kind,
        }
        raw = fn(payload)
        parsed = raw if isinstance(raw, dict) else {}
        rule_str = str(parsed.get("scope_rule") or "").strip()
        try:
            rule = ScopeRule(rule_str)
        except ValueError:
            rule = ScopeRule.recognition_only_fallback
        rationale_raw = parsed.get("scope_rationale")
        rationale = rationale_raw.strip() if isinstance(rationale_raw, str) else ""
        return rule, rationale
    except Exception:  # noqa: BLE001 — classification is best-effort shadow telemetry, must never break the path
        return ScopeRule.recognition_only_fallback, ""


def build_prerequisite_goal(canonical_name: str, originating_domain: str, originating_goal_context: str) -> str:
    """PREREQ_LINKS_SPEC.md v8 §3 — deterministic (NOT LLM), context-aware. Always non-empty (§A15), unlike
    `classify_recommended_scope_rule` this runs unconditionally regardless of whether classification ran at
    all. A generic template, not a reproduction of the spec's bespoke illustrative examples ("...how it drives
    current in a circuit") — those need world knowledge a deterministic builder doesn't have; this is an
    acceptable approximation for a scoped-goal string, not learner-facing prose quality."""
    name = canonical_name.strip() or "this concept"
    # Lowercase the leading letter for an ordinary capitalized word ("Voltage" -> "voltage", reads naturally
    # after "the basics of"), but leave acronym-shaped names alone ("DNS", a lone capital "A") — those are
    # already all-caps or have an uppercase SECOND letter, neither of which a simple capitalized word has.
    looks_like_acronym = len(name) > 1 and (name.isupper() or name[1].isupper())
    if name[0].isalpha() and not looks_like_acronym:
        name = name[0].lower() + name[1:]
    sentence = f"Understand the basics of {name} — what it represents and how it applies"
    context = originating_goal_context.strip()
    domain = originating_domain.strip()
    if context:
        sentence += f", in support of {context}"
    if domain:
        sentence += f" ({domain})"
    return sentence + "."
