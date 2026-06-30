# Implementation Checkpoints & Explicit Checks

> Companion to `ADAPTER_AND_GENERATION_SYSTEM_SPEC.md`. Every checkpoint must be independently testable.
> **Do not continue to the next checkpoint until the current one passes.** Do not scale to more adapters
> until all pass.
>
> **Status legend:** ✅ done & tested · 🟡 partial · ❌ not started.

## Status at a glance (updated as work lands)
| CP | Title | Status | Where |
|---|---|---|---|
| 0 | Baseline safety / observability | ✅ | M7 `generation_report`, full suite (18 pre-existing fails, steady) |
| 1 | No from-scratch fallback for supported topics | ✅ | P0a `545ae26` + single-path `40a34df` + invariant lock `8bd40c7` |
| 2 | Trace-preserving fallback narration | ✅ | P0a `_deterministic_narration` `545ae26` |
| 3 | Relax `count_mismatch` safely (coverage-based) | 🟡 | P0b `04f93ff` cuts the rate + P0a never-withholds; **coverage-based ACCEPT of a different count not yet built** |
| 4 | Prose hard/soft boundary | 🟡 | `hard_prose_violations` + A3 soft `value_not_allowed`; not yet a declared `TeachingValidationContract` |
| 5 | Regression fixtures (golden lessons) | ✅ | `test_golden_fixtures.py` — deterministic-narration golden net over all 8 adapters (CP5 historical bug classes) |
| 6 | Generation-report invariants | ✅ | `invariant_violations` (§1.2 + `verification_level`) + `_coverage_fields` (`trace_ids_rendered`/`required_transition_ids`/`missing_required_transition_ids`/`terminal_rendered`); tests in `test_generation_report.py`. *(structured `prose_validation` object still flat)* |
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
- Add a hard invariant: `if adapter_slug is not None: final_source not in {"gen_foundation", "legacy", "legacy_*"}`.
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
`test_supported_topic_withholds_instead_of_fabricating`. **TODO (CP6):** add the machine-checked report assertion
`adapter_slug != None ⇒ final_source ∉ {gen_foundation, legacy_*}` as a standing invariant test.

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

## Checkpoint 3 — Relax `count_mismatch` Safely

### Rule
A card count different from trace-step count is acceptable only when coverage is complete.

### Accept only if ALL are true
every required transition ID rendered · terminal/completion rendered · no surfaced learner decision omitted ·
no forbidden stage combination · final answer preserved · no hard prose contradiction.

### Reject if ANY are true
required transition missing · terminal/completion missing · two independent learner decisions merged without an
adapter-approved rule · card references nonexistent trace IDs · card result contradicts trace state.

### Tests
1. Count mismatch but complete coverage → pass.
2. Count mismatch missing completion → fail.
3. Count mismatch missing cycle-skip transition → fail.
4. Count mismatch with prose contradiction → fail.
5. Exact count with wrong state → fail.

**Pass condition:** count alone never withholds, but coverage/semantics still control correctness.
**Status (this session):** 🟡 — "count alone never withholds" is satisfied (P0a ships a trace-preserving narration
instead of withholding), and P0b states the exact count in the prompt to cut the mismatch rate (`04f93ff`).
**NOT yet built:** the **coverage-based ACCEPT** of the LLM's *grouped* cards (a different count that still covers
every required transition + terminal). That needs a `coverage_complete(cards, trace)` predicate + relaxing
`_normalize_and_attach`'s strict 1:1 (`len(cards)==len(steps)`). The 5 tests above are the gate for that work.

---

## Checkpoint 4 — Prose Hard/Soft Boundary

### Hard failures (block shipping)
contradiction of trace state · wrong selected edge/node/value · wrong final answer · wrong decision outcome ·
missing required fact · invented transition not in trace.

### Soft failures (must not block alone)
bland wording · slightly repetitive · value mentioned in a harmless context · non-ideal style · could be clearer.

### Tests
- "Kruskal accepts edge AB" when trace rejects AB → fail.
- "Stack contains C,B" when trace says B,C → fail.
- Bland but correct reasoning → pass with warning.
- Missing terminal statement → fail if terminal transition required.

**Pass condition:** validators block wrong content, not merely imperfect phrasing.
**Status (this session):** 🟡 — `hard_prose_violations` already splits hard (blocks) from advisory; A3 keeps
`value_not_allowed` SOFT for code-anchored cards (spec §4.3.3). **TODO:** make the hard set a *declared*
`TeachingValidationContract` (spec §2.7/§4.0) and add the four boundary tests above; ensure "missing terminal"
is a hard failure when the adapter marks a terminal transition required (ties to CP3 completion + C4).

---

## Checkpoint 5 — Required Regression Fixtures
Create permanent golden fixtures covering every historical bug class:
- **Prim:** no one-step "initialize graph" example · must include completion · no legacy/gf fallback if adapter exists.
- **Kruskal:** must show sorted edge order · ≥1 accept and ≥1 cycle skip when required · never mis-sorted / invalid MST.
- **DFS/BFS:** declare traversal convention · preserve queue/stack order · never render traversal as BST/tree unless the graph is a tree.
- **Merge sort:** never 80 learner-facing cards · include split / base case / merge selection / tail copy / completion when required · no opaque multi-comparison merge unless the adapter allows it.
- **Coding implementation:** code walkthrough and worked example must not duplicate each other · Result fields must not render raw dicts · repeated identical reasoning cards fail teaching validation.

**Pass condition:** all historical bug classes are covered by tests.
**Status (this session):** ❌ — M6 content-shape *linter* exists (catches raw-dict Result, repeated titles, step-card
explosion), but the **golden-lesson fixture set** is not built (carried from `STUDY_PATH_CONTENT_SPEC` §H / spec §5.4).

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
### Required checks
- Adapter-supported + `final_source=gen_foundation` → hard violation.
- Adapter-supported + `verification_level != trace_verified` unless withheld → hard violation.
- Missing terminal on a computational example → fail.
- Missing required transition → fail.

**Pass condition:** reports make every routing/fallback decision auditable.
**Status (this session):** 🟡 — M7 records `adapter`, `final_source`, `tp_reason`, `narration`,
`narration_failed_reason`, `code_validation`, `we_card_count`. **TODO:** add `verification_level`,
`trace_ids_rendered`, `required_transition_ids`, `missing_required_transition_ids`, `terminal_rendered`, and the
structured `prose_validation`; then add the four hard-violation assertions as standing tests.

---

## Checkpoint 7 — Manual Product QA
After tests pass, manually generate: Prim MST walkthrough · Kruskal MST walkthrough · DFS traversal · BFS
traversal · merge sort coding · binary search coding. For each verify: example is correct · steps reconstructable ·
visuals match state · no raw backend state leaks · no fallback-produced wrong example · completion/final answer
explicit · content feels useful, not just technically valid.

**Pass condition:** user-facing experience is correct and understandable.
**Status (this session):** ❌ — pending a regenerate after pushing the branch.

---

## Final Definition of Done
Done only when: adapter-supported topics cannot fall back to from-scratch generation · trace-preserving fallback
exists · `count_mismatch` is coverage-based (not count-only) · hard vs soft prose failures are separated ·
regression fixtures cover known failures · generation reports expose final source + verification level · manual QA
passes for core algorithm topics. **Do not scale to more adapters until these pass.**

This matches the main spec invariant (§1.2): *adapter-supported topics must use the adapter trace as the only
executable truth, never a from-scratch fallback.*
