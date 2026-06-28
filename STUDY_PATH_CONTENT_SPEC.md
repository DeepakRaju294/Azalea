# Study Path Content — Issues & Solutions Spec

Status: **Design / backlog — nothing here is implemented.** Compiled from the MST study-path review
(paths `fce190a4` = 5 topics/no comparison, `f6443a34` = 6 topics/with comparison, both "Minimum
Spanning Tree Algorithms", 2026-06-28) across four review threads: the Prim-coding fallback root cause,
five reported issues, the work-bullet/grouping/walkthrough-content discussion, and the learner's-
perspective content audit.

Each issue below carries its **evidence**, **root cause** (where known), and **Fix**. Severity:
🔴 correctness/blocking · 🟠 significant learning gap · 🟡 quality/polish.

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

### 1b. Coding variant — section layout  *(fixes B1, B2, B5, C7)*
- **Drop `goal`** (the title carries it).
- **Work bullets = short problem-context phrases**, not verbatim code + long comment. The per-bullet
  highlight (already built) shows the code line; the bullet says *what it does in problem terms*. Keep
  the `code_lines` anchor so the active bullet highlights its line.
- **Replace `result` with a `variables` panel**: a persistent, always-updating view of the **long-lived**
  variables only.
  - Source: the verified `state_after` already carries the durable state.
  - Persistent-vs-auxiliary: AST pass — assigned *before* the main loop and/or returned = persistent
    (`mst`, `uf`, `min_heap`, `visited`, `total`); loop-body-local (`u`,`v`,`weight`,`cost`) = auxiliary,
    excluded.
  - Remove the raw `prior_state` dump from Work.

### 1c. Walkthrough variant — richer content  *(fixes C2, C3, C4, C5, D4, D5)*
- **Step-specific reasoning** (not templated): which components/vertices, *minimum among what
  remaining*, and why the choice is safe (cut / no-cycle).
- **Always show candidates** (Prim already does; bring to Kruskal) — a structured `candidates` field.
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
- **Fix (M3):** decision-word guard — if the step decision is `accept`/`select` but prose contains a
  `skip`/`reject`/`already connected` claim (or vice-versa), emit a **hard** violation → re-format.

### A2. 🔴 Prim coding — displayed implementation returns vertices, not edges
```python
if cost > 0:
    mst_edges.append(u)         # appends the VERTEX
return mst_edges, total_cost     # returns (['B','C','D'], 4)
```
`total_cost` is right, but `mst_edges` is a vertex list — never the MST's edges. A learner copying it
gets a broken Prim.
- **Root cause:** LLM-generated code; no check on output shape.
- **Fix (M3):** return-shape guard — validate the displayed code's output against the adapter's
  `final_answer` structure (MST = list of **edges**); flag/regenerate if wrong.

### A3. 🔴 Prim coding withholds → falls back to the legacy solver
Kruskal coding ships the verified adapter trace; Prim coding withholds and uses the weaker legacy path.
- **Root cause (verified):** the verbatim-code contract makes the formatter quote the **lazy-heap** Prim
  code, but the Prim adapter is **eager / edge-centric**. The heap code's start cost `0` is **not** in the
  step's `allowed_values` (`[1,2,4,7,14]`) → **hard `value_not_allowed`** (`trace_contract.py:184`) →
  retry can't fix it → withhold → legacy. Kruskal survives (same variant; numbers are edge weights).
- **Fix (M3):** scope `value_not_allowed` to the text **after `//`** for coding Work lines (the claim),
  exempting structural code numbers (`0`, indices, heap costs). Root mismatch addressed by §4b.

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
- **D2 🟠 Walkthrough ≠ coding for the same algorithm** — Prim walkthrough is **eager**, Prim coding is
  **lazy-heap**; the learner is never told they're the same algorithm. (Also the mechanism behind A3.) →
  **Fix (M4, §4b):** constrain the coding topic's code to the **same variant** the adapter teaches (or
  expose the adapter variant the code uses) so walkthrough and code tell one story and the verbatim
  mapping stops breaking.
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
  before `practice`). `_lean_rule`: time + space complexity (with the cost driver), 1–2 benefits, 1–2
  drawbacks, "prefer this when…".
- **Accuracy (M3 tie-in):** complexity is a factual claim — declare known complexities on the adapter
  (`example_spec.time_complexity`/`space_complexity`) and validate the stated Big-O against it;
  benefits/drawbacks may be LLM-written.

### E2. 🟠 Comparison topic is non-deterministic (coin-flip)
Present in `f6443a34` (6 topics), absent in `fce190a4` (5 topics), same subject.
- **Root cause:** no deterministic rule — `comparison` is an LLM-chosen planning role gated by soft
  `use_when`/`excludes` criteria.
- **Fix (M4):** after planning, if a path has **≥2 sibling topics of the same family** (detectable from
  `topic_family`/decomposition metadata), ensure a `compare_distinguish` topic exists; inject if missing
  (same pattern as `_enforce_roadmap_coverage`).

### E3. 🟠 Introduction too thin
Background ≈3 bullets; missing what a spanning tree is (vs MST), what weight represents, a **motivating
problem**, and a prerequisite signpost.
- **Fix (M2):** strengthen the `study_path_introduction` background `_lean_rule` to require those.

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
| A1 skip/accept contradiction | decision-word hard guard | M3 |
| A2 Prim code returns vertices | return-shape guard vs adapter `final_answer` | M3 |
| A3 Prim withholds → legacy | `value_not_allowed` scoped to `//` (+ D2 root fix) | M3 (+M4) |
| B1 Goal redundant | drop Goal for coding | M2 §1b |
| B2 Work bullets too long | context-only bullet; highlight shows code | M2 §1b + M5 |
| B3 too many bullets | surface `required`, aggregate supporting | M2 §1a |
| B4 grouping dormant | thread stage grammar into formatter | M2 §1a |
| B5 Result → Variables panel | persistent variables field + AST persistence | M2 §1b + M5 |
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

## §H. Sequencing (severity × leverage)
1. **M3 correctness guards** (A1, A2, A3) — stop shipping wrong/contradictory content; quick.
2. **M2 §1a stage-grammar wiring** — the keystone; unlocks B3/B4/C1/C6 at once.
3. **M2 §1b/§1c step contracts** — coding (Variables panel, short bullets, no Goal) + walkthrough richness.
4. **M1 §E1 analysis card** + **M2 §E3 richer intro**.
5. **M4 rules** — comparison topic (E2), variant alignment (D2).
6. **M5 frontend** — Variables panel, short bullets, candidates (lands alongside 2–4).

## §J. New cards / structure changes at a glance (your framing)
- **New card:** `complexity_analysis` (E1).
- **Card-structure specs (the bulk):** Worked-Example Step Contract v2 — §1a stage-grammar wiring, §1b
  coding layout (no Goal, short Work, Variables panel), §1c walkthrough richness; plus `_lean_rule`
  tightening for the intro (E3), code walkthrough (E4), and concept→code bridge (D3).
- **Validators:** A1, A2, A3.
- **Planning rules:** comparison topic (E2), variant alignment (D2).
- **Frontend:** Variables panel, short bullets, candidates (B2/B5/C2).
