# Adapter Taxonomy Spec — the verified-trace type system

> **Purpose.** Define **every adapter type** the worked-example system implements, and the **single axis** they are
> classified on. An adapter turns a concept into a **verified trace** (steps whose values are re-computed and
> checked, not model-authored) that the teaching + visual pipelines render. This document is the map: what the
> types are, how a new concept is assigned one, and what each type's gate guarantees.
>
> **Core principle — classify by TRACE GRAMMAR, not by domain.** The catalog is enormous by *concept* (600+) but
> tiny by *trace shape*. "Ohm's law," "kinetic energy," and "compound interest" are the **same type** (plug values
> into a formula → substitute → compute → units → answer); "Dijkstra" and "Prim" are the same type (greedy frontier
> update). A concept's type is the **shape of its verified trace**, never its subject area. This is what makes the
> catalog finite and the authoring cost low.

---

## 1. The two macro-families

| Family | What the trace is | Backing | Adding a concept |
|---|---|---|---|
| **A — Algorithmic execution traces** (CS) | line → state-delta of *running an algorithm* on a concrete input; verified by an **executable reference** | **hand-coded adapter classes** (one class per algorithm family) | write/extend an adapter class + its gate |
| **B — Declarative generators** (math / science / finance) | the **spec IS the content** — a deterministic step script over declared givens; verified by an **independent oracle** | **five declarative type-engines**; a concept is a **DATA SPEC** | append one spec to `families/*_specs.py` (**one-file edit**, gate-verified) |

Family B is where breadth scales: *"turn each dominant trace shape into an ENGINE, then add each concept as data
gated by the type's test."* Family A is largely complete — the algorithmic set is bounded and hand-authored.

---

## 2. The full type table (authoritative)

Keyed to `app/services/examples/trace_adapters/manifest.py::ADAPTER_TYPES`. **14 types, 174 adapters today.**

| Type | Trace grammar | Family | Backing | Live | Example concepts |
|---|---|---|---|---|---|
| **T1** | `structured_traversal` | A | hand-coded | 7 | bfs, dfs, topological_sort, tree_{pre,in,post,level}order |
| **T2** | `greedy_frontier_update` | A | hand-coded | 3 | dijkstra, prim, kruskal |
| **T3** | `divide_and_conquer` | A | hand-coded | 2 | merge_sort, quick_sort |
| **T4** | `search_narrowing` | A | hand-coded | 2 | binary_search, bst_search |
| **T5** | `dp_table_fill` | A | hand-coded | 2 | coin_change, longest_increasing_subsequence |
| **T9a** | `edge_pass_relaxation` | A | hand-coded | 1 | bellman_ford |
| **T9b** | `layered_state_refinement` | A | hand-coded | 1 | floyd_warshall |
| **T11** | `constraint_search_backtracking` | A | hand-coded | 1 | n_queens |
| **T12** | `program_execution_memory_trace` | A | hand-coded | 1 | euclid_gcd |
| **T6** | `formula_application` | B | **formula_engine** | 101 | newtons_second_law, ohms_law, kinetic_energy, compound_interest, molarity, circle_area, descriptive_stats |
| **T7** | `reduction_rewriting` | B | **rewrite_engine** | 9 | linear_equation, combine_like_terms, distribute, simplify_fraction, solve_proportion |
| **T8a** | `incremental_construction` | B | **construct_engine** | 20 | prefix_sums, fibonacci_sequence, pascals_triangle_row, polynomial_derivative, polynomial_integral, gradient_descent, babylonian_sqrt, depreciation_schedule |
| **T8b** | `formal_derivation` | B | **derivation_engine** | 16 | complete_the_square, difference_of_squares, exponent_laws, log_product_law, sum_geometric_series, foil_expansion |
| **T10** | `stateful_operation_invariant_maintenance` | B | **stateful_engine** | 8 | stack_operations, queue_operations, hash_table_insert, lru_cache, min_stack, set_operations |

> `manifest_gaps()` is **CLEAN** — every declared adapter is registered and every registered adapter has a routing
> rule + declaration. There is no backlog of unwired adapters.

---

## 3. The classification decision procedure (assigning a new concept a type)

Ask, in order — the first match wins:

```text
1. Does the concept RUN AN ALGORITHM over an input, and is its truth an EXECUTION? → Family A:
   - visits nodes/edges along a structure          → T1 structured_traversal
   - repeatedly picks the best frontier item        → T2 greedy_frontier_update
   - splits, recurses, recombines                   → T3 divide_and_conquer
   - halves/narrows a search range                  → T4 search_narrowing
   - fills a DP table cell-by-cell                   → T5 dp_table_fill
   - relaxes every edge over passes                  → T9a edge_pass_relaxation
   - refines an all-pairs matrix in layers           → T9b layered_state_refinement
   - explores + backtracks under constraints         → T11 constraint_search_backtracking
   - steps raw program memory line-by-line           → T12 program_execution_memory_trace

2. Else it is a MATH/SCIENCE derivation → Family B, by trace shape:
   - plug known values into a formula, compute, attach units   → T6 formula_application
   - apply ONE allowed rewrite rule per step to a normal form  → T7 reduction_rewriting
   - ADD one valid piece to a growing structure per step       → T8a incremental_construction
   - each step JUSTIFIED BY A NAMED RULE/law                    → T8b formal_derivation
   - a structure MUTATES (grows AND shrinks) under operations   → T10 stateful_operation_invariant_maintenance
```

**Tie-breaks.** A concept that *could* read as two types is assigned by what the learner must SEE proven:
`complete_the_square` is **T8b** (each algebra step cites a named identity), not T6, because the teaching value is
the justified derivation, not a single plug-in. `gradient_descent`/`babylonian_sqrt` are **T8a** (iterative
refinement builds a sequence of estimates), not T6. A concept whose rule transforms need a CAS (chain rule,
non-polynomial integrals) is **T7-deferred** (see §5).

---

## 4. Per-type invariant (what each gate verifies — "ran" ≠ "correct")

A data row is **done** only when its type gate independently re-derives the answer:

- **Family A (T1–T5, T9, T11, T12):** an **executable reference** runs the real algorithm; every card's
  `state_after` must equal the reference state at that step, and prose numbers must be values the run actually held
  (the `code_execution_trace` / `node_link_trace` / `grid_table_trace` / `sequence_state_trace` grammars).
- **T6 formula:** re-evaluate every `Output` in a sealed namespace and compare to the shown substituted equation;
  units checked separately.
- **T7 rewrite:** apply each rule for real (before → after) and check the extracted answer against an **independent
  oracle** + that the solution satisfies the original — the invariant is **solution-set preservation**.
- **T8a construction:** a **validity predicate** must hold after *every* added piece; answer vs oracle.
- **T8b derivation:** value/identity **preserved at each named-rule step**; answer vs oracle.
- **T10 stateful:** an independent **replay oracle** reproduces the final state after the operation script.

This is why the two prose gates matter: the trace is ground truth, and **`TRACE_TO_TEACHING_CONTRACT_SPEC`
(Q23)** + **`FREE_TEXT_CONTENT_VALIDATION_SPEC` (Q24)** keep the *prose* honest to it.

---

## 5. Coverage status & the remaining tail

**The type system is complete and all five Family-B engines are live.** Autonomous data-authoring has reached
**saturation of the clean, generically-safe, verifiable concepts.** What remains is **not** a fixed backlog of
adapters — it is demand-driven data rows plus three gated items:

```text
- More Family-B data rows: one-file edits to families/*_specs.py, as demand warrants (no engine change).
- CAS-backed symbolic calculus (chain rule, non-polynomial integrals): a T7 variant BLOCKED on a `sympy`
  dependency decision, not on authoring.
- Constraint-heavy / 2-list concepts (correlation, trig ratios): each needs a per-concept guard; authored
  individually, not in a wave.
- Part-C conceptual topics (no verifiable trace): intentionally NOT adapters — they stay guided/source-grounded.
```

**Explicitly not planned as new types:** the 14 grammars above cover formula / rewrite / grow / derive / mutate +
the CS execution families. A genuinely new *trace shape* (e.g. continuous ODE integration = T9 numeric) would earn
a new type only if a concept cannot be expressed in an existing grammar; today none require it.

---

## 6. Invariants (binding)

- **Type = trace grammar, never domain.** A new concept is filed by §3, and its subject area is metadata.
- **A row is done when its gate verifies the answer independently**, not when the engine ran.
- **Adding a Family-B concept is a one-file DATA edit**; changing engine behavior is a rare, test-gated event.
- **Every adapter ships its walkthrough deterministically** (the spec/trace IS the content — no LLM in the value
  path); where a concept has a coding treatment it is deterministic too, else it defers.
- **New types are added only for a genuinely new verified-trace shape**, never to accommodate a domain.
