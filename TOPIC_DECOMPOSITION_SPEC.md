# Topic Decomposition & Cross-Topic Non-Overlap Spec

**Status:** Draft v7 — **FROZEN, ready to implement.** Not yet implemented.
**Owners:** topic generation (`backend/app/services/topic_generator.py`, `backend/app/prompts/topic_prompt.py`, `backend/app/core/{topic_type_definitions,course_types,course_stage_rules,course_blueprints}.py`).

**v7 changes (review round 7 — final, then frozen):** capability-level **`satisfies_end_actions`** so end-action reachability is mechanical, not prose-inferred (B.1/B.4); structured **`primary_action`** field + a **closed action verb enum** the duplicate validator compares (B.2/B.4); **prerequisite semantics separated from relationship semantics** — capability `prerequisite_capability_ids` are canonical for dependency/order; `topic_relationships` are pedagogical and induce an order edge only when declared dependency-bearing (B.2/B.4); role→type map declared a **complete** map over the 12 canonical types (B.3); explicit **implementation order** added.
**v6:** `unowned` transient-only; persisted `order_index`; mechanical "practice-capable"; three-level action matching; `policy_reason` on the topic; canonical `prerequisite_capability_ids`; max 2–3 parents; canonical-enum reconciliation with real repo state.
**v2–v5:** path-level planning artifact; explicit IDs + parent links (retire domain-token dedup heuristic); provenance; **Part C = derived blueprint variant, not a new type**; structured layered duplicate test; three repair outcomes; explicit validator ordering; policy-added capabilities; ownership on the capability record; `subject_key` = subject identity; `practice_evidence_type`; parent links as edges; tightened vague-goal fallback.

Covers: **Part A** (capability-first decomposition protocol), **Part B** (data model + deterministic validator), **Part C** (coding-implementation continuation variant — the "no background card" guarantee).

---

## 0. Why

Topic generation today specifies **constraints** but no **decomposition procedure**: the model improvises, and a deterministic layer only cleans up the result. We patch symptoms — the root cause of duplicate Prim's/Kruskal's topics, MST mis-categorization, redundant walkthroughs, coding topics filed under the wrong unit. The previous system generated **topic names**; this design generates and validates a **capability graph**.

**Design principle (binding):** the protocol is *structure*, not per-topic content. **Core invariant:**
```
Every standalone topic owns one unique capability.
Every embedded capability has one explicit owner topic.
Every required capability is reachable from prerequisites and contributes to the end capability.
```
**Data chain:**
```
scope → end capability → required-capability graph → standalone vs embedded ownership
→ topic generation → policy-added coding capabilities → parent-child edges
→ practice evidence → coverage / reachability / duplicate / ordering validation → traceable persisted path
```

---

# Part A — Goal-to-Topic Decomposition Protocol

Convert the learner goal + source into a **path plan** (end capability + ordered required capabilities), then into topics. **Do not** create topics from source headings/keywords/labels, nor because a topic can be assigned a different `topic_type`.

```
learner goal + source scope
  → scope (goal vs source)      (A.1a, A.1b)
  → end capability              (A.1)
  → required capabilities        (A.2)  ── path plan (B.1)
  → content role per capability  (A.3)
  → candidate units              (A.4)
  → split / keep / remove        (A.5, A.5a)
  → role→type assignment         (B.3)
  → ordered minimum-complete     (A.8)
  → non-overlap validation       (A.9–A.12, B.4)
```

### A.1 End capability
The concrete, action-oriented outcome (broad "learn graphs" → "represent graphs, choose a traversal, trace it, implement it"), stating what the learner will **understand, perform, explain, decide, construct, or solve**.

### A.1a Goal vs source precedence
The **learner goal defines the target scope**; source provides evidence/terminology/examples/prerequisite context, not the scope. Include a source topic outside the goal **only** as an essential prerequisite. Source scope becomes target scope **only** on an explicit "cover the whole source" request.

### A.1b No-source / vague-goal fallback
When both goal and source are broad/underspecified: a **concise introductory end capability**; **2–5 substantive topics**; foundational capabilities only; no branching into multiple advanced subdomains; **≤1** `application` topic; `study_path_introduction` only if ≥3 substantive topics; **no coding follow-ups unless the goal implies coding or the end capability includes implementation.** No hallucinated syllabus.

### A.2 Required capabilities (work backward)
For each: what precedes it; major job or support; needs its own example/practice/state-model/type; omitting it creates a gap; required by goal or source. **Retain only what is necessary** — the retained set is the path plan (B.1).

### A.3 Content roles
`orientation`, `foundation`, `terminology`, `mechanism`, `operation`, `algorithm_trace`, `implementation`, `calculation`, `proof`, `comparison`, `application`. Planning abstraction; map to `topic_type` via **B.3**.

### A.4 Candidate topics
A candidate is a topic only when it is **one independent learner capability** and can answer: what can the learner do after this; what practice proves it; in/out of scope; what later topic depends on it.

### A.5 Split / keep / remove (exactly one per candidate)
- **Separate topic** — new independent capability (BFS vs DFS; BST insert vs delete; *trace* vs *implement*; compare vs apply).
- **Keep inside a parent** → *embedded* capability (B.2): terminology for the current task, example setup, that task's edge cases, operation substeps, one-sentence paradigm framing, an invariant used by that operation, mistakes tied to the skill, complexity needed to use the method.
- **Remove** — restatements, broad categories, headings with no outcome, tiny definitions surfaced when needed, advanced siblings not required, generic background, paradigms already demonstrated, overview/review filler.

### A.5a Foundation-topic admission test
A standalone `concept_intuition` is allowed **only when removing it would make the learner unable to understand or practice the next concrete topic without more than a brief just-in-time explanation.** Otherwise fold it as an embedded capability.

### A.6 Concrete-subject rule
Build topics around the **concrete subject**. Broad categories it belongs to are taught **by example** inside the concrete topic. A paradigm is its own topic **only** when the paradigm *is* the goal, across multiple concrete examples.

### A.7 Required pairing — walkthrough → coding
Every `algorithm_walkthrough` / `data_structure_operation` gets a **separate following coding topic** by default — an `implementation_follow_up` edge (B.2) + a **policy-added implementation capability** (B.5) whose prerequisite is the walkthrough/operation capability. Walkthrough owns behavior/state/decisions/invariants/traces/edge-cases; coding owns code structure/control-flow/base-cases/mapping-steps-to-blocks/tracing-debugging. Skip **only** on explicit opt-out.

### A.8 Minimum-complete path
Shortest while complete. **Too fragmented:** adjacent topics share action/example-flow/state-model/practice-output. **Too broad:** one topic holds multiple independent actions / incompatible practice / unrelated state models / >1 outcome.

### A.9–A.11 Non-overlap, cross-type, same-subject
- **A.9:** not justified by a different title/type; duplicates teach substantially the same action/subject/state-model/example-flow/decision-rule/practice/output/core-scope.
- **A.10 cross-type:** concept→walkthrough (model vs concrete trace); terminology→operation (names/notation only); walkthrough→coding (complementary; no re-teach); compare→application (how-differ vs recognize-and-solve).
- **A.11 same-subject:** for one `subject_key`, multiple topics only when the **capability (action) changes**.

### A.12 Final validation — see B.4
> Validity rule: a path is valid only when **every topic has a unique learning delta**.

---

# Part B — Data Model & Deterministic Enforcement

### B.1 Path plan + topics — one structured call
Emitted in the **same** structured call (not outline-then-expand). **Ownership lives on the capability record** (`standalone` renders a topic; `embedded` folds into `owner_topic_id`). **`prerequisite_capability_ids` is the canonical dependency/ordering edge; `required_for` is derived.** Each capability declares **`satisfies_end_actions`** — which `end_capability_actions` it provides (mechanical, not prose-inferred).

```json
{
  "path_plan": {
    "end_capability": "Choose, trace, and implement BFS or DFS for graph traversal problems.",
    "end_capability_actions": ["choose", "trace", "implement"],
    "required_capabilities": [
      { "capability_id": "graph_representation", "description": "Represent nodes, edges, adjacency.",
        "ownership_mode": "standalone", "owner_topic_id": null,
        "prerequisite_capability_ids": [], "satisfies_end_actions": [], "basis": "goal" },
      { "capability_id": "queue_behavior_for_bfs", "description": "How the queue preserves BFS order.",
        "ownership_mode": "embedded", "owner_topic_id": "bfs_trace",
        "prerequisite_capability_ids": [], "satisfies_end_actions": [], "basis": "essential_prerequisite" },
      { "capability_id": "bfs_trace", "description": "Trace BFS with a queue and visited set.",
        "ownership_mode": "standalone", "owner_topic_id": null,
        "prerequisite_capability_ids": ["graph_representation"], "satisfies_end_actions": ["trace"], "basis": "goal" },
      { "capability_id": "bfs_implementation", "description": "Implement BFS with a queue.",
        "ownership_mode": "standalone", "owner_topic_id": null,
        "prerequisite_capability_ids": ["bfs_trace"], "satisfies_end_actions": ["implement"], "basis": "required_by_policy" }
    ]
  },
  "topics": [ /* each references a standalone capability_id */ ]
}
```

`ownership_mode`: `standalone` | `embedded` | **`unowned`** (transient planning/validation only, **FORBIDDEN in the persisted path** — an unowned required capability is a gap the validator must resolve before persist). `required_for(A) = { B : A ∈ B.prerequisite_capability_ids }`.

### B.2 Per-topic fields

```json
{
  "topic_id": "bfs_implementation",
  "order_index": 4,
  "subject_key": "breadth_first_search",
  "capability_id": "bfs_implementation",
  "primary_action": "implement",

  "topic_relationships": [ { "parent_topic_id": "bfs_trace", "relationship": "implementation_follow_up" } ],

  "primary_capability": "Implement BFS with a queue",
  "content_role": "implementation",
  "novelty_claim": "Maps the BFS trace to function structure, queue handling, and return.",
  "must_not_repeat": ["general graph terminology", "the full BFS conceptual trace"],
  "merge_reason": "Code-writing job distinct from the trace; different practice evidence.",

  "practice_target": "Implement and run BFS on a sample graph.",
  "practice_format": "coding",
  "practice_evidence_type": "write_code",
  "expected_output": "A working function returning the traversal order (or distances).",

  "basis": "goal",
  "policy_reason": null,
  "evidence_source_refs": ["SOURCE CHUNK 3"],
  "grounding_strength": "explicit"
}
```

- **`primary_action`** — a value from the **closed action verb enum** `{understand, identify, represent, trace, choose, implement, modify, debug, compare, prove, calculate, apply}`. This is what the duplicate validator compares; `primary_capability` stays free-text and learner-facing. (Backend never parses prose for the deterministic check.)
- **`order_index`** — resolved canonical position (persisted, topological). Invariant: every prerequisite edge has `prerequisite.order_index < dependent.order_index`.
- **`subject_key` = subject IDENTITY only** — the thing learned/acted on, never the action. `binary_search_tree` (capabilities `bst_search`/`bst_insert`), `breadth_first_search` (`bfs_trace`/`bfs_implementation`); `prim`/`kruskal` distinct. Same `subject_key` ⇒ not a duplicate by itself. Backend validates format and strips obvious framing (lowercase slug; strip lesson words + a *trailing generic* `algorithm`, never a domain `algorithm` — `genetic_algorithm_selection` survives); model's key is primary, no semantic reconstruction. Replaces the acronym/frequency dedup heuristic.
- **`topic_relationships`** (canonical edges) `{parent_topic_id, relationship}`. Derived views: `parent_topic_ids`; `relationship_to_parent` valid only when all edges share one relationship.
- **`practice_evidence_type`** ∈ {`explain_model`, `identify_component`, `trace_state`, `choose_method`, `solve_numeric`, `construct_proof`, `write_code`, `debug_code`, `modify_code`, `apply_pattern`}.
- **`basis`** ∈ {`goal`, `source`, `essential_prerequisite`, `required_by_policy`}; **`policy_reason`** non-null when `required_by_policy`, set on **both** the topic and its capability. **`grounding_strength`** ∈ {`explicit`, `inferred`}.

### B.3 Role → type map (single canonical enum — Open decision 1)
This is a **complete** map: every one of the 12 canonical topic types is reachable, and `mechanism` is the only role mapping to two types (resolved by the routing rule). It is not a partial subset — do not add roles to "fill it in."

| content_role | topic_type |
|---|---|
| orientation | study_path_introduction |
| foundation | concept_intuition |
| terminology | terminology_components |
| **mechanism** | **science_mechanism** *or* **process_walkthrough** (rule below) |
| operation | data_structure_operation |
| algorithm_trace | algorithm_walkthrough |
| implementation | coding_implementation (standalone or follow-up variant — Part C) |
| calculation | math_formula_method |
| proof | proof_reasoning |
| comparison | compare_distinguish |
| application | problem_solving_application |

**`mechanism` routing:** `science_mechanism` for causal/physical-biological-chemical/scientific-model; `process_walkthrough` for operational/software/system/business/procedural ordered flow.

### B.4 Validator — `validate_topic_decomposition(path_plan, topics, goal)`
```
CLEAR_DUPLICATE   → drop the later / weaker-provenance topic
SAFE_REPAIR       → apply a fixed deterministic correction
AMBIGUOUS_OVERLAP → one bounded "merge-or-justify" LLM call (action schema), else flag + keep safer path
```

**Checks:**
1. **Coverage & reachability (mechanical):** every required `standalone` capability owned by a surviving topic; every `embedded` has a real `owner_topic_id`; **no required capability `unowned`**; every topic maps to a capability; orphan (no goal/source/policy `basis`) → flag; every capability's `prerequisite_capability_ids` satisfied **earlier** (`order_index`); **for every action in `end_capability_actions`, ≥1 required standalone capability lists it in `satisfies_end_actions` AND is owned by a practice-capable surviving topic** — where **practice-capable** = standalone owner with non-null `practice_target`, valid `practice_format` + `practice_evidence_type`, and non-empty `expected_output`.
2. **Duplicate (layered), priority:** `same subject_key?` → `primary_action match (below)` → `same content_role?` → `same practice_evidence_type?` → `equivalent expected_output?` → `same dependency relationship?` → `allowed complementary pair (A.10)?` → `containment vs shared vocabulary?` `in_scope` overlap is **evidence only**.
3. **Pair distinctness:** each walkthrough→coding pair has materially different `in_scope`, `practice_evidence_type`, `expected_output`. Inherited ⇒ `SAFE_REPAIR`.
4. **Dependency DAG & ordering:** the DAG and `order_index` come from **capability `prerequisite_capability_ids` (canonical)**, NOT from `topic_relationships`. `topic_relationships` carry pedagogical/structural meaning; **only relationship types declared dependency-bearing induce a prereq/order edge.** For `implementation_follow_up`, the ordering already follows from the coding capability's prerequisite on the walkthrough/operation capability — so the topic edge need not (and does not) separately induce order. (`RELATIONSHIP_TYPES`: `implementation_follow_up` = pedagogical-only at the topic layer / dependency via capability prereq; `concept_lead_in` = similar; future `compare_with` / `alternative_to` / `related_case` = non-dependency-bearing.)
5. **Role↔type consistency** per B.3.

**Action matching (deterministic) — on the NORMALIZED `primary_action`:**
Raw model phrasing is first normalized to a canonical enum value via a closed **alias table**; the
validator then compares ONLY canonical enum values. Non-enum phrasings are normalized away **before**
the check and are never persisted.
```
normalization (raw model phrasing → primary_action enum):
  "walk through" / "simulate"   → trace
  …                             → …            (closed alias table; extend as needed)

exact enum match (post-normalization)    → CLEAR_DUPLICATE candidate
no enum match                            → AMBIGUOUS_OVERLAP
```
No broad semantic interpretation — only the curated alias table feeding the closed action enum.

**`CLEAR_DUPLICATE`** (all of): same `subject_key`; exact (post-normalization) `primary_action`; same `practice_evidence_type` + equivalent `expected_output`; no valid parent-child relationship; **and neither topic is the sole owner of a required capability not owned elsewhere.** Includes dropping a second same-capability standalone topic. Softer → `AMBIGUOUS_OVERLAP`.

**SAFE_REPAIR (corrections only):** force a paired coding topic's `practice_format = coding` / `practice_evidence_type = write_code`; replace inherited scope with the implementation template; attach a missing parent edge; repair ordering; set the derived continuation variant.

**Path-plan repair (after any drop/merge/repair):** reassign dependents to the surviving owner; redirect prerequisite edges (re-derive `required_for`); ensure no capability left `unowned`; recompute `order_index` **before** final coverage validation.

**Bounded LLM overlap — fixed action schema (not prose):**
```json
{ "decision": "keep_both | drop_topic | merge_topics | rescope_topic",
  "topic_ids": ["..."], "surviving_topic_id": "...", "reason": "...",
  "revised_fields": { "title":"...", "primary_capability":"...", "primary_action":"...", "in_scope":[], "out_of_scope":[], "practice_target":"...", "expected_output":"..." } }
```

### B.5 Validator order
```
1.  Generate path plan + topics + metadata   (ONE call)
2.  Normalize titles, fields, source evidence, roles, types, primary_action
3.  Assign/normalize topic_id, capability_id, subject_key, capability ownership, satisfies_end_actions, provenance
4.  Build prerequisite graph (capability prereqs); derive required_for; topological order_index
5.  Append required coding follow-ups + ADD their implementation capability to the graph
        (unique id; prerequisite = the walkthrough/operation capability; owned by the coding topic;
         satisfies_end_actions += [implement]; basis = required_by_policy; policy_reason on capability + topic)  ← BEFORE overlap
6.  Assign topic_relationships + implementation_follow_up variant
7.  Validate role ↔ type consistency
8.  Validate capability ownership + walkthrough→coding pair separation
9.  Detect clear duplicates (primary_action) + apply safe repairs
10. Path-plan repair (reassign ownership, redirect edges, recompute order_index)
11. Bounded merge-or-justify ONLY for unresolved AMBIGUOUS_OVERLAP
12. Reindex, FINAL coverage + reachability validation (assert no `unowned`; all end actions satisfied), persist
13. Log every action + rule fired
```

### B.6 Path-length precedence & consolidated coding follow-ups
Resolve "3–10 topics" vs mandatory pairs so coding is **never** dropped to hit the cap: preserve required capabilities → preserve walkthrough→coding follow-ups → remove redundant foundation/paradigm/filler → merge only shared support → consolidate implementations only under the rule below → allow >10 when source requires.

**Consolidated coding follow-up — hard rule.** One implementation topic covers **multiple** parents only when ALL hold: (1) source/goal explicitly treats them as one artifact; (2) one function/class/interface and one coherent code structure; (3) separate practice would be substantially repetitive; (4) a `topic_relationships` edge for **every** parent. **At most 2–3 parents**; beyond → require explicit shared-artifact justification and route to `AMBIGUOUS_OVERLAP`. Otherwise each parent gets its own follow-up.

### B.7 Telemetry & cost
Log every validator action + rule. Distill operational rules into the prompt; add `prompt_cache_key` to the topic call. Existing helpers (`_drop_paradigm_only_topics`, `_drop_same_type_subject_duplicates`, `_append_missing_coding_topics`) are **subsumed**; the domain-token heuristic is **retired** in favor of `subject_key`.

### B.8 Persistence & audit
**Persist on the topic:** `topic_id`, `order_index`, `subject_key`, `capability_id`, `primary_action`, `topic_relationships` (+ derived views), provenance (`basis`/`policy_reason`/`grounding_strength`), resolved blueprint variant, `practice_format`, `practice_evidence_type`, `expected_output`. **Persist on the path:** `required_capabilities` with `ownership_mode`/`owner_topic_id`/`satisfies_end_actions`/`basis` (never `unowned`). **Audit blob (not learner-facing):** `merge_reason`, `novelty_claim`, `must_not_repeat`, duplicate scores, validator evidence, `generated → validated → repaired → persisted` trace.

---

# Part C — Coding Implementation Continuation Variant

### C.1 The guarantee
> A coding follow-up after a walkthrough/operation **omits the `background` card** — it must not re-explain the algorithm. Everything else is a normal `coding_implementation`: the **same coding blueprint and all the same required card contracts**, with **`background` removed from the resolved card sequence**.

**Not a new topic type.** The learner's job is unchanged; only lesson composition differs.

### C.2 Model
```
topic_type = coding_implementation
no implementation_follow_up edge      → normal coding blueprint (resolved WITH background)
implementation_follow_up edge present → SAME blueprint, background removed from resolved sequence  ← derived
```

### C.3 When each applies
- **`implementation_follow_up`** (no background) — the A.7 pairing topic; appender sets the edge + the policy capability (B.5).
- **standalone** (with background) — no parent edge.

### C.4 Blueprint selection
`course_blueprints.py` checks for an `implementation_follow_up` edge: present → resolve the coding sequence **without `background`**; else full. One blueprint, one conditional omission.

### C.5 `is_coding_type` predicate
```python
def is_coding_type(topic_type: str) -> bool:
    return topic_type == "coding_implementation"
```
Frontend: 0 `topic_type` references → no frontend change.

### C.6 Migration
**No topic-type migration.** Persistence migration depends on storage: JSON-backed → versioned metadata shape; relational → schema migration for the new persisted fields (B.8). Existing topics default to standalone. "No DB migration" ≠ "no persistence work."

---

## Implementation order
```
1. Centralize the canonical topic-type enum (12); derive role→type map, API schema, frontend type from it;
   clean legacy ids out of course_stage_rules.py.
2. Add path-plan / capability-graph schemas (B.1) + per-topic fields (B.2).
3. Add primary_action (closed enum) + satisfies_end_actions.
4. Build ownership, ordering (order_index), and reachability validator (B.4.1, B.4.4).
5. Implement the coding-follow-up graph mutation (B.5 step 5).
6. Add duplicate detection + SAFE_REPAIR (B.4.2/B.4.3, action matching).
7. Add the bounded AMBIGUOUS_OVERLAP call (action schema).
8. Persist metadata + audit blob (B.8).
9. Move the legacy topic-generation helpers behind the new validator (subsume / retire).
```

## Tests

### Blueprint / unit
- coding topic with an `implementation_follow_up` edge → resolved sequence **no** `background`; without → **with**; other contracts identical.
- `is_coding_type` true; solver/prepass/caps/highlighting work for both variants.
- appender sets the edge **and** adds the implementation capability (`satisfies_end_actions=["implement"]`, `basis=required_by_policy`, `policy_reason` on capability + topic).

### Validator outcomes
- **CLEAR_DUPLICATE:** "Understanding BFS" + "BFS Overview" (same subject / `primary_action` / evidence / output, neither a sole owner) → later dropped.
- **SAFE_REPAIR:** coding follow-up inherited `trace` practice → forced to coding, scope replaced.
- **AMBIGUOUS_OVERLAP:** "Graph Search Patterns" + "Choosing BFS or DFS" → bounded merge-or-justify.
- **SOLE-OWNER GUARD / UNOWNED ASSERT / ORDER / MAX-PARENT:** redundant-but-sole-owner kept; persisted `unowned` fails; `prereq.order_index < dependent.order_index`; >3 parents → AMBIGUOUS_OVERLAP.
- **END-ACTION COVERAGE:** drop the only `implement`-satisfying topic → reachability fails.

### Behavior (end-to-end)
- **Merge sort / MST / BFS-DFS / BST:** as in v6 (one walkthrough + one follow-up; Prim/Kruskal distinct; `queue_behavior_for_bfs` embedded; `subject_key=binary_search_tree` with distinct operations).
- **Standalone coding goal:** one standalone `coding_implementation` (with background).
- **Goal narrower than source / vague goal / non-CS / regeneration:** scoped path; foundational-only with no coding; no algorithm-specific assumptions; scope change leaves no orphaned prereqs/stale pairs/`unowned`.

---

## Open decisions
1. **Single canonical type enum (reconcile before the role→type map is canonical).** The **12** canonical types live in `topic_type_definitions.py` **and** `course_types.py` (consistent), **but `course_stage_rules.py` still carries ~8 legacy ids** (`system_architecture`, `debugging_diagnosis`, `tool_workflow`, `design_decision`, `compare_decide`, `application_historical`, `problem_solving_pattern`, `system_workflow_debugging`) and `topic_prompt.py` keeps a deny-list. **Action:** one backend `TOPIC_TYPES` constant (the 12); validator map, API schema, frontend type all derive from it; clean the legacy ids. This spec must not become a second type source of truth.
2. **`subject_key` collisions:** when normalization would collide two genuinely-distinct subjects, prefer the model's longer proposed key over aggressive stripping.

## Non-goals
- No per-subject hard-coding (no algorithm-name → topic-set tables).
- No new topic type; no lesson-*content* change beyond the follow-up variant's removed background card.
- No frontend behavior change.
