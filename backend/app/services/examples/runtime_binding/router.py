"""Offline runtime-binding orchestration (spec §4, Milestone B).

`bind_offline` runs the full offline chain for ONE scope concept: prove the registered adapter lookup MISSES,
then resolve -> bind -> generate -> build the neutral problem -> trace -> verify -> freeze immutable evidence.
It never touches a live solver route, `we_policy`, persistence, or the frontend (Milestone C). The registered
lookup is injected so the test can use the real router without this module importing routing policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from app.services.examples.runtime_binding.binding import validate_binding
from app.services.examples.runtime_binding.contract import ConceptContract
from app.services.examples.runtime_binding.evidence import EvidencePackage, freeze_evidence
from app.services.examples.runtime_binding.generation import GeneratedInstance, generate_instance
from app.services.examples.runtime_binding.grammar import GRAMMARS
from app.services.examples.runtime_binding.problem import ProblemStatement, build_problem_statement
from app.services.examples.runtime_binding.resolution import ContractResolutionRegistry
from app.services.examples.runtime_binding.trace import TraceBundle, build_trace_bundle
from app.services.examples.runtime_binding.verification import VerificationVector, run_verification

# lookup_fn(scope_concept_id) -> registered adapter/owner or None. A non-None result means DO NOT bind.
RegisteredLookup = Callable[[str], Optional[object]]


class RoutingError(ValueError):
    pass


@dataclass(frozen=True)
class OfflineBindingResult:
    scope_concept_id: str
    decision: str                      # "runtime_binding_evidence" | "registered_adapter_wins" | "withheld"
    registered_owner: Optional[str]
    evidence: Optional[EvidencePackage]
    problem: Optional[ProblemStatement]
    trace_bundle: Optional[TraceBundle]
    verification: Optional[VerificationVector]
    reason: str = ""


def bind_offline(
    scope_concept_id: str,
    *,
    contracts: dict[str, ConceptContract],
    registry: ContractResolutionRegistry,
    registered_lookup: RegisteredLookup,
    seed: int = 0,
    requested_variant: str | None = None,
) -> OfflineBindingResult:
    # 1) registered adapter must genuinely MISS before runtime binding runs
    owner = registered_lookup(scope_concept_id)
    if owner is not None:
        return OfflineBindingResult(
            scope_concept_id, "registered_adapter_wins", getattr(owner, "slug", str(owner)),
            None, None, None, None, "registered adapter owns this concept",
        )

    # 2) reviewed resolution (reviewed_match only)
    resolution = registry.resolve(scope_concept_id, requested_variant=requested_variant)
    if resolution.status != "resolved" or resolution.resolution_validity != "reviewed_match":
        return OfflineBindingResult(
            scope_concept_id, "withheld", None, None, None, None, None,
            f"resolution {resolution.status}/{resolution.resolution_validity}",
        )
    contract = contracts.get(resolution.contract_id)
    if contract is None:
        return OfflineBindingResult(
            scope_concept_id, "withheld", None, None, None, None, None,
            f"resolved contract {resolution.contract_id} not in fixture set",
        )

    grammar = GRAMMARS[contract.relationship.grammar_id]
    binding = validate_binding(contract, resolution, grammar)
    instance: GeneratedInstance = generate_instance(binding, seed=seed)
    problem = build_problem_statement(binding, instance)
    bundle = build_trace_bundle(binding, instance)
    verification = run_verification(binding, instance, bundle)
    if not verification.passed:
        return OfflineBindingResult(
            scope_concept_id, "withheld", None, None, problem, bundle, verification,
            "verification vector did not pass",
        )
    evidence = freeze_evidence(binding, instance, bundle, verification)
    return OfflineBindingResult(
        scope_concept_id, "runtime_binding_evidence", None, evidence, problem, bundle, verification,
        "reviewed-contract runtime binding produced verified evidence",
    )
