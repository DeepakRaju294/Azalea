"""Shared state normalizers (WORKED_EXAMPLE_REASONING_SPEC.md §15, level 1).

Canonicalize DATA only — no algorithm semantics. Adapters call these so "same state" is semantic
(component sets order-independent, visited list-vs-set, etc.) rather than serialization-equal.
"""
from __future__ import annotations

from typing import Any, Iterable


def states_equal(a: dict[str, Any] | None, b: dict[str, Any] | None, *,
                 ordered: Iterable[str] = (), as_set: Iterable[str] = ()) -> bool:
    """Compare two states key-by-key: `ordered` keys compared as sequences (order matters — queue/stack),
    `as_set` keys compared as unordered sets (visited), everything else by value."""
    a, b = a or {}, b or {}
    ordered, as_set = set(ordered), set(as_set)
    for k in set(a) | set(b):
        if k in as_set:
            if frozenset(a.get(k) or []) != frozenset(b.get(k) or []):
                return False
        elif k in ordered:
            if list(a.get(k) or []) != list(b.get(k) or []):
                return False
        elif a.get(k) != b.get(k):
            return False
    return True


def components_equal(a: Iterable[Iterable[Any]], b: Iterable[Iterable[Any]]) -> bool:
    """Disjoint-set partitions equal regardless of group order or within-group order."""
    return {frozenset(g) for g in (a or [])} == {frozenset(g) for g in (b or [])}


def canon_components(groups: Iterable[Iterable[Any]]) -> list[list[Any]]:
    """A stable display form: each group sorted, groups sorted by their first element."""
    return sorted((sorted(g) for g in groups), key=lambda g: (g[0] if g else None))
