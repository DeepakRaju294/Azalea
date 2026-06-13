"""Canonical fixtures — the concrete, verified instances of an application
(EXAMPLE_SYSTEM_SPEC.md §4). A fixture is *thin*: it names the concrete input/output
(+ code for the code lens) and inherits all rules from its ApplicationProfile.

Fixture-id convention (spec §5.2): `<application>_<concept|code>_<shape>_<NN>`.

This module holds the data only. Phase 0/1 created the ontology + profiles; this is
seeded in Phase 2 (the four sim-ready fixtures) and grows application-by-application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Optional

Visual = tuple[str, str]


@dataclass(frozen=True)
class CanonicalFixture:
    """The leaf of the hierarchy (spec §4). Authoritative for input/code/output/size;
    everything else is inherited from the application's profile."""

    fixture_id: str
    application: str
    example_type: str                 # WHICH lens this fixture serves (concept vs code)
    pattern: str                      # the run-shape (matches the profile lens pattern)
    expected_output: Any
    base_structure: dict[str, Any] = field(default_factory=dict)  # nodes/edges, array, rows/cols
    input: dict[str, Any] = field(default_factory=dict)           # run params: start, target, k
    variant: Optional[str] = None
    code: Optional[str] = None        # verified runnable code (code_execution_trace fixtures)
    entry_function: Optional[str] = None
    # PROJECTOR_SYSTEM_SPEC §3/§7 — a GraphProjection contract (dict of *_from fields).
    # When set, the fixture is a T2 projected node_link example: the conceptual trace is
    # computed by running `code` through the tracer + this projection (no simulator).
    graph_projection: Optional[dict[str, Any]] = None
    # One (title, explanation) per non-blank code line, in order — drives the
    # deterministic code_walkthrough (every line gets its own card + explanation).
    line_explanations: tuple[tuple[str, str], ...] = ()
    # The Worked Example Setup card's problem statement (falls back to a
    # type-generic statement when empty).
    setup_bullets: tuple[str, ...] = ()
    visual_override: Optional[Visual] = None
    sizing: dict[str, Any] = field(default_factory=dict)   # min_steps/max_steps/required_*/avoid
    source: str = "hand_verified"     # hand_verified | generated_deterministic | llm_validated
    practice_variants: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    learner_goal: str = ""


# Canonical binary search (verified, well-formed) — the code-lens fixture's source.
_BINARY_SEARCH_CODE: Final[str] = (
    "def binary_search(arr, target):\n    low = 0\n    high = len(arr) - 1\n"
    "    while low <= high:\n        mid = (low + high) // 2\n"
    "        if arr[mid] == target:\n            return mid\n"
    "        elif arr[mid] < target:\n            low = mid + 1\n"
    "        else:\n            high = mid - 1\n    return -1"
)

# A 15-element sorted array searched for its first element → >= 4 probes (min_steps).
_SORTED_15: Final[list[int]] = list(range(1, 16))

# §11 appendix graph: A-B, A-C, B-D, C-E ; start A (branches → BFS level order).
_BFS_NODES: Final[list[str]] = ["A", "B", "C", "D", "E"]
_BFS_EDGES: Final[list[list[str]]] = [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"]]
_GRAPH_ADJ: Final[dict[str, list[str]]] = {"A": ["B", "C"], "B": ["D"], "C": ["E"], "D": [], "E": []}

# Weighted 5-node graph for the projected (T2) MST / shortest-path fixtures.
_WGRAPH_NODES: Final[list[str]] = ["A", "B", "C", "D", "E"]
_WGRAPH_EDGES: Final[list[list[str]]] = [["A", "B"], ["A", "C"], ["B", "D"], ["C", "E"], ["D", "E"]]
_WGRAPH_WEIGHTED: Final[list[list]] = [["A", "B", 1], ["A", "C", 4], ["B", "D", 5], ["C", "E", 2], ["D", "E", 3]]

_PRIM_CODE: Final[str] = (
    "def prim(nodes, edges, start):\n"
    "    in_mst = [start]\n"
    "    mst = []\n"
    "    while len(in_mst) < len(nodes):\n"
    "        best = None\n"
    "        for edge in edges:\n"
    "            a, b, w = edge\n"
    "            if (a in in_mst) != (b in in_mst):\n"
    "                if best is None or w < best[2]:\n"
    "                    best = (a, b, w)\n"
    "        a, b, w = best\n"
    "        node = b if a in in_mst else a\n"
    "        in_mst.append(node)\n"
    "        mst.append((a, b))\n"
    "    return mst"
)

_DIJKSTRA_CODE: Final[str] = (
    "def dijkstra(nodes, edges, start):\n"
    "    import heapq\n"
    "    dist = {n: 999 for n in nodes}\n"
    "    dist[start] = 0\n"
    "    done = []\n"
    "    pq = [(0, start)]\n"
    "    while pq:\n"
    "        d, u = heapq.heappop(pq)\n"
    "        if u in done:\n"
    "            continue\n"
    "        done.append(u)\n"
    "        for edge in edges:\n"
    "            a, b, w = edge\n"
    "            if a == u or b == u:\n"
    "                v = b if a == u else a\n"
    "                if d + w < dist[v]:\n"
    "                    dist[v] = d + w\n"
    "                    heapq.heappush(pq, (dist[v], v))\n"
    "    return done"
)

# 7-node BST: inorder yields the sorted sequence.
_BST_7: Final[list[int]] = [50, 30, 70, 20, 40, 60, 80]

_INORDER_CODE: Final[str] = (
    "def inorderTraversal(root):\n    result = []\n    traverse(root, result)\n    return result\n\n\n"
    "def traverse(node, result):\n    if node is None:\n        return\n"
    "    traverse(node.left, result)\n    result.append(node.val)\n    traverse(node.right, result)"
)

_PREORDER_CODE: Final[str] = (
    "def preorderTraversal(root):\n    result = []\n    traverse(root, result)\n    return result\n\n\n"
    "def traverse(node, result):\n    if node is None:\n        return\n"
    "    result.append(node.val)\n    traverse(node.left, result)\n    traverse(node.right, result)"
)

_POSTORDER_CODE: Final[str] = (
    "def postorderTraversal(root):\n    result = []\n    traverse(root, result)\n    return result\n\n\n"
    "def traverse(node, result):\n    if node is None:\n        return\n"
    "    traverse(node.left, result)\n    traverse(node.right, result)\n    result.append(node.val)"
)

# Shared helper-skeleton explanations; only the three visit-order lines differ.
_TRAVERSAL_COMMON_HEAD: Final[tuple[tuple[str, str], ...]] = (
    ("Define the main function", "It takes the tree's root and returns the visit order."),
    ("Create the accumulator", "result will collect node values in visit order."),
    ("Start the recursion", "Hand the root and the accumulator to the recursive helper."),
    ("Return the answer", "When the recursion finishes, result holds the full sequence."),
    ("Define the helper", "traverse visits one node and both of its subtrees."),
    ("Base case test", "An empty subtree (node is None) ..."),
    ("Stop this branch", "... contributes nothing — return immediately."),
)

_BFS_CODE: Final[str] = (
    "def bfs(graph, start):\n    order = []\n    queue = [start]\n    visited = {start}\n"
    "    while queue:\n        node = queue.pop(0)\n        order.append(node)\n"
    "        for neighbour in graph[node]:\n            if neighbour not in visited:\n"
    "                visited.add(neighbour)\n                queue.append(neighbour)\n    return order"
)


# application -> its fixtures (any lens / variant). The first slice (spec §9.1).
FIXTURES: Final[dict[str, list[CanonicalFixture]]] = {
    "binary_search": [
        CanonicalFixture(
            fixture_id="binary_search_concept_found_late_01",
            application="binary_search",
            example_type="sequence_state_trace",
            pattern="range_halving",
            base_structure={"array": list(_SORTED_15)},
            input={"target": 1},
            expected_output=0,
            sizing={"min_steps": 4, "required_decisions": ["go_left"]},
            tags=("medium_nontrivial",),
            learner_goal="Trace how binary search halves the range to find a value near the start.",
        ),
        CanonicalFixture(
            fixture_id="binary_search_concept_absent_01",
            application="binary_search",
            example_type="sequence_state_trace",
            pattern="range_halving",
            base_structure={"array": list(_SORTED_15)},
            input={"target": 0},
            expected_output=-1,
            sizing={"min_steps": 4},
            tags=("edge_case",),
            learner_goal="See how binary search proves a value is ABSENT: the bounds cross and the range empties.",
        ),
        CanonicalFixture(
            fixture_id="binary_search_concept_practice_01",
            application="binary_search",
            example_type="sequence_state_trace",
            pattern="range_halving",
            base_structure={"array": [2, 5, 8, 12, 16, 23, 38, 45, 56, 72, 91]},
            input={"target": 72},
            expected_output=9,
            sizing={"min_steps": 3},
            tags=("isomorphic_variant",),
            learner_goal="Trace binary search yourself on a fresh array — same reasoning, different values.",
        ),
        CanonicalFixture(
            fixture_id="binary_search_code_loop_found_late_01",
            application="binary_search",
            example_type="code_execution_trace",
            pattern="loop_execution",
            input={"array": list(_SORTED_15), "target": 1},
            expected_output=0,
            code=_BINARY_SEARCH_CODE,
            entry_function="binary_search",
            line_explanations=(
                ("Define the function", "binary_search takes the sorted array and the target value to find."),
                ("Initialise low", "low = 0 — the left boundary of the search range starts at the first index."),
                ("Initialise high", "high = len(arr) - 1 — the right boundary starts at the last index."),
                ("Loop while the range is non-empty", "Keep searching while low <= high; once they cross, the range is empty and the target is absent."),
                ("Compute the midpoint", "mid = (low + high) // 2 — recomputed every iteration from the current bounds."),
                ("Check the middle element", "If arr[mid] equals the target, the search is over."),
                ("Return the found index", "Return mid — the position where the target sits."),
                ("Is the middle too small?", "If arr[mid] is LESS than the target, the target can only be in the right half."),
                ("Discard the left half", "low = mid + 1 — move the left boundary just past mid."),
                ("Otherwise the middle is too large", "arr[mid] is GREATER than the target — it must be in the left half."),
                ("Discard the right half", "high = mid - 1 — move the right boundary just below mid."),
                ("Not found", "The loop ended without a match — return -1 to signal the target is absent."),
            ),
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            learner_goal="Step through the binary-search loop line by line as it runs.",
        ),
    ],
    "bfs": [
        CanonicalFixture(
            fixture_id="bfs_concept_branching_graph_01",
            application="bfs",
            example_type="node_link_trace",
            pattern="frontier_expansion",
            base_structure={"nodes": list(_BFS_NODES), "edges": [list(e) for e in _BFS_EDGES]},
            input={"start": "A"},
            expected_output=["A", "B", "C", "D", "E"],
            sizing={"min_steps": 4, "required_features": ["branching"]},
            tags=("medium_nontrivial",),
            learner_goal="Trace BFS visiting a small branching graph in level order.",
        ),
        CanonicalFixture(
            fixture_id="bfs_code_queue_loop_01",
            application="bfs",
            example_type="code_execution_trace",
            pattern="loop_execution",
            input={"args": [dict(_GRAPH_ADJ), "A"]},
            expected_output=["A", "B", "C", "D", "E"],
            code=_BFS_CODE,
            entry_function="bfs",
            line_explanations=(
                ("Define the function", "bfs takes the graph (an adjacency map) and the start node."),
                ("Create the output list", "order will collect nodes in the sequence BFS visits them."),
                ("Seed the queue", "The queue starts holding just the start node — the frontier."),
                ("Mark the start visited", "visited remembers seen nodes so none is enqueued twice."),
                ("Loop while the queue has nodes", "BFS runs until the frontier is exhausted."),
                ("Dequeue the OLDEST node", "pop(0) takes from the front — first in, first out is what makes it breadth-first."),
                ("Visit it", "Append the node to the output order."),
                ("Scan its neighbours", "Every adjacent node is a candidate for the frontier."),
                ("Skip already-seen nodes", "Only unvisited neighbours join the queue."),
                ("Mark the neighbour visited", "Mark BEFORE enqueueing, so duplicates can't slip in."),
                ("Enqueue it", "The neighbour waits its turn at the BACK of the queue."),
                ("Return the visit order", "order now lists every reachable node, level by level."),
            ),
            setup_bullets=(
                "The problem: visit every node of this 5-node graph in breadth-first order, starting from A.",
                "A queue holds the frontier: nodes are visited first-in, first-out, level by level.",
                "Watch the code run — the variables panel tracks the queue, visited set, and order.",
            ),
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            learner_goal="Step through the BFS queue loop line by line as it runs.",
        ),
    ],
    "dfs": [
        CanonicalFixture(
            fixture_id="dfs_concept_branching_graph_01",
            application="dfs",
            example_type="node_link_trace",
            pattern="frontier_expansion",
            base_structure={"nodes": list(_BFS_NODES), "edges": [list(e) for e in _BFS_EDGES]},
            input={"start": "A"},
            expected_output=["A", "B", "D", "C", "E"],
            sizing={"min_steps": 4, "required_features": ["branching"]},
            tags=("medium_nontrivial",),
            learner_goal="Trace DFS diving depth-first down one branch before backtracking.",
        ),
    ],
    "linear_search": [
        CanonicalFixture(
            fixture_id="linear_search_code_loop_found_late_01",
            application="linear_search",
            example_type="code_execution_trace",
            pattern="loop_execution",
            input={"array": [4, 8, 15, 16, 23, 42], "target": 23},
            expected_output=4,
            code=(
                "def linear_search(arr, target):\n    for i in range(len(arr)):\n"
                "        if arr[i] == target:\n            return i\n    return -1"
            ),
            entry_function="linear_search",
            line_explanations=(
                ("Define the function", "linear_search takes the array and the value to find — no sorting required."),
                ("Walk every index", "i visits 0, 1, 2, ... — one element at a time, left to right."),
                ("Check the current element", "Is arr[i] the target? Every element gets this same test."),
                ("Found — return its index", "Stop immediately: the first match wins."),
                ("Exhausted — return -1", "The loop ended without a match: the target is absent."),
            ),
            setup_bullets=(
                "The problem: find the INDEX of the target value 23 in an UNSORTED array of 6 values.",
                "Linear search checks every element left to right — simple, and the only option when the data isn't sorted.",
                "Watch i sweep the array in the variables panel.",
            ),
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            learner_goal="Step through the scan: check, move on, check — until the target appears.",
        ),
    ],
    "coin_change": [
        CanonicalFixture(
            fixture_id="coin_change_concept_1_3_4_amount6_01",
            application="coin_change",
            example_type="grid_table_trace",
            pattern="dp_table_fill",
            base_structure={"coins": [1, 3, 4], "amount": 6, "rows": 1, "cols": 7},
            input={},
            expected_output=2,  # 3 + 3
            sizing={"min_steps": 5},
            tags=("medium_nontrivial",),
            setup_bullets=(
                "The problem: make the amount 6 with the FEWEST coins from {1, 3, 4}.",
                "Greedy fails here (4 + 1 + 1 = three coins) — the best answer is 3 + 3 = two coins.",
                "We fill a strip: cell j holds the fewest coins that make amount j, built from smaller amounts.",
            ),
            learner_goal="Fill the DP strip amount by amount and see why 3 + 3 beats the greedy choice.",
        ),
    ],
    "linear_equation": [
        CanonicalFixture(
            fixture_id="linear_equation_concept_3x_plus_4_01",
            application="linear_equation",
            example_type="symbolic_derivation",
            pattern="equation_solving",
            input={"a": 3, "b": 4, "c": 19},
            expected_output="x = 5",
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            setup_bullets=(
                "The problem: solve 3x + 4 = 19 — find the value of x that makes it true.",
                "Strategy: undo each operation in reverse order — subtraction first, then division.",
                "Every move is applied to BOTH sides, so the equation stays balanced.",
            ),
            learner_goal="Isolate x by undoing the operations around it, one inverse at a time.",
        ),
    ],
    "distance_formula": [
        CanonicalFixture(
            fixture_id="distance_formula_concept_3_4_5_01",
            application="distance_formula",
            example_type="symbolic_derivation",
            pattern="formula_substitution",
            input={"x1": 1, "y1": 2, "x2": 4, "y2": 6},
            expected_output="d = 5",
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            setup_bullets=(
                "The problem: find the distance between the points (1, 2) and (4, 6).",
                "The distance formula is the Pythagorean theorem in disguise: the gap is the hypotenuse.",
                "Substitute the coordinates and evaluate piece by piece.",
            ),
            learner_goal="Substitute two points into the distance formula and evaluate to the hypotenuse.",
        ),
    ],
    "compound_interest": [
        CanonicalFixture(
            fixture_id="compound_interest_concept_1000_10pct_2y_01",
            application="compound_interest",
            example_type="symbolic_derivation",
            pattern="formula_substitution",
            input={"P": 1000, "r": 0.1, "n": 1, "t": 2},
            expected_output="A = 1210",
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            setup_bullets=(
                "The problem: $1000 grows at 10% per year, compounded annually, for 2 years — what's the balance?",
                "Compounding means each year's interest itself earns interest the next year.",
                "Substitute into A = P(1 + r/n)^(nt) and evaluate piece by piece.",
            ),
            learner_goal="See compounding as repeated multiplication by one growth factor.",
        ),
    ],
    "algorithm_comparison": [
        CanonicalFixture(
            fixture_id="algorithm_comparison_concept_bfs_vs_dfs_01",
            application="algorithm_comparison",
            example_type="case_comparison_example",
            pattern="contrast_table",
            base_structure={
                "columns": ["Dimension", "BFS", "DFS"],
                "left_label": "BFS", "right_label": "DFS",
                "rows": [
                    ["Frontier", "a queue (FIFO)", "a stack / recursion (LIFO)"],
                    ["Visit order", "level by level, nearest first", "deep down one branch, then backtrack"],
                    ["Finds", "the SHORTEST path (unweighted)", "any path; natural for full exploration"],
                    ["Memory", "wide — holds a whole level", "narrow — holds one path"],
                ],
                "takeaway": "Use BFS for shortest paths and DFS for exhaustive search or recursion-friendly problems.",
                "caption": "BFS vs DFS",
            },
            input={},
            expected_output="BFS = shortest path; DFS = deep exploration",
            sizing={"min_steps": 3},
            tags=("medium_nontrivial",),
            setup_bullets=(
                "The question: BFS and DFS both visit every node — so when do you reach for each?",
                "They differ in ONE thing: the frontier. BFS uses a queue, DFS uses a stack.",
                "That single choice cascades into order, memory, and what each is good for.",
            ),
            learner_goal="Contrast BFS and DFS across the dimensions that decide which to use.",
        ),
    ],
    "set_operation": [
        CanonicalFixture(
            fixture_id="set_operation_concept_two_clubs_01",
            application="set_operation",
            example_type="set_logic_region_reasoning",
            pattern="set_counting",
            base_structure={"only_a": 3, "both": 2, "only_b": 4, "label_a": "Chess", "label_b": "Art"},
            input={},
            expected_output=9,  # union
            sizing={"min_steps": 3},
            tags=("medium_nontrivial",),
            setup_bullets=(
                "The problem: 5 students take Chess, 6 take Art, and 2 take BOTH — how many students total?",
                "A Venn diagram splits them into three regions: Chess-only, both, and Art-only.",
                "Intersection counts the overlap; union counts everyone once.",
            ),
            learner_goal="Count set intersection and union without double-counting the overlap.",
        ),
    ],
    "function_graph_analysis": [
        CanonicalFixture(
            fixture_id="function_graph_analysis_concept_parabola_01",
            application="function_graph_analysis",
            example_type="coordinate_plot_analysis",
            pattern="plot_analysis",
            input={"a": 1, "b": -2, "c": -3},
            expected_output="vertex (1, -4), roots x = -1, 3",
            sizing={"min_steps": 3},
            tags=("medium_nontrivial",),
            setup_bullets=(
                "The problem: analyse the parabola y = x² − 2x − 3 — find its key features.",
                "Every parabola has a y-intercept, possibly two roots, and a vertex (its turning point).",
                "Read each feature off the plotted curve.",
            ),
            learner_goal="Read the y-intercept, roots, and vertex of a parabola from its graph.",
        ),
    ],
    "stack_heap_allocation": [
        CanonicalFixture(
            fixture_id="stack_heap_allocation_concept_list_01",
            application="stack_heap_allocation",
            example_type="memory_reference_trace",
            pattern="memory_reveal",
            input={"array": [1, 2, 3]},
            expected_output="x (stack) → [1, 2, 3] (heap)",
            sizing={"min_steps": 3},
            tags=("medium_nontrivial",),
            setup_bullets=(
                "The problem: what actually happens in memory when you write x = [1, 2, 3]?",
                "Local variables live on the STACK; dynamically-sized data lives on the HEAP.",
                "Watch where the list goes and what x really holds.",
            ),
            learner_goal="See that a variable holds a reference into the heap, not the data itself.",
        ),
    ],
    "protocol_sequence": [
        CanonicalFixture(
            fixture_id="protocol_sequence_concept_tcp_handshake_01",
            application="protocol_sequence",
            example_type="timeline_interaction_trace",
            pattern="protocol_exchange",
            base_structure={
                "actors": [{"id": "client", "label": "Client"}, {"id": "server", "label": "Server"}],
                "messages": [
                    {"id": "m1", "from": "client", "to": "server", "label": "SYN", "time": 0},
                    {"id": "m2", "from": "server", "to": "client", "label": "SYN-ACK", "time": 1},
                    {"id": "m3", "from": "client", "to": "server", "label": "ACK", "time": 2},
                ],
            },
            input={},
            expected_output="connection established after 3 messages",
            sizing={"min_steps": 3},
            tags=("medium_nontrivial",),
            setup_bullets=(
                "The problem: how do a client and server agree to start talking over TCP?",
                "It takes THREE messages — the 'three-way handshake' — before any data is sent.",
                "Watch each message cross the timeline in order.",
            ),
            learner_goal="Trace the TCP three-way handshake message by message.",
        ),
    ],
    "triangle_geometry": [
        CanonicalFixture(
            fixture_id="triangle_geometry_concept_3_4_5_01",
            application="triangle_geometry",
            example_type="geometric_spatial_construction",
            pattern="construction",
            input={"a": 3, "b": 4},
            expected_output="c = 5",
            sizing={"min_steps": 3},
            tags=("medium_nontrivial",),
            setup_bullets=(
                "The problem: a right triangle has legs 3 and 4 — how long is the hypotenuse?",
                "The Pythagorean theorem relates the three sides: c² = a² + b².",
                "Label the legs, then compute the hypotenuse.",
            ),
            learner_goal="Apply the Pythagorean theorem to find a right triangle's hypotenuse.",
        ),
    ],
    "induction_proof": [
        CanonicalFixture(
            fixture_id="induction_proof_concept_sum_formula_01",
            application="induction_proof",
            example_type="proof_reasoning_chain",
            pattern="induction",
            input={},
            expected_output="1 + 2 + ... + n = n(n+1)/2",
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            setup_bullets=(
                "The claim: 1 + 2 + ... + n = n(n+1)/2 for every positive integer n.",
                "Induction proves infinitely many cases with two steps: a base case and an inductive step.",
                "If it holds at 1, and 'holds at k' forces 'holds at k+1', it holds for all n — like dominoes.",
            ),
            learner_goal="Follow a proof by induction from the base case through to the conclusion.",
        ),
    ],
    "quadratic_formula": [
        CanonicalFixture(
            fixture_id="quadratic_formula_concept_distinct_roots_01",
            application="quadratic_formula",
            example_type="symbolic_derivation",
            pattern="formula_substitution",
            input={"a": 1, "b": -5, "c": 6},
            expected_output="x = 3 or x = 2",
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            setup_bullets=(
                "The problem: solve x² − 5x + 6 = 0 — find the values of x that make it true.",
                "The quadratic formula solves ANY equation of the form ax² + bx + c = 0.",
                "Here a = 1, b = -5, c = 6; we substitute them and evaluate piece by piece.",
            ),
            learner_goal="Substitute a, b, c into the quadratic formula and evaluate it to both roots.",
        ),
    ],
    "tree_traversal": [
        CanonicalFixture(
            fixture_id="tree_traversal_code_recursive_inorder_01",
            application="tree_traversal",
            example_type="code_execution_trace",
            pattern="recursive_execution",
            variant="inorder",
            input={"tree": list(_BST_7)},
            expected_output=[20, 30, 40, 50, 60, 70, 80],
            code=_INORDER_CODE,
            entry_function="inorderTraversal",
            line_explanations=(
                ("Define the main function", "inorderTraversal takes the tree's root and returns the visit order."),
                ("Create the accumulator", "result will collect node values in inorder sequence."),
                ("Start the recursion", "Hand the root and the accumulator to the recursive helper."),
                ("Return the answer", "When the recursion finishes, result holds the full inorder sequence."),
                ("Define the helper", "traverse visits one node and both of its subtrees."),
                ("Base case test", "An empty subtree (node is None) ..."),
                ("Stop this branch", "... contributes nothing — return immediately."),
                ("Recurse LEFT first", "Everything in the left subtree is SMALLER, so it is visited before this node."),
                ("Visit the node itself", "Append its value — left, NODE, right is what makes it inorder."),
                ("Recurse RIGHT last", "Everything larger is visited after — producing sorted order on a BST."),
            ),
            setup_bullets=(
                "The problem: list the values of this 7-node binary search tree in INORDER (left, node, right).",
                "On a BST, inorder produces the values in sorted order — that's the property to watch.",
                "The code recurses: the call stack grows going left, then unwinds, visiting as it goes.",
            ),
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            learner_goal="Step through the recursive inorder traversal as the call stack grows and unwinds.",
        ),
        CanonicalFixture(
            fixture_id="tree_traversal_code_recursive_preorder_01",
            application="tree_traversal",
            example_type="code_execution_trace",
            pattern="recursive_execution",
            variant="preorder",
            input={"tree": list(_BST_7)},
            expected_output=[50, 30, 20, 40, 70, 60, 80],
            code=_PREORDER_CODE,
            entry_function="preorderTraversal",
            line_explanations=_TRAVERSAL_COMMON_HEAD + (
                ("Visit the node FIRST", "Append its value before either subtree — NODE, left, right is preorder."),
                ("Then recurse LEFT", "The whole left subtree is visited next."),
                ("Recurse RIGHT last", "The right subtree finishes the visit."),
            ),
            setup_bullets=(
                "The problem: list the values of this 7-node binary search tree in PREORDER (node, left, right).",
                "Preorder visits a node BEFORE its subtrees — the order you'd copy a tree in.",
                "The code recurses: each call visits, then descends left, then right.",
            ),
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            learner_goal="Step through the recursive preorder traversal — visit first, then descend.",
        ),
        CanonicalFixture(
            fixture_id="tree_traversal_code_recursive_postorder_01",
            application="tree_traversal",
            example_type="code_execution_trace",
            pattern="recursive_execution",
            variant="postorder",
            input={"tree": list(_BST_7)},
            expected_output=[20, 40, 30, 60, 80, 70, 50],
            code=_POSTORDER_CODE,
            entry_function="postorderTraversal",
            line_explanations=_TRAVERSAL_COMMON_HEAD + (
                ("Recurse LEFT first", "The whole left subtree is finished before anything else."),
                ("Then recurse RIGHT", "The right subtree is finished next."),
                ("Visit the node LAST", "Append its value only after BOTH subtrees — left, right, NODE is postorder."),
            ),
            setup_bullets=(
                "The problem: list the values of this 7-node binary search tree in POSTORDER (left, right, node).",
                "Postorder visits a node AFTER both subtrees — the order you'd safely delete a tree in.",
                "The code recurses: each call finishes both children before visiting.",
            ),
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            learner_goal="Step through the recursive postorder traversal — children first, node last.",
        ),
    ],
    "unique_paths": [
        CanonicalFixture(
            fixture_id="unique_paths_concept_3x4_01",
            application="unique_paths",
            example_type="grid_table_trace",
            pattern="dp_table_fill",
            base_structure={"rows": 3, "cols": 4},
            input={},
            expected_output=10,  # C(3+4-2, 3-1) = C(5,2) = 10
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            learner_goal="Fill a 3x4 DP grid cell-by-cell to count lattice paths.",
        ),
    ],
    # Projected (T2) node_link fixtures — verified code + a GraphProjection, no
    # simulator. The conceptual trace is computed by the tracer + projector
    # (PROJECTOR_SYSTEM_SPEC §7); the same machinery serves the whole graph family.
    "minimum_spanning_tree": [
        CanonicalFixture(
            fixture_id="minimum_spanning_tree_prim_concept_01",
            application="minimum_spanning_tree",
            example_type="node_link_trace",
            pattern="edge_selection",
            base_structure={"nodes": list(_WGRAPH_NODES), "edges": [list(e) for e in _WGRAPH_EDGES]},
            input={"args": [list(_WGRAPH_NODES), [list(e) for e in _WGRAPH_WEIGHTED], "A"], "start": "A"},
            expected_output=list(_WGRAPH_NODES),
            code=_PRIM_CODE,
            entry_function="prim",
            graph_projection={"current_from": "node", "visited_from": "in_mst", "selected_edges_from": "mst"},
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            learner_goal="Build the minimum spanning tree with Prim's algorithm, edge by edge.",
        ),
    ],
    "shortest_path": [
        CanonicalFixture(
            fixture_id="shortest_path_dijkstra_concept_01",
            application="shortest_path",
            example_type="node_link_trace",
            pattern="edge_relaxation",
            base_structure={"nodes": list(_WGRAPH_NODES), "edges": [list(e) for e in _WGRAPH_EDGES]},
            input={"args": [list(_WGRAPH_NODES), [list(e) for e in _WGRAPH_WEIGHTED], "A"], "start": "A"},
            expected_output=list(_WGRAPH_NODES),
            code=_DIJKSTRA_CODE,
            entry_function="dijkstra",
            graph_projection={"current_from": "u", "visit_order_from": "done",
                              "frontier_from": "pq", "frontier_node_key": "index:1"},
            sizing={"min_steps": 4},
            tags=("medium_nontrivial",),
            learner_goal="Finalize nodes by least cost with Dijkstra's algorithm.",
        ),
    ],
}


def fixtures_for(application: str) -> list[CanonicalFixture]:
    return FIXTURES.get(application, [])

