# Adapter Catalog — Verified-Trace Concept Coverage

> **Purpose.** The complete catalog of concepts Azalea may support with deterministic, verified-trace
> worked-example adapters.
>
> This is an **adapter coverage catalog**, not an instruction to implement every row immediately (see
> `ADAPTER_DEVELOPMENT_SPEC.md` §scope guard). A concept becomes production-supported only after:
> 1. Its adapter type has passed its pilot gate (`ADAPTER_DEVELOPMENT_SPEC.md` §2.1).
> 2. Its deterministic reference trace exists.
> 3. Its fixtures, visual contract, routing aliases, and negative guards exist.
> 4. Its per-adapter, per-type, and adversarial tests pass.
> 5. Its manifest entry is complete.
>
> The catalog includes:
> - **Coding adapters** — canonical code plus verified execution/teaching trace.
> - **Non-coding adapters** — verified mathematical, scientific, logical, or system-state trace with no
>   canonical program shown.
> - **Eligibility-review topics** — topics that may need guided or answer-anchored instruction rather than a
>   dedicated trace adapter.

---

## 0. Catalog rules

### 0.1 One row = one adapter boundary
A row represents ONE distinct trace: one algorithm · one operation with different state transitions · one
recurrence/derivation/governing-equation family · one explicit mode whose trace invariant differs materially.
`BST insertion` and `BST deletion` are separate adapters; `directed` and `undirected` cycle detection are
separate; `preorder`/`inorder`/`postorder` share a template but get distinct adapter IDs; `KMP prefix-table`
and `KMP matching` are separate; `regression prediction` and `gradient-descent fitting` are separate.

### 0.2 Shared template ≠ shared adapter
Many adapters reuse the same type template, visual compiler, and harness. They still need independent `slug`,
routing aliases + negative guards, fixtures, required cases, trace semantics, visual contract, canonical
solution (coding), and manifest entry. Never merge two different trace grammars behind one slug.

### 0.3 Family packages, not one growing file
Use family **packages**, split by concern once a module grows (~>8–12 adapters or unrelated trace grammars):
`graph/{traversal,shortest_paths,connectivity,mst}.py`, `sequence/{sorting,searching,windows}.py`,
`math/{algebra,calculus,linear_algebra}.py`. Today's families have 1–2 adapters each (single files); split when
they grow — don't pre-split.

---

## 1. Status and trace-type key

**Status:** ✅ production · 🟨 pilot (implemented, gate not fully signed off) · 🟩 template · ⬜ planned ·
◇ eligibility review (may become answer-anchored/guided instead of trace-verified).

| Type | Name | Typical concepts |
|---|---|---|
| T1 | Iterative traversal | BFS, DFS, tree traversals, linked-list traversal |
| T2 | Greedy frontier update | Kruskal, Prim, Dijkstra, A* |
| T3 | Divide and conquer | Merge sort, quicksort |
| T4 | Search and narrowing | Binary search, BST search, ternary search |
| T5 | Table / DP fill | Knapsack, LCS, edit distance |
| T6 | Formula application | Quadratic formula, kinematics, circuits |
| T7 | Reduction / rewriting | Algebra simplification, Euclid GCD, Gaussian elimination |
| T8a | Incremental construction | Matrix multiplication, truth tables, sieve |
| T8b | Formal derivation | Induction, symbolic derivation, proofs |
| T9 | Repeated relaxation / iterative refinement | Bellman–Ford, PageRank, value iteration |
| T10 | Stateful invariant maintenance | Heap ops, cache simulation, memory allocation |
| T11 | Constraint search / backtracking | N-Queens, Sudoku, subset construction |
| T12 | Program execution / memory trace | Loops, recursion, pointers, stack frames |

> **Note.** Part A (coding, A0–A16) and Part B (non-coding math/EE/science/finance, B0–B11) are the concepts
> that can be trace-verified; Part C is eligibility-review (guided/answer-anchored). Machine-checkable status
> per SHIPPED adapter lives in `trace_adapters/manifest.py`; this catalog is the human planning surface.

---

# PART A — CODING CONCEPTS

## A0. Programming fundamentals / code execution — family `program_trace`
Variable assignment · expression evaluation & precedence (T7/T12) · boolean branching · `for` loop · `while`
loop & termination · nested loops · function calls & returns · recursive call-stack execution · parameter
passing & scope · mutable vs immutable · array indexing & bounds · string indexing/slicing · exception flow ◇ ·
object construction & field mutation · method dispatch / inheritance ◇ · reference aliasing · pointer
dereference/updates · dynamic allocation (T10/T12) · stack vs heap · copy vs reference semantics. **Type T12**
(some T7/T10). Status ⬜ (a few ◇).

## A1. Core data structures — family `data_structures`
Static array access/update (T12) · dynamic array append/resize · insert/delete · singly-linked traversal (T1) ·
insertion (T8a/T10) · deletion · doubly-linked ins/del · stack push/pop · queue enqueue/dequeue · circular
queue · deque · hash table chaining · linear probing · resize/rehash · priority queue · binary heap insert ·
extract-min/max · heapify/sift-down · trie insertion (T8a) · trie search/prefix (T4) · trie deletion ·
skip-list search/insert ◇ · bloom filter ◇ · LRU cache. **Type T10** (traversal T1, trie-search T4, indexing
T12). Status ⬜.

## A2. Graph algorithms — family `graph`
**Traversal/reachability (T1):** BFS ✅ · DFS ✅ · connected components · reachability · directed cycle detection
(T1/T10) · undirected cycle detection (T1/T2) · bipartite/2-coloring · flood fill · multi-source BFS · grid BFS
· topo sort Kahn (T1/T8a) · topo sort DFS-finish · SCC Kosaraju · SCC Tarjan (T10) ◇ · articulation points ◇ ·
bridges ◇.
**MST & shortest paths:** Kruskal ✅ (T2) · Prim ✅ (T2) · Dijkstra ✅ (T2) · A* (T2) · Bellman–Ford (T9) ·
Floyd–Warshall (T5/T9) · Johnson ◇ · DAG shortest paths (T1/T9) · 0–1 BFS (T1/T10) · min-cost grid path (T2) ·
network delay (T2) · negative-cycle detection (T9).
**Flows/matching/advanced ◇ (unless noted):** Ford–Fulkerson (T2/T9) · Edmonds–Karp (T1/T9) · Dinic (T10) ·
bipartite matching (T1/T9) · Hungarian (T5/T9) · Union-Find (T10) ⬜ · path compression (T10) ⬜ · union by
rank/size (T10) ⬜.

## A3. Trees & hierarchical structures — family `trees`
Inorder BST 🟩 (T1) · preorder (T1) · postorder (T1) · level-order (T1) · height/depth (T3/T12) ·
count nodes/leaves (T1) · tree equality (T3/T12) · mirror/invert (T3/T8a) · BST search (T4) · BST insertion
(T8a) · BST deletion (T10) · BST validation (T1/T7) · LCA in BST (T4) · LCA in binary tree (T3/T12) · AVL single
rotations (T10) · AVL double rotations (T10) · AVL insert+rebalance (T10) · red-black insertion ◇ (T10) ·
segment tree build (T3/T8a) · seg range query (T4/T3) · seg point update (T10) · lazy propagation ◇ (T10) ·
Fenwick update (T10) · Fenwick prefix query (T4/T10) · B-tree search ◇ (T4) · B-tree split/insert ◇ (T10). ⬜.

## A4. Sorting, searching, sequences — family `sequence`
**Sorting:** merge sort ✅ (T3) · merge op (T3) · quicksort partition Lomuto/Hoare (T3) · quicksort recursion
(T3) · heap sort (T10) · insertion/selection/bubble (T10) · shell ◇ · counting (T8a) · radix (T8a/T10) · bucket
(T8a) · stable-vs-unstable ◇ (T8b) · comparator behavior ◇ (T12).
**Searching/array patterns:** binary search ✅ (T4) · first/last occurrence (T4) · binary search on answer (T4)
· ternary (T4) · exponential (T4) · interpolation ◇ · two-pointers pair-sum (T4/T10) · dedupe (T10) · palindrome
(T4) · sliding window fixed/variable (T10) · prefix sums (T8a) · difference arrays (T8a) · Kadane (T10) ·
Boyer–Moore majority ◇ · Dutch flag (T10) · rotate array (T10) · merge sorted arrays (T10) · interval merge
(T10) · sweep-line overlap ◇ · monotonic stack next-greater (T10) · monotonic queue window-max ◇.

## A5. Dynamic programming — family `dp` (all **T5** unless noted)
Fibonacci memo/tab · climbing stairs · house robber · 0/1 knapsack · unbounded knapsack · subset sum · equal
partition · coin change min/ways · LCS · longest common substring · LIS (T5/T4) · edit distance · matrix-chain ·
rod cutting · grid paths · min path sum · unique paths w/ obstacles · word break · palindrome partitioning ◇ ·
interval DP ◇ · bitmask DP ◇ · TSP DP ◇ · tree DP ◇ (T5/T3) · digit DP ◇.

## A6. Greedy — family `greedy` (all **T2** unless noted)
Activity selection · interval scheduling · min meeting rooms (T2/T10) · fractional knapsack · Huffman (T2/T8a) ·
job sequencing w/ deadlines · min platforms · gas-station ◇ (T10) · jump game · canonical coin greedy ·
scheduling w/ deadlines.

## A7. Strings & text — family `strings`
Frequency/anagram (T8a) · reversal (T10) · palindrome (T4/T10) · run-length encoding (T8a) · KMP prefix-function
(T10) · KMP matching (T4/T10) · Rabin–Karp (T10) · Z-algorithm (T10) · Manacher ◇ (T10) · trie prefix (T4) ·
Aho–Corasick ◇ (T10) · suffix array ◇ (T10) · suffix-array search ◇ (T4) · longest palindromic substring
(T5/T10) · edit-distance DP (T5) · LCS DP (T5) · regex-matching DP ◇ (T5).

## A8. Backtracking / recursion / constraint solving — family `recursion`
Factorial recursion (T12) · Fibonacci recursion (T12) · binary-tree recursion (T12) · Tower of Hanoi (T11) ·
permutations (T11) · combinations (T11) · subsets (T11) · N-Queens (T11) · Sudoku (T11) · word search (T11) ·
maze backtracking (T11) · parentheses generation (T11) · palindrome partition ◇ (T11) · graph coloring (T11) ·
exact cover ◇ (T11) · SAT/DPLL ◇ (T11).

## A9. Number theory / bitwise / algorithmic math — family `number_theory`
Euclid GCD (T7) · extended Euclid (T7) · LCM (T6/T7) · sieve (T8a) · segmented sieve ◇ · prime factorization
(T7/T8a) · modular add/mul (T7) · modular exponentiation (T7/T12) · modular inverse (T7) · CRT (T8b) · fast
exponentiation (T3/T12) · binary representation (T7) · two's complement (T7) · bitwise AND/OR/XOR (T7) · bit
masking (T10) · popcount (T7) · subset bitmask (T12) · Gray code ◇ (T8a) · RSA core (T7/T8b) · Diffie–Hellman
(T6/T7).

## A10. Computational geometry — family `geometry_algorithms`
Orientation/cross product (T6) · segment intersection (T7/T8b) · convex hull Graham ◇ (T10) · monotonic chain ◇
(T10) · closest pair ◇ (T3) · line sweep ◇ (T10) · point-in-polygon ◇ (T7) · Euclidean nearest neighbor (T6/T4)
· rectangle overlap (T7) · coordinate compression ◇ (T8a).

## A11. Databases & data systems — family `databases`
Relational selection (T7) · projection (T7) · join (T8a) · SQL filter/group trace (T12) · SQL join execution
(T8a/T10) · nested-loop join (T12) · hash join (T8a/T10) · sort-merge join (T10) · B+ tree lookup ◇ (T4) · B+
tree ins/split ◇ (T10) · index vs table scan ◇ (T10) · query-plan pipeline ◇ (T12) · functional dependencies
(T8b) · attribute closure (T8a) · normalization 3NF/BCNF ◇ (T8b) · transaction schedules (T10) · conflict
serializability (T8b) · two-phase locking ◇ (T10) · write-ahead logging ◇ (T10).

## A12. Operating systems / systems programming — family `systems`
Process state transitions (T10) · FCFS/SJF/round-robin/priority scheduling (T10) · MLFQ ◇ · context switch ◇ ·
deadlock detection ◇ (T8a/T10) · Banker's ◇ · mutex lock/unlock (T10) · semaphore ◇ · producer-consumer ◇ ·
reader-writer ◇ · virtual-address translation (T10) · page-table lookup (T10) · TLB hit/miss (T10) · FIFO/LRU
page replacement (T10) · optimal ◇ · buddy allocation ◇ · first-fit/best-fit (T10) · FS block allocation ◇ ·
inode path resolution ◇ (T12).

## A13. Computer architecture / digital systems — family `architecture`
Base conversion (T7) · signed integer rep (T7) · IEEE 754 ◇ (T7) · binary addition (T7) · ALU op ◇ (T10) ·
assembly execution (T12) · register-file updates (T12) · single-cycle datapath ◇ (T12) · 5-stage pipeline
(T10) · data hazards/forwarding (T10) · branch hazards ◇ (T10) · direct-mapped cache (T10) · set-associative
cache (T10) · cache LRU (T10) · write-through vs write-back ◇ (T10) · memory-hierarchy latency (T6) · ILP ◇
(T10) · SIMD ◇ (T12).

## A14. Computer networks — family `networks`
IPv4 subnetting (T6/T7) · CIDR (T7) · MAC-learning switch (T10) · ARP (T10) · DNS flow (T10) · TCP handshake
(T10) · TCP teardown (T10) · TCP seq/ack (T10) · retransmission ◇ (T10) · congestion window ◇ (T9/T10) · HTTP
lifecycle ◇ (T12) · routing-table longest-prefix (T4) · distance-vector routing (T9) · link-state routing
(T2/T9) · NAT (T10) · CSMA/collision ◇ (T10) · parity/checksum (T7) · CRC ◇ (T7).

## A15. Programming languages / compilers / formal languages — family `languages`
Lexical tokenization (T12) · regex→NFA ◇ (T8a) · NFA simulation (T10) · DFA simulation (T10) · NFA→DFA subset
◇ (T8a) · DFA minimization ◇ (T8a/T10) · CFG derivation (T8b) · parse-tree construction (T8a) · recursive
descent ◇ (T12) · shift-reduce ◇ (T10) · AST evaluation (T12) · scope/environment lookup (T12) · static type
checking ◇ (T8b/T12) · Hindley–Milner inference ◇ (T10) · lambda-calculus beta reduction (T7) · closures ◇
(T12) · mark-and-sweep GC ◇ (T10) · constant folding (T7) · CSE ◇ (T10) · CFG construction ◇ (T8a).

## A16. AI / machine learning / optimization — family `ml`
Linear-regression prediction (T6) · least-squares fit (T6/T7) · gradient descent (T9) · batch GD (T9) · SGD ◇
(T9) · logistic prediction (T6) · logistic gradient ◇ (T9) · kNN (T4/T10) · k-means (T9) · naive Bayes (T6) ·
decision-tree split ◇ (T2) · entropy/info gain (T6) · PCA ◇ (T6/T7) · perceptron update (T9) · NN forward pass
(T12) · backprop ◇ (T9) · SVM margin ◇ (T6) · Markov-chain update ◇ (T9) · value iteration ◇ (T9) · Q-learning
◇ (T9).

---

# PART B — NON-CODING MATH, EE, AND SCIENCE CONCEPTS

## B0. Pre-algebra / arithmetic — family `arithmetic` (all **T7** unless noted)
Integer arithmetic · fraction add/sub · fraction mul/div · decimal arithmetic · ratios/proportions (T6) ·
percent change (T6) · unit conversion (T6) · scientific notation · order of operations · absolute-value
equations · exponents/roots · logarithm eval & laws.

## B1. Algebra & functions — family `algebra` (all **T7** unless noted)
Linear equation · linear inequality · compound inequality · system by substitution · system by elimination ·
quadratic equation 🟩 (T6/T7) · factor quadratic · factor higher-degree patterns · complete the square ·
rational simplification · rational equations · radical equations · exponential equations · logarithmic
equations · polynomial division · synthetic division · function composition · function inverse · domain/range
(T8b) · piecewise eval (T6) · arithmetic sequences/series (T6) · geometric sequences/series (T6).

## B2. Trigonometry & geometry — family `geometry`
Coordinate distance (T6) · midpoint (T6) · slope & line equations (T6) · point-slope/slope-intercept (T7) ·
circle equation (T7) · area/perimeter (T6) · surface area/volume (T6) · similar triangles (T8b) · Pythagorean
(T6) · right-triangle trig ratios (T6) · unit-circle values (T8a/T7) · law of sines (T6) · law of cosines (T6)
· congruence/similarity proofs ◇ (T8b) · coordinate transformations (T8a) · vector geometry (T6).

## B3. Single-variable calculus — family `calculus`
Limit by substitution (T6) · by factoring (T7) · by rationalization (T7) · one-sided limits (T8b) · continuity
(T8b) · derivative power/product/quotient/chain (T7) · implicit diff (T7) · logarithmic diff (T7) · linear
approximation (T6) · related rates (T6) · optimization (T8b/T6) · antiderivative (T7) · definite integral (T7)
· u-substitution (T7) · by parts (T7) · partial fractions (T7) · improper integrals ◇ (T8b) · area between
curves (T6) · volume disks/washers (T6) · volume shells (T6) · sequences/convergence (T8b) · series tests
(T8b) · Taylor/Maclaurin ◇ (T8a/T7).

## B4. Multivariable calculus & ODEs — family `advanced_calculus`
Partial derivatives (T7) · gradient (T7) · directional derivative (T6) · tangent plane (T6) · multivariable
optimization (T8b/T6) · Lagrange multipliers (T8b) · double/triple integrals (T7) · change of vars/Jacobian ◇
(T7) · vector fields ◇ (T8a) · line integrals ◇ (T7) · Green's theorem ◇ (T8b) · separable ODEs (T7) ·
first-order linear ODEs (T7) · second-order constant-coeff ODEs (T7) · Laplace-transform ODE ◇ (T7) · Euler
method (T9) · Runge–Kutta ◇ (T9).

## B5. Linear algebra — family `linear_algebra`
Vector add/scalar mul (T7) · dot product (T6) · cross product (T6) · matrix add/scalar (T7) · matrix
multiplication (T8a) · transpose (T8a) · determinant 2×2 (T6) · 3×3 (T7) · cofactor expansion (T7) · row
reduction/Gaussian (T7) · Gauss–Jordan (T7) · inverse by row reduction (T7) · solve systems w/ matrices (T7) ·
linear independence (T8b) · span/basis (T8b) · dimension/rank (T7/T8b) · column/null space (T7/T8b) ·
orthogonality (T6) · Gram–Schmidt (T8a) · orthogonal projection (T6) · eigenvalues 2×2 (T7) · eigenvectors (T7)
· diagonalization (T8b) · SVD ◇ (T8b) · Markov matrices ◇ (T9).

## B6. Discrete math & CS theory — family `discrete`
Propositional eval (T7) · truth tables (T8a) · boolean simplification (T7) · Karnaugh maps (T8a/T7) · predicate
logic (T8b) · set ops (T8a) · Cartesian products (T8a) · relations & properties (T8b) · equivalence relations
(T8b) · partial orders (T8b) · function properties (T8b) · direct/contrapositive/contradiction/cases proofs
(T8b) · induction (T8b) · strong induction (T8b) · recursive definitions (T8b) · permutations (T6) ·
combinations (T6) · pigeonhole (T8b) · inclusion-exclusion (T6/T8b) · recurrence expansion (T7) · master
theorem (T8b) · Big-O/Θ/Ω for code (T8b) · asymptotic comparison (T8b) · degree/handshake lemma (T8b) · Euler
path/circuit (T8b) · Hamiltonian ◇ (T8b) · planarity ◇ (T8b) · DFA/NFA acceptance (T10) · pumping lemma ◇ (T8b)
· reductions/NP-completeness structure ◇ (T8b).

## B7. Probability & statistics — family `statistics` (all **T6** unless noted)
Mean/median/mode · weighted mean · variance · std dev · covariance · correlation · counting probability ·
conditional probability · Bayes' theorem · law of total probability · expected value · variance of RV ·
binomial · geometric · Poisson · normal/z-score · CLT interpretation ◇ (T8b) · CI mean · CI proportion · z-test
· t-test · two-sample tests ◇ · chi-square ◇ · regression prediction · least-squares (T6/T7) · residual
analysis ◇ (T8b).

## B8. Numerical methods & optimization — family `numerical`
Bisection (T4) · Newton's method (T9) · secant ◇ (T9) · fixed-point ◇ (T9) · Lagrange interpolation ◇ (T7) ·
Newton interpolation ◇ (T7) · numerical differentiation ◇ (T6) · trapezoidal (T6) · Simpson's (T6) · gradient
descent (T9) · Newton optimization ◇ (T9) · LP graphical (T8b) · simplex ◇ (T10) · duality ◇ (T8b).

## B9. Physics & electrical engineering — family `physics`
**Mechanics/energy/waves (T6 unless noted):** kinematics const-accel 🟩 · projectile · Newton's 2nd law ·
free-body diagram (T8a) · friction/inclines · circular motion · work & energy · energy conservation · momentum
& impulse · elastic collision (T6/T7) · inelastic collision (T6/T7) · torque/equilibrium · rotational
kinematics · SHM ◇ · wave speed/freq/wavelength · standing waves ◇ · Doppler ◇.
**Circuits/electronics/signals:** Ohm's law (T6) · series (T6/T8a) · parallel (T6/T8a) · KCL (T8b) · KVL (T8b)
· nodal analysis (T7) · mesh analysis (T7) · Thevenin (T7) · Norton (T7) · RC charge/discharge (T6) · RL ◇ ·
RLC resonance ◇ · AC phasors ◇ (T7) · RMS (T6) · AC power ◇ · op-amp ideal rules (T8b) · diode approx ◇ (T7) ·
MOSFET states ◇ (T10) · boolean gate eval (T7) · combinational construction (T8a) · mux/decoder (T10) ·
flip-flop transition (T10) · FSM trace (T10) · counter/register (T10) · discrete convolution ◇ (T8a/T7) ·
Fourier-series coeffs ◇ (T6/T7) · Fourier-transform properties ◇ (T8b) · sampling/aliasing (T6) · z-transform ◇
(T7).

## B10. Chemistry — family `chemistry` (all **T6** unless noted)
Balance a chemical equation (T8b) · mole conversion · stoichiometry · limiting reagent · percent yield ·
molarity · dilution · ideal gas law · combined gas law · pH / pOH · acid-base neutralization ·
oxidation-state assignment (T8a/T7) · redox balancing ◇ (T8b) · equilibrium expressions ◇ · thermochemistry ◇.

## B11. Finance, economics & accounting — family `finance` (all **T6** unless noted)
Simple interest · compound interest · present value · future value · annuity value · loan amortization (T8a) ·
net present value · internal rate of return ◇ (T9) · break-even analysis · supply-demand equilibrium · price
elasticity · marginal cost/revenue · consumer/producer surplus ◇ · GDP/inflation ◇ · journal entries (T8a) ·
trial balance (T8a) · income statement (T8a) · balance sheet (T8a) · cash-flow statement ◇ (T8a) ·
depreciation schedules (T8a).

---

# PART C — ELIGIBILITY-REVIEW TOPICS

These stay cataloged but do **not** automatically get a dedicated verified-trace adapter. They usually need
conceptual explanation, case comparison, simulation, source-grounded material, or design critique rather than a
single deterministic worked-example trace — i.e. Tier 3/4 of the coverage ladder.

| Family | Topics | Default treatment |
|---|---|---|
| Software engineering | requirements, architecture tradeoffs, design patterns, code review, SDLC, testing/deployment strategy | guided / scenario-based |
| Distributed systems | CAP tradeoffs, replication design, consensus intuition, eventual consistency, microservices | guided / simulation / curated case study |
| Cybersecurity | threat modeling, access-control policy, secure design, social engineering, incident response | guided / case-based |
| Human-computer interaction | usability heuristics, user research, accessibility, interface critique | guided / example comparison |
| Ethics & society | algorithmic bias, privacy tradeoffs, responsible AI, policy implications | guided / source-grounded |
| Product & entrepreneurship | market sizing, product strategy, experimentation, pricing, retention | guided / calculation hybrids |
| Research methods | literature review, study design, interpreting evidence, causal claims | guided / source-grounded |
| Advanced theoretical CS | computability proofs, advanced complexity reductions, randomized-algorithm proofs | formal derivation (T8b) only after a stable proof grammar exists |

---

## 2. Required metadata for every catalog row

Every adapter has a manifest entry (`trace_adapters/manifest.py`) with:
`slug` · `family` · `type` · `status` · `verification_level` · `coding` · `canonical_solution` ·
`routing_aliases` · `negative_guards` · `fixtures` · `visual_contract` · `feature_flag` · `telemetry_key` ·
`failure_policy`. (`telemetry_key`/`feature_flag`/`visual_contract` are auto-filled with defaults until
authored; `manifest_gaps()` enforces presence.)

**Minimum `failure_policy`:**
```yaml
invalid_trace: retry_then_withhold
prose_claim_violation: regenerate_prose_then_withhold
visual_compile_failure: show_verified_text_trace_if_available
frontend_render_failure: show_safe_text_fallback_and_log
```

---

## 3. Catalog prioritization rules

The catalog is intentionally broad. **Priority** is set by: current demand (`adapter_demand.jsonl`) · frequency
in popular EECS/math curricula · whether the concept has a stable deterministic trace · whether it introduces a
NEW trace type (proves a type gate) · whether it unlocks many related lessons · whether it has a clear visual
model · whether failure would be especially harmful/misleading.

**Initial expansion favors** (one type gate at a time): T1 graph+tree traversal · T2 MST + shortest-path
frontier · T3 merge sort + quicksort · T4 binary search + BST search · T5 knapsack + LCS + edit distance ·
T6 algebra + calculus + physics fundamentals · T7 arithmetic + algebraic rewriting + Gaussian elimination ·
T8a matrix mult + truth tables + sieve · T8b induction + symbolic derivation · T9 Bellman–Ford + gradient
descent · T10 heaps + hash tables + cache/OS state · T11 permutations + N-Queens + Sudoku · T12 loops +
recursion + pointers + memory.

---

## 4. Coverage note

This catalog intentionally exceeds the first 100-adapter target — the major undergraduate EECS, mathematics,
engineering, science, finance, and technical-foundation concepts that can plausibly benefit from a verified
worked-example trace. It is **not** a promise that every row gets an immediate custom adapter; it is a map of
*what can eventually be trace-verified*, *what type of executable truth each topic requires*, *which concepts
share infrastructure*, and *which should remain guided until a sound trace grammar exists* (Part C).
