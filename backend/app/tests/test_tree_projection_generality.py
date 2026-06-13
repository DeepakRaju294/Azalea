"""Generality proof: the projector subsumes tree traversal (PROJECTOR_SYSTEM_SPEC §12).

Tree traversal is a graph walk with `visited` + `current`. One projector — the SAME one
that handles BFS/Dijkstra/Prim — produces a correct inorder highlight sequence over a
BST, with no tree-specific code. This is the litmus test that the generalization is real:
once proven, the legacy `_looks_like_tree_traversal` normalization is retireable.

(Deletion of that legacy path is intentionally deferred until live testing confirms the
projector path, with the existing BST goldens as the safety gate.)

Run: python -m unittest app.tests.test_tree_projection_generality
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from app.services.visual_v2.delta_fold import DeltaFoldEngine
from app.services.visual_v2.profiles import delta_vocabulary, profile_for_mode
from app.services.visual_v2.compilers import node_link as node_link_compiler
from app.services.visual_v2.projectors.node_link import (
    GraphProjection,
    project_node_link,
    validate_projection,
)
from app.services.visual_v2.simulators.code_tracer import trace_execution

# Iterative inorder traversal of a binary tree.
INORDER = '''
def inorder(root):
    result = []
    stack = []
    node = root
    while stack or node is not None:
        while node is not None:
            stack.append(node)
            node = node.left
        node = stack.pop()
        result.append(node.val)
        node = node.right
    return result
'''

# BST (level-order) — inorder yields the sorted sequence.
_BST = [50, 30, 70, 20, 40, 60, 80]
_SORTED = sorted(_BST)
_BASE = {
    "nodes": [str(v) for v in _BST],
    "edges": [["50", "30"], ["50", "70"], ["30", "20"], ["30", "40"], ["70", "60"], ["70", "80"]],
}


class TestTreeProjectionGenerality(unittest.TestCase):
    def setUp(self):
        self.steps, _ = trace_execution(INORDER, "inorder", {"tree": _BST})
        # `node` serializes to its .val; `result` is the val sequence. node_key=identity.
        self.proj = GraphProjection(current_from="node", visit_order_from="result")

    def test_projection_validates(self):
        self.assertEqual(validate_projection(self.steps, _BASE, self.proj), [])

    def test_projected_order_is_the_inorder_sequence(self):
        result = project_node_link(self.steps, _BASE, self.proj)
        frames = DeltaFoldEngine().fold(
            result.initial_state(), result.deltas, set(_BASE["nodes"]), delta_vocabulary("graph_network")
        )
        model, _ = node_link_compiler.compile_from_trace(
            trace={"steps": result.deltas}, frames=frames, base_structure=_BASE,
            profile=profile_for_mode("graph_network"), mode="graph_network", model_id="tree",
        )
        # The output panel of the terminal frame is the inorder (sorted) order.
        final_output = model["frames"][-1]["state"]["runtime_state"]["output"]
        self.assertEqual([str(x) for x in final_output], [str(v) for v in _SORTED])
        # Every node ends visited (no node left un-highlighted — the old tree bug).
        visited = {e["node_id"] for e in model["frames"][-1]["state"]["node_state_map"]
                   if e["state"] in ("completed", "current")}
        self.assertEqual(visited, set(_BASE["nodes"]))


if __name__ == "__main__":
    unittest.main()
