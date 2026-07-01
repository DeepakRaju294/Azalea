# Adapter Development Spec — types, concepts, and the no-adapter system

> **Purpose.** The authoritative guide for building the 100+ adapters in [`ADAPTER_CATALOG.md`]. It answers
> three questions for every concept:
> 1. **Which TYPE of adapter is it?** (§2) — the structural pattern that fixes the trace shape.
> 2. **What INFO does its adapter declare?** (§3) — the concept-specific fields, by type.
> 3. **What happens when NO adapter applies?** (§4–6) — sound degradation, safe routing, demand tracking.
>
> Companion to `ADAPTER_AND_GENERATION_SYSTEM_SPEC.md` (the contract + pipeline). Every adapter, coding or
> not, implements the same contract (`ExampleSpec` · verified `reference()` · required cases · structured
> `fact()`s · equivalence/invariant hooks · `label_convention`). Templates: `families/trees.py` (coding),
> `families/algebra.py` (math), `families/physics.py` (science).
>
> **Scope guard.** This document defines the SYSTEM capable of supporting 100+ adapters. It does **not**
> authorize implementing every catalog row in one change set. The operating mode is: *build the platform,
> ship the pilots per type, pass the type gate (§2.1), then scale — prioritized by demand (§6) and curriculum
> value.* An implementer must not batch-generate adapters just because the catalog lists them.

---

## 1. The one idea

An adapter is the **executable truth** behind a worked example: it runs the real algorithm/computation (no
LLM) and emits a **verified trace** of learner-facing steps. The generator only *words* those steps. Because
every concept's trace has a **structural shape**, we don't design 100 adapters from scratch — we design **8
types**, and each concept is an instance of one type. Building an adapter = *pick the type, copy its template,
fill the concept-specific info.*

---

## 2. The 8 adapter TYPES

Each type fixes: what one **step** is, how **stages** sequence, the **required-case** pattern, the **state**
shape, and whether it is **coding** (ships a `canonical_solution`) or **non-coding** (calculation only).

| # | Type | One step is… | Required-case pattern | Coding? | Template |
|---|---|---|---|---|---|
| T1 | **Iterative traversal** | visiting the next element of a structure | first-visit · a representative visit · completion | coding | `tree_inorder` |
| T2 | **Greedy frontier update** | pop a frontier candidate → accept / **relax** / reject | ≥1 accept/relax · ≥1 reject/skip/no-improvement · completion | coding | `kruskal`, `dijkstra` |
| T3 | **Divide & conquer** | a split / base-case / combine | a split · a base case · a combine · completion | coding | `merge_sort` (shipped) |
| T4 | **Search / narrowing** | one probe + the direction it eliminates | go-left · go-right · found/not-found · completion | coding | `binary_search` (shipped) |
| T5 | **Table / DP fill** | computing one cell from the recurrence | a base cell · a recurrence cell · the answer cell | coding | *(planned)* |
| T6 | **Formula application** | applying one governing equation | identify · apply each equation · completion (+ branch) | **non-coding** | `quadratic`, `kinematics` |
| T7 | **Reduction / rewriting** | one rewrite that shrinks the expression | each rewrite kind used · reaches normal form | either | `arithmetic_eval` (shipped) |
| T8a | **Incremental construction** | adding one piece to a growing structure | each construction rule used · partial output stays VALID · target reached | either | *(planned)* |
| T8b | **Formal derivation** | one rule-justified derivation step | each transformation rule used · every step follows an ALLOWED rule · conclusion reached | either | *(planned)* |
| T9 | **Repeated relaxation / iterative improvement** | one edge/cell relaxation within a numbered PASS | a relax-that-improves · a pass with no change · the sufficiency bound (why `V−1` passes) | coding | *(planned)* |
| T10 | **Stateful transformation / invariant restoration** | one operation + the sift/restore that repairs the invariant | a restore that bubbles · a no-op restore · completion | coding | *(planned)* |
| T11 | **Constraint search / backtracking** | choose a candidate → explore → **undo** on failure | a valid extension · a dead-end that backtracks · a solution found | coding | *(planned)* |
| T12 | **Program execution / memory trace** | executing one statement, updating variable/stack/heap state | a state update · a branch/loop-condition eval · a call push/return | coding | *(planned)* |

### T1 — Iterative traversal
- **Trace:** one Step per visit; `state = {visited/output so far, current}`; ascending/level/… order.
- **State effects:** one element moves from unvisited → output; the ordering invariant holds.
- **Concepts:** graph BFS/DFS · tree in/pre/post/level-order · linked-list traversal · connected components.
- **Per-concept info:** the *structure* (graph vs tree), the *order rule*, the *frontier* (queue/stack/recursion),
  the *visited invariant*, `label_convention` (letters for graph nodes, ints for values).

### T2 — Greedy frontier update
> **Not "pick the shortest thing".** The dangerous oversimplification (esp. Dijkstra) is collapsing this to a
> single "always choose smallest" step. A T2 trace is a **frontier update**: pop a candidate, inspect it
> against the current state, and take one of *several* outcomes — the trace MUST show both a positive
> (accept/relax/settle) **and** a negative (reject/skip/no-improvement) outcome. `test_type_contracts` enforces
> ≥2 decision outcomes with evidence, so an implementer cannot ship the collapsed version.
- **Trace:** one Step per candidate popped from the frontier; `decision ∈ accept | relax | reject/skip`;
  `state = {result so far, frontier, tentative values (distances), predecessors}`.
- **Concepts & their real semantics:**
  - *Kruskal* — sorted edge → accept (no cycle) **or** reject (cycle).
  - *Prim* — frontier = cut edges → settle the **lightest crossing edge**; skip edges to in-tree nodes.
  - *Dijkstra* — pop min-tentative node → **relax** each out-edge (update dist/predecessor) **or** no-improvement;
    handle a stale priority-queue entry (already-settled node); settle the node. (State: settled set, tentative
    distances, predecessors.)
- **Per-concept info:** the *candidate/frontier order*, the *comparison* driving accept/relax, the *result +
  auxiliary state* (distances/predecessors), the *invariant* (e.g. "settled edge is the lightest crossing edge
  considered"), the `forbidden_claims` catching an inverted decision, required cases (a positive **and** a
  negative outcome).

### T3 — Divide & conquer
- **Trace:** Steps of kind split / base_case / combine; `state = the recursion frontier / merged runs`.
- **Concepts:** merge sort · quick sort · (binary search is T4).
- **Per-concept info:** the *split rule*, the *base case*, the *combine rule* (merge selection + tail copy),
  required cases (split · base · combine).

### T4 — Search / narrowing
- **Trace:** one Step per probe; `decision` names the eliminated half; `state = {lo, hi}` (or search node).
- **Concepts:** binary search · ternary search · exponential search · BST search.
- **Per-concept info:** the *probe rule* (midpoint), the *comparison*, the *narrowing*, required cases
  (go-left, go-right, and found **or** not-found).

### T5 — Table / DP fill
- **Trace:** one Step per cell; `state = table filled so far`; `decision` = the recurrence choice (take/skip).
- **Concepts:** 0/1 knapsack · LCS · LIS · edit distance · coin change · matrix-chain.
- **Per-concept info:** the *table dimensions*, the *recurrence*, the *fill order*, required cases (a base
  cell, a recurrence cell that exercises the choice, the answer cell). **Cap the table size** (small instance)
  so the trace stays bounded.

### T6 — Formula application (NON-CODING)
- **Trace:** identify knowns → apply each governing equation → state the result; `state = {knowns, derived}`.
- **Concepts (math):** quadratic · linear systems · Pythagorean · trig ratios · determinant.
- **Concepts (science):** kinematics · projectile · F=ma · Ohm's law · ideal gas law · stoichiometry · pH.
- **Concepts (finance):** compound interest · present/future value · elasticity · break-even.
- **Per-concept info:** the *knowns/unknowns*, the *governing equation(s)*, **units** (science), the *branch
  cases* (e.g. discriminant sign; zero vs nonzero initial velocity), required cases (identify · apply each ·
  completion). **`allowed_values` is derived from each step's own prose** (see §7 pattern) so formula
  constants / units / signs never false-flag.

### T7 — Reduction / rewriting
- **Trace:** one Step per rewrite; `state = the current expression`; value/meaning preserved each step.
- **Concepts:** arithmetic evaluation · boolean simplification · algebraic simplification · Gaussian
  elimination · factoring · Euclid GCD · modular reduction.
- **Per-concept info:** the *rewrite rule* + *which reducible part to pick next* (highest precedence / pivot),
  the *invariant* (value/solution-set preserved), the *normal form* terminal, required cases (each rule kind).

### T8a — Incremental construction
- **Trace:** one Step per piece added; `state = the partial construction`; the target grows monotonically and
  the **partial output stays structurally valid** at every step.
- **Concepts:** matrix multiplication · sieve of Eratosthenes · truth tables · journal entries.
- **Per-concept info:** the *construction rule*, the *validity invariant on the partial output*, the *target*.

### T8b — Formal derivation
- **Trace:** one Step per rule-justified transformation; `state = the current formal object`; **every step must
  follow an ALLOWED transformation rule** (this is the invariant — you cannot validate an induction proof with a
  sieve's state contract).
- **Concepts:** proof by induction · balancing chemical equations · symbolic equation manipulation.
- **Per-concept info:** the *set of allowed rules*, the *rule cited per step*, the *goal state*.

> T8a and T8b differ in their **core invariant** — "partial output is valid" vs "each step follows an allowed
> rule" — which is why they get separate templates rather than one generic "construction" template.

### T9 — Repeated relaxation / iterative improvement
> **Bellman-Ford is NOT T2.** It is not frontier-greedy — it relaxes edges over **repeated numbered passes**,
> its invariant is *pass-based* (after pass k, all shortest paths using ≤ k edges are correct), and teaching it
> means explaining **why `V−1` passes suffice** and the negative-cycle check. Forcing it into a Dijkstra-shaped
> frontier trace teaches it wrong.
- **Trace:** Steps grouped by PASS; each step is one edge relaxation (improves or not); `state = {distances,
  pass number, changed-this-pass}`.
- **Concepts:** Bellman-Ford · Floyd-Warshall (triple loop) · iterative policy/value updates.
- **Per-concept info:** the *pass structure*, the *relaxation rule*, the *stopping/sufficiency condition*,
  required cases (an improving relax, a no-change pass, the bound).

### T10 — Stateful transformation / invariant restoration
> **Heap sort is NOT divide-and-conquer.** There is no split/combine — it maintains a **heap invariant**:
> build-heap, then repeatedly swap root↔end and **sift-down to restore** the heap. Its teaching core is the
> invariant restoration, not recursion.
- **Trace:** each Step is one operation + the sift/heapify that repairs the invariant; `state = {array/heap,
  sorted-suffix}`.
- **Concepts:** heap sort · heapify / build-heap · heap insert / extract-min · AVL rotation restore.
- **Per-concept info:** the *invariant* (heap property), the *restore operation* (sift-down/up), required
  cases (a restore that bubbles multiple levels, a no-op restore).

### T11 — Constraint search / backtracking
- **Trace:** choose a candidate → explore → **undo** when it violates a constraint; `state = {partial
  assignment, remaining choices, decision depth}`. The teaching core is the *undo* — a trace that only ever
  succeeds hides the whole idea.
- **Concepts:** N-Queens · Sudoku · permutations/combinations/subsets · graph coloring · maze solve.
- **Per-concept info:** the *choice set*, the *constraint check*, the *undo*, required cases (a valid
  extension, a dead-end that backtracks, a solution). **Cap the instance** (small board) — backtracking
  explodes; the learner-facing projection prunes to representative branches.

### T12 — Program execution / memory trace
- **Trace:** one Step per executed statement; `state = {variables, call stack, heap/refs, output}`. This is the
  substrate under "coding fundamentals" (loops, recursion, pointers, scope) — the reference is a small
  interpreter, not a domain algorithm.
- **Concepts:** variable/assignment · for/while loops · function calls + call stack · recursion frames ·
  pointers/aliasing · array/string indexing.
- **Per-concept info:** the *statement set*, the *state model* (env + stack + heap), required cases (a state
  update, a branch/loop-condition eval, a call push/return). **Cap iterations** so the trace stays bounded.

---

## 2.1 Rollout matrix — a TYPE scales only after its pilots prove the grammar

> **The rule.** A type is *not* "ready to scale" because one adapter passes. It is ready only after its **pilot
> adapters** prove the trace grammar survives **meaningful structural variation** — different state models,
> branch cases, and edge cases. Binary search alone does not prove T4 (a BST search has a different state
> model; exponential search adds an expansion phase before narrowing). Build the pilots, evaluate the worked
> examples on real topics, pass the **type-level gate**, *then* expand.

| Type | Pilot adapters | Type-level gate before scaling | Expansion target |
|---|---|---|---|
| **T1** Traversal | tree inorder, graph BFS, graph DFS | handles queue **and** stack **and** recursion frontiers + a disconnected/again-visited case | pre/post/level-order, list/graph traversals |
| **T2** Greedy frontier | Kruskal, Prim, Dijkstra | correctly separates accept / reject / **relax / no-improvement** + auxiliary state (distances, predecessors, stale PQ entry) | Huffman, activity selection, fractional knapsack |
| **T3** Divide & conquer | merge sort, quicksort | recursion tree + base cases + combine frames (merge selection, tail copy) | other recursive split/combine sorts |
| **T4** Search / narrowing | binary search, **BST search** | found **and** absent + strictly-legal narrowing across **two different state models** (array bounds vs tree node) | ternary / exponential search |
| **T5** DP fill | knapsack, LCS, edit distance | table order + recurrence dependency + the take/skip choice + a bounded table | coin change, LIS, matrix-chain |
| **T6** Formula | quadratic, kinematics, Ohm's law | units + **sign/branch** handling + symbolic **and** numeric output | remaining formula/science/finance topics |
| **T7** Rewrite | arithmetic, boolean simplification, Gaussian elimination | equivalence invariant + rewrite-priority + normal-form terminal | factoring, Euclid, modular arithmetic |
| **T8a/T8b** Construct / derive | matrix mult + truth tables (T8a); induction + balancing (T8b) | partial-validity (T8a) **and** allowed-rule (T8b) invariants each proven | sieve, journal entries; symbolic proofs |
| **T9** Repeated relaxation | Bellman-Ford, Floyd-Warshall | pass structure + sufficiency bound + negative-cycle case | iterative-improvement algorithms |
| **T10** Stateful transformation | heap sort, heapify | invariant restoration (sift-down) + no-op vs bubbling restore | heap ops, AVL rotations |

**Current status:** T2/T3/T4/T7 have production pilots; T1/T6 are in **pilot** (templates shipped, gate not yet
signed off across enough variation); T5/T8/T9/T10/T11/T12 are **not started**. Status per adapter lives in the manifest (§8).

---

## 2.2 Adapter boundaries & family packages

**One catalog row = one adapter boundary.** A row is a *distinct trace*, not a topic label. Split into separate
adapters (they may share a template, but each gets its own `slug`, routing aliases + negative guards, fixtures,
required cases, and manifest entry) whenever the **trace rules differ**:

- `preorder` / `inorder` / `postorder` — same template, **distinct adapters** (different ordering rule).
- `directed cycle detection` / `undirected cycle detection` — **distinct** (different state/decision).
- `BST insertion` / `BST deletion` — **distinct** (T8a vs T10 state model).
- `KMP prefix-table` / `KMP matching` — **distinct traces**.

> Shared template ≠ shared adapter. Reuse the type template + visual compiler + harness; never merge two
> different trace grammars behind one slug.

**Family packages, not one growing file.** A family is a *package* and splits by concern once it grows (~>8–12
adapters or unrelated trace grammars): `graph/{traversal,shortest_paths,connectivity,mst}.py`,
`sequence/{sorting,searching,windows}.py`, `math/{algebra,calculus,linear_algebra}.py`. (Today's families have
1–2 adapters each, so they're single files; split when they grow — don't pre-split.)

---

## 3. Per-concept adapter info — the declaration checklist

Whatever the type, a concept's adapter declares exactly these (the varying parts are type-specific above):

1. **`slug`** — stable id · **`label_convention`** — `letters` | `ints`.
2. **`ExampleSpec`** — `input` (InstanceShape: value type, count, range, structure) · `stages` (the type's stage
   grammar) · `structure` (legal sequence) · `must_exercise` (per-instance required cases) · `must_cover`
   (per-suite branch coverage) · `must_avoid` (degenerate anti-cases) · `terminal` · `output_shape`.
3. **`candidates(seed)`** — a deterministic generator of bounded instances (NO hardcoded example values).
4. **`is_teaching_trace(trace)`** — the Stage-0 gate (enough steps + the interesting cases exercised).
5. **`reference(instance)`** — runs the REAL algorithm/computation → a `ContractTrace` of Steps. Each Step:
   `operation` (a declared stage id) · `prior_state`/`state_after` · `decision` · `reason` ·
   `expected_visible_result` · structured `facts` (`allowed_values`, `required_facts=[fact(...)]`,
   `forbidden_claims`).
6. **Hooks:** `states_equivalent` · `final_answer_entails` · `invariant_holds` · `validate_step_shape` ·
   `validate_prose_claims`.
7. **Coding only:** a `canonical_solution` entry (`canonical_solutions.py`) — the simplest idiomatic Python;
   C++/Java are translated on demand. **Non-coding concepts ship NO canonical solution.**
8. **Routing:** a tight title alias in `trace_pipeline.route_adapter` (§5).
9. **§E behavior test:** membership in `test_trace_prose_adversarial` (a lying formatter must be caught).

---

## 4. Coverage ladder — when NO adapter applies (sound degradation)

A topic with no adapter must degrade **honestly**, never fabricate. In descending order of guarantee:

| Tier | When | Guarantee | Where |
|---|---|---|---|
| **Tier 1 — adapter** | an adapter matches | trace-verified steps + answer | `trace_pipeline` (`verification_level=trace_verified`) |
| **Tier 2 — answer anchor** | computational, no adapter, endpoint independently checkable | final answer verified, steps model-authored | `answer_anchor.anchor_final_answer` (`answer_anchored`) |
| **Tier 3 — guided** | conceptual / unverifiable | no wrong claim, no fake trace | guided "key process" (`guided_fallback`) |
| **Tier 4 — illustrative** | narrative concept | factual checks only | `model_only` |

**Invariant (§1.2 of the system spec):** an adapter-supported topic may NEVER fall to a from-scratch
generator. A non-adapter topic uses Tiers 2–4 — and is **recorded** for demand (§6).

### 4.1 Failure policy — "withheld" is not always right

Each adapter declares a `failure_policy` (default in `manifest.py`; overridable per entry). The key
distinction: **a correct trace whose downstream fails must still ship the verified TEXT** — losing a whole
lesson to a rendering hiccup is worse than degrading — but an **invalid trace ships nothing**.

| Failure | Default behavior |
|---|---|
| `invalid_trace` (structural/fidelity gate fails) | **withhold** — nothing ships from a wrong trace |
| `prose_claim_violation` (hard prose/ledger violation) | regenerate prose, then withhold |
| `visual_compile_failure` (trace correct, visual compiler fails) | **ship the verified text cards** |
| `frontend_render_failure` (trace correct, renderer errors) | ship verified text cards + error telemetry |

---

## 5. Routing — explicit + SAFE (no over-matching)

Routing (`route_adapter`) is **explicit and non-fuzzy**: a topic routes only when a tight title/slug alias
names a supported concept. Two safety layers prevent handing a topic an adapter for something it isn't:

1. **Meta/intro guard** — a topic whose title is *about* a concept (`introduction to`, `applications of`,
   `history of`, `when to use`, `comparison of`, …) or whose `topic_type` is `study_path_introduction` /
   `conceptual_overview` **never routes** — it defers, even if it names the algorithm.
2. **Tight aliases + negative guards** — e.g. a binary-search *tree* topic must not match array binary search;
   a graph BFS/DFS alias is blocked on tree topics (`is_tree`). Add the negative guard whenever two concepts
   share vocabulary.

A mis-route that slips through is still caught downstream by the structural + prose fidelity gates (a trace
that doesn't fit the topic fails validation and is withheld), but the guards above stop it at the door.

---

## 6. Missing-adapter demand tracking (`adapter_demand.py`)

Every generation, a **computational topic with no adapter** is recorded (best-effort, append-only, never
affects the lesson) to `logs/adapter_demand.jsonl`, keyed by a normalized concept signature (language- and
filler-word-insensitive, so "Radix Sort" and "Radix Sort in Python" aggregate).

`adapter_demand.summarize()` ranks the buckets by count → **the priority queue for which adapter to build
next**: the concepts learners request most often while still unsupported. Once there are users, this turns
adapter development from guesswork into demand-driven prioritization.

---

## 7. Truth model for computation adapters — the TYPED claim ledger

The **primary** truth model for a computation step is a **typed claim ledger** (`claim_ledger(...)` in
`trace_contract.py`), NOT a flat numeric allowlist. Each value is declared by its **role**, so a number is
allowed only *as a specific quantity*:

```python
facts["claims"] = claim_ledger(
    inputs={"a": 1, "b": -5, "c": 6},                 # given
    constants={"square": 2, "discriminant_multiplier": 4},  # formula structure (NOT answers)
    derived={"D": 1},                                  # intermediates
    outputs={"roots": [2, 3]},                         # the answer
    units={"velocity": "m/s"},
)
```

`validate_claim_ledger` then checks a claim **against its category**: `"D = 1"` is valid; `"D = 4"` is a HARD
`mislabeled_value` (4 is only a formula constant); `"the answer is 4"` is caught as a wrong output. This closes
the gap a flat allowlist misses — a model repeating a *legal* number in an *illegal* claim. It is conservative
(fires only on an explicit `name <copula> number`), so faithful prose is never flagged.

**Supplemental guard only:** the prose-derived numeric allowlist (`_ints(decision, reason, evr, …)`, last step
also covering the final-answer values) stays as a second net — it catches a number that appears *nowhere* in
the verified step — but it is **not** the source of truth. New computation adapters declare `claims`; the
allowlist is the backstop.

**Other patterns:** structured `required_facts=[fact(predicate, text, value)]` (never bare strings) · bounded
`candidates()` (T5 especially — cap the table) · no hardcoded example values in production (§9).

### 7.1 Trace-size budgets — correctness is not enough

> **Rule.** The full trace may be complete; the **learner-facing projection must obey a trace-size budget**.
> Correctness alone does not stop a 45-card merge sort or a 30-step DP walkthrough.

`manifest.TYPE_TRACE_BUDGET` sets a raw-trace **ceiling** per type (enforced by `test_type_contracts` across
many seeds — a bounded instance must never exceed it). The tighter **pedagogical target** below is what the
learner-facing projection should aim for; an adapter whose raw trace runs long (e.g. Dijkstra ~15) uses
**teaching-projection grouping** (§2.5.2 of the system spec) to stay within the target, not a bigger ceiling.

| Type | Pedagogical target (learner-facing) | Raw ceiling (enforced) |
|---|---|---|
| T1 traversal | 5–10 | 12 |
| T2 greedy frontier | 6–12 | 16 |
| T3 divide & conquer | 8–16 (projected) | 12 |
| T4 search | 3–7 | 8 |
| T5 DP | 6–12 selected cells (not the whole table) | 16 |
| T6 formula | 3–6 | 8 |
| T7 rewriting | 3–10 | 12 |
| T8/T9/T10 | 4–12 | 16–20 |

---

## 8. The adapter manifest — the machine-readable source of truth

`trace_adapters/manifest.py` holds one entry per adapter: `type` (T1–T12) · `family` · `status`
(production | pilot | experimental) · `verification_level` · `coding` · `canonical_solution` ·
`routing_aliases` · `negative_guards` · `fixtures` · `visual_contract` · `feature_flag` · `telemetry_key` ·
optional `failure_policy` override. (`telemetry_key`/`feature_flag`/`visual_contract` are auto-filled with
defaults — slug / None / `<family>_state_v1` — until authored.) Module-level it also declares
`TYPE_TRACE_BUDGET` (§7.1) and `DEFAULT_FAILURE_POLICY` (§4.1). The Markdown here stays
human-readable; the **manifest is what code enforces**: `manifest_gaps()` cross-checks it against the live
registry + canonical solutions + type budgets (`test_type_contracts` fails if they disagree), so an adapter
can't ship without a complete entry and the manifest can't name a phantom. It is the operational backbone for
catalog status, routing, test discovery, rollout flags, trace budgets, failure behavior, telemetry, and
coverage reporting.

---

## 9. Production instances vs. test fixtures — both, deliberately

"No hardcoding" applies to **production**, not tests. These are complementary:

| Use case | Instance source |
|---|---|
| Production generation | **seeded bounded generator** (`candidates(seed)`) — never a canned example |
| Unit / contract tests | **fixed deterministic fixtures** (a known input + expected output) |
| Golden visual tests | fixed fixture + expected frame snapshots |
| Property / fuzz tests | many generated seeds |
| Regression tests | **the exact historical bug input**, kept forever |

So `binary_search_target_absent: [2,5,8,12,17], target 9 → -1`, `dfs_reverse_push_order: A→[B,C] pushes C before
B`, and `merge_sort_tail_copy` are **permanent fixtures**, even though production never hardcodes examples. The
two rules coexist: *don't hardcode production examples* **and** *do save fixed regression fixtures*.

---

## 10. Testing tiers — per-adapter AND per-type

- **Per-adapter acceptance block** (declared alongside the adapter): its named `fixtures` (manifest) with
  required *must-produce* cases and *must-reject* cases (e.g. binary search: "found after left narrowing",
  "reject if `lo` decreases when target > mid"). This turns a template into an implementation contract.
- **Per-type invariant suite** (`test_type_contracts.py`): what EVERY adapter of a type must satisfy, so 20
  search adapters can't each invent their own correctness — e.g. T4 "domain never grows, net-shrinks", T2
  "shows both a positive and a negative outcome (no oversimplified greedy)".
- **Shared conformance / artifact / adversarial** (all adapters): 0 contract violations, 0 C1 gaps, a lying
  formatter is caught.

---

## 11. Verification tiers are user-visible

`verification_level` is not only internal — it must shape the UI so lower-guarantee content is never
indistinguishable from a verified trace:

| Tier | Internal | User-facing treatment |
|---|---|---|
| Trace verified | `trace_verified` | full worked example, confident step-by-step visuals |
| Answer anchored | `answer_anchored` | "Verified answer; explanatory steps may vary" |
| Guided | `guided_fallback` | "Guided walkthrough" |
| Illustrative | `model_only` | "Conceptual illustration" |

(No raw technical label shown, but the treatment differs — a user must not assume all examples carry the same
reliability.) The level already flows in the generation report; the frontend badge is the remaining wire-up.

---

## 12. Build a new adapter — the workflow

1. Find the concept in `ADAPTER_CATALOG.md`; note its **type** (§2) and **family**; confirm the type's
   rollout gate (§2.1) is met or that this is a sanctioned pilot.
2. Copy the type's template class into the family module (create the family module if new).
3. Fill the **per-concept info** (§3); computation adapters declare a **typed claim ledger** (§7).
4. Coding only: add the `canonical_solution` (simplest idiomatic Python).
5. Register it (`trace_adapters/__init__.py`) + add the tight routing alias + negative guards (§5).
6. Add a **manifest entry** (§8) and named **fixtures** (§9–§10); add it to the adversarial coverage set.
7. Run `test_adapter_conformance`, `test_adapter_artifacts`, `test_trace_prose_adversarial`, and its
   **type-level suite** (§10) — all must pass (0 contract violations, 0 C1 gaps, type invariant holds).
8. Flip its catalog row to ✅ and set the manifest `status`.

> **Do not batch-build.** Ship the first few of a new type, evaluate the worked examples on real topics, pass
> the type gate (§2.1), *then* scale — the template is refined by the *first* adapters of each type, not by
> writing 20 at once.
