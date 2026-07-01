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
| T2 | **Greedy selection** | one accept/reject decision on a candidate | ≥1 accept · ≥1 reject/skip · completion | coding | `kruskal` (shipped) |
| T3 | **Divide & conquer** | a split / base-case / combine | a split · a base case · a combine · completion | coding | `merge_sort` (shipped) |
| T4 | **Search / narrowing** | one probe + the direction it eliminates | go-left · go-right · found/not-found · completion | coding | `binary_search` (shipped) |
| T5 | **Table / DP fill** | computing one cell from the recurrence | a base cell · a recurrence cell · the answer cell | coding | *(planned)* |
| T6 | **Formula application** | applying one governing equation | identify · apply each equation · completion (+ branch) | **non-coding** | `quadratic`, `kinematics` |
| T7 | **Reduction / rewriting** | one rewrite that shrinks the expression | each rewrite kind used · reaches normal form | either | `arithmetic_eval` (shipped) |
| T8 | **Construction / derivation** | adding one piece to a growing structure/proof | each construction rule used · target reached | either | *(planned)* |

### T1 — Iterative traversal
- **Trace:** one Step per visit; `state = {visited/output so far, current}`; ascending/level/… order.
- **State effects:** one element moves from unvisited → output; the ordering invariant holds.
- **Concepts:** graph BFS/DFS · tree in/pre/post/level-order · linked-list traversal · connected components.
- **Per-concept info:** the *structure* (graph vs tree), the *order rule*, the *frontier* (queue/stack/recursion),
  the *visited invariant*, `label_convention` (letters for graph nodes, ints for values).

### T2 — Greedy selection
- **Trace:** one Step per candidate considered; `decision ∈ accept|reject`; `state = {result so far, remaining}`.
- **Concepts:** Kruskal · Prim · Dijkstra (relaxation) · activity selection · Huffman · fractional knapsack.
- **Per-concept info:** the *candidate order* (e.g. edges sorted by weight), the *accept criterion* (no cycle /
  improves distance), the *result* being built (MST edges / distances), the *`forbidden_claims`* that catch an
  inverted decision (accept-vs-skip), required cases (an accept **and** a reject/skip).

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

### T8 — Construction / derivation
- **Trace:** one Step per piece added; `state = the partial construction`; the target grows monotonically.
- **Concepts:** balancing chemical equations · matrix multiplication · truth tables · sieve of Eratosthenes ·
  journal entries · induction (structure).
- **Per-concept info:** the *construction rule*, the *target*, required cases (each rule used, target reached).

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

## 7. Reusable patterns (learned building the templates)

- **`allowed_values` from prose (T6/T7).** For a computation, derive each step's numeric allowlist by scanning
  that step's OWN verified prose (`_ints(decision, reason, evr, *fact_texts)`). A faithful card then passes
  while an invented number is still caught — and formula constants (the `2` in b², the `4` in 4ac), units, and
  signs don't false-flag. The **last step also includes the final-answer values** (the completion suffix
  restates the whole answer).
- **Structured facts.** `required_facts=[fact(predicate, text, value)]` — never bare strings.
- **Bounded instances.** `candidates()` must keep the trace small (T5 especially — cap the table).
- **No hardcoding.** Values come from a seeded generator; the algorithm is the adapter's `reference()`.

---

## 8. Build a new adapter — the workflow

1. Find the concept in `ADAPTER_CATALOG.md`; note its **type** (§2) and **family**.
2. Copy the type's template class into the family module (create the family module if new).
3. Fill the **per-concept info** (§3) from the type's info list.
4. Coding only: add the `canonical_solution` (simplest idiomatic Python).
5. Register it (`trace_adapters/__init__.py`) + add the tight routing alias (§5).
6. Add it to the adversarial coverage set; run `test_adapter_conformance`, `test_adapter_artifacts`,
   `test_trace_prose_adversarial` — all must pass (0 contract violations, 0 C1 gaps).
7. Flip its catalog row to ✅.

> **Do not batch-build.** Ship the first few of a new type, evaluate the worked examples on real topics, then
> scale — the template is refined by the *first* adapters of each type, not by writing 20 at once.
