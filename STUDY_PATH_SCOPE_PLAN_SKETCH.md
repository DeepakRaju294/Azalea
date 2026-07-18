# Study-Path Scope Plan — implementation sketch (rev 8)

> A pragmatic, failure-grounded sketch for the up-front path plan. The full typed design is
> `STUDY_PATH_SCOPE_SPEC.md` (Draft v3.2, frozen); this sketch is the "why + minimal build", written against the
> concrete failures observed in the July 2026 TCP-congestion-control review rounds.
> Status: **Phase 0 APPROVED TO IMPLEMENT after iterative review; no further architectural review needed before
> starting it.** The §12/§13 items gate Phase 1/2. Remaining work is contract tightening, not system redesign.
>
> **Changelog** (details in git history): rev 2 — delta-based uniqueness, ownership model, compound goals,
> repair split. rev 3 — per-action goal ownership, semantic distinctness, definition ⟂ teaching ownership,
> audited claims, derived IntroPlan. rev 4 — identity provenance/confidence + canonicalization metrics, skeletal
> section_plan in Phase 0, labeled-fixture thresholds, scope_out = must-not-teach, plan ⟂ run, fingerprint,
> intro budget, DAG-scoped failure. rev 5 — stable `delta_id` keys ownership + claims; `treatment_level`;
> fingerprint split (input ⟂ build provenance); depth feature projection; phase boundaries; spec precedence.
> rev 6 — fixed stale invariant-4 key + phase-boundary contradiction; lesson-level definition-ownership rule;
> `AuditedClaim` shape; `concept_treatments` marked derived; Phase-0-evidenced promotion thresholds.
> rev 7 — `LearningDelta.teaches_concept_keys` = the authoritative taught-concept set (derivation was declared
> from a source that lacked the data); `PathPlan.concepts` canonical-identity registry; distinctness thresholds
> follow the §9 evidence process (removed from PR choices); derived-index consistency invariant (#7); only
> `planned|repaired` plans are generation-eligible.
> rev 8 — Phase 0 runs invariants #1–#7; `union(Section.teaches) == teaches_concept_keys` (subset left planned
> content unassigned with no Phase-1 audit to catch it); `definition_owners` covers in-scope taught concepts
> ONLY (external prereqs excluded — a prereq gloss is not a definition; prereq ∩ taught = ∅).

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
  plan_id, schema_version
  planning_input_fingerprint                      # WHAT was planned: normalized goal, goal-scope pref, depth/level
                                                  #   pref, domain classification, source revision, policy-affecting
                                                  #   user inputs. Governs plan REUSE (same fingerprint -> reuse).
  plan_build_provenance                           # HOW it was planned: planner_version, policy_version,
                                                  #   schema_version. A newer planner => "newer plan available"
                                                  #   marker on existing paths — NEVER an automatic replacement.
  concepts:          { concept_key -> CanonicalConcept }   # the identity REGISTRY — every concept key anywhere in
                                                  #   the plan (prereqs, definitions, deltas, sections, uses/reviews/
                                                  #   scope_out, ownership indexes) must resolve through it, so
                                                  #   provenance/confidence TRAVEL WITH the immutable plan. (If the
                                                  #   frozen spec's identity records already store this, reference
                                                  #   that registry — do not create a second copy.)
  goal_targets:      [GoalTarget]
  prerequisites:     [Prereq]
  intro:             IntroPlan                    # DERIVED — never a PlannedTopic
  topics:            [PlannedTopic]               # ordered by dependency, not list position
  definition_owners: { concept_key -> topic_id | "intro" }   # IN-SCOPE taught concepts ONLY. External
                                                  #   prerequisites are explicitly excluded — a prereq is linked,
                                                  #   never defined here (its gloss is not a definition), so every
                                                  #   entry identifies an actual definition within THIS path.
  teaching_owners:   { delta_id -> topic_id }     # AUTHORITATIVE ownership: the delta identity, never an ad-hoc tuple
  concept_treatments: { (concept_key, delta_id) -> topic_id }   # DERIVED index (from teaching_owners + deltas) for
                                                  #   validation/queries — never independently authored. Authority:
                                                  #   teaching_owners + LearningDelta authoritative; PlannedTopic.teaches
                                                  #   and concept_treatments derived (three hand-kept copies would drift)
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
  delta_id                                        # STABLE identity — ownership maps and claims reference THIS
  subject_identity
  facet            : intuition | mechanism | derivation | trace | comparison | implementation | application
  learner_action
  expected_evidence
  teaches_concept_keys                            # the AUTHORITATIVE taught-concept set for this delta.
                                                  #   union(Section.teaches) == teaches_concept_keys — EQUALITY:
                                                  #   a concept needs no dedicated section (sections teach several),
                                                  #   but every planned concept must be ASSIGNED to some section,
                                                  #   else the section plan drives generation with planned content
                                                  #   unassigned and Phase 1 has no claims audit to catch the
                                                  #   omission. An unassigned concept = INVALID plan, pre-generation.
                                                  #   PlannedTopic.teaches == owner's teaches_concept_keys;
                                                  #   concept_treatments = teaches_concept_keys × delta_id × owner.
                                                  #   Invariant-#2 `teaches`-overlap reads THIS set — one stable source.

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

**Ownership-role contract (unambiguous form) — for a concept the topic does NOT own in `teaches`:**
`uses` → may mention/apply. `reviews` → may briefly reinforce. `scope_out` → may not define/derive/fully
explain. Absent from all three → incidental mention only. (An owned concept is of course taught freely —
the roles constrain non-owned concepts.)

**Intro definition budget:** a term is intro-eligible only if it is (a) required to understand the roadmap or the
prerequisite boundary, (b) used by multiple later topics, (c) briefly explainable without teaching a substantive
mechanism — and the count is capped by a small product budget. "Path-wide" alone does NOT make a term intro-owned;
a central term (e.g. `cwnd`) may deliberately belong to the first substantive topic instead.

**⚠ Canonicalization is the hardest remaining Phase-0 risk.** Every invariant below assumes concept identity is
trustworthy; `congestion_window_growth` vs `cwnd_adjustment` evading ownership checks is the old `subject_key`
failure at finer granularity. Hence identity carries provenance + confidence, low-confidence merges are never
silent, and Phase 0 measures canonicalization explicitly (§9). **Ambiguity propagates by impact:** a
low-confidence identity that affects goal ownership, duplicate determination, parent/prereq classification, or
dependency ordering makes the whole plan `ambiguous`; one affecting only an optional alias leaves the plan valid
with an unresolved-alias warning.

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
4. **Ownership uniqueness (keyed on `delta_id`):** one `definition_owner` per IN-SCOPE definable concept —
   external prerequisites are excluded (no internal definition owner; a prereq gloss never counts as a
   definition; a concept is never simultaneously an external prereq AND internally taught). Every `delta_id` has
   exactly one teaching owner; every `(concept_key, delta_id)` treatment has at most one topic owner unless an
   explicit spiral policy authorizes another. Referential checks: every planned delta has an owner; every
   teaching owner references an existing delta + topic; every concept treatment references the topic that owns
   its delta; a topic's `teaches` entries are all represented in `concept_treatments`. `uses`/`reviews`
   unrestricted.
5. **Dependency soundness:** `prerequisite_topic_ids` form a DAG; every `uses` concept is an external prereq,
   taught earlier, intro-owned, or taught by an **earlier section of the same topic**.
6. **Prereq budget (POLICY, not validity):** >3 prereqs → group under a canonical parent or narrow the goal;
   never silently omit a real dependency.
7. **Derived-index consistency:** every derived ownership/topic/concept index must equal its recomputation from
   the authoritative fields (`LearningDelta.teaches_concept_keys`, `teaching_owners`, `definition_owners`).
   Derived indexes are REBUILT after every repair, never patched individually — this catches stale `teaches`,
   missing treatments, indexes referencing removed topics, and delta-merges that skipped the rebuild.

**Generation eligibility:** only `planned` and `repaired` plans may drive generation; an `ambiguous` plan is a
valid immutable *planning result* retained for telemetry/replanning, but it is never consumable.

**Repairs are split:** deterministic (exact-duplicate drop, identical-identity merge, alias normalization,
dangling-reference fixes) vs **semantic → targeted replan** (facet distinctness, ownership splits, goal-boundary
parent calls, low-confidence identity equivalence). Conflating these recreates the subject-key heuristic.

## 5. How generation consumes it

- `section_plan` drives the card blueprint (no per-topic type re-guess). **Domain routing INFORMS planning** —
  section templates, allowed evidence types, validators, renderers — but never overrides the accepted plan.
- Each lesson emits **authored content-claims**, bound to the plan at the DELTA level (a concept-level claim
  cannot enforce facet-level ownership — two topics can both "explain tcp_congestion_control" while one teaches
  the mechanism and the other Reno recovery), with **structural anchors** (same contract as interactive-link
  anchors; raw offsets break under transformation passes):
  ```
  authored_claims: [ { delta_id,                   # binds the claim to the plan's ownership model
                       concept_key,
                       relation:        defines | explains | derives | applies | mentions,
                       treatment_level: mention | use | brief_review | substantive_instruction,
                       anchor: {card_id, section_id, field, item_index}, content_hash } ]
  ```
  The audited counterpart is NOT forced to bind uncertain content to an existing delta — an unbound substantive
  claim is precisely how the system detects that generation invented an UNPLANNED learning delta:
  ```
  AuditedClaim: { concept_key, proposed_delta_id: str|null, proposed_facet, proposed_action,
                  relation, treatment_level, anchor, confidence }
  ```
  Unbound (`proposed_delta_id = null`) substantive claims route to review rather than silently passing.
- **Claims are audited, and independence is operational, not nominal.** The audit pass: (a) never receives the
  authored claim labels as suggestions, (b) reads the FINAL post-transformation content, (c) produces its own
  relations + anchors, (d) is evaluated separately against labeled spans, (e) reports both omissions (false
  negatives) and relation misclassifications. `claim_disagreements` = authored ↔ audited delta, a measured
  quantity gating Phase-2 promotion. (Whether the auditor is a different model, a deterministic classifier, or
  a hybrid is an implementation choice — the five properties above are the contract.)
- **Scope validator severity tiers** — keyed on `treatment_level` (operational, not inferred from `explains`):
  - `mention` → normally harmless (a `scope_out` mention = non-blocking warning).
  - `use` → requires the concept be a prereq, an earlier topic's `teaches`, intro-owned, or an earlier
    same-topic section.
  - `brief_review` → allowed only when the concept is in `reviews` (else repairable drift → regenerate section).
  - `substantive_instruction` → requires this topic to be the matching `teaching_owner` (via `delta_id`);
    otherwise **blocking** — the lesson is not marked ready.
  - **`relation = defines` is checked against `definition_owners` separately from delta ownership:** it requires
    the current topic (or intro) to equal `definition_owners[concept_key]`. A topic may own a mechanism delta
    involving `cwnd` without owning `cwnd`'s definition — a second definition is **blocking at the lesson level**
    even when the topic legitimately owns a different facet of that concept (not deferred to the whole-path audit).
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
  cannot be compared and F3 is unmeasurable**. Run invariants #1–#7 (derived-index consistency is especially
  live during shadow construction + deterministic repair — not deferred). Two logged comparisons, zero user impact:
  - `PathPlan ↔ shipped topic structure` — F1/F2/F3 + prereq/ordering disagreement.
  - `PathPlan ↔ generated lesson claims` — only once lessons emit claims; F4/F5.
  **Depth is compared via a deterministic feature projection**, not planned-`depth` vs legacy type labels
  (incompatible representations): project both sides onto {substantive_section_count,
  evidence_bearing_section_count, has_worked_trace, has_derivation, has_practice_setup} — planned from
  `section_plan`, shipped inferred from final cards — and diff the vectors.
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
- Regeneration reuses `plan_id` when the `planning_input_fingerprint` matches; content-only feedback reuses the
  plan; scope-changing feedback (a changed input fingerprint) explicitly creates a NEW plan. A change in
  `plan_build_provenance` alone (planner/policy upgrade) surfaces a "newer plan available" marker — the old plan
  stays attached to its generation revisions until an explicit migration or replan.

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

**Exit criteria are recorded from Phase-0 evidence, then approved — never chosen inside an implementation PR.**
Phase 0 exists partly to establish baselines; before promotion, explicit thresholds are set for at least:
invalid/ambiguous-plan rate, same-goal delta stability, human disagreement with canonical merges, false-merge and
false-split rates on the labeled fixtures, unresolved-identity rate, parent/prereq classification agreement, and
depth-projection agreement (or human preference).

## 10. Explicit non-goals

- Not adapters, not study-materials, not the practice system (out of scope by direction).
- Not factual/numeric correctness of non-adapter content — the plan constrains **structure and scope**, not
  truth. Self-inconsistency and scope violations become catchable; ground-truth accuracy still needs a verifier.

## 11. The one-line pitch

We have been fixing "the model picked a bad structure" one symptom at a time. The scope plan fixes it once:
**decide the path — goal actions, prereqs, per-delta topics with unique definition + teaching ownership,
dependency order, a derived intro, and section plans — authoritatively before generation, and make generation
fill it instead of re-inventing it.** The five review rounds' corrections are what keep the planner from
becoming a fancier subject-key heuristic.

## 12. Phase-1 gate: five decisions (second review — resolved)

1. **Multiple goal-owning deltas per target** — ADOPTED (per required action).
2. **Definition ⟂ teaching ownership** — ADOPTED.
3. **Semantic delta distinctness beyond tuple equality** — ADOPTED; thresholds from human-labeled fixtures.
4. **Independent claim verification** — ADOPTED; independence contract in §5.
5. **Intro explicitly modeled** — ADOPTED (`IntroPlan`, derived, budgeted).

## 13. Phase boundaries, contract items, and spec precedence

**Phase-1 additions** (structure; promotion must NOT depend on the claims pipeline): canonical
provenance/confidence; `planning_input_fingerprint` ⟂ `plan_build_provenance`; plan ⟂ run separation;
`delta_id` + exact teaching-owner keys; section-plan-driven generation; the depth feature projection.
**Phase-2 additions** (content): authored claims (delta-bound, treatment-leveled); audited claims +
`claim_disagreements`; scope enforcement tiers; whole-path content audit. The schema MAY reserve Phase-2 fields
early; Phase-1 promotion gates never reference them.

Resolved rev 4→5: plan⟂run separation; fingerprint split; `scope_out` = must-not-teach; intro definition
eligibility + budget; operational claim-audit independence; DAG-scoped partial failure; skeletal section plans
in Phase 0; canonicalization metrics + ambiguity propagation; delta-bound claims + `treatment_level`;
owned-concept wording. Remaining implementation choices (decide in the PR, not by another design pass): the
concrete auditor (model/deterministic/hybrid); the Phase-1 fallback choice; the intro definition budget value
(a product configuration). **Distinctness thresholds are NOT a PR choice** — the PR implements metric collection
+ configurable threshold machinery; Phase 0 produces the labeled evidence; thresholds are approved from that
evidence and recorded as a configuration/promotion decision (§9).

**Spec precedence (drift control — this sketch is NOT a second spec):**
1. `STUDY_PATH_SCOPE_SPEC.md` (frozen, typed) governs persisted contracts.
2. This sketch governs motivation, rollout, and the newly-accepted deltas listed above.
3. Any conflict requires an explicit spec amendment or a mapping record — never silent divergence. The rev-4/5
   contracts (teaching_owners/delta_id, audited claims, identity confidence, fingerprint split, plan⟂run) are to
   be incorporated into the typed spec at Phase-1 implementation, after which the sketch's data-model section
   becomes non-normative.

> **Implementation note:** Phase-1A plumbing already exists dark in `backend/app/core/study_path_scope/`
> (schema/identity with canonical keys + aliases, mappings, construction incl. `LessonSectionPlan`, planning
> validation, shadow telemetry, builder; 76 core + 7 shadow-bridge tests). Sketch vocabulary maps onto the frozen
> spec's (`LearningDelta` ≈ ConceptIdentity(key, facet) + action; `teaches/uses` ≈ mappings). Genuinely NEW items,
> by phase (matching §13 — the claims pipeline is NEVER a Phase-1 requirement):
> **Phase 1:** `delta_id` + `teaching_owners`, identity provenance/confidence, the fingerprint split, the
> plan⟂run status split, the depth feature projection.
> **Phase 2:** the authored/audited claim contracts (`treatment_level`, `AuditedClaim`, `claim_disagreements`)
> and definition-vs-delta enforcement. (The schema may reserve these fields during Phase 1.)
