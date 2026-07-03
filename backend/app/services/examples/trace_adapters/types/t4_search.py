"""T4 — Search / narrowing. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.sequence import BinarySearchAdapter
from ..families.trees import BSTSearchAdapter

BINARY_SEARCH = declare(BinarySearchAdapter, "binary_search", "T4")
BST_SEARCH = declare(BSTSearchAdapter, "bst_search", "T4")

DECLARATIONS = [BINARY_SEARCH, BST_SEARCH]
