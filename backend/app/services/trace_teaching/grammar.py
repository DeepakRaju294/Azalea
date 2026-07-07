"""The real trace step grammar (Q23 §2) + the typed schemas from §§6–8.

Keys off the uniform step grammar the type-engines emit, not per-adapter data. The §§6–8 typed shapes
(required_facts with fact_id/acceptable_renderings, structural forbidden_claims, the operation-intent vocabulary)
are the engine-side metadata this contract validates against.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class AllowedQuantity:
    """A quantity a step exposes, with a STABLE quantity_id (names repeat across a derivation)."""
    quantity_id: str
    name: str
    value: str                       # literal, normalized by numeric.canonical_number
    unit: Optional[str] = None
    output_name: Optional[str] = None
    fact_id: Optional[str] = None


@dataclass(frozen=True)
class RequiredFact:
    """§6 — a fact the step's prose MUST state, matched deterministically (not LLM-graded)."""
    fact_id: str
    kind: str
    subject: str
    relation: str
    value: str
    acceptable_renderings: Tuple[str, ...]
    required_in_fields: Tuple[str, ...]


@dataclass(frozen=True)
class ForbiddenClaim:
    """§7 — a structurally-encoded forbidden claim; known_phrasings is a fast first pass, not complete (C6 backstop)."""
    claim_type: str
    subject: str
    forbidden_when: Dict[str, str]   # {"trace_field": <name>, "equals": <value>}
    known_phrasings: Tuple[str, ...]


@dataclass(frozen=True)
class OperationContract:
    """§8 — the operation-intent vocabulary that makes C5 deterministic."""
    operation: str
    allowed_action_intents: Tuple[str, ...]
    forbidden_action_intents: Tuple[str, ...]


@dataclass(frozen=True)
class Step:
    id: str
    operation: str
    expected_visible_result: str = ""
    state_after: Dict[str, str] = field(default_factory=dict)
    allowed_values: Tuple[str, ...] = ()            # facts.allowed_values (∪ authoritative literals, below)
    allowed_quantities: Tuple[AllowedQuantity, ...] = ()
    required_facts: Tuple[RequiredFact, ...] = ()
    forbidden_claims: Tuple[ForbiddenClaim, ...] = ()
    trace_field_values: Dict[str, str] = field(default_factory=dict)   # e.g. {"motion_direction": "unchanged"}
    operation_contract: Optional[OperationContract] = None

    def all_allowed_values(self) -> Tuple[str, ...]:
        """allowed_values ∪ the step's authoritative literals (state_after + quantity values)."""
        vals = list(self.allowed_values)
        vals.extend(str(v) for v in self.state_after.values())
        vals.extend(q.value for q in self.allowed_quantities)
        return tuple(vals)


@dataclass(frozen=True)
class Trace:
    trace_id: str
    steps: Tuple[Step, ...] = ()
    required_operations: Tuple[str, ...] = ()
