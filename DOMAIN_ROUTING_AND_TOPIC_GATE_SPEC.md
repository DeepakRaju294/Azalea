# Domain Routing & Topic-Type Gate Spec — Phase 0 (implementation-ready)

> **Purpose.** Classify a study path's **domain** from its goal, and make that domain the **final authority**
> over which topic types may be generated. This is the highest-leverage slice of the content-adaptation work and
> ships **without** the onboarding wizard, depth/language preferences, or any renderer change. It fixes the root
> cause behind the coding-topic-on-math / CS-loop-on-algebra defects.
>
> Split from the monolith `CONTENT_ADAPTATION_OVERVIEW.md`. Siblings: `ONBOARDING_AND_PREFERENCE_CAPTURE_SPEC.md`
> (Phase 1), `DOMAIN_CARD_NARRATION_AND_RENDERING_SPEC.md` (Phase 2).

---

## 1. Root cause (why this ships first)

Domain-specific structures **already exist** — `app/core/course_blueprints.py` defines 12 topic types incl.
`math_formula_method` (setup→calc→interpret + `formula_breakdown`), `proof_reasoning`, `science_mechanism`.
The defects come from **classification**: across *every* completing-the-square path, topics were labeled
`process_walkthrough` / `algorithm_walkthrough` / `coding_implementation` — and **never** `math_formula_method`.
The CS-loop scaffold fires because the math blueprint is never selected.

**Fix:** a path-level `domain`, and a deterministic gate — *`enrich_topic_with_course_type` may **suggest** any
type, but `_gate_topic_types_by_domain` is the **final authority** and guarantees every emitted topic belongs to
the domain's allow-list.*

---

## 2. Domain taxonomy (resolved)

- **Q1 — v1 domains = `coding · math · science · concept`.** No stored `other` (it becomes a structure-less
  dumping ground that poisons analytics). Unknown/unsupported requests resolve to `concept`; **ambiguous**
  requests resolve to `concept` **only when classification completes** — a classifier *failure* uses
  `classification_status = classifier_failed` and takes the §3.2 failure route rather than applying the concept
  gate. The raw classifier label may be kept internally for debugging, but routing always resolves to one of the
  four.
- **Q2 — `concept` definition.** Content whose primary learning mode is **explanation, categorization,
  comparison, or historical/contextual understanding** — rather than executable code, symbolic derivation, or a
  causal physical mechanism. `concept` is also the safe fallback profile.
- **Q4 — one primary domain per path; no `mixed` in v1.** Store a single `domain`; optionally keep ranked
  candidates internally for debugging. A **topic-level domain override** may be added later (Phase 3), but v1
  routing is deterministic off the path domain. Examples: "Learn Python for data analysis" → `coding`;
  "Understand gradient descent mathematically" → `math`; "Build a neural net in PyTorch" → `coding`; "the physics
  behind neural nets" → `science`/`concept`.

---

## 3. Classification contract

`classify_domain(goal) -> PromptSignals`:

| Field | Values | Use |
|---|---|---|
| `domain` | `coding · math · science · concept` | the gate + arc |
| `subdomain_family` | controlled (per §3.3) | stable routing/analytics |
| `subdomain_label` | free text (e.g. `completing_the_square`) | adapter-routing prior |
| `confidence` | 0–1 (top-minus-runner-up margin) | escalation + auto-apply bar |

### 3.1 Strategy (Q5 + Q31 resolved for v1)

- **Stage 1 — heuristic, deterministic, zero latency.** A **simple weighted count** of hits (no ML): per-domain
  keyword/notation lists + explicit language names + CS/physics/chem **adapter routing-slug** hits. `confidence`
  = top − runner-up margin.
  - coding — language names (`python/java/sql`), verbs (`implement/code/function/API`), CS nouns
    (`algorithm/data structure`), CS routing-slug hits.
  - math — `solve/prove/derive/equation/formula/theorem/integral/matrix`, notation (`x²`, `∑`, `∫`),
    algebra/calculus slug hits.
  - science — `physics/chemistry/biology/reaction/force/circuit/cell/mechanism`, unit tokens (`m/s`, `mol`,
    `N`), physics/chem adapter families.
  - concept — none dominate ⇒ default.
- **Stage 2 — LLM escalation, only when the margin is below a tuned threshold.** One small call returning
  `{domain, subdomain_family, subdomain_label, confidence}`; cached per goal string.
- **Auto-apply bar (Q17/Q28).** Above a **high** confidence bar the gate applies silently; below it, the gate
  still applies (deterministic) but the wizard (Phase 1) leads with a domain confirm. Never blocks path creation.

### 3.2 Classification certainty vs. `concept` fallback (don't turn an outage into bad structure)

`StudyPath.domain` stays one of `coding · math · science · concept`, but a **positively classified `concept`**
must be distinguished from **classification unavailable/untrusted** — otherwise a classifier/LLM outage turns
"Teach me DFS in Python" into `concept` and strips the coding types. Record separately:
```
classification_status: classified | low_confidence | classifier_failed | fallback_concept
```
Rules:
- `concept` + `classified` → normal concept gate.
- **Classification failed before a reliable domain** → do **not** silently apply the restrictive concept gate
  just because `concept` is the storage fallback. (The gate is final authority only when the result is
  trustworthy enough to enforce.)

**Classifier-failure route (exact — no implementer choice).** When `classification_status = classifier_failed`:
1. Persist `StudyPath.domain = concept` **only as the storage fallback** + `classification_status = classifier_failed`.
2. **Do not** invoke `_gate_topic_types_by_domain`.
3. Execute the **existing legacy** topic-generation route for that path (legacy behavior unchanged during the
   flag rollout — it may still call its own repair logic; the *new gated route* never does).
4. Emit `classifier_failed_legacy_route` telemetry.

The system must never apply the concept allow-list solely because the storage fallback is `concept`.

### 3.3 Subdomain — two layers (Q6 resolved)

Don't build a big controlled vocabulary. Use `subdomain_family` (controlled) + `subdomain_label` (free text):

| Domain | v1 controlled families |
|---|---|
| coding | programming-basics · data-structures · algorithms · web-development · databases · systems · machine-learning |
| math | algebra · calculus · linear-algebra · discrete-math · probability-statistics · geometry |
| science | physics · chemistry · biology · earth-science |
| concept | business · history · economics · philosophy · writing · general |

The free label still helps adapter routing; the family gives stable gates + analytics.

---

## 4. The domain gate

### 4.1 Allow-lists
`U` (universal, every domain): `study_path_introduction · concept_intuition · terminology_components ·
compare_distinguish · problem_solving_application`.

| Domain | Allowed (+ `U`) | Forbidden ⇒ remap |
|---|---|---|
| coding | `algorithm_walkthrough · data_structure_operation · coding_implementation · process_walkthrough` | `math_formula_method · proof_reasoning · science_mechanism` |
| math | `math_formula_method · proof_reasoning` | `coding_implementation · algorithm_walkthrough · data_structure_operation · process_walkthrough · science_mechanism` |
| science | `science_mechanism · math_formula_method` *(quantitative)* | `coding_implementation · algorithm_walkthrough · data_structure_operation · process_walkthrough` |
| concept | `process_walkthrough` | `coding_implementation · math_formula_method · proof_reasoning · science_mechanism` |

`process_walkthrough` is forbidden for math/science on purpose — its `process` card is the CS **loop** scaffold
(the completing-the-square offender). Gating it out forces `math_formula_method` (setup→calc→interpret).

### 4.2 Remap table (forbidden ⇒ nearest allowed)
Rule: remap to the domain's **primary teaching type**; `coding_implementation` **drops** if a walkthrough
already covers the subject, else remaps. (`—` = allowed.)

| Forbidden | @ coding | @ math | @ science | @ concept |
|---|---|---|---|---|
| `coding_implementation` | — | drop → else `math_formula_method` | drop → else `math_formula_method` | drop → else `process_walkthrough` |
| `algorithm_walkthrough` | — | `math_formula_method` | `science_mechanism` | `process_walkthrough` |
| `data_structure_operation` | — | `math_formula_method` | `science_mechanism` | `process_walkthrough` |
| `process_walkthrough` | — | `math_formula_method` | `science_mechanism` | — |
| `math_formula_method` | `algorithm_walkthrough` | — | — | `concept_intuition` |
| `proof_reasoning` | `concept_intuition` | — | `science_mechanism` | `concept_intuition` |
| `science_mechanism` | `concept_intuition` | `math_formula_method` | — | `concept_intuition` |

- **Q35 — "sole teaching topic" (resolved).** A topic is *sole* if, **after gating and dedup**, no other
  non-intro topic covers the same normalized subject + teaching objective. Sole coding topics remap (not drop).

**Gate-failure behavior (invariant).** A forbidden topic is remapped per the table; if it cannot be
deterministically remapped it is **dropped**. If dropping leaves the path with **no valid teaching topic**,
generation **fails safely and logs a `routing_validation` error** — the gate must **never** keep the original
forbidden type or emit an out-of-domain type as a fallback. (No "if no valid remap: keep original" escape hatch.)

**Gate execution — two-pass (deterministic, order-independent).** "Drop if a walkthrough already covers the
subject" depends on the *post-gating* result, so single-pass per-topic processing is circular and
order-dependent. Run:
1. **Normalize & propose** — enrich all topics with course type; compute normalized subject + teaching-objective
   fingerprints; compute remap *candidates* **without** dropping any duplicate implementation topic yet.
2. **Resolve coverage** — group by (normalized subject + objective); determine whether a valid walkthrough
   exists *after* remapping; drop a `coding_implementation` **only** when another valid teaching topic covers its
   group; otherwise remap the sole implementation per §4.2.
3. **Validate** — assert every remaining type is domain-allowed; assert ≥1 non-intro teaching topic remains;
   else fail with `routing_validation`.

**Native-domain coverage invariant.** The allow-list only *forbids* wrong types — it doesn't guarantee a
meaningful **native** one appears. A math path could survive with only universal types (`study_path_introduction
· concept_intuition · terminology_components · problem_solving_application`) and pass the allow-list while
failing the product goal (no `math_formula_method`/`proof_reasoning`). So the **final post-transform topic set**
— checked **after** `_append_missing_coding_topics` + collapse/fold, so the coding append can still repair a
coding path — must contain **≥1 native domain teaching type**:
- coding → `algorithm_walkthrough` / `data_structure_operation` / `coding_implementation` / `process_walkthrough`
- math → `math_formula_method` / `proof_reasoning`
- science → `science_mechanism` (or `math_formula_method` only when `quantitative_center == true`)
- concept → `process_walkthrough`, **or** `concept_intuition` (single-concept / terminology / historical /
  contextual), **or** `compare_distinguish` when the goal explicitly asks to compare. `study_path_introduction`
  and `terminology_components` **alone never** satisfy coverage.

Universal intro/definition cards alone are **never** sufficient coverage (so "What is inflation?" gets a real
`concept_intuition` shape, not just a roadmap + glossary).

**Native-coverage recovery (exact — non-circular, no new topics).** If the final post-transform set has no native
teaching type:
1. Identify the **first non-intro topic** by stable original topic order.
2. Attempt **one** deterministic domain-primary remap of it: math → `math_formula_method`; science →
   `science_mechanism` by default, `math_formula_method` **only when `quantitative_center == true`** (respects
   the §4.3 qualitative-science protection); coding → `algorithm_walkthrough`; concept → `concept_intuition`
   (or `compare_distinguish` only when the goal is comparative).
3. Re-run domain allow-list + card-safety validation.
4. If coverage still fails → raise `routing_validation`.

**Never create a new topic or infer a new subject** during recovery — recovery only *relabels* an existing
topic.

### 4.3 Taxonomy sufficiency
Sufficient with the 12 types. `math_formula_method` is a **"formula/method"** type serving **both math and
quantitative science** (physics/chem adapters are already `FormulaSpec`s); `science_mechanism` covers
qualitative/causal science. A `science_quantitative` **alias** is an optional low-priority clarity add.

**Science × `math_formula_method` (constraint).** On a science path, `math_formula_method` is allowed **only for
quantitatively-centered topics** (a law with a computable formula — Newton's 2nd law, Ohm's law, stoichiometry).
**Qualitative** science (photosynthesis, evolution, plate tectonics, cell division) routes through
`science_mechanism`; the gate must not force a formula-method card onto a mechanism topic. When both apply
(a mechanism with a quantitative sub-result), prefer `science_mechanism` and let the formula appear inside it.

**Enforceable predicate (not just prose).** The gate only sees the *path* `domain == science`; it can't judge a
single topic's quantitativeness without a field. Add it to the enriched-topic contract:
```
TopicRoutingMetadata { course_type, quantitative_center: bool, quantitative_confidence: 0..1 }
```
Deterministic rule on a science path: `science_mechanism` always allowed; `math_formula_method` allowed **only
when `quantitative_center == true`**; if the classifier suggests `math_formula_method` but `quantitative_center
!= true`, **remap → `science_mechanism`**. The prompt may *suggest* `quantitative_center`, but the backend
**validates** it from signals: explicit formula/law · a target numeric quantity · units · calculation/solve
language · a compatible quantitative adapter family.

---

## 5. Integration mechanics

- **Q36 — storage + threading.** `StudyPath` has a `language` column but **no `domain`** — add one (a column +
  migration, since `create_all` won't ALTER a live Postgres; a `provenance` field travels with it). Thread:
  `classify_domain` at path-creation → `StudyPath.domain` → `generate_topics_from_chunks(domain=…)` → gate.
  Lesson generation needs no new signal (it reads the now-gated `topic.course_type`).
- **Q33 — pipeline order (resolved).** `classify → generate raw decomposition → enrich_topic_with_course_type
  (+ annotate quantitative_center) → two-pass _gate_topic_types_by_domain **+ full-contract rewrite (§5.1)** →
  (domain-gated) _expand_canonical_family / _order_canonical_family / _append_missing_coding_topics →
  _collapse_same_subject_method_topics → _fold_prereqs_into_intro → native-domain coverage validation (§4.2) →
  persist → blueprint resolution → domain card-safety validation`. **Invariant:** no transform after the gate may
  create a forbidden topic type, coding-only relationship, or coding-only title without **re-entering domain
  validation.** Coverage is validated on the **final** post-transform set.
- **Q34 — transform changes (resolved).** **Retire** `_fix_noncoding_coding_topics` (a special case of the gate).
  **All coding-only transforms run iff `domain == coding`** — one **shared predicate**, not scattered `if`s:
  `_append_missing_coding_topics` · `_expand_canonical_family` · `_order_canonical_family` · coding
  implementation-title synthesis · coding-family adapter backfills. (`_expand_canonical_family` deterministically
  injects sort/graph walkthroughs — it must **never** fire because a math/science prompt shares a word.) **Keep**
  `_collapse_same_subject_method_topics` and `_fold_prereqs_into_intro` (domain-orthogonal) — but they must use
  `DOMAIN_TEACHING_TYPES` (§5.2), not the coding-only sets they use today.
- **Classifier home.** New `app/services/domain_classifier.py`, called from the study-path creation route.
- **Gate mechanism.** Post-classification remap is the hard guarantee; **also** make the
  `enrich_topic_with_course_type` prompt domain-aware to reduce remaps (lean: do both).
- **Domain card-safety assertion (backstop, not a renderer rewrite).** The gate restricts *topic types*, but a
  surviving **universal** type (`problem_solving_application`) could still emit a domain-wrong card. After
  blueprint resolution, assert forbidden card types don't appear in the final card plan: for math + qualitative
  science, **reject `complexity_analysis`** and code-trace/code-implementation cards (unless a later mixed-domain
  policy allows them). This makes "no O(n) card on algebra" enforceable even when a universal type survives —
  a validation check, not a new blueprint system. **On failure (exact):** (1) do not render/ship the plan;
  (2) attempt **one** deterministic rebuild from the same gated topic types + domain-valid blueprint rules only;
  (3) if a forbidden card still appears, **fail with `domain_card_safety_validation`**; (4) log the forbidden
  card type, source topic type, blueprint key, flag state. **No** frontend repair, card deletion, or fallback to
  an out-of-domain blueprint.

### 5.1 Full-contract rewrite — `rewrite_topic_contract` (required on every remap)

A remap that changes only `course_type` leaves a **structurally inconsistent** topic (`content_role=implementation`
· `title="Implementing …"` · `practice_format=coding` · a coding follow-up) that either fails the
`content_role`↔`topic_type` validator (`app/core/topic_decomposition.py` `resolve_topic_type`) or leaks coding
wording back into a math card. So every remap calls **`rewrite_topic_contract(topic, target_type, domain)`**,
rewriting: `course_type/topic_type · content_role · secondary_course_types · title framing · learner_outcome ·
purpose · in_scope/out_of_scope · practice_format · any coding follow-up relationship · decomposition_metadata`
(the fields that drive blueprint resolution). Target → required normalized `content_role`:

| target type | required role |
|---|---|
| `math_formula_method` | `calculation` |
| `proof_reasoning` | `proof` |
| `science_mechanism` | `mechanism` (scientific=true) |
| `algorithm_walkthrough` | `algorithm_trace` |
| `data_structure_operation` | `operation` |
| `coding_implementation` | `implementation` |
| `concept_intuition` | `foundation` |
| `process_walkthrough` | `mechanism` (scientific=false) |

### 5.2 `DOMAIN_TEACHING_TYPES` — a fix to already-merged code

Today `_TEACHING_TYPES` / `_MEMBER_TEACHING_TYPES` (`topic_generator.py`) are coding/process-only and **omit**
`math_formula_method` · `proof_reasoning` · `science_mechanism`. So the moment the gate routes math to
`math_formula_method`, `_fold_prereqs_into_intro` treats the *actual taught topic* as an untaught prerequisite
(and canonical-family/coverage checks misjudge it too). Replace both with **one authoritative per-domain set**
consumed by prereq-folding, native-coverage, same-subject dedup, ordering, and completion checks:
- coding → `{algorithm_walkthrough, data_structure_operation, coding_implementation, process_walkthrough}`
- math → `{math_formula_method, proof_reasoning}`
- science → `{science_mechanism, math_formula_method when quantitative_center}`
- concept → `{concept_intuition, compare_distinguish, process_walkthrough when genuinely procedural}`

---

## 6. Phase-0 acceptance test (the first vertical slice)

Every fixture asserts the **stored** `StudyPath.domain` (proving classifier + persistence, not a hardcoded gate
outcome), the allowed types, and the forbidden types.

```
Input: "Teach me completing the square."
Expect:
  - StudyPath.domain == math   (classifier + persistence)
  - topic generation emits NO coding_implementation / algorithm_walkthrough /
    data_structure_operation / process_walkthrough
  - ≥1 central topic is `math_formula_method`
  - no complexity card is emitted
  - `_append_missing_coding_topics` does not run (math path)
  - the existing math blueprint renders successfully
  - `_fix_noncoding_coding_topics` is not called (retired)
```

Symmetric guards:
- `"Teach me DFS in Python."` → `domain == coding`; allows `algorithm_walkthrough` / `coding_implementation`;
  emits no `math_formula_method` / `science_mechanism`.
- `"Teach me Newton's second law."` → `domain == science`; allows `science_mechanism` + quantitative
  `math_formula_method`; emits no coding type / complexity card.
- `"Teach me photosynthesis."` → `domain == science`; routes through `science_mechanism`; **no forced
  formula-method card** (qualitative science, per §4.3).
- `"Teach me how to calculate force using F = ma."` → `domain == science`; ≥1 `math_formula_method` (or
  quantitative-science) topic with `quantitative_center == true`; no coding types. (Positive side of §4.3.)
- Gate-failure: a path whose only topics are all forbidden-and-unremappable **fails with `routing_validation`**,
  never emits an out-of-domain type.
- Classifier-failure: with the classifier forced to fail, an obvious coding goal is **not** silently gated to
  `concept` — `classification_status == classifier_failed` and the **legacy route** is used (§3.2).

**`test_math_formula_method_blueprint_resolves_and_renders`** (turn "the math blueprint renders" into an
automated assertion — no pixel/screenshot test needed in Phase 0):
```
- generated topic type == math_formula_method
- blueprint resolution succeeds
- card plan contains NO complexity_analysis card
- all required card schemas validate
- the frontend render model is non-empty and schema-valid
```

---

## 7. Phase-0 entry criteria & rollout

**May start when resolved:** Q1, Q2, Q4, Q5, Q31, Q33, Q34, Q35, Q36 — **all resolved above.** (Threshold values
in Q5/Q31 are tunable constants, not blockers.)

**Feature flag (named).** `AZALEA_DOMAIN_ROUTING_GATE`:
```
false → existing route only (no classifier, no domain, no gate)
true  → classifier + persisted StudyPath.domain + gated route WHEN classification succeeds;
        classifier_failed → persisted fallback domain + legacy generation route, no gate (§3.2)
```
(So a `true` request does **not** always reach the gate — a classifier failure deliberately routes around it.)
The gate is deterministic and additive; the `true` route must **not** call legacy repair logic
(`_fix_noncoding_coding_topics`), but the `false` route stays available for rollback until fixture parity +
telemetry are stable. **Telemetry records the flag state per generation** (so old vs new outputs are
comparable). Validate on completing-the-square + a coding + a physics goal before default-on.

**Telemetry (Phase-0 done criterion).** Record per path: `flag_state`, inferred domain, confidence bucket, gate
remap count, gate drop count, paths left with zero teaching topics, `classifier_failed_legacy_route` count
(§3.2), general legacy-path usage, feature-flag error rate, and (when available later) inferred-vs-user-confirmed
domain divergence. This tells us the classifier is broadly
sane *before* onboarding exists. **Launch gate:** a **high `classifier_failed_legacy_route` rate means the gate is
mostly not running** (failed paths bypass it, §3.2) — its guarantees only hold at high classifier confidence, so
classifier precision on math/science is doing more load-bearing work than the allow-list table implies.

**Still open (non-blocking):** exact heuristic keyword lists & weights (tune), the escalation + auto-apply
thresholds (tune), the `science_quantitative` alias (defer).

---

## 8. Implementation sequence (the vertical slice, ordered)

No dependency on wizard screens, preference storage, depth, language rendering, or new visual components:

1. Add `StudyPath.domain` + `domain_provenance` + **`classification_status`** + the migration.
2. Implement the deterministic heuristic classifier with **configurable** thresholds/weights (§3.1), emitting
   `classification_status` (§3.2).
3. Add the optional low-confidence LLM escalation, behind the **same** feature flag.
4. Persist the primary domain during path creation (§5, `AZALEA_DOMAIN_ROUTING_GATE`); on `classifier_failed`
   take the **exact legacy failure route (§3.2)** — don't invoke the gate, don't force the concept gate.
5. Thread `domain` into topic generation (`generate_topics_from_chunks`).
6. Run course-type enrichment (unchanged — it only *suggests*), emitting `TopicRoutingMetadata`
   (incl. `quantitative_center` for science, §4.3).
7. Run the **two-pass** deterministic domain gate (`_gate_topic_types_by_domain`, §4.2) — final authority.
8. Domain-gate the coding-only append (`_append_missing_coding_topics`); then collapse/fold transforms.
9. Remove `_fix_noncoding_coding_topics` from the new path.
10. Enforce the **native-domain coverage invariant** on the **final post-transform** set (§4.2) — remap or fail
    `routing_validation`.
11. Add the **domain card-safety assertion** (rebuild-once-then-`domain_card_safety_validation`) after blueprint
    resolution (§5).
12. Add fixtures: math / coding / science-qualitative / science-quantitative / gate-failure / classifier-failure
    / native-coverage + the render-model assertions (§6).
13. Emit routing telemetry (§7, incl. `flag_state`).
14. Enable the new path only through `AZALEA_DOMAIN_ROUTING_GATE`.
