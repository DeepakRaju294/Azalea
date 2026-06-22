"""Canonical constants + deterministic helpers for the topic-decomposition protocol
(TOPIC_DECOMPOSITION_SPEC.md, Part B). This is the SINGLE source of truth the validator,
prompt schema, and blueprint resolver derive from — so the spec never becomes a second,
narrower topic-type source of truth.

Pure data + pure functions: no LLM, no I/O. Everything here is deterministic and unit-testable.
"""
from __future__ import annotations

import re
from typing import Optional

from app.core.course_types import TopicType

# ----------------------------------------------------------------------------------------------
# Canonical topic types (derived from the one enum — never re-listed by hand). Iterating a
# str-Enum yields only the 12 canonical members; the backward-compat aliases share values and are
# excluded automatically.
# ----------------------------------------------------------------------------------------------
TOPIC_TYPES: tuple[str, ...] = tuple(t.value for t in TopicType)

_CODING_TYPES = frozenset({TopicType.CODING_IMPLEMENTATION.value})


def is_coding_type(topic_type: Optional[str]) -> bool:
    """Single predicate for 'treat as a coding topic'. The coding continuation variant is NOT a
    separate type (spec Part C) — it is `coding_implementation` with an implementation_follow_up
    edge — so this stays trivial and every coding branch in the backend can route through it."""
    return str(topic_type or "").strip() == TopicType.CODING_IMPLEMENTATION.value


# ----------------------------------------------------------------------------------------------
# Content roles (planning abstraction, spec A.3) and the COMPLETE role -> type map (spec B.3).
# `mechanism` is the only role mapping to two types; resolve via resolve_topic_type().
# ----------------------------------------------------------------------------------------------
CONTENT_ROLES: tuple[str, ...] = (
    "orientation", "foundation", "terminology", "mechanism", "operation",
    "algorithm_trace", "implementation", "calculation", "proof", "comparison", "application",
)

# 1:1 rows; `mechanism` handled by resolve_topic_type().
_ROLE_TO_TYPE: dict[str, str] = {
    "orientation": TopicType.STUDY_PATH_INTRODUCTION.value,
    "foundation": TopicType.CONCEPT_INTUITION.value,
    "terminology": TopicType.TERMINOLOGY_COMPONENTS.value,
    "operation": TopicType.DATA_STRUCTURE_OPERATION.value,
    "algorithm_trace": TopicType.ALGORITHM_WALKTHROUGH.value,
    "implementation": TopicType.CODING_IMPLEMENTATION.value,
    "calculation": TopicType.MATH_FORMULA_METHOD.value,
    "proof": TopicType.PROOF_REASONING.value,
    "comparison": TopicType.COMPARE_DISTINGUISH.value,
    "application": TopicType.PROBLEM_SOLVING_APPLICATION.value,
}


def resolve_topic_type(content_role: str, *, scientific: bool = False) -> Optional[str]:
    """Map a planning content_role to a canonical topic_type (spec B.3). `mechanism` routes to
    `science_mechanism` for causal/scientific models, else `process_walkthrough` (procedural flow).
    Returns None for an unknown role."""
    role = str(content_role or "").strip().lower()
    if role == "mechanism":
        return (TopicType.SCIENCE_MECHANISM.value if scientific
                else TopicType.PROCESS_WALKTHROUGH.value)
    return _ROLE_TO_TYPE.get(role)


def role_matches_type(content_role: str, topic_type: str) -> bool:
    """B.4 check 5 — role↔type consistency (mechanism accepts either of its two types)."""
    role = str(content_role or "").strip().lower()
    tt = str(topic_type or "").strip()
    if role == "mechanism":
        return tt in (TopicType.SCIENCE_MECHANISM.value, TopicType.PROCESS_WALKTHROUGH.value)
    return _ROLE_TO_TYPE.get(role) == tt


# ----------------------------------------------------------------------------------------------
# Closed enums used by the deterministic validator (spec B.2 / B.4).
# ----------------------------------------------------------------------------------------------
ACTION_VERBS: tuple[str, ...] = (
    "understand", "identify", "represent", "trace", "choose", "implement",
    "modify", "debug", "compare", "prove", "calculate", "apply",
)

# Closed synonym families for the three-level action match (spec B.4). A bare verb maps to its
# canonical ACTION_VERB; matching is over canonical verbs, never free-text semantics.
_ACTION_SYNONYMS: dict[str, str] = {
    "walk_through": "trace", "walkthrough": "trace", "simulate": "trace", "step_through": "trace",
    "build": "implement", "write": "implement", "code": "implement", "construct": "implement",
    "explain": "understand", "describe": "understand",
    "select": "choose", "decide": "choose", "pick": "choose",
    "distinguish": "compare", "contrast": "compare",
    "compute": "calculate", "evaluate": "calculate", "derive": "calculate",
    "fix": "debug", "diagnose": "debug",
    "recognize": "apply", "solve": "apply",
}


def canonical_action(action: Optional[str]) -> Optional[str]:
    """Normalize an action to a canonical ACTION_VERB (via the closed synonym map), else None."""
    a = re.sub(r"[^a-z]+", "_", str(action or "").strip().lower()).strip("_")
    if a in ACTION_VERBS:
        return a
    return _ACTION_SYNONYMS.get(a)


def match_action(a: Optional[str], b: Optional[str]) -> str:
    """Three-level action match (spec B.4): 'exact' (same canonical verb, both directly in the
    enum), 'synonym' (same canonical verb via a closed family), or 'none'."""
    ca, cb = canonical_action(a), canonical_action(b)
    if ca is None or cb is None or ca != cb:
        return "none"
    raw_a = re.sub(r"[^a-z]+", "_", str(a or "").strip().lower()).strip("_")
    raw_b = re.sub(r"[^a-z]+", "_", str(b or "").strip().lower()).strip("_")
    if raw_a in ACTION_VERBS and raw_b in ACTION_VERBS:
        return "exact"
    return "synonym"


PRACTICE_EVIDENCE_TYPES: tuple[str, ...] = (
    "explain_model", "identify_component", "trace_state", "choose_method", "solve_numeric",
    "construct_proof", "write_code", "debug_code", "modify_code", "apply_pattern",
)

OWNERSHIP_MODES: tuple[str, ...] = ("standalone", "embedded", "unowned")  # 'unowned' is transient only
BASIS_VALUES: tuple[str, ...] = ("goal", "source", "essential_prerequisite", "required_by_policy")
GROUNDING_STRENGTHS: tuple[str, ...] = ("explicit", "inferred")

# Topic relationships carry pedagogical meaning; only dependency-bearing types induce a
# prereq/order edge. implementation_follow_up's ordering comes from the coding capability's
# prerequisite on the walkthrough capability, so the topic edge itself is NOT dependency-bearing.
RELATIONSHIP_TYPES: dict[str, dict[str, bool]] = {
    "implementation_follow_up": {"dependency_bearing": False},
    "concept_lead_in": {"dependency_bearing": False},
}


# ----------------------------------------------------------------------------------------------
# subject_key normalization (spec B.2). The MODEL proposes a semantic key; the backend only
# validates FORMAT and strips obvious framing — it never reconstructs domain meaning. Replaces the
# acronym/frequency/empty-fallback domain-token heuristic in topic_generator.py.
# ----------------------------------------------------------------------------------------------
_FRAMING_WORDS = frozenset({
    "understand", "understanding", "trace", "tracing", "implement", "implementing", "implementation",
    "overview", "walkthrough", "concept", "concepts", "coding", "lesson", "guide", "step", "steps",
    "intro", "introduction", "learn", "learning", "basics", "basic", "fundamentals", "fundamental",
    "how", "what", "why", "the", "a", "an", "of", "for", "to", "with", "in", "on", "and",
})


def normalize_subject_key(proposed: Optional[str]) -> str:
    """Lowercase ASCII slug, noun-phrase only. Strips framing/lesson words and a *trailing generic*
    `algorithm` (never a mid-phrase domain `algorithm`), drops 1-char tokens (possessive 's').
    Never empties: if stripping removes everything, falls back to the format-cleaned slug."""
    tokens = [t for t in re.findall(r"[a-z0-9]+", str(proposed or "").lower())]
    cleaned = [t for t in tokens if t not in _FRAMING_WORDS and len(t) > 1]
    # 'algorithm' only as a trailing generic descriptor (keep 'genetic algorithm selection').
    if len(cleaned) > 1 and cleaned[-1] == "algorithm":
        cleaned = cleaned[:-1]
    if not cleaned:  # never empty — fall back to a format-cleaned slug of the original
        cleaned = [t for t in tokens if len(t) > 1] or tokens
    return "_".join(cleaned)
