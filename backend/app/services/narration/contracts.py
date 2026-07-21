"""Per-domain within-card narration contracts (DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC §3).

A *lens over existing config*, not a new build (Q38): declarative per-(domain × card) framing that the Phase-2B
wiring injects at the blueprint/prompt layer (path A) and the trace-step formatter (path B). Two change kinds —
**reframe** (labels/contract/order change; most cards) vs **restructure** (the `process` scaffold shape changes).

Only PRESENTATION lives here (§4 adapter-neutral boundary): labels, field headings, prose ordering, action-
oriented step titles. Truth-bearing values (units, rule identifiers, state deltas, interpretation) come from the
fact-source registry — never from this module.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.narration.matrix import narration_domain_of

# --- process card scaffold (RESTRUCTURE, §3) --------------------------------------------------------------
# The core scaffold shape per domain — replaces the coding loop framing ("Starting state / Repeated action /
# State update") that produced the awkward math reads. Injected at the blueprint/prompt layer (Q39 path A).
PROCESS_SCAFFOLD: dict[str, tuple[str, ...]] = {
    "coding":  ("Setup", "Loop / repeated action", "State update", "Termination"),
    "math":    ("Setup", "Operation", "Result", "Why"),
    "science": ("Principle", "Apply", "Interpret"),
    "concept": ("Idea", "Structure", "Example"),
}

# --- worked-example step framing (REFRAME, §3 table) ------------------------------------------------------
WORKED_EXAMPLE_FIELD_FRAMING: dict[str, dict[str, str]] = {
    "coding": {
        "goal": "what this line does",
        "reasoning": "why (control / purpose)",
        "work": "the code line (+ trace)",
        "result": "variable state after",
    },
    "math": {
        "goal": "what we transform, toward what",
        "reasoning": "the rule / identity justifying it",
        "work": "the rewritten expression",
        "result": "the new form / running result",
    },
    "science": {
        "goal": "what quantity we're finding",
        "reasoning": "the law / principle invoked",
        "work": "the substitution & solve",
        "result": "value + units + interpretation",
    },
    "concept": {
        "goal": "what idea / distinction is established",
        "reasoning": "relation / definition / contextual basis",
        "work": "example / comparison / evidence",
        "result": "concise takeaway / classification",
    },
}

# --- formula_breakdown card (math; §2.1 D2 first slice) ---------------------------------------------------
# Teaches WHY a formula/method works by decomposing it — central to completing-the-square (not optional). Fields
# are REFRAME framing; the identity/rule labels + transformed forms are truth-bearing and come from the
# derivation trace (fact_source.py), never free prose.
FORMULA_BREAKDOWN_FRAMING: dict[str, dict[str, str]] = {
    "math": {
        "goal": "the identity/method and what it achieves",
        "parts": "each component of the expression and the role it plays",
        "transformation": "the rewrite that assembles the target form",
        "why": "the algebraic rule that makes each step valid",
    },
    # science(quantitative) is DEFERRED in the matrix — no framing shipped until its metadata gaps close (§4).
}


def process_scaffold_directive(domain: str | None) -> str | None:
    """Path-A prompt injection (§3 restructure): the per-domain process/method-card frames, so a math (or
    science) process card is framed with its own scaffold instead of the coding loop framing ("Starting state /
    Repeated action / State update"). None for coding/unknown — keep the default frames there."""
    nd = narration_domain_of(domain)
    if nd is None or nd == "coding" or nd not in PROCESS_SCAFFOLD:
        return None
    frames = ", ".join(f'"{f}"' for f in PROCESS_SCAFFOLD[nd])
    return (
        f"PROCESS/METHOD CARD FRAMES ({nd}) — THIS OVERRIDES any 'Starting state / Repeated action / State update "
        "/ Stopping condition / Output rule' framing described anywhere else in these instructions. For the "
        f"process/method card use EXACTLY these frames as the main bullets, in order: {frames}. This is a {nd} "
        "method, not a running program — never use loop/state framing for it under any circumstances. These "
        f"frame labels ({frames}) belong ONLY on the process/method card — do not use them as headers on the "
        "background/purpose card, the key-terms card, the edge-case card, or any other card in this lesson; "
        "every other card keeps its own normal framing."
    )


def formula_breakdown_framing(domain: str | None) -> dict[str, str] | None:
    """Framing for the formula_breakdown card, or None where it isn't `defined` (only math in v1)."""
    nd = narration_domain_of(domain)
    return dict(FORMULA_BREAKDOWN_FRAMING[nd]) if nd in FORMULA_BREAKDOWN_FRAMING else None


# --- other cards (REFRAME, §3) ----------------------------------------------------------------------------
BACKGROUND_FRAMING = {
    "coding": "what it's for", "math": "where it applies",
    "science": "the phenomenon", "concept": "the idea",
}
COMPONENTS_TERMS_FRAMING = {
    "coding": "data structures", "math": "symbols + notation",
    "science": "quantities + units", "concept": "key terms",
}
EDGE_CASE_FRAMING = {
    "coding": "boundary input", "math": "degenerate case",
    "science": "limiting assumption", "concept": "common misconception",
}
PRACTICE_FRAMING = {
    "coding": "modify-code", "math": "solve",
    "science": "predict", "concept": "classify-compare-explain",
}

# --- cross-cutting rules (all cards, §3) ------------------------------------------------------------------
# (1) framing only — truth-bearing values come from the fact-source registry.
# (2) never introduce a term outside assumed_prerequisites + what's taught.
# (3) practice stays within the taught method (closes the a≠1 gap).
# (4) step titles describe the ACTION, not the rule name.
# (5) result lines are terminal, not narrated.
STEP_TITLE_RULE = "action_not_rule_name"      # "Add and subtract (b/2)²", NOT "Completing-the-square rule"
RESULT_LINE_RULE = "terminal_not_narrated"    # drop "Complete: the conclusion is reached. Final result: …"


@dataclass(frozen=True)
class NarrationContract:
    """The resolved per-domain framing bundle handed to the narrator (path A) / step formatter (path B)."""
    domain: str
    process_scaffold: tuple[str, ...]
    worked_example_fields: dict[str, str]
    background: str
    components_terms: str
    edge_case: str
    practice: str
    step_title_rule: str = STEP_TITLE_RULE
    result_line_rule: str = RESULT_LINE_RULE


def narration_contract_for(domain: str | None) -> NarrationContract | None:
    """Resolve the within-card narration contract for a fine/family/coarse `domain`. None for a non-gating domain
    (mixed/unknown) — the caller then keeps the legacy framing (no domain contract to apply)."""
    nd = narration_domain_of(domain)
    if nd is None or nd not in PROCESS_SCAFFOLD:
        return None
    return NarrationContract(
        domain=nd,
        process_scaffold=PROCESS_SCAFFOLD[nd],
        worked_example_fields=dict(WORKED_EXAMPLE_FIELD_FRAMING[nd]),
        background=BACKGROUND_FRAMING[nd],
        components_terms=COMPONENTS_TERMS_FRAMING[nd],
        edge_case=EDGE_CASE_FRAMING[nd],
        practice=PRACTICE_FRAMING[nd],
    )
