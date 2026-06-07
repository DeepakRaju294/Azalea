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
4. **Author once, render deterministically.** The LLM commits to the example
   and the sequence of states once; turning a state into a frame is a pure
   function (no LLM, no regex).
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

### 3.4 Re-divide the work
- **LLM (once):** pick the example shape + the correct sequence of states.
- **Visual call (once per lesson, optional):** layout coordinates + label polish
  for the base — never per-card, never structure invention.
- **Deterministic:** state → frame (colours, panels, annotations).

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

---

## 5. Migration plan (incremental, reversible — never a big-bang)

1. **Spec schema + generic renderer + validator.** Generalise the existing
   `worked_example_plan` into the unified spec; write the `state → frame` mapper
   (~one per base kind) and the structural validator.
2. **Pilot: graph traversal.** Most broken, no deterministic path today. LLM
   authors the spec; render it; keep the old path behind a flag as fallback.
3. **Migrate tree traversal.** Largest deletion of bespoke code; BST
   canonicalisation survives only as an optional simulator.
4. **Roll out** to arrays, code, grid/DP, etc. — each is "fill the state fields".
5. **Retire** keyword inference, per-card structure repetition, and the regex
   extractors. Bridge shrinks dramatically.

Each phase ships independently with the old path as fallback, so the system is
never in a broken state.

---

## 6. Reference

- Taxonomy + descriptions: `backend/venv/app/core/visual_ontology_v2.py`
  (`BASE_TYPE_DESCRIPTIONS`, `MODE_DESCRIPTIONS`, `describe()`).
- Bridge (to shrink): `backend/venv/app/services/legacy_v2_visual_bridge.py`.
- Compilers: `backend/venv/app/services/visual_compilers/*`.
- Content call: `generate_lean_structured_lesson`; visual call:
  `generate_visual_patches` (`backend/venv/app/services/llm_client.py`).
- Renderers: `frontend/components/visuals_v2/*`.
