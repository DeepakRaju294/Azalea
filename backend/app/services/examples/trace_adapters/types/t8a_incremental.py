"""T8A — Incremental construction. Adapter declarations (migrated onto the declarative infra).

The adapter IMPLEMENTATIONS (reference + hooks) still live in their family module (shared machinery
by family); this TYPE file owns their declarations (type + routing + canonical), grouped by type.
Byte-identical to the pre-migration classes (see the all-adapters golden check).
"""
from . import declare
from ..families.sequence import BubbleSortAdapter, HeapSortAdapter, InsertionSortAdapter, SelectionSortAdapter
from ..families.number_theory import SieveAdapter

INSERTION_SORT = declare(InsertionSortAdapter, "insertion_sort", "T8a")
SELECTION_SORT = declare(SelectionSortAdapter, "selection_sort", "T8a")
BUBBLE_SORT = declare(BubbleSortAdapter, "bubble_sort", "T8a")
HEAP_SORT = declare(HeapSortAdapter, "heap_sort", "T8a")
SIEVE_OF_ERATOSTHENES = declare(SieveAdapter, "sieve_of_eratosthenes", "T8a")

DECLARATIONS = [INSERTION_SORT, SELECTION_SORT, BUBBLE_SORT, HEAP_SORT, SIEVE_OF_ERATOSTHENES]
