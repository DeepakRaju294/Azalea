"""Graph-algorithm family (WORKED_EXAMPLE_ACCURACY_SPEC §15.3) — the `node_link` visual family.

Members share the random-graph generator and the visited/dist/component state idioms; each algorithm owns
only its reference run + required cases + prose facts. Members here: BFS, iterative DFS, Dijkstra, Kruskal.
Future graph algorithms (Prim, Bellman-Ford, topological sort, …) are added as new classes in THIS file,
reusing `random_unweighted_graph` / the normalizers — not as new files.
"""
from __future__ import annotations

import random
from typing import Any, Iterable

from ...state_normalizers import canon_components, components_equal, states_equal
from ...trace_contract import ContractTrace, Step
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase


def random_unweighted_graph(rng: random.Random, *, extra_lo: int, extra_hi: int,
                            n_lo: int = 5, n_hi: int = 7) -> dict[str, Any]:
    """A connected undirected graph (spanning tree + cross edges) labelled A.. with `start` = A."""
    n = rng.randint(n_lo, n_hi)
    labels = [chr(65 + j) for j in range(n)]
    adj: dict[str, set[str]] = {x: set() for x in labels}
    for j in range(1, n):                              # spanning tree → connected
        p = labels[rng.randrange(j)]
        adj[labels[j]].add(p); adj[p].add(labels[j])
    for _ in range(rng.randint(extra_lo, extra_hi)):   # cross edges → skip/revisit events
        a, b = rng.sample(labels, 2)
        adj[a].add(b); adj[b].add(a)
    return {"graph": {k: sorted(v) for k, v in adj.items()}, "start": labels[0]}


# ===================================================================================================
# BFS
# ===================================================================================================
_BFS_CONV = {"algorithm_variant": "breadth_first_search", "neighbor_order": "alphabetical",
             "visited_when": "on_enqueue", "trace_granularity": "dequeue_and_enqueue"}
_BFS_REQ = ["enqueue_neighbors", "skip_visited", "completion"]
_BFS_INV = [{"id": "order_subset_visited", "scope": "every_step", "statement": "dequeued ⊆ visited"},
            {"id": "queue_empty_at_end", "scope": "final_only", "statement": "queue empty"}]


class BFSAdapter(FamilyAdapterBase):
    slug = "bfs"
    example_spec = ExampleSpec(
        input=InstanceShape("letters", count=(5, 7), structure=["connected", "undirected", "has_cross_edge"]),
        stages={"dequeue_enqueue": StageSpec(
            "dequeue_enqueue", "process one node: dequeue it and enqueue its unvisited neighbors",
            teaching_focus="expand one node and add newly discovered neighbors to the queue",
            contains={"dequeue_node": "required", "enqueue_neighbor": "aggregated_supporting",
                      "skip_visited": "aggregated_supporting"},
            state_effects=["node moved from queue to order", "queue reflects newly enqueued neighbors"])},
        structure="dequeue_enqueue+ until queue empty",
        must_exercise=["enqueue_neighbors", "skip_visited", "completion"],
        must_avoid=["disconnected", "no_cross_edge_so_no_skip"],
        terminal="queue empty; every node visited", output_shape="visit order of all nodes")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            yield {**random_unweighted_graph(rng, extra_lo=1, extra_hi=3), "_id": f"bfs_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) >= 3 and bool(ev.get("enqueue_neighbors")) and bool(ev.get("skip_visited"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        graph: dict[str, list[str]] = example_input["graph"]
        start: str = example_input["start"]
        queue, visited, order = [start], {start}, []
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        i = 0
        while queue:
            i += 1
            sid = f"s{i}"
            node = queue[0]
            prior = {"queue": list(queue), "visited": sorted(visited), "order": list(order)}
            queue = queue[1:]
            order.append(node)
            enq, skip = [], []
            for nb in sorted(graph.get(node, [])):
                if nb not in visited:
                    visited.add(nb); queue.append(nb); enq.append(nb)
                elif nb != node:
                    skip.append(nb)
            after = {"queue": list(queue), "visited": sorted(visited), "order": list(order)}
            if enq:
                evidence.setdefault("enqueue_neighbors", []).append(sid)
            if skip:
                evidence.setdefault("skip_visited", []).append(sid)
            steps.append(Step(
                id=sid, operation="dequeue_enqueue", prior_state=prior, state_after=after,
                inputs={"node": node, "enqueued": enq, "skipped": skip},
                decision=f"visit {node}; enqueue {enq or 'nothing'}" + (f"; skip already-visited {skip}" if skip else ""),
                reason=f"dequeue {node}; its unvisited neighbours {enq} join the queue",
                visual_state={"kind": "queue_graph", "queue": list(queue), "visited": sorted(visited),
                              "active": node},
                visual_delta={"dequeued": node, "enqueued": enq, "skipped": skip},
                expected_visible_result=f"Visit {node}; queue {queue}; visited {sorted(visited)}",
                facts={"allowed_values": sorted(graph),
                       "required_facts": [f"visit {node}"] + [f"enqueue {x}" for x in enq],
                       "forbidden_claims": [f"visit {x}" for x in skip]}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=f"Run breadth-first search from {start} on the graph {graph}. Give the visit order.",
            conventions=dict(_BFS_CONV), initial_state={"queue": [start], "visited": [start], "order": []},
            final_answer={"visit_order": list(order)}, steps=steps,
            invariants=[dict(x) for x in _BFS_INV], required_cases=list(_BFS_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input, attempt=attempt))

    def states_equivalent(self, a, b):
        return states_equal(a, b, ordered=["queue", "order"], as_set=["visited"])

    def final_answer_entails(self, state, answer):
        return list(state.get("order") or []) == list((answer or {}).get("visit_order") or []) \
            and not state.get("queue")

    def invariant_holds(self, inv, state):
        if inv.get("id") == "order_subset_visited":
            return set(state.get("order") or []) <= set(state.get("visited") or [])
        if inv.get("id") == "queue_empty_at_end":
            return not state.get("queue")
        return True

    def validate_step_shape(self, step):
        errs = []
        if step.operation != "dequeue_enqueue":
            errs.append(f"unexpected operation {step.operation!r}")
        if "node" not in step.inputs:
            errs.append("missing inputs.node")
        for k in ("queue", "visited"):
            if k not in step.prior_state:
                errs.append(f"prior missing {k}")
        return errs

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        return [] if step.inputs["node"].lower() in prose else [("node_not_discussed", step.inputs["node"])]


# ===================================================================================================
# Iterative DFS (visited-on-pop, push reverse-alphabetical, duplicate stack entries skipped on pop)
# ===================================================================================================
_DFS_CONV = {"algorithm_variant": "iterative_dfs", "neighbor_order": "alphabetical",
             "push_order": "reverse_alphabetical", "visited_when": "on_pop",
             "duplicate_stack_entries": "allowed", "trace_granularity": "one_pop"}
_DFS_REQ = ["push_neighbors", "revisit_prevention", "completion"]
_DFS_INV = [{"id": "order_subset_visited", "scope": "every_step", "statement": "order ⊆ visited"},
            {"id": "stack_empty_at_end", "scope": "final_only", "statement": "stack empty"}]


class DFSIterativeAdapter(FamilyAdapterBase):
    slug = "dfs_iter"
    example_spec = ExampleSpec(
        input=InstanceShape("letters", count=(5, 7), structure=["connected", "undirected", "has_extra_edge"]),
        stages={"pop": StageSpec(
            "pop", "pop one node: visit it and push its unvisited neighbors (or skip if already visited)",
            teaching_focus="pop a node, visit it, and push its neighbors for later",
            contains={"pop_node": "required", "push_neighbor": "aggregated_supporting",
                      "skip_revisit": "optional_supporting"},
            state_effects=["node popped from stack", "visited+order updated if newly visited"])},
        structure="pop+ until stack empty",
        must_exercise=["push_neighbors", "revisit_prevention", "completion"],
        must_avoid=["no_revisit_so_no_skip"],
        terminal="stack empty; every node visited", output_shape="visit order of all nodes")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            yield {**random_unweighted_graph(rng, extra_lo=2, extra_hi=3), "_id": f"dfs_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) >= 4 and bool(ev.get("push_neighbors")) and bool(ev.get("revisit_prevention"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        graph: dict[str, list[str]] = example_input["graph"]
        start: str = example_input["start"]
        stack, visited, order = [start], set(), []
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        i = 0
        while stack:
            i += 1
            sid = f"s{i}"
            prior = {"stack": list(stack), "visited": sorted(visited), "order": list(order)}
            node = stack.pop()
            if node in visited:
                after = {"stack": list(stack), "visited": sorted(visited), "order": list(order)}
                decision = f"pop {node} — already visited, skip"
                pushed: list[str] = []
                evidence.setdefault("revisit_prevention", []).append(sid)
            else:
                visited.add(node); order.append(node)
                pushed = []
                for nb in sorted(graph.get(node, []), reverse=True):
                    if nb not in visited:
                        stack.append(nb); pushed.append(nb)
                after = {"stack": list(stack), "visited": sorted(visited), "order": list(order)}
                decision = f"visit {node}; push {list(reversed(pushed)) or 'nothing'}"
                if pushed:
                    evidence.setdefault("push_neighbors", []).append(sid)
            steps.append(Step(
                id=sid, operation="pop", prior_state=prior, state_after=after,
                inputs={"node": node, "pushed": pushed, "skipped": node in visited and not pushed},
                decision=decision,
                reason=(f"pop {node}; already visited" if node in visited and sid in
                        evidence.get("revisit_prevention", []) else f"pop and visit {node}"),
                visual_state={"kind": "stack_graph", "stack": list(stack), "stack_top": "right",
                              "visited": sorted(visited), "active": node},
                visual_delta={"popped": node, "pushed": pushed},
                expected_visible_result=f"Pop {node}; stack {stack}; visited {sorted(visited)}",
                facts={"allowed_values": sorted(graph),
                       "required_facts": [f"pop {node}"], "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=f"Run iterative depth-first search from {start} on the graph {graph}. Give the visit order.",
            conventions=dict(_DFS_CONV), initial_state={"stack": [start], "visited": [], "order": []},
            final_answer={"visit_order": list(order)}, steps=steps,
            invariants=[dict(x) for x in _DFS_INV], required_cases=list(_DFS_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input, attempt=attempt))

    def states_equivalent(self, a, b):
        return states_equal(a, b, ordered=["stack", "order"], as_set=["visited"])

    def final_answer_entails(self, state, answer):
        return list(state.get("order") or []) == list((answer or {}).get("visit_order") or []) \
            and not state.get("stack")

    def invariant_holds(self, inv, state):
        if inv.get("id") == "order_subset_visited":
            return set(state.get("order") or []) <= set(state.get("visited") or [])
        if inv.get("id") == "stack_empty_at_end":
            return not state.get("stack")
        return True

    def validate_step_shape(self, step):
        errs = []
        if step.operation != "pop":
            errs.append(f"unexpected operation {step.operation!r}")
        if "node" not in step.inputs:
            errs.append("missing inputs.node")
        for k in ("stack", "visited"):
            if k not in step.prior_state:
                errs.append(f"prior missing {k}")
        return errs

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        return [] if step.inputs["node"].lower() in prose else [("node_not_discussed", step.inputs["node"])]


# ===================================================================================================
# Dijkstra (settle the closest unvisited node, relax its edges; non-negative weights)
# ===================================================================================================
_DIJ_CONV = {"algorithm_variant": "dijkstra", "weights": "non_negative",
             "tie_break": "lexicographic_node", "trace_granularity": "settle_and_relax"}
_DIJ_REQ = ["relax_improves", "no_improvement", "completion"]
_DIJ_INV = [{"id": "dist_nonneg", "scope": "every_step", "statement": "all distances are non-negative"},
            {"id": "all_settled", "scope": "final_only", "statement": "every reachable node settled"}]


class DijkstraAdapter(FamilyAdapterBase):
    slug = "dijkstra"
    # Multi-stage grammar (§0): init -> settle_node -> relax_edge. Each relaxation is its own learner-visible
    # decision (improve vs no-change), not aggregated — the relaxation IS the Dijkstra decision.
    example_spec = ExampleSpec(
        input=InstanceShape("weighted_graph", count=(4, 6), value_range=(1, 12),
                            structure=["connected", "non_negative_weights"]),
        stages={
            "init": StageSpec(
                "init", "set the source to 0 and every other node to infinity",
                teaching_focus="Dijkstra starts with the source at distance 0 and all others at infinity",
                cardinality="exactly_once", contains={"init_distances": "required"},
                state_effects=["source distance 0, all others infinity, nothing settled"]),
            "settle_node": StageSpec(
                "settle_node", "settle the nearest unvisited node — its distance is now final",
                teaching_focus="the closest unvisited node's distance can never improve, so finalize it",
                contains={"pick_min": "required"},
                state_effects=["one node moved to visited at its final distance"]),
            "relax_edge": StageSpec(
                "relax_edge", "relax ONE outgoing edge: improve the neighbor's distance, or leave it",
                teaching_focus="try a shorter path through the settled node to each neighbor",
                contains={"compare_candidate": "required", "update_distance": "aggregated_supporting"},
                state_effects=["the neighbor's distance is lowered, or unchanged"]),
        },
        structure="init, then (settle_node, relax_edge*)+ until all reachable settled",
        must_exercise=["relax_improves", "no_improvement", "completion"],
        must_avoid=["star_graph_no_competition"],
        terminal="every reachable node settled", output_shape="shortest-distance map from the source")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(4, 6)
            labels = [chr(65 + j) for j in range(n)]
            adj: dict[str, dict[str, int]] = {x: {} for x in labels}
            for j in range(1, n):
                p = labels[rng.randrange(j)]
                w = rng.randint(1, 9)
                adj[labels[j]][p] = w; adj[p][labels[j]] = w
            for _ in range(rng.randint(2, 3)):
                a, b = rng.sample(labels, 2)
                w = rng.randint(1, 12)
                adj[a][b] = w; adj[b][a] = w
            yield {"graph": {k: dict(v) for k, v in adj.items()}, "source": labels[0],
                   "_id": f"dijkstra_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) >= 3 and bool(ev.get("relax_improves")) and bool(ev.get("no_improvement"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        graph: dict[str, dict[str, int]] = example_input["graph"]
        source: str = example_input["source"]
        inf = sum(w for nb in graph.values() for w in nb.values()) + 1
        dist = {x: (0 if x == source else inf) for x in graph}
        visited: set[str] = set()
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        _n = 0

        def _sid():
            nonlocal _n
            _n += 1
            return f"s{_n}"

        def _dmap():
            return {k: (None if d >= inf else d) for k, d in dist.items()}

        def _dstr():
            return ", ".join(f"{k}:{'inf' if d >= inf else d}" for k, d in sorted(dist.items()))

        all_w = sorted({w for nb in graph.values() for w in nb.values()})
        # init stage
        _init = {"dist": dict(dist), "visited": []}
        steps.append(Step(
            id=_sid(), operation="init", prior_state=_init, state_after=_init, inputs={"source": source},
            decision="initialize distances", reason=(f"set the source {source} to distance 0 and every other "
                                                     "node to infinity; nothing is settled yet."),
            visual_state={"kind": "dist_graph", "dist": _dmap(), "visited": [], "active": source},
            visual_delta={"source": source},
            expected_visible_result=f"Initialize distances: {source} at 0, all others at infinity. Distances {{{_dstr()}}}.",
            facts={"allowed_values": [0], "required_facts": [], "forbidden_claims": []}))
        while len(visited) < len(graph):
            u = min((x for x in graph if x not in visited), key=lambda x: (dist[x], x))
            if dist[u] >= inf:
                break
            # settle_node stage — u's distance is final
            s_id = _sid()
            prior = {"dist": dict(dist), "visited": sorted(visited)}
            visited.add(u)
            steps.append(Step(
                id=s_id, operation="settle_node", prior_state=prior, state_after={"dist": dict(dist), "visited": sorted(visited)},
                inputs={"node": u, "dist": dist[u]}, decision=f"settle {u} (final distance {dist[u]})",
                reason=f"{u} is the closest unvisited node, so its distance {dist[u]} can never improve — finalize it.",
                visual_state={"kind": "dist_graph", "dist": _dmap(), "visited": sorted(visited), "active": u},
                visual_delta={"settled": u},
                expected_visible_result=f"Settle {u}: its shortest distance is final at {dist[u]}.",
                facts={"allowed_values": sorted({d for d in dist.values() if d < inf}),
                       "required_facts": [f"settle {u}", str(dist[u])], "forbidden_claims": []}))
            # relax_edge stages — one learner-visible decision per outgoing edge
            for v, w in sorted(graph[u].items()):
                if v in visited:
                    continue
                r_id = _sid()
                prior = {"dist": dict(dist), "visited": sorted(visited)}
                cand = dist[u] + w
                pv = dist[v]
                pv_s = "inf" if pv >= inf else str(pv)
                improved = cand < pv
                if improved:
                    dist[v] = cand
                    evidence.setdefault("relax_improves", []).append(r_id)
                    decision = f"relax {u}->{v}: {dist[u]}+{w}={cand} < {pv_s} -> improve {v} to {cand}"
                    res = f"Relax edge {u}->{v} (weight {w}): {cand} beats {pv_s}, so improve {v} to {cand}."
                else:
                    evidence.setdefault("no_improvement", []).append(r_id)
                    decision = f"relax {u}->{v}: {dist[u]}+{w}={cand} >= {pv_s} -> no change"
                    res = f"Relax edge {u}->{v} (weight {w}): {cand} does not beat {pv_s}, so {v} stays {pv_s}."
                steps.append(Step(
                    id=r_id, operation="relax_edge", prior_state=prior, state_after={"dist": dict(dist), "visited": sorted(visited)},
                    inputs={"edge": [u, v, w], "from": u, "to": v, "weight": w, "candidate": cand, "improved": improved},
                    decision=decision,
                    reason=(f"through {u}, {v} is reachable in {dist[u]}+{w}={cand}; "
                            + ("that beats its current distance, so lower it." if improved else
                               "that does not beat its current distance, so keep it.")),
                    visual_state={"kind": "dist_graph", "dist": _dmap(), "visited": sorted(visited), "active": u},
                    visual_delta={"relaxed": [u, v], "improved": improved},
                    expected_visible_result=res,
                    facts={"allowed_values": sorted(set(all_w) | {d for d in dist.values() if d < inf} | {cand}),
                           "required_facts": [str(u), str(v), str(w)], "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=f"Run Dijkstra's algorithm from {source} on the weighted graph {graph}. Give shortest distances.",
            conventions=dict(_DIJ_CONV),
            initial_state={"dist": {x: (0 if x == source else inf) for x in graph}, "visited": []},
            final_answer={"dist": {k: (d if d < inf else None) for k, d in dist.items()}}, steps=steps,
            invariants=[dict(x) for x in _DIJ_INV], required_cases=list(_DIJ_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input, attempt=attempt))

    def states_equivalent(self, a, b):
        return states_equal(a, b, as_set=["visited"]) and (a or {}).get("dist") == (b or {}).get("dist")

    def final_answer_entails(self, state, answer):
        big = max([d for d in (state.get("dist") or {}).values() if isinstance(d, int)] or [0]) + 1
        sd = {k: (None if (isinstance(d, int) and d >= big) else d) for k, d in (state.get("dist") or {}).items()}
        return sd == (answer or {}).get("dist")

    def invariant_holds(self, inv, state):
        if inv.get("id") == "dist_nonneg":
            return all((d is None) or d >= 0 for d in (state.get("dist") or {}).values())
        return True

    def validate_step_shape(self, step):
        errs = []
        if step.operation == "init":
            if "source" not in step.inputs:
                errs.append("init missing inputs.source")
            return errs
        if step.operation == "settle_node":
            if "node" not in step.inputs:
                errs.append("settle missing inputs.node")
            return errs
        if step.operation == "relax_edge":
            if "edge" not in step.inputs:
                errs.append("relax missing inputs.edge")
            return errs
        errs.append(f"unexpected operation {step.operation!r}")
        return errs

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        if step.operation == "init":
            return []
        if step.operation == "settle_node":
            u = step.inputs["node"]
            return [] if u.lower() in prose and str(step.inputs["dist"]) in prose else \
                [("node_or_distance_not_discussed", f"{u}={step.inputs['dist']}")]
        # relax_edge: the prose must name the edge endpoints + weight
        u, v, w = step.inputs["edge"]
        if str(u).lower() in prose and str(v).lower() in prose and str(w) in prose:
            return []
        return [("edge_not_discussed", f"{u}->{v}({w})")]


# ===================================================================================================
# Kruskal (consider edges in ascending weight; accept if it joins two components, else skip as a cycle)
# ===================================================================================================
_KRU_CONV = {"algorithm_variant": "kruskal", "edge_order": "ascending_weight", "tie_break": "lexicographic",
             "component_representation": "disjoint_sets", "trace_granularity": "one_edge_consider"}
_KRU_REQ = ["edge_acceptance", "cycle_rejection", "completion"]
_KRU_INV = [{"id": "forest", "scope": "every_step", "statement": "selected edges form a forest (acyclic)"},
            {"id": "spans_all", "scope": "final_only", "statement": "selected edges connect all nodes (V-1)"}]


class KruskalAdapter(FamilyAdapterBase):
    slug = "kruskal"
    example_spec = ExampleSpec(
        input=InstanceShape("weighted_graph", count=(5, 6), value_range=(1, 30),
                            structure=["connected", "distinct_edges", "has_cycle_edge"]),
        stages={
            "setup_sorted_edges": StageSpec(
                "setup_sorted_edges", "sort every edge by weight and present that processing order",
                teaching_focus="Kruskal sorts all edges by weight first, then walks them cheapest-first",
                cardinality="exactly_once",
                contains={"sort_edges": "required"},
                state_effects=["edges presented in nondecreasing weight order; the MST is still empty"]),
            "consider_edge": StageSpec(
                "consider_edge", "consider one edge (in weight order): accept it or skip it as a cycle",
                teaching_focus="add an edge only when it connects two separate components",
                contains={"find_roots": "internal", "decide_accept_or_skip": "required",
                          "union_components": "aggregated_supporting", "append_to_mst": "aggregated_supporting"},
                state_effects=["edge accepted (components merged + MST grows) or skipped (cycle)"]),
        },
        structure="setup_sorted_edges, then consider_edge+ until V-1 edges accepted",
        must_exercise=["edge_acceptance", "cycle_rejection", "completion"],
        must_avoid=["tree_only_no_cycle_edge"],
        terminal="V-1 edges accepted (a spanning tree)", output_shape="MST edge set + total weight")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(5, 6)
            labels = [chr(65 + j) for j in range(n)]
            edges, seen = [], set()
            for j in range(1, n):                          # spanning tree (connected)
                p = labels[rng.randrange(j)]
                a, b = sorted((labels[j], p))
                edges.append([a, b, rng.randint(1, 9)]); seen.add((a, b))
            for _ in range(rng.randint(2, 4)):             # extra edges → cycle rejections
                a, b = sorted(rng.sample(labels, 2))
                if (a, b) not in seen:
                    edges.append([a, b, rng.randint(1, 30)]); seen.add((a, b))
            yield {"graph": {"nodes": labels, "edges": edges}, "_id": f"kruskal_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return bool(ev.get("edge_acceptance")) and bool(ev.get("cycle_rejection")) and len(trace.steps) >= 4

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        nodes: list[str] = list(example_input["graph"]["nodes"])
        edges = sorted([list(e) for e in example_input["graph"]["edges"]], key=lambda e: (e[2], e[0], e[1]))
        parent = {x: x for x in nodes}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def comps():
            groups: dict[str, list[str]] = {}
            for x in nodes:
                groups.setdefault(find(x), []).append(x)
            return canon_components(groups.values())

        selected: list[list[Any]] = []
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        total = 0
        target = len(nodes) - 1
        # setup_sorted_edges stage (multi-stage grammar §0): present the FULL sorted edge list up front so the
        # learner sees Kruskal's defining "sort, then add cheapest-first" before any decision (fixes C3).
        _init = {"selected_edges": [], "components": comps()}
        steps.append(Step(
            id="s0", operation="setup_sorted_edges", prior_state=_init, state_after=_init,
            inputs={"sorted_edges": [list(e) for e in edges]}, decision="sort",
            reason="Kruskal processes edges cheapest-first, so sort every edge by weight before adding any.",
            visual_state={"kind": "weighted_graph", "selected": [], "components": comps(), "active_edge": None},
            visual_delta={"sorted": [list(e) for e in edges]},
            expected_visible_result=("Edges sorted by weight: "
                                     + ", ".join(f"({u},{v},{w})" for u, v, w in edges) + ". MST starts empty."),
            facts={"allowed_values": sorted({e[2] for e in edges}), "required_facts": [], "forbidden_claims": []}))
        for i, (u, v, w) in enumerate(edges, start=1):
            sid = f"s{i}"
            prior = {"selected_edges": [list(e) for e in selected], "components": comps()}
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv
                selected.append([u, v, w]); total += w
                decision = "accept"
                evidence.setdefault("edge_acceptance", []).append(sid)
            else:
                decision = "skip"
                evidence.setdefault("cycle_rejection", []).append(sid)
            after = {"selected_edges": [list(e) for e in selected], "components": comps()}
            steps.append(Step(
                id=sid, operation="consider_edge", prior_state=prior, state_after=after,
                inputs={"edge": [u, v, w], "weight": w}, decision=decision,
                reason=(f"({u},{v},{w}): {u} and {v} are in different components — add it (no cycle)"
                        if decision == "accept" else
                        f"({u},{v},{w}): {u} and {v} are already connected — skip (would form a cycle)"),
                visual_state={"kind": "weighted_graph", "selected": [list(e) for e in selected],
                              "components": comps(), "active_edge": [u, v, w]},
                visual_delta={"considered": [u, v, w], "decision": decision},
                expected_visible_result=f"Edge ({u},{v},{w}) {decision}; MST so far {selected}",
                facts={"allowed_values": sorted({e[2] for e in edges} | {total, len(nodes), len(selected)}),
                       "required_facts": [str(u), str(v), str(w)],
                       "forbidden_claims": []}))   # decision correctness checked in validate_prose_claims
            if decision == "accept" and len(selected) == target:
                if evidence.get("cycle_rejection"):
                    break
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Find a minimum spanning tree of the weighted graph with nodes {nodes} and edges "
                     f"{example_input['graph']['edges']} using Kruskal's algorithm."),
            conventions=dict(_KRU_CONV),
            initial_state={"selected_edges": [], "components": canon_components([[x] for x in nodes])},
            final_answer={"mst_edges": [list(e) for e in selected], "total_weight": total}, steps=steps,
            invariants=[dict(x) for x in _KRU_INV], required_cases=list(_KRU_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input, attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        if [list(e) for e in (a.get("selected_edges") or [])] != [list(e) for e in (b.get("selected_edges") or [])]:
            return False
        return components_equal(a.get("components") or [], b.get("components") or [])

    def final_answer_entails(self, state, answer):
        sel = [list(e) for e in (state.get("selected_edges") or [])]
        return sel == [list(e) for e in (answer or {}).get("mst_edges", [])]

    def invariant_holds(self, inv, state):
        sel = state.get("selected_edges") or []
        if inv.get("id") == "forest":
            return len(sel) <= max(0, sum(len(g) for g in (state.get("components") or [])) - 1)
        if inv.get("id") == "spans_all":
            comps = state.get("components") or []
            return len(comps) <= 1 or len(sel) == sum(len(g) for g in comps) - 1
        return True

    def validate_step_shape(self, step):
        errs = []
        if step.operation == "setup_sorted_edges":       # multi-stage: the sort/present step
            if "sorted_edges" not in step.inputs:
                errs.append("setup missing inputs.sorted_edges")
            return errs
        if step.operation != "consider_edge":
            errs.append(f"unexpected operation {step.operation!r}")
        if "edge" not in step.inputs:
            errs.append("missing inputs.edge")
        if step.decision not in ("accept", "skip"):
            errs.append(f"bad decision {step.decision!r}")
        return errs

    def validate_prose_claims(self, card, step):
        if step.operation == "setup_sorted_edges":       # presents the sorted list; no per-edge decision
            return []
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        u, v, w = step.inputs["edge"]
        out = []
        if not (str(u).lower() in prose and str(v).lower() in prose and str(w) in prose):
            out.append(("edge_not_discussed", f"({u},{v},{w})"))
        if step.decision == "skip" and not any(k in prose for k in ("cycle", "skip", "reject", "already")):
            out.append(("decision_mismatch", "cycle edge but prose doesn't say skip/cycle"))
        if step.decision == "accept" and not any(k in prose for k in ("add", "select", "include", "accept")):
            out.append(("decision_mismatch", "accepted edge but prose doesn't say add/select"))
        return out


# ===================================================================================================
# Prim (eager: grow the tree from a start vertex; each step adds the cheapest edge crossing the cut)
# ===================================================================================================
_PRIM_CONV = {"algorithm_variant": "prim_eager", "start": "first_node", "edge_choice": "min_crossing_edge",
              "tie_break": "lexicographic", "trace_granularity": "one_vertex_added"}
_PRIM_REQ = ["edge_selection", "competing_candidates", "completion"]
_PRIM_INV = [{"id": "tree_edges", "scope": "every_step", "statement": "selected edges = |in_tree| - 1 (a tree)"},
             {"id": "spans_all", "scope": "final_only", "statement": "every node is in the tree"}]


def _canon_edge(u, v, w) -> tuple:
    a, b = sorted((u, v))
    return (a, b, w)


class PrimAdapter(FamilyAdapterBase):
    slug = "prim"
    example_spec = ExampleSpec(
        input=InstanceShape("weighted_graph", count=(5, 6), value_range=(1, 30),
                            structure=["connected", "distinct_edges"]),
        stages={
            "setup_start": StageSpec(
                "setup_start", "choose the start vertex; the tree begins with just that vertex",
                teaching_focus="Prim grows ONE tree from a chosen start, adding the cheapest crossing edge each step",
                cardinality="exactly_once",
                contains={"pick_start": "required"},
                state_effects=["the tree contains only the start vertex; no edges yet"]),
            "select_edge": StageSpec(
                "select_edge", "select the cheapest edge crossing out of the tree and add its new vertex",
                teaching_focus="grow the tree by the lowest-weight edge to a new vertex",
                contains={"scan_crossing_edges": "internal", "select_min_crossing_edge": "required",
                          "add_vertex": "aggregated_supporting", "update_frontier": "aggregated_supporting"},
                state_effects=["one new vertex added to the tree", "the selected edge added to the MST"]),
        },
        structure="setup_start, then select_edge+ until all vertices in the tree",
        must_exercise=["edge_selection", "competing_candidates", "completion"],
        must_avoid=["no_competing_crossing_edges"],
        terminal="all vertices in the tree (V-1 edges)", output_shape="MST edge set + total weight")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(5, 6)
            labels = [chr(65 + j) for j in range(n)]
            edges, seen = [], set()
            for j in range(1, n):                          # spanning tree (connected)
                p = labels[rng.randrange(j)]
                a, b = sorted((labels[j], p))
                edges.append([a, b, rng.randint(1, 9)]); seen.add((a, b))
            for _ in range(rng.randint(2, 4)):             # extra edges → competing crossing choices
                a, b = sorted(rng.sample(labels, 2))
                if (a, b) not in seen:
                    edges.append([a, b, rng.randint(1, 30)]); seen.add((a, b))
            yield {"graph": {"nodes": labels, "edges": edges}, "start": labels[0], "_id": f"prim_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) >= 3 and bool(ev.get("edge_selection")) and bool(ev.get("competing_candidates"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        nodes: list[str] = list(example_input["graph"]["nodes"])
        start: str = example_input.get("start") or nodes[0]
        adj: dict[str, dict[str, int]] = {x: {} for x in nodes}
        for u, v, w in example_input["graph"]["edges"]:
            adj[u][v] = w; adj[v][u] = w
        in_tree = {start}
        selected: list[list[Any]] = []
        total = 0
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        i = 0
        all_weights = sorted({e[2] for e in example_input["graph"]["edges"]})
        # setup_start stage (multi-stage grammar §0): make Prim's opening explicit — start vertex + empty tree.
        _init = {"in_tree": [start], "selected_edges": []}
        steps.append(Step(
            id="s0", operation="setup_start", prior_state=_init, state_after=_init,
            inputs={"start": start}, decision="start",
            reason="Prim grows one tree from a chosen start vertex, repeatedly adding the cheapest edge to a new vertex.",
            visual_state={"kind": "weighted_graph", "in_tree": [start], "selected": [], "active_edge": None},
            visual_delta={"start": start},
            expected_visible_result=f"Start Prim from {start}. Tree begins as {{{start}}}; no edges selected yet.",
            facts={"allowed_values": sorted(set(all_weights) | {0}), "required_facts": [], "forbidden_claims": []}))
        while len(in_tree) < len(nodes):
            crossing = sorted((w, u, v) for u in in_tree for v, w in adj[u].items() if v not in in_tree)
            if not crossing:
                break                                      # disconnected (candidates are connected)
            w, u, v = crossing[0]
            i += 1
            sid = f"s{i}"
            prior = {"in_tree": sorted(in_tree), "selected_edges": [list(e) for e in selected]}
            in_tree.add(v); selected.append([u, v, w]); total += w
            after = {"in_tree": sorted(in_tree), "selected_edges": [list(e) for e in selected]}
            evidence.setdefault("edge_selection", []).append(sid)
            if len(crossing) >= 2:                         # a real choice was made (competing crossing edges)
                evidence.setdefault("competing_candidates", []).append(sid)
            cand_str = ", ".join(f"{cu}-{cv}({cw})" for cw, cu, cv in crossing[:4])
            steps.append(Step(
                id=sid, operation="select_edge", prior_state=prior, state_after=after,
                inputs={"edge": [u, v, w], "weight": w,
                        "candidates": [[cu, cv, cw] for cw, cu, cv in crossing]},
                decision="select",
                reason=(f"the minimum-weight edge crossing out of the tree is {u}-{v} (weight {w}); "
                        f"among candidates {cand_str} it is the cheapest, so add {v}"),
                visual_state={"kind": "weighted_graph", "in_tree": sorted(in_tree),
                              "selected": [list(e) for e in selected], "active_edge": [u, v, w]},
                visual_delta={"added_vertex": v, "selected_edge": [u, v, w]},
                expected_visible_result=f"Select edge ({u},{v},{w}); tree now {sorted(in_tree)}",
                facts={"allowed_values": sorted(set(all_weights) | {total}),
                       "required_facts": [str(u), str(v), str(w)], "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Find a minimum spanning tree of the weighted graph with nodes {nodes} and edges "
                     f"{example_input['graph']['edges']} using Prim's algorithm, starting from {start}."),
            conventions=dict(_PRIM_CONV),
            initial_state={"in_tree": [start], "selected_edges": []},
            final_answer={"mst_edges": [list(e) for e in selected], "total_weight": total}, steps=steps,
            invariants=[dict(x) for x in _PRIM_INV], required_cases=list(_PRIM_REQ), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input, attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return (sorted(a.get("in_tree") or []) == sorted(b.get("in_tree") or [])
                and [list(e) for e in (a.get("selected_edges") or [])]
                == [list(e) for e in (b.get("selected_edges") or [])])

    def final_answer_entails(self, state, answer):
        sel = {_canon_edge(*e) for e in (state.get("selected_edges") or [])}
        ans = {_canon_edge(*e) for e in (answer or {}).get("mst_edges", [])}
        return sel == ans

    def invariant_holds(self, inv, state):
        sel = state.get("selected_edges") or []
        tree = state.get("in_tree") or []
        if inv.get("id") == "tree_edges":
            return len(sel) == max(0, len(tree) - 1)
        return True

    def validate_step_shape(self, step):
        errs = []
        if step.operation == "setup_start":              # multi-stage: the start/initialize step
            if "start" not in step.inputs:
                errs.append("setup missing inputs.start")
            return errs
        if step.operation != "select_edge":
            errs.append(f"unexpected operation {step.operation!r}")
        if "edge" not in step.inputs:
            errs.append("missing inputs.edge")
        return errs

    def validate_prose_claims(self, card, step):
        if step.operation == "setup_start":              # presents the start vertex; no edge decision
            return []
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        u, v, w = step.inputs["edge"]
        out = []
        if not (str(u).lower() in prose and str(v).lower() in prose and str(w) in prose):
            out.append(("edge_not_discussed", f"({u},{v},{w})"))
        if not any(k in prose for k in ("select", "add", "include", "choose", "pick")):
            out.append(("decision_mismatch", "selected edge but prose doesn't say select/add"))
        return out
