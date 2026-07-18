# Study-Path Scope Plan — implementation sketch

> A pragmatic, failure-grounded sketch for the up-front path plan. The full typed design is
> `STUDY_PATH_SCOPE_SPEC.md` (Draft v3.2, frozen); this sketch is the "why + minimal build", written against the
> concrete failures observed in the July 2026 TCP-congestion-control review rounds. It exists to decide whether
> to commit to the build, not to re-design it.

## 1. The problem, stated as observed failures

Every recurring defect this session has the **same root**: the pipeline never commits to a plan. It lets the
LLM re-derive the topic set, each topic's type/depth, and the prereq/topic split **freely on every generation**,
then we patch the symptoms after the fact with syntactic guards. Concretely, on the *same goal* ("learn TCP
congestion control") across generations we saw:

| # | Failure (live) | Why it happened | Current patch |
|---|----------------|-----------------|---------------|
| F1 | Duplicate topics ("Algorithms" + "Mechanisms"; two intros) | model split one concept into synonym capabilities with different subject_keys/types | `_collapse_near_duplicate_topics` (post-hoc, syntactic) |
| F2 | Foundation leaked in as a topic ("TCP Overview") | a parent-of-goal concept tagged as a normal teaching topic | `_demote_parent_of_goal_topics` (post-hoc, this session) |
| F3 | Depth inversion — goal topic shallow `concept_intuition`, foundation deep `science_mechanism` | per-topic type chosen by the LLM, unanchored to the goal | **none** — not fixable post-hoc |
| F4 | Scope drift — lesson teaches well beyond its declared `in_scope` | `in_scope` is advisory, never enforced against content | **none** |
| F5 | Cross-topic content repetition (same definitions/phases twice) | each lesson validated in isolation; no whole-path view | **none** |

F1/F2 are now netted post-hoc. **F3/F4/F5 cannot be fixed after generation** — they need a decision made
*before* it. That decision is the scope plan.

## 2. Core idea

**One deterministic-ish planning pass turns the goal into an authoritative `PathPlan`, before any lesson is
generated. Generation then FILLS the plan; it does not get to re-decide structure.** The plan is the single
source of truth for: what is a prerequisite, what is a topic, each topic's subject identity + depth, and each
topic's exact scope. Every existing guard becomes a *validator of the plan*, not a post-hoc cleaner of output.

## 3. The plan (minimal data model)

```
PathPlan
  goal_subject: CanonicalSubject          # the goal, normalized (identity + facet), e.g. {tcp_congestion_control}
  prerequisites: [Prereq]                  # OUT of scope; parent/foundation concepts (network protocols, "how TCP works")
  topics: [PlannedTopic]                   # IN scope; ordered; each is a distinct learning delta
  shared_vocabulary: [Term]                # path-wide terms → intro only

PlannedTopic
  subject: CanonicalSubject               # canonical key + facet (so 'algorithms'/'mechanisms' collapse to one)
  role: goal_core | supporting | application
  depth: deep | overview                  # DERIVED: the goal_core is always `deep`
  section_plan: [Section]                 # the intended cards/sections (drives blueprint, replaces per-topic type guess)
  scope_in: [concept]                     # what THIS topic teaches — authoritative
  scope_out: [concept]                    # explicit boundaries (siblings' scope + prereqs)

Prereq   { subject, gloss, required_knowledge, relation: parent | earlier_subject }
```

Two properties do all the work:
- **`CanonicalSubject` (identity + facet)** — duplication and prereq/topic decisions reason over *canonical
  subjects*, not normalized title strings. "TCP Congestion Control Algorithms" and "… Mechanisms" resolve to
  the same subject → one topic, by construction (kills F1 at the source).
- **`depth` is derived, not guessed** — `goal_core` topic is always `deep`; a parent/foundation is a `Prereq`,
  never a topic (kills F2 + F3 at the source).

## 4. How the plan is produced

A bounded planning call (LLM proposes, deterministic layer certifies) that emits the `PathPlan` and **must pass
planning invariants before any lesson generates**:

1. **Exactly one `goal_core`**, and it is `deep`. (kills F3)
2. **No topic's subject is a parent of `goal_subject`.** A parent concept must be a `Prereq`. (kills F2, generalizes this session's demotion guard)
3. **No two topics share a `CanonicalSubject`.** (kills F1)
4. **Every topic's `scope_in` is disjoint from every other topic's and from the prerequisites.** (kills F4/F5 pre-emptively)
5. **Prereqs are 0–3, none trivial, none the goal subject.** (existing prereq rules, now invariants on the plan)

Failing an invariant → deterministic repair (merge duplicate subjects, demote parents, split/trim overlapping
scope) or re-plan with targeted feedback — the same repair vocabulary we already use, moved *upstream*.

## 5. How generation consumes it

- Each `PlannedTopic.section_plan` drives the card blueprint directly (no per-topic type re-guess → F3 gone).
- Lesson generation is told its **`scope_in` and `scope_out`** and a **post-generation scope check** rejects
  content that teaches anything in `scope_out` or not covered by `scope_in` (closes F4).
- A **whole-path content audit** (the item from the last discussion) runs against the plan: cross-topic
  definition/phase overlap must be ~0 because scopes are disjoint by construction; the audit just verifies the
  generator honored the plan (closes F5).

## 6. What it subsumes

Every guard built this session becomes either an invariant on the plan or a redundant backstop:

- `_collapse_near_duplicate_topics` → invariant #3 (no shared canonical subject).
- `_demote_parent_of_goal_topics` → invariant #2 (no parent-of-goal topic).
- `_fold_prereq_topics`, foundation-fold, `_drop_umbrella_prereqs`, `_cross_topic_foundations` → the plan's
  prereq derivation + invariant #5.
- domain gate / type remap → the plan's `section_plan` already fixes the shape per topic.

They stay as backstops during rollout, then retire.

## 7. Build path (shadow-first, matches existing rollout style)

- **Phase 0 (shadow, `AZALEA_STUDY_PATH_SCOPE`):** produce the `PathPlan` alongside the current decomposition,
  run the planning invariants, and **log** what the plan *would* change vs. what shipped. Zero user impact. This
  immediately quantifies how often F1–F5 fire on real goals.
- **Phase 1 (plan drives structure):** the topic list + prereqs + per-topic `depth`/`section_plan` come from the
  plan; lessons still generate as today. Kills F1/F2/F3 at the source.
- **Phase 2 (plan enforces content):** the scope check + whole-path audit gate generation against the plan.
  Kills F4/F5.
- **Phase 3:** retire the post-hoc collapse/demotion/fold guards (now redundant).

## 8. Explicit non-goals

- Not adapters, not study-materials, not the practice system (all out of scope by direction).
- Not factual/numeric correctness of non-adapter content — the plan constrains *structure and scope*, not truth.
  Self-inconsistency and scope violations become catchable; ground-truth accuracy still needs a verifier.

## 9. The one-line pitch

We have been fixing "the model picked a bad structure" one symptom at a time. The scope plan fixes it once:
**decide the path — prereqs, topics, depth, scope — authoritatively before generation, and make generation fill
it instead of re-inventing it.** F1/F2 are already netted post-hoc; F3/F4/F5 only close here.
