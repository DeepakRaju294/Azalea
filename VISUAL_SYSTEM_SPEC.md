# Azalea Visual & Content Generation — System Spec

Status: living document. Owner: visuals workstream.
Purpose: define where the visual/content pipeline is today, what we want to
change and why, and the target architecture — so fixes stop being one-off and
per-type, and instead converge on a single, declared, validated path.

---

## 1. Current state

### 1.1 How a lesson is produced today
1. **Content call (LLM #1)** — `generate_lean_structured_lesson` produces the
   whole lesson: cards with prose `points`, a loose `visual_description`, and —
   for some cards — `visual_nodes`/`visual_edges` drawn inline.
2. **Visual call (LLM #2)** — `generate_visual_patches` receives, per card,
   `{title, card_type, blueprint_key, allowed_visual_type, visual_description,
   points}` and is asked to **invent the structure** ("generate 8–10 nodes,
   pick your own values…") **and** infer per-step state from the prose.
3. **Bridge (deterministic, ~105KB)** — `legacy_v2_visual_bridge.py` then tries
   to **reverse-engineer** the intended visual: it canonicalises trees, parses
   state out of prose with regexes (`current=(\d+)`, `queue=[…]`,
   `visited={…}`), simulates traversal order, and rewrites cards.
4. **Compilers** — `visual_compilers/*` turn the cards into v2 models (frames
   with `active_node` + `runtime_state`).

### 1.2 Root problems (why this has been hard)
- **Two sources of truth that drift.** Prose and visual are authored
  separately, so they disagree ("text says 40, tree shows 5–11"). The bridge
  exists mostly to *reconcile* a divergence that should never happen.
- **Structure re-authored per card → drift.** Each step card re-emits the whole
  graph/tree, so step 2's structure ≠ step 1's. The bridge's canonicalisation is
  a band-aid for this. It is also the source of the 16k-token truncation
  (the full node list repeated on every step card).
- **State recovered from prose by regex → brittle and type-specific.** The
  digit-only `extract_current`/`extract_output` (graphs use letters) is a direct
  example: the *same concept* needed different parsing per label style.
- **Subtype is *inferred* by keyword, not declared.** `_looks_like_tree_traversal`
  / `_looks_like_bst` guess from the title. "DFS" doesn't contain "tree", so
  graphs fell out of every tree fix → fixes became "BST-only" then "graph-only".
- **A good taxonomy exists but is ignored.** `app/core/visual_ontology_v2.py`
  already defines `BASE_VISUAL_TYPES` (12 renderer families) and
  `MODES_BY_BASE_TYPE` (subtypes: `tree_hierarchy`, `graph_network`, `circuit`,
  `dp_table`, …) — but generation navigates by keyword guesses instead of this
  map. (Descriptions for every base type/mode were just added to that file.)

### 1.3 What already works / recent fixes
- Tree (BST) traversals: deterministic trace, setup card with visual + code,
  per-bullet code highlight, tree-as-Diagram, min example size, call-stack panel.
- Graph BFS/DFS: now render the full graph, highlight the active node, and show
  visited/output (the digit-only extractors were generalised to letters +
  `visited={…}`); generic worked-example setup card now inherits its visual.
- Code: nested-helper flattener, cumulative-snippet de-duplication, indentation
  rule, one-statement-per-line.
- Generation: streaming preview (early cards while later ones generate), lower
  concurrency to avoid 429s, tree worked-examples emit one seed card (the bridge
  regenerates the trace), truncation surfaced explicitly.

---

## 2. What we want to improve (principles)

1. **One source of truth.** The visual and the prose derive from the same
   authored spec, so they cannot drift.
2. **One path for all visual types.** No more BST-only / graph-only code. Per-
   type behaviour comes from a *table keyed by declared subtype*, not from
   scattered keyword checks.
3. **State is explicit, not inferred.** Highlights and annotations come from
   declared per-step state (ids + enumerated states), never from re-parsing
   sentences.
4. **Author once, render deterministically.** The LLM commits to the *example*
   once; the **state sequence is simulator-owned for registered algorithms** and
   delta-authored only for unregistered/fuzzy topics (§3.4, §5.3.1). Turning a
   state into a frame is a pure function (no LLM, no regex).
5. **Efficient by construction.** Structure is emitted once (not per card);
   per-step state is a few ids; deterministic render is free.

---

## 3. Changes to make

### 3.1 Promote the taxonomy to a declared, validated contract
- Each visual declares **`base_type` + `mode`** (from `visual_ontology_v2.py`),
  plus an orthogonal **`algorithm`/`operation`** (`inorder`, `bfs`, `dfs`,
  `dijkstra`, `binary_search`) and a few render flags (`weighted`, `directed`,
  `ordered`).
- Validate against the ontology (`is_valid_base_type` / `is_valid_mode`).
- **Delete keyword inference** (`_looks_like_*`). Everything reads the declared
  values.

### 3.2 Hang a per-mode profile off the subtype
A lookup table keyed by `mode` encodes what used to be type-specific code:

| mode | layout | labels | node states | side panels |
|---|---|---|---|---|
| `tree_hierarchy` | root-top, balanced | integers | current/visited | call stack, output |
| `graph_network` | spread | letters | current/discovered/visited | queue **or** stack, output |
| `linked_list_chain` | linear | integers | current | pointer |
| `circuit` | components + wires | refs | active/energized | — |

"letters vs digits", "which panel", "tree vs spread" become table lookups — the
digit/letter class of bug becomes impossible.

### 3.3 Unified visual spec (the information contract)
Authored once; the single source the prose, the highlights, and the panels all
derive from:

```
base (ONCE, shared):
    kind/mode, nodes:[{id,label}], edges:[{from,to,directed?}]   # logical, no x/y
steps[] (ordered script), each:
    active:[ids], visited:[ids], frontier:{kind,items}, output:[vals],
    focus:{target,note}, code_line, newly_added:[ids], newly_completed:[ids]
card_id -> step index
```
Highlights are a **computed diff** (`state_after` − `state_before`): newly-added →
gold, active → purple, traversed edge highlighted, panels = the state verbatim.

### 3.4 Re-divide the work (see the layer contracts in §6.3)
- **LLM (once):** pick the example *shape + input*; for **registered** algorithms
  it stops there (the simulator computes the state sequence, §5.3.1); for
  **unregistered/fuzzy** topics it also proposes the delta timeline. It never
  emits coordinates, colours, layout, or render JSON.
- **Simulator/validator:** for registered algorithms, compute the *authoritative*
  sequence of states from the LLM's chosen example.
- **Visual call (once per lesson, optional):** **non-semantic presentation only** —
  coordinates, spacing, label shortening ("current node" → "current"). It may
  **not** rename semantic ids, change values, add/remove nodes, or alter labels
  that encode domain meaning (shortening is fine; node value `40` → `4` is not).
  Never per-card, never structure invention.
- **Deterministic compiler:** state → frame (colours, panels, annotations); may
  not alter trace semantics (§6.3).

### 3.5 Generic validator (not per-algorithm)
Check invariants that hold for any trace: `active ∈ base.nodes`; `visited` only
grows; a graph `frontier` holds only discovered-not-completed nodes; `code_line`
in range. ~one validator for all node-link traces. Optional deterministic
simulators (`base + algorithm → trace`) remain as a safety net for well-defined
algorithms only.

### 3.6 Enrich the call-1 → call-2 handoff (incremental, before the full spec)
Add to each card summary: `step_index`/`total_steps`, current-step operation,
`state_before` + `state_after` (so the delta is computed not guessed), and one
`focus_target` + `focus_note`. This makes the second model render, not
reconstruct — and is a strict accuracy + token win on its own.

---

## 4. Goal state

- A visual is `(base_type, mode, algorithm, flags) + base + steps[].state +
  card→step`, authored once, validated against the ontology, rendered
  deterministically.
- **No keyword inference, no per-card structure, no prose-regex state recovery,
  no per-type special-casing.** The bridge collapses to: *validate spec → render*.
- Prose and visuals are guaranteed consistent (same spec). New visual types are
  "fill the state fields + add a profile row", not "write a new pipeline".
- Per-subtype profiles are the home for future, feedback-driven UX rules
  (`visual_ontology_v2.py` descriptions are the seed of these).
- **Non-negotiable:** a worked example is one stable base object + a *delta
  timeline* (§5.3). A visual passes only if it teaches the card's step (§5–§7),
  not merely if it renders.

---

## 5. Teaching-quality layer (pedagogical validity)

> A visual is not valid because it matches the schema. It is valid only if it
> does the *learner job* of the card. This layer sits on top of the architecture
> in §3 and is what turns "it renders" into "it teaches."

### 5.0 Static vs dynamic visuals (scope the heavy machinery)
Two shapes — the trace/delta machinery (§5.3, §6) applies only to the dynamic one:
- **Static visual** (background, concept_definition, comparison, an edge case at
  rest): a `base` + **one validated at-rest state**. No `steps`, no
  `DeltaFoldEngine`, no simulator. Still subject to the §5 gates (richness floors,
  real labels, `PedagogicalVisualValidator`) and the same authority model.
- **Dynamic visual** (worked_example, algorithm_walkthrough, code_walkthrough,
  data_structure_operation): a `base` + a **trace** (`initial_state` + delta
  timeline). This is where §5.3 and §6.0–§6.5 apply.

`visual_intent_type` (§5.2) decides which: `define_structure` / `compare_cases`
→ static; `show_state_change` / `trace_execution` → dynamic. A card never needs
the dynamic machinery to render a static structure — over-applying it is part of
what made the old system heavy.

### 5.1 `visual_role` (declared on every visual)
```
visual_role: primary_visual | support_visual | code_panel | annotation_overlay | fallback_visual
```
**Hard rule:** for `worked_example`, `algorithm_walkthrough`,
`data_structure_operation`, `coding_implementation`, `math_formula_method`, and
`proof_reasoning` cards, a **support visual** (`step_flow`, `topic_snapshot`,
`path_progress`, `practice_feedback`, `source_annotation`) may **never be the
only visual** unless the card role is intro, summary, or roadmap. The domain's
structural visual is required (BFS → node_link/`graph_network`; binary search →
`indexed_sequence`; DP → `grid_matrix`; recursion → `code_execution` +
`call_stack`; formula → `formula`). Support visuals may appear *beside* it,
never *instead of* it. (This is exactly the failure where a single-node
`topic_snapshot` stood in for the real teaching visual.)

### 5.2 `visual_intent_type` (open enum → per-intent requirements)
```
visual_intent_type: define_structure | show_state_change | trace_execution |
  compare_cases | show_formula_mapping | show_memory_model | show_edge_case |
  show_input_output_transform | show_dependency | other(reason)
```
Validators enforce per-intent requirements:

| intent | requires |
|---|---|
| `show_state_change` | ≥2 frames; a non-empty delta per step |
| `trace_execution` | code-line refs; runtime/variable state; a visible change per step |
| `define_structure` | labelled parts; no animation required |
| `show_edge_case` | the boundary condition **and** contrast to the normal case |

**Open enum, with a *guarded* escape hatch.** `other` exists so a taxonomy gap
never blocks a legitimate visual — but it is guarded so the model can't reach for
it whenever unsure. `other(reason)` is allowed only when: (1) `reason` is specific
and non-empty; (2) it is **not** the `primary_visual` of a worked example unless
explicitly allow-listed; (3) the visual still passes the generic structural +
pedagogical validators; (4) telemetry records `other_intent_used` (a rising rate
means a real type is missing — add it, don't normalise the loophole).

**Edge-case contract (`show_edge_case`).** An edge case must show *why the usual
rule changes*, not merely a degenerate structure:
```
EdgeCaseVisual:
    normal_case_reference: visual_model_id | compact_state   # what "normal" looks like
    edge_case_state: state
    contrast_note: str             # how this differs from the normal case
    what_breaks_or_changes: str    # which rule/step behaves differently, and why
```
"Empty tree" alone is not an edge-case visual; "empty tree → the traversal returns
`[]` before the recursion ever runs" is.

### 5.3 Worked-example **delta** contract — *author the delta, compute the rest*
> **Refinement of the reviewer's `state_before + delta + state_after`.** Asking
> the model for all three is three views of one fact and invites the exact
> inconsistency we're killing. The model authors only what can't be derived; the
> system computes the rest, so it *cannot* drift.

Authored once: `initial_state`. Authored per step:
```
WorkedExampleStep:
    delta: { set_active:id, add_to_frontier:[ids], remove_from_frontier:[ids],
             newly_visited:[ids], append_to_output:[vals],
             code_line:int, set_vars:{name:value} }
    learner_should_notice: str          # the ONE thing this step teaches
    common_misread: str | null
    action, reason, text_points         # prose for the card
```
The system folds deltas over `initial_state` to compute `state_before` /
`state_after` for every step. Therefore:
- `state_after = state_before + delta` is true **by construction** — no validator
  is needed for it and it can never be violated.
- Highlights are the diff: `set_active` → current (purple); `add_to_frontier` /
  `newly_visited` *this step* → newly_discovered (gold); prior visited →
  completed; the connecting edge → traversed.
- **Every step must have either a non-empty state delta OR an explicit no-op**
  (`{ no_op: true, checked_element_ids:[…], reason }`) — never a silently empty
  delta. No-ops are first-class: "C is already visited, so BFS doesn't enqueue it"
  or a branch that runs and decides not to update are real teaching moments. A
  step is also invalid if `learner_should_notice` is not reflected in the prose.

This is the load-bearing rule of the whole system: **one stable base object + a
delta timeline.** Non-negotiable.

**Semantic state, not colour.** Deltas resolve to *semantic states*
(`active, newly_added, completed, compared, discarded, selected, error`); a theme
maps states → colours/encodings separately. The "purple/gold/completed" above are
theme defaults, not the contract — this keeps dark mode, accessibility themes, and
per-mode palettes possible (see §5.7 accessibility).

#### 5.3.1 Trace ownership — who authors the deltas
> For **registered** algorithms the LLM must NOT author the delta sequence: even
> clean deltas can encode an algorithmic mistake. The *simulator* owns the trace.

Every worked example declares:
```
trace_source: deterministic_simulator | llm_authored | hybrid_repaired
```
- **Registered algorithm → `deterministic_simulator`.** The LLM authors only the
  *example structure + input* (its chosen graph/array/values). The backend
  simulator runs **on that exact example** (never a canned one — so example and
  trace cannot diverge) and produces the canonical `initial_state` + delta
  timeline. The LLM then writes the prose **from the locked trace**.
- **Unregistered / fuzzy topic → `llm_authored`.** The LLM authors the delta
  timeline; validators + telemetry decide whether the visual is acceptable.
- **`hybrid_repaired`** — an `llm_authored` trace the repair ladder touched;
  logged and surfaced in telemetry for review.

Validation strictness keys off the source:

| trace_source | validation |
|---|---|
| `deterministic_simulator` | trace trusted — validate **render-sync only**; a failure here is a compiler/renderer bug, not content |
| `llm_authored` | validate **all** structural, state, and pedagogical invariants |
| `hybrid_repaired` | as `llm_authored`, plus record every repair |

**The single rule that prevents most remaining worked-example bugs:** *for
registered algorithms the backend simulator owns the delta timeline; for
unregistered topics the LLM authors deltas, but validators and telemetry decide
acceptability.*

**State vs teaching metadata.** The simulator owns the state deltas;
`learner_should_notice` is *teaching metadata*, not state. For a simulator-owned
trace the LLM may author/polish `learner_should_notice` **only if it adds no new
state fact**. The prose model always receives the locked trace **read-only** — it
may explain, compress, or rephrase a step, never add, remove, reorder, or mutate
trace steps.

### 5.4 Code-explanation contract
The code block owns syntax; the explanation owns meaning. Per code step:
```
CodeExecutionStep:
    line_refs:[int]
    line_role: initialize | branch | loop_check | update | recursive_call |
               return | helper_call | other(reason)
    runtime_change: str          # what changed at runtime on this line
    why_this_line_runs_now: str
    vars_delta: {name:value}     # before/after computed by folding (as in §5.3)
    explanation: str             # meaning/effect — NOT a restatement of the code
```
Validator: `explanation` must not quote or paraphrase the highlighted code; it
must name the runtime effect and what the learner should infer. (Formalises the
"EXPLAIN, DON'T RESTATE" rule into a gate.)

### 5.5 Explanation ↔ visual sync
Every visual carries:
```
text_refs: { mentioned_elements:[ids], mentioned_values:{name:value}, code_line_refs:[int] }
```
Validator: every element/value/line the prose mentions must **exist in the visual
state and match**; every highlighted element must be mentioned or justified by
the card. This makes "text says one thing, visual shows another" a hard failure
rather than a thing the bridge tries to reconcile afterward.

**Prose is downstream of the trace (hard invariant).** For worked examples and
code walkthroughs, prose is generated **after** the trace is locked; the prose
prompt *receives* the trace and **may not introduce a new state fact** — no new
step, value, node, or transition that isn't in the trace. The model emits
`text_refs` for what it claims; the validator compares those against trace facts
(no NLP needed). Invalid prose: "now D is visited" when D isn't in the frame
state; "stack is [A, C]" when `runtime_state.stack` is `[C, A]`; "left moves to 4"
when the trace says `left = 3`.

### 5.6 `PedagogicalVisualValidator` — repair → warn → reject ladder
> **Refinement of the reviewer's "reject useless visuals."** A hard reject also
> means *no* visual (text-only). Reject-first quietly trades "wrong visual" for
> "no visual" and tanks coverage. The ladder removes junk *and* protects coverage.

It targets schema-valid-but-useless visuals: a structure rendered as one node
labelled with the concept name; a graph drawn as a tree when `mode=graph_network`;
a step with no visible delta; generic labels (`node`, `edge`, `step`, `concept`);
a support visual used as primary; visual text longer than the card.

It runs as a ladder, not reject-first:
1. **Repair** — auto-fix the unambiguous (re-point a stale highlight, drop a
   generic label, clamp an out-of-range line, switch to the declared mode's
   layout).
2. **Warn** — keep the visual, log the issue (e.g. a slightly dense step).
3. **Reject** — only on a clear, unfixable violation → text-only fallback
   (loud in dev, graceful in prod — §7.1).

**Repairs fix representation, never semantics** — otherwise the repair layer
quietly becomes a new bridge:
- *Safe (allowed):* clamp an out-of-range code line; drop a generic label;
  re-point a stale highlight when the target is unambiguous; switch tree→graph
  layout when `mode` already declares `graph_network`.
- *Unsafe (forbidden):* changing traversal order; inventing missing nodes;
  changing algorithm output; rewriting the example structure; guessing variable
  values. A **semantic/algorithmic** error is not repairable — it must trigger
  simulator recomputation (if registered), a retry, or rejection. On a
  `deterministic_simulator` trace such a failure can't be a content error at all
  — it's a compiler/renderer bug.

Track **`visual_coverage`**, **`visual_rejection_rate`**, and
**`visual_repair_rate`** (broken down by `base_type` / `algorithm` / prompt
version) as first-class metrics. A high repair rate means generation is only
"working" because the backend constantly cleans up poor output — a signal the
prompt/schema/simulator split needs work. The goal is *high coverage of correct
visuals*, not maximal rejection.

### 5.7 Richness budgets (not too noisy, *and not too trivial*)
**Ceilings (cognitive load), per frame:** ≤2 callouts; ≤3 active highlights (more
only when comparing groups); ≤2 support panels; ≤3 primary animations (+ secondary
fades); visual text 20–35 words by type.

**Floors (must teach enough), per mode** — kept in the per-mode profile (§3.2) so
they are keyed by subtype, with an explicit edge-case exception:
- `tree_hierarchy` ≥5 nodes · `graph_network` ≥5 nodes + ≥1 branching choice ·
  `binary_search_range` array length ≥7 · `dp_table` ≥3×3 · `linked_list_chain`
  shows predecessor/current/next where relevant.

A single-node or trivial example passes the schema but fails the floor — this is
what catches the "BST rendered as one node" / tiny-example case from the other
direction than the noise ceiling.

**Accessibility (no meaning by colour alone).** Every highlight needs a
non-colour encoding (border / icon / label / pattern / position); every selectable
element has an `aria_label`; keyboard order follows trace/reading order;
reduced-motion preserves state changes via instant transitions. (This is why
§5.3 resolves to *semantic states* before colour.)

**Layout fit.** A visual fits the card without horizontal scroll; side panels
stack/collapse on mobile; code+diagram layouts declare a priority (code
left/right/top by width); large graphs **simplify layout** rather than shrink text
below readability.

**Motion budget.** A transition exists to show *one* state change, not to
decorate: ≤400 ms per step transition; one primary motion at a time (the change
in `primary_change`), secondary updates as instant or fades; target 60 fps with
≤30 animated elements (above that, animate the diff only, not the whole base);
`prefers-reduced-motion` ⇒ instant transitions that still leave before/after
legible. Motion is keyed to the delta, never free-running.

### 5.8 "One card = one change" (warning, not hard reject)
Each worked-example/code step should introduce one primary conceptual change (it
may touch several elements if they are one action). **Refinement:** dense
multi-change steps are **flagged**, not blocked — setup/summary cards legitimately
show several things at once.

### 5.9 `card_role → required visual behavior` (operational table)
Used by both validators (enforcement) and prompt construction (what to ask for):

| card role | required visual behavior |
|---|---|
| intro / background | support visual allowed |
| concept_definition | `define_structure` primary visual preferred |
| worked_example_setup | primary structural visual required (the base at rest) |
| worked_example_step | same primary visual + **non-empty delta OR explicit no-op decision** required |
| code_walkthrough_setup | full code panel required |
| code_walkthrough_step | code-line refs + **runtime delta OR explicit no-op/branch decision** required |
| edge_case | primary visual in the boundary state + contrast (§5.2) |
| comparison | side-by-side primary visual(s) |
| summary / roadmap | support visual allowed |
| practice | prediction/feedback support visual |

---

## 6. Pipeline order — canonicalise the example first

End-to-end (authority flows downhill — §6.2/§6.3; the LLM never emits render data):
```
  topic classifier ─▶ declares (base_type, mode, algorithm, flags)
        │
        ▼
  ① CanonicalExample ─▶ ② ExampleInvariantValidator ──(invalid)──▶ re-select example
        │ valid
        ▼                         registered → simulator (authoritative, §5.3.1)
  ③ Trace ───────────────────────┤
        │                         unregistered → LLM-authored deltas (validated, §5.6)
        ▼
  DeltaFoldEngine ─▶ FrameState[]  (state_before / delta / state_after + diff)
        │
        ▼
  ④ Compiler ─▶ VisualModel + RenderSteps          (styles; never re-decides — §6.3)
        │
        ├─▶ ⑤ Prose generated FROM the locked trace (read-only — §5.5)
        ▼
  ⑥ Validators (§6.4) ─▶ rendered | repaired | text-only fallback (§7.1)
        │
        ▼
  Frontend: renders only — never infers/recovers/decides (§7.4)
```

Lock the example *before* any prose or visuals are written, so both derive from
the same locked object:
```
1. Select example   LLM picks structure + input        → carries example_id
2. Validate example invariants (§6.0)                  → fail ⇒ retry SELECTION, not trace
3. Trace            registered → simulator; else LLM   → carries trace_id, trace_source (§6.1)
4. Compile frames   deterministic (§6.3)
5. Generate prose   FROM the locked trace (§5.5)
6. Validate prose ↔ trace sync (§5.5)
```
Not "generate prose and visual plan together" — that simultaneity is the drift
source. Every object downstream of step 1 carries `example_id` + `trace_id` (on
`WorkedExamplePlan`, `VisualModel`, `RenderStep`, debug payloads, telemetry) so a
failure can be traced across backend logs, frontend errors, and usage data.

### 6.0 ExampleInvariantValidator — validate the example *before* tracing
> A correct simulator will faithfully trace a **bad** example. So the example's
> domain invariants must hold before the trace runs — and a failure retries
> *example selection*, not trace generation.

Per declared `(mode, algorithm)`: e.g. `tree_hierarchy`+BST → `left < root <
right`; `binary_search_range` → array sorted; Dijkstra → non-negative weights; DP
table → dimensions match the recurrence; `linked_list_chain` → no accidental
cycle unless the topic is cycle detection; graph BFS/DFS → start node reachable to
the claimed extent. On failure: re-select the example (**bounded** — N retries),
then fall back to a **registered canonical seed** for that algorithm rather than
loop forever or burn tokens.

### 6.1 Deterministic simulator registry
> **Refinement of "simulator-first for well-defined algorithms."** Universal
> simulator-first is wrong (non-standard/fuzzy algorithms break it); universal
> LLM-authored is wrong (loses guaranteed correctness). Split by a registry.

A registry maps `algorithm → simulator`:
- **Registered algorithms own their trace** (simulator-first — correctness and
  consistency guaranteed). The LLM still *picks the example and writes the
  prose*; the backend computes the actual trace.
- **Unregistered / fuzzy algorithms** use the LLM-authored delta timeline (§5.3)
  plus the validators. Forcing a brittle simulator there would be worse.

Initial registry, by frequency (build in this order, not all up front): tree
traversals (in/pre/post/level-order) · BFS · DFS · binary search · two-pointer ·
sliding window · sorting passes · DP table fill · stack/queue ops · linked-list
insert/delete · Dijkstra.

### 6.2 Source-of-truth priority
When two layers disagree, the higher wins — and lower layers may never invent
what an upper layer omitted:
```
1. deterministic simulator trace   (for registered algorithms)
2. canonical example object         (§6 step 1)
3. compiled visual model
4. generated prose
5. frontend rendering
```
**Prose never overrides the trace. The frontend never infers missing state.**
This is the rule that stops bridge-style reconciliation (and `learn/page.tsx`
recovery logic) from creeping back in — there is exactly one authority per fact,
and it flows downhill.

### 6.3 Layer contracts — each layer's *may / may not*
The priority order (§6.2) only works if every layer stays in its lane. One table,
top to bottom:

| layer | may | may NOT |
|---|---|---|
| **LLM** | pick example structure + input; (unregistered only) propose deltas; write prose from the locked trace | emit coordinates, colours, layout, render JSON; (registered) author the state sequence; introduce facts not in the trace |
| **Simulator** | compute the authoritative delta timeline for a *registered* algorithm on the LLM's example | run on a different example than the LLM chose |
| **Compiler** | translate trace state → frames: highlights, layout, transitions, labels, panels | alter trace *semantics* — change active elements, visited sets, variable values, output, or code-line refs |
| **Frontend** (§7.4) | render, animate, expose click targets | infer type, recover missing state, choose between visuals, synthesise fallbacks, parse prose |

> **LLM output must be boring.** For a registered algorithm the LLM returns only
> `{ example_structure, input, why_this_example, learner_goal }` — data, not a
> creative render description. The "compiler may not mutate trace semantics" rule
> is the compiler's equivalent of the frontend contract: it styles the trace, it
> never re-decides it.

### 6.4 Validator pipeline (order + grouping)
Validators run in stages keyed to the pipeline; an earlier failure short-circuits
the rest and sets the lifecycle status (§7.0):

| stage | validators | on fail |
|---|---|---|
| **Pre-trace** | `VisualIntentValidator`, `ExampleInvariantValidator` (§6.0) | retry example *selection* (bounded → canonical seed) |
| **Trace** | `TraceValidator`, `DeltaFoldValidator` | registered → recompute; else retry / reject |
| **Compile** | `VisualModelValidator`, `RenderStepValidator`, `TransitionValidator`, `CoordinateStabilityValidator` | compiler bug → fail loud (§7.1) |
| **Teaching** | `TextVisualSyncValidator` (§5.5), `PedagogicalVisualValidator` ladder (§5.6) | repair → warn → reject |
| **Frontend** | `FrontendContractValidator` (§7.4) | reject any payload that asks the frontend to decide |

### 6.5 Core artifacts & services (make the implied objects explicit)
Three named objects flow through the pipeline so fields don't scatter across
prompts, intents, and plans:
```
CanonicalExample   (output of step 1; input to §6.0 + the simulator)
  { example_id, domain_object, base_type, mode, algorithm?,
    input, base_structure, expected_output?, why_this_example, learner_goal }

Trace              (output of step 3; input to the compiler — distinct from prose)
  { trace_id, example_id, trace_source, initial_state, steps:[TraceStep] }
  TraceStep {
    step_index, trace_step_id?,    # stable id for telemetry / debug / clickable context
    kind: initialize|select_active|compare|enqueue|dequeue|visit|update_pointer|
          discard_range|fill_cell|return|complete|other,   # pedagogical kind
    delta,                  # a state change OR { no_op:true, checked_element_ids:[…], reason }
    primary_change,         # the ONE teaching focus (a delta key) — drives prose + animation
    decision?: { condition, evaluated_to, reason },        # evaluated_to: bool OR enum (e.g. less_than|greater_than|equal)
    learner_should_notice, code_line_refs?, runtime_label?
  }
```
`kind` makes prose/animation/validation precise (a `compare` highlights two
values; an `enqueue` animates the frontier; a `return` emphasises output).
`primary_change` makes "one card = one change" (§5.8) concrete — a multi-key delta
still has a single teaching focus. `decision` makes conditional steps explicit
(e.g. `{ condition:"D not in visited", evaluated_to:true, reason:"D is new → enqueue" }`).
Flow: **CanonicalExample → Trace → VisualModel + RenderSteps + Prose.**

**`DeltaFoldEngine`** — the single core service that folds `initial_state` +
`TraceStep[]` → `FrameState[]` (with `state_before` / `delta` / `state_after` +
diff metadata for highlights). It applies deltas deterministically, detects
invalid deltas, and **never styles or lays out**. Every compiler consumes its
output, so delta-folding can't be re-implemented inconsistently per type.

**Each mode profile (§3.2) owns its delta vocabulary** — the allowed delta ops
(plus the shared `no_op` form), so deltas stay controlled and validator-friendly:
- `graph_network`: `set_active, add_to_frontier, remove_from_frontier, newly_visited, append_to_output`
- `binary_search_range`: `set_pointer, shrink_range, mark_mid, mark_discarded, set_vars`
- `dp_table`: `set_active_cell, fill_cell, add_dependency_arrow, mark_completed`
- `code_execution`: `set_highlight_lines, set_vars, push_call, pop_call, append_output`

Non-CS modes have vocabularies too (the model isn't graph-only): `formula` →
`substitute, simplify, define_symbol, factor`; `geometry` → `add_construction,
mark_angle, mark_length, drop_perpendicular`; `set_region` → `shade_region,
add_element, mark_overlap`. A new mode = "register its delta vocabulary + a
profile row," not a new pipeline.

**Simulators validate output.** For a registered algorithm the simulator computes
`expected_output` (or validates the example's against its own result); the LLM's
`expected_output` may never override the simulator's — preventing "BFS output is
`[A,C,B]`" prose over an `[A,B,C]` trace.

**Versioning.** Every artifact carries `visual_spec_version`,
`delta_schema_version`, `compiler_version`, `simulator_version?`,
`prompt_version?`, so telemetry and regressions attribute quality changes to a
specific version.

---

## 7. Operability (make failures visible, learn from usage)

### 7.0 Visual lifecycle status
Every visual carries one generation-lifecycle status, so each phase logs exactly
one outcome and `visual_coverage` is a simple count:
```
visual_status: planned | traced | compiled | validated | rendered | fallback_used | failed
failure detail: trace_failed | compile_failed | validation_failed | render_failed
```
Interaction (`interacted_with`, clicks, replays) is **usage telemetry (§7.2)**,
not a lifecycle state — keep generation status and usage events separate.

### 7.1 Failures: loud in dev, graceful in prod
- **Dev:** a visible error panel naming the failed invariant +
  `{visual_model_id, card_id, base_type, mode, frame_index}`. **No placeholder /
  stub visuals in real lesson flows** — a stub makes the page look fine while the
  learner experience is broken.
- **Prod:** degrade to text-only + emit structured telemetry.

Silent fallback hides the very failures we are removing (we hit this directly
with a stubbed prompt and quiet degradations earlier).

**Reproducible debug payload.** Every visual failure (dev panel + prod telemetry)
carries enough to drop straight into a regression test:
```
{ topic_id, lesson_id, card_id, visual_model_id, example_id, trace_id,
  trace_source, base_type, mode, algorithm, visual_status, failed_validator,
  initial_state, delta, compiled_frame }
```

### 7.2 Telemetry
Track: `visual_generation_failed`, `visual_validation_failed`, `fallback_used`,
`visual_repair_rate` (+ `repair_count_by_base_type` / `_by_algorithm` /
`_by_prompt_version`), `other_intent_used`, `visual_clicked`,
`visual_question_asked`, `animation_replayed`, `step_back_used`,
`step_skipped_fast`, `visual_hidden_or_ignored`, `time_on_step`. Headline metric:
**`visual_step_confusion_rate`** — e.g. a learner clicking a node and asking "why
is this visited?" means the state or explanation is unclear. Improve visuals from
real usage, not just prompt tuning. (Extends the existing `v2_telemetry`.)

### 7.3 Failure-mode + diff-snapshot regression tests
**Known-bad outputs** (must not silently return): single-node snapshot for a
structural topic · graph rendered as a tree · overlapping edge labels ·
worked-example step with no delta · code walkthrough with no line refs · support
visual used as primary · prose value absent from visual state · unstable element
ids across frames.

**Diff-snapshot tests** — given `initial_state` + deltas, snapshot `state_before`,
`delta`, `state_after`, `highlights`, `transitions` per step. These catch the case
where the delta-fold is correct but the compiler highlights the wrong element
(e.g. `delta.newly_visited=[B]`, `state_after.visited=[A,B]`, yet the frame marks
`C` gold — a compiler/highlight bug, not a content bug).

### 7.4 Frontend contract — the frontend renders; it does not decide
The frontend receives exactly `{ render_steps, visual_models, frame_index }`.
- **May:** render, animate, expose click targets.
- **May NOT:** infer the visual type, recover missing state, choose between
  multiple visuals, synthesise a fallback diagram, or parse prose for visual
  state.

A hard invariant — this is what stops the old `learn/page.tsx` visual-recovery
logic from reappearing in V2. If a fact is missing, the frontend shows the
declared fallback (§7.1); it never guesses. (Consistent with §6.2: the frontend
is the lowest layer and may not invent what an upper layer omitted.)

---

## 8. Migration plan (incremental, reversible — never a big-bang)

1. **Foundations (build once, used everywhere).** The unified spec schema
   (generalise `worked_example_plan`); the delta-fold (`initial_state` + deltas →
   per-step state, §5.3); the `state → frame` renderer (~one per base kind); the
   structural + `PedagogicalVisualValidator` ladder (§5.6); and **dev-loud
   failures + the telemetry hooks (§7) from day one** — so every later phase is
   measured, not guessed.
2. **Pilot: graph traversal.** Most broken, no deterministic path today. Add the
   canonicalisation stage (§6) and the first registry simulators (BFS/DFS, §6.1);
   render the spec; keep the old path behind a flag as fallback.
3. **Migrate tree traversal.** Largest deletion of bespoke code; BST
   canonicalisation survives only as a registry simulator. Add traversal/binary
   search/sliding-window simulators.
4. **Roll out** to arrays, code, grid/DP, etc. — each is "fill the delta fields +
   add a profile row + (optional) register a simulator".
5. **Retire** keyword inference, per-card structure repetition, and the regex
   extractors. Bridge collapses to *validate spec → render*.

Each phase ships independently with the old path as fallback, so the system is
never in a broken state, and `visual_coverage` / `visual_rejection_rate` /
`visual_step_confusion_rate` (§5.6, §7.2) gate whether a phase is actually better
before the old path is removed.

### 8.1 Graph-traversal pilot checklist (the first end-to-end slice)
1. Define `CanonicalExample` for graph traversal (§6.5).
2. `ExampleInvariantValidator` for `graph_network` + BFS/DFS (§6.0).
3. BFS/DFS simulators → `Trace` (§6.1, §6.5).
4. `DeltaFoldEngine` for the `graph_network` delta vocabulary (§6.5).
5. `NodeLinkCompiler` from folded states (semantic states → frames, §6.3).
6. `TextVisualSyncValidator` (§5.5) + the `PedagogicalVisualValidator` ladder (§5.6).
7. Diff-snapshot tests, seeded with the **Appendix (§11) BFS trace as the golden test**.
8. Route one graph-traversal topic through v2 behind a feature flag; compare
   against the old path before widening.

**Widening gates (tune the numbers, keep the gates):** `visual_coverage` ≥ 95% ·
`visual_rejection_rate` ≤ 5% · `visual_repair_rate` trending down · zero known-bad
regression failures · no dev-loud compiler failures on the golden traces. Only
then widen to the next mode/topic.

---

## 9. Status — specification complete

All previously-deferred items are now in the spec:
- Validator inventory + order → **§6.4**.
- End-to-end architecture diagram → **§6** (with the "LLM never emits render data"
  invariant in the layer contracts, §6.3).
- Animation/motion budgets → **§5.7**.
- Static-vs-dynamic visual shapes → **§5.0**.

No specification gaps remain. The only open work is **implementation** — the
graph-traversal pilot (§8.1), with the §11 BFS / §11.2 binary-search traces as
golden tests. Future spec changes should be *driven by* pilot telemetry
(`visual_repair_rate`, `confusion_rate`, rejection reasons), not added
speculatively.

---

## 10. Reference

- Taxonomy + descriptions: `backend/app/core/visual_ontology_v2.py`
  (`BASE_TYPE_DESCRIPTIONS`, `MODE_DESCRIPTIONS`, `describe()`).
- Bridge (to shrink): `backend/app/services/legacy_v2_visual_bridge.py`.
- Compilers: `backend/app/services/visual_compilers/*`.
- Content call: `generate_lean_structured_lesson`; visual call:
  `generate_visual_patches` (`backend/app/services/llm_client.py`).
- Renderers: `frontend/components/visuals_v2/*`.

---

## 11. Appendix — a concrete worked example (BFS)

The §5.3 contract end to end: one base, `initial_state` once, a delta per step.

```json
{
  "base": { "mode": "graph_network",
            "nodes": ["A","B","C","D","E"],
            "edges": [["A","B"],["A","C"],["B","D"],["C","E"]] },
  "trace_source": "deterministic_simulator",
  "algorithm": "bfs",
  "initial_state": { "active": null, "frontier": {"kind":"queue","items":["A"]},
                     "visited": [], "output": [] },
  "steps": [
    { "delta": { "set_active":"A", "remove_from_frontier":["A"], "newly_visited":["A"],
                 "add_to_frontier":["B","C"], "append_to_output":["A"] },
      "learner_should_notice": "BFS visits A, then queues neighbours B and C before going deeper." },
    { "delta": { "set_active":"B", "remove_from_frontier":["B"], "newly_visited":["B"],
                 "add_to_frontier":["D"], "append_to_output":["B"] },
      "learner_should_notice": "B is dequeued before C's children — breadth first." }
  ]
}
```

Folded result for step 2: `state_before = {visited:[A], queue:[B,C], output:[A]}`,
`state_after = {visited:[A,B], queue:[C,D], output:[A,B]}`. The **compiler**
derives (it does not invent): `B` → current (purple), `A` → completed, `D` →
newly_discovered (gold), edge `B→D` → traversed, QUEUE `[C,D]`, OUTPUT `[A,B]`.
No prose is parsed — the prose is generated *from* this trace and validated
against it (§5.5).

### 11.2 Second golden test — binary search (`indexed_sequence`)
Exercises a *different* delta vocabulary (pointers/ranges/compare/discard), proving
the model generalises beyond graphs:
```json
{
  "base": { "mode": "binary_search_range",
            "array": [3,7,9,12,18,21,30], "input": { "target": 18 } },
  "trace_source": "deterministic_simulator", "algorithm": "binary_search",
  "initial_state": { "vars": {"low":0,"high":6}, "range":[0,6], "mid": null },
  "steps": [
    { "kind":"compare",
      "delta": { "set_pointer":{"mid":3}, "mark_mid":3, "set_vars":{"mid":3} },
      "primary_change":"mark_mid",
      "decision": { "condition":"a[mid]=12 vs target 18", "evaluated_to":"less_than",
                    "reason":"a[mid] < target → search the right half" },
      "learner_should_notice": "Compare the midpoint, not a scan — that's the log n win." },
    { "kind":"discard_range",
      "delta": { "shrink_range":[4,6], "mark_discarded":[0,3], "set_vars":{"low":4} },
      "primary_change":"shrink_range",
      "learner_should_notice": "Half the array is eliminated in one comparison." }
  ]
}
```
Same engine, same validators — only the mode profile's delta vocabulary differs.
