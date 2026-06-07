# Visual Compilers (v2)

One compiler per base_type. Each compiler turns a `VisualIntent` (and optionally a `WorkedExamplePlan`) into a `VisualModel` the frontend renders.

The orchestrator is at [../lean_lesson_generator_v2.py](../lean_lesson_generator_v2.py); the contract types are at [../../schemas/visual_v2.py](../../schemas/visual_v2.py); the prompt that drives the LLM is at [../../prompts/lean_lesson_prompt_v2.py](../../prompts/lean_lesson_prompt_v2.py).

## Files

| File | Compiler | Status |
|------|----------|--------|
| `node_link.py` | NodeLinkCompiler — trees, graphs, linked lists, state machines, circuits | full |
| `indexed_sequence.py` | IndexedSequenceCompiler — arrays, strings, pointers, sliding window | full |
| `code_execution.py` | CodeExecutionCompiler — growing + execution modes | full |
| `grid_matrix.py` | GridMatrixCompiler — matrices, DP tables, adjacency, K-maps | full |
| `formula.py` | FormulaCompiler — symbolic expressions, substitutions, derivations | full |
| `table.py` | TableCompiler — comparison, truth, variable trace, routing | full |
| `coordinate_graph.py` | CoordinateGraphCompiler — function curves, distributions, ROC, loss | full |
| `memory_layout.py` | MemoryLayoutCompiler — stack/heap, pointer reference, allocation | full |
| `geometric.py` | GeometricCompiler — points, segments, regions, measurements | full |
| `timeline_sequence.py` | TimelineSequenceCompiler — protocol, race condition, OAuth | full |
| `set_region.py` | SetRegionCompiler — Venn diagrams, probability regions | full |
| `image_illustration.py` | ImageIllustrationCompiler — analogy + real-world illustrations | full |

Registry + dispatch lives in `__init__.py`. Abstract base + the `StubCompiler` fallback live in `base.py`.

## Compiler contract

Every compiler subclasses `VisualCompiler` and overrides four methods:

```python
class MyCompiler(VisualCompiler):
    base_type = "my_diagram"

    def compile(intent, plan, context) -> VisualModel:
        """Produce a VisualModel. For static visuals: one frame. For
        worked examples: N frames keyed to plan.steps."""

    def selectable_elements(frame_state, base, mode) -> list[SelectableElement]:
        """Per-frame click targets for click-to-ask."""

    def transitions(prev_state, curr_state, base, mode, hints) -> list[Transition]:
        """Per-frame animation specs derived by diffing prev → curr."""

    def synthesize_plan_from_legacy_cards(legacy_cards, context) -> WorkedExamplePlan | None:
        """LLM-compliance fallback: when the LLM nulled the plan,
        reconstruct one from legacy lean cards (visual_nodes, visual_edges,
        visual_array_values, code_snippet, etc.)."""
```

The base class provides default no-op implementations for `selectable_elements`, `transitions`, and `synthesize_plan_from_legacy_cards`. Compilers that don't override these get a passive, non-animated visual.

## Adding a new compiler

1. **Pick a base_type and add it to** `app/core/visual_ontology_v2.py`:
   - Append to `BASE_VISUAL_TYPES`
   - Add a `MODES_BY_BASE_TYPE[base_type]` entry
   - Add a `DOMAIN_TO_BASE_TYPE[domain]` mapping
   - Add a `DOMAIN_TO_DEFAULT_MODE[domain]` mapping

2. **Add the base_state schema** to `lean_lesson_prompt_v2.py` so the LLM knows how to fill the plan.

3. **Write the compiler** in this directory. Mirror an existing one (`node_link.py` is the largest, `image_illustration.py` is the smallest). At minimum:
   - `_build_base()` — normalize and validate the base_state from `plan.get("base_state")`, with cross-card reuse from `context["already_compiled_models"]`
   - `_compile_static()` — single-frame model for background / edge case cards
   - `_compile_dynamic()` — N-frame model for worked examples
   - `selectable_elements()` — per-frame clickable list with stable element_ids
   - `transitions()` — per-frame diff producing animation specs

4. **Register the compiler** by calling `register(MyCompiler())` at the module bottom. The bootstrap in `__init__.py` imports your module automatically once it exists.

5. **Add a frontend renderer** in `frontend/components/visuals_v2/` and dispatch to it from `VisualRenderer.tsx`.

6. **Add a fixture to `v2_e2e_smoke._SYNTHETIC_BASE_STATES`** so the smoke run covers your compiler.

7. **Add a case to `test_visual_compilers_v2.COMPILER_CASES`** so the contract tests cover it.

## Element-id stability invariant

The same conceptual element (a tree node, an array cell, a code line, a pointer named `l`) MUST keep the same `element_id` across every frame of a VisualModel. This is what makes transitions animate instead of teleport, and what makes the chat sidebar's visual_context payload point to the right thing.

The `SnapshotInvariantsTests.test_element_id_stability_across_frames` test enforces this. If you change a compiler and the test fails, your compiler is dropping or renaming elements mid-trace.

Pointer-type elements (the `l`, `r`, `m` of binary search) ARE allowed to move (their bounds change frame-to-frame); they're handled by emitting a `move` transition. Non-pointer types (`node`, `cell`, `code_line`, `symbol_definition`) must keep static bounds and only change `state`/`style` overlays.

## Cross-card model reuse

When a card has no plan (or has a partial plan), the compiler can pull the base structure from a previously-compiled model on the same lesson via `context["already_compiled_models"]`. This is how a worked-example card stays consistent with the background card's tree / array / code / table.

All 12 compilers honor this pattern. The `CrossCardReuseTests` in the snapshot tests verify it.

## Synthesizer fallback

When the LLM emits per-step `worked_example` cards but nulls the top-level `worked_example_plan`, the compiler can reconstruct an equivalent plan from those cards. Implemented in `node_link`, `indexed_sequence`, `code_execution`, `grid_matrix`. The other 8 compilers inherit the default no-op (return None).

The contract: read legacy `visual_*` fields from the background card to recover `base_state`; parse worked-example card text + visual fields to recover `state_after` per step. The reconstructed plan is then passed through the regular `compile()` path.

## Telemetry + validation

- `validate_lesson_v2()` runs after every compile. Errors degrade the offending render_step to text-only; warnings + info pass through.
- `record_generation()` (in `../v2_telemetry.py`) writes one CSV row per generation to `backend/venv/logs/v2_telemetry.csv` so v2 vs legacy can be compared without an external metrics stack.
