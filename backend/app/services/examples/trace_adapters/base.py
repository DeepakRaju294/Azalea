"""Adapter protocol for the trace pipeline. An algorithm adapter is the ONLY place algorithm-specific
knowledge lives — the reference run, state equivalence, invariants, final-answer entailment, the Stage-0
teaching gate, and prose facts. Everything else (the contract, fidelity, orchestration) is generic.
"""
from __future__ import annotations

from typing import Any, Iterable, Protocol

from ..trace_contract import ContractTrace, Step


class TraceAdapter(Protocol):
    slug: str
    version: int

    def candidates(self, seed: int) -> Iterable[dict[str, Any]]: ...      # Stage 0 inputs (deterministic for seed)
    def reference(self, example_input: dict[str, Any], *, candidate_id: str = "",
                  attempt: int = 1, seed: int = 0) -> ContractTrace: ...   # adapter-owned validated run -> full trace
    def is_teaching_trace(self, trace: ContractTrace) -> bool: ...         # Stage 0 quality gate
    def states_equivalent(self, a: dict[str, Any], b: dict[str, Any]) -> bool: ...
    def final_answer_entails(self, state: dict[str, Any], answer: Any) -> bool: ...
    def invariant_holds(self, inv: dict[str, Any], state: dict[str, Any]) -> bool: ...
    def validate_step_shape(self, step: Step) -> list[str]: ...
    def validate_prose_claims(self, card: dict[str, Any], step: Step) -> list[tuple[str, str]]: ...
