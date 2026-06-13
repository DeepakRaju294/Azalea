# Example System Spec

A typed ontology for **worked examples**, in tandem with the visual ontology
(`backend/app/core/visual_ontology_v2.py`) and the trace-authoritative pipeline
(`VISUAL_SYSTEM_SPEC.md`). Where the visual ontology answers *"what is drawn and
how,"* this answers *"what is being worked through and how it is built."* The two
are linked: one declaration drives the example content **and** its visual.

---

## 1. Current state → why this exists

Visuals improved because they are **typed**: `BASE_VISUAL_TYPES` (12 renderer
families) → `MODES_BY_BASE_TYPE` (~105 concrete applications), each with a
description and a deterministic compile path. Examples never got that treatment —
they are **free-form**, authored by one overloaded LLM call alongside structure,
code, sizing, and prose. The predictable result: broken code, truncated traces,
wrong example sizes, and card structures that drift from the blueprint.

The fix is the same move that fixed visuals: **make examples typed and
deterministic; make the LLM's job boring (explanation only).** This spec defines:

1. **Example types** — the "what it could be" (mirrors visual base types).
2. **Applications** — every concrete instance within a type (mirrors visual modes).
3. The **canonical spec** each application carries (input + code/algorithm = the
   source of truth), and its **tandem mapping** to a visual type + simulator.

A worked example is no longer invented per generation; it is **selected from the
ontology**, and the selected application's canonical spec drives the trace, the
visual, the example size, and what the LLM is allowed to say.

---

## 2. Principles

1. **Examples are typed, not free-form.** Generation declares `(example_type,
   application)`; it never invents an example from scratch.
2. **The application owns the truth.** Each application carries a canonical input
   and (where code is shown) a verified, runnable implementation. This is the
   source of truth for the code, the input, the expected output, and the minimum
   step count — not the LLM.
3. **Example ↔ visual ↔ trace are one declaration.** An application maps to a
   visual `(base_type, mode)` and a simulator. The example and its visual cannot
   disagree, because they come from the same row.
4. **Card structure comes from the blueprint, not the LLM.** The card skeleton
   (order, count, roles) per topic type is laid out from `course_blueprints.py`;
   the LLM fills slots.
5. **The LLM explains; it does not author structure, code, or example shape.**
   Its output is prose grounded in the canonical example + the locked trace
   (§5.5 of the visual spec).
6. **Same shape as the visual ontology.** Types → applications → descriptions →
   a deterministic spec, so the two ontologies are learned and maintained the
   same way.

---

## 3. The example ontology

### 3.1 `EXAMPLE_TYPES` — the families (what a worked example *is*)

Twelve example types, in tandem with the twelve visual base types. A type is **not**
a subject — it is the *shape of the thing being traced over time* (a 1-D sequence,
a node/link structure, a grid of cells, lines of code, memory, symbols, a plot, a
figure, regions, a comparison, a timeline, a chain of claims). The specific
algorithm/op/formula is the **application** (§3.2), exactly as `tree_hierarchy` and
`graph_network` are modes under one visual base type — not two base types.

> **Type → visual is a *default*; the application/fixture row (§3.3) is
> authoritative.** A `grid_table_trace` defaults to a grid but a SQL/truth-table
> application resolves to `table_diagram`; a `code_execution_trace` may add memory /
> call-stack panels. Never treat the table below as the source of truth — the
> application's `visual {base_type, mode}` is.

| example_type | description | default visual base_type |
|---|---|---|
| `sequence_state_trace` | A worked example over a 1-D ordered sequence where indices, ranges, pointers, or windows change over time. | indexed_sequence_diagram |
| `node_link_trace` | A worked example over nodes and edges where traversal, hierarchy, connectivity, or references change. | node_link_diagram |
| `grid_table_trace` | A worked example where values are filled, updated, compared, or read across rows / columns / cells. | grid_matrix_diagram · table_diagram |
| `code_execution_trace` | A line-by-line execution of real code — active lines, variables, calls, returns, output. | code_execution_panel |
| `memory_reference_trace` | A worked example over memory: stack/heap, references, pointers, object layout, addresses. | memory_layout_diagram |
| `symbolic_derivation` | A worked example that manipulates symbols, expressions, equations, or formulas step by step. | formula_symbolic_expression |
| `coordinate_plot_analysis` | A worked example that constructs, reads, or analyses a graph on coordinate axes. | coordinate_graph |
| `geometric_spatial_construction` | A worked example that builds or measures shapes, angles, lengths, vectors, or regions. | geometric_diagram |
| `set_logic_region_reasoning` | A worked example over sets, events, logical regions, or probability spaces. | set_region_diagram |
| `case_comparison_example` | A *composite* worked example pairing two+ cases/approaches/structures side by side (§4 note). | table_diagram · (paired instances of any base type) |
| `timeline_interaction_trace` | A worked example where actors, processes, threads, messages, or events unfold over time. | timeline_sequence_interaction |
| `proof_reasoning_chain` | A worked example that derives a conclusion through a chain of justified reasoning steps. | formula_symbolic_expression · table_diagram |

**The boundary rule (code vs concept):** use `code_execution_trace` only when the
**code itself** is the example (`coding_implementation` topics). If the learner is
understanding the algorithm conceptually (`algorithm_walkthrough` /
`data_structure_operation`), use `sequence_state_trace` / `node_link_trace` /
`grid_table_trace`. The declaration step (§5) keys off `topic_type`, so this is
deterministic, not a guess.

### 3.2 `APPLICATIONS_BY_TYPE` — the concrete instances (mirrors visual modes)

**Three axes — keep them distinct (this is load-bearing):**
- **application = WHAT** — the topic a title recognisably names (`binary_search`,
  `bfs`, `bst_operation`, `quadratic_formula`, `unique_paths`). Declaration (§5.1)
  matches titles to *this*. Never make a run-shape the application.
- **pattern = HOW** — the run/derivation shape, a field on the profile
  (`range_halving`, `frontier_expansion`, `dp_table_fill`, `loop_execution`,
  `recursive_execution`, `formula_substitution`, `calculus_derivation`). The pattern
  selects the `step_roles` (§3.4); many applications share one pattern.
- **variant = WHICH sub-op** — a field on the *fixture* (§4) for broad applications
  whose sub-operations have different traces: `bst_operation` → `insert` /
  `delete_leaf` / `delete_two_child`; `sorting_pass` → `bubble` / `selection`;
  `linked_list_operation` → `insert` / `reverse`.

So `binary search code` is **not** application `loop_execution`; it is application
`binary_search`, example_type `code_execution_trace` (the code-vs-concept lens),
pattern `loop_execution`. The lists below name **applications** (the WHAT); each
one-liner is the example analogue of the visual `MODE_DESCRIPTIONS`. The
parenthesised `(pattern: …)` is the profile's default pattern. **✓sim** = a
deterministic simulator already exists in `visual_v2/simulators/`.

> **`code_execution_trace` is a *lens*, not a home for applications.** Its entries
> below are `execution_pattern` values; the *application* is the algorithm
> (`binary_search`, `bfs`, `inorder`) carried over from its conceptual type and shown
> as code. **Every other type lists real applications** — recognisable topic names
> (`unique_paths`, `quadratic_formula`, never `dp_table_fill`/`formula_substitution`);
> the run-shape is the profile's `(pattern: …)`.

#### `sequence_state_trace`
- `binary_search` — halve a sorted range each probe until the target is found or ruled out. **✓sim**
- `linear_search` — scan left→right comparing each element to the target.
- `two_pointer` — move two indices inward / at a lag to meet a pair or order condition.
- `sliding_window` — grow and shrink a contiguous window maintaining a running constraint.
- `prefix_sum` — build a running cumulative total to answer range queries.
- `kadane` — keep the best running subarray sum while scanning once.
- `sorting_pass` — one pass of a comparison sort (bubble / selection / insertion).
- `merge_partition` — the merge step of merge sort or the partition step of quick sort.
- `string_scan` — sweep a string tracking characters / frequencies (RLE, dedupe).
- `palindrome_check` — converge two ends comparing mirrored characters.
- `anagram_check` — count and compare character frequencies across two strings.

#### `node_link_trace`
- `bfs` — breadth-first frontier expansion: queue + visited, level order. **✓sim**
- `dfs` — depth-first descent: stack / recursion + visited. **✓sim**
- `tree_traversal` — inorder / preorder / postorder / level-order visit of a tree.
- `bst_operation` — search / insert / delete on a BST preserving its ordering.
- `heap_operation` — sift-up / sift-down on a binary heap (push / pop).
- `linked_list_operation` — traverse / insert / delete / reverse by relinking nodes.
- `trie_operation` — walk and extend prefix branches for a key.
- `union_find` — union-by-rank / path-compression over connectivity.
- `shortest_path` — relax edges to find least-cost paths (Dijkstra / Bellman-Ford).
- `topological_sort` — emit nodes in dependency order (Kahn / DFS finish).
- `state_machine_run` — follow an FSM's transitions on an input.
- `automata_run` — run a DFA / NFA, tracking the active state(s).

#### `grid_table_trace` — applications are the specific problem; the run-shape is the `(pattern)`
- `unique_paths` — count lattice paths by filling a DP grid from its recurrence. **✓sim** (pattern `dp_table_fill`)
- `coin_change` — min coins / number of ways via a DP table. (pattern `dp_table_fill`)
- `knapsack_01` — max value under a weight cap via a 2-D DP table. (pattern `dp_table_fill`)
- `longest_common_subsequence` — LCS length via a 2-D DP table. (pattern `dp_table_fill`)
- `edit_distance` — minimum edits via a 2-D DP table. (pattern `dp_table_fill`)
- `min_path_sum` — least-cost grid path via DP. (pattern `dp_table_fill`)
- `matrix_multiplication` — multiply two matrices entry by entry. (pattern `matrix_operation`)
- `row_reduction` — Gaussian-eliminate a matrix to row-echelon form. (pattern `matrix_operation`)
- `floyd_warshall` — all-pairs shortest paths by relaxing a distance table. (pattern `distance_table_update`)
- `truth_table_evaluation` — enumerate inputs and evaluate a logical expression per row. (pattern `truth_table_fill`)
- `sql_join` — join / filter / group rows of relations. (pattern `sql_table_operation`)
- `confusion_matrix_metrics` — read TP/FP/FN/TN cells to compute precision / recall. (pattern `table_read`)

#### `code_execution_trace` — these are `execution_pattern` values; the *application* is the algorithm (e.g. `binary_search`, `bfs`, `inorder`) shown under the code lens
- `loop_execution` — step a for / while loop, tracking the loop variable and accumulator. **✓sim**
- `function_call_trace` — follow a call into a function and its return value. **✓sim**
- `recursive_execution` — trace recursion frames pushing / popping on the call stack. **✓sim**
- `nested_loop_execution` — step inner / outer loops building a result.
- `condition_execution` — evaluate an if/elif/else and take the live branch.
- `backtracking_execution` — choose → recurse → un-choose over a search space.
- `dp_code_execution` — run bottom-up / top-down DP code filling a table or memo.
- `pointer_code_execution` — execute in-place pointer / linked-structure relinking.
- `oop_method_execution` — dispatch a method or constructor on an object.

#### `memory_reference_trace`
- `stack_heap_allocation` — show where locals vs allocated objects live across a call.
- `pointer_assignment` — bind / rebind a pointer and what it now references.
- `pointer_dereference` — follow a pointer to read or write the pointed-to value.
- `object_layout` — lay out a struct / object's fields in memory.
- `array_memory_layout` — show contiguous elements and the index→address mapping.
- `shallow_vs_deep_copy` — compare which references are shared vs duplicated.
- `linked_structure_relinking` — repoint next / prev around an inserted or deleted node.
- `cache_access` — resolve an address to a cache line and hit / miss.
- `virtual_memory_translation` — translate a virtual address via the page table / TLB.

#### `symbolic_derivation` — applications are the specific formula/equation; the run-shape is the `(pattern)`
- `quadratic_formula` — solve ax²+bx+c=0 by substituting into the formula. (pattern `formula_substitution`)
- `linear_equation` — isolate x through inverse operations. (pattern `equation_solving`)
- `system_elimination` — solve a 2-variable system by elimination / substitution. (pattern `equation_solving`)
- `compound_interest` — evaluate A = P(1 + r/n)^(nt). (pattern `formula_substitution`)
- `distance_formula` — compute the distance between two points. (pattern `formula_substitution`)
- `mean_variance` — compute the mean, then variance / std of a dataset. (pattern `formula_substitution`)
- `bayes_formula` — update a probability with Bayes' rule. (pattern `formula_substitution`)
- `chain_rule` — differentiate a composite function. (pattern `calculus_derivation`)
- `integration_by_parts` — integrate a product via ∫u dv. (pattern `calculus_derivation`)
- `big_o_simplification` — drop constants and lower-order terms to a Big-O class. (pattern `algebraic_simplification`)
- `recurrence_expansion` — unroll a recurrence toward a closed form (Master theorem). (pattern `recurrence_expansion`)

#### `coordinate_plot_analysis`
- `function_graph_analysis` — plot and read a function's key features (intercepts, asymptotes).
- `slope_or_derivative_at_point` — find the slope / tangent at a point.
- `area_under_curve` — compute a definite integral / Riemann sum as area.
- `intersection_analysis` — locate where two curves meet.
- `distribution_reading` — read a probability distribution (z-score, area).
- `regression_fit` — fit and interpret a line through data points.
- `runtime_growth_comparison` — compare Big-O growth curves.
- `loss_curve_interpretation` — read a training loss curve over epochs.
- `roc_curve_interpretation` — read an ROC / precision-recall curve.

#### `geometric_spatial_construction`
- `triangle_geometry` — apply angle-sum / similarity / congruence to a triangle.
- `circle_geometry` — reason over radius / chord / tangent / arc / sector.
- `right_triangle_trig` — solve a right triangle (sine/cosine/tangent, law of sines/cosines).
- `coordinate_geometry` — compute midpoint / distance / slope on the plane.
- `vector_operation` — add vectors or take dot / cross products geometrically.
- `projection` — project a vector or point onto a line or subspace.
- `linear_algebra_geometry` — visualise span / basis / linear transformation / eigenvectors.
- `solid_geometry` — compute volume / surface area of a 3-D solid.
- `integration_region` — set up the region for area-between-curves / solid of revolution.
- `optimization_geometry` — find an optimum over a feasible region (incl. Lagrange).

#### `set_logic_region_reasoning`
- `set_operation` — compute union / intersection / complement / difference.
- `venn_counting` — count elements across overlapping Venn regions.
- `conditional_probability` — compute P(A|B) over a sample-space region.
- `bayes_reasoning` — update a probability with Bayes' rule.
- `inclusion_exclusion` — count a union via inclusion–exclusion.
- `truth_region_reasoning` — reason over logical regions / equivalences.
- `classification_overlap` — read TP / FP / FN regions for precision and recall.
- `logic_region` — evaluate predicate-logic membership regions.

#### `case_comparison_example` (composite — see §4)
- `algorithm_comparison` — run two algorithms on the same input to contrast time / space.
- `data_structure_comparison` — contrast structures on one operation (array vs list, BST vs hash).
- `approach_comparison` — contrast two solution styles (iterative vs recursive, top-down vs bottom-up).
- `valid_vs_invalid` — show an instance that satisfies vs violates the invariant.
- `normal_vs_edge_case` — contrast a typical run with a boundary run.
- `correct_vs_incorrect` — contrast a correct trace with a common buggy one.
- `before_vs_after` — contrast the state before and after a transformation.
- `tradeoff_analysis` — compare options across cost / benefit dimensions.

#### `timeline_interaction_trace`
- `request_response_flow` — trace a client↔server request and its response.
- `protocol_sequence` — step a protocol exchange (TCP / TLS / DNS / OAuth) message by message.
- `thread_interleaving` — show interleaved execution of concurrent threads.
- `race_condition` — expose a data race from a specific interleaving.
- `lock_acquisition` — trace mutex / semaphore acquire / release (and deadlock).
- `transaction_timeline` — commit / rollback a database transaction over time.
- `pipeline_flow` — move an item through pipeline stages.
- `scheduling_trace` — run a CPU scheduler (round-robin / priority) over a timeline.
- `network_handshake` — trace a connection handshake's stages.

#### `proof_reasoning_chain`
- `direct_proof` — derive the conclusion straight from the assumptions.
- `contradiction_proof` — assume the negation and derive a contradiction.
- `contrapositive_proof` — prove ¬Q ⇒ ¬P in place of P ⇒ Q.
- `induction_proof` — prove a base case, then the inductive step.
- `strong_induction_proof` — induct using all smaller cases.
- `loop_invariant_proof` — show an invariant holds before and after each iteration.
- `algorithm_correctness_proof` — argue an algorithm meets its specification.
- `set_equality_proof` — prove A = B by mutual inclusion.
- `greedy_exchange_proof` — justify a greedy choice via an exchange argument.
- `dp_recurrence_proof` — justify a DP recurrence's optimal substructure.

### 3.3 The hierarchy + tandem map

The full chain (the example analogue of the visual pipeline). An **ApplicationProfile**
(§3.4) holds the reusable rules every fixture of that application inherits; a
**FixtureSource** (§7.1) says where the concrete instance came from:

```
Example Type → Application Profile → Fixture Source → Canonical Fixture
                                                          → Trace
                                                              → Visual Frames
                                                              → Prose Slots

sequence_state_trace → binary_search(profile) → hand_verified → binary_search_found_late_01
    → low/mid/high trace → indexed_sequence_diagram frames + prose slots
node_link_trace      → bfs(profile)           → hand_verified → bfs_branching_graph_01
    → queue/visited trace → node_link_diagram frames + prose slots
```

A **fixture** is the named, sized, deterministic instance of an application. It is
*thin* — it only names the concrete input/output and any allowed overrides; the
*rules* (invariants, step roles, default visual, sizing, selection policy, forbidden
LLM actions) live once on the application's **profile** (§3.4):

```
fixture binary_search_found_late_01
  application binary_search                       # inherits the binary_search profile
  input { array: [1..15], target: 1 }    expected_output 0
  source hand_verified   sizing { min_steps 4, max_steps 6, required_decisions [go_left, go_right] }
```

`EXAMPLE_TYPE_TO_DEFAULT_VISUAL` (a default for unfixtured/novel cases only) maps
each of the 12 types to its primary `(base_type, mode)` — but the profile's
`default_visual` and a fixture's `visual_override` win (a SQL `grid_table_trace`
profile → `table_diagram`; a recursion `code_execution_trace` fixture → adds a
`call_stack` supporting panel).

### 3.4 `ApplicationProfile` — the reusable rules an application owns

An application is **not** just a name; it owns the rules shared by all its fixtures,
so validation and sizing live in **one** place, not repeated per fixture:

```
ApplicationProfile {
  application                 # §3.2 key (the WHAT)
  example_type                # §3.1 (default lens)
  code_example_type?          # if this app can also be shown as code → code_execution_trace
  pattern                     # the HOW: range_halving | frontier_expansion | dp_table_fill |
                              #          loop_execution | recursive_execution | formula_substitution | ...
  variants?[]                 # sub-ops a fixture may set (insert/delete_leaf/...) — §4
  description                 # the §3.2 one-liner
  default_visual { base_type, mode }      # tandem target; authoritative unless overridden
  allowed_visual_overrides[]              # (base_type, mode) a fixture may switch to
  supporting_visuals[]                    # default extra panels (call_stack, memory, ...)
  trace_authority             # "simulator:<key>" | "deterministic_eval" | "llm_validated"
  trace_granularity           # how raw frames group (below)
  milestone_policy            # which grouped steps become cards (below)
  fixture_schema              # the shape a fixture's `input`/`code` must satisfy
  required_invariants[]       # checked by InputValidator (sorted array, BST order, connected, ...)
  step_roles[]                # the semantic role vocabulary for this type's frames (below)
  default_min_steps           # sizing floor; a fixture may raise via override
  default_max_steps           # sizing ceiling
  fixture_selection_policy     # default policy keyed by card role (§5.2)
  forbidden_llm_actions[]     # e.g. ["author_code", "introduce_values", "mention_big_o"]
}
```

A fixture (§4) inherits all of this; it may override **only** `visual` (within
`allowed_visual_overrides`), `min_steps`/`max_steps`, `supporting_visuals`, and set a
`variant`.

**`variant` is required when `profile.variants` is non-empty.** For broad
applications (`bst_operation`, `heap_operation`, `linked_list_operation`,
`sorting_pass`, `matrix_operation`, `sql_join`) a fixture **must** declare its
`variant` (`insert` / `delete_two_child` / `push` / `bubble` / …); a fixture without
one is rejected by the InputValidator (§5.3). Applications with no `variants` (e.g.
`binary_search`, `bfs`) leave it unset.

**`trace_granularity` + `milestone_policy` — raw frames are too fine; group them.**
The simulator emits every state change; the profile says how to group into cards so
a learner sees *cycles*, not interpreter events:

```
trace_granularity ∈ { every_state_change | decision_points_only | grouped_by_iteration
                    | grouped_by_frontier_level | grouped_by_cell | grouped_by_region | grouped_by_call }
milestone_policy  = { include_setup, include_decisions, include_state_changes,
                      include_outputs, collapse_repetitive_steps, max_cards }
```
Examples: `binary_search` → `grouped_by_iteration` (one card per probe);
`bfs` → `grouped_by_frontier_level`; `dp_table_fill` → base cases + first recurrence
cell + representative middle + final; `loop_execution` → `grouped_by_call` /
explanatory line groups, not every tiny event. (`milestone_policy` generalises
today's `_milestone_frame_indices`, §4.5 Step C.)

**`step_roles` — the semantic role of each trace step** (so the LLM explains *a kind
of reasoning move*, never "frame 4"). Vocabulary is per example_type:

```
sequence_state_trace           : setup · inspect_position · make_comparison · update_pointer_or_range · repeat · terminate · return_output
node_link_trace                : setup · select_active · examine_neighbours · enqueue/push · visit/complete · record_output · terminate
grid_table_trace               : define_table · initialize_base_case · select_cell · read_dependencies · apply_rule · write_cell · read_final_answer
code_execution_trace           : bind_input · enter_function · execute_line · evaluate_condition · update_variable · call/return · produce_output
memory_reference_trace         : setup_memory_state · allocate · bind_reference · dereference · mutate_value · update_aliases · show_final_state
symbolic_derivation            : state_expression · choose_rule · apply_rule · simplify · substitute · isolate · state_result
coordinate_plot_analysis       : define_axes · plot_object · mark_feature · compute_value · interpret_feature · conclude
geometric_spatial_construction : draw_base_figure · label_knowns · add_helper_element · apply_property · compute_measure · conclude
set_logic_region_reasoning     : define_universe · mark_regions · apply_operation · count_region · compute_probability · conclude
case_comparison_example        : setup_cases · run_left_case · run_right_case · compare_dimension · extract_rule · conclude
timeline_interaction_trace     : setup_actors · send_event · receive_event · update_state · expose_interleaving · conclude
proof_reasoning_chain          : state_claim · state_assumption · apply_definition · derive_step · justify_step · conclude
```

The simulator/trace tags each grouped step (§3.4 granularity) with a `step_role`;
those roles drive the prose slots (§4.1).

---

## 4. The `CanonicalFixture` contract (per fixture)

The leaf of the hierarchy — data only, **thin**, inheriting all rules from its
`ApplicationProfile` (§3.4). It names only the concrete instance + allowed overrides:

```
CanonicalFixture {
  fixture_id              # e.g. binary_search_found_late_01
  application             # → its ApplicationProfile supplies example_type, default_visual,
                          #   pattern, invariants, step_roles, forbidden_llm_actions, default sizing
  variant?                # WHICH sub-op, from profile.variants (insert | delete_two_child | bubble | ...)
  input                   # the concrete instance (graph, array+target, tree, a,b,c, ...)
  code?                   # verified runnable implementation (code_execution_trace fixtures)
  expected_output         # computed + verified, never LLM-asserted
  visual_override?        # (base_type, mode) — only within profile.allowed_visual_overrides
  supporting_visuals_override?[]
  sizing {                # overrides/strengthens the profile defaults (a fixture can be valid
    min_steps? max_steps?           # but still boring — these make it good, not just legal)
    required_decisions?[]           # e.g. ["go_left", "go_right"] — must both occur
    required_features?[]            # e.g. ["branching", "shared_neighbour"] for a graph
    avoid?[]                        # e.g. ["target_at_first_mid", "simple_line_graph"]
    cognitive_load?                 # low | medium | high
  }
  source                  # hand_verified | generated_deterministic | llm_validated  (§7.1)
  practice_variants?[]    # isomorphic fixture ids — same reasoning shape, different values (§7.2)
  tags[]                  # difficulty / topic hints used by the selection policy (§5.2)
  learner_goal            # one line: what this fixture teaches
}
```

Everything *not* listed (the `invariants`, `default_visual`, `step_roles`,
`forbidden_llm_actions`, default `min_steps`) is **inherited from the profile** —
defined once, reused by every fixture. `input`/`code` + `sizing` are chosen so the
example is **non-trivial and correctly sized** — this is where "ensure ≥4 steps" /
"show the full grid" / "don't use a line graph for BFS" become spec properties, not
hopes.

### 4.1 `ProseSlot` — the only thing the LLM receives

The LLM is never handed lesson generation. It is handed **one grounded slot per
trace frame (or frame group)** and asked to write a few sentences. This is both the
accuracy mechanism (it cannot invent facts) and the efficiency mechanism (a tiny
prompt, not the whole ontology):

```
ProseSlot {
  slot_id
  frame_ids[]             # the frame(s) this slot explains
  event_id                # the projector's semantic event for this step, when available
                          #   (PROJECTOR_SYSTEM_SPEC §4); code-walkthrough + supporting-diagram
                          #   cards JOIN on event_id, not frame_index
  state_source            # which tier produced the state (T1..T5) — prose is precise for
                          #   T1–T4, conservative for T5 (PROJECTOR_SYSTEM_SPEC §6.4 INV-PROSE-SYNC)
  step_role               # from the profile's step_roles (§3.4) — e.g. "discard_left_half"
  previous_frame_summary  # what the state was before this step
  current_frame_delta     # what CHANGED this step — the prose must explain THIS, not the whole concept
  allowed_facts[]         # the ONLY facts the prose may use, lifted from the frame state
  required_mentions[]     # points the prose MUST make (the teaching beat)
  forbidden_mentions[]    # e.g. ["code syntax", "new array values", "unrelated Big-O"]
  style                   # ProseStylePolicy (below)
}

ProseStylePolicy {        # from the profile; keeps explanations tight + delta-focused
  max_bullets
  max_words_per_bullet
  must_explain_delta      # true → the bullet must describe the transition, not re-teach the concept
  no_code_in_bullets
  no_repeating_visual_labels   # don't restate what the chip/label already shows
  avoid_generic_phrases
}
```

The single most common bad-worked-example failure is prose that **re-explains the
whole concept instead of the step's delta**. `current_frame_delta` +
`must_explain_delta` make "explain only what changed from the previous frame" a
hard contract, not a hope.

Example (binary search, step 3):
```
{ step_role: "discard_left_half",
  allowed_facts: ["low=0, high=10, mid=5", "array[mid]=23", "target=72", "23 < 72", "new low=6"],
  required_mentions: ["target must be to the right", "low moves to mid + 1"],
  forbidden_mentions: ["code syntax", "new array values"], max_words: 55 }
```

The LLM may use **only** `allowed_facts`, must hit `required_mentions`, and must
avoid `forbidden_mentions`; output is `{ points: [str] }` and nothing else.
`allowed_facts` are extracted deterministically from the frame's folded state — so
the prose **cannot** drift from the trace (visual spec §5.5, enforced here by the
ProseValidator, §5.3).

**`case_comparison_example` is the one composite type.** Its fixture is not a single
trace; it **references two or more child fixtures** of other types and a comparison
dimension, e.g. `bfs_vs_dfs_01 = { left: bfs_branching_graph_01, right:
dfs_branching_graph_01, dimensions: [order, frontier, completeness] }`. The renderer
shows the children side by side (often under a `comparison_table`). Everything else
about each child — trace, visual, sizing — comes from that child's own fixture.

### 4.5 Handoff to the visual system — the exact interface

The example system never builds frames. It maps a fixture onto the visual system's
existing `CanonicalExample` and runs the V2 pipeline unchanged. Implement exactly
this — nothing here is approximate.

**Step A — field map**
(`fixture_to_canonical_example(fixture, declared, resolved_visual) -> CanonicalExample`).
Target type: `backend/app/services/visual_v2/schemas.py::CanonicalExample`.

Compute **`resolved_visual`** once via `resolve_visual(fixture, declared)` and pass it
in (so the field map never re-derives the resolution hierarchy, and only one value is
validated):
```
resolve_visual(fixture, declared):
  return fixture.visual_override
      or profile(declared.application).default_visual
      or EXAMPLE_TYPE_TO_DEFAULT_VISUAL[declared.resolved_example_type]
```

| CanonicalFixture field | → CanonicalExample field | notes |
|---|---|---|
| `fixture_id` | `example_id` | string id |
| `example_type` | `domain_object` | informational |
| `application` | `algorithm` *(when registered)* | the simulator-registry key (`bfs`, `binary_search`, `code_execution`, …) |
| `resolved_visual.base_type` | `base_type` | e.g. `node_link_diagram`, `indexed_sequence_diagram`, `code_execution_panel`, `grid_matrix_diagram` |
| `resolved_visual.mode` | `mode` | e.g. `graph_network`, `binary_search_range`, `dp_table` |
| `input` | `input` **and** `base_structure` | `base_structure` = the structural part (`{nodes,edges}`, `{array}`, `{rows,cols}`); `input` = the run params (`{start}`, `{target}`, `{tree}`) |
| `code` | `code` | only for `code_execution_trace`; entry function derived as today |
| `expected_output` | `expected_output` | cross-checked against the simulator's output (fixture is wrong if they differ) |
| `learner_goal` | `learner_goal` | one line |

`resolved_visual` **must** be a real `(base_type, mode)` pair in
`visual_ontology_v2.MODES_BY_BASE_TYPE` (validate at load, like the visual modes) —
this is the single value the VisualValidator (§5.3) checks.

**Step B — run the pipeline (unchanged).**
`run_for_registered(example, model_id=…)` from
`backend/app/services/visual_v2/pipeline.py`. It returns a dict with these exact
keys (already implemented): `status` (`"validated"` | `"failed"`), `stage`,
`errors`, `model` (a `VisualModel`), `render_steps` (`list[RenderStep]`), `trace`,
`frames`, `pedagogy`, `debug`, `example`. Validation (ExampleInvariantValidator,
TraceValidator, model + pedagogical) and `min_steps` are checked here; on
`status != "validated"` → **do not mutate the lesson**, log `debug`, return False.

**Step C — select which frames become cards (milestones).** Not every frame is a
card. Reuse the existing milestone logic (`code_lesson_integration._milestone_frame_indices`,
generalised): accumulator-growth steps, else loop-iteration + setup steps, else
every frame. `min_steps` is enforced against the *milestone* count, not the raw
frame count.

**Step D — attach + reference.** Exactly as the live adapters already do:

```
lesson_json["visual_models"]  append  model            # dedupe by model["id"]
for n, frame_index in enumerate(milestones):
    card = worked_example_step_card(
        title, points=<prose slot, filled by LLM>,
        visual_type   = model["base_type"],
        visual_v2_ref = { "visual_model_id": model["id"],
                          "frame_index": frame_index,
                          "source": "v2_example_ontology" },
    )
```

The frontend resolves `visual_v2_ref` → `components/visuals_v2/VisualRenderer.tsx`
switches on `model.base_type` → renders `model.frames[frame_index]`. **Card n shows
milestone-frame n; its prose describes that frame** (validated against the trace,
visual spec §5.5).

**Step E — the one generic adapter (replaces the three ad-hoc ones).**

```python
def apply_fixture_to_lesson(lesson_json, topic, card_role="worked_example") -> bool:
    declared = declare_example(topic, card_role)    # §5.1 — DeclaredExample | None
    if declared is None:
        return _fallback(lesson_json, "no_application_match")
    fixture = pick_fixture(declared, card_role)      # §5.2 — keyed by resolved_example_type + pattern
    if fixture is None:
        return _fallback(lesson_json, "no_fixture_for_role")
    resolved_visual = resolve_visual(fixture, declared)   # Step A — fixture override ▸ profile ▸ type default
    if not is_v2_enabled(resolved_visual.base_type, declared.application):
        return _fallback(lesson_json, "feature_flag_disabled")
    example = fixture_to_canonical_example(fixture, declared, resolved_visual)  # Step A
    result  = run_for_registered(example, model_id=f"v2_{declared.application}_{topic['id']}")
    if result["status"] != "validated":              # Step B (visual_pipeline_failed / fixture_validation_failed)
        return _fallback(lesson_json, result["debug"]["failed_stage"])
    milestones = milestone_frame_indices(result["frames"], fixture.profile.milestone_policy)  # Step C
    attach_model(lesson_json, result["model"])                     # Step D
    swap_worked_example_cards(lesson_json, result["model"], result["render_steps"], milestones)
    return True
```
(`_fallback` logs the `legacy_fallback_reason` — §9.1 enum — and returns False so the
legacy path runs.)

Wire it in `lessons.enrich_legacy_lesson_with_v2_visuals`, **flag-gated**
(`is_v2_enabled`), **failure-safe** (any exception → log, leave legacy untouched) —
identical to the current hook. This deletes `apply_v2_to_lesson`,
`apply_binary_search_to_lesson`, and `apply_code_execution_to_lesson` in favour of
this one path.

**Composite (`case_comparison_example`).** Run Steps A–D **once per child fixture**
→ two `VisualModel`s appended to `visual_models`. The comparison card carries
`visual_v2_refs: [ {model_id_left, frame_index}, {model_id_right, frame_index} ]`
plus the `dimensions` list; the renderer lays the two frames side by side. No new
pipeline.

---

## 5. How one declaration drives content *and* visual

```
topic
  │  (deterministic) topic_type + title → declare (example_type, application)  [§3.1 boundary rule]
  ▼
pick a CanonicalFixture for the application (§4)
  │
  ├─▶ VISUAL: feed (input, authoritative visual base_type/mode, simulator) into the V2 pipeline
  │           (CanonicalFixture → Trace → fold → compile → render)  [VISUAL_SYSTEM_SPEC §6]
  │
  ├─▶ WORKED EXAMPLE CONTENT: the same fixture + locked trace; the LLM writes
  │           per-step prose ONLY, validated against the trace (visual spec §5.5).
  │
  └─▶ CARD STRUCTURE: filled into the blueprint slot for this topic type (§6).
```

The example and the visual are the same object viewed two ways, so they can never
drift apart.

### 5.1 `declare_example(topic, card_role) -> DeclaredExample | None` — the exact rule

Deterministic, no LLM. Inputs: `topic.topic_type` (normalised via
`course_blueprints.normalize_topic_type_key`) and `topic.title`. It returns the full
resolution, not just the application name, so nothing downstream has to re-derive it:

```
DeclaredExample {
  application             # the WHAT (binary_search, unique_paths, quadratic_formula)
  resolved_example_type   # the lens AFTER the code-vs-concept gate (sequence_state_trace
                          #   for a concept topic; code_execution_trace for a coding topic)
  pattern                 # the HOW, from the chosen profile (range_halving | loop_execution | ...)
  variant?                # set later from the fixture; carried for telemetry
  card_role               # worked_example | edge_case | practice | comparison
}
```

1. **Title → application** via `APPLICATION_PATTERNS` (the example analogue of
   `visual_v2/integration.detect_mode_algorithm`), e.g. `binary_search` ←
   `r"\bbinary\s+search\b"`; `bfs` ← `r"\bbfs\b|breadth.first"`; `unique_paths` ←
   `r"unique\s+paths"`. Patterns live **in the ontology row**, first-hit in a defined
   priority order (most specific first).
2. **Code-vs-concept gate (§3.1) → `resolved_example_type`:** if
   `topic_type == coding_implementation` and the application's profile has a
   `code_example_type`, resolve to `code_execution_trace` (pattern = the code profile's
   `execution_pattern`); otherwise the application's conceptual `example_type`/`pattern`.
3. **No match → return None** (topic falls through to the legacy free-form path +
   the novel-code safety net of §7). Never guess an application.

`APPLICATION_PATTERNS` lives in `example_applications.py`, validated by the
declaration tests (§9.1): no two patterns claim the same title; coding topics always
gate to `code_example_type`; concept topics never do.

### 5.2 `pick_fixture(declared, card_role) -> CanonicalFixture | None`

An application owns ≥1 fixture (`FIXTURES[application]`). Selection keys off the full
`DeclaredExample` — the **same application needs different fixtures for different
lenses *and* card roles** (a `sequence_state_trace` worked example vs a
`code_execution_trace` walkthrough are different fixtures of `binary_search`):

```
pick_fixture(declared, card_role):
  candidates = FIXTURES[declared.application]
             filtered to declared.resolved_example_type AND declared.pattern
  policy = FIXTURE_SELECTION_POLICY[card_role]
  return first candidate matching the policy's tags/source, else None

FIXTURE_SELECTION_POLICY = {
  "worked_example": "medium_nontrivial",   # found-late, both branches taken
  "edge_case":      "edge_case",           # target absent / boundary value / empty structure
  "practice":       "isomorphic_variant",  # same shape, different values (§7.2)
  "comparison":     "contrast_pair",       # the composite's two children
}
```

**Fixture-id naming convention** — make the lens explicit so concept and code
fixtures never get confused: `<application>_<concept|code>_<pattern/shape>_<NN>`:
```
binary_search_concept_found_late_01      bfs_concept_branching_graph_01
binary_search_code_loop_found_late_01    bfs_code_queue_loop_01
tree_traversal_code_recursive_inorder_01 unique_paths_concept_3x4_01
```
Example: `binary_search + sequence_state_trace + range_halving + worked_example` →
`binary_search_concept_found_late_01`; `binary_search + code_execution_trace +
loop_execution + code_walkthrough` → `binary_search_code_loop_found_late_01`. None if
no fixture matches that role yet — keeping it inert (falls through to legacy) rather
than broken.

### 5.3 Validation stages — five gates, reusing the visual pipeline

Every generated example passes five validators (the first three are mostly the
visual spec's existing validators, §6.0/§6.4 — do **not** reimplement them):

1. **InputValidator** — the fixture's input against `profile.required_invariants`
   (array sorted, graph connected, BST order, matrix dims, formula coefficients).
   *= the visual `ExampleInvariantValidator`.* Fail ⇒ reject the fixture.
2. **TraceValidator** — simulator output: `expected_output` matches the final state,
   `min_steps` met (against *milestones*), transitions legal, no skipped states.
   *= the visual `TraceValidator` + the §4 sizing check.*
3. **VisualValidator** — `(base_type, mode)` is a real pair, frame count matches the
   trace, every highlight target exists. *= the visual `VisualModelValidator`.*
4. **ProseValidator** — the LLM's slot output: uses only `allowed_facts`, hits every
   `required_mention`, contains no `forbidden_mention`, doesn't contradict the frame.
   *= the visual `TextVisualSyncValidator`, scoped to the slot (§4.1).*
5. **CardValidator** — the final lesson: card set == blueprint allowed keys in order,
   roles preserved, continuations valid, no orphan visual, no over-long card.
   *= `_enforce_blueprint_cards` promoted to a validator (§6).*

A failure short-circuits and is logged with the offending stage (the visual spec's
debug payload, §7.1 there). Hand-verified fixtures pass 1–3 at author time (a
golden test), so at runtime only 4–5 can fail.

---

## 6. Card structure — from the legacy blueprints (not the LLM)

The card sequence that "used to work" is `course_blueprints.py`
`default_card_sequence` per topic type. It becomes a **deterministic skeleton**.
Explicit procedure:

1. **Build the slot list.** `get_topic_blueprint(topic_type)["default_card_sequence"]`
   gives the ordered `blueprint_key`s. Each becomes one **slot**. Multi-step slots
   (`worked_example`, `code_walkthrough`) may expand into a *run* of continuation
   cards (one per milestone-frame / one per revealed code line); that expansion is
   driven by the fixture's trace (§4.5 Step C), **not** the LLM.
2. **Fill the example slots from the fixture** (deterministic): the
   `worked_example` slot's cards get `visual_v2_ref` (§4.5 Step D); the
   `code_walkthrough` slot's snippet is the fixture's verified `code` (incrementally
   revealed, one validated line per card).
3. **The LLM fills each slot's *prose only*** — given `(slot blueprint_key, the
   slot's frame/code, the learner_goal)`, it returns the bullets for that card. It
   **may not** add, drop, reorder, or re-type cards, choose the example, or author
   code. Output schema per slot: `{ points: [str], title?: str }` — nothing else.
4. **Optional cards** (`blueprint["optional_cards"]`) are included only when the
   fixture/topic supplies content for them (e.g. an `edge_case` fixture exists);
   otherwise the slot is omitted, not emptied.
5. **No empty cards.** If a milestone or its `ProseSlot` fails validation (§5.3), do
   **not** emit a blank continuation card — drop that one continuation if the slot is
   part of an optional run, or fail the whole apply to legacy if it's a required
   worked-example step. A worked-example page is never blank.

Enforcement is the same deterministic filter already proven on the intro
(`_enforce_blueprint_cards`): the final card set is exactly the blueprint's allowed
keys in blueprint order. This is why the intro is already correct; extend it to
every topic type by building from the skeleton instead of filtering after the fact.

---

## 7. What this retires (the band-aids)

Once the application is the source of truth, the symptom-patches disappear:

| band-aid (today) | replaced by |
|---|---|
| canonical code as a *fallback* when codegen breaks | canonical code as the application's **definition**, used everywhere |
| `_fix_dedented_body_lines`, `_strip_module_level_strays`, `_split_accumulator_recursion`, `_synthesize_main_for_helper` | not needed — the code was verified before it shipped |
| `_fix_code_layout` blank-line/indent surgery | canonical code is already well-formed |
| `_enforce_blueprint_cards` filtering | the skeleton was deterministic from the start |
| "ensure ≥4 steps" heuristics | `min_steps` on the canonical example |
| worked example ↔ visual mismatch repairs | one declaration drives both |

Novel/custom topics (no matching application) keep a **safety net**: validate the
LLM's example + code (parses, runs, produces `expected_output`, meets `min_steps`);
regenerate on failure (the visual spec's §6.0 ExampleInvariantValidator + bounded
retry).

### 7.1 Fixture sources — three tiers (don't hand-author everything)

A fixture's `source` (§4) says how its input was produced, so we scale without
hand-writing thousands of fixtures:

| `source` | for | how it's trusted |
|---|---|---|
| `hand_verified` | high-frequency canonical topics (binary_search, bfs, dfs, inorder, unique_paths, quadratic_formula, row_reduction, bayes, …) | a golden test runs the trace + checks output/sizing at author time |
| `generated_deterministic` | easily-generated, deterministically-checkable (linear_equation, formula_substitution, truth_table, matrix_multiplication, mean/variance, distance_formula) | a small generator emits the input; validators 1–3 (§5.3) verify each instance |
| `llm_validated` | genuinely novel / material-specific topics with no application | the LLM proposes input+code; it **must** pass all five validators (§5.3) or regenerate (bounded) |

Tier order at runtime: prefer `hand_verified`, else generate, else LLM-validated,
else fall through to the legacy free-form path. Higher tiers are deleted only when a
lower one is proven by telemetry.

### 7.2 Isomorphic practice variants

Practice is not random. After the worked example, a `practice` card uses an
**isomorphic variant** of the same fixture — same `step_roles`/reasoning shape,
different concrete values (`binary_search [2,5,8,…,72] target 72` → practice
`[1,4,7,…,68] target 52`). A fixture lists its variants (`practice_variants[]`);
they're either hand-paired or generated by the Tier-2 generator with the same
`sizing` constraints, so practice stays aligned to the lesson with zero extra LLM
authoring.

---

## 8. Files

Keep the **stable ontology** separate from the **large, growing fixtures** — they
have different change rates and sizes:

```
backend/app/core/example_ontology.py        small, stable — EXAMPLE_TYPES,
                                             APPLICATIONS_BY_TYPE, *_DESCRIPTIONS,
                                             EXAMPLE_TYPE_TO_DEFAULT_VISUAL,
                                             STEP_ROLES_BY_EXAMPLE_TYPE, describe()
backend/app/core/example_applications.py     APPLICATION_PROFILES (§3.4) + APPLICATION_PATTERNS (§5.1)
backend/app/core/example_fixtures.py         FIXTURES — the concrete instances (arrays, graphs,
                                             code, expected outputs); grows fast, lives alone
backend/app/services/examples/declaration.py  declare_example (§5.1) + pick_fixture (§5.2)
backend/app/services/examples/handoff.py       fixture_to_canonical_example + apply_fixture_to_lesson (§4.5)
backend/app/services/examples/prose_slot.py    build ProseSlots (§4.1) + the slim LLM call (§8.1)
backend/app/services/examples/validators.py    the five validators (§5.3), reusing visual_v2 where noted
backend/app/core/visual_ontology_v2.py        the tandem target (base_type, mode)
backend/app/core/course_blueprints.py         the card skeleton (§6)
backend/app/services/visual_v2/               the trace authorities + pipeline + telemetry (reused unchanged)
```

`example_ontology.py` mirrors `visual_ontology_v2.py` exactly: a tuple of types, a
`dict` of applications per type, parallel `*_DESCRIPTIONS` dicts, and a `describe()`
helper — read and extended identically.

### 8.1 Efficiency — the LLM call is tiny

The backend resolves the fixture, trace, frames, and prose slots **before** any LLM
call. The model is sent only a single slot (§4.1) — never the ontology, all
applications/fixtures, every visual type, the codebase, or the legacy blueprint text:

```
Write the bullets for this step (≤ max_words).
  step_role: discard_left_half
  allowed_facts: [low=0, high=10, mid=5; array[mid]=23; target=72; 23 < 72; new low=6]
  required: [target must be to the right; low moves to mid + 1]
  forbidden: [code syntax; new array values]
```

Tiny, grounded, and reliable. **The unit of grounding is one `ProseSlot`, but the
runtime MAY batch several slots in one call** (`{ slots: [ProseSlot…] } →
{ slot_outputs: [{slot_id, points}…] }`) — each output keyed by `slot_id` and
validated separately by the ProseValidator (§5.3). Batching cuts latency for a
many-step example without weakening grounding (each slot is still fact-bounded). Use
`single_slot_call` for hard/edge slots, `batched_slot_call` (4–6 slots) for the rest.

---

## 9. Migration (incremental, reversible)

1. **Ontology + profiles + first fixtures** — `example_ontology.py` (types,
   descriptions, step_roles, default visuals), `example_applications.py` (profiles +
   patterns), `example_fixtures.py` (first hand-verified fixtures). The first
   **applications**: `binary_search`, `bfs`, `dfs`, `unique_paths`,
   `quadratic_formula`. With **code-lens fixtures** (the `code_execution_trace`
   resolution) for `binary_search` (pattern `loop_execution`), `tree_traversal`
   (pattern `recursive_execution`), and a `function_call` accumulator. Golden-tested
   (validators 1–3 at author time).
2. **Declaration + selection** — `declare_example` (§5.1) + `pick_fixture` (§5.2),
   deterministic. `case_comparison` declares two child applications.
3. **Handoff + prose slots** — `apply_fixture_to_lesson` (§4.5) drives the visual via
   the existing V2 pipeline; the skeleton fill (§6) places the fixture and routes the
   LLM to `ProseSlot` calls (§4.1); the five validators (§5.3) gate it.
4. **Widen** application-by-application (node_link ops → grid/table → symbolic → plot
   → geometric → set/logic → timeline → proof; `case_comparison` last). Each adds a
   profile + fixtures (+ a simulator or Tier-2 generator, §7.1), gated by the same
   telemetry as visuals (`visual_v2/metrics.py`).
5. **Retire** the band-aids in §7 as each application comes online; the legacy
   free-form path becomes the fallback for unrecognised topics only.

### 9.1 Required tests + telemetry (from day one)

**Declaration tests** (a formal category — bad routing is silent and costly):
```
"Binary Search" + algorithm_walkthrough     → binary_search (sequence_state_trace)
"Implementing Binary Search" + coding        → binary_search (code_execution_trace, pattern loop_execution)
"BFS Traversal of a Graph"                    → bfs
"Unique Paths (DP)"                           → unique_paths (grid_table_trace, pattern dp_table_fill)
"Quadratic Formula"                           → quadratic_formula (symbolic_derivation)
<unknown title>                               → None  (→ legacy)
+ no two APPLICATION_PATTERNS claim the same title (collision test)
+ coding_implementation always gates to code_example_type; concept topics never do
```

**Telemetry** (emit per build, extend the visual `metrics.py`): `example_application`,
`resolved_example_type`, `pattern`, `fixture_id`, `fixture_source`, `variant`,
`validation_failed_stage`, `prose_validation_retry_count`, `raw_frame_count`,
`milestone_count`, `legacy_fallback_reason`, `llm_tokens_per_slot`, `time_to_trace_ms`,
`time_to_render_ms`, `time_to_prose_ms`. These answer the only question that matters:
**is the ontology path actually more accurate/cheaper than the free-form path?**

`legacy_fallback_reason` is a closed enum (so dashboards can bucket failures):
```
no_application_match · no_fixture_for_role · fixture_validation_failed
visual_pipeline_failed · prose_validation_failed · card_validation_failed
feature_flag_disabled · unsupported_example_type · unsupported_visual_mode
```

---

## 10. The one-line summary

This is a **worked-example compiler**: a declared example goes in
(`type → application profile → fixture source → fixture`) and a *verified trace +
visual + grounded explanation* comes out. The fixture/profile owns the input, code,
sizing, invariants, step-roles, and visual target; the five validators (§5.3) gate
every stage; the LLM's entire job shrinks to writing one small, fact-bounded
`ProseSlot` per step. The example and its visual are the same object viewed two
ways, so they cannot drift — and the band-aids (§7) that patch today's free-form
generation disappear.
