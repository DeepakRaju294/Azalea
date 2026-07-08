# Adapter Taxonomy Spec — the verified-trace type system

> **Purpose.** Define **every adapter type** the worked-example system implements or will implement, and the
> **single axis** they are classified on. An adapter turns a concept into a **verified trace** (steps whose values
> are re-computed and checked, not model-authored) that the teaching + visual pipelines render. This document is
> the map: the type grammars, how a new concept is assigned one, what each type's gate guarantees, and the
> authoring backlog.
>
> **Core principle — classify by TRACE GRAMMAR, not by domain.** The catalog is enormous by *concept* (600+) but
> small by *trace shape*. "Ohm's law," "kinetic energy," and "compound interest" are the **same type** (plug values
> into a formula → substitute → compute → units → answer); "Dijkstra" and "Prim" are the same type (greedy frontier
> update). A concept's type is the **shape of its verified trace**, never its subject area. This is what keeps the
> catalog finite and the authoring cost low.
>
> **Status.** All **18 types are now LIVE** (188 adapters, `manifest_gaps()` CLEAN). The four types added in the
> last revision — T13 proofs, T14 tabular evaluation, T15 matrix row-reduction, T16 numerical convergence — are
> now implemented as declarative engines with their own gates (each keeps the "ran ≠ correct" guarantee; see §3/§5).
> **Durable taxonomy = 18 trace grammars across 8 declarative engines (Family B) + the hand-coded CS families
> (Family A).**

---

## 1. The three macro-families

| Family | What the trace is | Backing | Adding a concept |
|---|---|---|---|
| **A — Algorithmic execution traces** (CS) | line → state-delta of *running an algorithm* on a concrete input; verified by an **executable reference** | **hand-coded adapter classes** (one per algorithm family) | write/extend an adapter class + its gate |
| **B — Declarative generators** (math / science / finance) | the **spec IS the content** — a deterministic step script over declared givens; verified by an **independent oracle** | **8 declarative type-engines** (T6/T7/T8a/T8b/T10/T13/T14/T15/T16); a concept is a **DATA SPEC** | append one spec to `families/*_specs.py` (**one-file edit**, gate-verified) |
| **C — Guided / source-grounded** (conceptual) | prose with **no verifiable trace** (intuition, real-world meaning, open-ended proof) | not an adapter | authored as guided content; policed by Q24 free-text validation, never claimed as verified |

Family B is where breadth scales: *"turn each dominant trace shape into an ENGINE, then add each concept as data
gated by the type's test."* All eight Family-B engines (incl. the four newest — T13/T14/T15/T16) are live. Family A
is bounded and hand-authored (the algorithmic set is finite). Family C is the honest home for anything without a
machine-checkable trace — it is not forced into an adapter.

---

## 2. The full type table (authoritative)

Keyed to `app/services/examples/trace_adapters/manifest.py::ADAPTER_TYPES`.
**18 live types, 188 adapters, `manifest_gaps()` CLEAN.**

| Type | Trace grammar | Family | Status / backing | Adapters | Example concepts |
|---|---|---|---|---|---|
| **T1** | `structured_traversal` | A | LIVE · hand-coded | 7 | bfs, dfs, topological_sort, tree_{pre,in,post,level}order |
| **T2** | `greedy_frontier_update` | A | LIVE · hand-coded | 3 | dijkstra, prim, kruskal |
| **T3** | `divide_and_conquer` | A | LIVE · hand-coded | 2 | merge_sort, quick_sort |
| **T4** | `search_narrowing` | A | LIVE · hand-coded | 2 | binary_search, bst_search |
| **T5** | `dp_table_fill` | A | LIVE · hand-coded | 2 | coin_change, longest_increasing_subsequence |
| **T9a** | `edge_pass_relaxation` | A | LIVE · hand-coded | 1 | bellman_ford |
| **T9b** | `layered_state_refinement` | A | LIVE · hand-coded | 1 | floyd_warshall |
| **T11** | `constraint_search_backtracking` | A | LIVE · hand-coded | 1 | n_queens |
| **T12** | `program_execution_memory_trace` | A | LIVE · hand-coded | 1 | euclid_gcd |
| **T6** | `formula_application` | B | LIVE · formula_engine | 101 | newtons_second_law, ohms_law, kinetic_energy, compound_interest, molarity, descriptive_stats |
| **T7** | `reduction_rewriting` | B | LIVE · rewrite_engine | 9 | linear_equation, combine_like_terms, distribute, solve_proportion |
| **T8a** | `incremental_construction` | B | LIVE · construct_engine | 20 | prefix_sums, fibonacci, pascals_triangle_row, polynomial_derivative/integral, gradient_descent |
| **T8b** | `formal_derivation` | B | LIVE · derivation_engine | 16 | complete_the_square, difference_of_squares, exponent_laws, sum_geometric_series, foil_expansion |
| **T10** | `stateful_operation_invariant_maintenance` | B | LIVE · stateful_engine | 8 | stack, queue, hash_table_insert, lru_cache, min_stack |
| **T13** | `proof_obligation_discharge` | B | LIVE · induction_engine | 4 | induction: sum of first n / squares / cubes / odds (machine-checked base + inductive-step identity) |
| **T14** | `indexed_table_evaluation` | B | LIVE · table_engine | 4 | truth tables (A∧(B∨C), XOR, implication, majority); grammar covers K-maps / transition / probability tables |
| **T15** | `matrix_row_operation_elimination` | B | LIVE · rowreduce_engine | 3 | solve 2×2/3×3 linear systems, Gaussian/Gauss-Jordan elimination (Cramer oracle) |
| **T16** | `numerical_time_step_convergence` | B | LIVE · numerical_engine | 3 | Newton sqrt/cbrt, linear fixed-point (residual + convergence check) |

> `manifest_gaps()` is **CLEAN** — every declared adapter is registered with a routing rule + declaration.
> The four newest engines pilot a few concepts each; more are one-file DATA edits (§6).

---

## 3. The four newest types (T13–T16) — grammar, distinctness, gate

Each is a **live Family-B engine** (v1 pilots; more concepts are one-file data edits). Its verification invariant
is stated up front, because a new type must *keep* the gate's "ran ≠ correct" guarantee, not relax it. Where a
concept's truth is not machine-checkable, it is **not** a T13–T16 adapter — it is Family C (guided).

### T13 — `proof_obligation_discharge`
```
Grammar:   assumptions → subgoal → justified inference → discharged obligation → conclusion
Distinct:  T8b requires equality/identity preservation at EVERY step. A proof is not equality-preserving — it
           introduces assumptions, opens scoped subgoals, and discharges obligations. Induction, contradiction,
           contrapositive, invariant, existence/uniqueness, correctness, termination, and big-O proofs all fail
           the T8b invariant.
Gate:      each inference cites a registered rule; each obligation is MACHINE-CHECKABLE for the supported schema
           (induction: base + step both verified for the concrete predicate; big-O: an explicit (c, n0) witness
           checked over a bound; loop invariant: holds initially, preserved by the body, implies the postcondition
           on exit). An open-ended proof with no checkable obligation model is Family C, never a fake T13 adapter.
Coverage:  v1 = polynomial summation identities (sum of first n / squares / cubes / odds); more proof schemas
           (contradiction, big-O witness, loop invariants) extend §6.
```

### T14 — `indexed_table_evaluation`
```
Grammar:   select index/cell → apply a LOCAL rule → compute/store the cell → verify a table invariant
Distinct:  T5 is DP with OPTIMAL SUBSTRUCTURE (a cell is a recurrence over other cells). Many core tables are
           INDEPENDENT per-cell evaluations with a different invariant: a truth table row, a K-map cell, an FSM
           transition, a joint-probability cell, a convolution/DFT output tap.
Gate:      each cell recomputed from its local rule + inputs; a table-level invariant checked (rows exhaustive /
           probabilities sum to 1 / K-map groups cover exactly the on-set / convolution length = n+m−1).
Coverage:  digital logic (truth tables, K-maps), signals (convolution, DFT), probability tables.
```

### T15 — `matrix_row_operation_elimination`
```
Grammar:   choose pivot → apply a row/column operation → update the structured matrix → classify/solve
Distinct:  T7 is SCALAR rewriting (one algebraic rule to a normal form). Row reduction's teaching atom is a
           STRUCTURED row operation with pivot selection over a whole matrix, with matrix-level invariants and a
           final classification (unique / none / infinite; rank; nullity).
Gate:      each row op is a verified elementary linear transformation (the represented linear system / solution set
           is PRESERVED); the final classification is checked against an independent solver (rank, RREF).
Coverage:  linear algebra (Gaussian/Gauss-Jordan, LU, inverse-by-reduction, rank/nullity) and EE (nodal, mesh).
```

### T16 — `numerical_time_step_convergence`
```
Grammar:   current approximation/state → update rule → error/residual → stopping/convergence check
Distinct:  T8a "adds one valid piece" with a validity predicate — it does NOT model tolerance, residual, step
           size, stability, or time-indexed evolution. A numerical method's educational point is WHETHER and WHY
           it converges, which needs a verified residual + a stopping criterion, not just "another value appeared."
Gate:      each iterate recomputed by the update rule; the residual/error is computed and its trend checked against
           the method's guarantee (monotone decrease / contraction / order); the stopping test (|Δ| < tol, or
           residual < tol, or max_iters) is verified. Divergence is a legitimate, labeled outcome, not a failure.
Coverage:  root-finding (Newton-Raphson, fixed-point, bisection-as-root-find), ODE (Euler, RK), iterative solvers,
           numerical integration; several finance/EE iterative concepts (IRR, backward induction, filter recurrence).
```

---

## 4. The classification decision procedure (assigning a new concept a type)

Ask, in order — the first match wins:

```text
0. Is the truth machine-checkable at all? If there is no verifiable trace (open-ended proof, intuition,
   real-world meaning) → Family C (guided/source-grounded), NOT an adapter.

1. Does the concept RUN AN ALGORITHM over an input, its truth an EXECUTION? → Family A:
   - visits nodes/edges along a structure           → T1 structured_traversal
   - repeatedly picks the best frontier item         → T2 greedy_frontier_update   (carry g/h/f as facts for A*)
   - splits, recurses, recombines                    → T3 divide_and_conquer
   - halves/narrows a search range                   → T4 search_narrowing         (bisection lives here by SHAPE)
   - fills a DP table by RECURRENCE                   → T5 dp_table_fill
   - relaxes every edge over passes                  → T9a edge_pass_relaxation
   - refines an all-pairs matrix in layers           → T9b layered_state_refinement
   - explores + backtracks under constraints         → T11 constraint_search_backtracking
   - steps raw program memory line-by-line           → T12 program_execution_memory_trace

2. Else it is a MATH/SCIENCE derivation → Family B, by trace shape:
   - plug known values into a formula, compute, units          → T6 formula_application
   - apply ONE allowed rewrite rule per step to a normal form  → T7 reduction_rewriting
   - ADD one valid piece to a growing structure per step       → T8a incremental_construction
   - each step JUSTIFIED BY A NAMED RULE, value preserved      → T8b formal_derivation
   - a structure MUTATES (grows AND shrinks) under operations  → T10 stateful_operation_invariant_maintenance
   - assumptions → discharged obligations → conclusion         → T13 proof_obligation_discharge
   - independent per-cell evaluation over an indexed table      → T14 indexed_table_evaluation
   - pivot + structured row operation over a matrix            → T15 matrix_row_operation_elimination
   - iterate + residual + convergence/stopping check           → T16 numerical_time_step_convergence
```

**Tie-breaks (what the learner must SEE proven wins):**
- `complete_the_square` → **T8b** (each step cites a named identity), not T6.
- `gradient_descent`, `babylonian_sqrt` → today **T8a**; migrate to **T16** once convergence/tolerance is modeled.
- `bisection` → **T4** by its search-narrowing shape; `newton_raphson` → **T16** (residual/convergence is the point).
- induction / contradiction / correctness / termination → **T13**, moved OUT of T8b (they are not equality-preserving).
- Karnaugh-map simplification → **T14** (the grid/table is part of the truth), not T7.
- synchronous FSM / clocked flip-flops → start as a **T10** specialization; may earn a sub-grammar if simultaneous
  state updates prove awkward.
- symbolic-calculus rewrites (chain/product/quotient rule, u-sub, parts, partial fractions) → **T7-deferred**
  behind a CAS/`sympy` policy; not shipped as unverified "rewrite data rows."

---

## 5. Per-type gate invariant (what verifies "correct", not just "ran")

- **Family A (T1–T5, T9, T11, T12):** an **executable reference** runs the real algorithm; every card's
  `state_after` must equal the reference state at that step, and prose numbers must be values the run actually held
  (`code_execution_trace` / `node_link_trace` / `grid_table_trace` / `sequence_state_trace`).
- **T6 formula:** re-evaluate every `Output` in a sealed namespace vs the shown substituted equation; units separate.
- **T7 rewrite:** apply each rule for real (before → after); answer vs **independent oracle** + solution satisfies
  the original — invariant is **solution-set preservation**.
- **T8a construction:** a **validity predicate** holds after *every* piece; answer vs oracle.
- **T8b derivation:** value/identity **preserved at each named-rule step**; answer vs oracle.
- **T10 stateful:** an independent **replay oracle** reproduces the final state after the operation script.
- **T13 proof:** every obligation discharged by a checkable schema (v1: induction base + inductive-step polynomial
  identity by multi-point evaluation); a wrong closed form is rejected; un-checkable ⇒ Family C.
- **T14 table:** each cell recomputed locally + a table invariant (v1: exhaustive 2^n rows); column vs recompute.
- **T15 row reduction:** each row op preserves the represented system (solution satisfies every intermediate
  matrix); final solution vs an independent Cramer's-rule oracle.
- **T16 numerical:** each iterate recomputed; residual non-increasing + stopping test verified; converged estimate
  close to an independent oracle (within tolerance).

The trace is ground truth; **`TRACE_TO_TEACHING_CONTRACT_SPEC` (Q23)** + **`FREE_TEXT_CONTENT_VALIDATION_SPEC`
(Q24)** keep the *prose* honest to it.

---

## 6. Authoring backlog (by type) — the priority queue

The live catalog has saturated the clean/generic concepts within the 5 live engines. The backlog below is the
**high-value coverage** for an EECS / Math / Quant audience. It is a living list (non-exhaustive); each item is
one adapter class (Family A) or one data spec (Family B) unless marked *later*/*CAS*/*guided*.

**Priority order:** `T15 row reduction → T13 proofs → T14 tables → T16 numerical`, then the within-existing-type
expansions (DP, data-structure ops, program-memory traces, digital-logic/circuit rows, signals rows).

### Newest-engine families (engines LIVE — remaining items are one-file data rows / a hand-coded schema per row)
```text
T13 proofs:      direct, contrapositive, contradiction, (strong) induction, set-equality, divisibility,
                 existence/uniqueness, loop-invariant, algorithm-correctness, termination, recurrence, big-O
                 (explicit witness), epsilon-delta-lite.
T14 tables:      truth_table, karnaugh_map_grouping, fsm_transition_table, joint/conditional_probability_table,
                 contingency_table, binomial_distribution_table, decision_tree_expected_value, convolution_output,
                 dft_coefficient_table, payoff_matrix.
T15 row reduce:  gaussian_elimination, gauss_jordan, solve_linear_system, augmented_matrix, LU_factorization,
                 inverse_by_row_reduction, rank_nullity; EE: nodal_analysis, mesh_analysis.
T16 numerical:   newton_raphson, fixed_point_iteration, bisection_root, secant_method, euler_method, rk4,
                 numerical_integration (trapezoid/simpson), iterative_linear_solver (jacobi/gauss-seidel);
                 finance: newton_irr, binomial_backward_induction, monte_carlo_estimate (later).
```

### Family A — algorithms & data structures (largest CS gap)
```text
T1 traversal:    connected_components, bipartite_check, cycle_detection_{undirected,directed}, SCC (two-phase),
                 topological_sort_kahn, trie_search, linked_list_traversal, tree_height, expression_tree_eval.
T2 greedy:       a_star (g/h/f facts), best_first, huffman, interval_scheduling, activity_selection,
                 fractional_knapsack, job_sequencing, boruvka_mst; nearest_neighbor_tsp (heuristic-labeled).
T3 d&c:          count_inversions, quickselect, closest_pair, karatsuba; strassen (later, heavy visuals).
T4 search:       lower_bound, upper_bound, first/last_occurrence, search_rotated, binary_search_on_answer,
                 ternary_search.
T5 dp:           0/1_knapsack, unbounded_knapsack, edit_distance, LCS, LC_substring, matrix_chain, rod_cutting,
                 subset_sum, partition_equal_subset, word_break, house_robber, climbing_stairs, unique_paths,
                 min_path_sum, grid_obstacle_paths, max_subarray, palindromic_sub{sequence,string}.
                 (subfamilies: 1D recurrence · 2D alignment · grid path · capacity/knapsack · interval · bitmask —
                  same T5 grammar, not new types.)
T10 structures:  linked_list_{insert,delete,reverse}, doubly_linked_list, bst_{insert,delete}, avl_rotation,
                 heap_{insert,extract_min,heapify}, union_find_{union,find,path_compression},
                 hash_table_{chaining,linear_probing,quadratic_probing}, circular_queue, deque, priority_queue,
                 trie_{insert,delete}, bitset_ops.  (avl + union-find are high-value for interview prep.)
T11 backtrack:   permutations, subsets, combinations, combination_sum, sudoku_4x4, word_search, rat_in_a_maze,
                 graph_coloring, generate_parentheses, palindrome_partitioning, partition_k_equal_subsets.
T12 memory:      loop_trace, nested_loop_trace, recursion_call_stack, recursive_binary_search,
                 merge_sort_call_stack, reference_vs_value, array_mutation, linked_list_pointer_rewiring,
                 two_pointer_trace, sliding_window_trace, class_object_state, closure_capture, stack_vs_heap.
                 (essential for beginner programming, independent of any "algorithm".)
```

### Family B — math / science / EE / quant data rows (existing engines)
```text
T6 calculus:     derivative_at_point, limit_eval, tangent_line, linear_approximation, definite_integral_area,
                 average_value, ftc, partial_derivative, directional_derivative, gradient_magnitude, div, curl.
T6 lin-alg:      vector_magnitude, dot/cross_product, angle_between, projection_{vector,subspace}, matrix_add,
                 scalar_matrix_mult, matrix_vector_mult, matrix_mult_entry, det_{2x2,3x3}, trace, eigenvalue_check,
                 norms_{l1,l2,linf}, cosine_similarity.
T6 prob/stats:   conditional_probability, bayes_rule, expected_value, variance, std_dev, covariance, correlation,
                 z_score, normal_probability, confidence_interval, hypothesis_test_stat, weighted_mean,
                 binomial/geometric/poisson_probability.
T6 quant/fin:    present_value, npv, bond_price, ytm, portfolio_return, portfolio_variance, sharpe, beta, capm,
                 option_payoff, put_call_parity, forward_price, discount_factor; black_scholes (needs numerics+units).
T6 EE:           series_parallel_{resistance,impedance}, voltage/current_divider, power_dissipation, complex_impedance,
                 power_factor, complex_power, three_phase_power, transfer_function_eval, bode_{magnitude,phase}_point.
T7 rewrite:      factor_quadratics, rational_expr_simplify, radical_simplify, complex_number_simplify,
                 conjugate_rationalize, log/exp_equation, absolute_value_equation, inequality_solving,
                 systems_{substitution,elimination}, boolean_simplify, de_morgan.  (calculus rules → CAS-deferred.)
T8a construct:   arithmetic/geometric_sequence, taylor/maclaurin_polynomial, lagrange_interpolation,
                 finite_difference_table, histogram_bins, empirical_cdf, moving_average, ema, cumulative_return,
                 amortization_schedule, cash_flow_schedule, binomial_option_tree, markov_distribution_steps,
                 pagerank_iteration; EE: sampled_sine, impulse_response, fir_output_sequence.
                 (convergence-bearing ones may migrate to T16.)
T8b derive:      derive_quadratic_formula, derive_distance_formula, derive_arithmetic_series, derive_compound_interest,
                 derive_{voltage,current}_divider, derive_series_parallel_resistance, derive_kinematics,
                 derive_geometric_series_closed_form, derive_binomial_theorem_small_n, derive_expectation_linearity,
                 derive_variance_scaling.  (RC/RL charging → later, needs ODE/T16 support.)
EE digital/DSP:  → T14 (truth tables/K-maps/convolution/DFT) · T10 (flip-flops/counters/registers/ALU/FSM) ·
                 T3 (FFT) · T15 (nodal/mesh) · T16 (filter recurrence / transient samples).  binary_addition,
                 twos_complement, floating_point_representation, cache_mapping → T14 / T12 as fits.
```

---

## 7. Invariants (binding)

- **Type = trace grammar, never domain.** A new concept is filed by §4; its subject area is metadata.
- **A row is done when its gate verifies the answer independently**, not when the engine ran.
- **A new TYPE is added only for a genuinely new verified-trace shape** (T13–T16 qualify; a per-subject visual
  difference does not). Do not mint a type per EE/math topic.
- **A new type must not weaken the gate.** If a concept's truth isn't machine-checkable, it is Family C (guided),
  not a fake adapter — this is the honest boundary for open-ended proofs and CAS-only symbolic calculus.
- **Adding a Family-B concept is a one-file DATA edit** once its engine exists; changing engine behavior is a rare,
  test-gated event.
- **Every adapter ships its walkthrough deterministically** (the spec/trace IS the content — no LLM in the value
  path); where a concept has a coding treatment it is deterministic too, else it defers.
