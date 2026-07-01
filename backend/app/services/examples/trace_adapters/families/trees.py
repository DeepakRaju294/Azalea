"""Tree family (ADAPTER_CATALOG A2) — a parent/child binary-tree structure (NO visited-set / cycle handling,
unlike the graph family). Members here: inorder BST traversal. Future: pre/post/level order, BST search /
insert / delete, heap ops, trie, LCA.

TEMPLATE — this is the reference *coding* adapter every new coding concept follows. It shows the full
contract: an `ExampleSpec` (input shape + stage grammar + required cases + terminal), a `candidates()`
generator, a `reference()` that runs the REAL algorithm to produce a verified `ContractTrace` (no LLM), the
Stage-0 `is_teaching_trace` gate, the equivalence/entailment/invariant hooks, and structured `fact()` facts.
A coding adapter additionally ships a canonical solution (see `canonical_solutions.py::tree_inorder`)."""
from __future__ import annotations

import random
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


class InorderTraversalAdapter(FamilyAdapterBase):
    slug = "tree_inorder"
    label_convention = "ints"                  # §2.3 — BST node values are integers
    example_spec = ExampleSpec(
        input=InstanceShape("integers", count=(4, 7), value_range=(1, 40), structure=["distinct", "bst"]),
        stages={"visit": StageSpec(
            "visit", "visit the next node in inorder position",
            teaching_focus="a node is output only after its entire left subtree",
            contains={"emit_node": "required", "advance_to_right_subtree": "aggregated_supporting"},
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
            final_answer={"inorder": order}, steps=steps,
            invariants=[dict(x) for x in _INV], required_cases=list(_REQUIRED), case_evidence=evidence,
            provenance=self._provenance(seed=seed, candidate_id=candidate_id, example_input=example_input,
                                        attempt=attempt))

    def states_equivalent(self, a, b):
        return list((a or {}).get("output") or []) == list((b or {}).get("output") or [])

    def final_answer_entails(self, state, answer):
        return list((state or {}).get("output") or []) == list((answer or {}).get("inorder") or [])

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
