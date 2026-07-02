"""Tree family (ADAPTER_CATALOG A2) — a parent/child binary-tree structure (NO visited-set / cycle handling,
unlike the graph family). Members here: inorder / preorder / postorder / level-order traversal, BST search.
Future: BST insert / delete, heap ops, trie, LCA.

TEMPLATE — this is the reference *coding* adapter every new coding concept follows. It shows the full
contract: an `ExampleSpec` (input shape + stage grammar + required cases + terminal), a `candidates()`
generator, a `reference()` that runs the REAL algorithm to produce a verified `ContractTrace` (no LLM), the
Stage-0 `is_teaching_trace` gate, the equivalence/entailment/invariant hooks, and structured `fact()` facts.
A coding adapter additionally ships a canonical solution (see `canonical_solutions.py::tree_inorder`)."""
from __future__ import annotations

import random
import re
from collections import deque
from typing import Any, Iterable

from ...trace_contract import ContractTrace, Step, fact
from ..example_spec import ExampleSpec, InstanceShape, StageSpec
from .base import FamilyAdapterBase

_CONV = {"structure": "binary_search_tree", "order": "inorder (left, node, right)",
         "property": "inorder of a BST yields values in ascending order", "trace_granularity": "one_node_visit"}
_REQUIRED = ["visit_leftmost_first", "ascending_output", "completion"]
_INV = [{"id": "output_sorted", "scope": "every_step", "statement": "the output so far is strictly ascending"},
        {"id": "all_visited", "scope": "final_only", "statement": "every node has been visited exactly once"}]


def _insert(tree: dict[int, dict[str, Any]], root: int | None, value: int) -> int:
    """BST insert; returns the (possibly new) root. `tree[v] = {'left':..,'right':..}`."""
    if root is None:
        tree[value] = {"left": None, "right": None}
        return value
    node = root
    while True:
        side = "left" if value < node else "right"
        child = tree[node][side]
        if child is None:
            tree[node][side] = value
            tree[value] = {"left": None, "right": None}
            return root
        node = child


def _inorder(tree: dict[int, dict[str, Any]], root: int | None) -> list[int]:
    out: list[int] = []
    stack: list[int] = []
    node = root
    while node is not None or stack:
        while node is not None:
            stack.append(node)
            node = tree[node]["left"]
        node = stack.pop()
        out.append(node)
        node = tree[node]["right"]
    return out


def _subtree_size(tree: dict[int, dict[str, Any]], node: int | None) -> int:
    if node is None:
        return 0
    return 1 + _subtree_size(tree, tree[node]["left"]) + _subtree_size(tree, tree[node]["right"])


class InorderTraversalAdapter(FamilyAdapterBase):
    slug = "tree_inorder"
    label_convention = "ints"                  # §2.3 — BST node values are integers
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(4, 7), value_range=(1, 40), structure=["distinct", "bst"]),
        stages={"visit": StageSpec(
            "visit", "visit the next node in inorder position",
            teaching_focus="a node is output only after its entire left subtree",
            contains={"append this node's value to the output": "required",
                      "move on to the right subtree": "aggregated_supporting"},
            state_effects=["one node moves from unvisited to the output; the output stays ascending"])},
        structure="visit+ until every node is output",
        must_exercise=["visit_leftmost_first", "ascending_output", "completion"],
        must_avoid=["single_node_tree"],
        terminal="every node visited; output is the sorted values", output_shape="the inorder node sequence")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(4, 7)
            values = rng.sample(range(1, 41), n)          # distinct
            tree: dict[int, dict[str, Any]] = {}
            root: int | None = None
            for v in values:
                root = _insert(tree, root, v)
            yield {"tree": tree, "root": root, "insert_order": values, "_id": f"inorder_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        return len(trace.steps) >= 3 and bool(trace.case_evidence.get("visit_leftmost_first"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        tree = example_input["tree"]
        root = example_input["root"]
        order = _inorder(tree, root)
        leftmost = order[0] if order else None
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        output: list[int] = []
        for idx, node in enumerate(order, start=1):
            sid = f"s{idx}"
            prior = {"output": list(output), "current": node}
            output = output + [node]
            after = {"output": list(output), "current": node}
            if node == leftmost:
                evidence.setdefault("visit_leftmost_first", []).append(sid)
            if output == sorted(output):
                evidence.setdefault("ascending_output", []).append(sid)
            steps.append(Step(
                id=sid, operation="visit", prior_state=prior, state_after=after,
                inputs={"node": node, "position": idx, "output_after": list(output)},
                decision=f"visit {node}",
                reason=(f"{node}'s left subtree is fully visited, so {node} is next in inorder"
                        if idx > 1 else f"{node} is the leftmost node, so it is visited first"),
                visual_state={"kind": "tree", "visited": list(output), "current": node},
                visual_delta={"emitted": node},
                expected_visible_result=f"Visit {node}; output so far {output}.",
                facts={"allowed_values": sorted(tree.keys()),
                       "required_facts": [fact("visit", f"visit {node}"), fact("output", str(output))],
                       "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Perform an inorder traversal of the binary search tree built by inserting "
                     f"{example_input['insert_order']} (root {root})."),
            conventions=dict(_CONV), initial_state={"output": [], "current": None},
            final_answer={"visit_order": order}, steps=steps,
            invariants=[dict(x) for x in _INV], required_cases=list(_REQUIRED), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        return list((a or {}).get("output") or []) == list((b or {}).get("output") or [])

    def final_answer_entails(self, state, answer):
        return list((state or {}).get("output") or []) == list((answer or {}).get("visit_order") or [])

    def invariant_holds(self, inv, state):
        out = (state or {}).get("output") or []
        if inv.get("id") == "output_sorted":
            return out == sorted(out)
        if inv.get("id") == "all_visited":
            return True                                    # cardinality checked by fidelity, not per-state
        return True

    def validate_step_shape(self, step):
        errs = []
        if step.operation != "visit":
            errs.append(f"unexpected operation {step.operation!r}")
        for k in ("node", "position", "output_after"):
            if k not in step.inputs:
                errs.append(f"missing inputs.{k}")
        return errs

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        node = str(step.inputs["node"])
        return [] if node in prose else [("node_not_stated", node)]


# --- pre/post/level order traversals — verified siblings of inorder (were falling to unverified legacy) -------

def _preorder_walk(tree, root):
    """Preorder (node, left, right): output a node BEFORE its subtrees. Returns [(node, reason, [evidence])]."""
    out: list[tuple[int, str, list[str]]] = []

    def rec(n, parent, side):
        if n is None:
            return
        if parent is None:
            why, keys = f"the root {n} is output first — preorder outputs a node before its subtrees", ["root_first"]
        elif side == "left":
            why, keys = f"after {parent}, move left and output {n} before its own children", []
        else:
            why, keys = f"{parent}'s left subtree is finished, so move right and output {n}", ["right_branch"]
        out.append((n, why, keys))
        rec(tree[n]["left"], n, "left")
        rec(tree[n]["right"], n, "right")
    rec(root, None, None)
    return out


def _postorder_walk(tree, root):
    """Postorder (left, right, node): output a node only AFTER both its subtrees."""
    out: list[tuple[int, str, list[str]]] = []

    def rec(n):
        if n is None:
            return
        rec(tree[n]["left"])
        rec(tree[n]["right"])
        leaf = tree[n]["left"] is None and tree[n]["right"] is None
        why = (f"{n} is a leaf, so output it now" if leaf else
               f"both of {n}'s subtrees are fully output, so {n} comes last (postorder = subtrees, then node)")
        keys = (["leaf"] if leaf else []) + (["root_last"] if n == root else [])
        out.append((n, why, keys))
    rec(root)
    return out


def _levelorder_walk(tree, root):
    """Level-order (breadth-first): output every node on one level, left to right, before the next level.

    Each card names THIS node's parent + side and ties the order to the FIFO queue (why it comes out now),
    so the walkthrough teaches the mechanism rather than repeating one 'finish each level' rule per card."""
    out: list[tuple[int, str, list[str]]] = []
    q = deque([(root, 0, None, None)])                     # (node, depth, parent, side)
    while q:
        n, d, parent, side = q.popleft()
        if n is None:
            continue
        if d == 0:
            why = f"start at the root {n} — level-order begins at the top (level 0)"
        else:
            why = (f"{n} is the {side} child of {parent} (level {d}); {parent} enqueued it, and it now reaches "
                   f"the front of the queue — so every level {d - 1} node is output before it")
        out.append((n, why, ["root_level"] if d == 0 else ["deeper_level"]))
        q.append((tree[n]["left"], d + 1, n, "left"))
        q.append((tree[n]["right"], d + 1, n, "right"))
    return out


_TRAV_INV = [{"id": "all_visited", "scope": "final_only", "statement": "every node visited exactly once"}]


class _TreeTraversalBase(FamilyAdapterBase):
    """Shared machinery for the order traversals (pre/post/level). A subclass declares its slug, conventions,
    required cases, order word, and a `_walk(tree, root) -> [(node, reason, [evidence_keys])]`; the candidate
    generator, reference, Stage-0 gate, and hooks are shared with inorder's template."""
    label_convention = "ints"
    _walk = staticmethod(lambda tree, root: [])
    _conv: dict[str, Any] = {}
    _required: list[str] = []
    _order_word = "traversal"

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(4, 7)
            values = rng.sample(range(1, 41), n)          # distinct
            tree: dict[int, dict[str, Any]] = {}
            root: int | None = None
            for v in values:
                root = _insert(tree, root, v)
            yield {"tree": tree, "root": root, "insert_order": values, "_id": f"{self.slug}_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        ev = trace.case_evidence
        return len(trace.steps) >= 3 and all(ev.get(c) for c in self._required if c != "completion")

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        tree = example_input["tree"]
        root = example_input["root"]
        walk = self._walk(tree, root)
        order = [n for n, _, _ in walk]
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        output: list[int] = []
        for idx, (node, why, keys) in enumerate(walk, start=1):
            sid = f"s{idx}"
            prior = {"output": list(output), "current": node}
            output = output + [node]
            after = {"output": list(output), "current": node}
            for k in keys:
                evidence.setdefault(k, []).append(sid)
            steps.append(Step(
                id=sid, operation="visit", prior_state=prior, state_after=after,
                inputs={"node": node, "position": idx, "output_after": list(output)},
                decision=f"visit {node}", reason=why,
                visual_state={"kind": "tree", "visited": list(output), "current": node},
                visual_delta={"emitted": node},
                expected_visible_result=f"Visit {node}; output so far {output}.",
                # allow the node values + any integer that appears in the VERIFIED reason (e.g. level-order's
                # "level 2") — those are adapter-generated truth, not a model claim.
                facts={"allowed_values": sorted(set(tree.keys()) | {int(x) for x in re.findall(r"\d+", why)}),
                       "required_facts": [fact("visit", f"visit {node}")], "forbidden_claims": []}))
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Perform a {self._order_word} traversal of the binary search tree built by inserting "
                     f"{example_input['insert_order']} (root {root})."),
            conventions=dict(self._conv), initial_state={"output": [], "current": None},
            final_answer={"visit_order": order}, steps=steps,
            invariants=[dict(x) for x in _TRAV_INV], required_cases=list(self._required), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        return list((a or {}).get("output") or []) == list((b or {}).get("output") or [])

    def final_answer_entails(self, state, answer):
        return list((state or {}).get("output") or []) == list((answer or {}).get("visit_order") or [])

    def invariant_holds(self, inv, state):
        return True                                        # cardinality is checked by fidelity, not per-state

    def validate_step_shape(self, step):
        errs = []
        if step.operation != "visit":
            errs.append(f"unexpected operation {step.operation!r}")
        for k in ("node", "position", "output_after"):
            if k not in step.inputs:
                errs.append(f"missing inputs.{k}")
        return errs

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        node = str(step.inputs["node"])
        return [] if node in prose else [("node_not_stated", node)]


def _trav_spec(order_desc: str, focus: str, must: list[str], out_shape: str) -> ExampleSpec:
    return ExampleSpec(
        input=InstanceShape("integers", count=(4, 7), value_range=(1, 40), structure=["distinct", "bst"]),
        stages={"visit": StageSpec("visit", f"visit the next node in {order_desc} position", teaching_focus=focus,
                                   contains={"append this node's value to the output": "required"})},
        structure="visit+ until every node is output",
        must_exercise=must, must_avoid=["single_node_tree"],
        terminal="every node visited exactly once", output_shape=out_shape)


class PreorderTraversalAdapter(_TreeTraversalBase):
    slug = "tree_preorder"
    _walk = staticmethod(_preorder_walk)
    _conv = {"structure": "binary_search_tree", "order": "preorder (node, left, right)",
             "trace_granularity": "one_node_visit"}
    _required = ["root_first", "right_branch", "completion"]
    _order_word = "preorder"
    example_spec = _trav_spec("preorder", "a node is output BEFORE its subtrees (root first)",
                              ["root_first", "right_branch", "completion"], "the preorder node sequence")


class PostorderTraversalAdapter(_TreeTraversalBase):
    slug = "tree_postorder"
    _walk = staticmethod(_postorder_walk)
    _conv = {"structure": "binary_search_tree", "order": "postorder (left, right, node)",
             "trace_granularity": "one_node_visit"}
    _required = ["leaf", "root_last", "completion"]
    _order_word = "postorder"
    example_spec = _trav_spec("postorder", "a node is output AFTER both its subtrees (root last)",
                              ["leaf", "root_last", "completion"], "the postorder node sequence")


class LevelOrderTraversalAdapter(_TreeTraversalBase):
    slug = "tree_levelorder"
    _walk = staticmethod(_levelorder_walk)
    _conv = {"structure": "binary_tree", "order": "level-order (breadth-first, top to bottom)",
             "trace_granularity": "one_node_visit"}
    _required = ["root_level", "deeper_level", "completion"]
    _order_word = "level-order"
    example_spec = _trav_spec("level-order", "process the tree one level at a time, left to right (a queue)",
                              ["root_level", "deeper_level", "completion"], "the level-order node sequence")


class BSTSearchAdapter(FamilyAdapterBase):
    """T4 search/narrowing — the SECOND state model (a tree NODE, not array bounds). Building this proves the
    T4 type gate: the same 'search space strictly shrinks each probe' invariant must hold whether the space is
    an integer window [lo,hi] (binary_search) or a BST subtree. `remaining` = nodes still to examine."""
    slug = "bst_search"
    label_convention = "ints"
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(4, 7), value_range=(1, 40), structure=["distinct", "bst"]),
        stages={"probe": StageSpec(
            "probe", "compare the target to the current node, then go left / right / stop",
            teaching_focus="each comparison discards one whole subtree",
            contains={"compare": "required", "descend": "aggregated_supporting"},
            state_effects=["the search subtree shrinks; the target is found or ruled out"])},
        structure="probe+ until found or a null child is reached",
        must_exercise=["descend", "found_or_absent", "completion"],
        must_cover=["go_left", "go_right", "found", "absent"],     # per-SUITE (one search can't show all)
        must_avoid=["single_node_tree"],
        terminal="the target is found at a node or ruled absent", output_shape="found index / not-found")

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]:
        rng = random.Random(seed)
        for i in range(80):
            n = rng.randint(4, 7)
            values = rng.sample(range(1, 41), n)
            tree: dict[int, dict[str, Any]] = {}
            root: int | None = None
            for v in values:
                root = _insert(tree, root, v)
            present = rng.random() < 0.7
            target = rng.choice(values) if present else rng.choice([x for x in range(1, 41) if x not in values])
            yield {"tree": tree, "root": root, "target": target, "insert_order": values,
                   "_id": f"bst_search_v1_case_{i}"}

    def is_teaching_trace(self, trace: ContractTrace) -> bool:
        return len(trace.steps) >= 2 and bool(trace.case_evidence.get("found_or_absent"))

    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace:
        tree, root, target = example_input["tree"], example_input["root"], example_input["target"]
        steps: list[Step] = []
        evidence: dict[str, list[str]] = {}
        node = root
        idx = 0
        found_at: int | None = None
        while node is not None:
            idx += 1
            sid = f"s{idx}"
            prior = {"current": node, "remaining": _subtree_size(tree, node), "found": False}
            if target == node:
                after = {"current": node, "remaining": 0, "found": True}
                decision, reason = f"found {target}", f"{target} equals node {node}: found it"
                evidence.setdefault("found", []).append(sid)
                found_at = node
                nxt = None
            elif target < node:
                nxt = tree[node]["left"]
                after = {"current": nxt, "remaining": _subtree_size(tree, nxt), "found": False}
                decision = f"go left from {node}"
                reason = f"{target} < {node}, so the target can only be in {node}'s LEFT subtree"
                evidence.setdefault("go_left", []).append(sid)
                evidence.setdefault("descend", []).append(sid)
            else:
                nxt = tree[node]["right"]
                after = {"current": nxt, "remaining": _subtree_size(tree, nxt), "found": False}
                decision = f"go right from {node}"
                reason = f"{target} > {node}, so the target can only be in {node}'s RIGHT subtree"
                evidence.setdefault("go_right", []).append(sid)
                evidence.setdefault("descend", []).append(sid)
            terminal = after["found"] or nxt is None
            if terminal:
                evidence.setdefault("found_or_absent", []).append(sid)
                if not after["found"]:
                    evidence.setdefault("absent", []).append(sid)
            rem = after["remaining"]
            if after["found"]:
                evr = f"Compare {target} with {node}: FOUND at this node — search complete."
            elif nxt is None:                                  # the chosen subtree is empty → target absent
                side = "left" if "left" in decision else "right"
                evr = (f"Compare {target} with {node}: go {side}, but {node} has no {side} child — "
                       f"the target is absent.")
                reason += f" — but {node} has no {side} child, so the target is absent"
            else:                                              # descend: the search space shrinks
                side = "left" if "left" in decision else "right"
                evr = (f"Compare {target} with {node}: go {side}; "
                       f"{rem} node{'s' if rem != 1 else ''} still to search.")
            steps.append(Step(
                id=sid, operation="probe", prior_state=prior, state_after=after,
                inputs={"node": node, "target": target, "remaining": after["remaining"]},
                decision=decision, reason=reason,
                visual_state={"kind": "tree", "current": node, "target": target},
                visual_delta={"compared": node},
                expected_visible_result=evr,
                facts={"allowed_values": sorted(set(tree.keys()) | {target, after["remaining"]}),
                       "required_facts": [fact("compare", f"{target}"), fact("node", f"{node}")],
                       "forbidden_claims": []}))
            if terminal:
                break
            node = nxt
        if steps:
            evidence.setdefault("completion", []).append(steps[-1].id)
        return ContractTrace(
            problem=(f"Search the binary search tree built from {example_input['insert_order']} for the "
                     f"value {target}."),
            conventions={"structure": "binary_search_tree", "rule": "target<node -> left; target>node -> right",
                         "trace_granularity": "one_comparison"},
            initial_state={"current": root, "remaining": _subtree_size(tree, root), "found": False},
            final_answer={"found": found_at is not None, "found_at": found_at}, steps=steps,
            invariants=[{"id": "space_shrinks", "scope": "every_step",
                         "statement": "the search subtree strictly shrinks each probe"}],
            required_cases=["descend", "found_or_absent", "completion"], case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        a, b = a or {}, b or {}
        return (a.get("current") == b.get("current") and a.get("remaining") == b.get("remaining")
                and bool(a.get("found")) == bool(b.get("found")))

    def final_answer_entails(self, state, answer):
        st, an = state or {}, answer or {}
        return bool(st.get("found")) == bool(an.get("found")) and (
            not an.get("found") or st.get("current") == an.get("found_at"))

    def invariant_holds(self, inv, state):
        return True                                         # the shrink is checked step-to-step by fidelity

    def validate_step_shape(self, step):
        errs = []
        if step.operation != "probe":
            errs.append(f"unexpected operation {step.operation!r}")
        for k in ("node", "target", "remaining"):
            if k not in step.inputs:
                errs.append(f"missing inputs.{k}")
        return errs

    def validate_prose_claims(self, card, step):
        prose = " ".join([str(card.get("reasoning", "")), " ".join(card.get("work") or []),
                          str(card.get("result", ""))]).lower()
        return [] if str(step.inputs["target"]) in prose else [("target_not_stated", str(step.inputs["target"]))]
