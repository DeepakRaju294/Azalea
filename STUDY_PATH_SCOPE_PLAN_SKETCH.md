# Study-Path Scope Plan — implementation sketch (rev 4)

> A pragmatic, failure-grounded sketch for the up-front path plan. The full typed design is
> `STUDY_PATH_SCOPE_SPEC.md` (Draft v3.2, frozen); this sketch is the "why + minimal build", written against the
> concrete failures observed in the July 2026 TCP-congestion-control review rounds.
> Status: **direction approved through three review rounds; Phase 0 approved to build** (with the rev-4 payload
> clarifications); the §12 decisions + §13 contract items gate Phase 1.
>
> **rev 2** corrected the first review (delta-based uniqueness, teaching ownership, compound goals, boundary-aware
> parent demotion, derived depth, repair split, content-claims, versioning). **rev 3** folded in the second review
> (per-ACTION goal ownership; semantic delta-distinctness; definition ⟂ teaching ownership; within-topic `uses`;
> audited claims; structural anchors; derived `IntroPlan`; §12 gate decisions). **rev 4** folds in the third:
> canonical identity gets provenance/confidence + first-class Phase-0 metrics; Phase-0 payload includes skeletal
> `section_plan` (else F3 is unmeasurable); distinctness thresholds come from HUMAN-LABELED fixtures; `scope_out`
> = must-not-TEACH; immutable plan ⟂ per-run `GenerationRevision`; input fingerprint; intro definition budget;
> operational independence for the claim audit; DAG-scoped partial-failure behavior.

## 1. The problem, stated as observed failures

Every recurring defect this session has the **same root**: the pipeline never commits to a plan. It asks the
LLM to decide structure *and* author content at the same time, re-deriving the topic set, each topic's
type/depth, and the prereq/topic split **on every generation** — then we patch symptoms with syntactic guards.
On the *same goal* ("learn TCP congestion control") across generations we saw:

| # | Failure (live) | Why it happened | Prevent upstream | Detectable/repairable downstream |
|---|----------------|-----------------|:----------------:|:--------------------------------:|
| F1 | Duplicate topics ("Algorithms"+"Mechanisms"; two intros) | model split one concept into synonym capabilities | ✅ | ✅ (collapse) |
| F2 | Foundation leaked in as a topic ("TCP Overview") | a parent-of-goal concept tagged as a normal topic | ✅ | ✅ (demote) |
| F3 | Depth inversion — goal topic shallow, foundation deep | per-topic type chosen by the LLM, unanchored to the goal | ✅ | ⚠️ only via regeneration |
| F4 | Scope drift — lesson teaches beyond its declared scope | `in_scope` advisory, never enforced against content | ✅ | ✅ (post-gen audit + regen) |
| F5 | Cross-topic repetition (same definitions/phases twice) | each lesson validated in isolation; no whole-path view | ✅ | ✅ (post-gen audit + regen) |

The plan does not eliminate downstream audits — it gives them **something authoritative to validate against**.

## 2. Core idea

**Separate planning from authoring.** One planning pass turns the goal into an authoritative, versioned
`PathPlan` before any lesson is generated. Generation then **fills** the plan — it does not re-decide structure.
The consistency chain the design must preserve end-to-end:

```
goal actions → learning deltas → teaching/definition ownership → dependency-ordered topics
→ section plans → generated prose + authored claims → independent claims audit → scope + whole-path enforcement
```

## 3. The plan (data model)

Three ideas do the real work: **subject identity is separate from learning delta**; **scope is ownership**
(teaches / uses / reviews / must-not-teach), with **definition ownership separate from facet-level teaching
ownership**; and the **intro is derived, not a topic**. Underneath all of them sits one load-bearing dependency:
**canonical concept identity must be trustworthy** (see the callout below).

```
PathPlan                                          # IMMUTABLE planning result (runtime state lives on GenerationRevision)
  plan_id, schema_version, planner_version
  input_fingerprint                               # hash over: normalized goal, goal-scope pref, depth/level pref,
                                                  #   domain classification, source revision, planner + policy versions
  goal_targets:      [GoalTarget]
  prerequisites:     [Prereq]
  intro:             IntroPlan                    # DERIVED — never a PlannedTopic
  topics:            [PlannedTopic]               # ordered by dependency, not list position
  definition_owners: { concept_key -> topic_id | "intro" }
  teaching_owners:   { (concept_key, facet_or_action) -> topic_id }
  validation_status: planned | repaired | ambiguous
  repair_log:        [RepairAction]

GenerationRevision                                # ONE generation attempt against a plan — mutable runtime state
  plan_id                                         # same inputs -> reuse plan; scope-changing feedback -> NEW plan;
                                                  #   planner upgrade alone NEVER silently reinterprets an existing path
  execution_status                                # running | complete | generation_scope_failed
  fallback_mode                                   # none | fallback_legacy (degraded, marked, measured)
  per_topic_status                                # ready | regenerating | blocked_by_dependency | scope_failed

CanonicalConcept                                  # identity is EVIDENCED, not asserted
  key, canonical_label, aliases, parent_key
  source:     ontology | deterministic | model | resolver
  confidence                                      # low-confidence equivalence -> semantic replan or visibly
                                                  #   ambiguous; NEVER a silent merge

SubjectIdentity   { canonical_concept_key, parent_concept_key, aliases }

LearningDelta                                     # the unit of UNIQUENESS (invariant #2 is the real test)
  subject_identity
  facet            : intuition | mechanism | derivation | trace | comparison | implementation | application
  learner_action
  expected_evidence

GoalTarget        { subject_identity, required_actions: [action], owners: {action -> topic_id} }

PlannedTopic
  topic_id, provenance
  learning_delta:   LearningDelta
  role:             goal_owner | supporting | application
  prerequisite_topic_ids                          # explicit dependency edges -> ordering derived + checkable
  teaches:          [concept]                     # instruction this topic OWNS (per teaching_owners)
  uses:             [concept]                     # prior knowledge OR own earlier sections; may repeat
  reviews:          [concept]                     # deliberate short reinforcement (spiral policy)
  scope_out:        [concept]                     # semantics: MUST NOT TEACH (define/derive/fully explain).
                                                  #   NOT "must not appear" — a concept may be in uses AND scope_out
  section_plan:     [Section]                     # the real structural authority (drives the blueprint)
  depth                                           # DERIVED SUMMARY of section_plan

Section                                           # minimum shape — full detail in the frozen spec
  section_id
  pedagogical_function : orient | define | explain_mechanism | derive | worked_trace | compare | edge_cases | practice_setup
  teaches:  [concept]                             # enables within-topic `uses`
  uses:     [concept]
  required_evidence
  cardinality

IntroPlan                                         # presentation/orientation infrastructure, DERIVED from the plan
  prerequisite_refs
  definition_keys                                 # STRICT eligibility + budget — see below
  roadmap_topic_ids
  framing_claims

Prereq   { subject_identity, gloss, required_knowledge, relation: parent | earlier_subject, within_goal_boundary: bool }
```

**Ownership-role contract (unambiguous form):**
- `uses` → may mention/apply. `reviews` → may briefly reinforce. `scope_out` → may not define/derive/fully
  explain. Neither `uses` nor `reviews` → incidental mention only.

**Intro definition budget:** a term is intro-eligible only if it is (a) required to understand the roadmap or the
prerequisite boundary, (b) used by multiple later topics, (c) briefly explainable without teaching a substantive
mechanism — and the count is capped by a small product budget. "Path-wide" alone does NOT make a term intro-owned;
a central term (e.g. `cwnd`) may deliberately belong to the first substantive topic instead.

**⚠ Canonicalization is the hardest remaining Phase-0 risk.** Every invariant below assumes concept identity is
trustworthy; `congestion_window_growth` vs `cwnd_adjustment` evading ownership checks is the old `subject_key`
failure at finer granularity. Hence identity carries provenance + confidence, low-confidence merges are never
silent, and Phase 0 measures canonicalization explicitly (§9).

## 4. How the plan is produced

A bounded planning call (LLM proposes, deterministic layer certifies) emits the `PathPlan`. Planning invariants
(all must pass before any lesson generates):

1. **Goal-action coverage:** every required action covered by exactly ONE goal-owning delta; every goal-owning
   delta maps to ≥1 required action. (One target may own several deltas — trace + implement.)
2. **Semantic delta distinctness:** two deltas on the same subject need **materially distinct evidence
   obligations and non-overlapping primary teaching claims** — operationalized as `teaches`-overlap +
   `expected_evidence` comparison. Thresholds are fixed by **human-labeled fixtures** (`merge` /
   `keep_separate` / `ambiguous`) — NOT by agreement with shipped paths (they are known-defective). The fixture
   set must include the hard pairs: algorithms↔mechanisms, intuition↔derivation, trace↔implementation,
   formula↔application, definition↔operation, comparison↔two-technique-topics, introductory-foundation↔prereq,
   review↔duplicate-teaching. Facet-label inequality alone NEVER justifies two topics.
3. **Prereq/topic boundary:** a parent-of-goal concept outside the goal boundary is a `Prereq`; a parent
   explicitly requested or required by an introductory goal may be a topic.
4. **Ownership uniqueness:** one `definition_owner` per concept; ≤1 `teaching_owner` per (concept, facet/action);
   `uses`/`reviews` unrestricted; >1 treatment of the same (concept, facet) requires an explicit spiral policy.
5. **Dependency soundness:** `prerequisite_topic_ids` form a DAG; every `uses` concept is an external prereq,
   taught earlier, intro-owned, or taught by an **earlier section of the same topic**.
6. **Prereq budget (POLICY, not validity):** >3 prereqs → group under a canonical parent or narrow the goal;
   never silently omit a real dependency.

**Repairs are split:** deterministic (exact-duplicate drop, identical-identity merge, alias normalization,
dangling-reference fixes) vs **semantic → targeted replan** (facet distinctness, ownership splits, goal-boundary
parent calls, low-confidence identity equivalence). Conflating these recreates the subject-key heuristic.

## 5. How generation consumes it

- `section_plan` drives the card blueprint (no per-topic type re-guess). **Domain routing INFORMS planning** —
  section templates, allowed evidence types, validators, renderers — but never overrides the accepted plan.
- Each lesson emits **authored content-claims** with **structural anchors** (same contract as interactive-link
  anchors; raw offsets break under transformation passes):
  ```
  authored_claims: [ { concept_key, relation: defines|explains|derives|applies|mentions,
                       anchor: {card_id, section_id, field, item_index}, content_hash } ]
  ```
- **Claims are audited, and independence is operational, not nominal.** The audit pass: (a) never receives the
  authored claim labels as suggestions, (b) reads the FINAL post-transformation content, (c) produces its own
  relations + anchors, (d) is evaluated separately against labeled spans, (e) reports both omissions (false
  negatives) and relation misclassifications. `claim_disagreements` = authored ↔ audited delta, a measured
  quantity gating Phase-2 promotion. (Whether the auditor is a different model, a deterministic classifier, or
  a hybrid is an implementation choice — the five properties above are the contract.)
- **Scope validator severity tiers** (against audited claims):
  - `mentions`/`applies` on a `uses` concept → fine.
  - incidental mention of a `scope_out` concept → non-blocking warning.
  - repairable drift (short re-explanation of another topic's concept) → regenerate the offending section.
  - **blocking:** defines/derives/fully-explains a concept owned by another topic → lesson not marked ready.
- **Path-level consequence of a blocked topic follows the DAG:** a failed topic blocks its dependent
  *descendants* (`blocked_by_dependency`), not independent or already-valid topics. Completed earlier topics
  remain usable; the failed topic shows as regenerating/repairing. (This is a practical payoff of explicit
  dependency edges — state it, don't leave it implicit.)
- **Whole-path audit:** definition/teaching owners honored (a concept fully defined twice = F5); every
  `GoalTarget.required_action` actually delivered. Repeated *terminology* fine; repeated *instructional
  treatment* is the defect.

## 6. What it subsumes

Every guard built this session becomes a plan invariant or a retiring backstop:
- `_collapse_near_duplicate_topics` → invariant #2. `_demote_parent_of_goal_topics` → invariant #3 (the shipped
  guard is its conservative deterministic subset).
- `_fold_prereq_topics`, foundation-fold, `_drop_umbrella_prereqs`, `_cross_topic_foundations` → prereq
  derivation + invariants #3/#6.
- domain gate / per-topic type remap → `section_plan` for structure; domain routing repositioned as a planning
  input. Intro passes → `IntroPlan`.

## 7. Build path (shadow-first; stage the model so measurement isn't blocked)

- **Phase 0 (shadow, `AZALEA_STUDY_PATH_SCOPE`):** produce the `PathPlan` skeleton = identity + delta +
  dependencies + roles + ownership maps **+ skeletal `section_plan`** (section_id, pedagogical_function,
  required_evidence, teaches/uses — no cards, no claims). Without the section plan, planned-vs-shipped **depth
  cannot be compared and F3 is unmeasurable**. Run invariants #1–#6. Two logged comparisons, zero user impact:
  - `PathPlan ↔ shipped topic structure` — F1/F2/F3 + prereq/ordering disagreement.
  - `PathPlan ↔ generated lesson claims` — only once lessons emit claims; F4/F5.
  Canonicalization metrics (§9) are first-class Phase-0 outputs. Labeled fixtures fix the invariant-#2 thresholds.
- **Phase 1 (plan drives structure):** topic list + prereqs + intro + `section_plan`/`depth` come from the plan.
  Prevents F1/F2/F3. `fallback_legacy` = measured degradation with an explicit choice (legacy + degraded marker,
  retry planning, or conservative single-topic+orientation fallback).
- **Phase 2 (plan enforces content):** authored claims + independent audit + scope validator + whole-path audit.
  Closes F4/F5.
- **Phase 3:** retire the redundant post-hoc guards.

## 8. Failure behavior + versioning

- **Plan (immutable):** `validation_status: planned | repaired | ambiguous` — properties of the planning result.
- **Run (mutable, on `GenerationRevision`):** `fallback_mode`, `execution_status`, per-topic
  `ready | regenerating | blocked_by_dependency | scope_failed` — outcomes of one attempt against the plan.
- Regeneration reuses `plan_id` when the `input_fingerprint` matches; content-only feedback reuses the plan;
  scope-changing feedback or a changed fingerprint explicitly creates a NEW plan; a planner upgrade alone never
  silently reinterprets an existing path.

## 9. Promotion gates (shadow → Phase 1)

Measured on the labeled golden set + production shadow (counts/distances):
- Duplicate-delta rate; parent-as-topic disagreement; planner-vs-shipped topic-count delta; repeated
  teaching-owner rate; invalid-plan rate; deterministic-repair rate; replan rate.
- **Canonicalization health (first-class):** alias-resolution rate, unresolved-canonicalization rate,
  low-confidence match rate, same-goal concept-key stability, human disagreement with canonical merges,
  keys-collapsed-per-identity distribution.
- **Same-goal stability** across repeated runs — equivalent learning deltas even when titles vary (weight heavily).
- (Phase-2 gates) scope-violation rate; claim-disagreement rate; scope-auditor false-positive rate; human
  acceptance on the golden set.

## 10. Explicit non-goals

- Not adapters, not study-materials, not the practice system (out of scope by direction).
- Not factual/numeric correctness of non-adapter content — the plan constrains **structure and scope**, not
  truth. Self-inconsistency and scope violations become catchable; ground-truth accuracy still needs a verifier.

## 11. The one-line pitch

We have been fixing "the model picked a bad structure" one symptom at a time. The scope plan fixes it once:
**decide the path — goal actions, prereqs, per-delta topics with unique definition + teaching ownership,
dependency order, a derived intro, and section plans — authoritatively before generation, and make generation
fill it instead of re-inventing it.** The rev-2/3/4 corrections are what keep the planner from becoming a
fancier subject-key heuristic.

## 12. Phase-1 gate: five decisions (second review — resolved)

1. **Multiple goal-owning deltas per target** — ADOPTED (per required action).
2. **Definition ⟂ teaching ownership** — ADOPTED.
3. **Semantic delta distinctness beyond tuple equality** — ADOPTED; thresholds from human-labeled fixtures.
4. **Independent claim verification** — ADOPTED; independence contract in §5.
5. **Intro explicitly modeled** — ADOPTED (`IntroPlan`, derived, budgeted).

## 13. Phase-1 contract items (third review — tracked)

Resolved in rev 4: plan ⟂ run status separation; input fingerprint; `scope_out` = must-not-teach; intro
definition eligibility + budget; operational claim-audit independence; DAG-scoped partial-failure behavior;
Phase-0 payload includes skeletal section plans; canonicalization as a Phase-0 metric with evidenced identity.
Remaining implementation choices (decide in the PR, not by another design pass): the concrete auditor
implementation (model/deterministic/hybrid); the Phase-1 fallback choice; the intro definition budget value;
distinctness thresholds (from the labeled fixtures).

> **Implementation note:** Phase-1A plumbing already exists dark in `backend/app/core/study_path_scope/`
> (schema/identity with canonical keys + aliases, mappings, construction incl. `LessonSectionPlan`, planning
> validation, shadow telemetry, builder; 76 core + 7 shadow-bridge tests). Sketch vocabulary maps onto the frozen
> spec's (`LearningDelta` ≈ ConceptIdentity(key, facet) + action; `teaches/uses` ≈ mappings). The genuinely NEW
> items to fold in during Phase 1: `teaching_owners` map, the audited-claims contract, identity
> provenance/confidence, the input fingerprint, and the plan⟂run status split.
