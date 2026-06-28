# Adapter Contract — the authoring checklist

> An adapter is not merely an algorithm implementation. It is a **versioned educational semantics
> contract**: it defines how truth is executed, which transitions are worth teaching, how completeness is
> measured, and how learner-facing claims are constrained.

Every trace adapter (WORKED_EXAMPLE_REASONING_SPEC §15) must satisfy **all of section A** and follow its
**section-B family row**. No adapter ships partially filled — that is how inconsistency crept in. Conformance
is **enforced in code** (`trace_adapters/contract.py` + `tests/test_adapter_conformance.py`).

> Writing a new adapter = fill the contract + follow the family row + ship its behavior tests. Nothing ad hoc.

**Status: FROZEN** (converged over 5 review rounds). The structural core is enforced in code today; the §0
`ExampleSpec`/`StageSpec` and the raw→teaching layer split are the **C1** target (see Conformance levels).

## Conformance levels
The contract is the **target** shape (aligned with WORKED_EXAMPLE_ACCURACY_SPEC's `raw_log → teaching_trace →
cards`). Items are tagged:
- **[now]** — the **structural core the conformance checker enforces today**; all 8 current adapters *pass
  that checker* (identity, trace shape, conventions, required-case evidence, per-step facts/visual, the
  structural gate). *Caveat:* the checker is a **subset** — the §E per-adapter behavior suites and the
  versioned state schema are documented but **not yet machine-checked**, so passing the checker ≠ fully
  conformant. Legacy adapters are **grandfathered** behind the existing path until their migration completes.
- **[C1]** — the post-C1 target (the raw→teaching split, `ExampleSpec`/`StageSpec`, `TeachingTracePolicy`,
  structured facts); documented now, **enforced once C1 lands**.

`adapter_contract_violations()` enforces the **[now]** core; `adapter_c1_gaps()` lists missing **[C1]** items.
**Fully conformant** = passes the checker **AND** ships its §E behavior tests **AND** has zero C1 gaps.

---

## 0. The Example Specification (`ExampleSpec`) — the declarative envelope [C1]

The heart of "**guidelines, not examples**." Each adapter declares **one** `ExampleSpec` that constrains the
*shape* of every example without fixing any value. `candidates()` generates **inside** it,
`is_teaching_trace()` **checks** it, completeness **checks** it — all from this one object.

```python
class ExampleSpec:
    input:         InstanceShape        # how the problem is formed: value type, counts, ranges, structure
    size_tier:     "small" | "medium"   # size bounds for pacing + cognitive load
    must_exercise: list[CoverageCase]   # per-INSTANCE: situations ONE chosen trace must contain (each w/ a "why")
    must_cover:    list[CoverageCase]   # per-ADAPTER: situations the test SUITE must show across instances
    must_avoid:    list[str]            # degenerate anti-cases (valid but pedagogically useless)
    transition:    StageGrammar         # the STAGES + their boundaries + sequencing (below)
    terminal:      TerminalShape         # what "complete" is + the output shape
    tie_break:     str                   # the rule when several choices are equally valid
    variety:       VarietyPolicy         # vary per study path; avoid recently-used equivalents
```

### The four layers (the only correct hierarchy)
```
raw events          literal implementation actions (pointer writes, counter bumps, heap sifts)
   v classified
semantic operations algorithm-level facts: pop, relax, accept, union, merge-select   (role: required|supporting|internal)
   v grouped by a stage boundary
teaching stages     ONE controlled learner decision = one or more semantic operations  (always surfaced)
   v narrated
cards               the LLM's prose for one verified teaching stage
```
**`internal`/`supporting` are properties of *semantic operations*, never of stages.** A stage is always a
learner-facing unit; internal logic lives *below* it (inside `contains`). This is the review's key fix.

### `transition` = a stage grammar with an EXECUTABLE boundary
Each adapter declares the **stages** (one learner decision each) — heterogeneous algorithms get several,
repetitive ones (binary search, BST traversal) get a single stage. `Step.operation` = the **surfaced** stage
id. A grammar MAY also contain **non-surfaced phase markers** (e.g. `merge_pass_start`) for sequencing
context only: they are **not** `Step` instances, have **no card**, and never appear in `Step.operation`.

```python
Predicate = "StatePredicate | Callable"   # declared, but MAY be a tested pure function when config is too weak

class StageSpec:
    id: str                       # the Step.operation value
    primary_decision: str         # the ONE learner-facing decision this stage is
    teaching_focus: str           # constrained pedagogical label (NOT truth-bearing) — anchors title/goal/reasoning
    # --- executable grouping boundary (limits, not prose) ---
    primary_entity_limit: int = 1 # ONE node / edge / merge-selection / probe per step
    core_decision_limit:  int = 1 # one learner DECISION per step — the hard line (aggregate support, never decisions)
    max_core_iterations:  int = 1 # one loop iteration per step
    contains: dict[str, str]      # semantic op -> required | aggregated_supporting | optional_supporting | internal
    aggregation_safe_when: list[Predicate]    # aggregate repeated support ONLY when the learner needn't choose between them
    forbidden_combined: set[str] = set()      # ops that must NOT co-occur in one step
    # --- truth (state effects) vs explanation (prose facts) — DISTINCT ---
    state_effects: list[StatePredicate]       # machine-checked consequences that MUST hold in state_after (validate the TRACE)
    fact_contract: FactContract               # claims the card MUST communicate (validate the EXPLANATION)
    # --- occurrence + pacing ---
    min_occurrences: int          # exactly_once=1/1 . zero_or_once=0/1 . one_or_more=1/cap . zero_or_more=0/cap
    max_occurrences: int | None
    required_if_triggered: bool = False
    trigger: "Predicate | None" = None        # MACHINE-CHECKABLE (e.g. "endpoints already share a component")
    # --- placement + presentation ---
    allowed_previous: set[str]; allowed_next: set[str]
    visual_kind: str
    max_visible_state_changes: int | None = None   # ADVISORY pacing for visual density (steers instance/visual choice; never invalidates a correct trace)
```
`state_effects` validate the **trace** (e.g. *queue_after = queue_before − node + new neighbors*); the
`fact_contract` validates the **explanation** (e.g. *"the queue now holds B and C"*). They overlap but are
not the same — keep them separate. Semantic conditions too complex for static config (`trigger`,
`aggregation_safe_when`, `state_effects`) may be **tested pure functions**; the adapter still *declares* them.

**`contains` roles (how each semantic op may appear in the step):** `required` = must appear as a semantic
claim · `aggregated_supporting` = may recur, shown as ONE summarized stage effect (not a bullet each) ·
`optional_supporting` = may appear, not required · `internal` = affects execution, never a standalone fact.

**The four granularity rules (now executable):**
1. **One step = one stage instance**, bounded by `primary_entity_limit` / `core_decision_limit` /
   `max_core_iterations` -> **no tiny steps, no mega-steps, always reconstructable.**
2. **Cardinality is explicit bounds**, not "repeats." `min/max_occurrences` give predictable pacing; Stage 0
   **rejects** an instance that would exceed `max_occurrences`.
3. **Aggregate support, never decisions.** A step may bundle *repeated supporting* ops ONLY when the learner
   needn't independently CHOOSE between them to reconstruct the algorithm (`aggregation_safe_when`):

   | safe aggregate (ONE decision) | unsafe compression (MANY decisions) |
   |---|---|
   | BFS: enqueue **all** neighbors of one dequeued node | merge sort: pick **3** output values (each a separate compare) |
   | Prim: push **all** new frontier edges after adding one vertex | binary search: **two** probes (each changes the interval) |

   So `merge_select` / `probe` are `required` per step (one decision each); `push_frontier_edge` /
   `enqueue_neighbor` are `aggregated_supporting`. `state_effects` then guarantees the *aggregate*
   before/after is still shown (e.g. "frontier now reflects the new vertex"), so nothing meaningful hides.
4. **Stage boundaries are semantic, not merely numeric.** The limits (one entity / decision / iteration) are
   necessary but **not sufficient**: a stage is valid only when its included operations together explain
   **one coherent algorithmic choice and its resulting state effect**. Adapters may use tested semantic
   predicates to enforce that coherence — you can't satisfy the counts while building a confusing stage.

**Phase-1 stage↔card invariant:** every **surfaced** teaching stage maps to **exactly one card**, and no card
cites more than one surfaced stage. (Non-card phase markers like `merge_pass_start` are not surfaced.) Phase
2+ may merge adjacent stages into one card **only** via a declared, validated stage-combination rule.

**Triggers replace vague "if observed":** a `required_if_triggered` stage fires its `trigger` predicate
against the reference run; completeness then reads *"trigger occurred AND stage absent -> fail"* — exact, not
fuzzy. **`required_if_triggered` OVERRIDES `min_occurrences`** (don't set both meaningfully); `max_occurrences`
still applies:
```python
def effective_min_occurrences(stage, raw_log) -> int:
    if stage.required_if_triggered:
        return 1 if stage.trigger(raw_log) else 0   # the trigger decides; min_occurrences is ignored
    return stage.min_occurrences
```

**Grammar vs policy (no duplication):** the `StageGrammar` (§0) owns stage **grouping, sequencing, and
cardinality**; `TeachingTracePolicy` (§A item 5) owns **instance acceptance, representative-coverage
requirements, and trace-budget selection**. The policy *references* the grammar; it never duplicates it.

### Two coverage scopes (the BST fix)
A single trace can't demonstrate every case, so coverage splits:
```
must_exercise (per INSTANCE):  what ONE chosen trace must contain  (e.g. deletion target found; valid result; N-1 nodes)
must_cover    (per ADAPTER):   what the suite must show ACROSS instances  (leaf . left-only . right-only . two-child . root)
```
Stage 0 never hunts for an impossible single example; the adapter's test suite guarantees breadth.

### Stage table (boundary = the limits above)
| Concept | Stages (occurrence) | One step (primary_entity_limit) |
|---|---|---|
| **BFS** | init(1/1) . process_node(1+/cap) | dequeue **one** node + enqueue all its unvisited neighbors |
| **Dijkstra** | init(1/1) . settle_node(1+/cap) . relax_edge(1+/cap) . completion(1/1) | settle **one** nearest node, OR **one** edge relaxation (improves / does not) — the relaxation IS the decision; dist/pred/heap updates `aggregated_supporting` |
| **Bellman-Ford** | init(1/1) . relax_edge(1+/cap) . pass_complete(1+) . negative_cycle_check(required_if_triggered) . completion(1/1) | **one** edge relaxation — **NO `settle_node`** (repeated full passes); a negative-cycle pass when triggered. Shares the weighted normalizers / dist+pred maps / relaxation facts / visuals, but a **distinct grammar** |
| **Kruskal** | setup_sorted_edges(setup card) . consider_edge(1+/cap) . cycle_skip(required_if_triggered: endpoints share component) . completion(1/1) | **one** edge -> accept/skip (groups find+find+union+append). **Sorting is SETUP** (show the ordered list in the setup card), not its own decision card — unless "why sort first?" is the teaching goal |
| **Merge sort (bottom-up)** | init_runs(1/1) . merge_select(1+/cap) | **one** output selection (compare two heads, copy the smaller); a full merge only if the runs are tiny + marked safe aggregate |
| **BST insert** | descend(1+/cap) . attach(1/1) | **one** compare-and-go |
| **BST deletion** | descend(1+/cap) . one of {remove_leaf, splice_one_child, replace_successor} (each required_if_triggered) | descend, then **one** removal |

Adapters declare their **exact variant** — these are **different grammars**, one vague family grammar may not
cover both:
- *recursive*: split . base_case . merge_select . tail_copy . return
- *bottom-up*: init_runs . **merge_pass_start** (non-card phase marker) . merge_select+ . tail_copy? .
  merge_complete (summary) . [next merge_pass_start] . completion

So `merge_pass_start`/`merge_complete` are phase context; `merge_select` (and `tail_copy`) are the
learner-facing card stages.

### Filled illustrations (guidelines, zero values)
**Binary search** — single stage:
```
input:         sorted-ascending ints, 6-9 distinct, 1-60; target present 70% / absent 30%
stages:        probe (one_or_more, primary_entity_limit=1): "compute mid, compare, move ONE bound"
must_exercise: a lower-bound move . an upper-bound move . the found/absent terminal   must_avoid: found on first probe
terminal:      lo>hi (absent) or arr[mid]==target (found);  output: index or -1
```
**Merge sort (bottom-up)** — declared variant:
```
stages:        init_runs (exactly_once);  merge_select (one_or_more, primary_entity_limit=1): "compare two run heads, copy the smaller"
contains(merge_select): {compare_heads: required, copy_value: required, advance_pointer: aggregated_supporting, tail_copy: aggregated_supporting}
required_stage_effects: one output value placed in order; the two run-heads reflect the copy
must_exercise: a multi-element merge;   terminal: one sorted run of length N    (full-merge-per-card allowed only for tiny runs, marked safe)
```
**BST deletion** — triggers + two scopes:
```
input:         distinct ints, 7-10 nodes, valid BST, height >= 3
stages:        descend (one_or_more);  remove_leaf / splice_one_child / replace_successor (required_if_triggered)
               triggers: splice_one_child <= target has exactly one child; replace_successor <= two children
must_exercise (per instance): target found . valid result BST . N-1 nodes
must_cover (per suite):       leaf . left-only splice . right-only splice . two-child successor . root deletion
must_avoid:    deleting the root immediately (unless the root-deletion suite case);  output: tree of N-1 nodes
```

### What `ExampleSpec` lets the contract check (mechanically)
- generated instances stay **inside `input`**; Stage 0 rejects ones exceeding `max_occurrences`;
- **every step is one stage instance** (`Step.operation` in stage ids) within its `primary_entity_limit`;
- the teaching trace contains **every `required` stage**, **every triggered `required_if_triggered` stage**,
  in legal `allowed_previous/next` order, with **no `internal` semantic op surfaced as its own step**;
- all `must_exercise` (per instance) hit, no `must_avoid` hit; the final step matches `terminal`;
- `must_cover` (per suite) is checked by the adapter's behavior tests (section E), not a single trace.

This **subsumes** the teaching policy's grouping/suppression/cardinality (section A item 5) into one model.
`candidates`, `is_teaching_trace`, and `required_cases` all **derive from** this object — every concept gets
the *same level* of structure, with *exactly* what's in each step.

> **The principle (§0 in one line):** a card may contain many low-level actions, but it must expose exactly
> **one learner decision** and **one reconstructable before/after transition**. Safe aggregation bundles
> *support*; it never compresses *decisions*.

## A. Universal contract — the 15, identical for every adapter

| # | Member | What it is | Rule | Lvl |
|---|---|---|---|---|
| 1 | `slug`, `version`, `family` | identity | non-empty str + int; one slug per algorithm, in its family file | now |
| 2 | `candidates(seed)` + acceptance policy | **deterministic seeded** instance stream | enough valid diversity for the family's acceptance + recent-equivalence policy; bounded so a trace fits the card budget (**not** a fixed "≥N") | now |
| 3 | `run_reference(instance) -> RawExecutionLog` | the real algorithm's **raw** events (incl. internal ones) | the ONLY source of step values; no LLM | C1 |
| 4 | `build_teaching_trace(raw_log) -> ContractTrace` | curate raw → learner-facing transitions | suppress internal events, group supporting ones, keep required ones | C1 |
| 5 | `teaching_trace_policy: TeachingTracePolicy` | the object that makes completeness **non-arbitrary** | owns instance-acceptance + min/max transition count + representative-branch. **Grouping, suppression, and cardinality live in the §0 `transition.stages` grammar** (one model, not two). `is_teaching_trace` implements it | C1 |
| 6 | **canonical state schema** (versioned) | the fields of `prior_state`/`state_after` | declared required fields (always present) + optional fields (explicitly declared) + stable null/empty when absent; **no undeclared dynamic fields** | now |
| 7 | **conventions** (on the trace) | every semantic choice needed to define correctness | non-empty (order, tie-break, when-marked, granularity) | now |
| 8 | **teaching-step unit** (`Step.operation`) | one **stage instance** = one card (§0) | non-empty `operation` = a declared stage name; exactly one stage per step | now |
| 9 | `required_transition_ids` + `case_evidence` | the must-show set, with **stable ids** | family-defined, typically **2–5, representative not exhaustive**; the real rule = *every required id maps to a rendered transition, every required case has evidence* | now |
| 10 | `states_equivalent`, `final_answer_entails` | semantic equality / answer check | semantic, **never** dict-equality; tolerates declared representational variation | now |
| 11 | scoped invariants + `invariant_holds` + `validate_step_shape` | every_step / final_only properties + structural check | non-empty; each machine-checkable | now |
| 12 | **structured prose fact contract** + `validate_prose_claims` | per-step facts as **predicate objects** (§C) + family-specific contradiction check | formatter gets the readable `text`, validator uses the structured fields | C1 (string form **now**) |
| 13 | **visual contract** | `primary_kind` + `allowed_kinds` + optional `operation_to_kind` (§D) | every teaching transition can produce a `visual_state` with a `kind` from the allowed set | now (single-kind) / C1 (map) |
| 14 | **final_answer** schema | the answer object | not None; checked by #10 | now |
| 15 | **behavior test fixtures** | the adapter's own bad-behavior tests (§E) | conformance + ≥1 family-specific hallucination caught | now |

**Definition of done (L0):** `adapter_contract_violations(adapter) == []` — `select_instance` → all **[now]**
items + `structural_invariants == []`. **Definition of done (L1):** also `adapter_c1_gaps(adapter) == []`.

---

## B. Per-concept-type specialization — the shape every family member shares

| Concept family | State schema | Step = | Required transitions (pattern) | Visual: primary → allowed | Answer |
|---|---|---|---|---|---|
| **Graph traversal** (BFS, DFS) | frontier(queue/stack), visited, order | process one node | expand_neighbors · skip/revisit · completion | `queue_graph`/`stack_graph` → {graph_state, visited_order_strip} | visit_order |
| **Graph weighted** (Dijkstra, Kruskal, Prim, Bellman-Ford) | dist/selected_edges, visited/components/in_tree | consider/settle one edge-or-node | progress (relax/accept/select) · no-progress (skip/no-improve) · completion | `weighted_graph` → {dist_graph, frontier_table} | mst_edges+weight / dist_map |
| **Array scan** (binary search, two-pointer, sliding window) | bounds/cursors, found/window | one probe / pointer move | move-down · move-up · terminal(found/absent) | `array_window` → {pointer_array} | index / result |
| **Sorting** (merge sort, …) | runs / array | one merge-**selection** (full merge only if runs are tiny + marked safe aggregate) | merge-select · tail-copy · completion | `run_list` → {split_tree, merge_pointer_array} | sorted array |
| **DP** (knapsack, LCS, edit distance) | table cells | fill one cell | base-case · recurrence-fill · optimum-read | `dp_table` → {cell_dependency} | optimal value |
| **Data-structure op** (BST, heap, linked list) | structure shape, cursor | one structural op | locate · modify · rebalance/terminal | `tree`/`list_chain` | resulting structure |
| **Formula** (arithmetic, recurrence, Big-O) | expression tokens | one operation | high-precedence-first · low-precedence · completion | `expression` | value |

Required-transition counts are **policy targets, not universal constants** — a linked-list insertion may need
5 (locate · head-case · link-predecessor · link-successor · integrity), a small formula only 2.

---

## C. Structured prose facts (item 12)
Facts are predicate objects; the formatter receives `text`, the validator uses the structured fields (so a
correct paraphrase like *"advance the left boundary past the midpoint"* isn't falsely flagged against
*"set low to 6"*):
```python
{"predicate": "state_change", "field": "low", "before": 0, "after": 6, "text": "Move low from 0 to 6"}
{"predicate": "decision", "subject": "edge", "value": ["B","C",4], "outcome": "reject", "text": "Reject edge (B,C,4)"}
```
The string bundle (`allowed_values`/`required_facts`/`forbidden_claims`) is the **[now]** form; predicate
objects are the **[C1]** upgrade.

## D. Visual contract (item 13)
A family is not flattened to one diagram — an adapter declares a set:
```python
visual_contract = {"primary_kind": "weighted_graph",
                   "allowed_kinds": {"weighted_graph", "dist_graph", "frontier_table"},
                   "operation_to_kind": {"accept_edge": "weighted_graph", "relax_distance": "dist_graph"}}
```
Requirement: **every teaching transition produces a `visual_state` whose `kind` is in `allowed_kinds`.**

## E. Required per-adapter behavior tests (item 15)
Conformance ≠ happy-path. Each adapter ships tests asserting the *negative* and family-specific cases:
- invalid instance rejected · trivial instance rejected · oversized trace rejected (pacing cap)
- required-case evidence present · a **missing required transition fails completeness**
- `states_equivalent` tolerates allowed representational variation
- a known **invalid transition fails invariant validation**
- the prose validator catches **one representative family hallucination**, e.g.
  - Kruskal: *rejecting a cycle edge must not merge components*
  - DFS: *a node can't be "visited" unless popped (visited-on-pop)*
  - binary search: *a comparison below target moves the **lower** bound, not the upper*
- `visual_state` generates for **every** teaching transition

## F. Conformance vs quality (two levels — keep separate)
- **Conformance** (this contract, per-instance): does the adapter implement the interfaces + invariants?
- **Quality** (multi-seed, statistical): do *selected* examples consistently meet pedagogical standards —
  avg teaching-transition count in the family's target range · required cases appear reliably · equivalent
  structures not overused · prose-contradiction + format-retry rates below threshold · visual generates for
  all transitions. An adapter can be conformant yet low-quality; track both.

## G. What is NOT in the adapter
No stored example values, no fixed learner prose, no LLM prompt/rules. The adapter is **executable truth + a
contract**. (`canonical_code` for displayed-code highlighting is a separate, later concern — not here.)

## H. Coverage & the non-match strategy
Not every concept gets a dedicated adapter — and one that doesn't **never gets a fabricated example**. It
degrades down a **ladder of honesty**. We hardcode the bounded computational core; the long tail degrades.

**Coverage spectrum (most → least specific):**
| Match | Treatment | Guarantee |
|---|---|---|
| **specific adapter** (Kruskal) | Tier 1 | hard |
| **generic family adapter** — ONE executor for a whole class (an arithmetic/expression evaluator; a DP-table filler over a recurrence DSL) | Tier 1 | hard — **only if the concept compiles into a DECLARED generic spec** (below) |
| **independent answer anchor** (Tier 2, WORKED_EXAMPLE_ACCURACY_SPEC §7) | soft | final answer verified, steps not |
| **guided "Key process"** | guided_fallback | no claim, no fake |
| **illustrative** | non-verified | factual checks only |

**Generic family adapter — the safe boundary.** A generic adapter is Tier 1 **only when the concept compiles
into a declared generic spec** whose execution semantics, state schema, stage grammar, terminal predicate,
and teaching policy are all validated — never from a vague "executor."
- **Safe today:** an arithmetic/expression evaluator (explicit AST + operator precedence + fixed stages + evaluable output).
- **Plausibly safe:** a DP-table adapter over a *recurrence DSL* (declared fill order + base cases + cell deps + optimum extraction).
- **NOT automatically safe:** a "generic graph executor" — graph material needs **specific declared policies**
  (traversal / shortest-path / MST / topological-order / flow) that **share infrastructure** (weighted
  normalizers, dist/pred maps, relaxation facts, graph visuals) but are **distinct grammars**, not one adapter.

**The variant rule (close-but-not-exact):** a topic uses a **separate adapter only when its declared
differences change the learner-facing semantics, trace state, required stages, terminal interpretation, or
canonical-code mapping**. **Internal optimizations that don't change the teaching trace stay under the same
adapter** (their events are `internal`) — e.g. **union-find path compression is internal to Kruskal**, not a
new variant. Genuine variants (→ a separate adapter, or Tier 2 if none exists):
- *Kruskal/union-find* — only if the lesson **teaches** union-find internals / shows parent-pointer mutations.
- *Dijkstra* — negative-weight edges · multi-source init · early-stop vs full-distance · a learner-visible
  heap/frontier or tie-break/predecessor convention differing from the canonical adapter. (A **directed**
  graph is **not** a variant — Dijkstra is fine on digraphs.)
- *BST* — duplicate-key handling that changes the structure.

Forcing the wrong adapter ships a *confidently wrong* trace (`false-hard`): **soft-correct beats hard-wrong.**

**Promotion:** same family, no adapter yet → Tier 2 now; promoting to Tier 1 is cheap (fill §A + the §0
`ExampleSpec`, reuse the family's generators/normalizers/visual). The **Tier-2 hit-rate IS the prioritized
backlog** — coverage grows where it's needed, not speculatively. We never enumerate the infinite tail.
