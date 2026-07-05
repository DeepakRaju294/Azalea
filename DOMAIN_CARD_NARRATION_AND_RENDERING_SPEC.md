# Domain Card Narration & Rendering Spec — Phase 2

> **Purpose.** Once routing (Phase 0) selects the correct topic type, make each card's *within-card* content adapt
> to the domain: per-domain field framing (`goal/reasoning/work/result`, step titles, result lines), the
> presentation shape, and whether existing renderers can express math/science layouts. **Downstream of routing;
> consumes Phase-1 `DEPTH_PROFILE_V1` (does not redefine depth).**
>
> Split from `CONTENT_ADAPTATION_OVERVIEW.md`. Depends on two **companion specs** for correctness (§12).
> `Phase 0: domain → topic type · Phase 2: topic type → within-card framing · companions: keep framing truthful.`

---

## 1. Starting point: the structures largely exist

Per-topic-type card **sequences / example types / visuals** already exist in `app/core/course_blueprints.py`
(`TOPIC_BLUEPRINTS`, `EXAMPLE_CARD_RULES`, `VISUAL_CARD_RULES`). So this phase is **audit + within-card narration**,
not greenfield.

- **Q38 — `StructureProfile` = a lens over existing config, NOT a new build (resolved).** The existing dicts
  *are* the profile; "extract coding into the first profile" is a relabel, not a rewrite. Do not re-architect the
  blueprint system.
- **Q20 — audit the existing sequences** (does `math_formula_method` teach the a≠1 case? is its `process`
  scaffold right?). Review-and-fill, not invent.

---

## 2. Card-contract coverage matrix (from the real blueprint inventory)

**No card may silently keep the generic coding framing because its domain contract was omitted.** Every card type
emitted by `TOPIC_BLUEPRINTS` must be in exactly one state below. (Inventory pulled from
`course_blueprints.py`; `causal_chain`/`setup→calc→interpret` are *visuals/scaffolds on the `process` card*, not
separate cards.)

**One status vocabulary** per (card × domain) cell — no competing labels:

**Canonical status enum** (code-facing): `defined | not_applicable | deferred_from_initial_rollout`. In the matrix
below, `deferred` is prose shorthand for `deferred_from_initial_rollout`.

| Status | Meaning |
|---|---|
| `defined` | contract written + eligible for rollout |
| `not_applicable` | this domain/card combination must never occur in v1 |
| `deferred_from_initial_rollout` | domain-compatible, but excluded until its contract + fact-source registry are complete |

| Card type | coding | math | science | concept |
|---|---|---|---|---|
| `background` | defined | defined | defined | defined |
| `components_terms` | defined | defined | defined | defined |
| `process` | defined | defined | defined | defined |
| `worked_example` (step) | defined | defined | defined | defined |
| `edge_case` | defined | defined | defined | defined |
| `practice` | defined | defined | defined | defined |
| `formula_breakdown` | not_applicable | deferred | deferred *(quantitative)* | not_applicable |
| `proof_plan` | not_applicable | deferred | not_applicable | not_applicable |
| `code_walkthrough` | deferred | not_applicable | not_applicable | not_applicable |
| `complexity_analysis` | defined | not_applicable\* | not_applicable\* | not_applicable\* |
| `comparison` | deferred | deferred | deferred | deferred |
| `roadmap` (shared) | deferred | deferred | deferred | deferred |
| `prerequisites` — "Before you start" (shared) | deferred | deferred | deferred | deferred |

\* `complexity_analysis` on math/science is **dropped by Phase-0 card-safety** (never rendered) — recorded here
as `not_applicable`. The `deferred` cells are the Phase-2 deliverables; re-derive the exact list from the live
inventory at implementation, not from this table.

### 2.1 Card-contract eligibility gate (runtime — where the matrix is enforced)

**Runtime order:** `Phase-0 route → blueprint resolution → card-contract eligibility gate → fact-source
validation → narration contract → renderer selection → domain card-safety validation → scoped rollout decision`.

After blueprint resolution and **before** narration/render-model compilation (and before the Phase-2 renderer
choice / any `on_enforced` display), evaluate each planned card against its `(card_type, topic_domain)` status:
- **`defined`** → may proceed **only when** its contract + required fact-source entries are registered.
- **`not_applicable`** → must **not** appear; its presence is a `domain_card_safety_validation` failure.
- **`deferred_from_initial_rollout`** → must **not** be narrated/rendered by the Phase-2 contract path. For a
  deferred card: (1) blueprint-**optional** → remove deterministically, record `deferred_card_pruned`;
  (2) blueprint-**required** → **do not silently prune** — either keep that topic-type/family out of the initial
  rollout, or `define` the card contract + fact-source registry before enrolling it in `on_enforced`;
  (3) **no** deferred card may fall back to generic narration merely because the blueprint emitted it.

**Immediate consequence for the first math slice.** `formula_breakdown` is **required** in `math_formula_method`
and is `deferred` above — so completing-the-square **cannot enter `on_enforced` until `formula_breakdown` (math)
is `defined`.** Lean: define it first (it's central to *why* completing the square works); until then the math
slice runs in `shadow_validate` / fixtures only.

---

## 3. The within-card catalog (per card × per domain)

Two change kinds: **reframe** (fields stay; labels/contract/order change — most cards) vs **restructure**
(scaffold shape changes — the `process` card; swapping `complexity ↔ pitfalls ↔ assumptions`).

**Core `process` scaffold (restructure):** loop (coding) · `Setup→Operation→Result→Why` (math) ·
`Principle→Apply→Interpret` (science) · `Idea→Structure→Example` (concept).

**worked-example step (reframe):**

| Field | coding | math | science | concept |
|---|---|---|---|---|
| `goal` | what this line does | what we transform, toward what | what quantity we're finding | what idea/distinction is established |
| `reasoning` | why (control/purpose) | the rule/identity justifying it | the law/principle invoked | relation / definition / contextual basis |
| `work` | the code line (+ trace) | the rewritten expression | the substitution & solve | example / comparison / evidence |
| `result` | variable state after | the new form / running result | value **+ units + interpretation** | concise takeaway / classification |

**Other cards:** `background` (what it's for / where it applies / phenomenon / idea) · `components_terms` (data
structures · symbols+notation · quantities+units · key terms) · `edge_case` (boundary input / degenerate case /
limiting assumption / common misconception) · `practice` (modify-code / solve / predict / classify-compare-explain).

**Cross-cutting rules (all cards):** (1) framing only — see §4 for the adapter-neutral boundary; (2) never
introduce a term outside `assumed_prerequisites` + what's taught; (3) practice stays within the taught method
(closes the a≠1 gap); (4) **step titles describe the action, not the rule name** ("Add and subtract (b/2)²", not
"Completing-the-square rule"); (5) **result lines are terminal, not narrated** (drop "Complete: the conclusion is
reached. Final result: …").

- **Q39 — injection point (TWO paths, not just the trace pipeline).** The loop scaffold that produced the
  awkward math reads ("Starting state / Repeated action / State update") lives in the **blueprint/prompt layer**
  (`course_blueprints.py` · `course_stage_rules.py` · `lean_lesson_prompt.py`) — the **general card path** — not
  in the trace pipeline. So passing `domain` only into `trace_pipeline.py` leaves the process card loop-framed.
  Phase 2 branches **both**:
  - **(A) general card narration** — background · terms · process · formula_breakdown · proof_plan · edge_case ·
    practice · roadmap/prereqs — injected at the **blueprint/prompt layer**;
  - **(B) verified worked-example narration** — the trace-backed step formatter (`solver.py` / `trace_pipeline.py`),
    per-domain (coding / math / science / concept).
  The trace pipeline's formatter contract is currently coding-oriented (code lines, variables, branches, loops,
  runtime state); (B) adds math/science/concept formatters. **(A) is where most cross-domain leakage is fixed.**

---

## 4. The adapter-neutral boundary (narration may not invent truth)

"Reframe is adapter-neutral" is only true for **presentation**. Split precisely:

- **Adapter-neutral narration** (Phase 2 may freely change): labels · field headings · prose ordering · sentence
  templates · action-oriented titles.
- **Adapter-backed narration** (Phase 2 may *only surface*, never invent): units · formula/law identifiers ·
  transformed-expression metadata · state deltas · final-answer semantics · interpretation of computed values.

**Narration-data audit (before adding any domain framing).** Confirm every required truth-bearing field exists in
the authoritative trace/adapter metadata:
- science **units** come from the adapter/trace, not the LLM;
- math **rule/identity** labels come from an operation tag / verified metadata, not free prose;
- coding **result state** comes from the execution trace;
- **interpretation** may be generated only from authoritative values via a domain template, or validated by the
  trace-to-teaching contract (§12).

If a required field is absent, Phase 2 **omits/defers the dependent card behavior** — it **may not invent it in
prose.** Adding new authoritative metadata is a **separately-approved adapter/trace change**, not implicit Phase-2
narration work (keeps the rollout bounded and consistent with §11, which forbids changing adapter computation).

**Narration fact-source registry (required artifact — the machine-checkable bridge).** Before a card contract
ships, every truth-bearing **output** field maps to exactly one registered **source mode** (`direct` / `derived`
/ `validated_generated`); a `derived` mode may consume **multiple enumerated** authoritative inputs:

| Card / field | Domain | Source | Required? | Fallback |
|---|---|---|---|---|
| `worked_example.result` | math | `trace.step.result_expression` | yes | block card |
| `worked_example.reasoning` | math | `trace.step.operation_tag` | yes | omit / block |
| `worked_example.result.units` | science | `trace.step.units` | when quantitative | block calculation framing |
| `worked_example.interpretation` | science | **`derived`** (see below) | optional | omit interpretation |
| code result state | coding | execution-trace delta | yes | block card |

**Source-mode semantics.** Each truth-bearing field maps to exactly one **mode** (not necessarily one field):
- **`direct`** — one authoritative trace/adapter field;
- **`derived`** — a **named deterministic template/function** + an **enumerated set** of authoritative input
  fields; must record `{template/function id · input field ids · output schema · validation rule (if any)}`;
- **`validated_generated`** — generated text accepted **only** through the applicable companion validator (§12).

**Free generation is never a source mode.** The interpretation row as `derived`:
`template: science_quantity_interpretation_v1 · inputs: trace.step.value, trace.step.units,
trace.step.quantity_label · fallback: omit`.

**Derived-interpretation eligibility (a template is not a truth source on its own).** `value=9.8, units=m/s²,
quantity_label=acceleration` doesn't say whether it's a magnitude, signed direction, average vs. instantaneous,
or an idealized-model result. A `derived` interpretation template runs **only when all its required semantic
inputs are registered.** For `science_quantity_interpretation_v1`, require: `quantity_label · value · units ·
quantity_kind`/dimensional category · direction/sign metadata (when applicable) · model/assumption metadata
(when it depends on an idealization) · `reference_frame` **required_when** the `quantity_kind` needs one
(velocity, displacement, position, torque, electric potential) — **not** for frame-irrelevant scalars (mass,
temperature) · a **calculation-status** confirming the value is **final, not intermediate**. If any required
input is absent: **omit interpretation**, retain value + units, and **do not** generate explanatory prose as a
substitute. (Keeps a deterministic template from becoming a deterministic source
of *misleading* prose.)

Rules: a narrator/renderer may read **only registered** sources; a missing **required** source **blocks that card
type** from the initial rollout; **optional** unsupported fields are **omitted, never free-generated**. (Closes
the loophole where an LLM writes something that *sounds like* a rule identifier / unit interpretation /
justification but isn't grounded in metadata.)

**This registry IS the adapter-capability registry — one artifact, not two.** Key it by adapter slug; the trace
routing already defers unsupported/meta topics, so Phase 2 cannot assume every requested math/science topic has a
verified trace + units + rule tags + calculation-status + quantity-kind + assumptions. Per adapter, record what
it can actually supply — `supported_domains · supports_verified_worked_example · supports_rule_identifier ·
supports_units · supports_quantity_kind · supports_sign_or_direction · supports_assumption_metadata ·
supports_final_result_status · supported_languages · supported_card_types` — so the fact-source rules above are
**enforced, not aspirational**. (Produced in Phase 2A; don't build a second capability object.)

---

## 5. Card-level scaffold overrides (defined now, disabled in v1)

A genuinely-mixed topic (a math lesson with one code card) may *eventually* override a card's domain scaffold —
but uncontrolled, this recreates the Phase-0 problem locally. Rules:
1. only an **explicitly whitelisted** card type may override;
2. the override is chosen by **deterministic metadata / an approved adapter flag**, never free LLM choice;
3. it must not bypass Phase-0 topic-type or card-safety rules;
4. the card declares **both** `topic_domain` and `scaffold_domain`;
5. every override is logged for review.

**v1: ship with the allowed-override set EMPTY.** Define the data shape (`topic_domain` + `scaffold_domain`) now;
enable no overrides until a concrete fixture proves the need. (Q29.)

---

## 6. Depth — consume Phase-1, don't redefine it

Phase 1 owns depth: `DEPTH_PROFILE_V1`, effective-depth validation, capability declarations, `working_limited`,
and the structural knobs. **Phase 2 consumes `DEPTH_PROFILE_V1`; it defines only the Phase-2 *rhetorical/rendering*
extensions** (longer intuition framing, expanded justification, deeper narration) and must not restate structural
values (avoids "deep = 2 examples" here vs "2–3" there). Single source of truth: the onboarding/preferences spec.

---

## 7. Renderer spike (Q21) — bounded, with a definition of done

Do **not** design all math/science renderers up front. Run a **three-fixture spike** — completing the square ·
Newton's second law · DFS code walkthrough. For each fixture: compile the final render model · render in the
existing frontend · capture a screenshot/visual-test artifact · record missing layout/semantic capabilities ·
classify each gap as {template/config-only · existing-renderer extension · new renderer component · blocked by
missing authoritative metadata}.

**The spike concludes with exactly one decision per affected card type:** (1) existing renderer sufficient;
(2) extend renderer **X** with named fields; (3) build named renderer **Y**; (4) defer that card type from Phase 2.
**No production rendering changes ship as part of the spike** (else it silently becomes a partial frontend
rewrite).

---

## 8. Phase-2 vertical slice + regression fixtures

**First slice — completing the square:**
```
- Phase 0 routes the path to math; math_formula_method blueprint selected
- process card renders Setup → Operation → Result → Why (no loop scaffold)
- worked-example steps use math field framing (§3)
- no code / loop / complexity framing appears
- every truth-bearing worked-example expression, transition, result, and rule label maps to registered
  authoritative metadata (§4) — background prose/titles/labels need not map 1:1 but still obey §12
- final card plan passes domain card-safety validation
- existing renderer (or an explicitly-approved extension) displays it
```

**Regression fixtures (no cross-domain leakage):**
1. **Completing the square** — math derivation framing · no loop template · no complexity card.
2. **Newton's second law** — science calculation framing · units from authoritative data · interpretation never
   contradicts the computed value.
3. **DFS code walkthrough** — code-state framing intact · no math/science templates leak · code lines + state
   highlights stay aligned.
4. **"What is inflation?"** — concept framing uses `Idea → Structure → Example`; ≥1 `concept_intuition` card
   satisfies native coverage; **no** code-loop / formula-method / complexity / science-mechanism framing appears
   (proves the concept scaffold doesn't collapse into a generic roadmap + glossary path).

---

## 9. Phase-2 definition of done

- [ ] Existing blueprint inventory fully mapped to the §2 card-contract matrix (no card omitted).
- [ ] Every in-scope card has a domain framing **or** is explicitly deferred.
- [ ] Narration receives `domain`/`topic_type` through a documented interface (§3, Q39).
- [ ] **No truth-bearing narration field is invented outside authoritative metadata** (§4).
- [ ] Renderer spike concluded with a documented decision per card type (§7).
- [ ] Math / science / coding / concept fixtures pass (§8).
- [ ] No generic coding loop scaffold appears on math/science `process` cards.
- [ ] No domain-forbidden card type survives final card-plan validation (Phase-0 card-safety).
- [ ] The **card-contract eligibility gate** (§2.1) runs before narration/render: `not_applicable` ⇒ safety
  failure; a **required** `deferred` card blocks `on_enforced` for that family (no silent prune, no generic
  fallback).
- [ ] Mixed scaffold overrides remain **disabled** unless explicitly approved (§5).
- [ ] `AZALEA_DOMAIN_NARRATION_V2` supports the three rollout modes (§9.1); a live domain/card family rolls back
  to `shadow_validate` or an approved same-domain fallback, **never** `off_legacy`.
- [ ] Trace-to-teaching + free-text validation dependencies are either active **or** the shipped scope clearly
  limits correctness claims (§12).

### 9.1 Phase-2 rollout modes — `AZALEA_DOMAIN_NARRATION_V2`

A boolean can't be both "pre-launch legacy" and "safe rollback" — at first deploy the existing math/science
narration is exactly the unsafe thing this work removes, so it isn't yet on the fallback allow-list. **Three
modes** (a rollout ladder, not `off → fully on`):
```
off_legacy      → pre-rollout / dev baseline ONLY: existing narration + renderer; Phase-0 routing stays active;
                  NOT eligible for production traffic once any card/domain contract is activated.
shadow_validate → production shows the approved legacy/safe path; Phase-2 contracts + fact-source + render-model
                  validation run WITHOUT display; telemetry compares outcomes + validation failures.
on_enforced     → approved Phase-2 contracts + spike-approved renderer shown; a validation failure uses only an
                  approved same-domain fallback (below), else WITHHOLDS the card/path with a typed error.
```
**After Phase 2 is enabled for a domain/card family, rollback goes to `shadow_validate` or an approved fallback —
NOT `off_legacy` for that family.** (Phase 0 fixes the topic type but does not make old within-card narration
domain-safe, so `off_legacy` could reintroduce a coding-loop scaffold on math/science.)

**Rollout scope — per family, not global.** The mode is evaluated per **rollout family**, so a science failure
never forces rolling back math/coding, and telemetry attributes to the exact contract/version:
```
RolloutFamily { topic_domain, card_type, optional_topic_type,
                mode: off_legacy | shadow_validate | on_enforced,
                contract_version, renderer_version, fallback_allowlist_version }
```
Once a family enters `shadow_validate`/`on_enforced` it **may not** return to `off_legacy`; its only rollback
targets are `shadow_validate` or an approved same-domain fallback.

**Per-family telemetry:** `rollout_family · mode · contract_version · renderer_version · fallback_allowlist_version
· validation_outcome · withheld_reason` (+ `deferred_card_pruned` from §2.1) — so "science interpretation metadata
missing" is distinguishable from "renderer contract failed," not just an aggregate Phase-2 error.

**Shadow-validation display rule (no-safe-display case).** In `shadow_validate`, production may show an approved
legacy/safe path **only when one exists in the fallback allow-list for that family.** If none exists (a newly
introduced family): **do not enroll it in production shadow traffic** — run the contract only in fixture/staging
or explicitly opted-in traffic, and **never** use `off_legacy` output as a display fallback. (Old unsafe
math/science narration must not sneak back into production under the "shadow" label.)

**Approved legacy-template fallback (mechanically constrained).** A prior template/renderer may be registered as
a Phase-2 fallback **only when** it: (1) preserves the same `topic_domain`, `scaffold_domain`, and card type;
(2) passes Phase-0 domain card-safety validation; (3) contains **no** prohibited domain framing (e.g. no coding
loop scaffold on math/science); (4) uses only registered truth-bearing sources (§4) for the affected card; and
(5) is named in an **explicit fallback allow-list**. Otherwise the failure **withholds** the card/path with a
typed error. (Prevents a failed math contract from silently reverting to the very loop wording Phase 2 removes.)

**Rollback boundary.** On rollback, math/science `process` cards **must retain the domain scaffold**
(`Setup→Operation→Result→Why` / `Principle→Apply→Interpret`): drop to `shadow_validate` or an approved
same-domain fallback — never `off_legacy` once the family is live, and **never** a coding-loop scaffold on a
math/science card. If no approved fallback exists, **withhold** the card/path with the typed error.

---

## 10. Phase-2 entry gates (2A audit/spike ≠ 2B implementation)

The renderer spike is **work Phase 2 performs**, not a precondition — so split the gate:

**Phase 2A — audit & spike.** *May start when:* Phase-0 routing is live behind its flag · companion specs at
least scoped · the live blueprint inventory is available · the narration-data audit can inspect trace/adapter
metadata. *Delivers:* the completed §2 card-contract inventory · renderer-spike artifacts + decision (§7) · the
§4 fact-source registry incl. required-field gaps · explicit Phase-2B scope. (This is where Q20, Q21, Q22, Q29,
Q30, Q39 are *produced*, not pre-resolved.)

**Phase 2B — narration/rendering implementation.** *May start only when:* the spike has a documented decision per
affected card type · every card in the initial rollout slice has a defined contract · every truth-bearing field in
that slice has a registered authoritative source · unresolved card types are explicitly `deferred_from_initial_rollout`
· the `AZALEA_DOMAIN_NARRATION_V2` flag + rollback path are defined (§9.1).

---

## 11. Non-goals
- **Not** a re-architecture of the blueprint system (Q38).
- **Not** a change to adapter **computation, trace state, expected answers, or validation.** Phase 2 *may* change
  the narration **interfaces that consume** those outputs — including passing `topic_type` / `domain` / approved
  framing templates into `solver.py` / `trace_pipeline.py` (§3). (The trace pipeline is the injection point, not
  untouchable — but its computed values never change.)

---

## 12. Companion specs (dependencies — correctness the gate can't provide)

The domain gate produces **better-shaped but potentially still-wrong** content. Two separate truthfulness problems:

- **`TRACE_TO_TEACHING_CONTRACT_SPEC.md` (Q23).** Which trace fields are authoritative; how process/prose cards
  reference/derive from the trace; how a prose-vs-example contradiction is detected; retries; what blocks shipping.
- **`FREE_TEXT_CONTENT_VALIDATION_SPEC.md` (Q24).** Factual checking for free-text cards — the gate cannot stop a
  false claim like `x² = −4 → (x)² = 0`.

**Exact ship rule.** Phase 2 may ship domain-specific labels, templates, and renderer layouts **before** those
companions are complete **only when every truth-bearing value is adapter/trace-backed** (§4). Any newly-generated
explanatory claim, rule justification, interpretation, or edge-case assertion **outside authoritative metadata**
must be **blocked, deferred, or validated** by the companion contract before release. **No claim may be made that
the domain system solves factual correctness** outside verified adapter-backed examples.
