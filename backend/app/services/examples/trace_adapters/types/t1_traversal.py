"""T1 — structured traversal (visit the next node/element via a frontier). Type template + declarations.

The tree order-traversals (pre/post/level) already share ONE reference + hooks (`_TreeTraversalBase`); that
shared class IS the type template. A traversal declaration supplies only its deltas: the walk function, the
conventions, the required cases, the order word, and its ExampleSpec. `hydrate` reuses the base's exact
methods (so traces are byte-identical to the old subclasses) and injects the deltas as class attributes.

This is the first real migration onto the declarative infra. Graph traversals (BFS/DFS) and inorder can move
here next; for now they stay as classes and this module owns the three order-traversal siblings.
"""
from __future__ import annotations

from ..decl import AdapterDecl, _REQUIRED_METHODS
from ..families.trees import (_levelorder_walk, _postorder_walk, _preorder_walk, _trav_spec,
                              _TreeTraversalBase)

# The T1 traversal TEMPLATE = the exact methods shared by every order-traversal (reference, hooks, gate).
_TEMPLATE_METHODS = {name: getattr(_TreeTraversalBase, name) for name in _REQUIRED_METHODS}


def _traversal_decl(slug, *, walk, conv, required, order_word, spec, routing) -> AdapterDecl:
    return AdapterDecl(
        slug=slug, type="T1", family="trees", example_spec=spec, methods=dict(_TEMPLATE_METHODS),
        label_convention="ints", routing=routing, canonical=slug,
        class_attrs={"_walk": staticmethod(walk), "_conv": conv, "_required": required,
                     "_order_word": order_word})


TREE_PREORDER = _traversal_decl(
    "tree_preorder", walk=_preorder_walk, order_word="preorder",
    conv={"structure": "binary_search_tree", "order": "preorder (node, left, right)",
          "trace_granularity": "one_node_visit"},
    required=["root_first", "right_branch", "completion"],
    spec=_trav_spec("preorder", "a node is output BEFORE its subtrees (root first)",
                    ["root_first", "right_branch", "completion"], "the preorder node sequence"),
    routing={"any": ["preorder", "pre-order"], "priority": 280})

TREE_POSTORDER = _traversal_decl(
    "tree_postorder", walk=_postorder_walk, order_word="postorder",
    conv={"structure": "binary_search_tree", "order": "postorder (left, right, node)",
          "trace_granularity": "one_node_visit"},
    required=["leaf", "root_last", "completion"],
    spec=_trav_spec("postorder", "a node is output AFTER both its subtrees (root last)",
                    ["leaf", "root_last", "completion"], "the postorder node sequence"),
    routing={"any": ["postorder", "post-order"], "priority": 270})

TREE_LEVELORDER = _traversal_decl(
    "tree_levelorder", walk=_levelorder_walk, order_word="level-order",
    conv={"structure": "binary_tree", "order": "level-order (breadth-first, top to bottom)",
          "trace_granularity": "one_node_visit"},
    required=["root_level", "deeper_level", "completion"],
    spec=_trav_spec("level-order", "process the tree one level at a time, left to right (a queue)",
                    ["root_level", "deeper_level", "completion"], "the level-order node sequence"),
    routing={"any": ["level order", "level-order", "levelorder"], "priority": 260})

DECLARATIONS = [TREE_PREORDER, TREE_POSTORDER, TREE_LEVELORDER]


# Migrated onto the infra alongside the template-built siblings: inorder (its own class) + the
# graph traversals BFS/DFS (T1, but the graph family). Their implementations stay in their family.
from . import declare as _declare
from ..families.trees import InorderTraversalAdapter as _Inorder
from ..families.graph import BFSAdapter as _BFS, DFSIterativeAdapter as _DFS
TREE_INORDER = _declare(_Inorder, "tree_inorder", "T1")
BFS = _declare(_BFS, "bfs", "T1")
DFS_ITER = _declare(_DFS, "dfs_iter", "T1")
DECLARATIONS = DECLARATIONS + [TREE_INORDER, BFS, DFS_ITER]
