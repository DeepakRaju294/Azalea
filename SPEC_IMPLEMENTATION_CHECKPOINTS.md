# Implementation Checkpoints & Explicit Checks

> Companion to `ADAPTER_AND_GENERATION_SYSTEM_SPEC.md`. Every checkpoint must be independently testable.
> **Do not enable a checkpoint's dependent production behavior, mark the rollout complete, or scale adapter
> coverage until all preceding BLOCKING checkpoints pass.** Independent safety, observability, and regression
> work may proceed in parallel — but must not be treated as proof that an earlier blocking checkpoint is done.
>
> **Current rollout blocker: CP3 — grouped checkpoint/artifact acceptance wiring.** CP3a (default checkpoint
> emission) has LANDED: `_attach_checkpoints` puts a `checkpoint_id` + contiguous source-transition provenance on
> every card in both ship paths, tested across all 8 adapters. CP1/CP2/CP4/CP5/CP6 already reduce risk; the
> remaining P0-tier work is accepting GROUPED LLM artifacts under the checkpoint contract (relax the strict 1:1
> in `_normalize_and_attach` behind the checkpoint-aware `coverage_complete`).
>
> **Status legend:** ✅ done & tested · 🟡 partial · ❌ not started.

## Status at a glance (updated as work lands)
| CP | Title | Status | Where |
|---|---|---|---|
| 0 | Baseline safety / observability | ✅ | M7 `generation_report`, full suite (18 pre-existing fails, steady) |
| 1 | No from-scratch fallback for supported topics | ✅ | P0a `545ae26` + single-path `40a34df` + invariant lock `8bd40c7` |
| 2 | Trace-preserving fallback narration | ✅ | P0a `_deterministic_narration` `545ae26` |
| 3a | Default checkpoint emission (per-transition, with provenance) | ✅ | `_attach_checkpoints` puts a `checkpoint_id` + `source_transition_start/end` on every card (both ship paths) + CP6b report fields; `test_cp3a_checkpoints.py` runs the 6-step contract × all 8 adapters |
| 3 | Checkpoint/artifact alignment (was: relax `count_mismatch`) | 🟡 | never-withhold (P0a) + **`coverage_complete` now CHECKPOINT-AWARE (`checkpoints=` param) — 9 boundary tests pass** (`test_coverage_complete.py`: artifact-without-checkpoint / unknown-checkpoint / missing-required-checkpoint); the grouped-count ACCEPT wiring in `_normalize_and_attach` is still deferred (needs the formatter to EMIT grouped cards with `checkpoint_id`s — a prompt change held back to protect 1:1 reliability) |
| 4 | Prose hard/soft boundary | ✅ | declared `TeachingValidationContract` (`DEFAULT_TEACHING_VALIDATION`) + `hard_prose_violations(contract=)`; four boundary tests in `test_teaching_validation_contract.py` |
| 5 | Regression fixtures (golden lessons) | ✅ | `test_golden_fixtures.py` — deterministic-narration golden net over all 8 adapters (CP5 historical bug classes) |
| 5b | Normal-narration golden coverage (Prim/Kruskal) | 🟡 | deferred — fixtures cover the deterministic FALLBACK path; the normal prose-fill path is not yet asserted |
| 6 | Generation-report invariants | ✅ | `invariant_violations` (§1.2 + `verification_level`) + `_coverage_fields` (`trace_ids_rendered`/`required_transition_ids`/`missing_required_transition_ids`/`terminal_rendered`); tests in `test_generation_report.py` |
| 6b | Checkpoint provenance + structured `prose_validation` in the report | 🟡 | checkpoint fields NOW recorded (`checkpoint_ids_rendered`/`required_checkpoint_ids`/`missing_required_checkpoint_ids`) + a `missing_required_checkpoint_ids` invariant (`test_generation_report.py`); the nested `prose_validation{hard_failures,soft_warnings}` object is still flat |
| 7 | Manual product QA | 🟡 | live audits clean on binary-search + graph BFS/DFS (keystone, de-hardcoding, continuity all confirmed); full 6-topic matrix not yet swept |

---

## Checkpoint 0 — Baseline Safety

### Required checks
- Existing tests pass before changes.
- Feature flags are documented.
- Current fallback sources are observable in generation reports.
- Adapter-supported topics can be identified deterministically.

### Tests
- Run existing backend test suite.
- Generate one known adapter-supported topic and confirm report includes: selected adapter slug · final source ·
  verification level · fallback/withhold reason if any.

**Pass condition:** no behavior change yet, only observability confirmed.
**Status (this session):** ✅ — M7 report records `adapter`, `final_source`, `tp_reason`/withhold reason; flags
documented in spec §4.4; `route_adapter(topic)` deterministically identifies supported topics; full suite steady.

---

## Checkpoint 1 — No From-Scratch Fallback for Adapter-Supported Topics

### Rule
If a topic routes to an adapter, final worked-example cards must descend from the adapter trace. They may not
come from `gen_foundation`, `legacy`, or any from-scratch LLM derivation.

### Required implementation checks
- Add a hard invariant: for an adapter-supported topic, `not is_from_scratch_source(final_source)` — an
  OPERATIONAL predicate (the enumerated set + any `legacy`/`legacy_*` variant), not a literal set, so a future
  `legacy_*` variant can't slip through. Deliberately NOT a blanket `gen_*` prefix (that would misclassify a
  legitimate future adapter-backed source like `gen_trace_pipeline`); `gen_foundation` is enumerated explicitly
  (`generation_report.is_from_scratch_source`; tested on `legacy_v2`/`legacy_fallback` + a `gen_*` non-violation).
- If narration fails, the system must (1) retry prose-fill, (2) use trace-preserving fallback narration, or
  (3) withhold. It must never re-derive the example.

### Tests
- Adapter-supported Prim/Kruskal/BFS topic with forced formatter failure.
- Expected: no `gen_foundation` output · no legacy output · either trace-preserving fallback or withheld ·
  generation report marks adapter source.

**Pass condition:** supported topics cannot escape the adapter trace path.
**Status (this session):** ✅ — P0a ships a trace-preserving narration on narration failure (`545ae26`);
single-path enforcement withholds (lean base) instead of gen_foundation/legacy when no trace exists (`40a34df`).
Tests: `test_narration_failure_ships_trace_preserving_narration_not_none`,
`test_supported_topic_withholds_instead_of_fabricating`. ✅ **Done (CP6, `8bd40c7`):** the standing invariant `adapter_slug != None ⇒ not is_from_scratch_source(final_source)`
(+ `verification_level == trace_verified` unless withheld) is asserted in `test_generation_report.py`.

---

## Checkpoint 2 — Trace-Preserving Fallback Narration

### Rule
When prose-fill fails but the adapter trace is valid, fallback should simplify wording over the same trace,
not discard the trace.

### Required checks — fallback narration must preserve
- same transition IDs · same ordering · same prior/result states · same final answer · same required transition
  coverage · same terminal/completion step.

### Tests
- Force prose validator to fail on one card.
- Expected fallback: card count may differ only if coverage remains complete · every rendered card references
  adapter trace IDs · no generated state differs from trace state.

**Pass condition:** fallback changes wording only, never semantics.
**Status (this session):** ✅ — `_deterministic_narration` builds each card from the step's own
`trace_step_ids`/`prior_state`/`state_after`/`expected_visible_result` (semantic preservation by construction),
1:1 with steps, final answer from the trace. Test asserts cards descend from trace IDs and the bad LLM prose is
absent. *(Today it's 1:1 with steps; the "count may differ if coverage complete" relaxation is CP3.)*

---

## Checkpoint 3 — Checkpoint / Artifact Alignment (was: relax `count_mismatch`)

### CP3a — Default checkpoint emission (PREREQUISITE, must land first)
Grouped-artifact acceptance cannot begin until every current adapter emits a default `TeachingCheckpoint[]`:
one checkpoint per `TeachingTrace` transition, each carrying `checkpoint_id`,
`source_transition_start`/`source_transition_end`, state-before/after anchors, required-case coverage, and the
terminal marker. **Pass condition:** every adapter-backed payload can attach a `checkpoint_id` to every
learner-facing artifact — even before GROUPED checkpoints exist. (`base.teaching_checkpoints` already builds the
identity-projection form; CP3a is wiring it into the runtime payload + report.) Only then does CP3 progress from
*one transition → one checkpoint → one+ artifacts* to grouped checkpoints.

**CP3a status: ✅** — `_attach_checkpoints` (`trace_pipeline`) wires the identity projection onto every card in
BOTH ship paths (LLM + deterministic narration); `test_cp3a_checkpoints.py` runs the 6-step contract across all
8 adapters; the CP6b checkpoint report fields + a `missing_required_checkpoint_ids` invariant are locked in
`test_generation_report.py`.

**CP3a tests — for each currently supported adapter:**
1. build the default `TeachingCheckpoint[]` identity projection;
2. run deterministic narration;
3. assert every emitted artifact has exactly one `checkpoint_id`;
4. assert that checkpoint exists in `AdapterOutput.teaching_checkpoints`;
5. assert `source_transition_start`/`end` resolve to valid contiguous `TeachingTrace` transitions;
6. assert the terminal checkpoint mapping when the adapter has a terminal transition.

**CP3a provenance semantics.** `source_transition_start`/`source_transition_end` are **stable `TeachingTrace`
transition IDs** (inclusive, in TeachingTrace order) — NOT array indexes (indexes break if the trace is filtered
or re-represented). A range is **contiguous** only when it covers every transition between those two IDs in the
emitted TeachingTrace order; the CP3a test validates both IDs ∈ `teaching_trace.transition_ids` and that the
range is ordered + contiguous.

**Required-checkpoint derivation (stated once).** For the default identity projection, every REQUIRED transition
maps to exactly one required checkpoint with the same single-transition source range. For grouped projections, a
checkpoint is REQUIRED whenever its source range contains ≥1 required transition — a required transition may
never be covered only by an optional/support checkpoint (which would hide a must-show transition).

### Rule
Learner-facing artifact COUNT is not itself a correctness gate. An artifact is accepted only when it cites
exactly one adapter-produced `checkpoint_id`, and the complete artifact set preserves all required checkpoints,
terminal coverage, decision visibility, state provenance, and final-answer correctness. (Card count vs
trace-step count is no longer the reference — checkpoints are.)

### Accept only if ALL are true
every required CHECKPOINT is represented by ≥1 learner-facing artifact · the terminal checkpoint is represented ·
every artifact cites exactly one EXISTING `checkpoint_id` · every cited checkpoint has valid contiguous
source-transition provenance · no surfaced learner decision omitted · no forbidden checkpoint/stage combination ·
final-answer + state anchors stay consistent with the TeachingTrace · no hard narration contradiction.

### Reject if ANY are true
a required checkpoint has no artifact · terminal checkpoint missing · two independent learner decisions merged
without an adapter-approved rule · an artifact cites a nonexistent `checkpoint_id` · a checkpoint's source-transition
range is non-contiguous · an artifact's result contradicts the TeachingTrace state.

> **Transition IDs remain the underlying proof.** Checkpoint coverage is validated THROUGH each checkpoint's
> source-transition range — transition-level checks are the semantic proof; `checkpoint_id`s are the
> learner-facing + reporting proof. The existing `coverage_complete(cards, trace, adapter)` machinery stays.

**`coverage_complete` is now checkpoint-aware (✅ landed, backward-compatible):**
```
coverage_complete(cards, trace, adapter=None, *, checkpoints=None)
```
With `checkpoints=` supplied it verifies **exactly one existing `checkpoint_id` per artifact · required-checkpoint
coverage · terminal-checkpoint coverage**, on top of the transition-level required/terminal/unknown-id/hard-prose
checks (transition coverage stays the underlying semantic proof — no new abstraction, same predicate). Existing
callers pass no `checkpoints` and are unchanged; 9 boundary tests in `test_coverage_complete.py`. **Remaining CP3
work is the runtime WIRING:** relax `_normalize_and_attach`'s strict 1:1 to ACCEPT a grouped card set via this
predicate — held until the formatter emits grouped cards carrying `checkpoint_id`s (protects 1:1 reliability).

### Tests
1. Artifact-count mismatch with complete required-checkpoint coverage → pass.
2. Terminal checkpoint has no artifact → fail.
3. Required cycle-skip checkpoint has no artifact → fail.
4. Artifact cites a valid checkpoint but has a hard narration contradiction → fail.
5. Exact artifact count but a checkpoint state-anchor contradiction → fail.

**Pass condition:** count alone never withholds, but coverage/semantics still control correctness.
**Status (this session):** 🟡 — "count alone never withholds" is satisfied (P0a ships a trace-preserving narration
instead of withholding), and P0b states the exact count in the prompt to cut the mismatch rate (`04f93ff`).
**NOT yet built:** the **coverage-based ACCEPT** of the LLM's *grouped* cards. Per the frozen model this is
**checkpoint** alignment, not a loose trace-id list: each learner-facing artifact must cite exactly one
`checkpoint_id` exposing a contiguous `source_transition_start..source_transition_end` range + state-before/after
anchors + required-case/terminal coverage — and the formatter may NOT create or merge checkpoints.
`coverage_complete(...)` + relaxing `_normalize_and_attach`'s strict 1:1 (`len(cards)==len(steps)`) are the
remaining wiring; the 5 tests above are the gate for that work.

---

## Checkpoint 4 — Prose Hard/Soft Boundary

### Hard TRUTH failures (withhold — never ship wrong truth)
invalid replay · wrong state · illegal transition · wrong final answer · failed independent oracle.

### Hard NARRATION failures (retry → deterministic checkpoint narration; do NOT withhold a correct trace)
contradiction of checkpoint state · wrong selected edge/node/value · wrong decision outcome · missing required
fact · invented transition not in trace.

### Soft failures (must not block alone)
bland wording · slightly repetitive · value mentioned in a harmless context · non-ideal style · could be clearer.

### Tests
- "Kruskal accepts edge AB" when trace rejects AB → fail.
- "Stack contains C,B" when trace says B,C → fail.
- Bland but correct reasoning → pass with warning.
- Missing terminal statement → fail if terminal transition required.

**Pass condition:** validators block wrong content, not merely imperfect phrasing.
**Status:** ✅ — the hard set is a *declared* `TeachingValidationContract` (`DEFAULT_TEACHING_VALIDATION`) and
`hard_prose_violations(contract=)` splits hard (blocks) from advisory; A3 keeps `value_not_allowed` SOFT for
code-anchored cards (spec §4.3.3). The four boundary tests pass in `test_teaching_validation_contract.py`. A hard
NARRATION failure triggers retry → deterministic checkpoint narration (§4.3.1), NOT a withhold — only a Truth
failure withholds a supported topic.

---

## Checkpoint 5 — Required Regression Fixtures
Create permanent golden fixtures covering every historical bug class:
- **Prim:** no one-step "initialize graph" example · must include completion · no legacy/gf fallback if adapter exists.
- **Kruskal:** must show sorted edge order · ≥1 accept and ≥1 cycle skip when required · never mis-sorted / invalid MST.
- **DFS/BFS:** declare traversal convention · preserve queue/stack order · never render traversal as BST/tree unless the graph is a tree.
- **Merge sort:** never 80 learner-facing cards · include split / base case / merge selection / tail copy / completion when required · no opaque multi-comparison merge unless the adapter allows it.
- **Coding implementation:** code walkthrough and worked example must not duplicate each other · Result fields must not render raw dicts · repeated identical reasoning cards fail teaching validation.

**Pass condition:** all historical bug classes are covered by tests.
**Status:** ✅ — `test_golden_fixtures.py` runs a deterministic-narration golden net over all 8 adapters covering
the CP5 historical bug classes (raw-dict Result, repeated titles, step-card explosion, missing completion,
mis-sorted/invalid MST, traversal-rendered-as-tree). **CP5b (🟡 deferred):** also assert the NORMAL prose-fill mode (not only the deterministic fallback) preserves
checkpoint provenance + required transitions + terminal for at least Prim/Kruskal, so a "safe in theory, broken
in practice" narration regression is caught — the two golden modes are (1) normal prose-fill, (2) forced prose
failure → deterministic checkpoint narration.

---

## Checkpoint 6 — Generation Report Invariants
Every generated worked example must record:
```json
{
  "adapter_slug": "... or null",
  "verification_level": "trace_verified | answer_anchored | model_only | guided_fallback",
  "final_source": "...",
  "trace_ids_rendered": ["..."],
  "required_transition_ids": ["..."],
  "missing_required_transition_ids": [],
  "terminal_rendered": true,
  "fallback_reason": "... or null",
  "prose_validation": { "hard_failures": [], "soft_warnings": [] }
}
```
> **Schema split (resolves the ✅/flat contradiction).** The flat fields — `adapter_slug`, `verification_level`,
> `final_source`, `trace_ids_rendered`, `required_transition_ids`, `missing_required_transition_ids`,
> `terminal_rendered`, `fallback_reason` — are **CP6, required NOW (✅)**. The nested
> `prose_validation{hard_failures,soft_warnings}` + the checkpoint fields (`checkpoint_ids_rendered`,
> `required_checkpoint_ids`, `missing_required_checkpoint_ids`) are **CP6b, required WITH checkpoint wiring (🟡)**.
> So CP6 is honestly ✅ and CP6b owns the remaining report-shape work.

### Required checks
- Adapter-supported + `final_source=gen_foundation` → hard violation.
- Adapter-supported + `verification_level != trace_verified` unless withheld → hard violation.
- Missing terminal on a computational example → fail.
- Missing required transition → fail.

**Pass condition:** reports make every routing/fallback decision auditable.
**Status:** ✅ (one caveat) — `invariant_violations` enforces §1.2 + `verification_level`, and `_coverage_fields`
adds `trace_ids_rendered` / `required_transition_ids` / `missing_required_transition_ids` / `terminal_rendered`;
the four hard-violation assertions are standing tests in `test_generation_report.py` (incl. the CP1 shared
invariant, `8bd40c7`). **CP6b (🟡, lands with CP3):** `prose_validation` is still flat (not the nested `{hard_failures, soft_warnings}`
object above), and the report keys are transition-based. Once checkpoint wiring lands, ADD the checkpoint
provenance fields — `checkpoint_ids_rendered`, `required_checkpoint_ids`, `missing_required_checkpoint_ids` —
and promote them to the principal audit unit; keep `trace_ids_rendered` for semantic provenance.

---

## Checkpoint 7 — Manual Product QA
After tests pass, manually generate: Prim MST walkthrough · Kruskal MST walkthrough · DFS traversal · BFS
traversal · merge sort coding · binary search coding.

**Per-topic exit checklist (all must hold):**
adapter selected · `trace_verified` · no from-scratch `final_source` · required checkpoints visible · terminal
visible · final answer correct · visual artifact matches checkpoint state · no raw state object leaks · content
feels useful (not merely technically valid) · **fallback mode exercised for at least Prim and Kruskal**.

**Pass condition:** user-facing experience is correct and understandable.
**Status:** 🟡 — live audits clean on binary-search + graph BFS/DFS (keystone, de-hardcoding, continuity
confirmed); the full 6-topic matrix above is not yet swept.

---

## Final Definition of Done
Done only when: adapter-supported topics cannot fall back to from-scratch generation · trace-preserving fallback
exists · `count_mismatch` is coverage-based (not count-only) · hard vs soft prose failures are separated ·
regression fixtures cover known failures · generation reports expose final source + verification level · manual QA
passes for core algorithm topics. **Do not scale to more adapters until these pass.**

This matches the main spec invariant (§1.2): *adapter-supported topics must use the adapter trace as the only
executable truth, never a from-scratch fallback.*

