# Adapter & Generation System Spec — the unified standard

> **Purpose.** One source of truth for the two systems that produce worked examples / walkthroughs:
> the **adapter system** (executable truth + teaching boundaries) and the **orchestration pipeline**
> (instance selection, prose-fill, validation, fallback, rendering). It standardizes every component so a
> single template scales to the **100+ concept adapters** — and records, per component, **what exists
> today**, **what must change**, and **what carries over unfinished from prior specs**.
>
> **Status:** v2.6 — **BASELINE. ARCHITECTURE-COMPLETE & FROZEN. Next change is code, not spec.** (v2.6
> reconciles with `ADAPTER_DEVELOPMENT_SPEC`'s four-layer trace model: adapter-owned checkpoints replace
> formatter grouping §4.3.2, the semantic-transition layer + `TeachingCheckpoint` §2.5, three-layer validation
> §4.0, the 5-step deterministic fallback §4.3.1, production evidence §6.) From here,
> the first 5–10 adapters are the test: update this doc only if the *same* implementation pain recurs across
> several of them. (v2.5 = two-lifecycle split authoring vs runtime §1.3, adapter-structure diagram §2.
> v2.4 = `TeachingProjection` explicit interface §2.5.2, §4 renamed "Orchestration pipeline". v2.3 =
> `AdapterOutput` Semantic vs Implementation split §2.6, mirror rule §2.4, "trace-preserving" narration §4.3.1.) v2.2 finalizes the trace-artifact chain with
> `LessonIntent` (§2.5/§2.5.1), `AdapterOutput` + `AdapterDiagnostics` (§2.6), adapter-owned machine-checkable
> `TeachingObjectives` / capability *services* / `TeachingProfile→Objectives` (§2.7), concept↔family split
> (§2.8), adapter-owned two-phase Truth/Teaching validation (§4.0), the **"what, never how" boundary** (§2.4).
> Supersedes the *coordination* role of the worked-example specs below; their mechanics stay valid.
>
> **Scope freeze (do not add abstractions without an implementation forcing it):** no new `*Service`/`*Provider`
> types, no further artifacts. The owners are fixed: `LessonIntent` (why) · Adapter (truth + teaching
> semantics) · `TeachingTrace` (canonical pedagogy) · Orchestrator (flow/retries/narration/rendering) · LLM
> (wording only) · Renderer (presentation only). New ideas are refinements during adapter development, not
> spec growth.
>
> **Consolidates / carries forward:** `ADAPTER_CONTRACT.md` (FROZEN), `WORKED_EXAMPLE_ACCURACY_SPEC.md`
> (v6, design-only), `WORKED_EXAMPLE_REASONING_SPEC.md` (Phase 1 implemented), `CODING_WORKED_EXAMPLE_SPEC.md`
> (v1 implemented), `GENERATION_AND_VISUAL_FOUNDATION_SPEC.md` (gen_foundation, shadow), `STUDY_PATH_CONTENT_SPEC.md`
> (M-series, partial).

**Legend:** ✅ HAVE (in code, enforced) · 🟡 PARTIAL (exists, not complete/enforced) · ❌ MISSING (to build)

---

## 1. Architecture — the two systems and the boundary

```
ADAPTER  (per concept — "truth + teaching boundaries")
  declares the ExampleSpec, runs the real algorithm, produces a verified teaching trace,
  owns conventions / stage grammar / required cases / fact contracts / visual state.
        |
        | hands over a VERIFIED trace (no LLM in the computation)
        v
ORCHESTRATION  (one per run — "selection + prose + validation + fallback")
  selects the adapter, picks a teaching instance, asks the LLM ONLY for wording,
  validates the narration, and on failure degrades to a trace-preserving narration of the
  SAME verified trace — never to a from-scratch re-derivation.
        |
        v
  legacy Goal/Reasoning/Work/Result cards -> existing renderer
```

**The core principle (carried from `ADAPTER_CONTRACT.md` §0):** *the adapter says "here are the correct
steps, explain them"; the generator never says "make correct steps."* A card must expose **one reconstructable before/after transition** and, whenever its
checkpoint contains a learner decision, **exactly one visible learner decision** (setup / formula-identification
/ terminal / invariant-confirmation checkpoints legitimately have none).

**The responsibility split (the clean three-way boundary the whole spec serves):**
- **Adapters own truth and teaching *semantics*** — what is true, which transitions/decisions matter, what a
  good example must show. **Never *how* it is written** (§2.4).
- **Orchestration owns *language*, retries, rendering, and validation flow** — instance selection, prose-fill,
  fallback, the renderer, and the `LessonIntent` (§2.5.1).
- **The LLM is reduced to *explaining verified information*** — wording over a verified TeachingTrace, never
  inventing the content.

### 1.1 Current reality vs. target (the key structural change)
- **Today there are two parallel generators.** `trace_pipeline` (the adapter orchestrator: `route_adapter →
  select_instance → reference → prose-fill formatter → validate`) **already is** the target orchestration
  layer. `gen_foundation` is a **separate from-scratch path that never calls the adapters** and re-derives
  the example with an LLM ("make correct steps"). `legacy` is a third from-scratch path.
- **The bug this creates:** when `trace_pipeline` withholds (prose/count gate), control falls to
  `gen_foundation`/`legacy`, which **discard the verified trace** and re-derive — shipping *fluent-but-wrong*
  content (observed: an incorrect Prim MST, a mis-sorted Kruskal trace).
- **Target:** for adapter-supported topics, `trace_pipeline` is the **only** path. **`gen_foundation` is no
  longer a worked-example generator for adapter-supported topics — it becomes the Tier-2 unsupported-topic
  prose/scaffold generator only.** A withhold degrades *within* the adapter trace, never to a from-scratch
  path. See §1.2 (the invariant) and §4.3 (fallback policy) — this is the single most important change.

### 1.2 Non-negotiable invariant (the hard rule everything else serves)
> **For any topic routed to an adapter, the adapter trace is the ONLY source of executable truth.** The
> system may **retry** narration, **simplify** narration (trace-preserving), or **withhold** the worked example —
> but it may **NOT** replace the trace with a from-scratch LLM-generated example. **Every rendered
> worked-example card must descend from the adapter trace.** No output for an adapter-supported topic may be
> generated from a from-scratch LLM derivation.

This invariant is **machine-checkable** and should be enforced, not just documented: an adapter-supported
topic whose final cards have `final_source ∈ {gen_foundation, legacy_*}` is a **hard violation** (today it's
merely recorded in M7; §4.3 makes it impossible). It subsumes the accuracy-spec's Phase-A1
self-floor-replacement guarantee (§5.1).

### 1.3 Two lifecycles — authoring (static) vs runtime (per-lesson)
The document spans **two distinct pipelines**; keeping them separate avoids mixing static and runtime
concepts. `TeachingProjection` is the only artifact in both — *declared* at authoring, *applied* at runtime.

**Adapter (authoring) lifecycle — runs ONCE when writing an adapter (builds infrastructure):**
```
Author → ExampleSpec → ReferenceExecutor → build_teaching_trace (semantic) → TeachingProjection → TeachingObjectives → §E behavior tests → Conformance (L0/L1/L2)
```
**Runtime lifecycle — runs for EVERY lesson (serves users):**
```
LessonIntent → adapter selection → ExecutionTrace → TeachingTrace → TeachingProjection → TeachingCheckpoint[] → Narration → Validation → Renderer
```

---

## 2. Adapter system — component inventory

The authoring contract is `ADAPTER_CONTRACT.md` (15 universal members + §0 `ExampleSpec`). Conformance is
machine-checked by `trace_adapters/contract.py` (`adapter_contract_violations` = `[now]` core;
`adapter_c1_gaps` = `[C1]` targets). **All 8 current adapters pass the `[now]` core (0 violations) and have
CLOSED all 5 `[C1]` gaps (§2.2).**

**The adapter, structurally.** `ExampleSpec` is the adapter's *declarative specification* (static config);
`AdapterOutput` (§2.6) is its *runtime output*. Everything else hangs off the adapter:
```
Adapter
  ├── ExampleSpec          declarative config — input · stages · required cases · terminal   (static, §2.1 / §0)
  ├── ReferenceExecutor    run_reference → ExecutionTrace (raw log)                           (§2.2 C1-a)
  ├── SemanticTraceBuilder ExecutionTrace → TeachingTrace (verified semantic transitions)     (§2.5)
  ├── TeachingProjection   TeachingTrace → TeachingCheckpoint[] (checkpoint selection)        (§2.5.2)
  ├── TeachingProfile      → TeachingObjectives                                               (§2.7)
  ├── TeachingObjectives   machine-checkable quality / TeachingValidationContract            (§2.7)
  └── AdapterOutput        the standardized runtime return                                    (§2.6)
```

### 2.1 What every adapter HAS today (the enforced `[now]` core)
| # | Component | Construct | Status |
|---|---|---|---|
| 1 | Identity | `slug`, `version`, family file | ✅ |
| 2 | Input rules + candidate generator | `ExampleSpec.input` (`InstanceShape`: value_type, **count = size**, value_range, structure), `must_avoid`, `candidates(seed)` | ✅ |
| 3 | Teaching-instance selector | `is_teaching_trace()` — rejects too-short/too-easy | ✅ |
| 4 | Reference executor (truth) | `reference()` → `ContractTrace` (true states + `final_answer`) | ✅ |
| 5 | Conventions | per-trace `conventions` dict (ordering, tie-break, visited-timing, granularity) | ✅ |
| 6 | **Step types for grouping** | `StageSpec.contains` roles: **required / aggregated_supporting / optional_supporting / internal** | ✅ |
| 7 | Trace + state schema | `ContractTrace` + `Step` (prior_state, state_after, operation, decision, reason, inputs) | ✅ |
| 8 | Fact contract / step | `Step.facts` (allowed_values, required_facts, forbidden_claims) + `validate_prose_claims()` | ✅ |
| 9 | Semantic equality / answer | `states_equivalent`, `final_answer_entails`, `invariant_holds`, `validate_step_shape` | ✅ |
| 10 | Visual state (per step) | `Step.visual_state` + `Step.visual_delta` | ✅ (single-kind) |
| 11 | Declarative envelope | `ExampleSpec`: stages, structure (grammar), must_exercise, terminal, output_shape, **size_tier**, tie_break | ✅ |
| 12 | **Estimated example size** | `InstanceShape.count` (input) + `coding_step_band()` (derived step count) | 🟡 (band lives in `solver.py`, not adapter) |

### 2.2 The 5 uniform `[C1]` gaps — ✅ CLOSED (machine-reported: `adapter_c1_gaps` returns `[]` for all 8)
| # | Gap | Status |
|---|---|---|
| C1-a | **Raw→teaching split** — `run_reference()` (raw log) + `build_teaching_trace(raw)` | ✅ interface / 🟡 depth — `FamilyAdapterBase` ships an IDENTITY split (today's adapters emit only teaching transitions); a **non-identity** raw→semantic split is required for high-event-density types (T5 DP, T9 relaxation, T11 backtracking) before they ship |
| C1-b | **Stable transition ids** — `required_transition_ids()` | ✅ base class (declarative `example_spec.must_exercise`) |
| C1-c | **`teaching_trace_policy`** — first-class `TeachingTracePolicy` | ✅ base class (accepts/must_exercise/must_cover/must_avoid/structure, from §0 ExampleSpec) |
| C1-d | **Structured prose facts** — predicate objects, not string lists | ✅ `fact(predicate, text, value)` dicts across graph/sequence/formula; `_fact_text` reads the surface form |

> These 5 were **identical across all adapters** → fixed once in the shared base class (C1-a/b/c) + one `fact()`
> helper (C1-d). `test_adapter_conformance.test_every_adapter_is_c1_complete` locks zero gaps.

### 2.3 What's MISSING beyond the checker (depth + enforcement gaps I measured)
| Gap | Today | Target | Status |
|---|---|---|---|
| **Multi-stage grammars** | **8 of 12 adapters already ship 2–3 stages** — dijkstra `init/settle_node/relax_edge` (per-edge improve/no-improve), bfs/dfs/kruskal/prim/merge_sort 2-stage, quadratic/kinematics 3-stage. The 4 single-stage (binary_search/bst_search/tree_inorder/arithmetic) are correctly single — one decision-bearing op per step | keep ONE learner decision per stage; add a stage only for a NEW decision, never a second OUTCOME of one (e.g. Kruskal's accept-vs-cycle-skip is ONE `consider_edge` decision, not two stages) | 🟡 **largely closed** (was mis-tracked as ❌; verified via live `example_spec.stages`) |
| **Per-suite coverage** | `must_cover = 0` on every adapter | declared `must_cover` + checked by §E behavior tests | ❌ |
| **Behavior test suites (§E)** | `test_trace_prose_adversarial.LyingFormatterIsCaught` over all 8 adapters (faithful passes, lie/out-of-range is hard) + machine-required coverage assertion | ✅ |
| **Versioned state schema** (item 6) | declared concept | enforced required/optional fields, no undeclared dynamic fields | 🟡 |
| **Visual contract as a declared set** | ad-hoc per-step `kind` strings | `{primary_kind, allowed_kinds, operation_to_kind}` + every transition's kind ∈ allowed | 🟡 |
| **Field consistency** | bfs/dfs have no `value_range`; `size_tier` uniformly "small"; `tie_break` field empty (lives in conventions dict) | every field populated + consistent | 🟡 |
| **Adapter-owned step-band — `estimate_teaching_step_band(trace) -> {min, target, max}`** | on `FamilyAdapterBase` — every adapter predicts its step count from the actual trace | drives count gate + pacing | ✅ |
| **One step-kind vocabulary** | adapter `StageSpec.contains` **and** legacy `_CODING_STEP_KINDS` (pass/split/visit/…) coexist | unify on the adapter grammar | ❌ |
| **Label convention** | walkthroughs use letters (A–F), coding uses ints (0–3) — inconsistent within one path | a declared, consistent labeling convention per path | ❌ |

### 2.4 What is explicitly NOT in the adapter (carried from `ADAPTER_CONTRACT.md` §G)
No stored example values, no fixed learner prose, no LLM prompt/rules, no presentation artifacts. The adapter
is **executable truth + a contract**. For CODING adapters the **canonical executable artifact** (algorithm:
idiomatic implementation · T10: operation simulator/sequence · T12: executable teaching specimen) is
adapter-owned INFRASTRUCTURE — required, but neither a teaching-semantic nor a phrasing field; the separate
`canonical_code` for displayed-code highlighting is a later rendering concern.

> **The boundary (the rule that stops adapters from over-growing):** **Adapters define WHAT should be taught,
> never HOW it is written.** Wording style, card titles, hooks, narration tone, emphasis, and teaching voice
> belong **entirely** to orchestration. The adapter owns truth + teaching *semantics* (which transitions,
> which decisions, what must be shown); orchestration owns *language*. If a proposed adapter field is about
> phrasing, it's in the wrong layer.

> **The mirror rule (so the boundary holds both ways):** **The orchestrator may retry narration, invoke the
> adapter-declared `TeachingProjection`, narrate, validate, and render the TeachingTrace — but it may NEVER
> compress, merge, remove, reorder, or otherwise modify its semantics itself. Any semantic change requires
> returning to the adapter.** Compression/merging lives in the adapter's `TeachingProjection` (§2.5), never in the
> formatter — this is what stops someone adding a "smart merge" inside narration six months from now.

### 2.5 The trace artifact chain — FIRST-CLASS artifacts (not just transformations) ✅ (`trace_adapters/artifacts.py`)
The raw-execution → semantic-trace → checkpoint pipeline is a **chain of named artifacts**, each independently
inspectable, validated, and cached, so truth / pacing / grouping / provenance stay local:

```
LessonIntent       WHY this example exists (see §2.5.1) — chosen by orchestration BEFORE the adapter runs
   ↓  (parameterizes instance + difficulty selection)
ExecutionTrace     the complete RAW execution log for the bounded instance (every low-level event)
   ↓  build_teaching_trace()   the adapter folds contiguous raw events into verified semantic transitions
TeachingTrace      the verified SEMANTIC-transition sequence — first-class (transition · decision · facts ·
                   before · after · operation · terminal · raw_event range). Truth + coverage read THIS.
   ↓  TeachingProjection   adapter-owned policy selecting/grouping transitions into learner checkpoints
TeachingCheckpoint[]  provenance-bearing units consumed by narration + renderers (0+ artifacts per checkpoint)
   ↓  Narration           the LLM's prose (or deterministic template) for ONE checkpoint (wording only)
Renderer           cards · timeline · animation · video · chatbot (presentation — many from one checkpoint set)
```
> **Alignment with the four-layer model (`ADAPTER_DEVELOPMENT_SPEC` §7.0).** The chain above is the SAME four
> layers, named precisely: **ExecutionTrace** = the complete raw log for the bounded instance; **TeachingTrace**
> = the *verified semantic-transition* trace (each transition may summarize a CONTIGUOUS, replayable raw-event
> range — a Floyd-Warshall `k`-layer or a DP row folds its raw cell checks while keeping a verified
> before/after + `raw_event_start/end` provenance); **TeachingProjection** = the adapter-owned checkpoint-
> selection policy OVER the TeachingTrace; **TeachingCheckpoint** = the normalized, provenance-bearing unit that
> narration + rendering consume. Runtime flow: `ExecutionTrace → TeachingTrace → TeachingCheckpoint[] →
> narration / visual compiler → cards`. This middle semantic layer keeps the trace budgets coherent for
> Floyd-Warshall / DP / merge sort / Dijkstra / backtracking (raw events ≫ bounded semantic transitions).

Why first-class (not just `build_teaching_trace()` output): the **TeachingTrace** can be diffed against the
ExecutionTrace (truth check), validated for pacing/coverage (teaching check, §4.0), re-narrated on a gate
failure (§4.3.1 step 2) **without re-executing**, and cached. `TeachingProjection` is the place compression
lives — never the formatter.

> **TeachingTrace stays SEMANTIC, never presentation.** It is `transition/decision/facts/before/after/
> operation` — **not** `Card 1, Card 2, …`. Cards are one *renderer* among several (timeline, animation,
> video, chatbot); all consume the same TeachingTrace. If a field is about layout or a card, it belongs in
> the renderer, not the TeachingTrace. It is the canonical **semantic** trace, NOT the final learner-visible
> sequence — learner-visible pacing is defined ONLY by `TeachingCheckpoint[]`, so not every semantic transition
> receives its own card or narration call.

#### 2.5.1 `LessonIntent` — WHY the example exists (orchestration-owned, upstream of the adapter) ✅ (`artifacts.LessonIntent`, `from_topic`)
The adapter produces a *correct, representative* example; **LessonIntent** says *for whom and to what end*,
so the same adapter serves beginner / interview-prep / review / implementation-focus without change:
```
LessonIntent {
  primary_goal · target_profile (§2.7) · attention_budget · preferred_depth ·
  expected_prior_knowledge · focus
}
```
It is **orchestration-owned input** to instance + difficulty selection — *not* an adapter field (the adapter
reads it, doesn't define it). Future audience variants change the LessonIntent, never the adapter.

> **`required_cases` are NOT in LessonIntent — they are adapter knowledge** (`must_exercise`, §2.1). LessonIntent
> says *"interview prep"* / *"implementation focus"*; the **adapter translates** that intent into which of its
> required cases satisfy it. Orchestration must never name algorithm-specific cases — that would put algorithm
> semantics in the orchestration layer and violate the §2.4 boundary.

#### 2.5.2 `TeachingProjection` — the interface (the most important artifact, made explicit) ✅ (`base.teaching_projection`)
The whole architecture pivots on this one mapping, so it is specified as an interface, not just prose. It is
**adapter-owned** (it's where compression/pacing decisions live, per the §2.4 mirror rule):
```
TeachingProjection
  input:   TeachingTrace       (the verified semantic-transition trace, §2.5)
  must:
    - select the required semantic transitions   (no `required` transition dropped)
    - group ONLY contiguous supporting transitions (aggregate `aggregated_supporting`; never across a decision)
    - preserve every surfaced learner decision   (decisions are never merged away — §4.3.2)
    - preserve terminal + required-case checkpoints
    - attach complete provenance to each checkpoint (source-step range + before/after — DEV spec §7.0)
  output:  list[TeachingCheckpoint]
```
A `TeachingProjection` is **valid iff** every checkpoint carries contiguous source-step provenance, the set
covers every required transition + the terminal, and the underlying TeachingTrace replays to the same states as
the ExecutionTrace (Truth, §4.0). This is the single point
where "what the learner sees" is decided — nowhere else (not the formatter, not the renderer).

> **Covers, never replaces.** A `TeachingCheckpoint` may COVER a contiguous range of supporting semantic
> transitions, but it does NOT replace them with a new semantic transition: the source transitions stay
> individually retained, replayable, and traceable, and the checkpoint exposes the range's verified
> state-before / state-after anchors. Grouping is a VIEW over the TeachingTrace, never a rewrite of it.

### 2.6 `AdapterOutput` — the single standardized return contract ✅ (`base.build_adapter_output`; `test_adapter_artifacts`)
Orchestration consumes **one object regardless of concept** (Kruskal, merge sort, DFS, binary search). It is
two contracts so a new-adapter author answers two questions **in order** — *"what is the teaching
semantics?"* then *"what infrastructure do I provide?"*:
```
AdapterOutput {

  # ── SEMANTIC CONTRACT (the teaching truth — define this FIRST) ──
  execution_trace:     ExecutionTrace           # raw log (§2.5)
  teaching_trace:      TeachingTrace             # verified semantic-transition sequence (§2.5)
  teaching_checkpoints: list[TeachingCheckpoint] # narration/render units (adapter-owned projection §2.5.2)
  teaching_objectives: TeachingObjectives        # what a GOOD example shows/avoids (§2.7)
  teaching_profile:    TeachingProfile           # easy/normal/hard → objectives (§2.7)
  validation_contract: { truth: [...], teaching: TeachingValidationContract }   # three layers; teaching adapter-owned (§4.0)
  visual_contract:     adapter-declared semantic visual state + allowed transition kinds (§2.3)
  # per-transition visual_state/delta lives on TeachingTrace; compiled_visual_frames are COMPILER output,
  # NOT adapter output — adapters never return presentation-ready frames (no-direct-frames boundary)

  # ── IMPLEMENTATION CONTRACT (the infrastructure — what services + debug info it provides) ──
  supported_services:  {ExecutionService, TeachingTraceService, VisualService, ...}  # what it implements (§2.7)
  diagnostics:         AdapterDiagnostics        # why-this-output, for debugging (§2.6.1)
  metadata:            { verification_level, step_band, slug, version }
}
```
The orchestrator never reaches inside an adapter; it reads `AdapterOutput`. New concept = produce this
object; the pipeline is concept-agnostic.

#### 2.6.1 `AdapterDiagnostics` — the why-this-output record (debugging, not user-facing) ✅ (`artifacts.AdapterDiagnostics`)
The one architectural addition that pays for itself: every `AdapterOutput` carries a structured record of the
adapter's own choices, so a failure is read, not reverse-engineered from logs:
```
AdapterDiagnostics {
  selected_instance_reason   # why THIS graph/array was chosen
  difficulty_selected        # which TeachingProfile + why
  semantic_trace_summary     # raw execution events -> verified semantic transitions (what folded + provenance)
  projection_summary         # semantic transitions -> checkpoints (what was selected/grouped and why)
  checkpoint_grouping_summary # which contiguous supporting transitions formed each checkpoint
  validation_summary         # truth + teaching results
  warnings                   # soft issues that didn't block
}
```
Complements M7 (the *pipeline* decision record) with the *adapter's* internal reasoning — "why this graph,
why two stages merged, why a card disappeared, why pacing changed" — without reading raw logs.

### 2.7 Adapter-owned QUALITY (not just correctness) ✅ (`artifacts.TeachingObjectives`, `base.teaching_objectives`)
The adapter defines what a *good* example for its concept is, not merely a valid one. Three new declarations:

**`TeachingObjectives`** — the quality target, **MACHINE-CHECKABLE** (not guidelines — these become Teaching
validators in §4.0 / M6, not prose advice):
```
must_show:                        [cycle_skip, accepting_edge, mst_completion]  # required transition ids
must_include_completion:          true
must_include_decision_transition: true
max_support_checkpoints_in_row:   2          # pacing (SEMANTIC)
reason_class_sequence:            [...]       # declared reason classes (comparison/invariant/choice/completion)
# PRESENTATION rules (max_identical_reasoning_cards, max_work_lines, no_raw_state_rendering, card layout) are
# ORCHESTRATOR-owned narration/presentation validators (§4.0) — NOT adapter objectives (§2.4 boundary).
```
Each line is a predicate the Teaching-validation phase evaluates against the verified semantic artifacts
(TeachingTrace and, where pacing or learner visibility is involved, `TeachingCheckpoint[]`) — pass/fail, not
a hint to the LLM. **These predicates ARE the adapter's `TeachingValidationContract`** (§4.0): the adapter
declares its quality rules, the orchestrator merely *executes* them — so M6 never accumulates
algorithm-specific exceptions.

**Capability SERVICES** (what the adapter implements, not boolean flags) — orchestration asks *"do you
provide this service?"*, which scales better than flag lists:
```
ExecutionService · TeachingTraceService · VisualService · ValidationService · TeachingProfileService ·
CodeMappingService · CompletionService · StepBandService · TransitionIdService
```
(An adapter not providing `CompletionService` is exactly the C4 gap, made explicit and discoverable.)

**`TeachingProfile`** (renamed from "DifficultyPolicy" — it selects a *representative teaching example*, it
does **not** change correctness): the adapter declares what easy/normal/hard look like for its concept:
```
profile: easy | normal | hard              (or a numeric complexity_score)
e.g. binary_search:  easy = 3 probes · normal = 5 probes · hard = 7 probes + duplicates + not-found
```
**`TeachingProfile → TeachingObjectives` (the explicit dependency, so they don't drift):** the profile
*produces* the objectives — easy Kruskal yields one `TeachingObjectives`, hard Kruskal another (more
required cases, tighter pacing). Selection flow: `LessonIntent.target_profile` (§2.5.1) → adapter picks a
`TeachingProfile` → that profile emits the `TeachingObjectives` instance selection + validation use.

### 2.8 Concept adapters vs family adapters (scaling to 100+) 🟡
Shared behavior lives in a **family adapter**; each concept specializes it — not 100+ independent files.
```
FamilyAdapter (e.g. GraphTraversalAdapter)   shared: graph parsing, visuals, state schema, normalizers
  ├─ BFSAdapter            concept-specific: grammar, conventions, required cases, objectives
  ├─ DFSAdapter
  └─ TopologicalSortAdapter
```
Partially present today (`FamilyAdapterBase` + the `families/` modules), but the concept/family split isn't
formalized as the inheritance contract above. Standardizing it is what makes the 100+ rollout cheap:
a new concept overrides only its grammar/conventions/objectives, inheriting parsing/visual/state machinery.

---

## 3. Coverage ladder — what happens when no adapter matches
Carried from `ADAPTER_CONTRACT.md` §H + `WORKED_EXAMPLE_ACCURACY_SPEC` §3. **A concept with no adapter never
gets a fabricated example; it degrades down a ladder of honesty.**

| Match | Tier | Guarantee | Status |
|---|---|---|---|
| Specific adapter (Kruskal) | Tier 1 | hard (verified trace) | ✅ for 8 algorithms |
| Generic family adapter — one executor for a class, **only if the concept compiles into a declared generic spec** (arithmetic/expression eval; DP-table over a recurrence DSL) | Tier 1 | hard | 🟡 (arithmetic done; DP-DSL ❌) |
| Independent answer anchor | Tier 2 | final answer verified, steps not | ❌ |
| Guided "Key process" | guided_fallback | no claim, no fake | 🟡 |
| Illustrative | non-verified | factual checks only | 🟡 |

**Unsupported-topic honesty label (required).** Any worked example NOT descended from an adapter trace must
carry a metadata trust label so unsupported content never *looks* as trusted as verified content:
```
verification_level: "trace_verified" | "answer_anchored" | "model_only" | "guided_fallback"
```
- `trace_verified` — adapter-backed (the only hard-guaranteed level; §1.2).
- `answer_anchored` — Tier 2: final answer independently checked, steps not.
- `model_only` / `guided_fallback` — no verification; the renderer should signal lower confidence.
This makes the ladder visible end-to-end and prevents a model-only example from being presented as truth.

**Variant rule (carried):** a topic gets a separate adapter **only when its declared differences change the
learner-facing semantics, trace state, required stages, terminal, or code mapping.** Internal optimizations
(e.g. union-find path compression in Kruskal) stay `internal` under the same adapter. *Forcing the wrong
adapter ships a confidently-wrong trace — soft-correct beats hard-wrong.*

---

## 4. Orchestration pipeline — component inventory
*(Renamed from "Generation system": after the refactor it barely generates — it **routes → selects instance
→ coordinates the adapter → narrates → validates → renders**. Generation is one small stage, not the role.)*

### 4.0 Three validation layers — Truth · Semantic teaching · Narration/presentation 🟡
Validation today is treated as one pass; it is really **three**, with different sources of authority. The
`validation_contract` (§2.6) carries them:

| Layer | Authority | Checks | Failure → |
|---|---|---|---|
| **Truth** | the **ExecutionTrace** + independent oracle (DEV §7.5) | replay · legal transitions · answer/invariant correct · facts no-contradiction | **withhold** (never ship wrong truth) |
| **Semantic teaching** | the adapter's **`TeachingValidationContract`** over TeachingTrace + `TeachingCheckpoint[]` (§2.7) | required transitions · terminal · decision visibility · checkpoint order · pacing / support streaks | **pick another instance or projection** |
| **Narration / presentation** | orchestrator generic validators | prose contradiction · duplicate wording · raw-state leakage · ≤2 work lines · card layout | **retry narration, then deterministic fallback** (§4.3.1) |

**Teaching validation is adapter-owned, orchestrator-executed.** The adapter *declares* its quality rules
(`TeachingValidationContract`); the orchestrator (M6) is the **generic executor** of those predicates — it
must not grow algorithm-specific exceptions. Generic shape checks (≤2 work lines, no raw dict) stay in M6;
concept-specific rules (e.g. "Kruskal must show a cycle skip") live in the adapter's objectives.

> **Three layers, not two (reconciled).** Teaching validation itself splits: **semantic teaching** (adapter-owned
> — required transitions, decision visibility, completion, checkpoint order + pacing / support-card streaks;
> failure → pick another instance or projection) vs **narration / presentation** (orchestrator-owned generic
> checks — prose contradiction, duplicate wording, raw-state leakage, ≤2 work lines, card layout; failure →
> retry narration or trace-preserving fallback). `max_identical_reasoning_cards` and `≤2 work lines` are
> PRESENTATION, not semantic — the adapter may declare a semantic `reason_class` / `required_explanation_role`,
> but phrasing caps are enforced generically by the orchestrator, keeping the §2.4 "what, never how" boundary.

The split clarifies the whole fallback logic: a **Truth** failure means the trace itself is wrong (rare —
the adapter is ground truth) → withhold; a **Teaching** failure means the *narration* is poor → retry or
trace-preservingly simplify (§4.3.1 step 2), never fall to a from-scratch path. Most current "withholds" are
mislabeled Teaching failures (`count_mismatch`) being treated as Truth failures — §4.3.2 fixes exactly that.

### 4.1 What `trace_pipeline` HAS (the real orchestrator today)
| Component | Construct | Status |
|---|---|---|
| Adapter selection | `route_adapter(topic)` | ✅ |
| Teaching-instance selection | `select_instance` (candidates → teaching gate → `reference`) | ✅ |
| **Prose-fill-only prompt** | `build_format_payload` + formatter (`fmt`) — maps verified steps to wording/code | ✅ |
| Narration validation | fidelity replay, prose contradiction (A1), edge/decision checks, count match | ✅ exists — but **count match is too strict** (the #1 fallback cause, see §4.3/§4.4) |
| Targeted retry | `_retry_feedback` (prose_fail / count_mismatch / work_too_long) | ✅ (insufficient alone — §4.3) |
| §1a stage-grammar threading | `_stage_guidance` from `example_spec.stages` → formatter | ✅ |
| Observability (M7) | `generation_report` (adapter, source, withhold reason, counts, code_validation) | ✅ |

### 4.2 What `gen_foundation` HAS (the parallel from-scratch path)
| Component | Construct | Status |
|---|---|---|
| Pre-pass config | `prepass.py` (caps §5.2, category, input gen, trace mode, required cases) | ✅ |
| Single first-pass + audit + repair prompts | `prompts.py`, `llm.py` | ✅ |
| Validators | fields / state / caps / final-answer | ✅ |
| Execution-as-truth path | `executor.py` + `reference_first.py` / `trace_first.py` (executes a **model-written** reference) | ✅ |
| Projection caps | `trace.py` PROJECTION_CAPS | 🟡 (no `graph_mst` grouping → line-trace explosion) |
| Telemetry | M7 + audit telemetry | ✅ |

### 4.3 What the generation system is MISSING (the changes)
| Change | Today | Target | Priority |
|---|---|---|---|
| **Fallback policy (keystone)** | adapter withhold → from-scratch `gen_foundation`/`legacy` → wrong example | adapter withhold → **trace-preserving narration of the same verified trace**; if unavailable → withhold/flag (no fabrication) | **P0** |
| **Single path for supported topics** | 3 competing paths; gen_foundation can win on adapter-supported topics | adapter-supported → `trace_pipeline` only; gen_foundation = Tier-2/unsupported orchestrator | **P0** |
| **`count_mismatch` gate (the #1 measured cause)** | formatter emits ≠ trace-step count → withhold → fallback; the retry isn't enough (31 of the measured withholds) | **checkpoint alignment**: validate cards against the adapter-produced `TeachingCheckpoint` set (one card per checkpoint, or a declared renderer split of ONE checkpoint; never a semantic merge across checkpoints). Count alone never withholds a checkpoint-aligned narration; formatter grouping is FORBIDDEN (§4.3.2) | **P0** |
| **`prose_fail` gate strictness** | over-strict `edge_not_discussed`/`decision_mismatch` reject correct narrations (10 measured) | hard/soft narration boundary: a hard contradiction blocks THAT narration → retry → deterministic checkpoint narration; a soft phrasing note never blocks delivery; only a Truth failure withholds an adapter-supported example | P1 |
| **Executor input-shape + signature (the `unverifiable=61` cause, #2/#5)** | A2/trace-first can't run code with a `start` param, nested `{"graph":{…}}`, or custom signatures | normalize the example input to the entry's signature (graph relabel, start-vertex, adjacency variants); broaden `_arg_candidates`; only `unverifiable` when truly unrunnable | P1 |
| **Routing-miss robustness (#1, distinct from the tail)** | empty `topic_family`/vague title/wrong `topic_type` → adapter not picked even when one exists | derive family from title before routing (already partial in `prepass`); a topic that *should* map but doesn't is a **routing bug**, not a no-adapter case — log them separately | P1 |
| **Supported topics route BEFORE generation** | a legacy/gen_foundation caller can begin generating a supported topic | any caller hitting an adapter-supported topic routes to `trace_pipeline` FIRST; gen_foundation never re-derives a supported topic nor owns adapter execution | P1 |
| **Stop the "make correct steps" overreach** | first-pass asks the LLM for structure/order/state/cases/answer | LLM does **only** prose-fill over verified skeletons | P1 |
| **graph_mst projection** | unbounded line trace | grouped to the cap (or N/A once routed to adapter) | P2 (mooted by P0) |
| **`coding_step_band` → adapter-owned** | sampled in `solver.py` | declared from grammar + input size — **required for every adapter, not just coding** (§2.2 `estimate_teaching_step_band`) | P2 |

#### 4.3.1 Fallback order for adapter-SUPPORTED topics (concrete — enforces §1.2)
```
1. LLM prose-fill over the verified checkpoints                 (the normal path)
2. retry with targeted feedback over the SAME checkpoints       (narration-gate failure)
3. DETERMINISTIC/template trace-preserving narration            (guaranteed last mile — API/narrator outage)
4. verified TEXT-ONLY payload                                   (visual compile/render failure; trace correct)
5. withhold WITH a reason                                       (only if truth validation / adapter exec fails)
Never call gen_foundation / legacy for a supported topic.
```
Steps 2–4 are the guaranteed last mile: the trace is ground truth, so a narration-gate failure simplifies the
*wording* and step 3 (deterministic) means even an API/narrator outage yields a terse verified explanation — the
*content* is never discarded and never reaches a from-scratch generator. Only a Truth failure (step 5) withholds.

> **"Trace-preserving" ≠ "deterministic."** Step 2 may even use an LLM — what matters is **semantic
> preservation**: it must never change facts, transitions, or ordering. Determinism is one way to guarantee
> that, not the requirement. (A terse template is the simplest trace-preserving narrator; an LLM constrained
> to the verified TeachingTrace is also valid.)

> **Backend owns semantic degradation; the frontend only re-renders.** The BACKEND always includes verified
> text cards when Truth succeeds, emits visual frames when compilation succeeds, and may set
> `render_mode=text_only_verified` before delivery (step 4). If the FRONTEND's own rendering then throws, it
> falls back to the already-supplied verified text cards — it never reconstructs semantics, groups checkpoints,
> or invents fallback teaching content (a browser crash can't be predicted by the backend in advance).

#### 4.3.2 `count_mismatch` acceptance criteria (when a ≠ count is OK)
Grouping is decided by the **adapter's TeachingProjection BEFORE narration** (§2.5.2) — never by the formatter.
The formatter receives one normalized **TeachingCheckpoint** at a time; each card + visual frame cites exactly
one `checkpoint_id`. A count mismatch is therefore NOT fixed by accepting arbitrary formatter grouping (that
would smuggle compression back into narration, violating §2.4). It is resolved by validating cards against the
**precomputed checkpoint set**:
```
- every learner-facing artifact (card / frame / animation phase / timeline event / chatbot turn) cites exactly ONE `checkpoint_id`
- a renderer may emit ZERO OR MORE artifacts per checkpoint, but none may span multiple checkpoints unless the adapter declares a COMPOSITE checkpoint
- no semantic merge ACROSS checkpoints (grouping is a view, never a rewrite — §2.5.2)
- every required transition + the terminal checkpoint is rendered (fixes C4, §5.4)
- no surfaced learner decision is omitted           (decisions are never merged away)
- prose has no HARD contradiction                   (soft phrasing notes never block)
```
If all hold, ship; otherwise retry, then fall to §4.3.1 step 3. **Count alone is never a withhold reason — and
the count that matters is the ADAPTER's checkpoint count, not a formatter free-for-all.**

#### 4.3.3 Prose hard/soft boundary (the measured drivers) — protect the A3 exemption
**Hard-narration** prose codes (force RETRY → deterministic checkpoint narration, NOT an immediate withhold —
only a Truth failure withholds a supported topic, §4.3.1), from the logs: `edge_not_discussed` (19),
`decision_mismatch` (13), `decision_contradiction` (12), `missing_fact` (4). **`value_not_allowed` (44 — the largest raw count) MUST
remain SOFT for code-anchored cards (A3).** If it ever regresses to hard it becomes the #1 false-withhold —
this is an invariant to protect, not just a setting.

### 4.4 Measured fallback causes (from the logs) — the evidence-ranked priority
353 generation-report entries + 133 trace-pipeline debug records; flags confirmed **on**
(`TRACE_PIPELINE/TRACE_FIRST/SHADOW/EXECUTE=1`). Each of the 9 known fallback reasons mapped to what is
*actually* firing, so the change list above is grounded, not guessed:

| # | Reason | Measured | Firing? | Addressed in |
|---|---|---|---|---|
| 7 | **Narration validation rejects adapter output** | `count_mismatch` 31 + `prose_fail` 10 = **41** | 🔴 **dominant** | §4.3 count_mismatch (P0) + prose_fail (P1) |
| 9 | **Permissive fallback** (fabricate instead of withhold) | 116 legacy/gf outputs | 🔴 **multiplier** | §4.3 fallback keystone (P0) |
| 1 | **No adapter / routing** | `no_adapter` 30 (mostly *genuine* tail) | 🟠 tail + a routing-miss subset | §3 ladder (tail) + §4.3 routing-miss (P1) |
| 2/5 | **Executor can't run code** | `code_validation: unverifiable` **61** | 🟡 code-trust only, not the WE | §4.3 executor input-shape (P1) |
| 4 | Trace > cap | `we_over_cap` ~0 now, but **fired historically** (`"25 cards over the 10-card projection"`) | 🟡 rare, pre-routing-fix | §4.3 graph_mst projection (P2) |
| 6 | Incomplete adapter projection | not the cause (projection works) | ⚪ not firing | §2.2 C1-a (present, lower priority) |
| 3 | Impossible/untriggered required case | 0 distinct | ⚪ not firing | §2 candidates/`must_avoid`/triggers |
| 8 | Feature flag off | flags confirmed on | ⚪ ruled out | n/a |
| — | **No API key at gen time** (`solver_returned_none_no_api_key` 21) | env, not architecture | ⚪ not a fallback | **Do NOT conflate:** 21 of the `None` sources are *no key*, not adapter failure. Audits must exclude these. |

**Reading:** the worst content comes from **#7 × #9** — a correct trace exists, the *narrator* trips a gate
(usually `count_mismatch`), and the permissive fallback then ships a *fluent-but-wrong* re-derivation. Fixing
the **count gate (P0)** and the **fallback keystone (P0)** together removes the bulk of wrong output; #1
routing-miss and #2/#5 executor-shape are the next tier; #3/#4/#6/#8 are not currently firing. **Caveat:** a
slice of `final_source=None` is just *no API key* (21), not a real fallback — don't over-count it.

---

## 5. Carried-over UNFINISHED items from prior specs
Consolidated here so nothing is lost; each tagged with its source spec.

### 5.1 From `WORKED_EXAMPLE_ACCURACY_SPEC` (v6 — design only, **not implemented**)
- ❌ The full **Tier 1/2/3 honesty ladder** (only Tier 1 partially live via trace_pipeline).
- ✅ **`raw execution log → verified semantic TeachingTrace → adapter-owned TeachingCheckpoint[] → cards/frames`** explicit interfaces with stable transition ids (= adapter C1-a/b — CLOSED §2.2).
- ✅ **`TeachingTracePolicy`** as a first-class adapter property (= adapter C1-c — CLOSED §2.2).
- ❌ **Terminal-vs-endpoint split**, **prose-validator hard/soft boundary** as declared structure.
- 🟡 **Phase-A1 self-floor-replacement invariant** (the "withhold, never silently degrade" guarantee) — partially via M7, not enforced as an invariant.

### 5.2 From `WORKED_EXAMPLE_REASONING_SPEC` (Phase 1 implemented, flag-gated)
- ✅ 7 deterministic adapters + `trace_pipeline` (flag `AZALEA_WORKED_EXAMPLE_TRACE_PIPELINE`).
- ❌ **Checkpoint grouping** (contiguous SUPPORTING semantic transitions → one adapter-declared `TeachingCheckpoint`; never across a decision boundary) — needed once multi-stage grammars (§2.3) land.
- ✅ Per-step **structured fact predicates** (objects = C1-d — CLOSED §2.2).

### 5.3 From `CODING_WORKED_EXAMPLE_SPEC` (v1 implemented)
- ✅ Structural-step outline + hard gate + code-anchored cards; ✅ adapter-derived step band + ceiling (this session).
- ❌ **v1.1 refinements:** input-size-aware ranges per topic, coarse/filler-pattern suspicion detection, richer required-case coverage for graph coding (`REQUIRED_CASES_BY_TOPIC` has no graph entries).

### 5.4 From `STUDY_PATH_CONTENT_SPEC` (M-series)
**Fully deferred (never started):**
- ❌ **M5 frontend polish:** Variables watch-panel (persistent-var AST detection), candidate/sorted-edge strip/frontier, code chips/highlight (§1b/§1c).
- ❌ **D2 deep** code-variant constraint (code-gen must be told the adapter's variant).
- ❌ **E2** deterministic comparison-topic injection (needs a shared-end-capability trigger decision).

**Partially done but STILL FAILING in the latest audit (must finish — these are content bugs, not polish):**
- ✅ **C4 — stopping/completion statement (FIXED).** The last card now states BOTH the stopping criterion and the answer: `_ensure_completion` appends the adapter's declared `terminal` — "Complete: a spanning tree — every vertex connected with no cycles. Final result: …". Threaded through both ship paths; digit-free terminals guarded by `test_c4_completion` (a digit would trip prose validation on the LLM path). A first-timer now sees WHY it stopped, not just the result.
- ✅ **C7 / B5 — raw-state → prose (FIXED).** Learner-facing state no longer leaks Python `repr`: `fmt_edges`/`fmt_edge`/`fmt_nodes` (graph) + `fmt_runs` (merge sort) + Dijkstra `A=∞` render every adapter's `result`/`reason`/`decision` as prose (`A–B (2)`, `tree now: A, B`, `[48], [23]`). Standing guard: `test_state_formatting.py` (all 12 adapters × seeds) + the CP7 net's raw-state check. The trace_pipeline `result` was already EVR-prose; this fixed the underlying adapter strings.
- ✅ **C1 / E4 — per-step reasoning (FIXED).** Root cause: the formatter payload omitted each step's `reason`/`decision`, and `_STAGE_GRAMMAR_RULE` told the model to lead reasoning with the generic stage `teaching_focus` — so every coding card (incl. the cycle-SKIP) shipped one identical line. Now: the payload passes the verified `decision`+`reason`; the rule leads with THIS step's specific decision (identical-to-sibling = invalid); and a deterministic backstop in `_normalize_and_attach` substitutes the verified `step.reason` if the model echoes the generic line. CP7 net asserts reasoning diversity.
- 🟡 **M6 golden-lesson *fixtures* (§H).** The content-shape *linter* shipped; `test_golden_fixtures.py` (deterministic net over 8 adapters) + `test_cp7_end_to_end_net.py` (6 topics × both modes) + `test_state_formatting.py` now cover the historical bug classes — the broader hand-authored §H fixture set (one math/one proof/one DS-op) is the remaining piece.

**Done this session:** ✅ prerequisites/complexity reveal-1-by-1, comparison-card removal, repeated-title fix, M6 content-shape linter, content-shape→retry, A2→regenerate, E1 complexity card, E3 intro v2, §1a stage-grammar threading, adapter-derived coding step band.

### 5.5 From `GENERATION_AND_VISUAL_FOUNDATION_SPEC`
- 🟡 gen_foundation is **shadow / flag-gated**; its production role is superseded by §4.3 (demote to Tier-2).
- ❌ **graph_mst projection grouping** (§4.3 P2).

### 5.6 Visual (from `VISUAL_SYSTEM_V2_SPEC` / `VISUAL_GENERATION_ARCHITECTURE`)
- 🟡 Adapter `Step.visual_state`/`visual_delta` exist, but the **declared visual_contract set** (§2.3) and the
  trace-authoritative visual pipeline wiring are partial. (Tracked in `visual_v2/README.md`; not duplicated here.)

---

## 6. Conformance & definition of done (per adapter)
Carried from `ADAPTER_CONTRACT.md` §A, extended:
- **L0 (today):** `adapter_contract_violations(adapter) == []` (the `[now]` core).
- **L1 (standardized):** also `adapter_c1_gaps(adapter) == []` (the 5 C1 gaps) **AND** real multi-stage grammar
  **AND** ships its §E behavior suite **AND** declared `must_cover` **AND** a declared `visual_contract`
  **AND** `estimate_teaching_step_band(trace)` **AND** every emitted example carries a `verification_level`.
- **L2 (full teaching contract — the §2.5–§2.8 refinements):** the adapter returns a standardized
  **`AdapterOutput`** (§2.6) with a first-class **semantic `TeachingTrace`** (§2.5) + **`AdapterDiagnostics`**
  (§2.6.1), declares **machine-checkable `TeachingObjectives`** + an adapter-owned **`TeachingValidationContract`**
  (§2.7/§4.0), the **capability services** it implements (§2.7), and a **`TeachingProfile`** that *produces* its
  objectives (§2.7); consumes (never defines) the orchestration-owned **`LessonIntent`** and translates it into
  required cases (§2.5.1); writes only teaching semantics, never wording (§2.4); and specializes a **family
  adapter** rather than standing alone (§2.8).
- **Production-ready (safe to route to users):** L2 **plus** the `ADAPTER_DEVELOPMENT_SPEC` production evidence —
  trace **replay** from initial state, an independent answer/invariant **oracle**, checkpoint-**provenance**
  validation, **visual-budget** validation, regression **fixtures**, a **fallback-payload** test, routing aliases
  + negative guards, and reviewed examples tied to the adapter **version**. L2 = "owns quality"; production =
  "proven safe to route".
- **An adapter is "standard-complete"** only at L1 (correctness + structure) and **"teaching-complete" at L2**
  (owns quality, not just truth) — then a new concept = subclass the family + fill the contract + ship §E
  tests, and the checker guarantees consistency across all 100+.

---

## 7. Sequencing (build order — evidence-ranked, §4.4)
1. **P0 — the two changes that remove most wrong content (do together):**
   (a) **fallback keystone** — adapter withhold → trace-preserving narration; supported topics →
   `trace_pipeline` only (kills #9); (b) **checkpoint/artifact alignment gate** — validate narration against the
   precomputed `TeachingCheckpoint` set (every learner-facing artifact cites exactly one `checkpoint_id`; a
   renderer may emit 0+ artifacts per checkpoint but none spanning checkpoints unless the adapter declares a
   composite checkpoint; never a semantic merge across checkpoints; never withhold on count alone) — kills the
   #1 measured cause (#7). *Both small; together they convert fluent-but-wrong fallbacks into correct examples.*
2. **P1 — the next tier of measured causes.**
   - **Multi-stage grammars (§2.3) — LARGELY DONE.** 8 of 12 adapters already ship 2–3 stages (Dijkstra
     `init/settle_node/relax_edge`, merge-sort `init_runs/merge`, Kruskal `setup_sorted_edges/consider_edge`, …);
     the 4 single-stage adapters are correctly single (one decision-bearing op). Remaining: finer splits ONLY
     where a genuinely new learner decision exists — not a priority.
   - `prose_fail` hard/soft boundary, **executor input-shape + signature** (`unverifiable=61`),
     **routing-miss** vs no-adapter split, and routing legacy/gen_foundation entrypoints to `trace_pipeline`
     BEFORE generation whenever an adapter applies (gen_foundation stays Tier-2, never re-derives a supported topic).
3. **WIRE the existing C1/L2 interfaces into the RUNTIME path + enforce them (§2.2, §2.5–§2.8):** the C1
   contracts, `AdapterOutput`, `TeachingObjectives`/`TeachingProfile`, and diagnostics already EXIST — the work
   is runtime enforcement, not building abstractions: semantic `TeachingTrace` construction (non-identity where
   raw events are dense), `TeachingCheckpoint` generation + provenance, adapter-owned semantic validation,
   generic narration/presentation validation, and the production-evidence checks (§6). *This is where adapters
   gain ownership of teaching quality at RUNTIME, not just in the contract — the highest-payoff refinement.*
4. **Family/concept refactor (§2.8):** lift shared machinery into family adapters so concepts subclass.
5. **Enforcement (§6 L1/L2):** wire §E behavior suites + `must_cover` + `visual_contract` + Teaching
   validation into the conformance checker so "passes checker" = "teaching-complete."
6. **Retire gen_foundation as a WE generator (§1.1):** Tier-2 unsupported-topic prose/scaffold only; one path.
   (Its supported-topic AUTHORITY is removed during P0; this step is the later code deletion/cleanup.)
7. **Then scale to 100+** — the template is enforced; new adapters are mechanical.

---

## 8. Relationship to existing specs
This spec is the **coordination layer / index**. It does not replace the detailed mechanics in
`ADAPTER_CONTRACT.md` (authoring checklist), `WORKED_EXAMPLE_ACCURACY_SPEC` (the ladder + interfaces),
`CODING_WORKED_EXAMPLE_SPEC` (coding path), or the visual specs — it **states the division of
responsibility, the current HAVE/MISSING status, and the migration order**, and cites those specs for depth.
When this spec and an older one disagree on *responsibility or sequencing*, **this spec wins**; for *mechanics*,
the cited spec wins.
