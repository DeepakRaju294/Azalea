# visual_v2 — spec-driven visual pipeline

Implements VISUAL_SYSTEM_SPEC.md (project root). **Additive**: nothing here is
wired into lesson generation yet. The deterministic core has no LLM/API deps and
is unit-tested in isolation.

## Flow
`CanonicalExample → (ExampleInvariantValidator) → Trace (simulator) →
DeltaFoldEngine → FrameState[] → NodeLinkCompiler → VisualModel + RenderStep[] →
validators`. Authority flows downhill (§6.2/§6.3): the simulator owns the trace,
the compiler styles but never re-decides it.

## Modules
- `schemas.py` — CanonicalExample, Trace, TraceStep, FrameState, VisualModel, RenderStep
- `profiles.py` — per-mode profile (layout, labels, states, panels, delta vocab, richness floors)
- `example_invariants.py` — validate the example BEFORE tracing (§6.0)
- `simulators/` — `graph.py` (BFS/DFS) + `registry.py`; registered algorithms own their trace
- `delta_fold.py` — DeltaFoldEngine: initial_state + deltas → frame states + diff
- `compilers/node_link.py` — FrameState[] → renderer-consumable VisualModel
- `validators.py` — trace / model / pedagogical validators (repair→warn→reject)
- `pipeline.py` — `run_for_registered(example)` orchestrator
- `telemetry.py` — visual_status + reproducible debug payload

## Status (per §8.1 graph-traversal pilot)
- [x] Slice 1 — schemas, graph profile/vocab, invariants, BFS/DFS sims, DeltaFoldEngine
- [x] Slice 2 — NodeLinkCompiler from folded states
- [x] Slice 3 — trace/model/pedagogical validators + orchestrator + telemetry
- [x] §11 BFS appendix as golden diff-snapshot test
- [x] Slice 4 — LLM "boring" example call + prose-from-trace + sync validator + fallback (LLM injected; stub-tested)
- [x] Slice 5a — feature flag + `integration.maybe_build_v2_visual` (flag-gated seam)
- [x] Slice 5b — `lesson_integration.apply_v2_to_lesson`: trace → WorkedExamplePlan →
      the existing `NodeLinkCompiler` → swap worked-example cards; wired into
      `lessons.enrich_legacy_lesson_with_v2_visuals` (guarded, failure-safe)
- [x] Binary search — second mode (`binary_search_range`): profile, simulator,
      invariants (array must be sorted), §11.2 golden. The SAME `DeltaFoldEngine`
      renders a different vocabulary (the generalisation proof). Core only — not
      yet wired into the lesson build (needs the `indexed_sequence` compiler seam).
- [x] Slice 6 — telemetry (`metrics.py`: coverage / rejection / repair + failure-by-stage)
      recorded by the build path, plus `widening_gates()` for the §8.1 go/no-go
- [x] **code_execution mode** (core) — `simulators/code_tracer.py` real `sys.settrace`
      tracer + `simulators/sandbox.py` subprocess+timeout + fold ops + CodeExampleValidator
      + `compilers/code_execution.py` + golden. The permanent replacement for the legacy
      coding heuristics. (not yet wired into the lesson build / not yet flag-flipped live)
- [x] **static-visual path** (`static_visual.py`, §5.0) — define_structure/compare_cases =
      base + one at-rest frame, no simulator. The cheap breadth unlock.
- [x] **indexed_sequence compiler** (`compilers/indexed_sequence.py`) — 2nd renderer family;
      renders binary-search/array states (in_range/mid/discarded/found/pointer).

### Open (next)
- [ ] live wiring per mode (code_execution, binary search) into the lesson build + flag-flip
      verification in a running env  ← the one thing not verifiable from unit tests
- [ ] remaining renderer compilers: grid_matrix, formula, table, coordinate, memory_layout,
      timeline, set_region, geometric, image (9 of 12)
- [ ] remaining simulators: two-pointer, sliding window, sort passes, DP fill, stack/queue,
      linked-list, Dijkstra
- [ ] Phase 5 mechanics (repair ladder, accessibility, motion/layout budgets, card_role)
- [ ] Phase 6 frontend contract · Phase 7 legacy-bridge retirement (gated by telemetry)

**Coverage so far:** 3 of 12 renderer compilers (node_link, code_execution, indexed_sequence);
4 simulators (bfs, dfs, binary_search, code_execution); static path. Only graph BFS/DFS is
wired live (flag-gated). **151 tests, deterministic, no network.** Everything is isolated from
the running app: the flag is default-off, LLM imports are lazy, and the lesson hook only fires
when enabled (failures are caught and never break the legacy lesson).

## Registered so far
- Modes: `graph_network` (wired to lesson build), `binary_search_range` (core only),
  `code_execution` (core: real `sys.settrace` tracer — runs the code, records the
  truth; tracer + fold ops + validator + compiler + golden, not yet wired/sandboxed)
- Algorithms: `bfs`, `dfs`, `binary_search`, `code_execution`

## code_execution mode (Phase 1)
`simulators/code_tracer.py` executes the generated code ONCE under `sys.settrace`
and records `(line, variables, call_stack, output)` per executed line — the visual
is derived from that recording, never guessed. Trusted in-process path is built +
tested; untrusted production code must run via the subprocess+timeout sandbox
(Phase 1.5, reuses `code_runner`). This is the permanent replacement for the
legacy coding heuristics.

## Run tests
```
cd backend
PYTHONPATH=. python -m unittest \
  app.tests.test_visual_v2_slice1 app.tests.test_visual_v2_slice2 \
  app.tests.test_visual_v2_slice3 app.tests.test_visual_v2_slice4 \
  app.tests.test_visual_v2_slice5 app.tests.test_visual_v2_slice5b \
  app.tests.test_visual_v2_slice6
```

## How to turn it on (it's wired — just flip the flag)
1. Add to `backend/.env`: `AZALEA_VISUAL_V2_MODES=graph_network:bfs`
2. Restart the backend; **regenerate a BFS walkthrough topic** (e.g. "Breadth-First
   Search (BFS)").
3. The worked example should show the simulator-authoritative trace — correct BFS
   order, per-step node highlights, and queue/output panels — rendered by the
   existing `NodeLinkVisual`. Compare against the old path; widen to
   `graph_network:dfs` (then the next mode) once the §8.1 gates hold.

Backend-verified by 64 unit tests (deterministic core + plan→compile→apply). The
two pieces that need a *running* environment: the live LLM example/prose calls
(`llm.default_*_generator`) and the browser render — flip the flag and check.
