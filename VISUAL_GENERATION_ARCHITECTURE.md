# Visual Generation Architecture

Status: **v5 — ARCHITECTURE FROZEN; READY TO IMPLEMENT** (provisioned-not-triggered). Extracted from
`GENERATION_AND_VISUAL_FOUNDATION_SPEC.md` §10 v10. v2 added Blueprint/Ontology/concept-assets/confidence/
concept-aware-retrieval/evolution/benchmark (§17–§23); v3 made the Visual Blueprint a root + Reference
Packs/Failure Memory/style-vs-concept versioning/benchmark categories/coverage (§24–§27); v4 added
operational refinements — complexity levels, invariants, educational-vs-rendering intent, deterministic
fallback, observability (§28–§31); **v5 closes the last two structural gaps** — the **Canonical Concept
Library above the blueprint** (blueprints become per-purpose), the **explicit rendering pipeline**, and the
**declarative-blueprint rule** (§32–§34) — adding no new metadata/fields/dimensions. The dedicated
specification for Azalea's visual subsystem: how educational visuals are steered, generated, validated,
stored, versioned, retrieved, adapted, and improved.

**Relationship to other specs.** This is the companion to `GENERATION_AND_VISUAL_FOUNDATION_SPEC.md`
(the "cost spec"), which owns text generation, the worked-example pipeline, and the **semantic-state
keystone** this subsystem consumes. Where the cost spec previously held §10, that content now lives here;
the cost spec keeps a short pointer + the dependency contract. This doc owns everything visual; the cost
spec owns everything textual. They share one artifact: the per-step **semantic state** (cost spec §7).

**One-line philosophy:** *generate one accurate conceptual visual per topic, reuse it wherever possible,
adapt it only when necessary, validate everything before it is stored, version it, and continuously grow
a curated, self-improving library of validated educational visuals.*

---

## Architecture overview (three layers; the Blueprint is the root)

The subsystem is **three layers with a two-level Knowledge root**. The **Canonical Concept (§32) is the
root** — the durable, purpose-independent truth of what a concept *is* (representation, terminology,
structure, invariants, relationships). Below it sit **per-purpose Visual Blueprints (§17)** — one per
lesson purpose (intro / worked-example / implementation / review) — each a *rendering definition* derived
from the canonical concept; and validation rules, reference pack, and metadata are projections of the
blueprint. Generation and storage are implementation details below that.

```text
Concept
   │
   ▼
VISUAL KNOWLEDGE LAYER  — what a concept's visual IS (durable, rarely changes)
   Canonical Concept  (ROOT, §32)   — representation · terminology · structure · invariants · relationships
     │   (one per concept; educational truth; purpose-independent)
     ▼
   Visual Blueprints  (PER PURPOSE, §17)   intro · worked_example · implementation · review
     ├ Rendering intent (visual type §4 / shape / composition §6)
     ├ Complexity level (§28)     ├ Reference Pack (§24)
     ├ Validation rules (§10)     └ Metadata (§12.2, derived)
   │
   ▼
GENERATION LAYER  — how a visual is produced + checked (per lesson)
   Blueprint → reference selection → prompt assembly → generate → validate → adapt   (the §33 pipeline)
   + Failure Memory (§25)
   │
   ▼
VISUAL MEMORY DATABASE  — what we keep + improve (curated library)
   store → version → retrieve → curate   (§12)  + style-vs-concept versions (§26) + coverage (§27)
```

Read the rest of this doc through these layers: **Knowledge** = §4–§9 + §17–§18 + §32; **Generation** =
§1, §10–§11 + §25 + the §33 pipeline; **Memory** = §12 + §26–§27. The benchmark (§23) and coverage (§27)
measure the whole.

---

## 0. North star

> A visual is correct **before** it is attractive. The platform generates **one canonical, validated
> visual per topic**, reuses it across the topic's cards, adapts it only at real structural transitions,
> and stores only **validated** visuals as **versioned, full assets** in a curated **Visual Memory
> Database** that learns from usage and user feedback. Image generation is the primary mechanism, but it
> is **steered** (visual type + shape description + metadata) and **gated** (acceptance validation), never
> open-ended.

**Provisioned, not triggered.** Build the schemas, derive the data, and stand up the deterministic
validators **now**; do not call an image model or render a pixel until `AZALEA_VISUALS_ENABLED=true`
(§14). Turning visuals on is wiring the generator/renderer to already-present data — not changing text
generation.

---

## 1. Scope and primary mechanism

**Primary production mechanism: AI image generation, guided — not open-ended.** The main way to produce
an educational visual is to generate an image with an image model, *steered* by three deterministic
controls so the result reliably shows the correct conceptual structure (a BST always looks like a valid
BST, a graph a node-link diagram, merge sort a recursive split/merge of arrays, a linked list a linear
pointer chain):
1. a chosen **visual type** (§4) — fixes the expected geometry/layout family;
2. a **shape description** (§4) — the structural properties a correct rendering must have;
3. rich **metadata** (§12) — the concept, required elements, forbidden elements.

**Deterministic structural rendering is a complementary exact option.** For pure structural shapes,
rendering a valid BST directly from semantic state is *more* reliable than any image model, and the
deterministic semantic/topological checks are the natural correctness gate on a generated image (§10).
The two are complementary, not competing: image generation gives reach and richness; deterministic
rendering/validation gives exactness.

**Objective: conceptual correctness, not attractiveness.** Every visual must immediately communicate the
right structure. Style is cosmetic (§10).

---

## 2. Central rule (carry verbatim)

> The model decides what the visual **means** (objects, relationships, emphasis, archetype, visual type);
> **deterministic systems decide / enforce exact structure, geometry, labels, layout, collisions,
> validation, and acceptance**; a rendered audit verifies it teaches the intended idea. The model never
> emits coordinates, arrow routing, collision avoidance, SVG, colors, or sizes — and when an image model
> *does* draw those, the **visual contract (§10)** is what validates the result.

---

## 3. Canonical image ownership (the topic owns the visual)

The unit of visual generation is the **topic**, not the card. Ownership is explicit so a lesson is
visually consistent end to end:

```text
Topic ─────────────▶ OWNS the canonical visual (one validated base image + its asset record §12)
  ├─ Worked Example ─▶ REFERENCES the topic canonical (adapts via §11)
  ├─ Algorithm Walkthrough ─▶ REFERENCES the topic canonical
  ├─ Edge Case ──────▶ REFERENCES the topic canonical
  └─ Implementation ─▶ REFERENCES the topic canonical
```

Rules:
- A topic resolves its canonical visual **once** (retrieve or generate, §12), then every card in the
  topic **references** it. Cards do **not** each independently hit the database for an unrelated image.
- A card adapts the canonical (annotate or reference-regenerate, §11); it never silently introduces a
  visually inconsistent image.
- A topic may own **more than one base scene per visual phase** when the structure genuinely changes
  (e.g. merge sort's *split* scene and *merge* scene, §8) — but each phase scene is still topic-owned and
  shared by the cards in that phase, not per-card.

This is what guarantees a single consistent visual language within a lesson. **Refinement (§19):**
ownership is actually two layers — the **concept** owns the durable canonical (a *concept asset*), and a
topic/lesson holds a derived *lesson asset* that references it — so the same concept asset is shared
across every lesson that teaches it.

---

## 4. Visual types + shape descriptions (steering, not free-prompting)

Generation is guided by a **visual type** and a **shape description**, never open-ended prompting. Both
are composed into the per-concept **Visual Blueprint** (§17), which is what the generator actually
consumes; and the visual type itself sits **under the Visual Ontology** (§18), a semantic layer that
constrains which types are even eligible.

- **Visual type** — *which structural family* represents the concept: hierarchical tree, node-link
  diagram, array structure, recursive split tree, grid, state machine, mathematical graph, pointer
  diagram, circuit diagram, etc. Each type fixes the **expected geometry and layout**. The visual types
  are the **primitive grammar of §6** plus their composition recipes — the closed vocabulary the
  archetype inference (§5) selects. Chosen **deterministically** for known families (zero model call);
  only a genuinely novel concept needs an LLM pick from the closed vocabulary.
- **Shape description** — a per-concept-family statement of the **structural properties a correct
  visualization must have** (what it should *fundamentally look like*, not how it's styled): e.g. "a BST
  is a rooted binary tree where every left descendant < node < every right descendant"; "merge sort is a
  recursive top-down split of one array into halves, then a bottom-up merge of sorted halves." Shape
  descriptions + visual type + metadata stop the image model from rendering a graph as a tree or a merge
  sort as a generic flowchart, and they double as the **topological acceptance test** (§10): an image is
  accepted/stored only if it satisfies its shape description.

Maintain shape descriptions **per concept family** (reusable, not per-topic) so they amortize across the
curriculum and feed both steering and acceptance validation.

---

## 5. Archetype inference from a composite key (not state keys alone)

State shape alone is ambiguous — a `list` could be an array, linked list, queue, stack, set, or
timeline; a `call_stack` could be a stack, a recursion tree, or a code+stack panel — and the right choice
is **pedagogical**, not just structural. So the archetype is inferred deterministically from a
**composite key**, not from `resolved_state_after` keys alone:
```json
{
  "topic_family": "recursive_divide_and_conquer",
  "example_mode": "coding_implementation",
  "card_role": "worked_example_step",
  "primary_kind": "merge",
  "state_schema": "merge_state_v1",
  "visual_goal": "show how two sorted halves combine",
  "visual_archetype": "split_merge_process"
}
```
For known families this composite maps deterministically to an archetype (zero model call); a novel
concept needs an LLM pick from the closed vocabulary (§6; cheap, cached per concept). The archetype is
chosen **once per example** (stable), never per step.

**Fallback policy — keep type and status separate (never force a bad visual):** `visual_archetype` is a
known archetype **or `null`**; the *reason* a visual is or isn't shown lives in a distinct
`visual_status`:
```json
{ "visual_archetype": "split_merge_process | null",
  "visual_status": "supported | unsupported | withheld_untrusted" }
```
- **`supported`** → archetype resolved with confidence; proceed.
- **`unsupported`** → no grammar/archetype fits yet (novel shape). Retain state + intent packet, render
  **text-first**, route to reference-guided generation later. *(Signal: expand primitive coverage.)*
- **`withheld_untrusted`** → a grammar fits, but `trace_confidence` (cost spec §6.3) is too low to trust
  the state. Render **text-first**, do not derive a visual from unverified state. *(Signal: improve
  trace.)*

---

## 6. Primitive grammar (closed, composable vocabulary — not a diagram zoo)

A small set of generic primitives, each with a schema and a **concept-agnostic** layout engine (a tree
layout draws *any* tree), so ~10 primitives cover ~all structural concepts without per-concept
hardcoding.

| primitive | covers | layout engine |
|---|---|---|
| `sequence` | arrays, strings, linked lists, pointers, ranges | row of cells |
| `graph` | trees, graphs, state machines, recursion trees | tree/force layout |
| `grid` | matrices, DP tables, boards | 2-D grid |
| `axes` | functions, curves, scatter | coordinate plane |
| `container` | stack, queue, set, multiset | ordered/unordered box |
| `regions` | Venn, partitions, set ops | overlapping areas |
| `flow` | pipelines, processes, transitions | boxes + arrows |
| `bars` | comparisons, histograms | bar chart |
| `component_diagram` | labeled spatial systems (circuit, device, anatomy, architecture) | components + compartments + connectors + label anchors + focus region |

`component_diagram` replaces a vague catch-all "scene": it has an **explicit contract** (objects/
components, compartments, connectors, label anchors, directional relations, focus region) so it stays
constrained — not the escape hatch where every hard visual lands.

**Composition recipes** (reusable arrangements, not topic diagrams): `source→transformation→output`,
`before→action→after`, `main_structure + side_state_panel`, `two_systems + comparison_bridge`,
`hierarchy + focus_node`, `central_object + labeled_components`, `code_panel + state_panel +
highlighted_block`, `equation_chain + active_transformation`. The model may pick/compose recipes; the
renderer owns panel sizes, spacing, alignment, label placement, responsive layout.

---

## 7. Visual intent packet — DERIVED, not a default LLM call

The intent packet describes the *semantics* needed to produce the right shape. Its fields come almost
entirely from data already produced — **derive it; only call the LLM for the novel tail**.
```json
{
  "visual_goal": "<from the card's goal>",
  "learner_question": "<from the card's goal + reasoning/how>",
  "reasoning_pattern": ["comparison","state_change","elimination"],
  "primary_objects": "<derived from resolved-state keys + topic family>",
  "required_relationships": "<derived from state + work>",
  "must_emphasize": "<derived from the step delta>",
  "must_not_show": ["unrelated structure","decorative nodes","paragraphs inside the visual"],
  "reading_direction": "left_to_right",
  "density": "low",
  "visual_mode": "exact_structural",
  "step_scope": "delta_from_previous_state",
  "reference_profile": {
    "reasoning_patterns": ["comparison", "state_change"],
    "composition_recipe": "main_structure_plus_side_state",
    "density": "low",
    "preferred_reference_family": "array_state"
  }
}
```
`reference_profile` future-proofs reference-image retrieval: deriving it cheaply now means the retrieval
system (§12) plugs into the existing intent packet without changing first-pass generation.

---

## 8. Base scene(s) + per-step delta + layered assets

**One stable base scene per visual PHASE** (not necessarily one per whole example), then a small
**delta per step** within the active scene — never a new visual per card. A scene change happens only at
a **meaningful structural transition** (merge sort: a *split* scene and a *merge* scene, each stable
across its run of cards). Scenes + deltas are derivable from the semantic state (cost spec §7).
```json
// base scene (once per phase)
{ "scene_type": "split_merge_process",
  "entities": [ {"id":"input","kind":"array","role":"source"} ],
  "relations": [ {"from":"input","to":"left_half","type":"split_into"} ],
  "layout_intent": { "composition_recipe": "source_to_transformation_to_output",
                     "reading_direction": "top_to_bottom" },
  "invariants": [ "all input values appear exactly once", "merged stays sorted as it grows" ] }
```
```json
// per-step delta (derived from consecutive resolved states)
{ "active_entities": ["left_half","right_half"],
  "compared_entities": ["left_half[0]","right_half[0]"],
  "changed_entities": ["merged"],
  "pointer_updates": { "left_index": 1, "right_index": 0 },
  "emphasis": { "selected": ["left_half[0]"], "destination": ["merged[0]"] } }
```

**Layered assets (keep the annotation layer independent).** A stored visual is **not one flat image** —
it is composed layers, so future interactivity does not require regenerating pixels:
```text
Base image          — the canonical structural render (the expensive artifact)
  + Annotation layer — highlights, arrows, labels, overlays, dimming, callouts (cheap, per step)
  + Animation layer  — (future) transitions between deltas
  + Interaction layer— (future) click-to-explain regions, hotspots
```
Each layer references the base image's **stable entity IDs** (§10). A per-step annotation is a separate,
budgeted layer over the same base image — never a new base render. This is what makes "annotate"
adaptation (§11) free and makes the future-compatibility roadmap (§16) additive.

**Stable identifiers (required).** Every entity and relationship has an **immutable semantic ID** that
**persists across all steps**; deltas, annotations, and future layers refer only to existing IDs or an
explicit `create` op; a deleted/hidden entity **retains its ID** for continuity. Without stable IDs a
pointer highlight, callout, graph node, code block, or recursion frame cannot be tracked across steps.

---

## 9. Semantic state + structural representation (the keystone, and storing it)

The visual subsystem **consumes** the per-step semantic state owned by the cost spec (§7): a compact,
typed, renderer-agnostic `state_delta` → derived `resolved_state_after`. The state's type structure
**plus topic context** implies the visual shape (§5) — this is the text↔visual bridge, and it is why
producing the state now makes "turn on visuals" wiring rather than a rewrite.

**Store the structural representation, not only the image (future-proofing).** Every stored asset (§12)
keeps the **semantic scene** it was generated from, not just the pixels:
```json
{ "semantic_scene": { "entities": ["..."], "relations": ["..."] },
  "entity_graph": "<nodes + typed edges with stable IDs>",
  "shape_graph": "<the topological skeleton the shape description asserts>",
  "resolved_state_ref": "<link to the example's state chain>" }
```
Why: if a future image model improves dramatically, **every visual can be regenerated from its semantic
structure** — no need to recreate lessons or re-derive state. The image becomes a *rendering* of a stored
structure, and the structure is the durable asset.

---

## 10. Visual contract + image acceptance validation

### 10.1 The contract (four levels)

The machine-checkable definition of a correct visual:
- **Semantic** — required objects/relationships present (deterministic, build now).
- **Topological** — structure obeys domain rules: trees valid, linked-list `next` valid, graph edges
  match input, no duplicate/missing nodes (deterministic, build now).
- **Geometric** — readable: no overlap/clipping, spacing, contrast, stable placement across steps
  (deterministic, build with the renderer).
- **Pedagogical** — the visual supports the card's claim (elimination visibly obvious, both compared
  objects emphasized, return destination visible). This is the **rendered audit's** job — later.

### 10.2 Acceptance validation (a generated image must EARN its way into the DB)

Generation is not trusted on its own — every generated/regenerated image passes validation before it can
be stored or shown. **The contract validated here is the blueprint's `validation_rules` (§17):** the
blueprint *owns* what "correct" means for its concept; §10 is the *executor* of that contract, not a
separate authority.
```text
generate image
   ↓
validate against the blueprint's validation_rules (§17) = §10.1 levels + §4 shape + §12 metadata
   ↓
pass → store as a versioned asset (§12)        fail → regenerate WITH the validator's feedback
                                                       (bounded retries; if still failing →
                                                        deterministic-renderer fallback, then
                                                        text-first — the §30 fallback ladder)
```
The validator answers concrete questions (each a recorded `validation_reason`, §12):
- Does it actually **depict the intended concept** (not a near-miss of a different one)?
- Does it satisfy the **expected structural shape** (§4)?
- Are all **`required_elements` present** and all **`forbidden_elements` absent** (§12)?
- Is it **clear enough to teach from** (readable, focus legible, not cluttered)?

### 10.3 Structural correctness vs. visual style (two independent goals)

- **Structural correctness (MANDATORY — gates storage):** the BST satisfies BST properties; merge sort
  shows recursive split + merge; a graph actually has nodes and edges; required present, forbidden
  absent. A structural failure means **regenerate** — never store. This is the §10.1 semantic/topological
  contract; for pure structural shapes it is checkable deterministically.
- **Visual style (COSMETIC — never gates correctness):** color palette, typography, shadows, branding,
  minimalism. Style may inform a `quality_score` but a plain-yet-correct image is **acceptable**; a
  beautiful-but-wrong image is **rejected**. Conceptual correctness always outranks attractiveness.

### 10.4 What runs now vs later

For **exact-structural** concepts the deterministic semantic/topological validators check the underlying
scene the image was generated from (and when the deterministic renderer is on, the image is *derived* and
correct by construction). The **vision/pixel** half of validation (does the rendered image actually look
right) is the deferred half. The **acceptance gate is provisioned now**; the vision half runs later
(§14).

---

## 11. Adaptation — annotate vs. reference-regenerate

A card adapts the topic canonical (§3) by **one of two paths, chosen deterministically from whether the
underlying structure changed** (the §8 base-scene/delta distinction, applied to images):

- **Annotate (structure unchanged)** → the layout stays identical; apply a **lightweight annotation
  layer** (§8) — highlights, arrows, labels, overlays, dimming, callouts — over the same base image. **No
  regeneration.** Cheapest and most consistent.
- **Reference-regenerate (structure changed significantly)** → a different tree shape, graph topology, or
  algorithm state needs a new image; generate it **using the previous image as a structural reference**
  so appearance and layout stay as consistent as possible.

The decision "did the structure change enough to need a new image?" is made deterministically from the
**resolved-state delta** (cost spec §7) + archetype/scene change (§8), not by the model guessing. Annotate
is preferred; reference-regenerate only at a meaningful structural transition. This minimizes
regeneration while preserving learner continuity. **Either path must preserve the concept's invariants
(§29)** — an adaptation that would break one (move a stable node, cross edges, flip a subtree) is rejected
and redone, so the visual reads as one stable diagram evolving.

---

## 12. Visual Memory Database (retrieve → adapt → generate → validate → store → version → learn)

The Visual Memory DB is a **curated library, not a cache.** A cache stores whatever was last produced;
this DB stores **only validated educational visuals** (§10), keeps **versions** (a better image *promotes*
over an older one without losing history), and **learns from user regenerations**. It is a long-term
knowledge asset.

### 12.1 Retrieval + confidence thresholds (never force an unrelated reference)

On a topic request, search the DB for the closest existing visual by **concept, visual type, concept
family, structural shape, and metadata tags** (conceptual/structural similarity, *not* pixel similarity);
the search returns a **similarity score**. Decide deterministically by threshold:
```text
similarity ≥ ~0.90  → reuse directly (same concept, same shape) — no image call
~0.65–0.90          → adapt: reuse as the structural reference for §11 annotate/reference-regenerate
< ~0.65             → no real match → generate a NEW canonical base visual (§11/§10)
```
Thresholds are tunable config, not model judgment. A weak match is **not** adapted — forcing a 45%-similar
image onto a different concept produces a wrong visual; below the floor, generate fresh. (Adaptation
inherits the reference's *shape*, so adapting across concepts that don't share a shape is exactly the
failure to avoid.)

### 12.2 Generation metadata vs. retrieval metadata (they evolve for different reasons)

Split metadata into two groups so each can change independently:

**Generation metadata (steers the image model):**
```json
{ "visual_type": "graph",
  "shape_description": "rooted binary tree; left subtree < node < right subtree",
  "required_elements": ["root node", "child edges", "node values", "ordered left/right children"],
  "forbidden_elements": ["cycles", "cross edges", "unordered children", "decorative imagery"],
  "editable_regions": ["node fill", "edge highlight", "value labels", "callout layer"] }
```
**Retrieval metadata (indexes + ranks the library):**
```json
{ "concept": "binary_search_tree",
  "concept_family": "rooted_tree",
  "structural_signature": "<hash of visual_type + shape + entity/relation skeleton>",
  "retrieval_tags": ["bst", "tree", "ordered", "search"],
  "difficulty": "intro | standard | advanced",
  "usage_count": 42,
  "quality_score": 0.87 }
```
Both are **derived** from data the pipeline already produces (composite key §5 + intent packet §7 + shape
description §4) — no separate LLM call. Metadata is a **semantic** description so retrieval is by meaning,
not pixels.

### 12.3 The stored asset = a full versioned record (not just pixels)

```json
{
  "concept_id": "merge_sort",
  "version": 3,                         // v1, v2, v3 … — never overwrite; promote the better one
  "status": "active | superseded | reverted | archived",
  "image_ref": "...",
  "layers": { "base": "...", "annotation": ["..."], "animation": null, "interaction": null },  // §8
  "structural_representation": { "semantic_scene": "...", "entity_graph": "...",
                                 "shape_graph": "..." },                                        // §9
  "generation_metadata": { "...": "§12.2" },
  "retrieval_metadata":  { "...": "§12.2" },
  "validation_result": "passed",
  "validation_reason": ["correct recursive structure", "symmetric split tree", "merge phase present",
                        "accepted by validator"],
  "generation_prompt": "...",          // the steering used — reproducibility + debugging
  "adaptation_history": [ { "from_version": 2, "op": "annotate", "reason": "highlight merge step" } ],
  "user_feedback": [ { "action": "regenerated", "reason": "wrong shape" } ]
}
```

### 12.4 Versioning + promotion (improve monotonically, revert safely)

The DB keeps history. A newer, better-performing visual is **promoted to `active`** and the prior becomes
`superseded` — **never overwritten**. If a new generation is *worse*, **revert** by re-promoting the
earlier version. Storing **`validation_reason`** (why an image is good, §10) — not just "passed" —
supports retrieval ranking and debugging a later regression.

### 12.5 Learn from regenerations (the biggest lever)

A user regenerating a visual **is feedback.** Record it against the asset —
`unclear | wrong_shape | wanted_more_detail | incorrect_example | too_much_text | …` — and feed it back
into **retrieval ranking and adaptation choices** (down-rank an asset repeatedly regenerated for
`wrong_shape`; bias future generation away from the cited failure). Over time the library becomes
**self-improving**.

### 12.6 Curation / periodic maintenance (so retrieval quality doesn't degrade)

The DB will accumulate many similar visuals. Run a periodic maintenance pass:
```text
new version created
   ↓ validation passes (§10)
   ↓ compare against existing versions of the same concept (quality_score, validation_reason, feedback)
   ↓ if superior → promote (active); archive the previous
   ↓ if inferior → keep prior active; mark new as superseded
   ↓ deduplicate near-identical assets; prune archived beyond a retention window
```
Without curation, retrieval slowly returns staler/lower-quality matches; with it, the active set stays
the best-known visual per concept.

---

## 13. End-to-end visual lifecycle

```text
topic
  ↓ determine visual type + shape description (§4, deterministic for known families)
  ↓ build concept contract + generation/retrieval metadata (§10/§12.2, derived)
  ↓ RETRIEVE from Visual Memory DB by concept/shape/family (§12.1)
  ↓ confidence?  ≥0.90 reuse · 0.65–0.90 adapt(reference) · <0.65 generate new (§12.1)
  ↓ [generate path] image-gen steered by type + shape + metadata (§1/§4)
  ↓ VALIDATE against concept contract (§10) ──fail──▶ regenerate w/ feedback (bounded) / withhold
  ↓ STORE as versioned, validated, layered, structurally-represented asset (§8/§9/§12.3)
  ↓ VERSION + PROMOTE (curation §12.4/§12.6)
  ↓ REUSE/ADAPT for the remaining cards in the topic — annotate (no regen) or reference-regenerate (§11)
  ↺ user regeneration / usage FEEDS BACK into retrieval + adaptation (§12.5)
```
The unit is the **topic** (one canonical validated visual, reused across its cards); the DB turns
per-topic work into a growing, curated, self-improving library.

---

## 14. Provisioned now vs. deferred (the "ready but off" checklist)

**Build NOW (cheap, deterministic, no image model):**
- The **schemas as code types**: semantic-scene/primitive grammar, base-scene + delta, layered-asset
  record (§8), structural representation (§9), intent packet (§7), visual contract (§10), the
  full-asset/version/feedback record + generation/retrieval metadata split (§12).
- The **composite-key → visual-type/archetype** inference (§5/§4; pure, unit-tested).
- The **base-scene + delta derivation** as pure functions over resolved state (§8; no render).
- The **semantic + topological validators** = the **deterministic half of acceptance validation** (§10).
- **Shape descriptions** per concept family (§4) + **metadata derivation** (§12.2).
- The **Visual Blueprint schema + deterministic derivation** (§17) and the **Visual Ontology** category
  set + concept→ontology map (§18) — the single-source-of-truth steering artifacts.
- The **concept-asset vs. lesson-asset** two-layer schema (§19); the **concept-aware retrieval key** +
  ranking (§21); the **visual-confidence** scoring function (deterministic half, §20).
- The **Visual Memory DB schema + retrieval keys + similarity-threshold config** (§12) — **empty / not
  populated**.
- The **visual benchmark** concept list (**by category**) + metric definitions + harness interface (§23;
  deterministic metrics).
- The **Reference Pack** schema + purpose→entry selection rule (§24); the **Failure Memory** schema +
  negative-constraint injection rule (§25); the **`style_version` / `concept_version` two-axis** field on
  the asset (§26); the **concept-coverage** metric over the blueprint/DB (§27). All schema/derivation,
  no image model.
- The **complexity-level** enum + `card_role+difficulty → level` map (§28); the per-concept **invariants**
  list + deterministic invariant checks (§29); the **deterministic-fallback ladder** + `visual_type →
  renderer-available?` map (§30); the **observability** metric definitions + aggregation queries (§31).
- The **Canonical Concept schema** + concept→per-purpose-blueprint derivation/inheritance (§32); the
  **rendering-pipeline stage interfaces** + the deterministic stages ①②④⑥ (§33); the
  **declarative-blueprint lint** that rejects procedural fields (§34). Schema/interfaces only, no image
  model.

**Deferred behind the flag (the planned primary path — not a vague "later"):**
- Any **image generation / image-model call**; populating the DB with real images; the
  retrieve→adapt→store loop *running*.
- The **annotation/animation/interaction layer renderers** and the reference-regeneration call (§8/§11);
  the layout engines / pixel rendering (define the interface; stub it).
- The **vision/pixel half of acceptance validation** (§10.4).
- The **regeneration-feedback learning loop**, the feedback-weighted half of **confidence** (§20),
  version promotion/revert, and periodic **curation** *running* (schema exists §12/§20/§22; the loops run
  later).
- **Running the benchmark** (§23) end-to-end and the **blueprint-driven image generation** (§17) — the
  harness + blueprint schema exist now; regeneration runs when image-gen is on.
- **Populating reference packs** with real assets (§24), the **failure-memory negative-constraint loop**
  *firing* during generation (§25), and the **platform restyle pipeline** that bumps `style_version`
  (§26) — schemas exist now; these run when image-gen is on.
- The novelty budget.

**The switch:** `AZALEA_VISUALS_ENABLED` (default `false`). When `false`: schemas + derived scene/delta +
metadata + retrieval keys + deterministic validators run (cheap, no model, no render). When `true`: the
image-generation + memory-DB pipeline and/or the deterministic renderer consume the already-present data.

---

## 15. Cost (the visual portion)

- The **deterministic substrate** — semantic state, scene/delta, metadata, shape descriptions, retrieval
  keys, deterministic validators — adds **zero** model calls (all derived).
- **Image generation** adds an **image-model call only for a new canonical base visual** (§11), plus
  **bounded regeneration retries** when acceptance validation rejects it (§10).
- **Per-card reuse** via **annotation** (§11) and a **retrieval hit** (≥0.90, §12.1) add **zero** image
  calls; reference-regeneration runs only at a real structural transition.
- Steady state amortizes toward **≈one image generation per topic** (less as the DB fills and retrieval
  hit-rate climbs), **not one per card**. While `AZALEA_VISUALS_ENABLED=false`, visual cost is **zero**.

---

## 16. Future compatibility (intentionally supported, additive)

This architecture intentionally supports future additions **without changing lesson generation**, because
visuals are layered (§8), structurally represented (§9), validated (§10), and stored as versioned assets
(§12):
- **Interactive visuals** — hotspots over stable entity IDs (interaction layer §8).
- **Click-to-explain regions** — map a region's entity ID back to the card's `goal`/`how`.
- **Visual quizzes** — hide/scramble a labeled entity; the contract (§10) supplies the correct answer.
- **Animated transitions** — render the per-step deltas (§8) as an animation layer.
- **Adaptive highlighting** — the annotation layer keyed by learner state.
- **Image replacement as models improve** — regenerate from the stored **structural representation** (§9)
  and re-validate (§10); promote the better version (§12.4). No lesson rework.

These are additive because each new capability consumes data the foundation already produces.

---

## 17. Visual Blueprint — a per-purpose rendering definition (under the Canonical Concept §32)

A **Visual Blueprint is the object the generator consumes** — but a concept has **one blueprint per
lesson purpose** (intro / worked-example / implementation / review), each **derived from the single
Canonical Concept (§32)** that holds the concept's durable, purpose-independent truth. The canonical
concept answers *what merge sort is*; each blueprint answers *how to render it for this purpose*. A
blueprint defines four things:
1. **what it teaches vs. how it's drawn** — `educational_intent` (the durable learning goal, **inherited
   from the Canonical Concept §32**) kept **separate** from `rendering_intent` (the chosen visualization,
   **blueprint-specific**), so a visualization can be swapped without rewriting the educational goal;
2. **what the visual should contain** — visual type, shape, required/forbidden elements, the concept's
   ontology and **`invariants`** (§29) — all **inherited from the Canonical Concept** (the same across
   every purpose);
3. **how it should be generated for THIS purpose** — composition recipe, generation hints, reference
   pack, and the chosen **`complexity_level`** (§28) the purpose demands (**blueprint-specific**);
4. **how it should be validated** — its `validation_rules` (the §10 acceptance contract, inherited from
   the concept and optionally tightened per purpose).

Everything below the blueprint is a **projection of it**: the §10 acceptance validation *executes the
blueprint's `validation_rules`*; the §12.2 metadata is *derived from* the blueprint; the §24 reference
pack and §16 teaching styles *hang off* it. The generator consumes **one object** (the purpose's
blueprint), never a re-assembly of scattered fields. **Keep blueprints declarative** (§34): they describe
*what* must exist, never procedural `if concept == …` logic.

**How it's built.** At a concept's first sight the backend **derives** the blueprint (deterministically
for known families; one cached LLM pick only for the novel tail). It is then the single input to
generation, validation, and retrieval-key/metadata derivation.

**Relationship to existing fields (no new machinery — the blueprint *owns* what already existed,
scattered):** `visual_type` (§4), `shape_description` (§4), `required/forbidden_elements` (§12.2),
`composition_recipe` (§6), `ontology_tags` (§18), the **`reference_pack`** (§24, replacing the flat
`reference_versions` list), the **`validation_rules`** (§10, previously implicit), and `teaching_styles`
(§16) all live **on the blueprint**; §12.2 generation/retrieval metadata is **derived from it**.
```json
{
  "concept_id": "merge_sort",
  "purpose": "worked_example",            // intro | worked_example | implementation | review (§32)
  "canonical_ref": "concept:merge_sort",  // inherits the fields below from the Canonical Concept (§32)

  // ── INHERITED from the Canonical Concept (§32) — same across every purpose ──
  "educational_intent": "teach divide-and-conquer: split into like subproblems, solve, recombine",
  "ontology_tags": ["recursive", "linear", "temporal"],           // §18
  "required_elements": ["arrays", "split arrows", "merge arrows"],
  "forbidden_elements": ["flowcharts", "node-link graphs"],
  "invariants": ["split always top→bottom", "merge always bottom→top",                 // §29
                 "every input value appears exactly once"],

  // ── BLUEPRINT-SPECIFIC (this purpose only) ──
  "rendering_intent": {                                           // HOW it's drawn for this purpose
    "visual_type": "recursive_split_tree",                        // §4 / §6
    "shape_description": "recursive top-down split into halves, then bottom-up merge of sorted halves",
    "composition_recipe": "top_down_split + bottom_up_merge",     // §6
    "generation_hints": ["symmetric layout", "equal spacing"]
  },
  "complexity_level": "3_detailed",                               // §28 — picked from the concept's ladder
  "validation_rules": {                                          // §10 — inherited, may tighten per purpose
    "must_contain": ["two source arrays", "one merged output", "split step", "merge step"],
    "must_not_contain": ["flowchart arrows", "decorative imagery"],
    "shape_assertions": ["binary recursive split", "merge combines two sorted runs into one"]
  },
  "reference_pack": { "...": "see §24" }                          // §24 (replaces reference_versions)
}
```
**Educational vs. rendering intent (§3 note).** `educational_intent` is the durable learning goal;
`rendering_intent` (visual type + shape + composition + hints) is one *chosen visualization* of it. Keep
them separate so you can A/B a different visualization for the same goal — or let an improved image model
re-render the structure (§9) — **without** touching the educational definition.
**Provision now:** the **Canonical Concept schema (§32)** + the per-purpose blueprint **schema +
deterministic derivation** (inheriting concept fields; adding `validation_rules` and the §24
`reference_pack` skeleton). Blueprint-driven image generation runs later behind the flag (§14). Because
the canonical concept + its per-purpose blueprints are the knowledge root, future capabilities
(interactive hotspots, animation, multiple teaching styles, §16) attach there — not to the rest of the
pipeline.

---

## 18. Visual Ontology — a semantic layer above visual types

`visual_type` (§4) says *which shape* (tree, grid, sequence). The **ontology** says *what kind of
thinking* the concept is — a deeper, reusable semantic layer that retrieval and generation share. Closed,
composable category set (a concept maps to ≥1):
```text
hierarchy · network · linear · circular · spatial · recursive · temporal · comparative · functional · probabilistic
```
Examples: BST → `hierarchy + recursive`; merge sort → `recursive + linear + temporal`; DFS →
`network + recursive + temporal`; supply/demand → `comparative + functional`.

**How we use it (relationship to visual types).** Ontology is **upstream** of visual type: the ontology
tags *constrain/suggest* the visual type + composition (a `hierarchy` concept is never drawn as a flat
sequence), and they are a **retrieval key (§21) richer than concept-name or visual-type matching** (two
concepts sharing `recursive + temporal` can share reference assets even if their names differ). Ontology
tags live on the blueprint (§17) and in retrieval metadata (§12.2). Closed vocabulary → deterministic and
unit-testable; a novel concept gets one cached LLM tag assignment. **Provision now:** the category set +
the concept→ontology map.

---

## 19. Concept assets vs. lesson assets (two ownership layers)

§3 said "the topic owns the canonical visual." Refine that into **two layers**, because a concept's
visualization and a particular lesson's use of it change at different rates:
```text
Concept Asset (rarely changes)            Lesson Asset (generated per lesson, often)
  merge_sort canonical visual      ──▶      Merge Sort: Introduction    (references + adapts §11)
  + blueprint (§17) + version history       Merge Sort: Worked Example  (references + adapts §11)
  + structural representation (§9)          Merge Sort: Implementation  (references + adapts §11)
```
- **Concept asset** — the durable, validated canonical visual for a concept + its **Canonical Concept
  definition (§32)** + per-purpose blueprints + structural representation + version history (§12/§22).
  Owned by the **concept**, shared across **every** lesson that teaches it.
- **Lesson asset** — a lesson-/card-specific instance **derived** from the concept asset via annotate or
  reference-regenerate (§11). Cheap, disposable, regenerable.

**How we use it (relationship to §3).** §3's "topic owns the canonical" becomes "the **concept** owns the
canonical; the **topic/lesson references** it." This cuts regeneration further — two different lessons
(intro vs. implementation) reuse **one** concept asset instead of each generating a canonical. Retrieval
(§12.1/§21) hits the **concept** layer; adaptation (§11) produces the **lesson** layer. **Provision now:**
the two-layer schema; the sharing is exercised when generation is on.

---

## 20. Visual confidence (validation becomes a score, not just pass/fail)

Acceptance validation (§10) gates pass/fail. Add a **confidence score** (0–1) so the system can rank
*among passing* visuals. Confidence is a deterministic blend of contract results already produced — **not
a new model call**:
```text
confidence = f(structural_pass, required/forbidden coverage, shape-match strength,
               geometric clarity, historical user-feedback signal)        // each from §10 / §12.5
```
**How we use it (relationship to existing fields).** Confidence **subsumes** the loose `quality_score`
(§12.2) and pairs with `validation_reason` (§12.3). Two consumers change:
- **Retrieval (§12.1/§21)** prefers the **highest-confidence** matching asset — **not merely the latest
  version**.
- **Promotion (§12.4/§22)** defines "better" as **higher confidence** (feedback-weighted), making
  promote/revert objective.

Pass/fail still gates **storage** (a structural fail is never stored); confidence ranks **what passed**.
**Provision now:** the scoring function (deterministic half); the feedback-weighted term matures with
§12.5.

---

## 21. Concept-aware retrieval (retrieve by concept + purpose + audience + visual type)

§12.1 retrieves by concept/shape/family similarity. Make the retrieval **key** explicitly
multi-dimensional so retrieval is *intelligent*, not name-matching:
```text
retrieval key = concept + purpose(card_role) + audience(difficulty) + visual_type + ontology_tags(§18)
```
e.g. `merge_sort · worked_example · beginner · split_tree · {recursive,temporal}`.

**How we use it (relationship to existing fields).** These dimensions **already exist** as retrieval
metadata (`concept_family`, `difficulty`, `retrieval_tags`, `card_role`, ontology) — this section
promotes them from *stored* fields to *ranked retrieval-key* dimensions, with **confidence (§20)** as the
tie-break. The same beginner-worked-example asset is preferred for a beginner worked-example card; an
advanced implementation card retrieves a different, better-matching asset of the **same** concept.
**Provision now:** the composite retrieval key + ranking; live retrieval runs once the DB is populated.

---

## 22. Concept-level evolution (the concept owns the history, not the image)

§12.4 versions images. Reframe ownership: the **concept** owns an **evolution timeline**; each version is
a point on it:
```text
merge_sort
  → v1 canonical → v2 improved spacing → v3 improved merge visualization
  → v5 better annotations → v8 better example
```
**How we use it (relationship to §12.4).** Mechanically this is the existing `concept_id`-keyed version
history — the reframing is that the **concept asset (§19)** owns the timeline (not a per-lesson image),
`active` = the current best (highest **confidence**, §20), and `validation_reason` + feedback annotate
each step so evolution is explainable and revertible. This is what makes "the library improves over time"
a property of **concepts**, not scattered images.

---

## 23. Visual benchmark (an objective measure that the system improved)

Promote the deferred "benchmark suite" (§14) to a defined harness — the objective way to know an
architecture change helped, instead of ad-hoc spot checks. A fixed benchmark set of **~100 representative
concepts**, **grouped into categories** so a regression is immediately localizable to a domain rather
than hidden in an aggregate:
```text
Trees       : BST, AVL, heap, trie, segment tree
Graphs      : DFS, BFS, Dijkstra, topological sort, MST
Arrays      : binary search, merge sort, quicksort, two-pointer, sliding window
Recursion   : factorial, Fibonacci, tower of Hanoi, backtracking
Dynamic Prog: knapsack, LCS, edit distance, DP grid
Math        : functions/curves, vectors, probability trees, set operations
Circuits    : logic gates, adders, flip-flops
Physics     : forces, circuits, wave/field diagrams
Operating Sys: CPU pipeline, cache, paging, scheduling
Networking  : packet flow, OSI layers, routing
```
On every architecture change, regenerate all benchmark concepts and compare against the prior run —
**per category and in aggregate**:
```text
validation pass rate · regeneration (retry) rate · retrieval hit rate · human/teaching score · confidence distribution(§20)
```
Per-category reporting tells you *which* domain regressed (e.g. "Graphs validation dropped 12%") so a
change can be accepted, reverted, or scoped to the affected category.
**How we use it.** The benchmark consumes each concept's **blueprint (§17)**, runs the full lifecycle
(§13), and reports the metrics above versus the previous run — **gating whether an architecture change
ships**. **Provision now:** the benchmark **concept list + metric definitions + harness interface**
(deterministic metrics build now); the generation half runs when image-gen is on (§14). This replaces
§14's vague "benchmark suite" deferral with a first-class, defined artifact.

---

## 24. Reference Packs (a purpose-tagged set, not a flat version list)

The blueprint's references (§17) are a **Reference Pack** — a small, **named, purpose-tagged** set the
generator chooses from per lesson — not a flat `["v3","v5","v8"]` list. The generator picks the pack
entry that fits the **lesson purpose** (which it already knows from the concept-aware retrieval key §21):
```json
"reference_pack": {
  "canonical":        "asset:merge_sort@v8",     // the active best (§22)
  "alternative_layout":"asset:merge_sort@v5",
  "textbook":         "asset:merge_sort@v3",     // formal / dense
  "minimal":          "asset:merge_sort_min@v2", // fewest elements, intro use
  "detailed":         "asset:merge_sort_det@v4", // every pointer/step shown
  "step_by_step":     "asset:merge_sort_steps@v6",// worked-example friendly
  "technical":        "asset:merge_sort_impl@v7" // implementation/code-adjacent
}
```
**How we use it.** A worked-example card steers from `step_by_step`; an implementation card from
`technical`; an intro from `minimal`. Each entry **points at a stored asset version** (§12/§22) — so the
pack is a *curated index over versions*, not a parallel store. This is more flexible than one flat list
(the same concept can present differently per purpose without a new generation) and it is the §17
field `reference_pack` replacing `reference_versions`. **Provision now:** the pack schema + the
purpose→entry selection rule; populating real reference assets happens when generation is on.

---

## 25. Failure Memory (learn what NOT to produce)

§12.5 records user *regenerations*; **Failure Memory** records **rejected generations** — images the
acceptance validator (§10) threw out — so the system learns its own anti-patterns. Stored per concept on
the blueprint/asset:
```json
"failure_memory": [
  { "rejected_at": "v-attempt-3", "reason": "looked_like_flowchart",
    "violated_rule": "must_not_contain: flowchart arrows", "avoid": "flowchart layout / sequential boxes" },
  { "rejected_at": "v-attempt-5", "reason": "unordered_children",
    "violated_rule": "shape_assertions: ordered left/right", "avoid": "random child placement" }
]
```
**How we use it.** On the next generation for that concept, the recorded `avoid` items are **injected as
explicit negative constraints** into the steering (alongside the blueprint's `forbidden_elements`), so a
repeated failure mode is pre-empted rather than re-discovered. Failure Memory is the **negative**
counterpart to the reference pack's positive examples, and it feeds the §23 benchmark's
`regeneration rate`. **Provision now:** the schema + the negative-constraint injection rule (the loop runs
when generation is on, §14).

---

## 26. Visual style version vs. concept version (guard against visual drift)

Over years a concept's *appearance* may drift (flat diagrams → gradients → 3-D) while its *educational
structure* is unchanged. Keep **two orthogonal version axes** so a platform-wide restyle never risks the
pedagogy:
```text
concept_version  — the EDUCATIONAL structure/content of the visual (§12.4/§22): split tree, merge step…
style_version    — the VISUAL treatment only: palette, typography, stroke, depth, branding
```
**How we use it (relationship to §12.4/§22).** §22's concept evolution moves `concept_version` (and is
gated by structural validation + confidence). A **style refresh** bumps `style_version` **platform-wide**
without touching `concept_version` — re-render existing concept assets in the new style, re-validate
**structure** (§10 must still pass; style is cosmetic per §10.3), and promote. The stored asset (§12.3)
carries both:
```json
{ "concept_id": "merge_sort", "concept_version": 8, "style_version": 3, "status": "active" }
```
This lets the platform look modern in 2030 without regenerating educational structure or reworking
lessons. **Provision now:** the two-axis field on the asset; the restyle pipeline runs later.

---

## 27. Concept coverage (measure breadth, not just quality)

The benchmark (§23) measures **quality**; coverage measures **breadth** — *which* concepts the library can
actually visualize well, by domain:
```text
Computer Science   92%
Mathematics        68%
Electrical Eng.    41%
Economics          15%
```
**How we use it.** Coverage = (concepts with a **validated blueprint + at least one passing concept asset**)
÷ (concepts in the domain's curriculum). It is derived from the blueprint library + DB (§12/§17), needs
no generation, and tells you **where to invest** next (author blueprints / seed reference assets for the
weak domains) rather than over-polishing already-strong ones. Pair it with §23: benchmark says *how good*
the visuals are; coverage says *how much* of the curriculum is covered at all. **Provision now:** the
coverage metric over the blueprint/DB schema (deterministic; runs even with visuals off).

---

## 28. Visual complexity levels (how much to show, per lesson role)

The same concept needs **different amounts of detail** depending on where it appears — and the generator
should not have to *infer* how much belongs in the image. So complexity is a **first-class blueprint
field** (§17), a small ordered ladder:
```text
Level 1  minimal     — the core move only            (intro: merge sort = one split + one merge)
Level 2  educational — the full structure, no values (recursive breakdown)
Level 3  detailed    — structure + concrete values   (worked example: actual array values + pointers)
Level 4  technical   — structure + annotations        (advanced: recursion tree + complexity)
```
**How we use it (relationship to reference packs + teaching styles).** This is the *amount* of detail;
the **reference pack (§24)** is the *style/purpose* of the reference and **teaching styles (§16)** are the
*audience framing*. The generator maps `card_role + difficulty` (the §21 retrieval key) → a complexity
level deterministically (intro→L1, standard explanation→L2, worked example→L3, advanced/implementation→L4),
then steers the image to that level. A higher level is a **superset** of the lower (same invariants §29,
more detail), so levels stay mutually consistent and one base scene (§8) can be progressively revealed.
**Provision now:** the level enum on the blueprint + the role→level map.

---

## 29. Visual invariants (what must stay true across every adaptation)

`validation_rules` (§17) check a *single* generated image; **invariants** are the stronger, per-concept
properties that must hold across **every** step, adaptation, and version — they are what keep annotate /
reference-regenerate (§11) and complexity levels (§28) consistent:
```text
BST        : left subtree always on the left · right subtree always on the right · root always on top
merge sort : split always top→bottom · merge always bottom→top · each value appears exactly once
graphs     : declared edges never dropped · node positions stable across steps · no spurious crossings
```
**How we use it.** Invariants live on the blueprint (§17) and are enforced at **two** points: acceptance
validation (§10) checks them on each generated image, and **adaptation (§11) must preserve them** — an
annotate/reference-regenerate that would violate an invariant (e.g. a re-layout that moves a node or
crosses edges unnecessarily) is rejected and redone. This is what makes a multi-step or multi-card visual
feel like *one stable diagram evolving*, not a series of unrelated images. **Provision now:** the
invariant list per concept family + the deterministic invariant checks (they extend §10.1 topological).

---

## 30. Deterministic fallback (the learner never ends up with no visual)

Image generation can fail repeatedly (validation rejects every retry, the model is unavailable, the
concept is hard to draw). The lesson must **never** show "no visual" when a deterministic alternative
exists:
```text
generate (steered by blueprint §17)
   ↓ reject / fail
retry with failure-memory constraints (§25)   ── bounded (e.g. ≤3) ──┐
   ↓ still failing                                                    │
DETERMINISTIC RENDERER for the visual_type (§1, §6 layout engines) ◀──┘   ← exact-structural shapes
   ↓ unavailable (novel/illustrative shape with no deterministic renderer)
TEXT-FIRST with retained state + intent packet (§5 visual_status: unsupported/withheld) — lesson continues
```
**How we use it (relationship to §1/§5/§10).** §1 already names deterministic structural rendering as the
*more reliable* path for pure structural shapes; this section makes it the **explicit fallback rung**:
for any concept whose `visual_type` has a deterministic layout engine (sequence/graph/grid/…, §6), a
repeated image-gen failure **falls back to rendering the visual directly from semantic state** — which is
correct by construction — rather than withholding. Only genuinely non-structural shapes with no
deterministic renderer fall through to text-first. The learner always gets *a* correct visual or a clean
text-first card, never a blank. **Provision now:** the fallback ladder + the
`visual_type → deterministic-renderer-available?` map (the renderers themselves are §14-deferred, but the
decision and text-first path exist now).

---

## 31. Observability (operational metrics — the data already exists)

The subsystem already produces the signals; expose them as defined operational metrics so the system can
be improved with evidence, not intuition. All are **derived** from the asset records (§12.3), validation
(§10), confidence (§20), feedback (§12.5/§25), and benchmark (§23):
```text
most-regenerated concepts          ← user_feedback + failure_memory  (where the model struggles)
highest / lowest confidence        ← confidence (§20)                (what to trust / what to fix)
average retries per generation     ← failure_memory (§25)            (generation difficulty)
database hit rate                  ← retrieval (§12.1)               (how often we avoid generating)
reference-pack entry usage         ← reference_pack selection (§24)  (which purposes are exercised)
validation failures by rule        ← validation_rules / invariants (§10/§29)  (which rules trip most)
coverage by domain                 ← concept coverage (§27)          (where the library is thin)
```
**How we use it.** These power dashboards/alerts that guide where to invest (author blueprints for
low-coverage domains, fix the rules that trip most, restyle low-confidence concepts). They are
**operational, not new architecture** — every field already exists. **Provision now:** the metric
definitions + aggregation queries over the existing schema (they compute even with visuals off, returning
zeros until the DB is populated).

---

## 32. Canonical Concept Library (the object above the Blueprint)

There is **one object above the blueprint**: the **Canonical Concept** — the durable, purpose-independent
definition of what a concept *is*. The blueprint shouldn't have to re-define "what merge sort is" for each
lesson type; it should *render* a shared canonical truth. So:
```text
Concept
   ▼
Canonical Concept (one per concept, §32)        ── the educational truth
   • canonical_representation : the agreed structure to depict (recursive split + merge of arrays)
   • canonical_terminology    : the names to use (left/right half, merge, pivot, …)
   • canonical_structure      : entities + relationships (the §9 shape_graph at concept level)
   • invariants               : concept-wide (§29)
   • educational_intent + ontology (§18)
   ▼
Visual Blueprints (per purpose, §17)            ── renderings of the canonical truth
   intro · worked_example · implementation · review · quiz
   ▼
Generation (the §33 pipeline)
```
**Why split it from the blueprint.** Implementation lessons, worked examples, reviews, and quizzes will
want *slightly different* visuals of the **same** concept (an intro shows the shape; a worked example
shows values; an implementation is code-adjacent; a review is compressed). Bundling all purposes in one
blueprint forces compromise; separating the **canonical truth** (one) from **per-purpose renderings**
(many) lets each purpose specialize **without** duplicating — or diverging on — what the concept *is*.

**Relationship to existing structure (no new machinery, a reparenting):** fields that are
purpose-independent (`educational_intent`, `invariants` §29, `ontology_tags` §18, canonical
structure/terminology, the §28 complexity ladder definition) move **up** to the Canonical Concept; each
blueprint (§17) **inherits** them and adds only its purpose's `rendering_intent`, chosen
`complexity_level`, `reference_pack` (§24), and any tightened `validation_rules`. This is the natural
completion of educational-vs-rendering intent (§17) and concept-vs-lesson assets (§19): the **concept
asset (§19) = the Canonical Concept**; a **lesson asset** is produced by a purpose blueprint. **Provision
now:** the Canonical Concept schema + the concept→blueprint derivation (deterministic; one concept may
start with a single `worked_example` blueprint and grow purposes lazily).

---

## 33. The rendering pipeline (explicit, independently replaceable stages)

"Generation" is **not one box** — it is an ordered pipeline of stages, each with a typed input/output so
any stage can be swapped (a new image model, a new prompt assembler, a new validator) **without touching
the others**:
```text
Blueprint (§17)
   ▼  ① reference selection     — pick the reference-pack entry for this purpose (§24) + failure memory (§25)
   ▼  ② prompt assembly         — compose steering from the blueprint (declarative §34) → generator input
   ▼  ③ image generation        — the image model (or deterministic renderer fallback §30)
   ▼  ④ validation              — execute the blueprint's validation_rules + invariants (§10/§29) → confidence (§20)
   ▼  ⑤ adaptation              — annotate / reference-regenerate for the card (§11)
   ▼  ⑥ storage                 — versioned, layered, structurally-represented asset (§12.3) → Memory layer
```
**Why explicit.** Each stage is a **replaceable component** behind a stable interface: swapping the image
model (③) leaves prompt assembly (②) and validation (④) untouched; improving validation (④) doesn't
touch generation. This is what lets the system evolve (better models, better validators) without
rewrites, and it is where the §31 observability metrics attach (retries at ③, failures-by-rule at ④, hit
rate before ① via retrieval §12.1). **Provision now:** the stage interfaces + ①②④⑥ deterministic parts
(selection, declarative prompt assembly, validation, storage schema); ③ generation and ⑤ image-adaptation
are the §14-deferred half.

---

## 34. Keep blueprints declarative (an implementation rule, not a component)

Blueprints (and canonical concepts) **describe what must exist; they never contain procedural logic.**
```yaml
# WRONG — procedural, becomes unmaintainable as the library grows
if concept == "merge_sort": use split_tree; if intro: hide values

# RIGHT — declarative; the generator decides HOW to realize it
visual_type:        recursive_split_tree
shape_description:  recursive divide into equal halves, then merge
required_elements:  [arrays, split arrows, merge arrows]
complexity_level:   3_detailed
```
The blueprint says **what** the visual is; the **generator/pipeline (§33) decides how** to create it.
**No `if concept == …` branches, no per-concept code paths** — a new concept is a **new data file
(canonical concept + blueprints), not new code.** This keeps the library scalable to thousands of
concepts without the codebase growing per concept (the same anti-hardcoding discipline the rest of Azalea
follows). **Provision now (enforced):** a lint/validator that **rejects** a blueprint containing
procedural/conditional fields, so this rule is mechanically guaranteed, not just documented.

---

## 35. Resolved decisions

- **Image generation is primary, but steered + gated** (§1/§4/§10): visual type + shape description +
  metadata steer; acceptance validation gates. Deterministic structural rendering is a complementary
  exact option and the deterministic correctness gate.
- **Topic references the canonical; the *concept* owns it** (§3 refined by §19): **concept asset**
  (durable canonical + blueprint + structural representation + history) vs. **lesson asset** (per-card
  derived instance) — two lessons of one concept reuse one concept asset.
- **Annotate vs. reference-regenerate** chosen deterministically from the state delta + scene change
  (§11); annotate preferred; layered assets keep annotation independent of the base image (§8).
- **Acceptance validation precedes storage** (§10): structural correctness mandatory and gates storage;
  visual style cosmetic. Deterministic half now, vision half later.
- **Visual Memory DB = curated library, not a cache** (§12): confidence-thresholded retrieval;
  generation vs. retrieval metadata split; **versioned full assets** (image + layers + structural
  representation + validation_reason + prompt + adaptation history + feedback); promote/revert; learn
  from regenerations; periodic curation.
- **Store the structural representation** (§9) so visuals can be regenerated from semantics when image
  models improve.
- **Stable entity IDs** across steps + layers (§8) — required for deltas, annotations, and all future
  layers.
- **Provisioned, not triggered** (§14): build schemas + deterministic validators now; image-gen,
  feedback loop, curation, and the vision-audit half run later behind `AZALEA_VISUALS_ENABLED`.
- **Keystone shared with the cost spec** (§9): the per-step semantic state is produced once (cost spec
  §7) and consumed by text, validators, and visuals.
- **Three layers; two-level Knowledge root** (Architecture overview): **Knowledge** (Canonical Concept →
  per-purpose Blueprints / ontology / shape) → **Generation** (the §33 pipeline + failure memory) →
  **Memory** (the Visual Memory DB). Responsibilities are separated by layer.
- **Canonical Concept = the root object** (§32): one per concept, the durable purpose-independent truth
  (representation / terminology / structure / invariants / relationships / educational intent). The
  blueprint does **not** re-define what a concept *is*.
- **Visual Blueprint = a per-purpose rendering definition** (§17): one blueprint **per lesson purpose**
  (intro / worked-example / implementation / review), **derived from** the Canonical Concept and adding
  only `rendering_intent`, chosen `complexity_level` (§28), `reference_pack` (§24), and `validation_rules`
  (§10). It is the object the generator consumes; metadata (§12.2) is a projection of it.
- **Visual Ontology** (§18): a closed semantic layer (`hierarchy/network/linear/circular/spatial/
  recursive/temporal/comparative/functional/probabilistic`) **upstream of visual type**; constrains the
  visual type and enriches the retrieval key beyond name/type matching.
- **Visual confidence** (§20): validation yields a **0–1 score** (deterministic blend of contract +
  feedback), **subsuming** `quality_score`; retrieval prefers **highest confidence**, not latest version,
  and promotion (§22) defines "better" by confidence. Pass/fail still gates storage.
- **Concept-aware retrieval** (§21): the retrieval key is `concept + purpose(card_role) +
  audience(difficulty) + visual_type + ontology` (fields that already exist, promoted to ranked
  dimensions) with confidence as tie-break.
- **Concept-level evolution** (§22): the **concept** owns the version timeline (§12.4 reframed); `active`
  = highest-confidence version; explainable + revertible.
- **Visual benchmark** (§23): ~100 ontology-spanning concepts, **grouped by category** (trees/graphs/
  arrays/recursion/DP/math/circuits/physics/OS/networking), regenerated per architecture change; compare
  validation/regeneration/retrieval/human/confidence **per category + aggregate** — gates whether a change
  ships and localizes regressions. Replaces §14's vague "benchmark suite."
- **Reference Packs** (§24): the blueprint's references are a **purpose-tagged set** (canonical/textbook/
  minimal/detailed/step_by_step/technical), each an index over a stored version (§22) — the generator
  picks by lesson purpose (§21). Replaces the flat `reference_versions` list.
- **Failure Memory** (§25): store **rejected** generations + reason and inject them as **negative
  constraints** next time — the system learns what *not* to produce (the negative counterpart to
  reference packs).
- **Style vs. concept version** (§26): two **orthogonal** version axes — `concept_version` (educational
  structure, §22) and `style_version` (cosmetic treatment). A platform restyle bumps `style_version`
  only, re-validating structure; guards against multi-year visual drift without reworking pedagogy.
- **Concept coverage** (§27): measure **breadth** (validated-blueprint + passing-asset ÷ curriculum, by
  domain) alongside the benchmark's **quality** — tells you where to invest in new blueprints.
- **Visual complexity levels** (§28): a first-class blueprint ladder (minimal/educational/detailed/
  technical); `card_role + difficulty` → level deterministically; higher levels are supersets of lower.
- **Visual invariants** (§29): per-concept properties that hold across **every** step/adaptation/version;
  enforced by both validation (§10) and adaptation (§11) so a multi-step visual is one stable diagram.
- **Educational vs. rendering intent** (§17): the blueprint separates the durable learning goal from the
  chosen visualization, so a rendering can be swapped/improved without touching the educational definition.
- **Deterministic fallback** (§30): repeated image-gen failure falls back to the deterministic renderer
  (for structural types) then text-first — the learner **never** gets a blank visual.
- **Observability** (§31): defined operational metrics (most-regenerated, confidence, retries, hit rate,
  reference-pack usage, failures-by-rule, coverage) derived from existing data — operational, not new
  architecture.
- **Canonical Concept Library** (§32): one object **above** the blueprint holding the concept's durable
  truth; blueprints become **per-purpose** renderings that inherit it — the natural completion of
  educational-vs-rendering intent (§17) and concept-vs-lesson assets (§19). A reparenting, not new
  machinery.
- **Explicit rendering pipeline** (§33): generation is an ordered, **independently replaceable** stage
  sequence — reference selection → prompt assembly → generation → validation → adaptation → storage — so a
  model/validator swap doesn't ripple.
- **Declarative blueprints** (§34, enforced by lint): blueprints describe **what** must exist, never
  procedural `if concept == …` logic; a new concept is a **new data file, not new code**.

> **Architecture status: FROZEN at v5.** The object model (Canonical Concept → per-purpose Blueprints →
> the §33 Generation pipeline → Memory) and all components are settled. v5 closed the last two structural
> gaps (the concept-above-blueprint layer and the explicit pipeline) and added the declarative-blueprint
> rule; it added **no** new metadata, fields, retrieval dimensions, or version systems. Further changes
> should be **implementation measured against the §23 benchmark, not more spec.** **Next step (do this,
> not another spec pass):** a thin vertical slice — the Canonical Concept + worked-example Blueprint
> schema + deterministic validators/invariants for **one** concept (merge sort or BST), unit-tested,
> behind `AZALEA_VISUALS_ENABLED=false`, then run it through the §23 benchmark harness.

---

### Appendix — section mapping from the cost spec's former §10

| former (cost spec) | now (this doc) |
|---|---|
| §10 intro / scope / central rule | §0–§2 |
| §10.1 composite key + visual_status | §5 |
| §10.2 primitive grammar | §6 |
| §10.3 intent packet | §7 |
| §10.4 base scene + delta | §8 (+ layered assets) |
| §10.5 visual contract | §10.1 |
| §10.6 provisioned vs deferred | §14 |
| §10.7 canonical + adaptation | §3 (ownership) + §11 (adaptation) |
| §10.8 visual types + shape descriptions | §4 |
| §10.9 Visual Memory DB | §12 (+ §12.1 thresholds, §12.6 curation) |
| §10.10 metadata | §12.2 (split gen/retrieval) |
| §10.11 acceptance validation | §10.2–§10.4 |
| §10.12 versioned asset + feedback | §12.3–§12.5 |
| §10.13 lifecycle | §13 |
| *(new in VGA v1)* ownership / structural repr / layers / future-compat / curation | §3 / §9 / §8 / §16 / §12.6 |
| *(new in VGA v2)* blueprint / ontology / concept-vs-lesson assets / confidence / concept-aware retrieval / concept evolution / benchmark | §17 / §18 / §19 / §20 / §21 / §22 / §23 |
| *(new in VGA v3)* three-layer framing + blueprint-as-root (owns validation) / reference packs / failure memory / style-vs-concept version / concept coverage / benchmark categories | Architecture overview + §17 / §24 / §25 / §26 / §27 / §23 |
| *(new in VGA v4, operational)* complexity levels / invariants / educational-vs-rendering intent / deterministic fallback / observability | §28 / §29 / §17 / §30 / §31 |
| *(new in VGA v5, structural)* Canonical Concept Library (above the blueprint) / per-purpose blueprints / explicit rendering pipeline / declarative-blueprint rule | §32 / §17 / §33 / §34 |
