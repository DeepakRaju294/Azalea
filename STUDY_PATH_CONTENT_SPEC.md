# Study Path Content — Issues & Solutions Spec

Implementation status (reconciled):
- **Implemented + flag-gated:** the trace pipeline itself — the system already creates and verifies a
  canonical trace before formatting (see `WORKED_EXAMPLE_REASONING_SPEC.md`). This spec **builds on**
  that; it must not bypass or duplicate it.
- **NOT implemented (this spec):** the **Step Contract v2** (§1) and every Fix listed in §A–§E. Design
  only.

Compiled from the MST study-path review (paths `fce190a4` = 5 topics/no comparison, `f6443a34` = 6
topics/with comparison, both "Minimum Spanning Tree Algorithms", 2026-06-28) across four review threads
plus an external design review (v2 revisions below).

Each issue below carries its **evidence**, **root cause** (where known), and **Fix**. Severity:
🔴 correctness/blocking · 🟠 significant learning gap · 🟡 quality/polish.

**The core arc (why these fixes hang together).** Azalea should not generate cards directly — it should
generate a **verified instructional model**, then project that model into cards. A canonical algorithm
trace (state transitions) is necessary but not sufficient; a good lesson needs a second artifact, an
**instructional trace** that says, per step: what transition happened, what decision mattered, why it
was safe/necessary, what state stays visible, what is hidden/grouped, what misconception it prevents,
and what visual change to show. **The stage grammar is the start of that instructional trace** — §1a is
the keystone that begins projecting it. (Related: `PROJECTOR_SYSTEM_SPEC.md`.)

---

## §0. Solution mechanisms

Every Fix is one of these. The card-structure work concentrates in **M2 / §1**.

| | Mechanism | Where it lives |
|---|---|---|
| **M1** | **New card blueprint** | `course_blueprints.py` (registry + topic `default_card_sequence`) + `course_stage_rules.py` (`_lean_rule`) + `topic_type_definitions.py` |
| **M2** | **Card-structure spec** (what goes in each section/field) | the worked-example step contract (solver prompts + `trace_pipeline.build_format_payload` + the adapter stage grammar) and per-card `_lean_rule`s |
| **M3** | **Validator / guard** | `trace_contract.py` (`validate_prose`/`validate_fidelity`) + adapter `validate_prose_claims` |
| **M4** | **Deterministic planning rule** | `lean_lesson_generator.py` post-generation enforcement / `topic_decomposition.py` |
| **M5** | **Frontend rendering** | `learn/page.tsx` |
| **M6** | **Content acceptance suite** (instructional-quality regression gate) | golden-lesson fixtures + content-shape assertions (§H) |

---

## §1. Worked-Example Step Contract v2 (M2 — the keystone)

The central card-structure spec; referenced by most of §B, §C, and parts of §A/§D. Root enabler: **the
formatter must consume the stage grammar** (`contains` roles + `teaching_focus`) instead of flying blind.
Defines **two variants** of the step card.

### 1a. Make the formatter stage-grammar-aware  *(fixes B3, B4, C1, C6)*
- `build_format_payload(trace, code)` passes, per step: the stage's `teaching_focus` and the `contains`
  map with roles (`internal` / `required` / `aggregated_supporting`).
- Prompt rule: surface the **required** operation as the step's one decision line; **aggregate**
  supporting operations into a single line; **omit** internal ones; lead reasoning with `teaching_focus`.
- Net: Work collapses from ~4 raw lines to ~1 decision + ~1 aggregated line; reasoning gets a spine.
- Data already exists on the adapters (`example_spec.stages[*].contains` / `teaching_focus`) — just
  thread it through. (Confirmed dormant today: the formatter never references it.)
- **Make the hierarchy enforceable, not implied** (v2): one learner-visible decision per step, declared
  so a validator can check it.
  ```text
  Every step has EXACTLY ONE learner-visible decision.
  required:              the core decision/transition the learner must recognize (the one decision line).
  aggregated_supporting: necessary implementation/state updates, summarized in ONE phrase.
  internal:              hidden unless teaching_focus explicitly requires it.
  teaching_focus:        the misconception, invariant, or selection rule this step is meant to teach.
  ```
  Without this, the model falls back to line-by-line execution narration (the "safest" reading of a raw
  trace). A correct trace is necessary but **not sufficient** — the learner interacts with *claims*, not
  internal JSON.

### 1b. Coding variant — section layout  *(fixes B1, B2, B5, C7)*
- **Drop `goal`** (the title carries it).
- **Work bullets = short problem-context phrases**, not verbatim code + long comment. The per-bullet
  highlight (already built) shows the code line; the bullet says *what it does in problem terms*. Keep
  the `code_lines` anchor so the active bullet highlights its line.
- **Replace `result` with a `variables` panel**: a persistent, always-updating view of the variables
  that carry the algorithm's state forward.
  - **HYBRID model (v2) — adapter-declared is primary; AST is only a fallback.** Pure AST persistence
    ("assigned before the loop / returned") is too brittle to decide what matters: a persistent var may
    be built in a helper, a returned local may be temporary, a loop-local pointer (`mid` in binary
    search; `i`,`j`,`k` in merge) can be pedagogically central, durable objects mutate without
    reassignment, and recursion has no "main loop." So:
    ```python
    display_variables = {
        "persistent":  ["mst", "total_cost", "min_heap", "visited"],  # always visible (durable state)
        "step_focus":  ["u", "v", "weight"],                          # shown only for the current step
    }
    ```
  - Resolution order: `adapter_declared` → `inferred_persistent` (AST fallback) → `step_focus`
    (temporary, shown only when the transition needs it). Values come from the verified `state_after`.
  - Remove the raw `prior_state` dump from Work.

### 1c. Walkthrough variant — richer content  *(fixes C2, C3, C4, C5, D4, D5)*
- **Step-specific reasoning** (not templated): which components/vertices, *minimum among what
  remaining*, and why the choice is safe (cut / no-cycle).
- **Show candidates — under a compact display policy** (v2; Prim already does; bring to Kruskal).
  "Always show" must NOT mean dumping every edge/heap entry per card (that recreates the overload). The
  learner only needs to answer *"why was this choice allowed, and why preferred?"*
  ```text
  Kruskal:  show the sorted-edge strip ONCE; highlight the current edge; mark accepted/rejected as it goes.
  Prim:     show frontier (crossing) candidates only; highlight the selected edge; collapse stale/
            non-crossing candidates unless one explains a misconception.
  BFS/DFS:  show queue/stack + the newly eligible neighbors; do not re-dump the full graph as text.
  ```
- **Surface the signature first move**: Kruskal shows the **sorted edge list** up front; the trace
  references positions in it.
- **Stopping condition**: once `selected_edges == V-1`, the step states "MST complete; remaining edges
  are redundant" rather than silently continuing.
- **Prim framing**: Step 0 = "start at vertex A"; each `result` names the **selected edge** (not just the
  node set); reasoning states the **crossing-edge rule** (cheapest edge leaving the tree, not globally
  cheapest).

### 1d. Where these live
- Section definitions: extend `WORKED_EXAMPLE_REASONING_SPEC.md` (or a new `WORKED_EXAMPLE_STEP_CONTRACT.md`).
- Coding prompt: `_CODING_FORMAT_SYSTEM` (trace_pipeline) + `_CODING_CARDS_SYSTEM` (solver, legacy path).
- Walkthrough prompt: the non-coding branch of `build_format_payload`.

### 1e. Implementation principle — structure first, prompt second (v2)
**Do NOT let Step Contract v2 become only prompt wording.** Its core fields — the decision, `teaching_focus`,
the role of each operation (`required`/`aggregated_supporting`/`internal`), candidate context, visible
variables, and the safety rationale — must be represented as **structured data** (on the trace step /
adapter stage grammar) wherever possible. The prompt is then responsible mainly for **wording and
compression**, not for inventing the structure. This is what keeps the instructional model verifiable
(M3) and regression-testable (M6) rather than a re-styled prose dump.

---

## §A. Correctness & accuracy bugs

### A1. 🔴 Kruskal walkthrough — Step 5 narration contradicts the result
```
Step 5: Consider Edge (A, B, 8)
Reasoning: The edge connects two components that are already connected in the MST.
Work:    - Edge (A, B, 8) connects components already linked.
         - Skip the edge.
Result:  Edge (A,B,8) accept; MST so far [..., ['A','B',8]]     ← accepted
```
The result is correct (A∈{A,C}, B∈{B,D,E,F} — different components), but the prose says skip. Self-
contradictory; a learner is derailed.
- **Root cause:** prose drifted from the backend-attached verified result; `validate_prose` didn't flag
  it as a hard contradiction.
- **Fix (M3) — structured, not keyword-based** (v2). A keyword guard (`skip`/`reject`/`already
  connected`) is a useful *temporary defensive layer now*, but it false-positives ("we do **not** skip
  this edge…") and false-negatives. The durable mechanism: the trace step carries explicit semantic
  labels, and the validator checks the prose's extracted claims against them — natural prose is still
  allowed, only the *asserted fact* is checked.
  ```json
  step:   { "decision_type": "accept_edge", "decision_reason": "different_components",
            "decision_target": ["A","B",8] }
  claim:  { "edge_action": "accept", "components_relation": "different" }   // extracted from the prose
  // hard violation if claim.edge_action != step.decision_type's action, etc.
  ```
  Ship the keyword guard first; replace it with the structured check.

### A2. 🔴 Prim coding — displayed implementation returns vertices, not edges
```python
if cost > 0:
    mst_edges.append(u)         # appends the VERTEX
return mst_edges, total_cost     # returns (['B','C','D'], 4)
```
`total_cost` is right, but `mst_edges` is a vertex list — never the MST's edges. A learner copying it
gets a broken Prim.
- **Root cause:** LLM-generated code; no check on output shape.
- **Fix (M3) — validate EXECUTABLE behavior, not only shape** (v2). Shape alone misses code that returns
  edges but still has a cycle, omits a vertex, picks a non-minimal tree, or mismatches the total. For a
  deterministic coding example, the contract is:
  ```text
  1. Parse the displayed code.
  2. Execute it on the chosen teaching instance.
  3. Assert output shape vs the adapter's final_answer.
  4. Assert structural MST properties: exactly V-1 edges, connected, acyclic, total == expected.
  5. Run 1-2 small hidden companion instances (guards against overfitting to the shown graph).
  ```
  Guarantees a learner could copy the code and get a valid result — not merely that the narration looks
  compatible.
  - **Boundary (v2):** full execution applies only to code intended to be **runnable end-to-end**. For a
    **partial snippet** (a fragment, a helper, a class method), validate the *snippet contract* and
    execute a **generated harness** that supplies the surrounding scaffold — don't try to run the
    fragment as a standalone program.

### A3. 🔴 Prim coding withholds → falls back to the legacy solver
Kruskal coding ships the verified adapter trace; Prim coding withholds and uses the weaker legacy path.
- **Root cause (verified):** the verbatim-code contract makes the formatter quote the **lazy-heap** Prim
  code, but the Prim adapter is **eager / edge-centric**. The heap code's start cost `0` is **not** in the
  step's `allowed_values` (`[1,2,4,7,14]`) → **hard `value_not_allowed`** (`trace_contract.py:184`) →
  retry can't fix it → withhold → legacy. Kruskal survives (same variant; numbers are edge weights).
- **Fix has two levels; do BOTH, and the second is more fundamental** (v2):
  1. *(immediate, M3)* scope `value_not_allowed` to the text **after `//`** for coding Work lines (the
     claim), exempting structural code numbers (`0`, indices, heap costs). Stops the false withhold.
  2. *(root, M4 §4b — pull EARLIER, alongside A3, not the late phase)* **variant alignment.** Even with
     validation passing, teaching Prim as *eager* in the walkthrough and *lazy-heap* in the code (with no
     bridge) confuses learners. This is a correctness/comprehension issue, not just a validator quirk —
     so D2 belongs here, not in step 5. See §D2.

---

## §B. Worked-example step structure (coding) — all fixed by §1b unless noted

- **B1 🟡 `Goal` redundant with the title** (often the raw `Goal: consider_edge`). → drop Goal for coding
  [§1b].
- **B2 🟠 Work bullets too long** (`mst.append((u,v,weight)) // Adds the edge (A,B,2)…`). → context-only
  bullet; the highlight shows the code [§1b + M5]. Optional code "chip" styling.
- **B3 🟠 Too many Work bullets** (one per executed line, no cap). → surface `required`, aggregate the
  rest [§1a].
- **B4 🟠 Grouping is declared but dormant.** The roles already encode the fix:

  | Algorithm | Declared groups (role) |
  |---|---|
  | Kruskal `consider_edge` | `find_roots`[internal] · `decide_accept_or_skip`[required] · `union_components`[aggregated] · `append_to_mst`[aggregated] |
  | Prim `select_edge` | `scan_crossing_edges`[internal] · `select_min_crossing_edge`[required] · `add_vertex`[aggregated] · `update_frontier`[aggregated] |
  | BFS `dequeue_enqueue` | `dequeue_node`[required] · `enqueue_neighbor`[aggregated] · `skip_visited`[aggregated] |

  → thread the stage grammar into the formatter [§1a].
- **B5 🟠 Replace raw-dict `Result` with a persistent Variables panel** (coding only). Today: `Result:
  {'selected_edges': [...], 'components': [...]}`. → `variables` watch-panel of long-lived vars only
  [§1b + M5].

---

## §C. Algorithm-walkthrough content quality — all fixed by §1c unless noted

Steps read like a mechanical state change with generic reasoning, not a walkthrough.
- **C1 🟠 Templated reasoning** ("connects two components and has the minimum weight" every step). →
  step-specific, led by `teaching_focus` [§1a/§1c].
- **C2 🟠 Candidates not shown (Kruskal)** — each greedy pick looks arbitrary. → `candidates` field
  everywhere [§1c + M5].
- **C3 🟠 Sorted edge list invisible** — the example jumps to "Consider Edge (B,D,5)"; the learner can't
  verify it's smallest. → show sorted edges up front [§1c].
- **C4 🟠 Stopping condition invisible** — continues past V-1 edges with no note. → "MST complete" step
  [§1c].
- **C5 🟠 "Why it's safe" never stated** (cut/no-cycle). → safety line in reasoning [§1c].
- **C6 🟡 `teaching_focus` declared but thrown away.** → thread it into the prompt [§1a].
- **C7 🟡 `prior_state` dumped into Work.** → move state to the Variables panel [§1b].

---

## §D. Consistency

- **D1 🟠 The two walkthroughs feel like different products** (Kruskal: components/no candidates; Prim:
  candidates/nodes-only result). → one shared walkthrough contract [§1c].
- **D2 🟠🔴 Walkthrough ≠ coding for the same algorithm** — Prim walkthrough is **eager**, Prim coding is
  **lazy-heap**; the learner is never told they're the same algorithm. (Also the mechanism behind A3 —
  treat this as correctness, and schedule it EARLY, alongside A3.)
  **Fix (M4, §4b) — one canonical variant per LEVEL + an explicit bridge** (v2):
  > Teach **eager Prim** in the conceptual walkthrough, then introduce the **lazy-heap implementation as
  > an optimization of it — not a different algorithm.** Constrain the coding topic's code to that variant
  > (or expose the adapter variant the code uses) so walkthrough and code tell one story and the verbatim
  > mapping stops breaking.

  Bridge line (also covers D3):
  ```text
  Conceptually, Prim repeatedly chooses the cheapest edge crossing out of the current tree.
  The heap implementation stores candidate crossing edges so it can find that edge efficiently.
  ```
  (The three options — eager everywhere / lazy everywhere / teach both — are all valid; the standard path
  uses one-per-level as above.)
- **D3 🟡 Concept→code bridge missing** — "components merging" → `disjoint_set.union` with nothing saying
  *components = disjoint sets*. → bridge line in the coding background/walkthrough [§1 _lean_rule].
- **D4 🟠 Prim walkthrough never explains the crossing-edge rule** (Step 4 picks weight 1 after weight 9;
  a Kruskal-trained learner is baffled). → state it in reasoning [§1c]. *Highest-value single content
  fix.*
- **D5 🟡 Prim framing/result polish** — Step 1 should be "start at vertex A"; the result should name the
  edge, not just nodes. → [§1c].

---

## §E. Missing content (cards & topics)

### E1. 🟠 No analysis / complexity card anywhere
After both algorithms, zero coverage of complexity, when-to-prefer, or trade-offs. Confirmed: no such
blueprint exists.
- **Fix (M1):** register a `complexity_analysis` card; add to `default_card_sequence` for
  `algorithm_walkthrough`, `coding_implementation`, `data_structure_operation` (after `worked_example`,
  before `practice`). Not a generic Big-O dump — required structure (v2):
  ```text
  Cost driver       — what operation dominates runtime?
  Time and space    — Big-O, with assumptions stated
  Why it exists     — its practical advantage
  When to prefer it — concrete input / data-structure conditions
  When NOT to       — a sibling algorithm or condition that makes it weaker
  ```
- **Accuracy (M3 tie-in):** complexity is a factual claim — declare known complexities on the adapter
  (`example_spec.time_complexity`/`space_complexity`) and validate the stated Big-O against it;
  the "why/when" prose may be LLM-written.

### E2. 🟠 Comparison topic is non-deterministic (coin-flip)
Present in `f6443a34` (6 topics), absent in `fce190a4` (5 topics), same subject.
- **Root cause:** no deterministic rule — `comparison` is an LLM-chosen planning role gated by soft
  `use_when`/`excludes` criteria.
- **Fix (M4):** after planning, if a path has **≥2 sibling topics of the same family** (detectable from
  `topic_family`/decomposition metadata), ensure a `compare_distinguish` topic exists; inject if missing
  (same pattern as `_enforce_roadmap_coverage`).

### E3. 🟠 Introduction too thin — **Intro Contract v2** (M1 + M2)
Today the intro is just `background` (≈2–3 sentences) + `roadmap`. It never grounds a cold learner in the
foundations or the shared vocabulary the later topics assume, and the same cross-cutting terms (Edge,
Vertex, Weight) get **re-defined in every topic's `components_terms`** (observed: Kruskal *and* Prim both
redefine them). Principle: **intro = orientation + shared foundation; topics = depth + topic-specific
detail.**

**New intro card sequence:** `background → prerequisites → key_terms → roadmap`.

1. **`background`** *(keep, lightly strengthen):* the motivating hook + what this path covers (add a
   concrete real problem, e.g. "the cheapest way to wire all the offices so they're all connected").
2. **`prerequisites` (NEW card, M1):** *"What you need going in."* A **brief** primer on the foundations
   the path assumes — what a **weighted graph** is, what a **spanning tree** is (connects all vertices,
   no cycles, V−1 edges), and a **one-line anchor** for the subject (e.g. "an MST is the spanning tree of
   smallest total weight"). An anchor only — the *intuition* belongs to the `concept_intuition` topic.
   Optional "review X first" signpost.
3. **`key_terms` (NEW card, M1):** the **shared glossary** used across *every* later topic, defined once
   (vertex/node, edge, weight, cycle, connected, spanning tree, greedy) — one line each. Explicitly the
   **cross-cutting** terms, NOT topic-specific ones (`union-find`, `priority queue` stay in their topics).
4. **`roadmap`** *(keep, unchanged).*

**Boundary rules (avoid duplication):**
- **Intro ↔ `concept_intuition`:** the intro only *anchors* the subject in one sentence; the deep
  intuition is developed in the `concept_intuition` topic. Decision: **Option A — the intro is ALWAYS
  brief** (never teaches), for consistency across path shapes (chosen over the adaptive Option B).
- **Intro ↔ per-topic `components_terms`:** the intro owns **shared** terms (appear in ≥2 topics); each
  topic's `components_terms` keeps only its **unique** terms — removing the Edge/Vertex/Weight repetition.
  Shared set = terms common across the path's topics (derivable from the topics' term lists, or
  LLM-identified as "used throughout").

**System changes (Fix):**
- **M1:** register `prerequisites` + `key_terms` blueprints; add to `study_path_introduction`
  `default_card_sequence` → `[background, prerequisites, key_terms, roadmap]`.
- **M2:** `_lean_rule`s for the two new cards (content above; primer stays brief — no re-teaching the
  `concept_intuition` topic). **Flip the current intro rule** that *forbids* `components_terms`
  ("vocabulary belongs in the subtopic") → the intro defines **cross-cutting** vocabulary, subtopics
  define **topic-specific** vocabulary.

### E4. 🟡 Code walkthrough is robotic
Every bullet starts "This line…"; narrates *what* a line is, never *why*.
- **Fix (M2):** `_lean_rule` requires "why, not just what" (e.g., union-find *is* the cycle check).

---

## §F. Cross-cutting root causes
- **The formatter flies blind** — no stage grammar, so it can't group Work, lead with the decision, or
  teach consistently. Wiring it in (§1a) is the common enabler for B2/B3/B4 and most of C.
- **Eager-vs-lazy variant mismatch** between adapters and LLM code drives both the Prim withholding (A3)
  and the walkthrough↔coding inconsistency (D2).
- **Validation blind spots** — decision-word contradictions (A1) and wrong return shapes (A2) pass; the
  value allowlist misfires on verbatim code (A3).

---

## §G. Per-issue solution map

| Issue | Fix | Mechanism |
|---|---|---|
| A1 skip/accept contradiction | keyword contradiction guard (temporary) → **durable structured decision/claim validation** | M3 |
| A2 Prim code returns vertices | **execute displayed code on the teaching + hidden instances**; validate output shape AND algorithm correctness properties | M3 |
| A3 Prim withholds → legacy | `value_not_allowed` scoped to `//` (+ D2 root fix) | M3 (+M4) |
| B1 Goal redundant | drop Goal for coding | M2 §1b |
| B2 Work bullets too long | context-only bullet; highlight shows code | M2 §1b + M5 |
| B3 too many bullets | surface `required`, aggregate supporting | M2 §1a |
| B4 grouping dormant | thread stage grammar into formatter | M2 §1a |
| B5 Result → Variables panel | variables field; adapter-declared persistence (+AST fallback) | M2 §1b + M5 |
| C1 templated reasoning | step-specific, led by `teaching_focus` | M2 §1a/§1c |
| C2 no candidates (Kruskal) | `candidates` field everywhere | M2 §1c + M5 |
| C3 sorted list invisible | show sorted edges up front | M2 §1c |
| C4 stopping invisible | "MST complete" step at V-1 | M2 §1c |
| C5 no "why safe" | cut/no-cycle line in reasoning | M2 §1c |
| C6 `teaching_focus` unused | thread it into the prompt | M2 §1a |
| C7 prior_state dump | move state to Variables panel | M2 §1b |
| D1 walkthroughs inconsistent | one shared walkthrough contract | M2 §1c |
| D2 walkthrough≠coding variant | align variants | M4 §4b |
| D3 concept→code bridge | bridge line in coding background/walkthrough | M2 _lean_rule |
| D4 crossing-edge rule unstated | Prim reasoning states it | M2 §1c |
| D5 Prim framing/result | start-vertex + name the edge | M2 §1c |
| E1 no analysis card | new `complexity_analysis` card | M1 |
| E2 comparison non-deterministic | sibling-family rule | M4 |
| E3 intro too thin | richer background `_lean_rule` | M2 |
| E4 robotic code walkthrough | "why not just what" in `_lean_rule` | M2 |

---

## §H. Content acceptance suite (v2 — new; M6)
Validators (M3) protect *correctness*; they don't stop *instructional-quality regression* — a valid
change can still reintroduce too many bullets, generic "why," missing bridge, no stopping condition,
overlong cards, repeated titles, or raw-state dumps. Add **golden-lesson fixtures** for a fixed set
(BFS, DFS, Kruskal, Prim, merge sort, binary search, one math method, one proof, one data-structure
operation) and assert content *shape*, then manually review the rendered result after each structural
change:
```text
- exactly 1 core decision per step
- <= 2 Work lines per step
- no raw dict rendering
- every greedy-selection step states its selection criterion
- every algorithm has an explicit stopping condition
- coding steps have a visible code anchor
- titles do not repeat generic operation labels (no "Goal: consider_edge")
- no unsupported implementation claims
```
This becomes the permanent quality gate — the product's differentiator is *correct output that is fast
to understand and reconstruct*, not correctness alone.

## §I. Sequencing (severity × leverage — v2, revised)
The key change from v1: **variant alignment (D2) moves much earlier** — it affects correctness, formatter
mapping, comprehension, and fallback all at once, so building format rules on incompatible traces first
would be wasted.
1. **Stop correctness leaks (M3)** — A1 (ship keyword guard now → structured decision/claim check),
   A2 (executable code validation + return shape), A3 (narrow the false validator + fallback telemetry).
2. **Align canonical variants (M4 §4b)** — fix D2 *before* more format rules; add the concept→code bridge.
3. **Wire stage grammar into formatting (M2 §1a)** — required/aggregated/internal + `teaching_focus`.
4. **Implement the two step contracts (M2 §1b/§1c)** — coding (no Goal, short Work, Variables panel) +
   walkthrough (candidates policy, safety reason, stopping, selected-edge framing).
5. **Golden-fixture regression tests (M6 §H)** — content-shape + rendered output; MST as the first set.
6. **Missing coverage** — `complexity_analysis` (E1), deterministic comparison topic (E2), stronger intro
   (E3), "why not what" code walkthrough (E4).
7. **Frontend polish (M5)** — Variables panel, candidate strip/frontier, code chips/highlight.

## §J. New cards / structure changes at a glance (your framing)
- **New card:** `complexity_analysis` (E1).
- **Card-structure specs (the bulk):** Worked-Example Step Contract v2 — §1a stage-grammar wiring, §1b
  coding layout (no Goal, short Work, Variables panel), §1c walkthrough richness; plus `_lean_rule`
  tightening for the intro (E3), code walkthrough (E4), and concept→code bridge (D3).
- **Validators:** A1 (structured decision/claim check; keyword guard as a temporary layer), A2
  (executable code validation), A3 (`//`-scoped allowlist).
- **Planning rules:** comparison topic (E2), variant alignment (D2 — scheduled early, with concept→code
  bridge).
- **Content acceptance suite (M6):** golden-lesson fixtures asserting instructional shape (§H).
- **Frontend:** Variables panel, candidate strip/frontier, short bullets/code chips (B2/B5/C2).
