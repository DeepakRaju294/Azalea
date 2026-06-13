"""Simulator registry (VISUAL_SYSTEM_SPEC §6.1).

Registered algorithms own their trace (simulator-first). Unregistered/fuzzy
topics fall through to the LLM-authored delta timeline + validators.
"""
from __future__ import annotations

from typing import Callable

from ..schemas import CanonicalExample, Trace
from .array import simulate_binary_search
from .code_tracer import simulate_code_execution
from .concept_visuals import (
    simulate_function_plot,
    simulate_protocol_sequence,
    simulate_set_operation,
    simulate_stack_heap,
    simulate_comparison,
    simulate_triangle_geometry,
)
from .graph import simulate_bfs, simulate_dfs
from .grid import simulate_coin_change, simulate_unique_paths
from .symbolic import (
    simulate_compound_interest,
    simulate_distance_formula,
    simulate_linear_equation,
    simulate_induction_proof,
    simulate_quadratic_formula,
)

Simulator = Callable[[CanonicalExample], Trace]

_REGISTRY: dict[str, Simulator] = {
    "bfs": simulate_bfs,
    "dfs": simulate_dfs,
    "binary_search": simulate_binary_search,
    "code_execution": simulate_code_execution,
    "unique_paths": simulate_unique_paths,
    "quadratic_formula": simulate_quadratic_formula,
    "linear_equation": simulate_linear_equation,
    "distance_formula": simulate_distance_formula,
    "compound_interest": simulate_compound_interest,
    "coin_change": simulate_coin_change,
    "set_operation": simulate_set_operation,
    "function_graph_analysis": simulate_function_plot,
    "stack_heap_allocation": simulate_stack_heap,
    "protocol_sequence": simulate_protocol_sequence,
    "triangle_geometry": simulate_triangle_geometry,
    "induction_proof": simulate_induction_proof,
    "algorithm_comparison": simulate_comparison,
}


def get_simulator(algorithm: str | None) -> Simulator | None:
    if not algorithm:
        return None
    return _REGISTRY.get(algorithm)


def is_registered(algorithm: str | None) -> bool:
    return bool(algorithm) and algorithm in _REGISTRY


def registered_algorithms() -> list[str]:
    return sorted(_REGISTRY)
