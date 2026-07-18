"""Domain topic-type gate (Phase 0, DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §4–§5).

Deterministic, no LLM. Given a path-level `domain`, `enrich_topic_with_course_type` may *suggest* any type, but
`gate_topic_types_by_domain` is the **final authority**: every emitted topic's `course_type` is in the domain's
allow-list, forbidden types are **remapped** (with a full-contract rewrite, §5.1), and the path is guaranteed to
retain a native teaching type (§4.2 coverage). Pure functions over topic dicts — no DB, no generation call — so
the whole gate is unit-testable in isolation.

`GATE_VERSION` is bumped whenever the allow-lists / remap / rewrite rules change (telemetry, §7).
"""
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from app.services.domain_classifier import FAMILY_OF, gate_family_of

GATE_VERSION = "v1"
REWRITE_VERSION = "v1"

# --- taxonomy (spec §4.1 / §5.2) — keyed by GATE FAMILY (coding · math · science · expository) ------------
# The fine `domain` (physics, finance, logic, …) maps to a family via FAMILY_OF; the family drives the
# allow-list. mixed/unknown (and any unmapped domain) are NON-GATING (no-op).
_UNIVERSAL = frozenset({
    "study_path_introduction", "concept_intuition", "terminology_components", "compare_distinguish",
    "problem_solving_application",
})
_FAMILY_ALLOWED: dict[str, frozenset[str]] = {
    "coding": frozenset({"algorithm_walkthrough", "data_structure_operation", "coding_implementation",
                         "process_walkthrough"}),
    "math": frozenset({"math_formula_method", "proof_reasoning"}),
    "science": frozenset({"science_mechanism", "math_formula_method"}),  # math_formula_method only if quantitative
    "expository": frozenset({"process_walkthrough"}),                     # humanities · language learning
    # CS (non-coding systems: networking, OS, architecture) — MECHANISM-shaped, like science but labeled CS.
    # No coding/implementation types: "learn about TCP congestion control" is an understanding goal, not a
    # from-scratch coding exercise (a genuinely implementable CS topic belongs in the coding family).
    "cs": frozenset({"science_mechanism", "process_walkthrough", "math_formula_method"}),
    "data_science": frozenset({"math_formula_method", "science_mechanism", "process_walkthrough"}),
    "ee": frozenset({"math_formula_method", "science_mechanism", "process_walkthrough"}),
    "quant": frozenset({"math_formula_method", "process_walkthrough"}),   # finance · economics (formula + process)
}
# The authoritative per-FAMILY TEACHING set (§5.2 — replaces the coding-only _TEACHING_TYPES/_MEMBER_TEACHING_TYPES).
_FAMILY_TEACHING_TYPES: dict[str, frozenset[str]] = {
    "coding": frozenset({"algorithm_walkthrough", "data_structure_operation", "coding_implementation",
                         "process_walkthrough"}),
    "math": frozenset({"math_formula_method", "proof_reasoning"}),
    "science": frozenset({"science_mechanism", "math_formula_method"}),
    "expository": frozenset({"concept_intuition", "compare_distinguish", "process_walkthrough"}),
    "cs": frozenset({"science_mechanism", "process_walkthrough", "math_formula_method"}),
    "data_science": frozenset({"math_formula_method", "science_mechanism", "process_walkthrough"}),
    "ee": frozenset({"science_mechanism", "math_formula_method", "process_walkthrough"}),
    "quant": frozenset({"math_formula_method", "process_walkthrough", "concept_intuition"}),
}
# The family's PRIMARY teaching type (remap target of last resort + coverage recovery, §4.2).
_FAMILY_PRIMARY = {"coding": "algorithm_walkthrough", "math": "math_formula_method",
                   "science": "science_mechanism", "expository": "concept_intuition",
                   "cs": "science_mechanism", "data_science": "math_formula_method",
                   "ee": "science_mechanism", "quant": "math_formula_method"}

# Remap table (§4.2): forbidden type -> per-FAMILY target. "drop_else_*" = coding_implementation special case.
_REMAP: dict[str, dict[str, str]] = {
    "coding_implementation": {"math": "drop_else_primary", "science": "drop_else_primary",
                              "expository": "drop_else_process", "cs": "drop_else_primary",
                              "data_science": "drop_else_primary", "ee": "drop_else_primary",
                              "quant": "drop_else_primary"},
    "algorithm_walkthrough": {"math": "math_formula_method", "science": "science_mechanism",
                              "expository": "process_walkthrough", "cs": "science_mechanism",
                              "data_science": "math_formula_method", "ee": "science_mechanism",
                              "quant": "math_formula_method"},
    "data_structure_operation": {"math": "math_formula_method", "science": "science_mechanism",
                                 "expository": "process_walkthrough", "cs": "science_mechanism",
                                 "data_science": "math_formula_method", "ee": "science_mechanism",
                                 "quant": "math_formula_method"},
    "process_walkthrough": {"math": "math_formula_method", "science": "science_mechanism"},
    "math_formula_method": {"coding": "algorithm_walkthrough", "expository": "concept_intuition"},
    "proof_reasoning": {"coding": "concept_intuition", "science": "science_mechanism",
                        "expository": "concept_intuition", "cs": "science_mechanism",
                        "data_science": "math_formula_method", "ee": "science_mechanism",
                        "quant": "math_formula_method"},
    "science_mechanism": {"coding": "concept_intuition", "math": "math_formula_method",
                          "expository": "concept_intuition", "quant": "math_formula_method"},  # cs/ds/ee ALLOW it
}


def teaching_types_for(domain: str) -> frozenset[str]:
    """Native teaching types for a `domain` (via its gate family). Empty for mixed/unknown/unmapped."""
    return _FAMILY_TEACHING_TYPES.get(gate_family_of(domain), frozenset())


def constrain_type_to_domain(course_type: str, domain: str | None) -> tuple[str, bool]:
    """Domain-aware topic-type constraint at the SOURCE (the classifier), so a coding type is never assigned on a
    known math/science path in the first place — the list-level gate then only backstops. Returns
    (final_type, was_remapped). No-op when the domain is unknown/mixed/unmapped, the type is universal (intro,
    concept, …), or it's already allowed. A DROP case (coding_implementation on a non-coding path) is left alone —
    the list gate does the real drop; relabelling a single topic here would just create a duplicate."""
    ct = str(course_type or "").strip().lower()
    family = gate_family_of(domain) if domain else ""
    allowed = _FAMILY_ALLOWED.get(family)
    if not ct or not allowed or ct in allowed or ct in _UNIVERSAL:
        return ct, False
    rule = _REMAP.get(ct, {}).get(family)
    if rule in ("drop_else_primary", "drop_else_process"):
        return ct, False                                       # a DROP case → leave for the list-level gate
    if rule is None:
        target = _FAMILY_PRIMARY[family]                       # unlisted forbidden ⇒ family primary
    elif rule == "math_formula_method" and family == "science":
        target = "math_formula_method"                        # quantitative-friendly default; gate refines later
    else:
        target = rule
    return target, target != ct
# Target topic type -> required normalized content_role (§5.1).
_TARGET_ROLE = {
    "math_formula_method": "calculation", "proof_reasoning": "proof", "science_mechanism": "mechanism",
    "algorithm_walkthrough": "algorithm_trace", "data_structure_operation": "operation",
    "coding_implementation": "implementation", "concept_intuition": "foundation",
    "process_walkthrough": "mechanism",
}
_CODING_TYPES = frozenset({"algorithm_walkthrough", "data_structure_operation", "coding_implementation"})
# Explicit, ordered title-framing prefixes to strip on remap (§5.1 — NOT a generic gerund strip; "Finding …" is kept).
_STRIP_PREFIXES = ("implementing ", "coding ", "programming ", "solving ", "calculating ", "computing ",
                   "applying ")
# Coding/procedural title framing that implies an algorithm shape ("Algorithm [Walkthrough] for X", "Walkthrough
# of X", trailing " Algorithm"). Stripped only when remapping AWAY from a coding type, so a math topic remapped
# from algorithm_walkthrough reads "Completing the Square", not "Algorithm for Completing the Square".
_ALGO_TITLE_FRAMING_RE = re.compile(
    r"^(?:the\s+)?algorithm(?:\s+walkthrough)?(?:\s+(?:for|to|of)\s+|\s*[:\-]\s*)"
    r"|^(?:step[-\s]?by[-\s]?step\s+)?walkthrough(?:\s+(?:for|of)\s+|\s*[:\-]\s*)",
    re.IGNORECASE,
)
_ALGO_TITLE_SUFFIX_RE = re.compile(r"\s+(?:algorithm|walkthrough)$", re.IGNORECASE)


def _tt(t: dict[str, Any]) -> str:
    return str(t.get("course_type") or t.get("topic_type") or "").strip().lower()


def _is_intro(t: dict[str, Any]) -> bool:
    return _tt(t) == "study_path_introduction"


# --- quantitative_center (§4.3, D-b) ----------------------------------------------------------------------
_QC_RELATION = ("formula", "equation", "law", "=", "ohm", "newton", "f = ma", "f=ma", "stoichiometr",
                "rate", "theorem")
_QC_VERB = ("solve", "calculate", "determine", "compute", "find", "evaluate", "apply", "derive", "use")
_QC_OPERAND = ("m/s", "mol", " kg", " n", "volt", "amp", "ohm", "joule", "%", "unit", "coefficient",
               "value", "measure")
_QC_ADAPTER = ("physics", "chemistry", "electric", "force", "velocity", "acceleration", "energy", "circuit",
               "current", "voltage", "resistance", "molar", "reaction", "stoichiometr", "finance", "interest",
               "formula", "equation", "law", "quadratic", "algebra")


def quantitative_center(topic: dict[str, Any]) -> dict[str, Any]:
    """Conservative v1 heuristic (no LLM): is a science topic quantitatively centered? Returns reason codes +
    `decision`. Numeric/unit signal is *strong* but not required when a supported computational law/method is
    invoked with a compatible adapter family (D-b)."""
    text = f" {str(topic.get('title') or '')} {str(topic.get('purpose') or '')} ".lower()
    formula = any(k in text for k in _QC_RELATION)
    verb = any(re.search(rf"\b{re.escape(v)}\b", text) for v in _QC_VERB)
    operand = any(k in text for k in _QC_OPERAND)
    adapter = any(k in text for k in _QC_ADAPTER)
    # A quantitative TARGET (verb) over a supported computational RELATION (adapter family — which subsumes
    # explicit formulas/laws AND implicit ones like "acceleration from force and mass"). `formula`/`operand` are
    # strengthening reason codes, not requirements (D-b: numeric/units strong but not required).
    decision = bool(verb and adapter)
    return {"formula_detected": formula, "quantitative_verb_detected": verb,
            "numeric_or_unit_signal_detected": operand, "adapter_compatible": adapter, "decision": decision}


# --- full-contract rewrite (§5.1, D-a) --------------------------------------------------------------------
def _normalize_title(title: str, target_type: str) -> str:
    t = str(title or "").strip()
    if target_type in _CODING_TYPES:                       # only strip framing when leaving a coding shape
        return t
    low = t.lower()
    for pfx in _STRIP_PREFIXES:
        if low.startswith(pfx):
            t = t[len(pfx):].strip() or t
            break
    # Strip algorithm/walkthrough framing ("Algorithm for X" → "X"); a math/science method is not an algorithm.
    stripped = _ALGO_TITLE_SUFFIX_RE.sub("", _ALGO_TITLE_FRAMING_RE.sub("", t)).strip()
    if stripped:
        t = stripped
    return t[:1].upper() + t[1:] if t else t


def rewrite_topic_contract(topic: dict[str, Any], target_type: str, domain: str, *, reason: str) -> dict[str, Any]:
    """Deterministically rewrite the FULL topic contract on a remap (never just `course_type`). Preserves the
    original for audit; records `rewrite_reason` / `rewrite_version`."""
    original_title = str(topic.get("title") or "")
    original_role = str(topic.get("content_role") or "")
    topic.setdefault("_original_title", original_title)
    topic.setdefault("_original_course_type", _tt(topic))
    topic.setdefault("_original_content_role", original_role)

    topic["course_type"] = topic["topic_type"] = target_type
    topic["title"] = _normalize_title(original_title, target_type)
    # Populate content_role only where the topic object supports it (§5.1, D-c).
    if ("content_role" in topic or original_role) and target_type in _TARGET_ROLE:
        topic["content_role"] = _TARGET_ROLE[target_type]
    topic["practice_format"] = ("coding" if target_type in _CODING_TYPES
                                else "math_input" if target_type in {"math_formula_method", "proof_reasoning"}
                                else "")
    if target_type not in _CODING_TYPES:                   # a non-coding target has no coding follow-up
        topic["coding_follow_up"] = False
    topic["rewrite_reason"] = reason
    topic["rewrite_version"] = REWRITE_VERSION
    return topic


# --- the gate (§4.2, two-pass) ----------------------------------------------------------------------------
def _remap_target(forbidden: str, family: str, *, has_other_teaching: bool,
                  qc_fn: Callable[[dict[str, Any]], dict[str, Any]], topic: dict[str, Any]) -> Optional[str]:
    """Resolve a forbidden type to its allowed target for `family` (None ⇒ drop)."""
    rule = _REMAP.get(forbidden, {}).get(family)
    if rule is None:
        return _FAMILY_PRIMARY[family]                     # unlisted forbidden ⇒ family primary
    if rule == "drop_else_primary":
        return None if has_other_teaching else _FAMILY_PRIMARY[family]
    if rule == "drop_else_process":
        return None if has_other_teaching else "process_walkthrough"
    if rule == "math_formula_method" and family == "science":
        return "math_formula_method" if qc_fn(topic).get("decision") else "science_mechanism"
    return rule


def gate_topic_types_by_domain(topics: list[dict[str, Any]], domain: str, *,
                               qc_fn: Callable[[dict[str, Any]], dict[str, Any]] = quantitative_center
                               ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The final authority. Returns (gated_topics, telemetry). The fine `domain` maps to a gate family
    (FAMILY_OF); `mixed`/`unknown`/any unmapped domain is a **no-op** (conservative — existing behavior). A path
    left with no native teaching type and no deterministic recovery surfaces `telemetry['routing_validation']`."""
    family = gate_family_of(domain)
    allowed = _FAMILY_ALLOWED.get(family)
    tel = {"gate_version": GATE_VERSION, "domain": domain, "gate_family": family, "topics_seen": len(topics),
           "topics_rewritten": 0, "topics_dropped": 0, "routing_validation": None, "coverage_recovered": False}
    if not allowed:
        return topics, tel                                 # mixed / unknown / unmapped -> no gating

    teach = _FAMILY_TEACHING_TYPES[family]

    # Pass 1+2: for each forbidden topic, decide remap vs drop (a coding_implementation drops only if another
    # non-intro teaching topic already covers the path).
    kept: list[dict[str, Any]] = []
    for t in topics:
        ct = _tt(t)
        # science × math_formula_method: allowed only when quantitatively centered, else remap to mechanism.
        if family == "science" and ct == "math_formula_method" and not qc_fn(t).get("decision"):
            rewrite_topic_contract(t, "science_mechanism", domain, reason="science_qualitative")
            tel["topics_rewritten"] += 1
            kept.append(t); continue
        if ct in allowed or ct in _UNIVERSAL:
            kept.append(t); continue
        # forbidden ⇒ remap/drop
        others_teaching = any(_tt(o) in teach and o is not t for o in topics)
        target = _remap_target(ct, family, has_other_teaching=others_teaching, qc_fn=qc_fn, topic=t)
        if target is None:
            tel["topics_dropped"] += 1                     # drop the forbidden coding twin
            continue
        rewrite_topic_contract(t, target, domain, reason=f"gate_remap:{ct}->{target}")
        tel["topics_rewritten"] += 1
        kept.append(t)

    # Pass 3: native-domain coverage (§4.2). Recover by relabeling the first non-intro topic; else routing_validation.
    if not any(_tt(t) in teach for t in kept):
        recovered = False
        for t in kept:
            if not _is_intro(t):
                rewrite_topic_contract(t, _FAMILY_PRIMARY[family], domain, reason="native_coverage_recovery")
                tel["topics_rewritten"] += 1
                tel["coverage_recovered"] = recovered = True
                break
        if not recovered:
            tel["routing_validation"] = "no_native_teaching_type"

    return (kept or topics), tel
