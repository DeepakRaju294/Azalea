"""Single-call path-plan + topics prompt (TOPIC_DECOMPOSITION_SPEC.md A / B.1).

One structured call emits BOTH the capability path plan and the topics that own its capabilities,
carrying the planning fields the deterministic validator needs AND the learner-facing fields the
existing lesson pipeline already consumes. The deny-list / framing rules live in the spec; here we
keep the operational instructions tight (the heavy checking is the deterministic validator).
"""
from __future__ import annotations

from typing import Any

from app.core.topic_decomposition import (
    ACTION_VERBS, CONTENT_ROLES, PRACTICE_EVIDENCE_TYPES, TOPIC_TYPES,
)

OVERLAP_SYSTEM_PROMPT = (
    "You are Azalea's path auditor. Two topics share a subject and a learner action and the deterministic "
    "checks could not cleanly separate or merge them. Decide whether they are genuinely DISTINCT learning "
    "deltas (keep both) or REDUNDANT (one fully covers the other — drop the weaker). Be conservative: only "
    "drop when one truly adds nothing the other lacks. Return ONLY valid JSON."
)


def _topic_card(t: dict[str, Any]) -> str:
    keys = ("topic_id", "title", "subject_key", "primary_action", "content_role",
            "topic_type", "practice_evidence_type", "expected_output", "in_scope")
    return "; ".join(f"{k}={t.get(k)!r}" for k in keys if t.get(k) is not None)


def build_overlap_resolver_prompt(a: dict[str, Any], b: dict[str, Any]) -> str:
    return f"""Two candidate topics:

A: {_topic_card(a)}
B: {_topic_card(b)}

Return ONLY JSON:
{{"decision": "keep_both" | "drop_topic",
  "surviving_topic_id": "<the topic_id to KEEP if dropping; omit for keep_both>",
  "reason": "one sentence"}}
"""

SYSTEM_PROMPT = (
    "You are Azalea. Decompose a learner goal + source into a CAPABILITY GRAPH, then into a minimal, "
    "non-overlapping, ordered study path. Work backward from the end capability to the required "
    "capabilities; create one topic per independent learner capability; fold supporting capabilities "
    "into their parent topic; never create a topic from a heading/keyword or just to use a different "
    "type. Every topic must add a UNIQUE learning delta. Return ONLY valid JSON."
)


def build_decomposition_prompt(goal: str | None, chunks_text: str, feedback: str | None = None) -> str:
    fb = f"\n\nUSER FEEDBACK (apply to the path):\n{feedback.strip()}" if feedback and feedback.strip() else ""
    return f"""
GOAL:
{goal or "General understanding of the material"}

SOURCE MATERIAL:
{chunks_text}{fb}

---
PROCESS (capability-first):
1. end_capability: the concrete action-oriented outcome; list its action verbs in end_capability_actions.
2. required_capabilities: work backward. Each has a stable capability_id (snake_case), a one-line
   description, prerequisite_capability_ids (earlier capabilities it depends on), satisfies_end_actions
   (which end actions it provides, or []), ownership_mode ("standalone" -> its own topic; "embedded" ->
   folded into one owner topic, set owner_topic_id), and basis ("goal" | "source" | "essential_prerequisite").
3. topics: ONE per standalone capability. Fold supporting capabilities (terminology, setup, edge cases,
   one-line paradigm framing) into their parent as embedded capabilities — do NOT give them topics.
4. For every algorithm_walkthrough or data_structure_operation topic, a coding follow-up will be added
   automatically; do NOT also emit a near-duplicate coding topic for the same subject yourself.

RULES:
- subject_key = the SUBJECT IDENTITY only (the thing learned), never the action: "breadth_first_search",
  "binary_search_tree", "prim". The action lives in primary_action.
- primary_action ∈ {", ".join(ACTION_VERBS)}.
- content_role ∈ {", ".join(CONTENT_ROLES)}; topic_type ∈ {", ".join(TOPIC_TYPES)}.
- practice_evidence_type ∈ {", ".join(PRACTICE_EVIDENCE_TYPES)}.
- expected_output = the concrete artifact the learner produces (distinct from practice_target).
- Two topics on the same subject are allowed only when the learner job (primary_action) differs.
- Keep the path minimal (usually 3-10 topics); foundation topics only when a brief just-in-time note
  inside the next topic would not suffice.

Return ONLY JSON of this shape:
{{
  "path_plan": {{
    "end_capability": "...",
    "end_capability_actions": ["trace", "implement"],
    "required_capabilities": [
      {{"capability_id": "...", "description": "...", "prerequisite_capability_ids": [],
        "satisfies_end_actions": [], "ownership_mode": "standalone", "owner_topic_id": null, "basis": "goal"}}
    ]
  }},
  "topics": [
    {{
      "topic_id": "...", "capability_id": "...", "subject_key": "...", "primary_action": "trace",
      "content_role": "algorithm_trace", "topic_type": "algorithm_walkthrough",
      "title": "...", "unit_title": "...", "learner_outcome": "...", "purpose": "...",
      "in_scope": ["..."], "out_of_scope": ["..."], "prerequisite_topics": [], "source_refs": [],
      "practice_target": "...", "practice_format": "trace", "practice_evidence_type": "trace_state",
      "expected_output": "...", "novelty_claim": "...", "estimated_minutes": 12, "basis": "goal"
    }}
  ]
}}
"""
