"""Reference-first worked-example construction for algorithmic families (the correctness fix for
walkthroughs and non-executable code).

For graph/MST topics the model can't be trusted to hand-simulate the algorithm: it truncates, picks
wrong edges, and invents pseudo-code (see the disconnected/over-long examples). When there is no
executable user code to trace (algorithm walkthroughs) or the code won't run, we build the worked
example from a TRUSTED INTERNAL reference run of the algorithm on the real input — so the steps,
states, and final answer are COMPUTED, not guessed. Same correctness guarantee as trace_first
(``build_cards_from_trace``), sourced from the reference rather than from user code.

Pure: graph input in, card skeletons out. A downstream narration pass writes prose around the
verified states; it never changes a state or the final answer.
"""
from __future__ import annotations

import heapq
from collections import defaultdict
from typing import Any

from .property_checks import _node_labels, _weighted_edges
from .trace_first import canonical_final_answer


def _algorithm_for(title: str) -> str:
    """Pick the algorithm the topic is teaching so the trace matches it (Prim grows a frontier from a
    start vertex; Kruskal sorts edges globally). Same MST, different teaching narrative."""
    return "prim" if "prim" in (title or "").lower() else "kruskal"


def _components_str(find, nodes: set[str]) -> str:
    groups: dict[str, list[str]] = defaultdict(list)
    for n in sorted(nodes):
        groups[find(n)].append(n)
    return ", ".join("{" + ", ".join(g) + "}" for g in groups.values())


def kruskal_steps(nodes: set[str], edges: list[tuple[str, str, float]]):
    """One step per edge considered in weight order: select (joins two components) or skip (cycle).
    Returns (steps, mst) where each step carries the real running MST + component partition."""
    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    mst: list[tuple[str, str, float]] = []
    target = len(nodes) - 1
    steps: list[dict[str, Any]] = []
    for u, v, w in sorted(edges, key=lambda e: (e[2], str(e[0]), str(e[1]))):
        if u not in parent or v not in parent:
            continue
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
            mst.append((u, v, w))
            action = "select"
        else:
            action = "skip"
        steps.append({"action": action, "edge": (u, v, w), "mst": list(mst),
                      "components": _components_str(find, nodes)})
        if len(mst) >= target:
            break
    return steps, mst


def prim_steps(nodes: set[str], edges: list[tuple[str, str, float]], start: str):
    """One step per cheapest frontier edge popped: select (reaches a new vertex) or skip (already in).
    Returns (steps, mst) where each step carries the real running MST + visited set."""
    adj: dict[str, list[tuple[float, str, str]]] = defaultdict(list)
    for u, v, w in edges:
        adj[u].append((w, u, v))
        adj[v].append((w, v, u))
    visited = {start}
    mst: list[tuple[str, str, float]] = []
    heap = list(adj[start])
    heapq.heapify(heap)
    steps: list[dict[str, Any]] = []
    while heap and len(visited) < len(nodes):
        w, frm, to = heapq.heappop(heap)
        if to in visited:
            steps.append({"action": "skip", "edge": (frm, to, w), "mst": list(mst),
                          "visited": sorted(visited)})
            continue
        visited.add(to)
        mst.append((frm, to, w))
        steps.append({"action": "select", "edge": (frm, to, w), "mst": list(mst),
                      "visited": sorted(visited)})
        for w2, _f, nxt in adj[to]:
            if nxt not in visited:
                heapq.heappush(heap, (w2, to, nxt))
    return steps, mst


# --- sorting references (the next walkthrough family) -------------------------------------------
# Same principle as MST: run the REAL algorithm on the REAL input and emit one conceptual, state-
# accurate card per outer pass (bounded to ~n cards, not per-comparison). The array state on each
# card is the true intermediate, so the trace can't truncate or misstate it.

def _sort_algorithm_for(title: str) -> Optional[str]:
    t = (title or "").lower()
    for key in ("insertion", "selection", "bubble"):
        if key in t:
            return key
    if "sort" in t:
        return "bubble"  # a generic comparison sort when the name doesn't pin one
    return None


def bubble_sort_steps(arr: list) -> list[dict[str, Any]]:
    a = list(arr)
    steps: list[dict[str, Any]] = []
    n = len(a)
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swapped = True
        steps.append({"array": list(a), "sorted_tail": i + 1, "swapped": swapped})
        if not swapped:
            break
    return steps


def selection_sort_steps(arr: list) -> list[dict[str, Any]]:
    a = list(arr)
    steps: list[dict[str, Any]] = []
    n = len(a)
    for i in range(n - 1):
        m = i
        for j in range(i + 1, n):
            if a[j] < a[m]:
                m = j
        a[i], a[m] = a[m], a[i]
        steps.append({"array": list(a), "placed_index": i, "placed_value": a[i]})
    return steps


def insertion_sort_steps(arr: list) -> list[dict[str, Any]]:
    a = list(arr)
    steps: list[dict[str, Any]] = []
    for i in range(1, len(a)):
        key = a[i]
        j = i - 1
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = key
        steps.append({"array": list(a), "inserted_value": key, "sorted_prefix": i + 1})
    return steps


_SORT_STEPPERS = {
    "bubble": bubble_sort_steps, "selection": selection_sort_steps, "insertion": insertion_sort_steps,
}


def build_sort_reference_cards(title: str, array: list) -> dict[str, Any]:
    algo = _sort_algorithm_for(title)
    if not algo or len(array) < 2:
        return {}
    steps = _SORT_STEPPERS[algo](array)
    if not steps:
        return {}
    cards: list[dict[str, Any]] = []
    prior = list(array)
    for idx, s in enumerate(steps, start=1):
        arr_str = "[" + ", ".join(str(x) for x in s["array"]) + "]"
        if algo == "bubble":
            goal = f"Pass {idx}: bubble the largest unsorted value to the end."
            reasoning = ("Compare each adjacent pair across the unsorted region and swap when out of order; "
                         "the largest remaining value settles into place.")
            work = [f"sweep & swap adjacent out-of-order pairs // array -> {arr_str}"]
        elif algo == "selection":
            goal = f"Pass {idx}: select the smallest remaining value into position {s['placed_index'] + 1}."
            reasoning = (f"Scan the unsorted region for its minimum ({s['placed_value']}) and place it at the "
                         f"front of that region.")
            work = [f"select min of unsorted, place at index {s['placed_index']} // array -> {arr_str}"]
        else:  # insertion
            goal = f"Step {idx}: insert {s['inserted_value']} into the sorted prefix."
            reasoning = (f"Shift larger values right and drop {s['inserted_value']} into its correct slot so the "
                         f"prefix of length {s['sorted_prefix']} stays sorted.")
            work = [f"insert {s['inserted_value']} into the sorted prefix // array -> {arr_str}"]
        cards.append({
            "card_id": f"step_{idx}", "title": goal, "goal": goal, "reasoning": reasoning,
            "work": work, "result": f"Array now: {arr_str}",
            "prior_state": {"array": prior}, "state": {"array": list(s["array"])},
            "code_refs": [], "state_relevance": "none", "state_delta": None,
            "cases_covered": [], "trace_backed": True,
        })
        prior = list(s["array"])
    final = list(steps[-1]["array"])
    arr_in = "[" + ", ".join(str(x) for x in array) + "]"
    return {
        "cards": cards,
        "problem": f"Sort the array {arr_in} in ascending order using {algo} sort.",
        "final_answer": final,
        "final_answer_struct": canonical_final_answer(final),
        "trace_backed": True, "source": "reference_first",
    }


# --- binary search reference (walkthrough) ------------------------------------------------------

def binary_search_steps(nums: list, target) -> tuple[list[dict[str, Any]], int]:
    lo, hi = 0, len(nums) - 1
    steps: list[dict[str, Any]] = []
    found = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        val = nums[mid]
        if val == target:
            steps.append({"lo": lo, "hi": hi, "mid": mid, "val": val, "decision": "found"})
            found = mid
            break
        decision = "right" if val < target else "left"
        steps.append({"lo": lo, "hi": hi, "mid": mid, "val": val, "decision": decision})
        if decision == "right":
            lo = mid + 1
        else:
            hi = mid - 1
    return steps, found


def build_search_reference_cards(title: str, nums: list, target) -> dict[str, Any]:
    if "binary" not in (title or "").lower() and "search" not in (title or "").lower():
        return {}
    if len(nums) < 2 or target is None:
        return {}
    steps, found = binary_search_steps(nums, target)
    if not steps:
        return {}
    cards: list[dict[str, Any]] = []
    for idx, s in enumerate(steps, start=1):
        window = "[" + ", ".join(str(nums[i]) for i in range(s["lo"], s["hi"] + 1)) + "]"
        if s["decision"] == "found":
            goal = f"Found {target} at index {s['mid']}."
            reasoning = f"The middle element {s['val']} equals the target, so the search succeeds."
            work = [f"check middle nums[{s['mid']}]={s['val']} // equals target {target} -> done"]
            result = f"Target {target} found at index {s['mid']}."
        else:
            side = "right" if s["decision"] == "right" else "left"
            goal = f"Check the middle of {window}; discard the {('left' if side=='right' else 'right')} half."
            reasoning = (f"Middle element {s['val']} is {'less' if side == 'right' else 'greater'} than "
                         f"{target}, so the target can only be in the {side} half.")
            work = [f"check middle nums[{s['mid']}]={s['val']} // {'<' if side=='right' else '>'} {target} "
                    f"-> search {side}"]
            result = f"Search window narrows to the {side} half."
        cards.append({
            "card_id": f"step_{idx}", "title": goal, "goal": goal, "reasoning": reasoning,
            "work": work, "result": result,
            "prior_state": None, "state": {"lo": s["lo"], "hi": s["hi"], "mid": s["mid"]},
            "code_refs": [], "state_relevance": "none", "state_delta": None,
            "cases_covered": [], "trace_backed": True,
        })
    arr_in = "[" + ", ".join(str(x) for x in nums) + "]"
    return {
        "cards": cards,
        "problem": f"Use binary search to find {target} in the sorted array {arr_in}.",
        "final_answer": found,
        "final_answer_struct": canonical_final_answer(found),
        "trace_backed": True, "source": "reference_first",
    }


# --- BST reference (search / insert walkthroughs) -----------------------------------------------

def _bst_from_level_order(level: list) -> Optional[dict]:
    """Rebuild a BST as nested {'val','left','right'} from a level-order list with None gaps."""
    if not level or level[0] is None:
        return None
    nodes = [None if v is None else {"val": v, "left": None, "right": None} for v in level]
    kids = iter(nodes[1:])
    for node in nodes:
        if node is None:
            continue
        try:
            node["left"] = next(kids)
            node["right"] = next(kids)
        except StopIteration:
            break
    return nodes[0]


def _bst_op_for(title: str) -> Optional[str]:
    t = (title or "").lower()
    if "insert" in t or "add" in t:
        return "insert"
    if "search" in t or "find" in t or "lookup" in t or "contains" in t:
        return "search"
    return None


def build_bst_reference_cards(title: str, tree_level: list) -> dict[str, Any]:
    op = _bst_op_for(title)
    root = _bst_from_level_order(tree_level)
    if not op or root is None:
        return {}
    present = [v for v in tree_level if v is not None]
    if op == "search":
        target = present[len(present) // 2]                      # a value that IS in the tree
    else:  # insert a value NOT already present
        target = next((x for x in range(1, 100) if x not in present), max(present) + 1)

    cards: list[dict[str, Any]] = []
    node = root
    idx = 0
    while node is not None:
        idx += 1
        v = node["val"]
        if v == target and op == "search":
            cards.append(_bst_card(idx, f"Found {target} at this node.",
                                   f"{target} equals the current node, so the search succeeds.",
                                   f"compare {target} with {v} // equal -> found", f"{target} is in the tree."))
            break
        go = "left" if target < v else "right"
        nxt = node[go]
        if op == "insert" and nxt is None:
            cards.append(_bst_card(idx, f"Insert {target} as the {go} child of {v}.",
                                   f"{target} is {'less' if go == 'left' else 'greater'} than {v} and the "
                                   f"{go} slot is empty, so {target} is placed there.",
                                   f"compare {target} with {v} // go {go}, slot empty -> insert",
                                   f"{target} inserted as {v}'s {go} child."))
            break
        cards.append(_bst_card(idx, f"At node {v}: go {go}.",
                               f"{target} is {'less' if go == 'left' else 'greater'} than {v}, so descend to the "
                               f"{go} subtree.",
                               f"compare {target} with {v} // {'<' if go == 'left' else '>'} -> go {go}",
                               f"Move to the {go} child of {v}."))
        node = nxt
    if not cards:
        return {}
    verb = "Search for" if op == "search" else "Insert"
    return {
        "cards": cards,
        "problem": f"{verb} {target} in the binary search tree (level-order {present}).",
        "final_answer": target,
        "final_answer_struct": canonical_final_answer(target),
        "trace_backed": True, "source": "reference_first",
    }


def _bst_card(idx: int, goal: str, reasoning: str, work: str, result: str) -> dict[str, Any]:
    return {
        "card_id": f"step_{idx}", "title": goal, "goal": goal, "reasoning": reasoning,
        "work": [work], "result": result, "prior_state": None, "state": None,
        "code_refs": [], "state_relevance": "none", "state_delta": None,
        "cases_covered": [], "trace_backed": True,
    }


# --- graph traversal references (BFS / DFS walkthroughs) ----------------------------------------

def _traversal_algorithm_for(title: str) -> Optional[str]:
    t = (title or "").lower()
    if "depth" in t or "dfs" in t:
        return "dfs"
    if "breadth" in t or "bfs" in t:
        return "bfs"
    return None


def bfs_steps(graph: dict, start: str):
    from collections import deque
    visited = [start]
    q = deque([start])
    steps: list[dict[str, Any]] = []
    while q:
        node = q.popleft()
        newly = []
        for nb in graph.get(node, []):
            if nb not in visited:
                visited.append(nb)
                q.append(nb)
                newly.append(nb)
        steps.append({"node": node, "added": newly, "frontier": list(q), "visited": list(visited)})
    return steps, visited


def dfs_steps(graph: dict, start: str):
    visited: list[str] = []
    stack = [start]
    steps: list[dict[str, Any]] = []
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.append(node)
        newly = [nb for nb in reversed(graph.get(node, [])) if nb not in visited]
        stack.extend(newly)
        steps.append({"node": node, "added": newly, "frontier": list(stack), "visited": list(visited)})
    return steps, visited


def build_traversal_reference_cards(title: str, graph: dict) -> dict[str, Any]:
    algo = _traversal_algorithm_for(title)
    if not algo or not isinstance(graph, dict) or len(graph) < 2:
        return {}
    start = sorted(graph)[0]
    steps, order = (bfs_steps if algo == "bfs" else dfs_steps)(graph, start)
    if not steps:
        return {}
    holder = "queue" if algo == "bfs" else "stack"
    cards: list[dict[str, Any]] = []
    prior: dict[str, Any] | None = None
    for idx, s in enumerate(steps, start=1):
        added = ", ".join(s["added"]) if s["added"] else "nothing new"
        front = "[" + ", ".join(s["frontier"]) + "]"
        goal = f"Visit {s['node']}."
        reasoning = (f"Take {s['node']} off the {holder}, mark it visited, and "
                     f"{'enqueue' if algo == 'bfs' else 'push'} its unvisited neighbours ({added}).")
        work = [f"visit {s['node']}; {'enqueue' if algo == 'bfs' else 'push'} {added} // {holder} -> {front}"]
        cards.append({
            "card_id": f"step_{idx}", "title": goal, "goal": goal, "reasoning": reasoning,
            "work": work, "result": f"Visited so far: {', '.join(s['visited'])}",
            "prior_state": prior, "state": {"visited": list(s["visited"]), holder: list(s["frontier"])},
            "code_refs": [], "state_relevance": "none", "state_delta": None,
            "cases_covered": [], "trace_backed": True,
        })
        prior = {"visited": list(s["visited"]), holder: list(s["frontier"])}
    return {
        "cards": cards,
        "problem": f"Perform a {'breadth' if algo == 'bfs' else 'depth'}-first traversal from {start}.",
        "final_answer": order,
        "final_answer_struct": canonical_final_answer(order),
        "trace_backed": True, "source": "reference_first",
    }


def _fmt_edge(e: tuple[str, str, float]) -> str:
    u, v, w = e
    return f"({u}, {v}, {w:g})"


def _fmt_mst(mst: list[tuple[str, str, float]]) -> str:
    return ", ".join(_fmt_edge(e) for e in mst) or "(empty)"


def build_reference_cards(topic_family: str, title: str, example_input: Any) -> dict[str, Any]:
    """Build COMPLETE, state-accurate worked-example cards from a trusted reference run of the MST
    algorithm. Returns {cards, final_answer, ...} or {} when this isn't an MST topic / has no graph.

    The cards mirror ``trace_first`` card shape (goal/reasoning/work/result + real ``state``), so the
    same renderer, validators, and gate-skip semantics apply. ``final_answer`` is the real result."""
    fam = (topic_family or "").lower()
    if "sort" in fam:
        ei = example_input.get("graph") if isinstance(example_input, dict) and isinstance(
            example_input.get("graph"), dict) else example_input
        arr = ei.get("array") if isinstance(ei, dict) else None
        if isinstance(arr, list) and arr:
            return build_sort_reference_cards(title, arr)
        return {}
    if "traversal" in fam:
        g = example_input.get("graph") if isinstance(example_input, dict) else None
        # traversal input is a plain adjacency map {node: [neighbours]}; skip the weighted {nodes,edges} form
        if isinstance(g, dict) and g and not g.get("edges"):
            return build_traversal_reference_cards(title, g)
        return {}
    if "search" in fam and isinstance(example_input, dict) and isinstance(example_input.get("nums"), list):
        return build_search_reference_cards(title, example_input["nums"], example_input.get("target"))
    if "bst" in fam or "tree" in fam:
        tree = example_input.get("tree") if isinstance(example_input, dict) else None
        if isinstance(tree, list) and tree:
            return build_bst_reference_cards(title, tree)
        return {}
    if "mst" not in fam:
        return {}
    nodes = _node_labels(example_input)
    edges = _weighted_edges(example_input)
    if len(nodes) < 2 or not edges:
        return {}

    algo = _algorithm_for(title)
    if algo == "prim":
        steps, mst = prim_steps(nodes, edges, start=sorted(nodes)[0])
    else:
        steps, mst = kruskal_steps(nodes, edges)
    if not steps:
        return {}

    cards: list[dict[str, Any]] = []
    prior: dict[str, Any] | None = None
    for idx, s in enumerate(steps, start=1):
        edge = s["edge"]
        es = _fmt_edge(edge)
        u, v, _w = edge
        mst_str = _fmt_mst(s["mst"])
        if s["action"] == "select":
            if algo == "prim":
                goal = f"Add edge {es} to the tree, reaching vertex {v}."
                reasoning = f"{es} is the cheapest edge leaving the visited set, and {v} is not yet in it."
                work = [f"select {es} // cheapest frontier edge — add {v} to the tree"]
            else:
                goal = f"Add edge {es} to the MST."
                reasoning = f"{es} is the smallest remaining edge joining two separate components, so it forms no cycle."
                work = [f"select {es} // {u} and {v} are in different components — no cycle"]
            result = f"MST so far: {mst_str}"
        else:
            if algo == "prim":
                goal = f"Discard edge {es}."
                reasoning = f"{v} is already in the tree, so {es} would revisit a reached vertex."
                work = [f"skip {es} // {v} already visited"]
            else:
                goal = f"Skip edge {es}."
                reasoning = f"{u} and {v} are already connected, so {es} would create a cycle."
                work = [f"skip {es} // {u} and {v} already in the same component"]
            result = f"MST unchanged: {mst_str}"

        state: dict[str, Any] = {"mst": [list(e) for e in s["mst"]]}
        if "components" in s:
            state["components"] = s["components"]
        if "visited" in s:
            state["visited"] = s["visited"]
        cards.append({
            "card_id": f"step_{idx}",
            "title": goal,
            "goal": goal,
            "reasoning": reasoning,
            "work": work,
            "result": result,
            "prior_state": prior,
            "state": state,
            "code_refs": [],
            "state_relevance": "none",
            "state_delta": None,
            "cases_covered": [],
            "trace_backed": True,
        })
        prior = state

    # Problem statement built from the SAME input the cards solve, so the stated graph and the worked
    # solution can never disagree (single source of truth).
    edge_list = ", ".join(_fmt_edge(e) for e in sorted(edges, key=lambda e: (str(e[0]), str(e[1]))))
    problem = (f"Find a minimum spanning tree of the weighted graph with vertices "
               f"{{{', '.join(sorted(nodes))}}} and edges {edge_list}.")

    final = [list(e) for e in mst]
    return {
        "cards": cards,
        "problem": problem,
        "final_answer": final,
        "final_answer_struct": canonical_final_answer(final),
        "trace_backed": True,
        "source": "reference_first",
        "total_weight": sum(w for _u, _v, w in mst),
    }
