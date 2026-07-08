# Adapter Catalog — the full running list

> **Auto-generated from `app/services/examples/trace_adapters/manifest.py::MANIFEST` (the source of
> truth)** by `backend/gen_adapter_catalog.py`. Regenerate after adding adapters. Companion to
> `ADAPTER_TAXONOMY_SPEC.md` (which defines the *types*); this lists every *adapter*, grouped by type.
> Each row is `slug · family · trace|coding` (`coding` = also has a deterministic coding walkthrough;
> `trace` = ships its walkthrough from the verified trace).

**201 adapters · 18 types · manifest_gaps() = CLEAN**

## Family A — algorithmic execution traces (hand-coded)

### T1 — `structured_traversal` (7) · hand-coded

- `bfs` · graph · coding
- `dfs_iter` · graph · coding
- `topological_sort` · graph · coding
- `tree_inorder` · trees · coding
- `tree_levelorder` · trees · coding
- `tree_postorder` · trees · coding
- `tree_preorder` · trees · coding

### T2 — `greedy_frontier_update` (3) · hand-coded

- `dijkstra` · graph · coding
- `kruskal` · graph · coding
- `prim` · graph · coding

### T3 — `divide_and_conquer` (2) · hand-coded

- `merge_sort` · sequence · coding
- `quick_sort` · sequence · coding

### T4 — `search_narrowing` (2) · hand-coded

- `binary_search` · sequence · coding
- `bst_search` · trees · coding

### T5 — `dp_table_fill` (6) · hand-coded

- `coin_change` · dynamic_programming · coding
- `edit_distance` · dynamic_programming · trace
- `house_robber` · dynamic_programming · trace
- `longest_increasing_subsequence` · dynamic_programming · coding
- `max_subarray` · dynamic_programming · trace
- `rod_cutting` · dynamic_programming · trace

### T9a — `edge_pass_relaxation` (1) · hand-coded

- `bellman_ford` · graph · coding

### T9b — `layered_state_refinement` (1) · hand-coded

- `floyd_warshall` · graph · coding

### T11 — `constraint_search_backtracking` (1) · hand-coded

- `n_queens` · backtracking · coding

### T12 — `program_execution_memory_trace` (1) · hand-coded

- `euclid_gcd` · execution · coding

## Family B — declarative generators (one-file data specs on live engines)

### T6 — `formula_application` (101) · engine `formula_engine`

- `arc_length` · geometry · trace
- `arithmetic_sequence_term` · algebra · trace
- `average_speed` · physics · trace
- `boyles_law` · chemistry · trace
- `break_even` · finance · trace
- `celsius_to_fahrenheit` · physics · trace
- `centripetal_acceleration` · physics · trace
- `charles_law` · chemistry · trace
- `circle_area` · geometry · trace
- `circle_circumference` · geometry · trace
- `coefficient_of_variation` · statistics · trace
- `combinations` · discrete · trace
- `combined_gas_law` · chemistry · trace
- `compound_interest` · finance · trace
- `cone_volume` · geometry · trace
- `coordinate_distance` · geometry · trace
- `covariance` · statistics · trace
- `cube_surface_area` · geometry · trace
- `cube_volume` · geometry · trace
- `cylinder_volume` · geometry · trace
- `density` · chemistry · trace
- `descriptive_stats` · statistics · trace
- `determinant_2x2` · linear_algebra · trace
- `dilution` · chemistry · trace
- `discount_price` · finance · trace
- `distance_rate_time` · algebra · trace
- `dot_product_3d` · linear_algebra · trace
- `efficiency` · physics · trace
- `factorial` · discrete · trace
- `fahrenheit_to_celsius` · physics · trace
- `fluid_pressure` · physics · trace
- `free_fall_distance` · physics · trace
- `free_fall_velocity` · physics · trace
- `frequency_from_period` · physics · trace
- `future_value` · finance · trace
- `geometric_sequence_term` · algebra · trace
- `gravitational_pe` · physics · trace
- `heat_energy` · physics · trace
- `hookes_force` · physics · trace
- `ideal_gas_pressure` · chemistry · trace
- `impulse` · physics · trace
- `kelvin_conversion` · physics · trace
- `kinematics` · physics · trace
- `kinetic_energy` · physics · trace
- `mass_from_density` · chemistry · trace
- `mean_absolute_deviation` · statistics · trace
- `mechanical_power` · physics · trace
- `median_range` · statistics · trace
- `midpoint` · geometry · trace
- `molarity` · chemistry · trace
- `mole_fraction` · chemistry · trace
- `moles_from_mass` · chemistry · trace
- `moles_ideal_gas` · chemistry · trace
- `momentum` · physics · trace
- `newtons_second_law` · physics · trace
- `ohms_law` · physics · trace
- `ohms_power` · physics · trace
- `ohms_resistance` · physics · trace
- `parallelogram_area` · geometry · trace
- `pendulum_period` · physics · trace
- `percent_change` · finance · trace
- `percent_composition` · chemistry · trace
- `percent_error` · statistics · trace
- `percent_increase` · finance · trace
- `percent_of` · algebra · trace
- `percent_yield` · chemistry · trace
- `permutations` · discrete · trace
- `ph_poh` · chemistry · trace
- `polygon_exterior_angle` · geometry · trace
- `polygon_interior_angle` · geometry · trace
- `potential_to_kinetic` · physics · trace
- `power_from_current` · physics · trace
- `present_value` · finance · trace
- `pressure` · physics · trace
- `probability_simple` · statistics · trace
- `profit_margin` · finance · trace
- `projectile_range` · physics · trace
- `pythagorean` · geometry · trace
- `quadratic` · algebra · trace
- `rectangle_area` · geometry · trace
- `rectangle_perimeter` · geometry · trace
- `root_mean_square` · statistics · trace
- `sales_tax_total` · finance · trace
- `sector_area` · geometry · trace
- `simple_interest` · finance · trace
- `simple_roi` · finance · trace
- `slope` · geometry · trace
- `sphere_surface_area` · geometry · trace
- `sphere_volume` · geometry · trace
- `spring_pe` · physics · trace
- `spring_period` · physics · trace
- `tangent_ratio` · geometry · trace
- `trapezoid_area` · geometry · trace
- `triangle_area` · geometry · trace
- `unit_price` · finance · trace
- `vector_magnitude` · linear_algebra · trace
- `wave_speed` · physics · trace
- `weight_force` · physics · trace
- `weighted_mean` · statistics · trace
- `work_done` · physics · trace
- `z_score` · statistics · trace

### T7 — `reduction_rewriting` (9) · engine `rewrite_engine`

- `arithmetic_eval` · formula · coding
- `combine_like_terms` · algebra · trace
- `distribute` · algebra · trace
- `equation_both_sides` · algebra · trace
- `linear_equation` · algebra · trace
- `multiplication_equation` · algebra · trace
- `one_step_equation` · algebra · trace
- `simplify_fraction` · algebra · trace
- `solve_proportion` · algebra · trace

### T8a — `incremental_construction` (20) · engine `construct_engine`

- `babylonian_sqrt` · numerical · trace
- `bubble_sort` · sequence · coding
- `cumulative_product` · sequence · trace
- `depreciation_schedule` · finance · trace
- `digit_sum` · number_theory · trace
- `fibonacci_sequence` · sequence · trace
- `gradient_descent` · numerical · trace
- `heap_sort` · sequence · coding
- `insertion_sort` · sequence · coding
- `pascals_triangle_row` · discrete · trace
- `polynomial_derivative` · calculus · trace
- `polynomial_integral` · calculus · trace
- `powers_of_two` · discrete · trace
- `prefix_sums` · sequence · trace
- `prime_factorization` · number_theory · trace
- `running_maximum` · sequence · trace
- `savings_growth` · finance · trace
- `selection_sort` · sequence · coding
- `sieve_of_eratosthenes` · number_theory · coding
- `triangular_numbers` · discrete · trace

### T8b — `formal_derivation` (16) · engine `derivation_engine`

- `complete_the_square` · algebra · trace
- `cube_of_binomial` · algebra · trace
- `difference_of_cubes` · algebra · trace
- `difference_of_squares` · algebra · trace
- `exponent_laws` · algebra · trace
- `factor_gcf` · algebra · trace
- `foil_expansion` · algebra · trace
- `induction_proof` · proof · trace
- `log_evaluation` · algebra · trace
- `log_product_law` · algebra · trace
- `log_quotient_law` · algebra · trace
- `perfect_square_expansion` · algebra · trace
- `power_of_power` · algebra · trace
- `sum_first_n` · algebra · trace
- `sum_geometric_series` · algebra · trace
- `sum_odd_numbers` · algebra · trace

### T10 — `stateful_operation_invariant_maintenance` (8) · engine `stateful_engine`

- `hash_table_insert` · structures · trace
- `lru_cache` · structures · trace
- `min_stack` · structures · trace
- `modular_counter` · structures · trace
- `queue_operations` · structures · trace
- `set_operations` · structures · trace
- `stack_operations` · structures · trace
- `union_find` · structures · coding

### T13 — `proof_obligation_discharge` (6) · engine `induction_engine`

- `induction_sum_first_n` · proof · trace
- `induction_sum_i_times_i_plus_1` · proof · trace
- `induction_sum_of_cubes` · proof · trace
- `induction_sum_of_evens` · proof · trace
- `induction_sum_of_odds` · proof · trace
- `induction_sum_of_squares` · proof · trace

### T14 — `indexed_table_evaluation` (9) · engine `table_engine`

- `truth_table_and_or` · discrete · trace
- `truth_table_biconditional` · discrete · trace
- `truth_table_full_adder_sum` · discrete · trace
- `truth_table_implication` · discrete · trace
- `truth_table_majority` · discrete · trace
- `truth_table_nand` · discrete · trace
- `truth_table_nor` · discrete · trace
- `truth_table_xnor` · discrete · trace
- `truth_table_xor` · discrete · trace

### T15 — `matrix_row_operation_elimination` (3) · engine `rowreduce_engine`

- `gaussian_elimination` · linear_algebra · trace
- `solve_linear_system_2x2` · linear_algebra · trace
- `solve_linear_system_3x3` · linear_algebra · trace

### T16 — `numerical_time_step_convergence` (5) · engine `numerical_engine`

- `euler_newton_cooling` · numerical · trace
- `fixed_point_linear` · numerical · trace
- `newton_cbrt` · numerical · trace
- `newton_reciprocal` · numerical · trace
- `newton_sqrt` · numerical · trace

