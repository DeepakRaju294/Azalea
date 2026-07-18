# Study-Path Scope Plan — implementation sketch (rev 3)

> A pragmatic, failure-grounded sketch for the up-front path plan. The full typed design is
> `STUDY_PATH_SCOPE_SPEC.md` (Draft v3.2, frozen); this sketch is the "why + minimal build", written against the
> concrete failures observed in the July 2026 TCP-congestion-control review rounds. Status: **direction approved;
> Phase 0 committed; NOT yet the Phase 1 contract** — the five §12 decisions gate Phase 1.
>
> **rev 2** corrected the first review's findings (delta-based uniqueness, teaching ownership, compound goals,
> boundary-aware parent demotion, derived depth, repair split, content-claims, versioning).
> **rev 3** folds in the second review: goal ownership is per required ACTION; semantic delta-distinctness beyond
> tuple equality; definition vs teaching ownership separated; within-topic `uses`; independently AUDITED claims;
> structural evidence anchors; a derived `IntroPlan`; a minimum `Section` shape; domain routing *informs* planning;
> `fallback_legacy` is a measured degradation, not "safe"; scope-failure severity tiers; prereq cap as policy.

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
F1/F2 are already netted post-hoc; F3/F4/F5 can only be **reliably prevented** with the plan (F4/F5 remain
*detected + regenerated* downstream).

## 2. Core idea

**Separate planning from authoring.** One planning pass turns the goal into an authoritative, versioned
`PathPlan` before any lesson is generated. Generation then **fills** the plan — it does not re-decide structure.
The plan is the single source of truth for: goal targets and their required actions, prerequisites, each topic's
*learning delta* and teaching ownership, dependency ordering, the derived intro, and each topic's section plan.
Existing guards become **plan invariants**, not post-hoc cleaners.

## 3. The plan (data model)

Three ideas do the real work: **subject identity is separate from learning delta**; **scope is ownership**
(teaches / uses / reviews / mentions), with **definition ownership separate from facet-level teaching
ownership**; and the **intro is derived, not a topic**.

```
PathPlan
  plan_id, schema_version, planner_version        # versioned + IMMUTABLE for a generation revision
  goal_targets:      [GoalTarget]                 # compound goals -> multiple targets
  prerequisites:     [Prereq]
  intro:             IntroPlan                    # DERIVED — never a PlannedTopic (see below)
  topics:            [PlannedTopic]               # ordered by dependency, not list position
  definition_owners: { concept_key -> topic_id | "intro" }        # ONE authoritative DEFINITION per concept
  teaching_owners:   { (concept_key, facet_or_action) -> topic_id } # facet-level instruction ownership
  planning_status                                 # see §8
  repair_log:        [RepairAction]

SubjectIdentity   { canonical_concept_key, parent_concept_key, aliases }

LearningDelta                                     # the unit of UNIQUENESS (see invariant #2 for the real test)
  subject_identity
  facet            : intuition | mechanism | derivation | trace | comparison | implementation | application
  learner_action                                  # what the learner can DO after
  expected_evidence                               # the delta's distinct evidence obligation

GoalTarget        { subject_identity, required_actions: [action], owners: {action -> topic_id} }

PlannedTopic
  topic_id, provenance
  learning_delta:   LearningDelta
  role:             goal_owner | supporting | application
  prerequisite_topic_ids                          # explicit dependency edges -> ordering derived + checkable
  teaches:          [concept]                     # instruction this topic OWNS (per teaching_owners)
  uses:             [concept]                     # required prior knowledge OR own earlier sections; may repeat
  reviews:          [concept]                     # deliberate short reinforcement (spiral policy)
  scope_out:        [concept]                     # explicit boundaries (siblings' teaches + prereqs)
  section_plan:     [Section]                     # the real structural authority (drives the blueprint)
  depth                                           # DERIVED SUMMARY of section_plan (not an independent driver)

Section                                           # minimum shape — full detail in the frozen spec
  section_id
  pedagogical_function : orient | define | explain_mechanism | derive | worked_trace | compare | edge_cases | practice_setup
  teaches:  [concept]                             # concepts this section establishes (enables within-topic `uses`)
  uses:     [concept]
  required_evidence                               # what the section must SHOW (trace states, derivation steps, …)
  cardinality

IntroPlan                                         # presentation/orientation infrastructure, DERIVED from the plan
  prerequisite_refs                               # from `prerequisites` (named, linked, never taught)
  definition_keys                                 # ONLY concepts whose definition_owner == "intro" (roadmap-critical)
  roadmap_topic_ids
  framing_claims

Prereq   { subject_identity, gloss, required_knowledge, relation: parent | earlier_subject, within_goal_boundary: bool }
```

Why this shape **prevents the known structural failure modes when its semantic invariants are satisfied**
(not "by construction" — the invariants in §4 are what carry the guarantee):
- Duplicate detection compares **subject identity + evidence obligations + teaching ownership + section scope**;
  differently-named facets collapse when they do not produce *materially distinct* learning deltas (F1). Exact
  tuple inequality alone is NOT sufficient — see invariant #2.
- A parent-of-goal concept is a `Prereq` **unless `within_goal_boundary`** (introductory goals may teach their
  parents). (F2)
- `goal_owner` topics get the substantive section plan; `depth` is read off the section plan, so there is no
  second `topic_type`-style guess to invert. (F3)
- Definition ownership (one definer) vs teaching ownership (one owner per concept×facet) vs `uses`/`reviews`
  (unrestricted) is what makes scope enforceable without failing a lesson for *using* an earlier concept — and
  without forbidding one topic to define `cwnd` while another teaches how Reno changes it. (F4/F5)
- The intro is **derived infrastructure**, not a competing topic — the duplicate-introduction class cannot
  recur, because nothing else can occupy the orientation slot. (part of F1)

## 4. How the plan is produced

A bounded planning call (LLM proposes, deterministic layer certifies) emits the `PathPlan`. It must pass
**planning invariants** before any lesson generates:

1. **Goal-action coverage:** every `GoalTarget.required_action` is covered by exactly ONE goal-owning delta, and
   every goal-owning delta maps to at least one explicit required action. (One target MAY own several deltas:
   "trace and implement Dijkstra" → two goal-owning deltas, one per action; duplicate ownership of the same
   action is the violation.)
2. **Semantic delta distinctness:** two deltas on the same subject must have **materially distinct evidence
   obligations and non-overlapping primary teaching claims** — operationalized as: `teaches`-set overlap and
   `expected_evidence` comparison, with thresholds fixed by golden fixtures during Phase 0 (shadow data decides
   the boundary, not another design pass). Facet-label inequality alone NEVER justifies two topics.
3. **Prereq/topic boundary:** a parent-of-goal concept **outside the goal boundary** is a `Prereq`; a parent
   **explicitly requested or required by an introductory goal** may be a topic. (level/boundary aware)
4. **Ownership uniqueness:** every concept has exactly one `definition_owner`, and every (concept, facet/action)
   pair has at most one `teaching_owner`. `uses`/`reviews` are unrestricted; >1 instructional treatment of the
   same (concept, facet) requires an explicit spiral/review policy.
5. **Dependency soundness:** `prerequisite_topic_ids` form a DAG; every concept in a topic's `uses` is
   (a) an external prerequisite, (b) taught by an earlier topic, (c) intro-owned shared vocabulary, or
   (d) **taught by an earlier section of the SAME topic** (section order establishes it before use). Phase 0
   validates topic-level edges; section-level dependency checking may follow.
6. **Prereq budget (POLICY, not validity):** >3 prerequisites is a product-complexity violation prompting
   grouping under a canonical parent or goal-narrowing — never a reason for the planner to silently omit a real
   dependency, and never structural invalidity by itself.

**Repairs are split, not all "deterministic":**
- *Deterministic:* drop an exact-duplicate delta, merge identical `SubjectIdentity`, normalize aliases, drop a
  prereq equal to the goal, fix dependency references after a merge.
- *Semantic → targeted replan:* decide whether two facets are genuinely distinct (invariant #2), split
  overlapping teaching ownership, choose an owner for a shared concept, decide whether a parent is inside an
  introductory goal, trim a topic without breaking its learning outcome.

Conflating these is exactly how the current subject-key heuristic would reappear in the planner; keep them apart.

## 5. How generation consumes it

- `section_plan` drives the card blueprint directly (no per-topic type re-guess). **Domain routing INFORMS
  planning — it selects section templates, allowed evidence types, validators, and renderers — but it no longer
  overrides the accepted plan afterward.** (It is not "subsumed": a worked example in networking vs math vs
  coding still carries different evidence requirements.)
- Each lesson is generated against its `teaches` / `uses` / `reviews` / `scope_out`, and **emits structured
  content-claims** alongside prose:
  ```
  authored_claims: [ { concept_key, relation: defines|explains|derives|applies|mentions,
                       anchor: {card_id, section_id, field, item_index}, content_hash } ]
  ```
  Anchors are STRUCTURAL (the same contract as interactive-link anchors, which exist because raw text offsets
  break under the cosmetic passes); `content_hash` detects when later transformations invalidate a claim.
- **Claims are audited, not trusted.** Self-authored claims share the author's blind spots (a lesson can teach
  fast recovery while claiming only `mentions`). An independent extraction pass over the final prose produces
  `audited_claims`; `claim_disagreements` (omissions + relation misclassification) is a measured quantity.
  Structured claims make scope checking *tractable*; the audit is what makes it *trustworthy*. Phase 2 may begin
  with authored claims, but promotion depends on measured claim completeness.
- The **scope validator** compares (audited) claims to the plan, with **severity tiers**:
  - `mentions`/`applies` on a `uses` concept → fine.
  - incidental mention of a `scope_out` concept → non-blocking warning.
  - repairable drift (short re-explanation of another topic's concept) → regenerate the offending section.
  - **blocking:** fully teaching (defines/derives/explains) a concept whose teaching_owner is another topic →
    the lesson is not marked ready.
- The **whole-path audit** checks definition/teaching owners are honored (a concept fully defined in two places
  = F5) and every `GoalTarget.required_action` was actually delivered. Repeated *terminology* is fine; repeated
  *instructional treatment* is the defect.

## 6. What it subsumes

Every guard built this session becomes a plan invariant or a retiring backstop:
- `_collapse_near_duplicate_topics` → invariant #2 (semantic delta distinctness).
- `_demote_parent_of_goal_topics` → invariant #3 (parent → prereq, boundary-aware; the shipped guard is the
  conservative deterministic subset of it).
- `_fold_prereq_topics`, foundation-fold, `_drop_umbrella_prereqs`, `_cross_topic_foundations` → prereq
  derivation + invariants #3/#6.
- domain gate / per-topic type remap → replaced by `section_plan` for STRUCTURE; domain routing itself remains,
  repositioned as a planning input (§5).
- intro synthkeeper/dedup passes → `IntroPlan` (derived; nothing competes for the slot).

They stay as backstops during rollout, then retire (Phase 3).

## 7. Build path (shadow-first; stage the model so measurement isn't blocked)

- **Phase 0 (shadow, `AZALEA_STUDY_PATH_SCOPE`):** produce the `PathPlan` **structural skeleton only** (identity
  + delta + dependencies + roles + ownership maps — *no* content-claims yet) and run invariants #1–#6. Two
  comparisons, both logged, zero user impact:
  - `PathPlan ↔ shipped topic structure` — quantifies F1/F2/F3 + prereq/ordering disagreement.
  - `PathPlan ↔ generated lesson claims` — *only once lessons emit claims*; quantifies F4/F5.
  Fallback behavior is free here (shadow-only). Golden fixtures fix the invariant-#2 thresholds.
- **Phase 1 (plan drives structure):** topic list + prereqs + intro + per-topic `section_plan`/`depth` come from
  the plan; lessons still author as today. Prevents F1/F2/F3. **`fallback_legacy` is a measured DEGRADATION here,
  not a safe default** — the legacy decomposition is known to produce exactly these failures. Define the Phase-1
  choice explicitly: ship legacy WITH a degraded marker + metric, retry planning, or use a conservative
  single-topic+orientation fallback (sometimes safer than an unstable multi-topic decomposition).
- **Phase 2 (plan enforces content):** generation emits authored claims; the independent audit produces
  audited claims; the scope validator + whole-path audit gate against the plan with the §5 severity tiers.
  Closes F4/F5.
- **Phase 3:** retire the redundant post-hoc guards.

## 8. Failure behavior + versioning (must be defined before Phase 1)

Explicit statuses instead of silent fallthrough:
- `planned` — invariants pass clean.
- `repaired` — passed after deterministic repair (see `repair_log`).
- `ambiguous` — a semantic decision could not be settled confidently → replan attempted, else escalate.
- `fallback_legacy` — planning failed/low-confidence → legacy decomposition **with a degraded marker + metric**
  (see §7 Phase-1 note; never described as simply "safe").
- `generation_scope_failed` — lessons repeatedly violate the plan. Severity-tiered (§5): warnings ship,
  repairable violations regenerate the offending sections, **blocking ownership violations prevent the lesson
  from being marked ready** — "keep best attempt" is defined by tier, not structural completeness.

The plan is **versioned and immutable for a generation revision**: regeneration must reuse the same `plan_id`
(or explicitly re-plan under a new `planner_version`), so a path never silently reinterprets under a newer
planner and recreates the very instability this design removes.

## 9. Promotion gates (shadow → Phase 1)

Measured on a golden goal set + production shadow (counts/distances, not "precision/recall"):
- Duplicate-delta rate; parent-as-topic disagreement rate; planner-vs-shipped topic-count delta.
- Repeated teaching-owner rate; invalid-plan rate; deterministic-repair rate; **replan rate**.
- **Same-goal stability** across repeated runs — equivalent learning deltas even when titles vary (the core
  promise; weight it heavily).
- (Phase 2 gates) scope-violation rate; **claim-disagreement rate** (authored vs audited — the claim-completeness
  gate); scope-auditor false-positive rate; human acceptance on the golden set.

## 10. Explicit non-goals

- Not adapters, not study-materials, not the practice system (out of scope by direction).
- Not factual/numeric correctness of non-adapter content — the plan constrains **structure and scope**, not
  truth. Self-inconsistency and scope violations become catchable; ground-truth accuracy still needs a verifier.

## 11. The one-line pitch

We have been fixing "the model picked a bad structure" one symptom at a time. The scope plan fixes it once:
**decide the path — goal actions, prereqs, per-delta topics with unique definition + teaching ownership,
dependency order, a derived intro, and section plans — authoritatively before generation, and make generation
fill it instead of re-inventing it.** The rev-2/rev-3 corrections are what keep the planner from becoming a
fancier subject-key heuristic.

## 12. Phase-1 gate: five decisions (from the second review — resolved as follows)

1. **Multiple goal-owning deltas per target** — ADOPTED (invariant #1: ownership is per required *action*).
2. **Definition vs teaching ownership separated** — ADOPTED (`definition_owners` ⟂ `teaching_owners`, invariant #4).
3. **Semantic delta distinctness beyond tuple equality** — ADOPTED (invariant #2), with thresholds fixed
   empirically by Phase-0 golden fixtures.
4. **Independent claim verification** — ADOPTED (`authored_claims` / `audited_claims` / `claim_disagreements`;
   promotion gated on measured completeness).
5. **Intro explicitly modeled** — ADOPTED (`IntroPlan`, derived; definition ownership may assign intro-owned
   roadmap-critical terms; the intro is never a `PlannedTopic`).

These are design-resolved in this sketch; Phase 1 implementation must not regress them.
