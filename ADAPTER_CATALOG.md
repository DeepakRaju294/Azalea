# Adapter Catalog — the full concept set we will build adapters for

> **Purpose.** The complete list of concepts that will each get a **verified-trace adapter** (the executable
> truth + teaching boundaries behind every worked example). Two classes:
>
> - **Coding concepts** — algorithms whose worked example is a *code walkthrough + execution trace* (the
>   adapter ships a canonical solution + the trace).
> - **Non-coding concepts** — computations/derivations whose worked example is a *step-by-step calculation*
>   with **no code** (the adapter ships only the verified trace; the learner sees the working, not a program).
>
> Every adapter — coding or not — has the SAME contract (`ExampleSpec` · `reference()` verified trace ·
> required cases · structured facts · stage grammar · label convention). The only difference is the coding
> ones also declare a `canonical_solution`.
>
> **Three template adapters** define the pattern every new one follows:
> - **Coding** → `families/trees.py` `InorderTraversalAdapter` (ships a canonical solution)
> - **Math** → `families/algebra.py` `QuadraticEquationAdapter` (no code; a calculation)
> - **Science** → `families/physics.py` `KinematicsAdapter` (no code; quantities + units + governing equations)
>
> **Status key:** ✅ shipped · 🟩 template (this batch) · ⬜ planned.

---

## PART A — CODING CONCEPTS (worked example = code walkthrough + trace)

### A1. Graph algorithms — family `graph`
| Concept | Status |
|---|---|
| Breadth-first search (graph) | ✅ |
| Depth-first search (graph) | ✅ |
| Dijkstra shortest path | ✅ |
| Prim MST | ✅ |
| Kruskal MST | ✅ |
| Bellman-Ford | ⬜ |
| Floyd-Warshall (all-pairs) | ⬜ |
| Topological sort (Kahn / DFS) | ⬜ |
| Union-Find / Disjoint Set | ⬜ |
| Connected components | ⬜ |
| Cycle detection (directed / undirected) | ⬜ |
| Bipartite check (2-coloring) | ⬜ |
| Tarjan / Kosaraju SCC | ⬜ |
| A* search | ⬜ |

### A2. Tree algorithms — family `trees`
| Concept | Status |
|---|---|
| Inorder traversal (BST) | 🟩 **template** |
| Preorder / postorder traversal | ⬜ |
| Level-order / BFS traversal (tree) | ⬜ |
| BST search | ⬜ |
| BST insertion | ⬜ |
| BST deletion | ⬜ |
| AVL rotations / rebalancing | ⬜ |
| Heap insert / extract-min (binary heap) | ⬜ |
| Trie insert / search | ⬜ |
| Lowest common ancestor | ⬜ |
| Segment tree build / query | ⬜ |
| Fenwick / Binary Indexed Tree | ⬜ |

### A3. Sorting — family `sequence`
| Concept | Status |
|---|---|
| Merge sort | ✅ |
| Quick sort (partition) | ⬜ |
| Heap sort | ⬜ |
| Insertion / selection / bubble sort | ⬜ |
| Counting / radix / bucket sort | ⬜ |

### A4. Searching & arrays — family `sequence`
| Concept | Status |
|---|---|
| Binary search | ✅ |
| Two pointers (pair sum, dedupe) | ⬜ |
| Sliding window (max/sum) | ⬜ |
| Kadane (max subarray) | ⬜ |
| Prefix sums | ⬜ |

### A5. Dynamic programming — family `dp`
| Concept | Status |
|---|---|
| 0/1 Knapsack | ⬜ |
| Longest common subsequence | ⬜ |
| Longest increasing subsequence | ⬜ |
| Edit distance | ⬜ |
| Coin change | ⬜ |
| Matrix-chain multiplication | ⬜ |
| Subset sum / partition | ⬜ |
| Grid paths | ⬜ |

### A6. Greedy — family `greedy`
| Concept | Status |
|---|---|
| Activity / interval selection | ⬜ |
| Huffman coding | ⬜ |
| Fractional knapsack | ⬜ |

### A7. Strings — family `strings`
| Concept | Status |
|---|---|
| KMP matching | ⬜ |
| Rabin-Karp | ⬜ |
| Z-algorithm | ⬜ |
| Longest palindromic substring | ⬜ |
| Anagram / frequency counting | ⬜ |

### A8. Backtracking / recursion — family `recursion`
| Concept | Status |
|---|---|
| N-Queens | ⬜ |
| Permutations / combinations / subsets | ⬜ |
| Tower of Hanoi | ⬜ |
| Factorial / Fibonacci (recursive) | ⬜ |
| Sudoku solve | ⬜ |

### A9. Math / number theory (algorithmic) — family `number_theory`
| Concept | Status |
|---|---|
| Euclid GCD | ⬜ |
| Sieve of Eratosthenes | ⬜ |
| Modular exponentiation | ⬜ |
| Prime factorization | ⬜ |
| Extended Euclid | ⬜ |

---

## PART B — NON-CODING CONCEPTS (worked example = calculation/derivation, NO code)

### B1. Algebra — family `algebra`
| Concept | Status |
|---|---|
| Solve a quadratic equation | 🟩 **template** |
| Solve a linear equation | ⬜ |
| System of linear equations (substitution / elimination) | ⬜ |
| Factor a polynomial | ⬜ |
| Complete the square | ⬜ |
| Solve an inequality | ⬜ |

### B2. Calculus — family `calculus`
| Concept | Status |
|---|---|
| Derivative (power / product / quotient / chain rule) | ⬜ |
| Definite / indefinite integral | ⬜ |
| Limit evaluation | ⬜ |
| Related rates | ⬜ |
| Optimization (max/min) | ⬜ |

### B3. Linear algebra — family `linear_algebra`
| Concept | Status |
|---|---|
| Matrix multiplication | ⬜ |
| Determinant (2×2 / 3×3) | ⬜ |
| Gaussian elimination | ⬜ |
| Matrix inverse | ⬜ |
| Dot / cross product | ⬜ |
| Eigenvalues (2×2) | ⬜ |

### B4. Probability & statistics — family `statistics`
| Concept | Status |
|---|---|
| Mean / median / mode | ⬜ |
| Variance / standard deviation | ⬜ |
| Bayes' theorem | ⬜ |
| Conditional probability | ⬜ |
| Expected value | ⬜ |
| Binomial probability | ⬜ |
| Normal distribution / z-score | ⬜ |
| Confidence interval | ⬜ |
| Hypothesis test (t / z) | ⬜ |
| Linear regression (least squares) | ⬜ |

### B5. Physics — family `physics`
| Concept | Status |
|---|---|
| Kinematics (constant acceleration) | 🟩 **template** |
| Projectile motion | ⬜ |
| Newton's second law (F = ma) | ⬜ |
| Work–energy / conservation of energy | ⬜ |
| Momentum / collisions | ⬜ |
| Ohm's law + series/parallel circuits | ⬜ |
| Waves (frequency / wavelength / speed) | ⬜ |

### B6. Chemistry — family `chemistry`
| Concept | Status |
|---|---|
| Balance a chemical equation | ⬜ |
| Stoichiometry (mole ratios) | ⬜ |
| Molarity / dilution | ⬜ |
| Ideal gas law (PV = nRT) | ⬜ |
| pH / pOH | ⬜ |
| Limiting reagent | ⬜ |
| Oxidation states | ⬜ |

### B7. Finance & economics — family `finance`
| Concept | Status |
|---|---|
| Compound interest | ⬜ |
| Present / future value | ⬜ |
| Net present value | ⬜ |
| Supply–demand equilibrium | ⬜ |
| Price elasticity | ⬜ |
| Marginal cost / revenue | ⬜ |
| Break-even analysis | ⬜ |

### B8. Discrete math & CS theory — family `discrete`
| Concept | Status |
|---|---|
| Truth table / boolean simplification | ⬜ |
| Set operations (union/intersection/complement) | ⬜ |
| Counting (permutations / combinations) | ⬜ |
| Modular arithmetic | ⬜ |
| Big-O of a code fragment | ⬜ |
| Solve a recurrence (Master theorem) | ⬜ |
| Proof by induction (structure) | ⬜ |

### B9. Geometry & trigonometry — family `geometry`
| Concept | Status |
|---|---|
| Area / perimeter / volume | ⬜ |
| Pythagorean theorem | ⬜ |
| Trig ratios (sin/cos/tan) | ⬜ |
| Law of sines / cosines | ⬜ |
| Coordinate geometry (distance / slope / midpoint) | ⬜ |

### B10. Accounting — family `accounting`
| Concept | Status |
|---|---|
| Journal entries (debit/credit) | ⬜ |
| Income statement | ⬜ |
| Balance sheet | ⬜ |

---

## Coverage note
~110 concepts across 19 families (9 coding, 10 non-coding). Families share machinery; new concepts are added
as compact classes to their family module, never as new files. The three 🟩 templates (coding / math /
science) define the pattern every remaining ⬜ follows.
