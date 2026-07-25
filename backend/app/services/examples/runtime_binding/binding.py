"""Deterministic binding (spec §5.4, §5.6) — no model call in v1a.

A `BindingProposal` maps reviewed grammar slots onto reviewed contract symbols. For
`direct_formula_calculation` this is fully determined by the contract, so v1a builds it deterministically:
given_symbols = contract inputs, unknown_symbol = output, relationship = the contract relationship. Validation
compiles the relationship onto the Milestone A substrate (reusing the proven executor) and produces a
`binding_digest` covering every execution-affecting identity, so a cache/preparation can detect any change.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

from app.services.examples.runtime_binding.artifacts import AuthoredRelationshipDescriptor
from app.services.examples.runtime_binding.contract import ConceptContract, compile_contract_descriptor
from app.services.examples.runtime_binding.grammar import GrammarManifest
from app.services.examples.runtime_binding.policy import numeric_unit_policy_digest
from app.services.examples.runtime_binding.resolution import ContractConceptResolution
from app.services.examples.runtime_binding.restricted_expression import expression_canonical_digest


class BindingError(ValueError):
    pass


@dataclass(frozen=True)
class BindingProposal:
    concept_contract_id: str
    grammar_id: str
    grammar_version: int
    relationship_ref: str
    slot_bindings: tuple[tuple[str, tuple[str, ...]], ...]   # (slot_id, bound symbol names)
    convention_selections: tuple[tuple[str, str], ...] = ()
    proposal_source: Literal["deterministic", "model"] = "deterministic"


@dataclass(frozen=True)
class ValidatedBinding:
    proposal: BindingProposal
    contract: ConceptContract
    resolution: ContractConceptResolution
    grammar: GrammarManifest
    descriptor: AuthoredRelationshipDescriptor
    binding_digest: str


def propose_binding(
    contract: ConceptContract, grammar: GrammarManifest
) -> BindingProposal:
    if contract.relationship.grammar_id != grammar.grammar_id:
        raise BindingError(
            f"{contract.contract_id}: relationship grammar {contract.relationship.grammar_id!r} "
            f"!= {grammar.grammar_id!r}"
        )
    inputs = tuple(s.symbol for s in contract.input_symbols)
    if not inputs:
        raise BindingError(f"{contract.contract_id}: at least one input symbol required")
    slot_bindings = (
        ("given_symbols", inputs),
        ("unknown_symbol", (contract.output.symbol,)),
        ("relationship", (contract.relationship.relationship_id,)),
    )
    conventions = tuple(sorted((c.artifact_id, c.normalized_value) for c in contract.conventions))
    return BindingProposal(
        concept_contract_id=contract.contract_id,
        grammar_id=grammar.grammar_id,
        grammar_version=grammar.version,
        relationship_ref=contract.relationship.relationship_id,
        slot_bindings=slot_bindings,
        convention_selections=conventions,
        proposal_source="deterministic",
    )


def _binding_digest(
    proposal: BindingProposal,
    resolution: ContractConceptResolution,
    contract: ConceptContract,
    descriptor: AuthoredRelationshipDescriptor,
) -> str:
    payload = {
        "resolution_registry_version": resolution.resolution_registry_version,
        "resolution_entry_version": resolution.resolution_entry_version,
        "concept_contract_id": contract.contract_id,
        "concept_contract_version": contract.version,
        "relationship_id": proposal.relationship_ref,
        "expression_canonical_digest": expression_canonical_digest(descriptor.expression),
        "grammar_id": proposal.grammar_id,
        "grammar_version": proposal.grammar_version,
        "slot_bindings": [[slot, list(names)] for slot, names in proposal.slot_bindings],
        "convention_selections": [[k, v] for k, v in proposal.convention_selections],
        "numeric_unit_policy_digest": numeric_unit_policy_digest(),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def validate_binding(
    contract: ConceptContract,
    resolution: ContractConceptResolution,
    grammar: GrammarManifest,
    proposal: BindingProposal | None = None,
) -> ValidatedBinding:
    if resolution.status != "resolved" or resolution.resolution_validity != "reviewed_match":
        raise BindingError(
            f"{contract.contract_id}: binding requires a reviewed_match resolution, "
            f"got {resolution.status}/{resolution.resolution_validity}"
        )
    if resolution.contract_id != contract.contract_id:
        raise BindingError(
            f"resolution contract {resolution.contract_id!r} != {contract.contract_id!r}"
        )
    proposal = proposal or propose_binding(contract, grammar)
    # every relationship node must be in the grammar allowlist (defense in depth over the compiler)
    descriptor = compile_contract_descriptor(contract)
    bound_inputs = dict(proposal.slot_bindings)["given_symbols"]
    contract_inputs = tuple(s.symbol for s in contract.input_symbols)
    if tuple(sorted(bound_inputs)) != tuple(sorted(contract_inputs)):
        raise BindingError(f"{contract.contract_id}: slot inputs {bound_inputs} != contract inputs {contract_inputs}")
    digest = _binding_digest(proposal, resolution, contract, descriptor)
    return ValidatedBinding(
        proposal=proposal,
        contract=contract,
        resolution=resolution,
        grammar=grammar,
        descriptor=descriptor,
        binding_digest=digest,
    )
