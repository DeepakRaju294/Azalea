"""T8A — Incremental construction. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.sequence import BubbleSortAdapter, HeapSortAdapter, InsertionSortAdapter, SelectionSortAdapter
from ..families.number_theory import SieveAdapter
from ..families.construct_engine import construct_decl, registered_specs

INSERTION_SORT = declare(InsertionSortAdapter, "insertion_sort", "T8a")
SELECTION_SORT = declare(SelectionSortAdapter, "selection_sort", "T8a")
BUBBLE_SORT = declare(BubbleSortAdapter, "bubble_sort", "T8a")
HEAP_SORT = declare(HeapSortAdapter, "heap_sort", "T8a")
SIEVE_OF_ERATOSTHENES = declare(SieveAdapter, "sieve_of_eratosthenes", "T8a")

# CP12d — Construction Engine concept rows (families/construction_specs.py). Each ConstructSpec becomes an
# adapter; its family + routing come from the spec, so adding a construction concept is a one-file edit.
_CONSTRUCT_DECLS = [construct_decl(s) for s in registered_specs()]

DECLARATIONS = [INSERTION_SORT, SELECTION_SORT, BUBBLE_SORT, HEAP_SORT, SIEVE_OF_ERATOSTHENES, *_CONSTRUCT_DECLS]
