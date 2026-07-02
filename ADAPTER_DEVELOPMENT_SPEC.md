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
every concept's trace has a **structural shape**, we don't design 100 adapters from scratch — we design a small set of
**types**, and each concept is an instance of one type. Building an adapter = *pick the type, copy its template,
fill the concept-specific info.*

---

## 2. The adapter TYPES

Each type fixes: what one **step** is, how **stages** sequence, the **required-case** pattern, the **state**
shape, and whether it is **coding** (ships a `canonical_solution`) or **non-coding** (calculation only).

| # | Type | One step is… | Required-case pattern | Coding? | Template |
|---|---|---|---|---|---|
| T1 | **Structured traversal** | visiting the next element via a frontier (queue / stack / recursion / parent-ptr) | first-visit · a representative visit · completion | coding | `tree_inorder` |
| T2 | **Greedy frontier update** | pop a frontier candidate → accept / **relax** / reject | ≥1 accept/relax · ≥1 reject/skip/no-improvement · completion | coding | `kruskal`, `dijkstra` |
| T3 | **Divide & conquer** | a split / base-case / combine | a split · a base case · a combine · completion | coding | `merge_sort` (shipped) |
| T4 | **Search / narrowing** | one probe + the direction it eliminates | go-left · go-right · found/not-found · completion | coding | `binary_search` (shipped) |
| T5 | **Table / DP fill** | computing one cell from the recurrence | a base cell · a recurrence cell · the answer cell | coding | *(planned)* |
| T6 | **Formula application** | applying one governing equation | identify · apply each equation · completion (+ branch) | **non-coding** | `quadratic`, `kinematics` |
| T7 | **Reduction / rewriting** | one rewrite that shrinks the expression | each rewrite kind used · reaches normal form | either | `arithmetic_eval` (shipped) |
| T8a | **Incremental construction** | adding one piece to a growing structure | each construction rule used · partial output stays VALID · target reached | either | *(planned)* |
| T8b | **Formal derivation** | one rule-justified derivation step | each transformation rule used · every step follows an ALLOWED rule · conclusion reached | either | *(planned)* |
| T9a | **Edge-pass relaxation** | one edge relaxation within a numbered PASS | a relax-that-improves · a pass with no change · the `V−1` sufficiency bound | coding | *(planned)* |
| T9b | **Layered state refinement** | process intermediate `k`, update all-pairs `dist[i][j]` | a path improved via `k` · a path unchanged · the last `k`-layer | coding | *(planned)* |
| T10 | **Stateful operation / invariant maintenance** | one operation (mutate/probe/rotate/resize/evict/restore/compress/schedule) + any invariant repair | a repair that propagates · a no-op operation · completion | coding | *(planned)* |
| T11 | **Constraint search / backtracking** | choose a candidate → explore → **undo** on failure | a valid extension · a dead-end that backtracks · a solution found | coding | *(planned)* |
| T12 | **Program execution / memory trace** | executing one statement, updating variable/stack/heap state | a state update · a branch/loop-condition eval · a call push/return | coding | *(planned)* |

### T1 — Structured traversal
> **Not only "iterative".** T1 covers any frontier-driven visit, including RECURSIVE traversal — the gate
> requires queue, stack, **and** recursion. The frontier `mode` is part of the per-concept info:
> `queue_frontier` (BFS) · `stack_frontier` (iterative DFS) · `recursive_call_frontier` (recursive pre/in/post
> order) · `implicit_parent_pointer`. Recursive preorder/postorder are valid T1 without masquerading as iterative.
- **Trace:** one Step per visit; `state = {visited/output so far, current}`; ascending/level/… order.
- **State effects:** one element moves from unvisited → output; the ordering invariant holds.
- **Concepts:** graph BFS/DFS · tree in/pre/post/level-order · linked-list traversal · connected components.
- **Per-concept info:** the *structure* (graph vs tree), the *order rule*, the *frontier `mode`*
  (queue/stack/recursion/parent-ptr), the *visited invariant*, `label_convention`.
> **T1 vs T12.** T1 verifies traversal ORDER + structural visitation. When the objective is recursive
> EXECUTION mechanics (call-stack growth, return timing, base-case unwinding, frame locals), route to **T12**
> instead — a T1 order-only trace cannot teach stack frames.

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
> **Dijkstra's NESTED grammar.** One frontier-pop expands into several out-edge events:
> `pop_candidate · skip_stale_candidate · settle_node · inspect_out_edge · relax_edge · no_improvement · complete`.
> Each edge-relaxation is independently truth-bearing and is grouped DETERMINISTICALLY by the teaching
> projection (§7.3) — never one full card per relaxation (overwhelming), never "settle A" with no reason for the
> distance change (opaque). Kruskal/Prim stay one-candidate-per-step; only Dijkstra needs this subgrammar.
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
  completion). **Truth model:** each step declares a **typed claim ledger** (§7) for inputs/constants/derived/outputs/units;
  the prose-derived numeric allowlist is a SUPPLEMENTAL backstop only, never the source of truth.

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

### T9a — Edge-pass relaxation
> **Bellman-Ford is NOT T2** (frontier-greedy). It relaxes edges over **repeated numbered passes**; its
> invariant is *pass-based* (after pass k, all shortest paths using ≤ k edges are correct); teaching it means
> **why `V−1` passes suffice** + the negative-cycle check.
- **Trace:** Steps grouped by PASS; each is one edge relaxation (improves or not); `state = {distances, pass
  number, changed-this-pass}`. **Concepts:** Bellman-Ford · value/policy iteration.
- **Per-concept info:** the *pass structure*, the *relaxation rule*, the *sufficiency condition*, required
  cases (an improving relax, a no-change pass, the bound).

### T9b — Layered state refinement
> **Floyd-Warshall is NOT the same as Bellman-Ford.** Its invariant is layered, not pass-count: *after
> intermediate vertex `k` is processed, `dist[i][j]` is the shortest `i→j` path whose intermediate vertices all
> lie in the processed set*. An implementer must not give it a Bellman-Ford-shaped trace.
- **Trace:** Steps grouped by intermediate `k`; each updates one `dist[i][j] = min(old, dist[i][k]+dist[k][j])`;
  `state = the matrix + current k`. **Concepts:** Floyd-Warshall · some DP-style all-pairs updates.
- **Per-concept info:** the *k-layer structure*, the *update rule*, the *layer invariant*, required cases (a
  path improved via `k`, a path unchanged, the last layer). **Cap V** — the raw trace is O(V³); project it.

### T10 — Stateful operation / invariant maintenance
> **Broader than heap-restore.** T10 is any stateful system where an operation may need to repair an
> invariant — heaps YES, but also hash probing, LRU eviction, page replacement, scheduling, TCP state,
> dynamic-array resize, union-find compression. Not everything is a sift-down; the operation has a `kind`:
> `mutate · probe · rotate · resize · evict · restore · compress · schedule`.
> (Heap sort is still NOT divide-and-conquer — no split/combine; it *maintains the heap invariant*.)
- **Trace:** each Step is one operation of a declared `kind` + any invariant repair; `state` is the system
  state (heap/table/cache/queue).
- **Concepts:** heap ops · hash probing/rehash · LRU/page replacement · scheduling · AVL rotations · union-find.
- **Per-concept info:** the *invariant*, the *operation kinds*, the *repair* (when triggered), required cases
  (an operation that propagates a repair, a no-op operation, completion).

### T11 — Constraint search / backtracking
- **Trace:** choose a candidate → explore → **undo** when it violates a constraint; `state = {partial
  assignment, remaining choices, decision depth}`. The teaching core is the *undo* — a trace that only ever
  succeeds hides the whole idea.
- **Concepts:** N-Queens · Sudoku · permutations/combinations/subsets · graph coloring · maze solve.
- **Per-concept info:** the *choice set*, the *constraint check*, the *undo*, required cases (a valid
  extension, a dead-end that backtracks, a solution). **The source-size cap is per-adapter, not type-wide** — a
  single "6-cell board" fits nothing: N-Queens `n_max=4`, mini-Sudoku `4x4` with `empty_cells_max=5`,
  permutations `item_count_max=4`, subsets `n_max=5`, maze `grid_max=4x4` + `branch_points_max=2`. Each T11
  adapter DECLARES its cap; the type keeps only the shared event-ceiling + teaching target. Backtracking
  explodes, so the learner-facing projection prunes to representative branches.

### T12 — Program execution / memory trace
- **Trace:** one Step per executed statement; `state = {variables, call stack, heap/refs, output}`. This is the
  substrate under "coding fundamentals" (loops, recursion, pointers, scope) — the reference is a small
  interpreter, not a domain algorithm.
- **Concepts:** variable/assignment · for/while loops · function calls + call stack · recursion frames ·
  pointers/aliasing · array/string indexing.
- **Per-concept info:** the *statement set*, the *state model* (env + stack + heap), required cases (a state
  update, a branch/loop-condition eval, a call push/return). **Cap iterations** so the trace stays bounded.
> **`canonical_solution` for T12 is an executable SPECIMEN**, not a solution to an external problem — a small
> program whose execution is the lesson (e.g. `def sum_until(n): total=0; for i in range(n): total+=i; return total`).

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
| **T9a** Edge-pass relaxation | Bellman-Ford | improving relax + no-change pass + `V−1`/early-stop bound + negative-cycle check | value/policy iteration |
| **T9b** Layered state refinement | Floyd-Warshall | improvement via `k` + unchanged comparison + the layer invariant + final all-pairs state | DP-style all-pairs updates |
| **T10** Stateful transformation | heap sort, heapify | invariant restoration (sift-down) + no-op vs bubbling restore | heap ops, AVL rotations |

**Status is a TEST-BACKED claim, not a label.** A "gate proven" line must cite its evidence — tests + fixtures + reviewed examples:

> **T4: PROVEN** — evidence: `test_bst_search_gate` (two-state-model + fixtures found-left/found-right/absent) · `test_type_contracts.test_t4_search_domain_never_grows_and_net_shrinks` · adapters `binary_search`, `bst_search`.

T2/T3/T7 have production pilots; T1/T6 are in **pilot** (templates shipped, gate not yet
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
7. **Coding only:** a **canonical executable artifact** (`canonical_solutions.py`) — *algorithm* adapters: the
   simplest idiomatic Python solution; *T10 stateful-system* adapters: a canonical operation sequence /
   simulator; *T12 program-trace* adapters: an executable teaching specimen. Other languages are translated
   from the canonical artifact on demand. **Non-coding concepts ship NO canonical artifact.**
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

**The fallback is delivered by the BACKEND, not recovered by the frontend.** Degradation is a decision made
where the truth lives. The backend emits a `WorkedExamplePayload` (`trace_adapters/artifacts.py`):

```python
WorkedExamplePayload(
    verified_text_cards=[...],          # ALWAYS present when a valid trace exists
    compiled_visual_frames=None,        # or the compiled frames
    render_mode="text_only_verified",   # "visual" | "text_only_verified"
    degradation_reason="visual_compile_failure",   # None on the happy path
)
```

The frontend's only job is to render `render_mode`. It NEVER has to reconstruct meaning from a crashed visual
compiler — on any downstream failure the backend has already chosen `text_only_verified` and attached the
reason. An `invalid_trace` produces **no payload** — but the caller receives a structured
`WorkedExampleFailure(reason, adapter_slug, retryable, telemetry_id)` (never a bare `null`), so upstream
handling and observability stay clean.

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

### 7.0 Four layers — raw execution vs. verified semantic transitions

The word "trace" was overloaded (every execution event **and** a bounded learner-meaningful sequence). Those
are DIFFERENT layers. Algorithms whose full execution has far more events than a small ceiling (Floyd-Warshall
~`V³` cell checks, a DP table's every cell, merge sort's every comparison) cannot be "complete AND capped" at
one layer — so we separate four:

| Layer | Large? | Fully retained? | May group events? |
|---|---|---|---|
| **1. Raw execution log** — every low-level event the real algorithm/simulator emits | yes | yes (for the bounded instance) | no |
| **2. Verified semantic trace** — the deterministic adapter-defined educational transitions; the `ContractTrace` that replay / oracle / invariant checks validate | bounded | yes | yes, but only via verified adapter rules |
| **3. Teaching checkpoints** — a selected/grouped subset that controls pacing + preserves required cases | small | no | yes |
| **4. Cards & visual frames** — compiled from checkpoints only | small | no | yes |

Chain: **raw execution → verified semantic trace → teaching checkpoint → card / visual frame.**

> **The summarization rule.** A verified semantic transition MAY summarize a **contiguous, replayable range of
> raw execution events** (Step `raw_event_start`/`raw_event_end`), but it must expose its `prior_state`,
> `state_after`, invariant, and that raw-event range. It may **never** summarize non-contiguous or semantically
> unrelated behaviour. So Floyd-Warshall's `k = B` layer is ONE semantic transition ("2 distances improve, 14
> unchanged; layer verified") folding its `V²` raw cell checks — truth preserved, pacing sane.

> **Reading the §2 type grammars.** Each type's "one Step is …" defines the **raw-event grain**. Where that
> grain would exceed the semantic ceiling, the verified semantic transition folds a **contiguous raw run**:
> **T5** → a dependency-complete cell group (a row / diagonal / bounded run) exposing representative take/skip
> decisions + the resulting state boundary; **T9b** → one intermediate-`k` layer exposing representative
> improved/unchanged comparisons + the verified matrix layer; **T9a** → representative relaxations + the pass
> boundary; **T3** → a recursion phase (split layer · representative base · representative merge · tail-copy ·
> completed run). One-op-per-step types (T1/T4/T6…) have raw grain == semantic grain and fold nothing.

> **Raw logs never ship, and aren't stored forever.** The raw execution log is never in the lesson payload. For
> reproducibility the backend keeps the **full** raw log only for fixture / pilot / failure / sampled-production
> runs; otherwise it keeps only `RawExecutionProvenance(adapter_slug, adapter_version, instance_seed,
> normalized_instance_hash, raw_log_digest)` — enough to deterministically regenerate the exact log on demand.

### 7.1 Trace-size budgets — correctness is not enough

> **Rule.** The full trace may be complete; the **learner-facing projection must obey a trace-size budget**.
> Correctness alone does not stop a 45-card merge sort or a 30-step DP walkthrough.

There is no single "raw ceiling" (that hid a contradiction: a projection can't surface 16 checkpoints from a
12-step trace). Size is governed by **three SEPARATE limits**, each owned by a different layer:

1. **Instance-size cap** — how big the *problem* may be. Owned by the generator's `candidates()`
   (`InstanceShape`, e.g. "6–8 array elements"). This is what stops a 45-card merge sort at the SOURCE.
2. **Verified semantic-transition ceiling** — the max *semantic-trace transitions* (§7.0 layer 2, each of which
   may summarize a contiguous raw-event range) a bounded instance may retain (`manifest.TYPE_TRACE_BUDGET`).
   Enforced by `test_type_contracts` on `len(trace.steps)` across many seeds.
3. **Teaching-checkpoint target** — the count the learner-facing **projection** aims for
   (`manifest.TYPE_TEACHING_TARGET`, always ≤ the semantic ceiling; `manifest_gaps()` rejects an inversion).
   An **absolute learner-facing max** = the semantic ceiling; a projection never exceeds its own source trace.

An adapter whose raw execution runs long (Floyd-Warshall, a full DP table, per-relaxation Dijkstra) keeps every
verified semantic TRANSITION in the trace (≤ ceiling) — each summarizing its contiguous raw range per §7.0 —
and uses **teaching-projection grouping** (§7.3) to land near the target. Grouping may collapse SUPPORTING semantic events only when their aggregate transition stays explicitly
represented by a verified checkpoint (e.g. Dijkstra folding three no-improvement edge checks into "the
remaining out-edges do not improve any distance" — still derived from verified events). **Required-case
events, branch evidence, and the terminal state are never omitted.**

| Type | Instance-size cap (source) | Verified semantic-transition ceiling (enforced) | Teaching-checkpoint target |
|---|---|---|---|
| T1 traversal | ≤ 8 nodes | 12 | 10 |
| T2 greedy frontier | ≤ 6 nodes / 8 edges | 16 | 12 |
| T3 divide & conquer | 6–8 elements | 12 | 10 |
| T4 search | ≤ 15-element domain | 8 | 7 |
| T5 DP | ≤ 5×5 table | 16 | 12 |
| T6 formula | fixed equation set | 8 | 6 |
| T7 rewriting | ≤ 8-token expression | 12 | 10 |
| T8a/T8b construction/derivation | ≤ 8 pieces / rules | 16 | 12 |
| T9a edge-pass (Bellman-Ford) | ≤ 5 nodes / 8 edges | 20 | 14 |
| T9b layered (Floyd-Warshall) | ≤ 4 nodes | 18 | 10 |
| T10 stateful operation | ≤ 8 operations | 16 | 12 |
| T11 backtracking | per-adapter (see T11) | 18 | 12 |
| T12 program execution | ≤ 12 lines executed | 16 | 12 |

> **Example (T3 merge sort).** Instance cap 6–8 elements → the **raw log** records every recursive call, base
> case, merge comparison, and tail copy (well over 12). The **verified semantic trace** derives ≤ 12 bounded
> transitions from contiguous recursion phases (split layer · representative base · representative merge ·
> tail-copy · completed run), each naming its raw-event range (§7.0). The teaching projection then groups
> sibling phases to ~10 checkpoints. The absolute learner-facing max is the semantic trace, never the raw log.

### 7.2 Visual-state budgets — few steps can still overload a frame

A short trace can still produce a dense frame (a full Floyd-Warshall matrix, every Dijkstra distance +
predecessor + heap item at once, a giant recursion tree). `manifest.TYPE_VISUAL_BUDGET` declares a
**machine-testable** budget per type — numeric so a golden/compiler test can *reject* a frame that highlights
too much, not just a prose reminder:

```python
{ "max_focus_entities": 3, "max_new_labels": 4, "max_changed_entities": 5,
  "max_visible_state_groups": 4, "focus_roles": [...], "emphasis": "..." }
```

`focus_roles` is the closed set of roles a frame of that type may emphasize (e.g. T4 = `{probe, eliminated}`;
T9a = `{relax_edge, changed_distance, pass}`; T12 = `{current_line, affected_vars, active_frame}`). A frame
that highlights an entity outside its type's `focus_roles`, or exceeds any numeric cap, is rejected.
`test_type_contracts.test_every_type_has_a_machine_testable_visual_budget` enforces the budget is present and
numeric for every type.

> **Rule.** A frame may preserve full semantic state in DATA, but must **visually emphasize only the minimum
> state needed to understand the current transition** — and that minimum is a *number*, checked in tests, not a
> hope. The visual compiler enforces the per-type budget frame-by-frame.

### 7.3 Teaching-checkpoint selection is ADAPTER-owned & deterministic

Which steps a long trace surfaces (and which support steps it groups) is decided by the **adapter**, via its
deterministic policy `select_teaching_checkpoints(semantic_trace) -> [step_id]` (default: every step; override
to group). The **generator never decides omissions** — letting the LLM pick "representative" DP cells or
Dijkstra relaxations would make it selectively drop truth-bearing transitions. Required-case steps + the
terminal are **always** surfaced regardless of grouping. Ownership across the four layers (§7.0):

- **Adapter** — emits the raw execution log + the verified semantic trace; declares the deterministic
  checkpoint-selection policy. It never returns UI-shaped artifacts.
- **Shared pipeline** — invokes the policy, validates provenance + budget compliance, and normalizes the result
  into `TeachingCheckpoint` artifacts (`teaching_checkpoints`); compiles the cards + visual frames.
- **Generator** — writes prose only, for the already-normalized checkpoints.
- **Frontend** — renders the supplied artifacts only.

**Every checkpoint carries provenance** (`TeachingCheckpoint`, `trace_adapters/artifacts.py`). A checkpoint may
collapse several supporting events into one card, but only if it cites its **complete contiguous
`source_step_ids` range** plus the `state_before`/`state_after` anchors bounding it:

```python
TeachingCheckpoint(
    checkpoint_id="settle_B_relax_neighbours",
    source_step_ids=["pop_B", "settle_B", "inspect_B_C", "relax_B_C", "inspect_B_D", "no_improvement_B_D"],
    visible_transition="settle_and_relax",
    state_before_step_id="pop_B", state_after_step_id="no_improvement_B_D",
    required_cases_covered=["relax", "no_improvement"],
)
```

This gives a full traceability chain — **card / visual frame → checkpoint id → source semantic steps → raw
execution range (§7.0) → verified reference trace** — so a wrong prose line or a mismatched frame is always
traceable to its origin. Every compiled card and `VisualFrame` therefore **carries `checkpoint_id` +
`source_step_ids`**; a frame that cites no checkpoint is rejected.
`test_type_contracts.test_teaching_checkpoints_cite_complete_source_provenance` enforces contiguous, ordered,
fully-covering ranges.

> **Hard boundary — no direct cards.** An adapter may return **only** a verified `ContractTrace` (+ its
> checkpoints). It may NEVER return learner-facing cards or visual frames directly. All cards, checkpoints, and
> frames are compiled through the shared pipeline, so nothing bypasses the manifest / replay / budget / prose
> gates as a local one-off.

### 7.4 Per-instance vs per-suite branch coverage

Some algorithms can't fit every branch into one small, natural example (Dijkstra: relax + no-improvement +
stale-entry + settle; AVL: LL/RR/LR/RL; binary search: left/right/found/absent). So:

> A single generated trace must exercise the **core mechanism + at least one meaningful branch**
> (`must_exercise`, per instance). **All** required branches are guaranteed across saved fixtures + generated
> examples (`must_cover`, per suite). A lesson **may use multiple short examples** when one instance cannot
> teach every branch without becoming contrived.

This is why `bst_search` declares `must_exercise=[descend, found_or_absent, completion]` but
`must_cover=[go_left, go_right, found, absent]`.

### 7.5 Independent oracle for high-risk adapters

`reference(instance)` runs the real computation — but a validator must **not** re-use the same helper it is
validating to check the exact property in question (a bug is then invisible to both). A production or high-risk
adapter declares at least one **independent oracle**: a separately-implemented computation, a trusted library,
or a replayable mathematical property that re-checks the answer/invariant by a different route.

| Adapter | Independent oracle |
|---|---|
| Dijkstra / Bellman-Ford | final distances match an exhaustive shortest-path search on the (tiny) graph |
| Kruskal / Prim | selected edges form a spanning tree; cost matches an independently computed MST |
| Binary / BST search | the returned index holds the target, or the absence condition is proven |
| Gaussian elimination | substitute the solution back into the original equations |
| Quadratic / polynomial | substitute each root into the original polynomial (≈ 0) |
| Matrix multiplication | independently recompute a sample of output cells |

Each oracle carries its **preconditions** in the *per-adapter* declaration (not just this generic table), so an
implementer can't pick the wrong one: Dijkstra's oracle assumes non-negative weights; Bellman-Ford must verify
the negative-cycle classification too; Kruskal/Prim distinguish connected (MST) from disconnected (spanning
forest); Gaussian elimination classifies inconsistent / underdetermined systems separately; quadratic roots use
a float tolerance and handle repeated/complex roots; Floyd-Warshall checks diagonal, unreachable, and
negative-cycle cells separately.

The oracle is **recommended for `pilot`** and **required for `production`** (§8 status) — so no one has to
debate whether Prim or AVL rotations count as "high risk". It is separate from the replay gate (§7.3): replay
proves the trace is *executable*; the oracle proves the *answer* is right by a second, independent method.

---

## 8. The adapter manifest — the machine-readable source of truth

**`status` is defined precisely** (so it can't drift into a subjective label):

- **experimental** — adapter exists locally; may lack full fixture coverage; **never routes** for normal users.
- **pilot** — contract + fixture tests pass; feature-flagged for selected/internal traffic; the type gate (§2.1)
  may still be pending.
- **production** — the type gate passed; acceptance + visual + **replay** + adversarial + regression suites
  pass; an **independent oracle** (§7.5) checks the answer by a second method; routing + fallback behaviour
  tested; reviewed examples meet the quality bar; telemetry + a rollback path are active.

`trace_adapters/manifest.py` holds one entry per adapter: `type` (T1–T12) · `family` · `status`
(production | pilot | experimental) · `verification_level` · `coding` · `canonical_solution` ·
`routing_aliases` · `negative_guards` · `fixtures` · `visual_contract` · `feature_flag` · `telemetry_key` ·
optional `failure_policy` override. (`telemetry_key`/`feature_flag`/`visual_contract` are auto-filled with
defaults — slug / None / `<family>_state_v1` — until authored.) Module-level it also declares
`TYPE_TRACE_BUDGET`, `TYPE_TEACHING_TARGET` (§7.1), `TYPE_VISUAL_BUDGET` (§7.2) and `DEFAULT_FAILURE_POLICY` (§4.1). The Markdown here
stays human-readable; the **manifest is what code enforces**: `manifest_gaps()` cross-checks it against the live
registry + canonical solutions + type trace/visual budgets, and enforces `teaching_target ≤ semantic-transition
ceiling` (`test_type_contracts` fails if they disagree). The per-trace layer relationships — checkpoint source
ranges + semantic-step raw ranges are contiguous (no illegal gap/overlap) — are enforced by
`structural_invariants` + the replay/provenance tests, not the manifest. The `production`-requires-an-oracle
rule (§7.5) is today a **promotion checklist**, not yet a hard `manifest_gaps()` field (an `oracle` manifest
field is the next wire-up). Together these mean an adapter
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
  "shows both a positive and a negative outcome (no oversimplified greedy)". Plus a **trace-replay** invariant
  (`test_trace_replay_is_executable_from_initial_state`): every adapter's trace must replay from
  `initial_state` — each step's `prior_state` equals the previous `state_after` (no hidden mutation, skipped
  transition, or discontinuity) and the terminal state entails the answer — so a chain of individually-plausible
  states that is not actually executable is rejected.
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
4. Coding only: add the **canonical executable artifact** for the adapter type (§3.7) — an idiomatic algorithm
   solution, an operation simulator (T10), or an executable teaching specimen (T12).
5. Register it (`trace_adapters/__init__.py`) + add the tight routing alias + negative guards (§5).
6. Add a **manifest entry** (§8) and named **fixtures** (§9–§10); add it to the adversarial coverage set.
7. Run `test_adapter_conformance`, `test_adapter_artifacts`, `test_trace_prose_adversarial`, and its
   **type-level suite** (§10) — all must pass (0 contract violations, 0 C1 gaps, type invariant holds).
8. Flip its catalog row to ✅ and set the manifest `status`.

> **Do not batch-build.** Ship the first few of a new type, evaluate the worked examples on real topics, pass
> the type gate (§2.1), *then* scale — the template is refined by the *first* adapters of each type, not by
> writing 20 at once.
