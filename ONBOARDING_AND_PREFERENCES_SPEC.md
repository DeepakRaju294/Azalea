# Content Adaptation — Overview & Index

> **This document was split.** The original monolith bundled four independently shippable projects, which made
> the decision surface look larger than it is and risked implementers touching the wrong layer. It is now an
> **index** over three focused specs + two companion specs. Read this first, then the doc for the phase you're
> building.

---

## The one idea

Most content defects (a coding topic on completing-the-square, an O(n) complexity card on algebra, a
"Starting state / Repeated action" loop on a one-shot derivation) share **one root cause: classification routes
everything to generic/CS-shaped topic types.** Domain-specific structures **already exist** (12 topic types incl.
`math_formula_method`, `proof_reasoning`, `science_mechanism`) — but classification currently fails to select
them reliably, and their card sequences and narration contracts still need targeted auditing. The fix establishes,
**before generation**, a path-level **`domain`** that gates topic-type selection, plus a **`depth_level`** that
modulates how much content shows without altering adapter-computed truth.

**V1 rule:** a study path has **one primary domain.** Phase 0 does not support mixed-domain routing; a per-topic
domain/scaffold override is deferred **until Phase 2 at the earliest and is not a committed Phase 2 deliverable.**

---

## The split

| Spec | Scope | Phase |
|---|---|---|
| [`DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC.md`](DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC.md) | domain classification + topic-type gate + pipeline wiring + migration + Phase-0 test | **Phase 0 (ship now)** |
| [`ONBOARDING_AND_PREFERENCE_CAPTURE_SPEC.md`](ONBOARDING_AND_PREFERENCE_CAPTURE_SPEC.md) | wizard UX + question graph + preference schema/persistence + language (Option B) | Phase 1 |
| [`DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC.md`](DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC.md) | per-domain within-card contracts + depth knobs + renderer spike | Phase 2 |
| [`TRACE_TO_TEACHING_CONTRACT_SPEC.md`](TRACE_TO_TEACHING_CONTRACT_SPEC.md) *(written; implement before Phase-2 `on_enforced` prose)* | trace↔prose consistency (Q23) | companion |
| [`FREE_TEXT_CONTENT_VALIDATION_SPEC.md`](FREE_TEXT_CONTENT_VALIDATION_SPEC.md) *(written; implement alongside `on_enforced`)* | factual checking of free-text cards (Q24) | companion |

**Why the split matters:** onboarding, depth, language, and renderers are **not** prerequisites for the routing
fix. Bundling them made all ~39 questions look like blockers. They aren't — see the phase gates below.

---

## Authority boundaries

This overview **defines**: project boundaries · sequencing · shared rules · phase entry gates · the first
end-to-end acceptance slice.

This overview **does not define**: classifier keyword weights or thresholds · domain allow-lists and remap
targets · database schema details · wizard screen behavior · language support rules · depth-profile values ·
renderer contracts · trace/prose validation logic. **Those decisions belong only in the linked focused spec** —
if this index and a focused spec disagree, the focused spec wins. Keep implementation-specific rules in the
focused spec only; this index may *summarize* a rule for orientation but must **link to — not redefine —** the
authoritative contract.

---

## Terms

- **Domain** — the path-level knowledge mode (`coding`, `math`, `science`, `concept`).
- **Topic type** — the educational structure assigned to one topic (`math_formula_method`,
  `coding_implementation`, …).
- **Blueprint** — the configured card sequence + example rules + visual rules for a topic type.
- **Gate** — the deterministic rule restricting topic types to those the path domain allows.

---

## Status: what exists vs. what's missing

| Layer | Status | Phase |
|---|---|---|
| Native domain topic types and their configured blueprints | **Exists** | Phase 0 consumes |
| Path-level domain classification | Missing | Phase 0 builds |
| Topic-type gate | Missing | Phase 0 builds |
| Wizard + preference capture | Missing | Phase 1 builds |
| Depth consumer | Partially missing | Phase 1 builds |
| Language consumer | Missing / adapter-dependent | Phase 1, only when supported |
| Domain-aware within-card narration | Missing | Phase 2 |
| Renderer changes for math/science | Unknown | spike before Phase 2 |
| Trace↔prose consistency | Missing | companion spec |
| Free-text factual verification | Missing | companion spec |

This table stops an implementer from either rebuilding the existing blueprint architecture or assuming the gate
solves all content-quality problems (it doesn't — see the companion specs).

---

## Phase-specific entry gates

Replace "resolve all questions before anything ships" with per-phase criteria:

- **Phase 0 may start now** — the routing spec contains **final v1 decisions** for Q1, Q2, Q4, Q5, Q31, Q33–Q36.
  Remaining tuning values (confidence thresholds, scoring weights) must be **configuration**, not product
  decisions that block implementation.
- **Phase 1 may start when** Q7–Q16, Q18, Q25, Q27 are resolved (most are resolved in the onboarding spec;
  Q7/Q10 are small).
- **Phase 2 may start when** Q19–Q24, Q29, Q30, Q38, Q39 are resolved (Q38 resolved; Q21 needs the spike; Q23/Q24
  need the companion specs).

### Phase 0 — definition of done

Phase 0 is complete only when:
- [ ] `StudyPath.domain` is persisted through a migration.
- [ ] The classifier emits one supported primary domain + confidence + provenance.
- [ ] The topic-type gate runs **after** topic-type enrichment.
- [ ] Forbidden topic types cannot survive the gate.
- [ ] `_append_missing_coding_topics` runs only for coding paths.
- [ ] `_fix_noncoding_coding_topics` is no longer called on the new path.
- [ ] Math, coding, and science golden fixtures pass (below).
- [ ] If a forbidden topic can't be deterministically remapped it is **dropped**; if that leaves no valid
  teaching topic, generation **fails safely and logs a routing-validation error** — it never keeps or emits an
  out-of-domain type as a fallback.
- [ ] Telemetry records: inferred domain, confidence bucket, gate remaps/drops, paths left with zero teaching
  topics, legacy-path usage, and (when available) user domain overrides.
- [ ] The feature flag can disable the new routing path (rollback intact).

---

## The first vertical slice (prove the fix before anything else)

```
Input:  "Teach me completing the square."
Expect: StudyPath.domain == math (classifier + persistence proven);
        NO coding_implementation / algorithm_walkthrough /
        data_structure_operation / process_walkthrough; ≥1 math_formula_method topic;
        no complexity card; no coding-append transform; existing math blueprint renders;
        _fix_noncoding_coding_topics not called.
```
(Full test in routing spec §6.)

### Symmetric routing guards
Completing-the-square is not a one-off patch — the gate is symmetric. **Each fixture asserts the stored domain**
(so the classifier + persistence thread is proven, not just a hardcoded gate outcome):
- **Coding** — "Teach me DFS in Python." → `StudyPath.domain == coding`. Must allow `algorithm_walkthrough` /
  `coding_implementation`; must **not** emit `math_formula_method` or `science_mechanism`.
- **Science** — "Teach me Newton's second law." → `StudyPath.domain == science`. Must allow `science_mechanism`
  and quantitative `math_formula_method`; must **not** emit `coding_implementation` / `algorithm_walkthrough` /
  complexity cards.

> `math_formula_method` is allowed for science **only when the topic is quantitatively centered**; qualitative
> science (photosynthesis, evolution, plate tectonics) routes through `science_mechanism` without forcing a
> formula-method card. (Authoritative rule: routing spec §4.)

---

## Rollout principle

Phase 0 is **additive and flag-gated**. The new route must not call legacy repair logic (`_fix_noncoding…`),
but the **existing route remains available for rollback** until fixture parity and production telemetry are
stable. Do not delete the fallback before confidence is earned — the old pipeline still holds implicit recovery
behavior.

---

## Shared rules across all specs

- Classification is the Phase-0 root fix: the domain gate is deterministic, never prompt-only.
- A path has **one primary domain** in v1; mixed-domain behavior is deferred until Phase 2 at the earliest and
  is not a committed Phase 2 deliverable.
- A forbidden topic that cannot be remapped is **dropped, not kept**; a path left with no valid teaching topic
  fails safely rather than emitting an out-of-domain type.
- `domain`, `depth`, and `knowledge_level` are independent axes with different consumers.
- No wizard question ships before its consumer is live.
- `depth` may change content **quantity and optionality** (card inclusion, number of adapter instances
  requested) — **never** adapter-computed states, traces, expected answers, or validation logic.
- Adapters own states, traces, expected answers, and verification.
- LLMs own teaching phrasing and intent, not truth-bearing render data.
- The frontend renders compiled state; it does not repair or infer semantic state.
- Existing blueprints are reused through routing and configuration, not rebuilt.
- Every phase ships behind a feature flag with a defined rollback path.

---

## After these specs land — finish the adapter catalog

This work makes the system **route and narrate** each domain correctly, but **verified worked examples still
depend on the adapter catalog** — **~150 adapters today, and incomplete.** Phase 2's fact-source / coverage
guarantees are only as broad as the adapters that back them: a math/science topic with no adapter falls to
`deferred` / withheld (Phase 2 §2.1/§4), so **broad domain-native content requires the full catalog.** Once these
specs are implemented, **resume CP12 (`SPEC_IMPLEMENTATION_CHECKPOINTS.md`) and complete the remaining adapters** —
the full math / physics / chemistry / finance breadth via the declarative type-engines. Treat "finish the adapter
catalog" as the committed follow-on to the content-adaptation program, not an afterthought.
