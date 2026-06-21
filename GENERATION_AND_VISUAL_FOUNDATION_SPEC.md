# Generation Cost + Visual Foundation Spec

Status: Implementation plan v11 (READY TO IMPLEMENT; ten review passes incorporated; architecture validated). The visual subsystem now lives in its own spec, **`VISUAL_GENERATION_ARCHITECTURE.md`** (VGA); this doc owns the text/cost pipeline and keeps only the visual **dependency contract** (§10). Single source of truth for two coupled changes:
1. **Cost reduction for text content** — fewer LLM calls/tokens, focused on worked examples, without
   losing content quality.
2. **The semantic-state keystone the visual system needs** — the per-step state/metadata that the visual
   subsystem consumes, **provisioned now but NOT triggered** (no image generation yet). The full visual
   architecture lives in **`VISUAL_GENERATION_ARCHITECTURE.md`**; this doc keeps the dependency contract
   (§10).

Relationship to existing specs: this supersedes the generation-flow parts of
`CODING_WORKED_EXAMPLE_SPEC.md` (the structural-step blueprint, kinds, gate, code anchors are kept and
referenced); the visual subsystem is specified in **`VISUAL_GENERATION_ARCHITECTURE.md`** (VGA, which
this doc's §10 points to) and it remains a companion to `VISUAL_SYSTEM_SPEC.md`. Where they conflict on
flow, this document wins.

---

## 0. North star

> Generate the complete learner-facing lesson **once**, render it directly, validate deterministically,
> audit the rendered output (always for worked examples — except fully deterministic canonical examples
> that pass deterministic coverage/continuity checks, which get a sampled LLM audit; flag-gated for
> other cards), and apply only small validated patches. Produce a compact **semantic state** for every
> example step that grounds
> validation, continuity, rendering, and future visuals. Never use multiple default
> authoring passes to discover, outline, expand, repair, and restate the same content. Never pay an LLM
> call for representation (visuals, fallbacks, IDs, layout) that can be derived.

The **keystone** is the per-step **semantic state**: one compact, typed, renderer-agnostic object
produced in the first pass. Three systems consume it — text rendering, deterministic validation, and
(later) visuals — so it is generated once and reused. Because this state is part of every example, it
is a **cost-bearing artifact**: keep it semantic and compact, never visual prose.

---

## 1. Operating model (the cost rule)

```text
deterministic topic configuration
→ first-pass lesson + example generation (ONE call, complete renderable cards + semantic state)
→ deterministic validation
→ render cards
→ second-pass audit (ALWAYS for worked examples; flag-gated for standard cards — §8)
→ apply bounded validated patch edits only
→ rerender affected cards
→ final deterministic validation
```

Hard rules:
- **No default outline call**, **no default outline→card expansion call**, **no default code-repair
  call**, **no default per-line walkthrough call**, **no separate visual-authoring call**.
- Code-repair and code-walkthrough remain **conditional** (run only when deterministic checks fail),
  never default.
- The audit (§8) is **always-on but bounded** for worked examples (≈2 calls total) and **flag-gated**
  for standard explanatory cards — never a full-lesson regeneration, never a third **normal**
  authoring/audit pass (exceptional first-pass recovery may use one targeted repair before the mandatory
  audit, §9.2). Two sanctioned exceptions: fully deterministic **canonical** examples get a deterministic
  + sampled audit instead of a mandatory one (§6); and the §9.2 recovery path.

---

## 2. Deterministic pre-pass configuration (what the model must NOT decide)

The backend computes all stable structural decisions before the call and passes them in. The model
fills content within these constraints; it does not invent structure.

Determined up front: topic type; lesson blueprint; required card sequence; optional cards; example
category; whether a worked example is needed; coding-implementation flag; whether code-walkthrough
content is needed; **required cases**; **min/target/max learner-facing example-card count**; target
detail level; topic family (recursive / iterative / formula / proof / comparison / conceptual / graph /
array); source context; available code; code language; valid source line ranges; the **exact output
schema**.

Example pre-pass config (merge sort):
```json
{
  "example_mode": "coding_implementation",
  "topic_family": "recursive_divide_and_conquer",
  "required_cases": ["split_with_slicing", "base_case_return", "recursive_return",
                     "merge_selection", "tail_copy"],
  "target_example_cards": 8,
  "minimum_example_cards": 6,
  "grouping_policy": "one card per structural transition; group all of a transition's actions into work",
  "trace_mode": "post_generation_trace"
}
```
`trace_mode` is set from **input availability** (§6.1): `post_generation_trace` (default — code generated
in-pass, executor validates after) | `preexisting_trace` (code supplied before, executor authority) |
`canonical` (deterministic) | `model_only` (no executor).

---

## 3. The first pass produces complete, renderable cards (not a plan)

The first pass emits the **entire lesson artifact** in final renderable structure: all lesson cards in
order, the worked-example setup + all step cards, concise per-card explanation, coding-implementation
explanation when applicable, practice where the blueprint requires it, **per-step semantic state**,
**code references** when tied to code, **required-case coverage markers**, and **final-answer info**
for deterministic verification.

There is **no `solution_plan` whose only purpose is to be expanded later**. The teaching plan lives
inside the generated cards and **is the object that renders**. The lesson is generated **holistically**
(one request) so flow is maintained across concept → worked example → code walkthrough → edge case →
practice → summary, and the worked example builds on earlier cards instead of re-explaining them.

For coding-implementation topics, two distinct explanations must not duplicate each other:
1. **Implementation explanation** — how the code is structured, organized by *logical blocks* (setup,
   base/stop condition, init, main loop / recursive branch, decision logic, state update,
   merge/return), **not** per nonblank line.
2. **Worked execution example** — how that implementation behaves on a concrete input, using code
   references where they add clarity.

---

## 4. Worked-example card contracts

### 4.1 Base contract (math / algorithm / proof / concept)

```json
{
  "title": "...",
  "goal": "the one subproblem this step resolves",
  "reasoning": "the single decisive justification (omit if self-evident)",
  "work": ["concrete action line", "..."],
  "result": "what is now true after the work",
  "state_delta": { "ops": ["... generic ops vs the family state_schema — §7.1"] },   // OR null
  "state_relevance": "stateful | static | none",   // precise definitions in §7
  "cases_covered": ["required_case", "..."],
  "teaching_note": { "type": "key_idea|invariant|watch_for|check", "content": "..." }
}
```
Backend-derived (never generated): `resolved_state_after` and `prior_state` (from the previous step's
resolved state, §7), points/bullet
fallback, card IDs, continuation group IDs, totals, expected step count, final-answer aliases,
frontend metadata, repeated code snippets, visual descriptions.

### 4.2 Coding-implementation schema (base + coding extension)

The coding worked example uses the base contract **plus** the four code-anchored fields. This is the
dedicated schema that de-risks generating the worked example inside the single first-pass call (the
model targets a tight, known shape).

Shown here is the **default `post_generation_trace`** shape — the model authors **teaching anchors**, NOT
executor trace IDs (which don't exist yet in this mode, §6.1). A **reconciler attaches `trace_range` /
`included_event_ids` after execution.**
```json
{
  "primary_kind": "merge",
  "subkinds": ["merge_selection", "tail_copy"],
  "explanation_mode": "implementation_how",
  "teaching_sequence_index": 5,
  "expected_state_effect": ["append_smaller_value", "advance_merge_pointer", "copy_remaining_tail"],
  "title": "Merge the two sorted halves",
  "goal": "Combine [2,4] and [3,7] into one sorted list.",
  "how": "The while loop compares the two fronts and appends the smaller, then copies the leftover tail.",
  "work": ["i=0, j=0", "2 < 3 → append 2, i=1", "4 > 3 → append 3, j=1",
           "4 < 7 → append 4, i=2", "left empty → copy [7]"],
  "result": "merged = [2,3,4,7]; returns to the call for [2,4,3,7].",
  "state_delta": { "ops": [ {"op": "append", "path": "merged", "values": [4]},
                            {"op": "set", "path": "i", "value": 2} ] },
  "code_refs": [14, 15, 16, 18, 19, 21],
  "cases_covered": ["merge_selection", "tail_copy"]
  // trace_range / included_event_ids: NOT model-emitted here — attached by the reconciler (§6.1)
}
```
The coding schema **replaces the base `reasoning` field with `how`** — *how the code performs this step*
(which construct / line does it and what it does), because a coding example teaches **how the code does
it**, not abstract justification. (Base math/proof/concept cards keep `reasoning`, §4.1.) An internal
**`explanation_mode`** (`reasoning | implementation_how`) lets the renderer stay generic while preserving
the different semantics.

**Trace-field ownership is conditional by mode (the temporal fix, §6.1):**
- `post_generation_trace` (default) → the model emits **anchors** (`primary_kind`/`subkinds`,
  `code_refs`, `expected_state_effect`, `teaching_sequence_index`) and **must NOT emit `trace_range`/
  `included_event_ids`**; the **reconciler** attaches them from the real trace after execution.
- `preexisting_trace` → the model **may** emit `trace_range`/`included_event_ids` (real events exist).
- `canonical` → the deterministic selector emits them.
- `model_only` → no `trace_range`, no executor links.

Other coding-specific fields: **`primary_kind` + `subkinds`** (classification; the *card boundary* is the
coherent teaching transition §5.1, not a single kind); **`state_delta`** (compact change; backend derives
`resolved_state_after`, §7); **`code_refs`** — a **single flat list** of 1-based source lines for the
card's highlight block (Option A). The kind taxonomy and the code-anchor rules are carried from
`CODING_WORKED_EXAMPLE_SPEC.md`; its old min-only/no-upper-cap gate is **replaced** by the projection
caps in §5.2.

---

## 5. Authoritative trace vs learner-facing teaching projection (the cost model)

The cost mistake to never repeat: treating **every internal trace event as a learner-facing card.**
The fix is two distinct objects:

```text
trace_events   : the COMPLETE authoritative runtime/semantic trace (uncapped) — for correctness,
                 verification, and future expanded/inspection visuals. NOT all rendered as cards.
teaching_steps : a SELECTED + GROUPED projection of trace_events that renders as cards (HARD-capped).
```

The example stays **complete** — the projection covers **every required case**, every *causally
necessary* transition, **representative** repeated structure, and reaches the final answer — but it does
**not** narrate every symmetric recursive call or repeated iteration. The full trace keeps all of that.
(This supersedes the earlier "show every recursive call as its own card": every call lives in
`trace_events`; the learner sees a bounded set of teaching steps.)

Each rendered card references the trace events it teaches — but **who produces that link depends on the
mode** (§6.1): in the default `post_generation_trace` the **reconciler attaches** it after execution
(the model emits anchors, §4.2); in `preexisting_trace` the **model authors** it; in `canonical` the
deterministic selector does. **Format (the attached/authored link):** an inclusive `trace_range`, plus
an optional `included_event_ids` for the **non-contiguous** case (e.g. a recursive card that shows
"call left → reach base case → return to parent" while omitting a repeated internal event in between —
an inclusive range alone would wrongly imply the omitted event belongs to the card):
```json
{ "trace_range": { "start": 12, "end": 18 },
  "included_event_ids": null,                 // null = the whole inclusive range; else an explicit list
  "primary_kind": "merge", "subkinds": ["merge_selection", "tail_copy"],
  "goal": "...", "work": ["..."], "result": "..." }
```
**Precedence (deterministic):** `trace_range` is **required** for every trace-backed step. When
`included_event_ids` is **null**, the card teaches **every** event in the range. When **non-null**, it is
the **authoritative taught-event set**, and every listed event must fall **within** `trace_range`; events
inside the range but absent from the list are **context only, not taught content** (this is what makes a
future "expand this step" deterministic).

**Trace-selection budget (per card).** Card/work-line caps (§5.2) don't bound how many trace events a
card *spans* — a card could claim `e1–e60` with 5 bullets, which is fine for text but impossible to
animate later. So each teaching step references **≤ ~8–12 trace events by default**; a larger span (up
to ~20) requires a **`compressed: true`** flag. The model may *propose* `compressed`, but the **backend
approves or rejects** it deterministically — `compressed` is valid only when **all** hold:
- the span exceeds the normal event budget, **and**
- the omitted/intermediate events share an allowed **repetitive signature**, **and**
- required-case coverage is preserved, **and**
- the card crosses **no more than one** teaching transition, **and**
- the per-step visual delta collapses to **one interpretable** state change.

A model-set `compressed` that fails any condition is rejected (the card must be split or its span
reduced).

### 5.1 Grouping rule — one card = one coherent TEACHING transition (not one `kind`)

`kind` is a **classification/validation** field, **not** the card boundary. A card may span several
adjacent trace events and several low-level kinds when they jointly explain one operation.

- **One card = one coherent teaching transition.** A whole small merge — compare, append, compare,
  append, copy the tail — is **one** card (`primary_kind: "merge"`, `subkinds: ["merge_selection",
  "tail_copy"]`), because the learner sees one move: "merge these two sorted halves." A split is one
  card; a call that immediately bottoms out is one card.
- **Start a new card only when the learner's subproblem, governing rule, visible state, or
  instructional focus changes** — not merely when the trace's kind classification changes.
- **Split a busy transition** into 2 cards only if its `work` would exceed ~6 actions, at a natural
  seam. Never split below the transition.
- **The test:** *"Can a learner read this card's `work` as one move?"* If yes → one card.

### 5.2 Hard caps on the PROJECTION (the trace stays uncapped)

The learner-facing projection has **hard maximums**; `trace_events` does not — so nothing is "cut
short" (completeness lives in the trace, and the projection still reaches the final answer + all
required cases within the cap, via grouping + representative selection):

```text
simple concept / operation       : 4–7 cards
algorithm walkthrough            : 6–10 cards
coding implementation example    : 7–12 cards
complex recursive / DP topic     : 8–14 cards
absolute exception ceiling       : 16 cards
plus: max ~6 work lines per card, a max total work-line budget, a max rendered-example token budget
```

If a complete teaching projection cannot fit the cap, the answer is to **split the topic** (§7.2) — not
to balloon one topic into a 30-card artifact, and never to recover oversize via extra default model
calls. Effect: merge sort on a 4-element input ≈ **7 teaching cards** over a ~30-event trace.

---

## 6. Trace authority — execute the code (the big cost + correctness lever)

For coding-implementation worked examples, the runtime trace should be **computed, not narrated** —
**run the code on the example input (instrumented / sandboxed)** to get the authoritative trace. *When*
the executor runs depends on whether the code exists before the call or is generated in it (§6.1): in
the default `post_generation_trace` mode the executor runs **after** the first pass and validates the
model's state/code-refs/answer; only when code **preexists** does the model consume a real trace and its
job shrink to *group + phrase*. Either way, execution eliminates state-hallucination and feeds visuals.

Why this is the keystone for coding:
- **Eliminates state-hallucination bugs** (e.g. wrong merge arithmetic) — state is real.
- **Cuts tokens** — the model annotates, it does not compute state.
- **IS the visual data** — the trace feeds the visual system (§10) directly.
- **Respects the anti-hardcoding directive** — it executes *generated* code, not a hand-written
  per-algorithm simulator.

Provisioning now (so this is plug-in-ready, not a rewrite later):
- Define the **trace interface**: `trace = run_trace(code, language, input)` → an ordered list of
  semantic states (the §7 shape) = `trace_events`. The solver consumes either an executed trace or,
  until execution is wired, the **LLM-computed state** it already emits.
- `trace_mode` config (§6.1) selects who owns the trace; until the executor is wired everything runs
  `model_only` and flipping a topic to `post_generation_trace`/`preexisting_trace` is a config change,
  not a redesign.
- **Canonical-algorithm fast path (future):** for common algorithms (merge sort, quicksort, binary
  search, BFS, DFS), execute + template the predictable steps → a near-zero-LLM-call worked example.
  Reserved by the same trace interface; not built yet. **Audit compatibility:** "near-zero LLM" refers
  to *authoring* — templated canonical content still gets a second look, but a **deterministic audit**
  (schema/coverage/continuity) plus a **sampled** LLM audit, not a mandatory per-lesson LLM audit. This
  is the one place the always-on-WE-audit rule (§8) relaxes, and only for fully deterministic content.

**Execution is gated and sandboxed.** Execute **only after deterministic parse + safety checks pass**;
otherwise fall back to `model_only` and set `trace_confidence: "low"`:
- sandboxed runner only — **no filesystem / network / process / subprocess access**;
- bounded wall-clock, memory, recursion depth, and output size;
- a deterministic input fixture (the same value used in the rendered example);
- per-language runner + instrumentation hooks;
- skip execution when the code fails to parse, has undefined names, needs unsupported imports, is
  incomplete, or is non-deterministic — fall back, never block the lesson.
A raw runtime trace is **not** automatically a teaching trace: it still passes through the projection
layer (§5) to become bounded teaching cards.

For non-coding topics there is no code to execute; the model computes the state and deterministic checks
(§9) verify what they can (e.g. arithmetic consistency).

### 6.1 Trace modes by INPUT AVAILABILITY (the temporal fix)

**The constraint that dictates the architecture:** if the implementation code is *generated inside the
first pass*, its execution trace does not exist until **after** the model has already emitted the cards.
So the model **cannot select executor trace ranges in the same call that writes the code**. Distinguish
modes by **when the code (and therefore the trace) is available**, not by a single flag alone:

```text
post_generation_trace  — DEFAULT for coding; code is GENERATED in the first pass
  one call:   code + lesson + teaching steps + MODEL-authored work, state_delta, code_refs
  after:      execute the generated code → compare the real trace against the model's state /
              code_refs / final answer → attach the real trace for future visuals →
              flag discrepancies for the audit
  the executor is a VALIDATOR + future visual-state source, NOT the first-pass authority.
  MODEL owns:    teaching steps, goal, how, work, state_delta, code_refs
  EXECUTOR owns: trace_events (produced AFTER) + the validation verdict
  → mismatches become audit patches (§8); NO extra authoring call.

preexisting_trace  — code exists BEFORE generation (user upload, supplied code, or a selected
                     canonical implementation)
  before:     execute + instrument the existing code → trace_events exist
  one call:   the model CONSUMES the real trace — selects trace_range / included_event_ids from
              REAL events and writes only goal/how/title/work phrasing
  EXECUTOR owns: trace_events, the FACTUAL trace, state_delta / resolved_state_after, code_refs
  MODEL owns:    teaching-step selection + grouping + goal/how/title/teaching_note + work PHRASING

canonical  — fully deterministic (a known algorithm with a deterministic implementation)
  deterministic implementation → deterministic trace → deterministic teaching projection / template
  DETERMINISTIC selector owns: input, initial_resolved_state, trace, code_refs, coverage map, deltas
  MODEL owns:    nothing required (optional light phrasing); audit is deterministic + sampled (§8).

model_only  — post_generation with NO executor available (non-coding, or execution failed)
  MODEL owns everything; no trace attached; visuals are withheld_untrusted (§10.1).
```

So **executor-as-first-pass-authority is `preexisting_trace` only.** The normal one-call coding flow is
`post_generation_trace`, where the executor runs *after* and validates. `trace_mode` is set from input
availability in the pre-pass config (§2): `post_generation_trace` (default) | `preexisting_trace` |
`canonical` | `model_only`.

**Field lifecycle in `post_generation_trace` (model claim → executor truth → reconciliation).** The
model's state/code-refs/answer are a **claim**, not production truth. After execution, the executor's
equivalents replace them; the model's versions are kept only as diagnostics:
```json
{ "model_claim":   { "state_delta": {"...": "..."}, "code_refs": [14,15],    "final_answer": "..." },
  "executor_truth":{ "state_delta": {"...": "..."}, "code_refs": [14,15,16], "final_answer": "..." },
  "reconciliation_status": "matched | partial | mismatched" }
```
After a successful reconciliation: `resolved_state_after` = **executor-derived** state, `code_refs` =
**executor-derived** refs, and the reconciler attaches `trace_range`/`included_event_ids` to each card
from the real trace. The implementation must never keep using model state for visuals once an executor
trace exists.

**Reconciliation threshold — a bounded audit cannot salvage a fundamental disagreement.** Classify the
mismatch deterministically:
- **minor** (final answer matches, code runs, ≤2 cards unaligned, coverage holds, ≤25% code-refs wrong)
  → the bounded audit patches wording / state / code-refs / one card (§8).
- **major** → **invalidate the worked example and enter first-pass failure recovery (§9.2)** — do NOT
  force the 5-edit audit to rewrite an example whose code and explanation fundamentally disagree.
  `major` if **any**: final answer differs · execution fails · **>2** teaching cards can't align to the
  trace · required-case coverage fails after execution · **>25%** of `code_refs` are invalid.

**Reconciler contract** (it is now central, so make it explicit — `card_anchor` + `trace_events` → the
attached link):
```json
{ "card_anchor": { "primary_kind": "merge", "subkinds": ["merge_selection", "tail_copy"],
                   "code_refs": [14,15,16,18,19,21],
                   "expected_state_effect": ["append_smaller_value", "advance_merge_pointer"],
                   "teaching_sequence_index": 5 },
  "trace_events": "...",
  "output": { "trace_range": {"start": 12, "end": 18}, "included_event_ids": null,
              "alignment_confidence": "high | medium | low" } }
```

**Reconciliation telemetry** (recorded per example — one of the most useful production signals for
whether generated examples are actually faithful to the generated code):
```json
{ "reconciliation_status": "matched | partial | mismatched",
  "unaligned_cards": 1, "invalid_code_refs_percent": 12,
  "coverage_after_execution": "passed | failed", "mismatch_severity": "minor | major" }
```

**What the reconciler checks vs. what the audit checks (`post_generation_trace`).** Draw the line
explicitly so neither over-reaches:
- **The reconciler is deterministic and structural.** It validates the **anchors** (`primary_kind`/
  `subkinds` plausible for the aligned events), the **state effects** (the model's `state_delta` ops
  resolve to the executor's `resolved_state_after`), the **`code_refs`** (the cited lines actually
  participate in the aligned events), the **final output** (model answer == executor answer), and
  **required-case coverage** (each case's claimed step aligns to a trace event that exhibits it). These
  are exact comparisons — no language understanding.
- **The reconciler does NOT judge prose.** In `post_generation_trace` the `work` is a free-text string
  array (no `support_fact_ids` exist — they are unavailable in-pass). So whether the **free-text `work`
  narration accurately describes the reconciled trace** is the **audit's** job (§8), not the
  reconciler's: the reconciler only flags the structural mismatches above; the audit reads the rendered
  card against the reconciled (executor-truth) state and patches narration that misreads it.
- **Per-line factual guarantees only exist in `preexisting_trace` / `canonical`,** where a real trace is
  present at authoring time and each `work` line carries `support_fact_ids` (§6.2). There, narration
  *is* deterministically checkable per line; in `post_generation_trace` / `model_only` it is not, and
  the audit is the safeguard.

### 6.2 Grounding `work` against the trace (structured only where a real trace exists)

`work` stays **model-narrated** (a raw trace is too code-literal for a learner) — but how it is *grounded*
depends on whether a real trace exists **at authoring time**:

- **`preexisting_trace` / `canonical` (real trace available when the cards are written):** `work` is
  **structured** so validation needs no English parsing — each line carries the fact IDs it rests on:
  ```json
  "work": [ { "text": "Compare 2 and 3.",               "support_fact_ids": ["f12"] },
            { "text": "Append 2 because it is smaller.", "support_fact_ids": ["f12","f13"] } ]
  ```
  paired with executor `work_facts`:
  ```json
  "work_facts": [ { "id": "f12", "type": "comparison", "left": 2, "operator": "<", "right": 3 },
                  { "id": "f13", "type": "append", "value": 2, "destination": "merged" } ]
  ```
  Validation (deterministic, no prose parsing): every `support_fact_id` exists; each fact belongs to a
  supporting trace event; the facts fall inside the card's taught range (or allowed context); **every
  work line has ≥1 fact**; and **every required runtime op in the card is represented by ≥1 work item.**

- **`post_generation_trace` / `model_only` (no trace at authoring time):** `work` is the lightweight
  **string array** (no `support_fact_ids` — factual grounding is unavailable in-pass). In
  `post_generation_trace` the post-call reconciler **deterministically** validates anchors, state
  effects, `code_refs`, final output, and case coverage (§6.1) and flags structural mismatches; whether
  the free-text `work` narration *reads correctly against the reconciled trace* is judged by the
  **audit** (§8), not the reconciler. In `model_only` there is no trace to reconcile against, so the
  audit carries the full narration check and visuals are withheld.

**`included_event_ids` ≠ evidence** (where a real trace exists): `included_event_ids` = the events the
card **teaches** (§5); `support_fact_ids` = the evidence for each work line. They may overlap, need not
be identical — a card can *teach* `e12–e18` while citing only the facts of `e12`, `e14`, `e18`.

### 6.3 Trace confidence is first-class metadata (drives audit + visual gating)

Every example carries:
```json
{ "trace_mode": "post_generation_trace | preexisting_trace | canonical | model_only",
  "trace_confidence": "high | medium | low",
  "trace_validation_status": "passed | partial | unavailable" }
```
Deterministic reactions:
- **executed (post_generation/preexisting/canonical) + passed** → normal audit; visuals provisioned from
  real state.
- **executed + low**, or **model_only** → the audit must focus on **state continuity + the final
  answer**; treat state as less trustworthy.
- **trace unavailable** → **visual provisioning disabled for that example** (do not derive a visual from
  unverified state). Future visual code must never treat model-derived state as equal to executed state.

### 6.4 Example input + setup ownership (and coverage-safe input selection)

Who produces the example input and `initial_resolved_state`, by mode:
- `post_generation_trace` / `model_only` → the **model** emits the example input + `initial_resolved_state`
  (the post-call executor then validates them against the real run, in `post_generation_trace`).
- `preexisting_trace` → a **deterministic example-input generator (or the executor)** derives
  `initial_resolved_state`; the model may *propose* an input only if it passes input/schema validation.
- `canonical` → the **deterministic template/input selector owns everything**: input,
  `initial_resolved_state`, trace, `code_refs`, the coverage map, and the state deltas. The model does
  **not** invent any example state in this mode (prevents a canonical example becoming a hybrid).

**Coverage-safe selection (all modes):** the chosen input must provably exercise the topic's
`required_cases` — never an arbitrary input that accidentally skips one. E.g. a 4-element merge-sort
input must force ≥1 nontrivial split, ≥1 merge selection, ≥1 tail copy, and a meaningful recursive
return. Prefer a deterministic/constrained input picker per topic family that guarantees coverage; a
model-proposed input is accepted only if a dry run hits every required case.

---

## 7. Semantic state — the shared keystone (model emits a DELTA; backend derives the snapshot)

State is **compact, typed, renderer-agnostic** and is the keystone consumed by text rendering,
validation, and (later) visuals — so producing it now is what makes visuals "wiring, not a rewrite."

**Contract: the model emits a compact `state_delta`; the backend derives `resolved_state_after`.**
This resolves the snapshot-vs-delta tension: the model pays only for the *change* (cheap), while the
system holds the *exact* resolved state for rendering, validation, and independent inspection of any
card.
The chain needs an explicit **origin**: the setup card carries `initial_resolved_state` (the state
before step 1), so the backend never has to infer the starting state from prose, code, or the first
delta.
```json
// setup card
{ "initial_resolved_state": { "array": [34, 7, 23, 11], "active_range": [0, 3], "call_stack": [] } }

// each step: model emits a delta; backend derives the next snapshot
{ "state_delta": { "ops": [ {"op":"append","path":"merged","values":[4]}, {"op":"set","path":"i","value":2} ] } }
{ "resolved_state_after": { "left": [4,7], "right": [3,42], "i": 2, "j": 1, "merged": [2,3,4] } }
```
Derivation: `initial_resolved_state → +delta₁ → resolved₁ → +delta₂ → resolved₂ → …`.

Rules:
- **Semantic, not visual** — **never** colors, coordinates, SVG, layout, or prose.
- **Compact** — paid on every step; no redundancy with `work`/`result`.
- A malformed delta is contained: validation (§9) checks each `resolved_state_after` connects to the
  next; if a delta can't resolve, flag that card rather than corrupting the chain.
- **State may be absent — `state_relevance` has three precise values:**
  - **`stateful`** → the step mutates a structure over time; `state_delta` is a non-null `ops` list and
    the backend derives `resolved_state_after` (arrays, pointers, call stacks, DP tables — the §7 chain).
  - **`static`** → a **stable semantic object exists** (a claim/dependency map, a comparison table, a
    fixed formula representation) but **no mutable `state_delta` is needed**: `state_delta` is `null`,
    and the object lives in its own typed field (`claim_map` / `comparison` / `formula_repr`), not in
    mutable state. The object is still machine-checkable and can still drive a visual (§10), it simply
    does not *evolve* step-to-step.
  - **`none`** → **no semantic object is needed at all** (a purely narrative/transitional step):
    `state_delta` is `null` and there is no static object either.

  Forcing a delta onto a `static`/`none` step invents fake data; such a step still passes its content
  contract on its own fields.
- **Payload size is bounded** (a delta is still a delta if it copies giant arrays every step).
  Validation (§9) enforces: **max state paths per step**, **max collection length embedded in a
  delta**, **max nested depth**, **max retained call-stack frames**, **max entities in a base scene**.
  Store full data only when it changed or is required for independent rendering; for long collections
  store **references / ranges / patch ops**, not copies.

Per-family resolved shapes (what the derived snapshot looks like):
```text
array sort        → { array | merged, low/mid/high or i/j/k pointers, active_range }
binary search     → { nums, low, mid, high, eliminated_range, active_range, target }
graph traversal   → { current_node, queue | stack, visited[], frontier[], discovered_edges[] }
recursion         → { frame, depth, call_args, return_value, call_stack[] }
dp / grid         → { table (2-D), filled_cells[], current_cell }
formula / math    → { expression, substitution, simplified }
```
The resolved state's structure **plus topic context** implies the visual shape (§10.1) — this is the
bridge.

### 7.1 Delta-key discipline (no free-form keys)

Free-form delta keys produce near-duplicates (`merged_append` / `appendMerged` / `new_merged_values`;
`left_index` / `left_idx` / `left_pointer_move`) that make validators and visual derivation brittle. So
deltas use a **generic operation form against a per-family `state_schema` with a closed set of allowed
paths** — the schema is part of the deterministic pre-pass config (§2):
```json
{ "ops": [ { "op": "append", "path": "merged", "values": [4] },
           { "op": "set",    "path": "i",      "value": 2 } ] }
```
Allowed `op`s: `set | append | remove | push | pop | add | move | clear`. Each `path` must exist in the
family's `state_schema` (e.g. `merge_state_v1` declares `left, right, i, j, merged, frame,
return_value`); validation (§9) rejects an op on an undeclared path. This keeps deltas machine-stable
across arbitrary concepts while still letting any concept define its own schema.

**Ownership by mode (no merging of model + executor state):**
- `post_generation_trace` / `model_only` → `state_delta` (the `ops`) is **required from the model**
  (the post-call executor then validates it against the real run, in `post_generation_trace`).
- `preexisting_trace` / `canonical` → `state_delta` is **forbidden in model output (ignored if
  present)**; the executor / deterministic selector supplies `state_delta` + `resolved_state_after`.
  Never merge the two sources "just in case."

### 7.2 Response budget (one holistic call, bounded by construction)

The single first-pass call is the default, but it must not silently compress later sections or degrade
JSON as the output grows. Enforce a deterministic budget: a **max output size per card role**, **max
work lines per worked-example card**, a **total lesson card max**, and a **total example-state max**.
When a concept would exceed the budget, **split it into two topics** at planning time — never grow one
topic into a 30-card artifact and never recover oversize with extra default model calls.

---

## 8. Second pass — bounded patch-only audit

**Policy (split by artifact):**
- **Worked examples: the audit ALWAYS runs.** The rendered artifact exposes problems raw validation
  cannot — awkward density, broken flow, an example that technically reaches the answer but teaches
  poorly, content/state mismatch. The worked example is the highest-value, most-failure-prone artifact,
  so it earns a guaranteed second look. The audit stays cheap by being tightly bounded (below).
- **Standard explanatory cards (background, components, edge case, summary): audit is FLAG-GATED** —
  run only when a trigger fires. These rarely need a rendered second look.

Either way the auditor inspects the rendered learner-facing artifact + resolved state + the
deterministic validation report (**text + state only — never screenshots/vision**, §10), and returns
**only bounded patches**. It is kept inexpensive: compact rendered representation (not giant source
context), `pass_no_edits` required when clean, ≤5 patches, no re-authoring, no third pass. This keeps
generation at a predictable **2 calls** for worked examples while replacing the old 4–5-call system.

**Trigger flags for the flag-gated path (any → run the audit):**
- `final_answer_uncertain` — the deterministic final-answer match was fuzzy or failed.
- `required_case_uncovered` — a required case is not clearly tagged.
- `count_at_extreme` — card count at/near the minimum or the §5.2 cap.
- `mechanics_floor_failed` — a coding card has no code/runtime signal.
- `arithmetic_inconsistent` — the deterministic merge/concat check tripped.
- `adjacent_duplicate` / `title_similarity_high` / `repeated_opening_phrase` — repetitive rhythm.
- `card_density_outlier` / `step_length_variance_high` / `card_text_overflow_risk` — presentation issues
  the rendered artifact exposes that raw JSON did not.
- `semantic_state_jump_large` / `work_to_result_mismatch` — a step that doesn't connect.
- `code_reference_density_low` — coding cards with few/no `code_refs`.
- `json_repaired` — first-pass JSON needed repair (low-confidence signal).
- `unknown_topic_family` — no deterministic validator/trace confidence for this topic.
- `sample` — a small random % (e.g. 5%) for drift monitoring even when clean.
- *(future, visual mode)* `layout_overlap`, `label_collision`, `contrast_failure`,
  `required_entity_not_visible`, `visual_text_focus_mismatch`.

**Patch contract** (the auditor never regenerates the lesson/example):
```json
{ "status": "pass_no_edits | pass_with_edits",
  "edits": [ { "op": "...", "card_id": "...", "...": "..." } ] }
```
Allowed ops: `replace_field`, `replace_fields` (one card), `merge_cards` (adjacent), `split_card`,
`delete_card` (redundant), `insert_card` (one), `update_state`, `update_code_refs`,
`update_case_coverage`, `pass_no_edits`. Forbidden: change the blueprint, rewrite all cards, exceed
the card cap-by-count rules, add unsupported fields, replace with an unrelated example, add visual
prose/layout.

**Edit budget:** ≤5 edits; ≤2 structural (merge/split/insert/delete); ≤1 insert; no required-case
coverage lost; no code change without a deterministic reason. **If a patch fails post-audit validation
(§9), reject only that patch and ship the valid first-pass output — never a third generation pass.**

**Prefer `pass_no_edits`.** The audit instruction must end with: *"Prefer `pass_no_edits` unless there is
a concrete correctness, completeness, clarity, density, continuity, or text-state mismatch. Do not edit
merely to express a different writing style."* This stops the second model from making needless
stylistic changes that add drift and make a reliable first pass look unreliable.

**Field-by-card-type (so the auditor checks the right thing):** for **coding** cards audit whether
**`how`** explains the implementation mechanism (which construct/line and what it does); for
**math/proof/concept** cards audit whether **`reasoning`** gives the decisive justification. The auditor
must NOT demand abstract justification on a coding card or a code mechanism on a concept card.

**Patch provenance + telemetry** (recorded per audit — the signal that tells you whether the first pass
is improving, the audit is over-correcting, which card types fail, and whether validators are too
strict/weak):
```json
{ "audit_status": "pass_no_edits | pass_with_edits",
  "audit_trigger": "worked_example_required | <flag>",
  "patches_proposed": 3, "patches_applied": 2, "patches_rejected": 1,
  "rejection_reason": "state transition invalid" }
```

---

## 9. Deterministic validation (before render, and after audit patching)

**Before render:** valid schema; mandatory cards present; valid ordering; example setup present;
required cases covered; card count within **[minimum, §5.2 cap]**; nonempty required fields; final
answer present; every `state_delta` resolves to a valid `resolved_state_after`; valid `code_refs`; no
unsupported fields; no duplicate IDs.

**After audit patching:** all of the above, plus: patches changed only allowed fields; order still
valid; no card became empty; no required-case coverage lost; final answer still matches; state
transitions still connect (each `resolved_state_after` chains to the next); `code_refs` still valid;
rendered card lengths within limits.

### 9.1 Projection coverage map (the trace ↔ teaching link)

A backend-derived structure that proves the bounded teaching projection actually corresponds to the
complete trace — required to verify a case isn't merely *tagged* but unsupported by its `trace_range`,
and that the final teaching step maps to the terminal trace state. Re-checked after any audit
merge/split/delete.
```json
{
  "projection_coverage": {
    "required_cases": { "split_with_slicing": ["step_1"], "base_case_return": ["step_2"],
                        "recursive_return": ["step_4"], "merge_selection": ["step_5"],
                        "tail_copy": ["step_5"] },
    "final_trace_event": "e30",
    "teaching_step_reaching_final": "step_7"
  }
}
```
Validation: every required case maps to ≥1 step **whose `trace_range` actually contains an event for
that case**; `teaching_step_reaching_final` exists and its range includes `final_trace_event`; no step
claims a case its trace range does not support.

**Mode-aware (a validator must not claim trace-backed proof when no trace exists yet):**
- `preexisting_trace` / `canonical` → trace events exist at authoring time, so **trace-backed coverage
  is required before render**.
- `post_generation_trace` → **provisional** (semantic) coverage before execution; **authoritative**
  trace-backed coverage **after reconciliation** — the audit receives the authoritative version.
- `model_only` → **semantic coverage only** (`cases_covered` + state/final-answer checks); no
  trace-backed proof is possible or claimed.

### 9.2 First-pass validation failure (recovery path, not normal flow)

The patch rule (§8) covers a failed *audit* patch. The **first pass itself failing** schema/coverage/
state validation is a separate error path — there is no valid output to ship, so the "no third pass"
rule does not apply (this is exception handling, not normal generation):
1. **Deterministic normalization/repair first** — apply only **lossless** fixes (reorder cards,
   re-derive IDs, drop a stray unsupported field).
2. If still invalid, **one targeted repair call** — hand the model the invalid artifact + the concrete
   validation errors; bounded, not a full re-author.
3. If repair still fails, **ship a safe degraded lesson** (e.g. omit the worked example and flag it) or
   **fail generation visibly** — surface it, mark the topic, let the learner regenerate.
4. **Never silently ship a semantically invalid worked example.**

**Call count on this exceptional path:** if the targeted first-pass repair (step 2) succeeds, the
worked example then still runs its **mandatory audit** (§8) — so this *recovery* path may use **3 calls
total** (first pass + repair + audit). That does not contradict "never a third pass": the "no third
pass" rule governs the *normal* flow; step 2 is error recovery for an invalid first pass, not a routine
authoring pass.

---

## 10. Visual system — see VISUAL_GENERATION_ARCHITECTURE.md

The visual subsystem has grown into a self-contained architecture (steering, generation, acceptance
validation, a versioned Visual Memory Database, retrieval/adaptation, curation, and a future-compatibility
roadmap) and now lives in its own spec: **`VISUAL_GENERATION_ARCHITECTURE.md`** (VGA). This section keeps
only the **contract the cost/text pipeline depends on**; everything else moved to VGA. (Former §10.x
references elsewhere in this doc map to VGA per its appendix table.)

**Provisioned, not triggered.** Build the visual schemas + deterministic validators now; no image-model
call or render until `AZALEA_VISUALS_ENABLED=true` (VGA §14). Turning visuals on is wiring, not a
text-generation change.

**The dependency contract (what the text pipeline guarantees the visual subsystem):**
- The per-step **semantic state** — model `state_delta` -> backend-derived `resolved_state_after` from an
  explicit `initial_resolved_state` (§7) — is the **shared keystone** VGA consumes. Its type structure +
  topic context implies the visual shape (VGA §5). Produce it regardless of whether visuals are on.
- **`trace_confidence`** (§6.3) gates visuals: executed + passed -> visuals may provision from real state;
  low / `model_only` / trace-unavailable -> **withhold** the visual (VGA `visual_status:
  withheld_untrusted`); never derive a visual from unverified state.
- `state_relevance` (§7): `stateful` state drives evolving visuals; a `static` object can still drive a
  (non-evolving) visual; `none` has no visual.
- Visuals add **zero** model calls while the flag is off and amortize to **~one image generation per
  topic** when on (VGA §15) — never one per card.

**Central rule (still binding):** the model decides what a visual *means*; deterministic systems
decide/enforce exact structure, geometry, layout, validation, and acceptance (VGA §2/§10). The model
never emits coordinates, SVG, colors, or sizes.

For the full architecture — canonical-image ownership, visual types + shape descriptions, the primitive
grammar, base-scene/delta + layered assets, structural representation, the visual contract + image
acceptance validation, the Visual Memory Database (retrieval thresholds, versioning, feedback learning,
curation), the end-to-end lifecycle, and the future-compatibility roadmap — **see
`VISUAL_GENERATION_ARCHITECTURE.md`.**

---

## 11. Cost model (current → target)

Per coding topic, default LLM calls:
```text
current:  lean lesson (1) + clean-code (1, conditional) + line-walkthrough (1)
          + WE outline (1) + WE cards (1)                          ≈ 4–5 calls
target:   first pass (1) + worked-example audit (1, ALWAYS)
          + standard-card audit (0–1, only if flagged)             ≈ 2 calls (3 only when flagged)
later:    canonical algorithm: deterministic generation + deterministic
          audit + SAMPLED LLM audit                                ≈ 0 calls normally, 1 when sampled
```
Per non-coding topic with a worked example:
`lean (1) + WE outline (1) + WE cards (1) = 3` → `first pass (1) + WE audit (1) ≈ 2`.
The worked-example audit is **mandatory** (§8), so the steady state is **2 calls**, not 1; a topic with
no worked example can ship at 1 call (its standard-card audit is flag-gated).
**Measure tokens, not just call count** — one holistic call sends context once instead of N times, but
the semantic state is paid per step, so keep it compact (§7). **Visual cost (when triggered):** the
deterministic substrate — semantic state, metadata, shape descriptions, retrieval keys, validators —
adds **zero** model calls (all derived). The image-generation track adds an **image-model call only for
a new canonical base visual** (§10.7), plus **bounded regeneration retries** when acceptance validation
(§10.11) rejects it; per-card reuse via **annotation** (§10.7) and DB **retrieval** (§10.9) add **zero**
image calls, and reference-regeneration runs only at a real structural transition. A **retrieval hit**
(≥0.90 similarity, §10.9) costs **zero** image calls. So steady-state visual cost amortizes toward
**≈one image generation per topic** (less as the Visual Memory DB fills and retrieval hit-rate climbs),
not one per card. While `AZALEA_VISUALS_ENABLED=false`, visual cost is **zero**.

---

## 12. Sequencing (don't big-bang a stabilized system; prototype before replacing)

The old gate is tied to the old outline→cards architecture, so do **not** optimize grouping inside the
legacy path that is about to be removed. Build the new schema in a **shadow** generator first, measure,
then replace.

1. **Define the new schemas + deterministic validators** — card contracts (§4), `state_delta` + derived
   `resolved_state_after` (§7), trace/projection (§5), caps (§5.2), projection-coverage (§9.1),
   confidence metadata (§6). Pure, unit-tested; no production change.
2. **Build a shadow single-pass generator behind a feature flag** — first pass → teaching steps (with
   anchors, §4.2) + state deltas + caps → deterministic validation. Renders nothing in production yet.
3. **Add the bounded worked-example audit** (§8) — always-on, patch-only; measure its edit rate.
4. **Add `post_generation_trace` reconciler stubs** (§6.1) — anchor→trace mapping + the
   model_claim/executor_truth reconciliation contract (executor itself can be stubbed first).
5. **Generate comparison fixtures** across representative topics (binary search, merge sort, BFS/DFS,
   linked list, DP, a math/proof, a concept). Measure **card count, output tokens, first-pass validity,
   audit edit rate, reconciliation status, final quality** vs the legacy multi-call solver.
6. **Replace the legacy outline/cards route** once the shadow path wins on the measures — and only then
   retire the old grouping gate.
7. **Wire the real code executor** (§6) once the first-pass lesson path is stable — replace the
   reconciler stubs; flip `trace_mode` to `post_generation_trace` (or `preexisting_trace` when code is
   supplied) per topic.
8. **Add visual provisioning** (§10.6 "build now") — composite-key/visual-type inference, base-scene/
   delta derivation, semantic/topological validators (the deterministic half of the §10.11 acceptance
   test), **metadata derivation + shape descriptions** (§10.8/§10.10), the **Visual Memory DB schema +
   retrieval keys + full-asset/version/feedback record + similarity-threshold config** (§10.9/§10.12,
   empty), and the **acceptance-validation interface** (§10.11) — all behind `AZALEA_VISUALS_ENABLED=
   false`. No image call, no render.
9. **Turn on the image-generation track** (later, behind the flag): canonical base visual per topic
   steered by visual type + shape + metadata, **gated by image acceptance validation** (§10.11, with
   bounded regenerate-on-fail); the retrieve→(confidence-thresholded)→adapt→store loop (§10.9) populating
   the Visual Memory DB with **versioned, validated assets** (§10.12); the annotate vs.
   reference-regenerate adaptation (§10.7). Then, independently: the **regeneration-feedback learning
   loop** + quality scoring + version promotion/revert (§10.12), the vision half of acceptance
   validation (§10.11), the deterministic structural renderer + geometric validation, and the canonical
   algorithm fast path.

---

## 13. Resolved decisions (so they aren't re-litigated)

- **Trace vs projection** → keep the **complete trace** (`trace_events`, uncapped) for correctness +
  future visuals; render a **bounded teaching projection** (`teaching_steps`, hard-capped §5.2). The
  example is complete (reaches the answer + all required cases) without narrating every symmetric
  event. *Supersedes "every recursive call as its own card."*
- **Card boundary** → *one coherent teaching transition*, may span several `subkinds`; `kind` is
  classification, not the boundary (§5.1).
- **Caps** → hard max on **learner-facing cards** (the trace is uncapped); oversize → **split the
  topic**, never balloon or add default calls (§5.2, §7.2). *Replaces the old min-only/no-upper-cap.*
- **Audit** → **always-on** (bounded, patch-only) **for worked examples** (steady state = **2 calls**);
  **flag-gated** for standard explanatory cards (§8, §11). Never whole-lesson regeneration, never a
  third pass.
- **Semantic state** → model emits a compact **`state_delta`** (generic ops vs a closed per-family
  `state_schema`, §7.1); backend derives **`resolved_state_after`** from an explicit
  `initial_resolved_state` (§7). Cheap to author, exact to render/validate.
- **Trace** → `trace_range {start,end}` + optional `included_event_ids` for non-contiguous (§5); a
  backend **projection-coverage map** proves cases↔trace + final-step↔terminal-state (§9.1).
- **Trace modes by INPUT AVAILABILITY (§6.1)** → `post_generation_trace` (DEFAULT: code generated
  in-pass, model authors state/work, executor validates **after** + feeds visuals) | `preexisting_trace`
  (code supplied first → executor is first-pass authority, model selects/phrases) | `canonical`
  (deterministic owns all) | `model_only` (no executor). **The model never selects executor trace ranges
  in the call that generates the code.** Sandboxed; **`trace_confidence`** is first-class and gates audit
  + visuals (§6.3). `work` is structured (`support_fact_ids`) only where a real trace exists (§6.2).
- **Code refs** → a **single flat line list** per card (Option A), not per-`work` mapping (§4.2).
- **Visuals now** → *(v4–v8 framing; the "exact-structural only / no image model" scope is **superseded
  by v9 §10**, which makes image generation primary; the composite-key/archetype/contract machinery below
  is **retained** as the steering + acceptance + retrieval layer.)* archetype from
  `topic_family + mode + card_role + primary_kind + state_schema + visual_goal`,
  not state keys alone (§10.1). `visual_archetype` is a known archetype **or `null`**; **status is a
  separate field** `visual_status` (`supported` / `unsupported` = no grammar / `withheld_untrusted` =
  low trace confidence) — never a forced bad visual (§10.1). Entities/relations carry **immutable IDs**
  stable across steps (§10.5).
  `component_diagram` replaces the vague `scene`. A dormant `reference_profile` future-proofs reference
  retrieval. Illustrative/hybrid is a later, costlier track.
- **Keystone** → *one compact semantic state*, produced now, consumed by text + validators + (later)
  visuals (§7) — the artifact that makes "turn on visuals" cheap.
- **Temporal fix (v6)** → trace modes are by **input availability** (§6.1), resolving the impossibility
  of selecting executor trace ranges in the call that generates the code: the default
  `post_generation_trace` runs the executor **after** as a validator + visual-state source;
  executor-as-first-pass-authority is `preexisting_trace` only. `work` is **structured**
  (`support_fact_ids`) only where a real trace exists (§6.2); `state_delta` uses the **`ops`** shape
  everywhere (§7.1); canonical mode's deterministic selector owns input/state/trace (§6.4); the
  first-pass *repair* path may legitimately use **3 calls** (first + repair + mandatory audit) without
  violating "no third pass" in the normal flow (§9.2).
- **Reconciler + anchors (v7)** → in the default `post_generation_trace`, the model emits **teaching
  anchors** (`primary_kind`/`subkinds`, `code_refs`, `expected_state_effect`, `teaching_sequence_index`)
  and **must NOT emit `trace_range`/`included_event_ids`** (the trace doesn't exist yet); a **reconciler
  attaches them after execution** (§4.2, §5, §6.1). The model's state/code-refs/answer are a
  **`model_claim`** reconciled to **`executor_truth`** (`matched|partial|mismatched`); after success the
  resolved state/refs are executor-derived and model state is never used for visuals (§6.1). A
  **minor/major reconciliation threshold** routes a fundamental code-vs-explanation disagreement to §9.2
  recovery instead of abusing the 5-edit audit (§6.1). Projection coverage is **mode-aware** — provisional
  pre-execution, authoritative post-reconciliation; `model_only` is semantic-only (§9.1). Internal
  **`explanation_mode`** (`reasoning | implementation_how`) keeps the renderer generic (§4.2). Visuals
  allow a **scene family per visual phase**, not one forced scene (§10.4).
- **Final polish (v8)** → base contract makes `state_delta` explicitly **nullable** with
  `state_relevance: stateful|static|none` (§4.1); the **reconciler has an explicit input/output
  contract** + **reconciliation telemetry** (§6.1); the audit checks **`how` on coding cards /
  `reasoning` on math-proof-concept** cards (§8); canonical steady-state cost is **≈0 calls (1 when
  sampled)** (§11). Sequencing (§12) adds an explicit reconciler-stub step.
- **AI visual generation + two precision fixes (v9)** →
  - **Visuals are now image-generation-primary** (§10): the main production mechanism is an **AI image
    model steered by visual type + shape description + metadata** so the result is conceptually correct
    (a BST always looks like a valid BST), **not** "exact-structural only / image-gen out of scope" as
    v4–v8 framed it. The v8 deterministic substrate (semantic state, primitive grammar/visual types,
    archetype/shape inference, intent packet, visual contract) is **retained as the control + validation
    + retrieval layer**: it steers generation, the **visual contract (§10.5) becomes the acceptance test**
    that decides if a generated image is correct enough to store, and it supplies the **retrieval keys**.
    Deterministic structural rendering remains a complementary exact option.
  - **One canonical visual per topic, reused/adapted** (§10.7): generate one validated base image per
    topic; per card either **annotate** (structure unchanged → highlights/arrows/labels/overlays, no
    regeneration) or **reference-regenerate** (structure changed → new image using the prior as
    structural reference). The annotate-vs-regenerate choice is **deterministic from the resolved-state
    delta + scene change** (§7/§10.4).
  - **Visual Memory Database** (§10.9): retrieve→reuse/reference→generate+store; only **contract-passing**
    visuals are stored; metadata (§10.10) is the **semantic** retrieval index (by concept/shape/family,
    not pixels). Provision the **schema + retrieval keys now (empty)**, populate later behind the flag.
  - **Visual types + shape descriptions** (§10.8): generation is guided by a closed visual-type
    vocabulary (the §10.2 primitives) + per-concept-family shape descriptions, which also serve as the
    topological acceptance test — never open-ended prompting.
  - **`state_relevance` defined precisely** (§7): `stateful` (mutable `state_delta`) / `static` (a stable
    semantic object exists — claim map / comparison table / formula repr — but **no** mutable delta,
    `state_delta: null`) / `none` (no semantic object at all).
  - **Reconciler vs audit split sharpened** (§6.1/§6.2): in `post_generation_trace` the reconciler is
    **deterministic** — it validates anchors, state effects, `code_refs`, final output, and case
    coverage; the **audit (not the reconciler) judges whether the free-text `work` narration accurately
    describes the reconciled trace.** Per-line factual guarantees (`support_fact_ids`) exist **only in
    `preexisting_trace` / `canonical`.**
  - **Cost** (§11): the deterministic substrate stays **0 model calls**; image generation amortizes
    toward **≈one image per topic** (less as DB retrieval hit-rate climbs); **0 while the flag is off.**
- **Visual lifecycle hardening (v10)** → the visual system gains an explicit, self-improving lifecycle
  (§10.11–§10.13):
  - **Image acceptance validation** (§10.11): a generated image must **earn** its way in — validate
    against the concept contract (depicts the concept? correct shape? required present / forbidden
    absent? clear enough to teach?); **pass → store, fail → regenerate with feedback** (bounded, else
    withhold + text-first). **Structural correctness is MANDATORY and gates storage; visual style is
    cosmetic** and never overrides correctness (a pretty-but-wrong image is rejected).
  - **Retrieval confidence thresholds** (§10.9): `≥0.90 reuse · 0.65–0.90 adapt(reference) · <0.65
    generate new` — never force a weak/unrelated reference onto a different concept.
  - **Versioned, full-asset records** (§10.12): the DB is a **curated library, not a cache** — store the
    image **plus** metadata, shape description, `validation_result` + **`validation_reason` (why it's
    good)**, generation prompt, adaptation history, quality score, usage count, user feedback; **keep
    versions** (promote a better one, revert a worse one — never overwrite).
  - **Learn from regenerations** (§10.12): a user regeneration is feedback (`unclear | wrong_shape |
    wanted_more_detail | incorrect_example | too_much_text`), recorded and fed back into retrieval
    ranking + adaptation so the library is **self-improving**.
  - Provision the schema + deterministic acceptance half **now**; image-gen, the feedback loop, version
    promotion, and the vision-audit half run **later behind the flag** (§10.6, §12 steps 8–9).
- **Visual subsystem extracted to its own spec (v11)** → §10 had grown into a self-contained subsystem,
  so the full visual architecture now lives in **`VISUAL_GENERATION_ARCHITECTURE.md`** (VGA); this doc's
  §10 keeps only the **dependency contract** (the semantic-state keystone, `trace_confidence` /
  `state_relevance` gating, the zero-cost-when-off / ≈one-image-per-topic cost). The extraction also folds
  in the reviewer's structural improvements: **canonical-image ownership** (topic owns; cards reference,
  VGA §3); **generation-vs-retrieval metadata split** (VGA §12.2); **store the structural representation**
  so visuals can be regenerated when image models improve (VGA §9); **periodic DB curation** (VGA §12.6);
  **independent annotation/animation/interaction layers** over a base image (VGA §8); a single
  **end-to-end lifecycle** diagram (VGA §13); and a **future-compatibility** roadmap — interactive
  visuals, click-to-explain, visual quizzes, animation, adaptive highlighting, model-upgrade image
  replacement (VGA §16). Former §10.x references map to VGA via its appendix table.
  **Status: ready to implement — start at §12 step 1 (text pipeline); visuals provisioned per VGA §14.**
- **Contract precision (v4)** → `included_event_ids` precedence + a per-card **trace-event budget**
  (~8–12, ≤20 if `compressed`) (§5); narration grounded via an executor **`work_facts`** layer +
  per-line `support_fact_ids`, not prose parsing (§6.2); **`state_delta` model-emitted only in
  post_generation_trace/model_only; executor/deterministic-supplied in preexisting_trace/canonical**
  (§7.1); **coverage-safe example input** that provably hits every required case (§6.4); audit
  **prefers `pass_no_edits`** + emits **patch telemetry** (§8); three-way **`visual_status`**
  (`supported` / `unsupported` / `withheld_untrusted`) separating "no grammar" from "untrusted state"
  (§10.1).
- **Contract precision (v5)** → `visual_archetype` (known or `null`) and `visual_status` are **separate
  fields** (§10.1); **`compressed` is backend-approved**, not model-free-labeled (§5);
  per-line `support_fact_ids` **required where a real trace exists (preexisting_trace/canonical)** and
  **distinct from `included_event_ids`** (taught vs evidence) (§6.2); state may be **`null` +
  `state_relevance: "none"`** for proof/comparison/
  concept (§7); **state payload size is bounded** (paths/collection/depth/frames/entities — store
  refs/ranges, not copies) (§7); **first-pass validation failure** has an explicit recovery path
  (deterministic repair → one targeted repair call → safe degrade / visible fail; never silently ship
  invalid) (§9.2); canonical-audit exception stated in the North Star + §1.
