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
   ORDERING IS DRIVEN BY prerequisite_capability_ids — so whenever one capability's METHOD USES another's
   result or formula, you MUST list that other capability as a prerequisite, or they order arbitrarily.
   Example: Bayes' theorem computes its denominator P(B) with the law of total probability, so
   `bayes_theorem.prerequisite_capability_ids` MUST include the total-probability capability — total
   probability is taught FIRST, then Bayes. Do not rely on the order you happen to list them in.
3. topics: ONE per standalone capability. Fold supporting capabilities (terminology, setup, edge cases,
   one-line paradigm framing) into their parent as embedded capabilities — do NOT give them topics.
4. For every algorithm_walkthrough or data_structure_operation topic, a coding follow-up will be added
   automatically; do NOT also emit a near-duplicate coding topic for the same subject yourself.

RULES:
- subject_key = the SUBJECT IDENTITY only (the thing learned), never the action: "breadth_first_search",
  "binary_search_tree", "prim". The action lives in primary_action.
- title = a CLEAN, CONSISTENT name — the subject, optionally "<Subject> Algorithm Walkthrough". Do NOT
  decorate it with a study-verb ("Analyzing/Exploring/Understanding/Mastering <X>"): within a family survey
  every member's title must read the SAME way (e.g. all "Bubble Sort", "Selection Sort", … — not "Understanding
  Bubble Sort" beside "Merge Sort Algorithm Walkthrough"). A coding follow-up is auto-titled "Implementing
  <Subject>", so a decorated walkthrough title corrupts it ("Implementing Analyzing Quick Sort").
- primary_action ∈ {", ".join(ACTION_VERBS)}.
- content_role ∈ {", ".join(CONTENT_ROLES)}; topic_type ∈ {", ".join(TOPIC_TYPES)}.
- practice_evidence_type ∈ {", ".join(PRACTICE_EVIDENCE_TYPES)}.
- expected_output = the concrete artifact the learner produces (distinct from practice_target).
- ONE concept = ONE topic. "Understanding X" and "applying X" are the SAME capability, never two topics:
  a single topic teaches a concept end-to-end and its card structure already carries intuition →
  worked example → practice. Do NOT emit a separate "understand" topic and "apply" topic for the same
  subject, and do NOT append "application"/"interpretation" to a subject_key to make a second topic.
  Two topics on ONE subject are allowed ONLY when the DELIVERABLE genuinely differs — the canonical case
  is trace-by-hand vs. write-the-code (algorithm_walkthrough + coding_implementation). "understand" vs
  "apply"/"calculate" is not such a split.
- Distinct TECHNIQUES are distinct learning deltas — even at the same complexity class or under one umbrella.
  When the GOAL is to learn or survey a FAMILY of methods (e.g. "sorting algorithms", "graph traversals",
  "search algorithms", "tree traversals"), each canonical member that teaches a DIFFERENT technique is its
  OWN topic — do NOT fold them as redundant. Cover the canonical set a course or textbook would teach
  (sorting -> bubble, selection, insertion, merge, quicksort; graph traversal -> BFS and DFS; not a single
  representative). The "unique delta" here is the TECHNIQUE, not the runtime class or the shared umbrella
  subject. (This does NOT apply when the goal targets ONE specific method — then include only what that
  method needs, not its whole family.)
- path_plan.assumed_prerequisites: the STRUCTURED list of OUT-OF-SCOPE concepts this path assumes the learner
  already knows and does NOT teach (the external prerequisites). THE TEST: a prerequisite is a concept that
  would be taught in the FEW lectures/units of a college course leading up to this material — e.g. "BSTs
  and their operations" before a BST-traversal path, "derivatives" before integration-by-parts. It must pass
  BOTH filters: (a) NOT trivial background (multiplication is not a prerequisite for Bayes' theorem — never
  list arithmetic, "basic math", or skills far below the path's level), and (b) NOT taught by any topic in
  this path and not the goal concept itself. Each is {{"name": <the bare concept name, a 1-3 word noun
  phrase, lowercase unless a proper noun — e.g. "conditional probability", "binary search trees">,
  "gloss": <one line: WHAT IT IS, a plain-language refresher>, "required_knowledge": <one line: what the
  learner MUST be able to do/know about it to follow THIS path — specific, e.g. "be able to compute P(A|B)
  from a joint table", not "understand it well">}}. Name the CONCEPT itself, never a goal phrase
  ("conditional probability", NOT "understanding conditional probability"). FEW: 0-3. An introductory path
  to a first concept in an area has NONE ([]). This is the source of truth the intro's prerequisites card
  and the prerequisite links are built from — so keep the names clean and canonical.
- The path BEGINS with exactly one orientation topic: content_role "orientation", topic_type
  "study_path_introduction", primary_action "understand". It FRAMES the area, NAMES the assumed
  prerequisites WITHOUT teaching them (a one-line "if X is new to you, review it first" — a prereq is
  mentioned, never taught), defines ONLY the terms used across ALL later topics (path-wide vocabulary; a
  term appearing in just one or two topics belongs to those topics, not the intro — and if no term is truly
  path-wide the intro defines none), and previews the topics.
  It teaches NO subtopic and has NO worked example and NO practice. Do NOT put a `foundation` teaching
  topic (e.g. "Interpreting Probability") in this slot — a prerequisite the learner is assumed to have is
  named in the intro, not made into its own teaching topic.
- Keep the path minimal (usually 3-10 topics); a standalone `foundation` topic only when the learner
  must genuinely LEARN that concept here (not merely be reminded of a prerequisite) AND a brief note in
  the next topic would not suffice. EXCEPTION: a family SURVEY (above) covers its canonical members
  even when that pushes past the usual count — breadth across the techniques IS the learning there.
- A `concept_intuition` topic is only for a concept the learner must MASTER on its own (a substantial,
  distinct learning delta). A paradigm / mental-model / "what X is" FRAMING for the topics that follow is
  NOT its own topic: set ownership_mode "embedded" with owner = the study-path introduction (or the first
  topic that uses it). NEVER create a standalone concept_intuition topic whose worked example could only be
  a trace of one of the concrete algorithms that follow — that concept is framing; embed it in the intro so
  the intro carries it, and do not spend a topic (or a forced worked example) on it.

EXAMPLE (illustrative — copy the SHAPE and granularity, NOT the subject or domain):
GOAL "learn the chain rule and the product rule" decomposes to 3 topics:
  1. study_path_introduction (role "orientation", subject_key "differentiation_rules"): frames what
     differentiation rules are, NAMES the assumed prerequisite in one line ("assumes you can take a
     basic derivative such as d/dx of x^n — if that is new, review it first"), defines the shared terms
     (derivative, composite function), previews the two rules. NO worked example, NO practice.
  2. math_formula_method (subject_key "chain_rule", primary_action "understand", prereq = topic 1): ONE
     topic that teaches the rule end-to-end — intuition, the formula, a worked example, practice.
  3. math_formula_method (subject_key "product_rule", primary_action "understand"): ONE topic, same shape.
BAD, do NOT do this:
  - splitting a concept into "Understanding the Chain Rule" + "Applying the Chain Rule" (that is ONE topic);
  - making the assumed prerequisite ("basic derivatives") its own teaching topic (it is NAMED in the
    intro, never taught);
  - a first topic typed math_formula_method / concept_intuition that carries a worked example in the
    intro's place (the opener is study_path_introduction and teaches nothing).

Return ONLY JSON of this shape:
{{
  "path_plan": {{
    "end_capability": "...",
    "end_capability_actions": ["trace", "implement"],
    "assumed_prerequisites": [
      {{"name": "conditional probability", "gloss": "the probability of one event given another has occurred",
        "required_knowledge": "be able to read and compute P(A|B) for concrete events"}}
    ],
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
