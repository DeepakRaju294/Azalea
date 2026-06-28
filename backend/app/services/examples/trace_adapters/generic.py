"""Generic adapter for reason→extract (non-deterministic) traces (WORKED_EXAMPLE_REASONING_SPEC.md §6,
soft classes). No algorithm semantics: structural equality, the trace's own declared invariants are
advisory, and CORRECTNESS is established by the Stage-2 critic (verifiers.verify_via_critic), not here.
Used when no deterministic adapter matches and the reason→extract path is enabled."""
from __future__ import annotations

from typing import Any

from ..trace_contract import Step


class GenericAdapter:
    slug = "generic"
    version = 1

    def states_equivalent(self, a: dict[str, Any], b: dict[str, Any]) -> bool:
        return (a or {}) == (b or {})

    def final_answer_entails(self, state: dict[str, Any], answer: Any) -> bool:
        # lenient: the answer's key/values are present in the final state, or the state equals it; the
        # critic does the real verification for soft classes.
        if isinstance(answer, dict) and isinstance(state, dict):
            return all(state.get(k) == v for k, v in answer.items()) or state == answer
        return True

    def invariant_holds(self, inv: dict[str, Any], state: dict[str, Any]) -> bool:
        return True   # declared invariants are advisory for soft classes; the critic verifies legality

    def validate_step_shape(self, step: Step) -> list[str]:
        errs = []
        if not step.id:
            errs.append("step missing id")
        if not isinstance(step.prior_state, dict) or not isinstance(step.state_after, dict):
            errs.append("states must be dicts")
        return errs

    def validate_prose_claims(self, card: dict[str, Any], step: Step) -> list[tuple[str, str]]:
        return []   # generic fact-bundle guard in trace_contract.validate_prose covers it
