# Study-Path Scope Plan — implementation sketch (rev 2)

> A pragmatic, failure-grounded sketch for the up-front path plan. The full typed design is
> `STUDY_PATH_SCOPE_SPEC.md` (Draft v3.2, frozen); this sketch is the "why + minimal build", written against the
> concrete failures observed in the July 2026 TCP-congestion-control review rounds. It exists to decide whether
> to commit to the build, not to be the final contract.
>
> **rev 2** incorporates a design review that (correctly) flagged the rev-1 model as too loose in ways that would
> reproduce the current subject-key heuristics one layer up. Key corrections: uniqueness is per **learning delta**
> not per subject; **unique teaching ownership** replaces disjoint scope; **compound goals** are first-class;
> **parent → prereq** is conditional on the goal boundary; **depth is a derived summary** of the section plan;
> **repairs split** into deterministic vs semantic-replan; enforcement uses **structured content-claims**; and
> **F3/F4/F5 are prevented upstream but still detected + repaired downstream**.

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
F1/F2 are already netted post-hoc; F3/F4/F5 can only be **reliably prevented** with the plan (F4/F5 can be
*detected + regenerated* today, just not prevented).

## 2. Core idea

**Separate planning from authoring.** One planning pass turns the goal into an authoritative, versioned
`PathPlan` before any lesson is generated. Generation then **fills** the plan — it does not re-decide structure.
The plan is the single source of truth for: goal targets, prerequisites, each topic's *learning delta* and
scope ownership, dependency ordering, and each topic's section plan. Existing guards become **plan invariants**,
not post-hoc cleaners.

## 3. The plan (data model)

Two ideas do the real work: **subject identity is separate from learning delta**, and **scope is expressed as
ownership roles** (teaches / uses / reviews / mentions), not raw presence.

```
PathPlan
  plan_id, schema_version, planner_version        # versioned + IMMUTABLE for a generation revision
  goal_targets:     [GoalTarget]                  # compound goals -> multiple targets, each covered
  prerequisites:    [Prereq]
  topics:           [PlannedTopic]                # ordered by dependency, not list position
  definition_owners: { concept_key -> topic_or_intro_id }   # exactly one authoritative definer per concept
  planning_status                                 # see §8
  repair_log:       [RepairAction]

SubjectIdentity   { canonical_concept_key, parent_concept_key, aliases }

LearningDelta                                     # the unit of UNIQUENESS
  subject_identity
  facet            : intuition | mechanism | derivation | trace | comparison | implementation | application
  learner_action                                  # what the learner can DO after
  expected_evidence

GoalTarget        { subject_identity, required_actions, owning_topic_id }

PlannedTopic
  topic_id, provenance
  learning_delta:   LearningDelta
  role:             goal_owner | supporting | application
  prerequisite_topic_ids                          # explicit dependency edges -> ordering is derived + checkable
  teaches:          [concept]                      # AUTHORITATIVE owner; must be unique across the path
  uses:             [concept]                      # required prior knowledge; MAY repeat across topics
  reviews:          [concept]                      # deliberate short reinforcement (spiral policy)
  scope_out:        [concept]                      # explicit boundaries (siblings' teaches + prereqs)
  section_plan:     [Section]                      # the real structural authority (drives the blueprint)
  depth                                            # DERIVED SUMMARY of section_plan (not an independent driver)

Prereq   { subject_identity, gloss, required_knowledge, relation: parent | earlier_subject, within_goal_boundary: bool }
```

Why this shape kills the failures **by construction**:
- Duplicate detection is over **`LearningDelta`**, so "algorithms"/"mechanisms" collapse (same delta) while
  "trace Dijkstra"/"implement Dijkstra" stay separate (same subject, different facet + action). (F1)
- A parent-of-goal concept is a `Prereq` **unless `within_goal_boundary`** (introductory goals may teach their
  parents). (F2, without the rev-1 over-absolute rule)
- `role=goal_owner` topics get the substantive section plan; foundations are prereqs. `depth` is read off the
  section plan, so there is no second `topic_type`-style guess to get backwards. (F3)
- `teaches` (unique) vs `uses`/`reviews` (may repeat) is what makes scope enforceable without failing a lesson
  for legitimately *using* an earlier concept. (F4/F5)

## 4. How the plan is produced

A bounded planning call (LLM proposes, deterministic layer certifies) emits the `PathPlan`. It must pass
**planning invariants** before any lesson generates:

1. **Goal coverage:** every `GoalTarget`'s required actions are covered, and each target has exactly **one**
   `goal_owner` learning delta. (compound goals supported; no universal single "goal_core")
2. **No duplicate delta:** no two topics share a `LearningDelta` (subject + facet + action). Splits require an
   explicit policy reason.
3. **Prereq/topic boundary:** a parent-of-goal concept **outside the goal boundary** is a `Prereq`; a parent
   **explicitly requested or required by an introductory goal** may be a topic. (level/boundary aware)
4. **Unique teaching owner:** every concept has exactly one topic (or the intro) in `definition_owners` /
   `teaches`. `uses`/`reviews` are unrestricted. A spiral/review policy is the only way to have >1 treatment.
5. **Dependency soundness:** `prerequisite_topic_ids` form a DAG; a topic's `uses` are `teaches`/prereqs of an
   earlier topic; ordering is the topological order (not stored list order).
6. **Prereqs 0–3**, none trivial, none the goal subject.

**Repairs are split, not all "deterministic":**
- *Deterministic:* drop an exact-duplicate delta, merge identical `SubjectIdentity`, normalize aliases, drop a
  prereq equal to the goal, fix dependency references after a merge.
- *Semantic → targeted replan:* decide whether two facets are genuinely distinct, split overlapping teaching
  ownership, choose which topic owns a shared concept, decide whether a parent is inside an introductory goal,
  trim a topic without breaking its learning outcome.

Conflating these is exactly how the current subject-key heuristic would reappear in the planner; keep them apart.

## 5. How generation consumes it

- `section_plan` drives the card blueprint directly (no per-topic type re-guess). (F3 gone)
- Each lesson is generated against its `teaches` / `uses` / `reviews` / `scope_out`, and **emits structured
  content-claims** alongside prose:
  ```
  content_claims: [ { concept_key, relation: defines|explains|derives|applies|mentions, section_id, evidence_span } ]
  ```
- The **scope validator** compares claims to the plan: a `defines`/`derives`/`explains` on a concept this topic
  does not `teach` (and that another topic owns) is a violation; a `mentions`/`applies` on a `uses` concept is
  fine. It inspects only the flagged spans, not all prose — so it neither misses paraphrased teaching nor
  rejects legitimate references to prerequisites. (enforceable F4)
- The **whole-path audit** checks `definition_owners` are honored (a concept fully defined in two places = F5)
  and that every `GoalTarget` was actually delivered. Repeated *terminology* is fine; repeated *definitions /
  instructional treatment* is the defect.

## 6. What it subsumes

Every guard built this session becomes a plan invariant or a retiring backstop:
- `_collapse_near_duplicate_topics` → invariant #2 (no duplicate delta).
- `_demote_parent_of_goal_topics` → invariant #3 (parent → prereq, now boundary-aware).
- `_fold_prereq_topics`, foundation-fold, `_drop_umbrella_prereqs`, `_cross_topic_foundations` → prereq
  derivation + invariants #3/#6.
- domain gate / type remap → the `section_plan` fixes each topic's shape.

They stay as backstops during rollout, then retire (Phase 3).

## 7. Build path (shadow-first; stage the model so measurement isn't blocked)

- **Phase 0 (shadow, `AZALEA_STUDY_PATH_SCOPE`):** produce the `PathPlan` **structural skeleton only** (identity
  + delta + dependencies + roles — *no* content-claims yet) and run the structural invariants (#1–#6). Two
  comparisons, both logged, zero user impact:
  - `PathPlan ↔ shipped topic structure` — quantifies F1/F2/F3 + prereq/ordering disagreement.
  - `PathPlan ↔ generated lesson claims` — *only once lessons also emit claims*; quantifies F4/F5.
  (rev-1 wrongly implied one shadow comparison covers all five — it doesn't.)
- **Phase 1 (plan drives structure):** topic list + prereqs + per-topic `section_plan`/`depth` come from the
  plan; lessons still author as today. Prevents F1/F2/F3.
- **Phase 2 (plan enforces content):** generation emits content-claims; the scope validator + whole-path audit
  gate against the plan. Closes F4/F5.
- **Phase 3:** retire the redundant post-hoc guards.

## 8. Failure behavior + versioning (must be defined before Phase 1)

Explicit statuses instead of silent fallthrough:
- `planned` — invariants pass clean.
- `repaired` — passed after deterministic repair (see `repair_log`).
- `ambiguous` — a semantic decision could not be settled confidently → replan attempted, else escalate.
- `fallback_legacy` — planning failed/low-confidence → use today's decomposition (safe default during rollout).
- `generation_scope_failed` — lessons repeatedly violate the plan → flag path, keep best attempt, surface loudly.

The plan is **versioned and immutable for a generation revision**: regeneration must reuse the same `plan_id`
(or explicitly re-plan under a new `planner_version`), so a path never silently reinterprets under a newer
planner and recreates the very instability this design removes.

## 9. Promotion gates (shadow → Phase 1)

Measured on a golden goal set + production shadow (counts/distances, not "precision/recall"):
- Duplicate-delta rate; parent-as-topic disagreement rate; planner-vs-shipped topic-count delta.
- Repeated teaching-owner rate; invalid-plan rate; deterministic-repair rate; **replan rate**.
- **Same-goal stability** across repeated runs — equivalent learning deltas even when titles vary (the core
  promise; weight it heavily).
- (Phase 2 gates) scope-violation rate in generated lessons; scope-auditor false-positive rate; human acceptance
  on the golden set.

## 10. Explicit non-goals

- Not adapters, not study-materials, not the practice system (out of scope by direction).
- Not factual/numeric correctness of non-adapter content — the plan constrains **structure and scope**, not
  truth. Self-inconsistency and scope violations become catchable; ground-truth accuracy still needs a verifier.

## 11. The one-line pitch

We have been fixing "the model picked a bad structure" one symptom at a time. The scope plan fixes it once:
**decide the path — targets, prereqs, per-delta topics with unique teaching ownership, dependency order, and
section plans — authoritatively before generation, and make generation fill it instead of re-inventing it.**
The rev-2 corrections are what keep the planner from becoming a fancier subject-key heuristic.
